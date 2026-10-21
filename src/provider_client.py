"""Bounded Chat Completions SSE parsing; never expose provider error bodies."""
import json
import os
import time
from email.utils import parsedate_to_datetime

import httpx

from src.provider_limits import LimitError

ENDPOINTS = {"nvidia": "https://integrate.api.nvidia.com/v1",
             "nebius": "https://api.tokenfactory.nebius.com/v1"}


class ProviderError(RuntimeError):
    def __init__(self, provider, status=None, *, retryable=False, retry_after=0, cause=None):
        # cause is a fixed internal code, never provider-supplied text.
        self.status, self.cause = status, cause
        self.retryable, self.retry_after = retryable, retry_after
        super().__init__(f"{provider} generation unavailable" + (f" (HTTP {status})" if status else "")
                         + (f" [{cause}]" if cause else ""))


def client():
    return httpx.AsyncClient(timeout=httpx.Timeout(65, connect=10), follow_redirects=False)


def input_bound(payload):
    # UTF-8 byte fallback bounds text tokens; include ample framing overhead for
    # message roles and function schemas, not a chars/4 optimistic cost estimate.
    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return size + 2048 + 64 * len(payload.get("messages", []))


def retry_delay(value):
    try:
        return max(0, float(value)) if value.replace(".", "", 1).isdigit() else max(0, parsedate_to_datetime(value).timestamp()-time.time())
    except (ValueError, TypeError, OverflowError):
        return 0


async def complete(http, selected, payload, *, key):
    """Yield text deltas followed by one validated transport result."""
    base = os.getenv(selected.provider.upper() + "_BASE_URL") or ENDPOINTS[selected.provider]
    if base.rstrip("/") != ENDPOINTS[selected.provider]:
        raise LimitError("Generation endpoint must match the selected provider")
    calls, finish, usage, done = {}, None, None, False
    content_size, argument_size = 0, 0
    try:
        async with http.stream("POST", base.rstrip("/") + "/chat/completions",
                               headers={"Authorization": "Bearer " + key}, json=payload) as response:
            if response.status_code != 200:
                retry_after = response.headers.get("retry-after", "0")
                delay = retry_delay(retry_after)
                raise ProviderError(selected.provider, response.status_code,
                                    retryable=response.status_code in (429, 500, 502, 503, 504), retry_after=delay)
            async for line in response.aiter_lines():
                if len(line) > 1048576:
                    raise ProviderError(selected.provider, cause="oversized_line")
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                message = json.loads(data)
                if message.get("error"):
                    raise ProviderError(selected.provider, cause="stream_error_event")
                if message.get("usage"):
                    usage = message["usage"]
                # Providers may send explicit nulls for absent fields.
                for choice in message.get("choices") or []:
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
                    delta = choice.get("delta") or {}
                    text = delta.get("content") or ""
                    if text:
                        content_size += len(text)
                        if content_size > 262144:
                            raise ProviderError(selected.provider, cause="oversized_content")
                        yield {"type": "text", "data": text}
                    for call in delta.get("tool_calls") or []:
                        index = call["index"]
                        if type(index) is not int or not 0 <= index < 24:
                            raise ProviderError(selected.provider, cause="invalid_tool_index")
                        row = calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        if call.get("id"):
                            if row["id"] and row["id"] != call["id"]:
                                raise ProviderError(selected.provider, cause="conflicting_tool_id")
                            row["id"] = call["id"]
                        for field in ("name", "arguments"):
                            value = (call.get("function") or {}).get(field) or ""
                            argument_size += len(value)
                            if argument_size > 262144:
                                raise ProviderError(selected.provider, cause="oversized_arguments")
                            row["function"][field] += value
        if not done:
            raise ProviderError(selected.provider, cause="missing_done")
        if finish not in ("stop", "tool_calls"):
            raise ProviderError(selected.provider, cause=f"finish_{finish if finish in ('length', 'content_filter') else 'other'}")
        ordered = [calls[i] for i in sorted(calls)]
        if finish == "tool_calls" and not ordered:
            raise ProviderError(selected.provider, cause="tool_finish_without_calls")
        if any(not c["id"] or not c["function"]["name"] for c in ordered):
            raise ProviderError(selected.provider, cause="incomplete_tool_call")
        if len({c["id"] for c in ordered}) != len(ordered):
            raise ProviderError(selected.provider, cause="duplicate_tool_id")
        yield {"type": "result", "data": {"tool_calls": ordered, "usage": usage, "finish_reason": finish}}
    except httpx.HTTPError as error:
        raise ProviderError(selected.provider, retryable=True, cause="transport_" + type(error).__name__) from None
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ProviderError(selected.provider, cause="malformed_" + type(error).__name__) from None
