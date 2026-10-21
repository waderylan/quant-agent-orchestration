"""One invocation's validated tool conversation and completion budget."""
import asyncio
import json
import hashlib

from jsonschema import Draft202012Validator

from src.tool_arguments import normalize


def echoed(call):
    try:
        json.loads(call["function"]["arguments"])
        return call
    except (TypeError, ValueError):
        return {**call, "function": {**call["function"], "arguments": "{}"}}


class ToolConversation:
    def __init__(self, tools, handler, agent, *, supplied_prompt=""):
        self.handler, self.agent = handler, agent
        self.supplied_prompt = supplied_prompt
        self.limit = getattr(handler, "max_tool_calls", 8)
        if type(self.limit) is not int or not 1 <= self.limit <= 24:
            raise ValueError("Worker tool budget must be between 1 and 24")
        self.schemas = {tool["name"]: tool["inputSchema"] for tool in tools}
        self.validators = {name: Draft202012Validator(schema) for name, schema in self.schemas.items()}
        self.wire_tools = [{"type": "function", "function": {
            "name": tool["name"], "description": tool.get("description", ""),
            "parameters": tool["inputSchema"]}} for tool in tools]
        self.structured = len(tools) == 1 and tools[0]["name"] in ("submit_plan", "submit_coverage")
        self.reports_outcome = "report_outcome" in self.schemas
        self.calls = self.denied = 0
        self.seen_ids = set()
        self.submitted = False

    @property
    def complete(self):
        return self.reports_outcome and getattr(self.handler, "status", None) is not None

    def available(self):
        if self.complete:
            return []
        if self.reports_outcome and self.calls >= self.limit - 1:
            return [tool for tool in self.wire_tools if tool["function"]["name"] == "report_outcome"]
        return self.wire_tools

    def context_result(self, value):
        """Reference verbatim text already supplied; retain the full evidence event."""
        if isinstance(value, list):
            return [self.context_result(item) for item in value]
        if not isinstance(value, dict):
            return value
        text = value.get("text")
        if isinstance(text, str) and len(text) > 8000 and any(
                json.dumps(text, ensure_ascii=ascii_only) in self.supplied_prompt for ascii_only in (False, True)):
            return {**{key: self.context_result(item) for key, item in value.items() if key != "text"},
                    "text_reference": {"location": "Exact full text already present in the original supplied context",
                                       "characters": len(text), "utf8_sha256": hashlib.sha256(text.encode()).hexdigest()}}
        return {key: self.context_result(item) for key, item in value.items()}

    async def execute(self, tool_calls, messages, text, available):
        if not available:
            raise RuntimeError("Provider exceeded the permitted tool budget")
        names = [call["function"]["name"] for call in tool_calls]
        if any(call["id"] in self.seen_ids or call["function"]["name"] not in self.schemas for call in tool_calls):
            raise RuntimeError("Unknown or repeated provider tool call")
        permitted = {tool["function"]["name"] for tool in available}
        self.seen_ids.update(call["id"] for call in tool_calls)
        # Providers reject histories that echo unparseable arguments; the tool
        # result below still reports the original error for correction.
        messages.append({"role": "assistant", "content": text or None,
                         "tool_calls": [echoed(call) for call in tool_calls]})
        remaining = self.limit-self.calls
        violates_slot = self.reports_outcome and (("report_outcome" in names and names.index("report_outcome") != len(names)-1)
                        or (len(names) == remaining and names[-1] != "report_outcome"))
        if len(names) > remaining or violates_slot or any(name not in permitted for name in names):
            self.denied += 1
            if self.denied > 2:
                raise RuntimeError("Provider repeatedly exceeded the permitted tool budget")
            reason = "Batch rejected without execution; preserve the reserved completion slot"
            yield {"type": "trace", "data": {"node": "provider_tool_rejected", "agent": self.agent, "reason": reason}}
            for call in tool_calls:
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps({
                    "error": reason, "remaining": remaining, "instruction": "Call one permitted tool at a time; finish with report_outcome."})})
            return
        for call in tool_calls:
            name = call["function"]["name"]
            issues = []
            try:
                if name == "report_outcome" and len(tool_calls) > 1:
                    raise ValueError("Submit report_outcome alone, after reading the preceding tool results")
                arguments = json.loads(call["function"]["arguments"])
                schema = self.schemas[name]
                arguments = normalize(arguments, schema)
                issues = [error.message[:300] for error in self.validators[name].iter_errors(arguments)][:3]
                if not isinstance(arguments, dict) or issues:
                    raise ValueError("Tool schema violation: " + "; ".join(issues))
                self.calls += 1
                yield {"type": "tool", "data": {"name": name, "arguments": arguments}}
                value = await asyncio.to_thread(self.handler, name, arguments)
                yield {"type": "evidence", "data": value}
                self.submitted = self.structured
            except (ValueError, KeyError) as error:
                self.denied += 1
                yield {"type": "trace", "data": {"node": "provider_tool_rejected", "agent": self.agent,
                       "tool": name, "reason": str(error)[:600], **({"validation": issues} if issues else {})}}
                if self.denied > 2:
                    raise RuntimeError("Provider repeatedly returned invalid tool arguments") from None
                value = {"error": str(error)[:600],
                         "instruction": "Correct the arguments within the remaining budget. Use only declared fields.",
                         "allowed_fields": list(self.schemas[name].get("properties", {}))}
            remaining = self.limit - self.calls
            value = {**(value if isinstance(value, dict) else {"result": value}),
                     "tool_budget": {"remaining": remaining, "limit": self.limit,
                     "instruction": "Finish with collected evidence and explicit gaps. Preserve bracketed citation IDs."
                     if remaining <= 2 else "Retrieve only missing evidence."}}
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(self.context_result(value))})
