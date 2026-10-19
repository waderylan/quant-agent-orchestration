# U1 — Agent progress clarity

Owner: Rylan Wade. The [milestone index](../README.md) owns status and order. U1 makes a multi-agent turn readable while it runs. The browser shows what the supervisor split the request into and which agent owns each part. It also shows who called each step, what evidence was handed to it, and what the agent is doing now. Each draft streams in its own section, and the reviewed answer finalizes that section in place. U1 extends the Activity panel and timeline from `934fee5` and does not replace them.

## Problem fixed

The 2026-10-19 15:12 AMD request (margin math, filing reasons, analyst reaction) produced a correct partial answer, but the browser was confusing:

- The planner's outputs appeared as "Researching: <long rewritten description>" lines that read like answer text.
- No prose appeared until the last of four steps began writing. `execute.emit` dropped `token`/`answer`/`sources` from every non-last step, and Financial Data, Quant and Current Developments discarded their own tokens when `emit_answer=False`.
- `finish` then replaced the whole answer with the composed text. The streamed text jumped below a new filings section, and up to three more silent replacements followed: citation normalization, reviewer removal plus the "Unresolved outputs" suffix, and invalid-citation replacement.
- The same gap was shown three times, and the raw JSON trace repeated the full evidence registry on every handoff.

## Assignment fit

The [assignment](../../reference/assignment/Assignment_2_Description.md) §2.6 and the §7.2 Frontend usability criterion (15%) apply.

| Requirement | U1 behavior |
| --- | --- |
| SSE token streaming into the response area | Every step streams `draft` deltas into its own answer section, starting with the first writing agent. In the recorded run, the first draft was visible at 8.3 s instead of after the last step started. Legacy `token`/`answer` are unchanged. |
| Visible routing per turn (agent, provider, why) | The plan card shows the route, the supervisor's routing reason, each step's task, caller, dependencies, received evidence and model/provider. A future `routing_reason` field on agent traces (M11) displays without UI changes. |
| Inspectable trace of orchestration transitions | One readable, expandable row per event, with the raw JSON in each row and a full raw-trace download. This addresses the "Trace log exists but is inscrutable" partial-credit case. |
| Citations linked to source identifiers | Unchanged registered-citation links, rendered per section through the same sanitized Markdown path. |
| Vanilla HTML/JS, no build step | One static script, [`web/request-progress.js`](../../../web/request-progress.js), served by the existing `/static` mount and allowlisted in `.dockerignore`. |
| Multi-agent orchestration | Routing, delegation, budgets, prompts and evidence rules are unchanged. New events only expose existing decisions. |

U1 delivers the progress, missing-output and partial-state part of the M12 browser refinement. Provider routing (M11), evaluation (M12) and deployment (M13) are unchanged.

## Event contract

All events are additive. `trace`, `tool`, `evidence`, `token`, `answer`, `sources`, `artifacts`, `scope`, `activity`, `error` and `complete` keep their meaning, so demonstrations and evidence scripts keep working. Step IDs are `worker-<n>`, the 1-based plan position. `execute` advances `task.steps` and `current` together, so the ID equals the Activity call ID. The plan card, answer sections, Activity calls and trace rows share these IDs.

| Event | Emitted by | Payload |
| --- | --- | --- |
| `plan` | `plan()` after `task_selection` (non-error turns with steps), the capability-only branch, and `execute` after a supported follow-up insertion. The latest replaces the previous one. | `planner` (`semantic`/`rules`), `route`, `reason`, `companies`, `years`, `outputs[]` (`id`, `kind`, short `title`, planner `description`, `owner`, `agent`, `timeframe`, `assigned`), `steps[]` (`id`, `position`, `worker`, `agent`, `title`, `output`, `reason`, `called_by`, `after`, `serves`, `feeds`) |
| `draft` | `execute.emit` for every step | `step`, `agent`, `delta` |
| `draft_replace` | `execute.emit` when a worker replaces its answer | `step`, `agent`, `markdown` |
| `draft_final` | `execute` after `worker_outcome` | `step`, `agent`, authoritative `markdown` (empty on failure), `outcome`, newly registered `evidence` IDs |
| `answer_sections` | `finish` after review, removal and citation checks, before the final `answer` | `sections[]` (`id`, `worker`, `agent`, `label`, `labeled`, `markdown`, `removed`), `folded[]` (`id`, `worker`, `agent`, `reason`), `review` (`status`, `results`, `removed_claims`), `gaps[]` (`output`, `text`, `source`), `fallback` |

Rules:

- Output owners come from module-level `OUTPUT_OWNERS`, which the planner also uses. `serves` lists outputs owned by the step's worker. `after` maps `depends_on` to earlier step IDs, and `feeds` is the inverse. The supervisor is the only dispatcher, so every step is `called_by: "Supervisor"`. Rules-mode turns derive outputs `O1…On` from the task list.
- Financial Data, Quant and Current Developments forward suppressed tokens as `draft` instead of discarding them. Their prompts, outcomes and `emit_answer` semantics are unchanged. Risk Summary, when it is not the last step, streams nothing until its `draft_final`. Its multi-issuer answer adds company headings that per-issuer deltas lack.
- `folded` gives a reason for every planned step that is not a final section:
  - Data folded into Quant's figures.
  - Quant calculations cited by Filings Research.
  - Earlier steps feeding the final agent in a single-answer request.
  - Failed or empty steps.
  - Sections the reviewer emptied.
- `review.status` is `completed`, `partial`, `failed` or `skipped` (rules mode, error and capability-only turns). Each gap maps to one output when it starts with `R<n>:`/`O<n>:`, or with that output's description followed by `:`. Otherwise `output` is null.

### Section correctness rule

Sections are the source of truth for the final answer:

1. `finish` builds sections with the existing include/fold rules and composes the answer exactly as before (`label:\n` prefix only when more than one worker section, blank-line joins, capability prefix unlabeled).
2. The reviewer sees that composed answer unchanged.
3. `strip_sections` applies `remove_unsupported` to every section and records each removed claim on the section where it occurred.
4. If any claim still occurs in the recomposed answer (a claim crossing a section boundary), `finish` applies whole-answer removal instead and emits one `answer` section with `fallback: true`.
5. Invalid citation IDs are replaced in each section and in the gap suffix. The legacy `answer` is emitted once, as `compose(sections)` plus the "Unresolved outputs" suffix. It previously went out twice when citations were invalid.

## Browser behavior

[`web/request-progress.js`](../../../web/request-progress.js) defines `RequestProgress` and `TraceLog`. `index.html` dispatches each event to `TraceLog`, `AgentActivity` and `RequestProgress`. Untrusted text uses `textContent`; Markdown uses the existing Marked + DOMPurify renderer (`renderMarkdown(container, markdown)`) with registered citation links.

- **Plan card:**
  - The header says "The supervisor split your request into N parts" and shows the route and the supervisor's reason.
  - Each part shows a number, short title and owner chip in the Activity colour, with status Queued → Working → Drafted → Being checked → Confirmed, or "Gap noted · see answer".
  - "What the planner understood" expands the planner's description and timeframe.
  - Steps list the caller and dependencies ("Called by Supervisor after Step 2 (Financial Analysis / Quant)"), the part each step works on or the step it supplies, its task, and the received evidence ranges ("Received 7 evidence items: F1–F4, C1–C3"). They also show the model/provider and the newly registered evidence ranges.
  - A "Now:" line narrates the running step: tool calls in plain language ("Looking up AMD FY2025 revenue, operating income", "Searching filings: …", "Reading reuters.com"), empty live results, and "Writing its answer" once prose streams.
  - The step list collapses when the answer is final. Chips and step rows select the same call in the Activity panel.
- **Answer sections:**
  - A section appears when its step starts, labelled with the final heading (Reported figures, Financial analysis, From the filings, Changes in filing risks, Outside research) and an agent chip.
  - Badges move through "Draft · writing", "Draft · waiting for review" and "Draft · being checked", then "Reviewed" or "Reviewed · gap noted above" when the part it answers has a gap. A step without review shows "Final"; a failed review shows "Not reviewed · review unavailable".
  - Reviewed text replaces the draft in the same DOM node. A "N sentences removed by the Answer Reviewer" disclosure lists struck-through removed sentences.
  - Folded drafts move into a closed "Intermediate drafts (N)" disclosure with their reason.
  - A stream that ends without `answer_sections` shows the latest legacy answer, with the final banner saying it was not reviewed.
- **Final answer banner and gaps:**
  - When review finishes, the answer opens with a banner titled "Final answer" or "Final answer · partly complete". It says the answer is finished and states whether the Answer Reviewer checked every part, or whether the review was unavailable.
  - Every gap appears once, in that banner, grouped by request part ("Part 1 · Recent developments") or under "Other limits". Each gap has a plain-language type with a one-line explanation: Not fully answered (the reviewer found part of a requested output missing), Sentences removed (listed struck through), Part of your question was not covered, Not found (reported by the researching agent), A step did not finish, Not reviewed, or Outside what this tool covers. The plan row shows only "Gap noted · see answer".
  - In sectioned mode the "Unresolved outputs" suffix and the "Still needed" banner are not rendered. The status line reads "Step 3 of 4 · Filings Research is working" while running, then "Final answer ready · 1 gap noted" or "Final answer ready · every part confirmed".
  - In Activity, a partial reviewer outcome reads "Found a gap" and a partial worker outcome reads "Done · reported a gap".
- **Route reason:** when the filing router's primary worker is not in the route, the reason lists part ownership instead, for example "Each part goes to the agent that owns it: Recent developments → Current Developments".
- **Legacy mode:** without `plan` or `answer_sections` (scope errors, older event fixtures), the single answer, requested-output checklist and status behave as before.
- **Trace:** one row per event with elapsed time, agent and summary. Examples: "handoff → Filings Research · 7 evidence items (F1–F4, C1–C3)", "query_financials · Looking up AMD FY2024 revenue, operating income" and "review: R1 ✓ R2 ✓". Opening a row renders its raw JSON. "Download raw trace (JSON)" saves every received event in order, including draft deltas.

## Verification

- `uv run --locked pytest -q`: 282 tests pass on 2026-10-19.
- [Event tests](../../../tests/test_progress_events.py) run an AMD-shaped Data → Quant → Research → Current turn with fake workers:
  - Plan owners, `after`/`feeds`/`serves`, and `plan` before the first `draft`.
  - Every step's drafts carry its Activity ID; legacy tokens still come only from the last step.
  - `draft_final` text, folded reasons, the reviewer-removed claim, R3 gap mapping and event order.
  - The final answer equals `compose(sections)` plus the suffix. A claim crossing two sections takes the fallback path and is removed.
- [Supervisor tests](../../../tests/test_supervisor.py) check that a follow-up insertion refreshes the plan.
- [Browser tests](../../../tests/test_request_progress.py) run real Chromium:
  - Narrated tool and model lines, per-agent streaming, the "being checked" badge, and the reviewed text finalizing in the same DOM node in final order.
  - The removed-sentence disclosure, folded intermediate drafts, the final banner first in the answer, gaps grouped by part with their explanations and shown only there, and the reviewer's "Found a gap" label.
  - Citation inspection, chip-to-Activity selection, readable trace rows with raw JSON, the raw-trace download, script-safe rendering, phone width without horizontal scroll, and the unreviewed fallback.
  - Existing [Markdown](../../../tests/test_markdown.py) and [Activity](../../../tests/test_agent_activity.py) browser tests still pass.
- [Live UI evidence](evidence/LIVE_UI_2026-10-19.json): a native local application run in Chromium with real Codex subscription generation. The question was the AMD operating-margin question (filings and math only).
  - The first draft was visible at 8.3 s; the final answer, then labelled "Complete · every part checked", arrived at 69.6 s. The labels changed after this run; the event flow did not.
  - Financial Data and Quant drafts streamed before Filings Research. The final section was checked in place, and both earlier drafts were folded with reasons.
  - 46 trace rows; no page errors.
  - The run made no Tavily calls (ledger at 231 rows before and after). Testing stays under the account's 500-credit monthly cap; the web path is covered by the event and browser tests.
- A Docker build of the branch contains `web/request-progress.js` and the new supervisor events.

```powershell
uv run --locked pytest -q tests/test_progress_events.py tests/test_request_progress.py tests/test_agent_activity.py tests/test_markdown.py
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8080
```

## Limits

- Draft text is unreviewed until `answer_sections` arrives, and its badge says so. Citations in drafts become links once the final cited-source registry arrives.
- A non-last Risk Summary draft appears at step completion rather than token by token.
- The last step's prose is sent twice, as a legacy `token` and as a `draft`. This keeps the existing API contract at the cost of duplicate bytes.
- A real web-research turn was not repeated through the new UI. Fixture tests cover the Current Developments path.
</content>
</invoke>
