# Public-Company Research Assistant

Rylan Wade's CSCI 599 Assignment 2 project. The local application answers cited filing questions and checks consolidated GAAP figures and calculations for NVIDIA, AMD, Intel, and Qualcomm. All four cover FY2024–FY2025; NVIDIA also covers FY2026. [Documentation map](docs/README.md) links the current scope, architecture, milestones, evidence, and assignment.

## Run locally

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), an authenticated Codex CLI (`codex login`), and network access for initial source/model downloads.

```powershell
uv sync --locked
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/research.py ingest
uv run --locked python scripts/financials.py collect
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`, select companies and fiscal years, and ask a self-contained question. The page streams answers, routing/tool traces, exact source passages, financial observations, and checked analysis artifacts. Local data and generated outputs are ignored by Git. `uv run --locked python scripts/collect_sources.py verify` checks downloaded originals.

Try:

- “How much of Qualcomm's FY2025 revenue came from automotive?”
- “Show Qualcomm FY2024 and FY2025 GAAP revenue, gross profit, operating income, and operating cash flow, then compare them.” Select QCOM and both years.
- “Which company had the largest earnings growth from FY2024 to FY2025?” Select all four companies and both years.
- “What explains AMD's FY2025 revenue growth, and did operating margin improve?” Select AMD and both years.

For direct worker runs and inspection:

```powershell
uv run --locked python scripts/research.py status
uv run --locked python scripts/research.py agent "What does AMD's amended FY2025 MD&A correct?" --company AMD --year 2025
uv run --locked python scripts/financials.py query --company AMD --year 2025 --period Q2 --basis ytd
uv run --locked python scripts/quant.py agent "Calculate AMD FY2024 versus FY2025 revenue growth and gross margin." --company AMD --year 2024 2025
uv run --locked python scripts/quant.py replay BUNDLE_ID
uv run --locked pytest -q
```

Use `--help` on each script for additional commands. [M4](docs/milestones/local-container/README.md) has the local Docker acceptance command. The [milestone index](docs/milestones/README.md) identifies the next work; broader live research, two-provider routing, formal evaluation, and Cloud Run remain planned.

Private market testing requires the four runtime keys listed in `.env.example`, `MARKET_MODE=live`, and the official Twelve Data checkout. Public market-data display rights are unverified; [M8](docs/milestones/buy-side-analyst/README.md) records actual entitlements, budgets, and excluded valuation inputs.

```powershell
git clone https://github.com/twelvedata/mcp.git artifacts/twelvedata-mcp
git -C artifacts/twelvedata-mcp checkout d139a77ea0f7d40995e6979cd09c22dd142fbfe8
uv run --locked python scripts/market_access.py --usage
uv run --locked python scripts/demo_buy.py --direct
uv run --locked python scripts/start_local_container.py --market-mode live
```

Use `MARKET_MODE=frozen` to replay cached provider responses without new calls, retaining original dates. The single ledger at `artifacts/market/usage.sqlite3` reserves calls before network execution; native and Docker acceptance share it. Do not run independent live account probes outside this adapter. The hard work limits remain Alpha Vantage 10/day and 40 total, Twelve Data 60 combined, and Tavily 100 additional credits with a 300-credit monthly stop. No plan upgrade is automatic.
