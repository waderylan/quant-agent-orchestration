"""Show locally recorded provider usage; credit limits are AGENTS.md instructions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.provider_limits import ProviderLedger


if __name__ == "__main__":
    print(json.dumps(ProviderLedger().status(), indent=2))
