"""Small sequential real entitlement matrix; no secret output or unbudgeted retries."""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.market_mcp import MarketGateway
from src.market_evidence import estimate_evidence, quote_evidence
from src.source_collection import ROOT, now, write_json


async def main():
    load_dotenv(ROOT / ".env")
    gateway = MarketGateway(mode="live")
    report = {
        "checked_at": now(),
        "kind": "Actual read-only MCP calls through application adapter",
        "results": [],
    }
    for company in ("NVDA", "AMD", "INTC", "QCOM"):
        for provider, tool in (
            ("twelve", "get_quote"),
            ("alpha", "EARNINGS_ESTIMATES"),
        ):
            snapshot = await gateway.fetch(provider, tool, {"symbol": company})
            normalized = (
                quote_evidence(snapshot, company)
                if provider == "twelve"
                else estimate_evidence(snapshot, company)
            )
            report["results"].append(
                {
                    "company": company,
                    "provider": provider,
                    "tool": tool,
                    "normalized": normalized,
                    "mcp": snapshot.get("mcp"),
                    "cache": snapshot.get("cache"),
                    "account": snapshot.get("account"),
                    "error": snapshot.get("error"),
                }
            )
            write_json(ROOT / "artifacts/market/account-probes.json", report)
            write_json(
                ROOT / "artifacts/market/usage-ledger.json", gateway.ledger.snapshot()
            )
            print(company, provider, normalized["status"], flush=True)
    # Probe higher datasets independently of a working quote.
    for tool in ("get_statistics", "get_earnings", "get_splits"):
        try:
            snapshot = await gateway.fetch("twelve", tool, {"symbol": "NVDA"})
        except ValueError as error:
            snapshot = {"error": str(error)}
        report["results"].append({"tool": tool, "snapshot": snapshot})
        write_json(ROOT / "artifacts/market/account-probes.json", report)
        write_json(
            ROOT / "artifacts/market/usage-ledger.json", gateway.ledger.snapshot()
        )
        print(tool, snapshot.get("outcome", snapshot.get("error")), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
