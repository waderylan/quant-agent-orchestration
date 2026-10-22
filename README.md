# Public-Company Research Assistant

Rylan Wade's CSCI 599 Assignment 2 project. The local application answers cited filing questions, checks consolidated GAAP figures and calculations, and researches dated current developments for NVIDIA, AMD, Intel, and Qualcomm. All four cover FY2024–FY2025; NVIDIA also covers FY2026. [Documentation map](docs/README.md) links the current scope, architecture, milestones, evidence, and assignment.

## Run locally

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), network access for initial source/model downloads, and either an authenticated Codex CLI (`codex login`) or the API provider setup below.

```powershell
uv sync --locked
uv run --locked python scripts/collect_sources.py collect
uv run --locked python scripts/research.py ingest
uv run --locked python scripts/financials.py collect
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`, select companies and fiscal years, and ask a self-contained question. Fiscal years select historical filings and numbers; current web research uses the timeframe in the question. The page streams answers, a requested-output checklist, inspectable citations, and checked analysis artifacts. Activity shows each agent call in color with its status and duration. Expand Timeline or select a call to inspect its task, model, tools, and sources. [Architecture](docs/architecture.md#http-browser-and-local-container) defines the activity contract. Local data and generated outputs are ignored by Git. `uv run --locked python scripts/collect_sources.py verify` checks downloaded originals.

Try:

- “What has happened at the selected companies since their latest filings? Cite dated sources.”
- “What has happened with Qualcomm lately?” Select QCOM; ordinary recent questions use the last 90 days.
- “Explain Qualcomm's revenue change from the filings, then research how outside commentators reacted.” Select QCOM and FY2024–FY2025; the answer separates filing drivers from reactions around the selected annual release.
- “Compare reactions to Qualcomm's FY2024 and FY2025 results, then tell me what's new lately.” Select both years; each research output retains its own timeframe.
- “Is the export-control risk in the latest annual filing still current? Check for an official update.” This example preserves the selected companies.
- “Compare Qualcomm's customer-concentration risk between FY2024 and FY2025.” Select QCOM and both years. Risk Summary automatically checks every registered finding for dated post-filing context; the browser's “Compare risk changes” example preserves the selected companies and years.
- “What can this system do, and what does each agent do?” Capability answers use local descriptions without web research. Recognized pure capability questions need no model generation; semantic variants use the request planner/reviewer with the same descriptions.
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

Use `--help` on each script for additional commands. [M4](docs/milestones/local-container/README.md) describes the local container profile. [Milestones](docs/milestones/README.md) own status; formal evaluation and Cloud Run deployment remain pending.

## Generation providers

The default `GENERATION_PROFILE=codex` uses the host subscription. For direct providers, copy `.env.example` to ignored `.env` and supply `NVIDIA_API_KEY` and `NEBIUS_API_KEY`. Select **Hosted (NVIDIA + Nebius)** in the browser Models control, or set `GENERATION_PROFILE=api` as the server default. Each request keeps its selection; model names and reasons share the existing activity details. Both providers are required for normal hosted routing. API mode never uses CLI authentication.

[M11](docs/milestones/provider-routing/README.md) owns model IDs, prices, dashboard links and account limits. No code blocks spend; limits are instructions in [AGENTS.md](AGENTS.md). NVIDIA failures and its 40 requests/minute pacing reroute calls to DeepSeek on Nebius.

```powershell
# Recorded calls and token-estimated cost per provider.
uv run --locked python scripts/providers.py
$env:GENERATION_PROFILE='api'
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```

`/api/runtime` identifies the profile; activity details show each provider/model and routing reason.

```powershell
uv run --locked python scripts/evaluate_provider_routes.py --url http://127.0.0.1:8080 --output artifacts/providers/application.json
uv run --locked python scripts/evaluate_provider_routes.py --url http://127.0.0.1:8080 --dataset tests/fixtures/provider_full_workflows.json --output artifacts/providers/full-workflows.json
uv run --locked python scripts/compare_provider_models.py --output artifacts/providers/comparison.json
uv run --locked python scripts/start_local_container.py --profile api --port 8084
```

Capture makes real calls against seven development cases; it is not formal RAGAS scoring. Stop native generation before Docker acceptance so the test ledger has a single operating-system owner. The API container receives keys at runtime without a host bridge. Hosted generation runs on Cloud Run when its keys are present; M14 owns deployment verification and cross-instance coordination.

## Static filing RAGAS

`uv sync --locked` includes pinned evaluation dependencies. The judge uses the authenticated local Codex subscription and local ONNX embeddings. No hosted judge or embedding key is required. [Evaluation](docs/evaluation.md) reports all four metrics, per-question results, source review, latency, costs and limits. This direct Research evaluation disables web acquisition without changing application live defaults.

```powershell
uv run --locked python scripts/evaluate_ragas.py calibrate --output artifacts/ragas/calibration.json
uv run --locked python scripts/evaluate_ragas.py capture --dataset tests/fixtures/ragas_development.json --output artifacts/ragas/development.json
uv run --locked python scripts/evaluate_ragas.py score --dataset tests/fixtures/ragas_development.json --capture artifacts/ragas/development.json --output artifacts/ragas/development-scores.json
uv run --locked python scripts/evaluate_ragas.py capture --dataset tests/fixtures/ragas_heldout.json --output artifacts/ragas/heldout.json
uv run --locked python scripts/evaluate_ragas.py score --dataset tests/fixtures/ragas_heldout.json --reference-errata tests/fixtures/ragas_reference_errata.json --capture artifacts/ragas/heldout.json --output artifacts/ragas/heldout-scores.json
```

Capture uses the prepared corpus/index from setup; `--corpus` and `--index` select other paths. `--profile api` explicitly selects hosted generation. Controls in `tests/fixtures/ragas_controls.json` run through `capture` and stay outside metric denominators. `--resume` requires matching capture/runtime/data identities. Run scoring commands sequentially when sharing the judge cache. Repeated relevancy draws retain separate cached samples. A new model run can yield different scores.

The committed input artifacts can be rescored without regenerating answers or querying Chroma. The recorded report also supports arithmetic replay with zero model calls:

```powershell
uv run --locked python scripts/verify_ragas_report.py docs/milestones/experience-evaluation/evidence/RAGAS_2026-10-22.json --output artifacts/ragas/replayed-arithmetic.json
```

## Live sources

**MCP tool sharing (graded):** Current Developments, Filings Research and Risk Summary invoke the same Tavily Remote MCP `tavily_search` tool in different contexts. Risk Summary uses it automatically for every registered finding, including stable risks. Exercise sharing with a risk comparison plus current developments, or a full five-agent request with an official-update clause to exercise all three callers. Each call appears as `node=live_mcp` with its agent, server and tool. Live calls need `TAVILY_API_KEY` and provider access. [Rationale](docs/architecture.md#mcp-tool-sharing); [M12 comparison](docs/milestones/risk-live-check/README.md).

Copy `.env.example` to ignored `.env` and supply `TAVILY_API_KEY` from your Tavily account. The key stays in the runtime environment. Live mode is the default when a key exists; set `LIVE_MODE=off` to disable acquisition or `LIVE_MODE=frozen` to replay recorded snapshots without new calls. `LIVE_CACHE` defaults to `artifacts/live/cache` and `LIVE_LEDGER` to `artifacts/live/usage.sqlite3`.

Current Developments uses Tavily Remote MCP search/extraction for recent events, requested calendar windows, developments since a filing, and outside reactions to selected releases. Research shares search for a specific official-update check, including mixed requests that also need developments. Explicit no-web instructions prevent acquisition. The planner identifies each requested output, and a separate reviewer checks the original question, answer and cited excerpts before completion. Unsupported claim spans are removed and the repaired answer receives one bounded recheck; unresolved requested findings remain partial. [Architecture](docs/architecture.md) owns tool limits, dates and caching; [M10](docs/milestones/current-developments/README.md) owns measured acceptance. Prices and valuation are unsupported.

```powershell
uv run --locked python scripts/demo_current.py --direct --output artifacts/current-direct.json
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8080 --output artifacts/current-app.json
uv run --locked python scripts/demo_current.py --browser --url http://127.0.0.1:8080 --output artifacts/current-browser.json
uv run --locked python scripts/start_local_container.py --live-mode live
uv run --locked python scripts/demo_current.py --url http://127.0.0.1:8084 --case nvda --refresh --output artifacts/current-container.json
```

Real demonstrations use account credits. Tests force frozen mode, isolated ledgers/caches and blocked default Tavily transport. Docker receives the key through an inherited runtime environment variable; the image contains no credentials. Native and container demonstrations share the per-host live ledger. [Evaluation](docs/evaluation.md) separates these checks from formal scores and deployed-provider measurements.

Capture the three development questions through the running application:

```powershell
uv run --locked python scripts/evaluate_usefulness.py --url http://127.0.0.1:8080 --output artifacts/usefulness-development.json
```

The capture command records actual answers/traces and the Tavily calls made since it started. `--dataset` accepts a JSON case list with `id`, `question`, `companies` and `years`; capture alone does not establish answer quality or a formal evaluation score.

For matched M12 comparisons, start separate server processes with `RISK_LIVE_CHECK=off` (Research baseline) and `RISK_LIVE_CHECK=on` (both uses, the default). Explicit no-web requests suppress acquisition in either process. Run captures serially when comparing wall times and per-host usage:

```powershell
uv run --locked python scripts/compare_risk_live.py --variant research=http://127.0.0.1:8093 --variant both=http://127.0.0.1:8092 --output artifacts/m12/comparison.json
```

Generation defaults to the local Codex subscription; Tavily still uses real account credits. `--profile api` selects hosted generation for targeted compatibility checks. `--dataset` accepts the same case format; `--resume` skips completed variant/case pairs after validating the dataset/profile.
