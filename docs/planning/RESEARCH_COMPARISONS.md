# Multi-company filing research

- Owner: Rylan Wade.
- Scope: the existing Filings Research worker, scoped retrieval, and local subscription transport. M7–M13 remain unstarted.

## Retrieval and answer contract

- Initial semantic retrieval supplies four passages per selected company/fiscal-year pair.
- `search_sources` searches every selected pair unless the model narrows company or year. It returns four passages per pair for comparisons, six for a single pair, and an explicit passage count for every pair, including zero results. Form, section, and version filters apply to each search. Registered source IDs remain local to the request.
- The worker starts comparisons with a shared search and refines missing evidence. Supplied source text can support paraphrases directly; contextual inspection remains available when the passage is insufficient or an exact quotation is needed.
- Answers distinguish shared drivers from those affecting only a subset. They check whether each company actually grew, preserve company/year labels and annual/interim distinctions, and explain missing evidence. Equal fiscal labels do not align company reporting dates.
- Research uses filing disclosures only. It does not replace checked Quant arithmetic, formal risk alignment, live retrieval, or the planned full supervisor workflow.

## Bounded stopping

- Research permits `min(24, max(8, 3 × selected company/year pairs))` executed dynamic calls. One company/year gets eight; four companies in one year get twelve; four companies over two years get twenty-four. The allowance accommodates a targeted search and contextual inspections per pair within a fixed cap. It is a policy choice, not an empirically optimized quality threshold.
- Other worker phases retain eight executed calls. All phases retain the 180-second model deadline and existing process cancellation behavior.
- The initial trace reports the call limit. The prompt and tool replies tell the model how much work remains and instruct it to synthesize supported findings before exhausting the allowance.
- Requests after the limit receive an explicit denial without executing the handler. Two denial responses allow final synthesis. A third excess request fails explicitly and closes the transport, bounding repeated refusal to stop.
- If Research receives a denial and returns an answer, normal citation and source-text checks still apply. The app adds a visible retrieval-limit qualification and finishes with `partial`, preserving cited findings. Invalid or absent citations still produce `unverified`; timeout and unavailable-model failures remain explicit failures. A partial result is not a guarantee that the question was fully answered.

## Verified local behavior

- `uv run --locked pytest -q`: 104 tests pass. Deterministic JSON-RPC checks exercise the actual adapter loop: eight executions with two denied requests followed by final text, nine executions under a twelve-call allowance, and bounded failure/transport closure on repeated excess calls. Research tests check balanced scope, empty retrieval cells, scope isolation, and cited partial output.
- [Native application evidence](../research/RESEARCH_COMPARISON_RESULTS.json): the exact question `what were comon factors driving revenue growth for all companies`, a four-company FY2025 shared/company-specific driver question, and an AMD/Intel annual/interim headwind comparison finish with cited answers. Their dynamic-call counts are four, five, and four; elapsed times are 26.842, 25.600, and 28.795 seconds on the local subscription route.
- [Chromium evidence](../research/RESEARCH_COMPARISON_BROWSER_RESULTS.json): all four companies with FY2024/FY2025 selected, the exact reported question, completed answer, and opened source passage. The response distinguishes Intel's consolidated declines from positive segment drivers and does not assert universal AI-led growth.
- [Source checks](../research/RESEARCH_COMPARISON_SOURCE_CHECKS.json): all 37 cited passages across the three native turns match the independently fetched inspection endpoint text. Each turn cites every selected company. These checks establish source identity and coverage, rather than a formal semantic-faithfulness score.
- These are exploratory correctness demonstrations. They do not establish a model reliability rate, formal claim-level faithfulness score, deployment-provider latency, or cloud acceptance. This change's actual application/browser acceptance runs natively; a fresh Docker acceptance run is not recorded for it.

```powershell
uv run --locked pytest -q
uv run --locked python scripts/demo_research_comparisons.py --output artifacts/research-comparisons.json
uv run --locked python scripts/demo_research_comparisons.py --browser --output artifacts/research-comparison-browser.json
```

- The demonstration defaults to `http://127.0.0.1:8086`; use `--url` for another local address. It requires the collected/indexed corpus, authenticated local Codex CLI, and Chromium for the browser check.
