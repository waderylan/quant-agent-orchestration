"""Inspect provider accounting or record a verified starting credit observation."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.provider_limits import CUTOFF, ProviderLedger


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    init = sub.add_parser("init")
    init.add_argument("--balance", required=True)
    init.add_argument("--observed-at", required=True, help="ISO timestamp of the verified dashboard balance")
    init.add_argument("--expires-at", help="Earlier promo expiry; local January 1 cutoff always applies")
    init.add_argument("--prior-reserved", default="0", help="Conservative prior untracked/reserved USD")
    init.add_argument("--exclusive-account-use", action="store_true", help="All subsequent consumption must use this ledger")
    refresh = sub.add_parser("refresh", help="Record a fresh dashboard balance without resetting spending")
    refresh.add_argument("--balance", required=True)
    refresh.add_argument("--observed-at", required=True)
    refresh.add_argument("--exclusive-account-use", action="store_true")
    args = parser.parse_args()
    ledger = ProviderLedger()
    if args.command in ("init", "refresh"):
        observed = datetime.fromisoformat(args.observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            parser.error("--observed-at requires a timezone")
        expiry_text = getattr(args, "expires_at", None)
        expiry = datetime.fromisoformat(expiry_text.replace("Z", "+00:00")) if expiry_text else None
        if expiry is not None and expiry.tzinfo is None:
            parser.error("--expires-at requires a timezone")
        if args.command == "refresh":
            ledger.refresh(balance=args.balance, observed_at=observed.timestamp(), exclusive=args.exclusive_account_use)
        else:
            ledger.initialize(balance=args.balance, observed_at=observed.timestamp(),
                              expires_at=min(expiry.timestamp(), CUTOFF) if expiry else CUTOFF,
                              prior_reserved=args.prior_reserved, exclusive=args.exclusive_account_use)
    print(json.dumps(ledger.status(), indent=2))


if __name__ == "__main__":
    main()
