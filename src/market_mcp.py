"""Read-only official MCP clients, frozen snapshots, and a single work-budget ledger.

Credentials are runtime-only. All stored/returned payloads pass the same scrubber.
Tool initialization/discovery is recorded separately from billable data calls.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import sqlite3
import sys
import uuid
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from src.source_collection import ROOT, digest, now, write_json
from src.market_evidence import payload_text

TD_REVISION = "d139a77ea0f7d40995e6979cd09c22dd142fbfe8"
ALLOW = {
    "twelve": {
        "get_quote",
        "get_api_usage",
        "get_statistics",
        "get_earnings",
        "get_splits",
        "get_financials",
    },
    "alpha": {
        "EARNINGS_ESTIMATES",
        "COMPANY_OVERVIEW",
        "EARNINGS",
        "BALANCE_SHEET",
        "CASH_FLOW",
        "INCOME_STATEMENT",
    },
    "tavily": {"tavily_search"},
}


def sanitized(value):
    if isinstance(value, dict):
        return {
            k: sanitized(v)
            for k, v in value.items()
            if k.lower()
            not in {"apikey", "api_key", "authorization", "cookie", "headers", "email"}
        }
    if isinstance(value, list):
        return [sanitized(v) for v in value]
    if not isinstance(value, str):
        return value
    for name in (
        "ALPHA_VANTAGE_API_KEY",
        "TWELVE_DATA_API_KEY",
        "TWELVE_DATA_GMAIL_API_KEY",
        "TAVILY_API_KEY",
    ):
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


def provider_error(payload):
    if not isinstance(payload, dict):
        return True
    if payload.get("isError"):
        return True
    text = payload_text({"payload": payload})
    try:
        body = json.loads(text)
    except (ValueError, TypeError):
        lowered = text.lower()
        return any(
            term in lowered
            for term in (
                "rate limit reached",
                "api limit reached",
                "premium endpoint",
                "out of api credits",
                "available exclusively with",
                "not available with your plan",
            )
        )
    return isinstance(body, dict) and bool(
        body.get("error")
        or body.get("Information")
        or body.get("Note")
        or body.get("status") == "error"
    )


class UsageLedger:
    """Atomic reservations precede calls; failures and crashes still count.

    SQLite serializes native callers. Frozen container tests do not write a second
    ledger. Daily limits use UTC, a conservative and reproducible provider-day policy.
    """

    def __init__(self, path=None):
        self.path = Path(
            path or os.getenv("MARKET_LEDGER", ROOT / "artifacts/market/usage.sqlite3")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, at TEXT, provider TEXT, account TEXT, tool TEXT, symbol TEXT, credits INTEGER, outcome TEXT); CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
        return row[0] if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value))
            )

    def reserve(self, provider, account, tool, symbol="", credits=1):
        if provider not in ALLOW or tool not in ALLOW[provider]:
            raise ValueError("Provider/tool is outside the read-only allowlist")
        if type(credits) is not int or credits <= 0:
            raise ValueError("Credit reservations must be positive integers")
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            total = db.execute(
                "SELECT COUNT(*) FROM calls WHERE provider=?", (provider,)
            ).fetchone()[0]
            if provider == "alpha":
                daily = db.execute(
                    "SELECT COUNT(*) FROM calls WHERE provider='alpha' AND substr(at,1,10)=?",
                    (timestamp[:10],),
                ).fetchone()[0]
                if total >= 40 or daily >= 10:
                    raise ValueError(
                        "Alpha Vantage work budget exhausted (10/day, 40 total); use frozen evidence"
                    )
            if provider == "twelve":
                if total >= 60:
                    raise ValueError(
                        "Twelve Data combined 60-call work budget exhausted; use frozen evidence"
                    )
                active = db.execute(
                    "SELECT value FROM settings WHERE key='twelve_active'"
                ).fetchone()
                if account != (active[0] if active else "yahoo"):
                    raise ValueError(
                        "Only the active Twelve Data account may make data calls"
                    )
                other_active = db.execute(
                    "SELECT 1 FROM calls WHERE provider='twelve' AND account<>? AND outcome='reserved' LIMIT 1",
                    (account,),
                ).fetchone()
                if other_active:
                    raise ValueError(
                        "Another Twelve Data account still has an outstanding call; account switching must be sequential"
                    )
                # Conservative local ceiling, not a claim about provider entitlement.
                # Include probes and both account audits in the same minute budget.
                recent = db.execute(
                    "SELECT COUNT(*) FROM calls WHERE provider='twelve' AND julianday(at)>julianday(?)-1.0/1440",
                    (timestamp,),
                ).fetchone()[0]
                if recent >= 8:
                    raise ValueError(
                        "Twelve Data local minute budget reached; no immediate retry or key switch"
                    )
            if provider == "tavily":
                spent = db.execute(
                    "SELECT COALESCE(SUM(credits),0) FROM calls WHERE provider='tavily'"
                ).fetchone()[0]
                usage = db.execute(
                    "SELECT value FROM settings WHERE key='tavily_month_usage'"
                ).fetchone()
                baseline = db.execute(
                    "SELECT value FROM settings WHERE key='tavily_baseline_reserved'"
                ).fetchone()
                current = (
                    int(usage[0]) + spent - int(baseline[0])
                    if usage and baseline
                    else None
                )
                start = db.execute("SELECT value FROM settings WHERE key='tavily_work_start_observed_usage'").fetchone()
                month = db.execute("SELECT value FROM settings WHERE key='tavily_work_start_month'").fetchone()
                if start and month and month[0] == timestamp[:7]:
                    start_reserved = db.execute("SELECT value FROM settings WHERE key='tavily_work_start_reserved'").fetchone()
                    current = max(current or 0, int(start[0]) + spent - int(start_reserved[0] if start_reserved else 0))
                if (
                    spent + credits > 100
                    or current is not None
                    and current + credits > 300
                ):
                    raise ValueError(
                        "Tavily work/month stop reached (100 additional credits; 300 monthly)"
                    )
            identity = str(uuid.uuid4())
            db.execute(
                "INSERT INTO calls VALUES (?,?,?,?,?,?,?,?)",
                (
                    identity,
                    timestamp,
                    provider,
                    account,
                    tool,
                    symbol,
                    credits,
                    "reserved",
                ),
            )
        return identity

    def finish(self, identity, outcome):
        with self.connect() as db:
            db.execute("UPDATE calls SET outcome=? WHERE id=?", (outcome, identity))

    def observe_tavily_usage(self, usage: int):
        """Monotonic monthly projection; concurrent or lagging reads cannot erase it."""
        if type(usage) is not int or usage < 0:
            raise ValueError("Invalid Tavily usage observation")
        timestamp = now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            settings = dict(db.execute("SELECT key,value FROM settings"))
            spent = db.execute("SELECT COALESCE(SUM(credits),0) FROM calls WHERE provider='tavily'").fetchone()[0]
            checked = settings.get("tavily_usage_checked_at", "")
            new_month = bool(checked) and checked[:7] != timestamp[:7]
            if new_month or "tavily_work_start_observed_usage" not in settings:
                settings.update(tavily_work_start_observed_usage=str(usage), tavily_work_start_month=timestamp[:7], tavily_work_start_reserved=str(spent if new_month else 0))
            previous = 0 if new_month else int(settings.get("tavily_month_usage", 0))
            baseline = spent if new_month else int(settings.get("tavily_baseline_reserved", 0))
            observed = usage if new_month else max(usage, int(settings.get("tavily_observed_usage", 0)))
            floor = int(settings["tavily_work_start_observed_usage"]) + spent - int(settings.get("tavily_work_start_reserved", 0))
            conservative = max(observed, previous + spent - baseline, floor)
            settings.update(tavily_observed_usage=str(observed), tavily_month_usage=str(conservative), tavily_baseline_reserved=str(spent), tavily_usage_checked_at=timestamp)
            db.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)", settings.items())
        return conservative

    def snapshot(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            calls = [dict(row) for row in db.execute("SELECT * FROM calls ORDER BY at")]
            settings = dict(db.execute("SELECT key,value FROM settings"))
        return {
            "checked_at": now(),
            "limits": {
                "alpha_daily": 10,
                "alpha_total": 40,
                "twelve_combined": 60,
                "tavily_work_credits": 100,
                "tavily_month_stop": 300,
            },
            "settings": settings,
            "calls": calls,
        }


def cache_key(provider, tool, arguments):
    return digest(json.dumps([provider, tool, arguments], sort_keys=True).encode())


class MarketGateway:
    def __init__(self, *, mode=None, path=None, ledger=None):
        self.mode = mode or os.getenv("MARKET_MODE", "off")
        if os.getenv("K_SERVICE") and os.getenv("MARKET_DISPLAY_RIGHTS") != "confirmed":
            self.mode = "off"
        if self.mode not in ("off", "live", "frozen"):
            raise ValueError("MARKET_MODE must be off, live, or frozen")
        self.path = Path(
            path or os.getenv("MARKET_CACHE", ROOT / "artifacts/market/cache")
        )
        self.ledger = ledger or UsageLedger()

    async def tavily_usage(self):
        """Read-only account usage; no search credits consumed or secret output."""
        key = os.getenv("TAVILY_API_KEY", "")
        if not key:
            return {"verified": False}
        try:
            async with httpx.AsyncClient(timeout=20) as http:
                response = await http.get(
                    "https://api.tavily.com/usage",
                    headers={"Authorization": "Bearer " + key},
                )
                response.raise_for_status()
                body = response.json()
            account = body.get("account", {})
            usage = int(account["plan_usage"]) + int(account.get("paygo_usage", 0))
            self.ledger.observe_tavily_usage(usage)
            return {
                "verified": True,
                "account": {
                    k: account.get(k)
                    for k in (
                        "current_plan",
                        "plan_usage",
                        "plan_limit",
                        "paygo_usage",
                        "paygo_limit",
                    )
                },
                "key": {k: body.get("key", {}).get(k) for k in ("usage", "limit")},
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "verified": False,
                "limitation": "Usage unavailable; conservatively count every reserved search credit",
            }

    async def _session(self, stack, provider, account):
        if provider == "twelve":
            script = Path(
                os.getenv(
                    "TWELVE_MCP_SCRIPT", ROOT / "artifacts/twelvedata-mcp/src/server.py"
                )
            )
            if not script.is_file():
                raise ValueError("Pinned official Twelve Data MCP checkout unavailable")
            env = {
                k: v
                for k, v in os.environ.items()
                if k.upper()
                in {
                    "PATH",
                    "SYSTEMROOT",
                    "WINDIR",
                    "TEMP",
                    "TMP",
                    "HOME",
                    "USERPROFILE",
                }
            }
            env.update(
                TWELVE_DATA_API_KEY=os.getenv(
                    "TWELVE_DATA_GMAIL_API_KEY"
                    if account == "gmail"
                    else "TWELVE_DATA_API_KEY",
                    "",
                ),
                MCP_TRANSPORT="stdio",
                MCP_HOST="127.0.0.1",
                PYTHONUTF8="1",
            )
            # Discard server stderr: upstream errors may echo credential-bearing URLs.
            stderr = stack.enter_context(open(os.devnull, "w"))
            read, write = await stack.enter_async_context(
                stdio_client(
                    StdioServerParameters(
                        command=sys.executable,
                        args=[str(script)],
                        env=env,
                        cwd=str(script.parent),
                    ),
                    errlog=stderr,
                )
            )
        else:
            variable = (
                "ALPHA_VANTAGE_API_KEY" if provider == "alpha" else "TAVILY_API_KEY"
            )
            secret = os.getenv(variable, "")
            if not secret:
                raise ValueError("Provider credential unavailable")
            endpoint = (
                "https://mcp.alphavantage.co/mcp?apikey="
                if provider == "alpha"
                else "https://mcp.tavily.com/mcp/?tavilyApiKey="
            ) + quote(secret, safe="")
            # HTTPX must never log credential URLs. Application exceptions are generic.
            for logger in ("httpx", "httpcore", "mcp.client.streamable_http"):
                logging.getLogger(logger).setLevel(logging.CRITICAL)
            read, write, _ = await stack.enter_async_context(
                streamable_http_client(endpoint)
            )
        session = await stack.enter_async_context(ClientSession(read, write))
        initialized = await session.initialize()
        discovered = await session.list_tools()
        return session, {
            "protocol": initialized.protocolVersion,
            "server": initialized.serverInfo.model_dump(),
            "tools": [t.model_dump(mode="json") for t in discovered.tools],
        }

    async def discover(self, provider):
        """Initialization/discovery alone spends no provider data-call reservation."""
        account = (
            self.ledger.setting("twelve_active", "yahoo")
            if provider == "twelve"
            else "primary"
        )
        try:
            async with asyncio.timeout(45), AsyncExitStack() as stack:
                _, metadata = await self._session(stack, provider, account)
                return sanitized(metadata)
        except Exception:
            return {
                "error": "MCP initialization/discovery failed",
                "provider": provider,
            }

    async def fetch(self, provider, tool, arguments, *, refresh=False):
        if provider not in ALLOW or tool not in ALLOW[provider]:
            raise ValueError("Provider/tool is outside the read-only allowlist")
        if self.mode == "off":
            return {
                "provider": provider,
                "tool": tool,
                "arguments": arguments,
                "error": "Market integration disabled; public display rights are unverified",
            }
        symbol = arguments.get("symbol", "")
        if symbol and symbol not in {"NVDA", "AMD", "INTC", "QCOM"}:
            raise ValueError("Market request exceeds supported symbols")
        if provider == "tavily" and (
            tool != "tavily_search"
            or arguments.get("search_depth") != "basic"
            or arguments.get("max_results", 0) > 3
        ):
            raise ValueError(
                "Only narrow basic Tavily search with at most three results is allowed"
            )
        key = cache_key(provider, tool, arguments)
        file = self.path / "requests" / (key + ".json")
        if not file.exists() and (self.path / (key + ".json")).exists():
            legacy_file = self.path / (key + ".json")
        else:
            legacy_file = file
        if legacy_file.exists() and not refresh:
            snapshot = json.loads(legacy_file.read_text(encoding="utf-8"))
            if snapshot.get("schema_version") == 2 and digest(json.dumps({k: v for k, v in snapshot.items() if k != "snapshot_id"}, sort_keys=True).encode()) != snapshot.get("snapshot_id"):
                raise ValueError("Market snapshot metadata checksum mismatch")
            if (
                digest(json.dumps(snapshot["payload"], sort_keys=True).encode())
                != snapshot["payload_sha256"]
            ):
                raise ValueError("Market snapshot checksum mismatch")
            age = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(snapshot["retrieved_at"])
            ).total_seconds()
            account_matches = provider != "twelve" or snapshot.get(
                "account"
            ) == self.ledger.setting("twelve_active", "yahoo")
            if (
                self.mode == "frozen"
                or account_matches
                and age <= (900 if tool == "get_quote" else 86400)
            ):
                return {
                    **snapshot,
                    "outcome": "provider_error"
                    if provider_error(snapshot["payload"])
                    else "returned",
                    "cache": True,
                    "replayed": self.mode == "frozen",
                }
        if self.mode != "live":
            return {
                "provider": provider,
                "tool": tool,
                "arguments": arguments,
                "error": "Market integration disabled or frozen snapshot missing",
                "replayed": self.mode == "frozen",
            }
        if provider == "tavily":
            await self.tavily_usage()
        account = (
            self.ledger.setting("twelve_active", "yahoo")
            if provider == "twelve"
            else "primary"
        )
        identity = self.ledger.reserve(
            provider, account, tool, symbol, credits=2 if provider == "tavily" else 1
        )
        try:
            async with asyncio.timeout(55), AsyncExitStack() as stack:
                session, metadata = await self._session(stack, provider, account)
                names = {t["name"] for t in metadata["tools"]}
                if tool not in names:
                    raise ValueError("Required MCP tool not discovered")
                result = await session.call_tool(tool, arguments)
                payload = sanitized(result.model_dump(mode="json"))
            body = json.dumps(payload).lower()
            error = provider_error(payload)
            outcome = "provider_error" if error else "returned"
            self.ledger.finish(identity, outcome)
            if (
                provider == "twelve"
                and outcome == "provider_error"
                and "day" in body
                and ("out of api credits" in body or "daily limit" in body)
            ):
                # Only demonstrated daily exhaustion permits a single account switch.
                if account == "yahoo" and os.getenv("TWELVE_DATA_GMAIL_API_KEY"):
                    self.ledger.set("twelve_active", "gmail")
                    self.ledger.set(
                        "twelve_switch_reason",
                        "Yahoo provider daily quota exhausted; no automatic retry",
                    )
            snapshot = {
                "schema_version": 2,
                "provider": provider,
                "account": account,
                "tool": tool,
                "arguments": arguments,
                "retrieved_at": now(),
                "payload": payload,
                "payload_sha256": digest(json.dumps(payload, sort_keys=True).encode()),
                "mcp": {
                    "protocol": metadata["protocol"],
                    "server": metadata["server"],
                    "discovered_tool": tool,
                    "tool_count": len(metadata["tools"]),
                },
                "evidence_kind": "live MCP",
                "outcome": outcome,
                "cache": False,
                "replayed": False,
            }
            snapshot["snapshot_id"] = digest(
                json.dumps(snapshot, sort_keys=True).encode()
            )
            write_json(self.path / (snapshot["snapshot_id"] + ".json"), snapshot)
            write_json(file, snapshot)
            return snapshot
        except asyncio.CancelledError:
            self.ledger.finish(identity, "cancelled_reserved")
            raise
        except Exception:
            self.ledger.finish(identity, "transport_failure_reserved")
            # Never stringify exceptions from an authenticated transport.
            return {
                "provider": provider,
                "tool": tool,
                "arguments": arguments,
                "error": "MCP transport/tool failed; call remains charged to work budget",
                "account": account,
            }

    def inspect(self, identity):
        if os.getenv("K_SERVICE") and os.getenv("MARKET_DISPLAY_RIGHTS") != "confirmed":
            raise ValueError("Public market-data display rights are unverified")
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise ValueError("Invalid market snapshot identity")
        snapshot = json.loads(
            (self.path / (identity + ".json")).read_text(encoding="utf-8")
        )
        if (
            snapshot.get("schema_version") == 2
            and digest(
                json.dumps(
                    {k: v for k, v in snapshot.items() if k != "snapshot_id"},
                    sort_keys=True,
                ).encode()
            )
            != identity
        ):
            raise ValueError("Market snapshot metadata checksum mismatch")
        if (
            digest(json.dumps(snapshot["payload"], sort_keys=True).encode())
            != snapshot["payload_sha256"]
        ):
            raise ValueError("Market snapshot checksum mismatch")
        return sanitized(snapshot)
