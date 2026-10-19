# Public-Company Research Assistant

Rylan Wade's CSCI 599 Assignment 2 project. The local application answers cited filing questions, checks consolidated GAAP figures and calculations, and researches dated current developments for NVIDIA, AMD, Intel, and Qualcomm. All four cover FY2024–FY2025; NVIDIA also covers FY2026. [Documentation map](docs/README.md) links the current scope, architecture, milestones, evidence, and assignment.

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

- “What has happened at the selected companies since their latest filings? Cite dated sources.”
- “Is the export-control risk in the latest annual filing still current? Check for an official update.” Both examples preserve the selected companies.
- “What can this system do, and what does each agent do?” The supervisor answers implemented-capability questions locally without provider calls.
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

Use `--help` on each script for additional commands. [M4](docs/milestones/local-container/README.md) describes the local container profile. [Milestones](docs/milestones/README.md) own status; generation-provider routing, formal evaluation and Cloud Run deployment remain planned.

## Live sources

Copy `.env.example` to ignored `.env` and supply `TAVILY_API_KEY` from your Tavily account. The key stays in the runtime environment. Live mode is the default when a key exists; set `LIVE_MODE=off` to disable acquisition or `LIVE_MODE=frozen` to replay recorded snapshots without new calls. `LIVE_CACHE` defaults to `artifacts/live/cache` and `LIVE_LEDGER` to `artifacts/live/usage.sqlite3`.

Current Developments uses Tavily Remote MCP search/extraction after the collected filing anchor. Research shares search for a single official-update check. [Architecture](docs/architecture.md) owns tool limits, freshness, caching and the 600-credit monthly stop; [M10](docs/milestones/current-developments/README.md) owns measured acceptance. Unknown publication dates and unavailable account-usage reads remain explicit partial results. Prices and valuation are unsupported.

```powershell
uv run --locked python scripts/demo_current.py --direct --output artifacts/current-direct.json
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8080 --output artifacts/current-app.json
uv run --locked python scripts/demo_current.py --browser --url http://127.0.0.1:8080 --output artifacts/current-browser.json
uv run --locked python scripts/start_local_container.py --live-mode live
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8084 --case nvda --refresh --output artifacts/current-container.json
```

Real demonstrations use account credits. Tests force frozen mode, isolated ledgers/caches and blocked default Tavily transport. Docker receives the key through an inherited runtime environment variable; the image contains no credentials. Native and container demonstrations share the per-host live ledger. [Evaluation](docs/evaluation.md) separates these checks from formal scores and deployed-provider measurements.
