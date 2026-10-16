"""Sequential second-account entitlement audit, not a production quota fallback.

Run only while application live tests are idle. Restore Yahoo after the bounded
audit. Do not use either account in parallel to increase throughput.
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.market_mcp import MarketGateway
from src.source_collection import ROOT, now, write_json


async def main():
    load_dotenv(ROOT / ".env")
    gateway = MarketGateway(mode="live")
    ledger = gateway.ledger
    previous = ledger.setting("twelve_active", "yahoo")
    report = {
        "checked_at": now(),
        "purpose": "Sequential Gmail entitlement audit under explicit two-account verification authorization; Yahoo quota is not exhausted; no production fallback",
        "calls": [],
    }
    try:
        ledger.set("twelve_active", "gmail")
        ledger.set(
            "twelve_audit", "Gmail entitlement check; restore Yahoo; never concurrent"
        )
        for tool in (
            "get_api_usage",
            "get_quote",
            "get_statistics",
            "get_earnings",
            "get_splits",
        ):
            args = {} if tool == "get_api_usage" else {"symbol": "NVDA"}
            result = await gateway.fetch("twelve", tool, args, refresh=True)
            report["calls"].append(result)
            write_json(ROOT / "artifacts/market/gmail-entitlement-audit.json", report)
            print(tool, result.get("outcome", result.get("error")), flush=True)
    finally:
        ledger.set("twelve_active", previous)
        ledger.set("twelve_audit", "completed; production restored to " + previous)
        write_json(ROOT / "artifacts/market/usage-ledger.json", ledger.snapshot())


if __name__ == "__main__":
    asyncio.run(main())
