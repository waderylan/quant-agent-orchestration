"""Inspect actual MCP access through the application's MarketGateway.

Only explicit --call invokes a provider data tool. Initialization/discovery and
Tavily usage inspection are separate from calls. Output is scrubbed by the adapter.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.market_mcp import MarketGateway
from src.source_collection import ROOT, write_json


async def main(args):
    load_dotenv(ROOT / ".env")
    gateway = MarketGateway(mode="live")
    if args.usage:
        result = await gateway.tavily_usage()
    elif args.call:
        arguments = json.loads(args.arguments)
        if args.symbol:
            arguments["symbol"] = args.symbol
        result = await gateway.fetch(
            args.provider, args.call, arguments, refresh=args.refresh
        )
    else:
        result = await gateway.discover(args.provider)
    write_json(args.output, result)
    write_json(ROOT / "artifacts/market/usage-ledger.json", gateway.ledger.snapshot())
    if "tools" in result:
        print(
            json.dumps(
                {
                    "server": result["server"],
                    "protocol": result["protocol"],
                    "tools": [t["name"] for t in result["tools"]],
                }
            )
        )
    else:
        print(json.dumps(result, ensure_ascii=True)[:10000])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["twelve", "alpha", "tavily"], default="twelve"
    )
    parser.add_argument("--usage", action="store_true")
    parser.add_argument("--call")
    parser.add_argument("--arguments", default="{}")
    parser.add_argument("--symbol", choices=["NVDA", "AMD", "INTC", "QCOM"])
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/market/access.json"
    )
    asyncio.run(main(parser.parse_args()))
