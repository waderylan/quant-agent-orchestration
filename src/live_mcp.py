"""Tavily Remote MCP, checked frozen snapshots, and conservative credit reservations."""

import asyncio
import json
import logging
import os
import re
import sqlite3
import uuid
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from src.source_collection import ROOT, digest, now, write_json
from src.source_collection import COMPANIES
from src.request_routing import COMPANY_ALIASES

ALLOW = {"tavily_search", "tavily_extract"}


def search_arguments(companies, query, topic="news"):
    if not isinstance(query, str) or not 1 <= len(query) <= 160:
        raise ValueError("Search query requires 1–160 characters")
    for company in companies:
        if not re.search(COMPANY_ALIASES[company][1], query, re.I):
            query = COMPANIES[company][1] + " " + query
    if len(query) > 160:
        raise ValueError("Company-prefixed search query exceeds 160 characters")
    return {"query": query, "topic": topic, "search_depth": "basic", "max_results": 5, "include_raw_content": False, "time_range": "year"}


def sanitized(value):
    if isinstance(value, dict):
        return {
            k: sanitized(v)
            for k, v in value.items()
            if k.lower()
            not in {"apikey", "api_key", "tavilyapikey", "authorization", "cookie", "headers", "email"}
        }
    if isinstance(value, list):
        return [sanitized(v) for v in value]
    if not isinstance(value, str):
        return value
    for name in ("TAVILY_API_KEY",):
        secret = os.getenv(name)
        if secret:
            value = value.replace(secret, "[REDACTED]").replace(
                quote(secret, safe=""), "[REDACTED]"
            )
    value = re.sub(
        r"https?://[^\s\"<>]*(?:apikey|api_key|tavilyApiKey|token)=[^\s\"<>]*",
        "[REDACTED MCP URL]",
        value,
        flags=re.I,
    )
    return re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[REDACTED]", value, flags=re.I
    )


def payload_body(payload):
    structured = payload.get("structuredContent")
    if isinstance(structured, dict) and structured:
        body = structured.get("result", structured)
        if isinstance(body, dict):
            return body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except ValueError:
                return {"error": "Unrecognized MCP result"}
    text = "\n".join(c.get("text", "") for c in payload.get("content", []) if c.get("type") == "text")
    try:
        return json.loads(text)
    except ValueError:
        return {"error": "Unrecognized MCP result"}


def failure_reason(value):
    text = str(value).lower()
    if "429" in text or "rate limit" in text or "quota" in text:
        return "rate limit (429)"
    if "401" in text or "403" in text or "unauthorized" in text or "invalid api" in text:
        return "credential rejected (401/403)"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    return "MCP transport or tool failure"


class UsageLedger:
    """Atomic reservations count failures, crashes and lagging usage observations."""

    def __init__(self, path=None):
        self.path = Path(path or os.getenv("LIVE_LEDGER", ROOT / "artifacts/live/usage.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, at TEXT, tool TEXT, credits INTEGER, outcome TEXT); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);")

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def observe_tavily_usage(self, usage):
        if type(usage) is not int or usage < 0:
            raise ValueError("Invalid Tavily usage observation")
        month = now()[:7]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            settings = dict(db.execute("SELECT key,value FROM settings"))
            spent = db.execute("SELECT COALESCE(SUM(credits),0) FROM calls WHERE substr(at,1,7)=?", (month,)).fetchone()[0]
            previous = int(settings.get("projection", 0)) if settings.get("month") == month else 0
            baseline = int(settings.get("reserved", 0)) if settings.get("month") == month else 0
            # Include all local reservations in the first observation conservatively.
            projection = max(usage, previous + spent - baseline, spent)
            db.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)", [("month", month), ("projection", str(projection)), ("reserved", str(spent)), ("observed_usage", str(usage)), ("checked_at", now())])
        return projection

    def reserve(self, tool):
        if tool not in ALLOW:
            raise ValueError("Tool is outside the live allowlist")
        timestamp = now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            settings = dict(db.execute("SELECT key,value FROM settings"))
            spent = db.execute("SELECT COALESCE(SUM(credits),0) FROM calls WHERE substr(at,1,7)=?", (timestamp[:7],)).fetchone()[0]
            projection = max(spent, int(settings.get("projection", 0)) + spent - int(settings.get("reserved", 0))) if settings.get("month") == timestamp[:7] else spent
            if projection + 2 > 600:
                raise ValueError("Tavily monthly stop reached (600 projected credits)")
            identity = str(uuid.uuid4())
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?)", (identity, timestamp, tool, 2, "reserved"))
        return identity

    def finish(self, identity, outcome):
        with self.connect() as db:
            db.execute("UPDATE calls SET outcome=? WHERE id=?", (outcome, identity))

    def snapshot(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            calls = [dict(r) for r in db.execute("SELECT * FROM calls ORDER BY at")]
            settings = dict(db.execute("SELECT key,value FROM settings"))
        return {"checked_at": now(), "monthly_stop": 600, "settings": settings, "calls": calls, "reserved_credits": sum(r["credits"] for r in calls)}


class LiveGateway:
    def __init__(self, *, mode=None, path=None, ledger=None):
        self.mode = mode or os.getenv("LIVE_MODE") or ("live" if os.getenv("TAVILY_API_KEY") else "off")
        if self.mode not in ("live", "frozen", "off"):
            raise ValueError("LIVE_MODE must be live, frozen, or off")
        self.path = Path(path or os.getenv("LIVE_CACHE", ROOT / "artifacts/live/cache"))
        self.ledger = ledger or UsageLedger()

    async def tavily_usage(self):
        key = os.getenv("TAVILY_API_KEY", "")
        if not key:
            return {"verified": False, "reason": "missing Tavily key"}
        try:
            async with httpx.AsyncClient(timeout=20) as http:
                response = await http.get("https://api.tavily.com/usage", headers={"Authorization": "Bearer " + key})
                response.raise_for_status()
                account = response.json()["account"]
            self.ledger.observe_tavily_usage(int(account["plan_usage"]) + int(account.get("paygo_usage", 0)))
            return {"verified": True}
        except httpx.HTTPStatusError as error:
            return {"verified": False, "reason": "usage endpoint HTTP " + str(error.response.status_code)}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"verified": False, "reason": "usage check unavailable"}

    async def _session(self, stack):
        key = os.getenv("TAVILY_API_KEY", "")
        if not key:
            raise ValueError("Missing Tavily key")
        for logger in ("httpx", "httpcore", "mcp.client.streamable_http"):
            logging.getLogger(logger).setLevel(logging.CRITICAL)
        endpoint = "https://mcp.tavily.com/mcp/?tavilyApiKey=" + quote(key, safe="")
        read, write, _ = await stack.enter_async_context(streamable_http_client(endpoint))
        session = await stack.enter_async_context(ClientSession(read, write))
        initialized = await session.initialize()
        discovered = await session.list_tools()
        return session, {"protocol": initialized.protocolVersion, "server": initialized.serverInfo.model_dump(), "tools": [t.model_dump(mode="json") for t in discovered.tools]}

    async def discover(self):
        try:
            async with asyncio.timeout(30), AsyncExitStack() as stack:
                _, metadata = await self._session(stack)
                return sanitized(metadata)
        except Exception as error:
            return {"error": failure_reason(type(error).__name__)}

    def validate(self, tool, arguments, request):
        if tool not in ALLOW or not isinstance(arguments, dict):
            raise ValueError("Tool is outside the live allowlist")
        if tool == "tavily_search":
            required = {"query", "topic", "search_depth", "max_results", "include_raw_content"}
            if set(arguments) - (required | {"time_range", "start_date", "end_date", "include_domains"}) or required - set(arguments) or not isinstance(arguments["query"], str) or not 1 <= len(arguments["query"]) <= 160 or arguments["topic"] not in ("news", "general") or arguments["search_depth"] not in ("basic", "advanced") or type(arguments["max_results"]) is not int or arguments["max_results"] != 5 or arguments["include_raw_content"] is not False or arguments.get("time_range", "year") not in ("day", "week", "month", "year"):
                raise ValueError("Unsupported live search argument or value")
            for key in ("start_date", "end_date"):
                if key in arguments and not re.fullmatch(r"20\d\d-\d\d-\d\d", arguments[key]):
                    raise ValueError("Invalid research date interval")
            if "include_domains" in arguments and (not isinstance(arguments["include_domains"], list) or len(arguments["include_domains"]) > 8 or any(not re.fullmatch(r"[a-z0-9.-]+", d) for d in arguments["include_domains"])):
                raise ValueError("Invalid search domain filter")
        elif set(arguments) - {"urls", "extract_depth", "query", "format"} or not {"urls", "extract_depth"} <= arguments.keys() or arguments["extract_depth"] not in ("basic", "advanced") or arguments.get("format", "text") != "text" or not isinstance(arguments["urls"], list) or len(arguments["urls"]) != 1 or arguments["urls"][0] not in request.get("urls", set()):
            raise ValueError("Extraction requires one URL returned by this request's search")

    def store(self, tool, arguments, payload, metadata, *, retrieved_at=None):
        payload = sanitized(payload)
        snapshot = {"schema_version": 1, "tool": tool, "arguments": sanitized(arguments), "retrieved_at": retrieved_at or now(), "payload": payload, "payload_sha256": digest(json.dumps(payload, sort_keys=True).encode()), "mcp": sanitized(metadata)}
        snapshot["snapshot_id"] = digest(json.dumps(snapshot, sort_keys=True).encode())
        write_json(self.path / (snapshot["snapshot_id"] + ".json"), snapshot)
        key = digest(json.dumps([tool, arguments], sort_keys=True).encode())
        write_json(self.path / "requests" / (key + ".json"), snapshot)
        return snapshot

    def inspect(self, identity):
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise ValueError("Invalid live snapshot identity")
        snapshot = json.loads((self.path / (identity + ".json")).read_text(encoding="utf-8"))
        if digest(json.dumps({k:v for k,v in snapshot.items() if k != "snapshot_id"}, sort_keys=True).encode()) != identity or digest(json.dumps(snapshot["payload"], sort_keys=True).encode()) != snapshot["payload_sha256"]:
            raise ValueError("Live snapshot checksum mismatch")
        return sanitized(snapshot)

    async def fetch(self, tool, arguments, *, request, agent, emit, refresh=False):
        self.validate(tool, arguments, request)
        count = "searches" if tool == "tavily_search" else "extracts"
        limit = (1 if agent == "Filings Research" else request.get("search_limit", 2)) if count == "searches" else (0 if agent == "Filings Research" else request.get("extract_limit", 2))
        event = {"agent": agent, "node": "live_mcp", "server": None, "tool": tool, "arguments": sanitized(arguments), "result_count": 0, "snapshot_id": None, "cache": False}
        def finish(result, outcome):
            body = payload_body(result.get("payload", {}))
            rows = body.get("results", []) if isinstance(body, dict) else []
            if not result.get("error"):
                request.setdefault("urls", set()).update(r["url"] for r in rows if isinstance(r, dict) and isinstance(r.get("url"), str) and re.match(r"^https?://", r["url"]))
            event.update(outcome=outcome, server=result.get("mcp", {}).get("server", {}).get("name"), result_count=len(rows), snapshot_id=result.get("snapshot_id"), cache=result.get("cache", False))
            emit({"type": "trace", "data": sanitized(event)})
            return result
        if request.get(count, 0) >= limit:
            return finish({"error": "request budget stop"}, "budget_stop")
        request[count] = request.get(count, 0) + 1
        if self.mode == "off":
            return finish({"error": "LIVE_MODE=off"}, "disabled")
        key = digest(json.dumps([tool, arguments], sort_keys=True).encode())
        cached = self.path / "requests" / (key + ".json")
        if cached.exists() and not refresh:
            pointer = json.loads(cached.read_text(encoding="utf-8"))
            snapshot = self.inspect(pointer["snapshot_id"])
            if snapshot["tool"] != tool or {k:v for k,v in snapshot["arguments"].items() if k != "time_range"} != {k:v for k,v in arguments.items() if k != "time_range"}:
                raise ValueError("Live cache request differs from its snapshot")
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(snapshot["retrieved_at"])).total_seconds()
            if self.mode == "frozen" or 0 <= age <= (21600 if count == "searches" else 86400):
                body = payload_body(snapshot["payload"])
                if snapshot["payload"].get("isError") or isinstance(body, dict) and body.get("error"):
                    return finish({**snapshot, "error": failure_reason(body), "cache": True}, "provider_error")
                return finish({**snapshot, "cache": True, "replayed": self.mode == "frozen"}, "returned")
        if self.mode == "frozen":
            return finish({"error": "frozen snapshot missing"}, "unavailable")
        if not os.getenv("TAVILY_API_KEY"):
            return finish({"error": "missing Tavily key"}, "unavailable")
        usage = await self.tavily_usage()
        usage_warning = None
        if not usage["verified"]:
            settings = self.ledger.snapshot()["settings"]
            if settings.get("month") != now()[:7] or "observed_usage" not in settings:
                return finish({"error": usage["reason"]}, "unavailable")
            # A lagging/unavailable account read cannot erase reservations. Keep
            # the verified monthly floor and count every subsequent local call.
            usage_warning = "Account usage verification unavailable (" + usage["reason"] + "); conservative credit reservations remain enforced."
        try:
            identity = self.ledger.reserve(tool)
        except ValueError:
            return finish({"error": "monthly budget stop"}, "budget_stop")
        try:
            async with asyncio.timeout(30), AsyncExitStack() as stack:
                session, metadata = await self._session(stack)
                metadata["usage_check"] = {"verified": usage["verified"], "warning": usage_warning}
                event["server"] = metadata["server"]["name"]
                schema = next((t for t in metadata["tools"] if t["name"] == tool), None)
                if schema is None:
                    raise ValueError("Required MCP tool not discovered")
                supported = schema["inputSchema"].get("properties", {})
                required = {"query", "topic", "search_depth", "max_results", "include_raw_content"} if tool == "tavily_search" else {"urls", "extract_depth"}
                arguments = {k:v for k,v in arguments.items() if k in required or k in supported}
                event["arguments"] = arguments
                result = await session.call_tool(tool, arguments)
                payload = sanitized(result.model_dump(mode="json"))
            body = payload_body(payload)
            if payload.get("isError") or not isinstance(body, dict) or body.get("error"):
                reason = failure_reason(body)
                self.ledger.finish(identity, reason)
                return finish({"error": reason, "mcp": metadata}, "provider_error")
            snapshot = self.store(tool, arguments, payload, metadata)
            # A tool without time_range uses the same deterministic request key.
            write_json(cached, snapshot)
            self.ledger.finish(identity, "returned")
            return finish({**snapshot, "cache": False, "replayed": False, "usage_warning": usage_warning}, "returned")
        except asyncio.CancelledError:
            self.ledger.finish(identity, "cancelled_reserved")
            raise
        except Exception as error:
            reason = "timeout" if isinstance(error, TimeoutError) else failure_reason(type(error).__name__)
            self.ledger.finish(identity, reason)
            return finish({"error": reason}, "transport_failure")
