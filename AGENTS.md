# AGENTS.md

CSCI 599 Assignment 2 — Multi-Agent System with RAG and Orchestration

This repository contains an individual course project to build and deploy a multi-agent system with RAG, inspectable cross-provider routing, and a streaming frontend. The completed project must satisfy the implementation, deployment, testing, documentation, and submission requirements in `docs/assignment/Assignment_2_Description.md`.

This file is the canonical coordination guide for coding agents in this repository. It intentionally does not repeat the assignment specification.

## 1. Assignment Ground Truth

- Read `docs/assignment/Assignment_2_Description.md` completely before making project decisions or changing code, configuration, documentation, tests, deployment, or submission artifacts. This Markdown transcription preserves the complete assignment text; `docs/assignment/Assignment_2_Description.pdf` is the authoritative original for visual formatting.
- Treat `docs/assignment/Assignment_2_Description.md` as the ground truth for all project requirements, grading criteria, academic-integrity rules, technical contracts, and deliverables.
- Do not rely on summaries in chat or agent memory when the assignment document can answer the question directly.
- If repository code, documentation, or a user request appears inconsistent with the assignment, identify the conflict before proceeding.
- Follow higher-priority user and platform instructions when they conflict with this file.

## 2. Required Agent Workflow

At the start of every agent session:

1. Read this file completely.
2. Read `docs/assignment/Assignment_2_Description.md` completely.
   Read `docs/planning/PROJECT_SPEC.md` before project decisions or changes; it defines the chosen project and incremental development approach.
3. If you are the top-level agent, generate one session UUID for working context only. Do not write a session-start entry.
4. Complete the user's request while preserving the assignment contract.
5. Only if the completed work qualifies under §3, the top-level agent appends exactly one event entry using §4.1 and §4.2 immediately before sending the response.

The top-level agent is the only transcript writer for its conversation. Sub-agents must never write to the transcript; they report qualifying work to the parent, which includes it in one consolidated entry. Separate top-level sessions and worktrees share the transcript and must use the concurrency-safe append protocol in §4.2.

## 3. Transcript Location and Safety

The shared transcript is `AI_TRANSCRIPT.md` beside this file in the repository root.

- Resolve its path relative to this file; do not hardcode an absolute path.
- Create it if missing with the single final line `<!-- AI_TRANSCRIPT_EOF -->`.
- Append only. Never rewrite, reorder, truncate, or delete earlier entries.
- The file must contain exactly one `<!-- AI_TRANSCRIPT_EOF -->` marker, and it must remain the final line. Treat this marker as the only legal insertion point.
- Never anchor a transcript edit on a previous heading, `Context` block, timestamp, or other repeated content. That can insert new entries in the middle of the file.
- Never rewrite the whole transcript with a formatter, generated file, search-and-replace, or shell redirection.
- Write an event entry only when at least one of these conditions is satisfied:
  - **Major feature implemented:** the turn completes and verifies a substantial new user-visible capability, assignment milestone, external integration, service, endpoint, persistent data model, deployment component, or comparably significant workflow.
  - **Major bug discovered or fixed:** the turn produces concrete evidence of, or verifies a fix for, a high-impact correctness, security, data-loss, crash, deployment, MCP-contract, or core-workflow failure.
- A feature plan, partial scaffold, or unverified implementation does not qualify until the major capability works.
- Minor bugs, cosmetic defects, small refactors, dependency maintenance, test-only changes, documentation-only changes, configuration tweaks, and routine cleanup do not qualify unless they are inseparable from a qualifying major feature or major bug.
- User feedback, revision requests, information-only answers, planning, status updates, code review, and ordinary repository edits do not qualify by themselves.
- Do not write `SESSION START`, interruption, or administrative entries. If no qualifying event occurred, do not touch `AI_TRANSCRIPT.md`.
- If a major bug is discovered and fixed in the same turn, write one combined entry rather than separate discovery and fix entries.
- When uncertain whether the threshold is met, do not log the turn.
- Record the user prompt verbatim unless it contains secrets or sensitive personal information.
- Record the final user-facing response verbatim. Draft it, append it, verify it, then send the same response.
- Replace API keys, tokens, passwords, cookies, OAuth codes, private keys, `.env` values, and sensitive PII with `[REDACTED]`.
- Do not copy binary data, large file contents, dependency output, or full command output into the transcript. Summarize actions and results.
- Keep `AI_TRANSCRIPT.md` separate from `PROCESS_LOG.md`. The transcript is automatic evidence; the submitted process log must remain Rylan Wade's accurate, personal reflection.

## 4. Transcript Format

### 4.1 Major Event Entry

```markdown
<!-- transcript-entry-id: event:<event-uuid> -->
## YYYY-MM-DDTHH:MM:SS±HH:MM — [MAJOR FEATURE|MAJOR BUG] <short descriptive title>

- Event: <major feature implemented|major bug discovered|major bug fixed|major bug discovered and fixed>

### User Prompt

<verbatim prompt with secrets and sensitive PII replaced by `[REDACTED]`>

### Agent Response

<verbatim final user-facing response>

### Work Performed

- <files created or edited>
- <implementation or bug evidence>
- <verification commands and results>
- <important decisions or unresolved issues>

### Context

- Session ID: <session UUID held in working context>
- Tool: <exact coding agent or harness name>
- Branch: <branch name or `not a Git repository`>
- Repository root: <absolute path>
- Parent agent: <name or `none`>
```

Generate one event UUID when qualifying work is confirmed and reuse it if the finalization step is retried. Before appending, search for its exact `transcript-entry-id`; if present, update nothing and do not create a duplicate.

### 4.2 Concurrency-Safe Append and Verification

For every qualifying event entry:

- Re-read the transcript tail immediately before editing and confirm the EOF marker is the final line.
- Use one `apply_patch` operation that matches only the unique EOF marker and replaces it with: the new entry, one blank line, and the same EOF marker. Do not use prior transcript content as patch context.
- If the patch fails, another session may have appended concurrently. Re-read the tail and retry against the EOF marker; never replace the file.
- Search for the new `transcript-entry-id` and confirm it occurs exactly once.
- Confirm the EOF marker occurs exactly once and is still the final line.
- Re-read the new transcript entry.
- Confirm the prompt and final response match the conversation.
- Confirm `Tool` is present and accurate.
- Confirm no secrets or sensitive PII were logged.
- Confirm the content that preceded the old EOF marker was not changed.

## 5. Minimal Repository Guardrails

- Never commit or expose credentials. Use environment variables and ignored local secret files as directed by the assignment.
- Do not claim that code, tests, tools, deployment, or verification worked unless the relevant action was actually performed and inspected.
- Do not fabricate personal experiences, prompts, lessons, or reflections for `PROCESS_LOG.md`; ask Rylan Wade when personal input is required.
- Preserve user-authored and unrelated changes.
- Keep `CLAUDE.md` as the single-line import `@AGENTS.md`.
- Keep project behavior and documentation aligned with `docs/assignment/Assignment_2_Description.md`.

## 6. Project Status and Assignment 2 Conventions

- Chosen project: **Public-Company Research Assistant**, specified in [`docs/planning/PROJECT_SPEC.md`](docs/planning/PROJECT_SPEC.md). The assignment specification remains the ground truth if the planning spec conflicts with it.
- Current status: scaffold with a selected project and high-level spec; implementation has not been authorized. Use the spec's initial scope and five application agents. Leave its milestones blank until Rylan Wade requests milestone planning.
- Build incrementally when implementation is requested. Work within the authorized milestone, provide a runnable demonstration and correctness evidence, and obtain Rylan Wade's feedback at the checkpoint before starting the next milestone unless he explicitly authorizes a different sequence. Include formal evaluation results once the evaluation harness exists.
- Development and testing are local through Rylan Wade's Codex and Claude Code subscriptions. Run browser/container checks locally; deploy to Cloud Run only at the end and retest the live service. Do not follow the superseded suggestion of an early cloud deployment.
- Test individual application agents directly in Codex sessions with their role instructions, permitted tools, and source-checked questions. Bypass Kessel for these tests; gateway availability must not block single-agent testing.
- Use Rylan Wade's existing [Kessel gateway](../../kessel/README.md) for full-application local generation and compatible automated evaluation judges through the Codex/Claude Code subscriptions. Verify HW2 client compatibility in the first model-backed milestone. Keep Kessel local and outside the deployed image; use explicit endpoint profiles and measure the actual deployment providers at final acceptance. Record direct Codex role tests and Kessel application tests separately.
- Nebius Token Factory is selected as one runtime provider; NVIDIA-hosted NIM is tentative as the second. Models remain unselected. Use subscription-backed Codex/Claude Code agents for development tests; defer Nebius/NVIDIA generation calls and separate paid judge calls to final integration/deployment. Verify runtime integration locally before deploying, and distinguish subscription-backed tests from actual provider measurements.
- Start with exploratory local demonstrations, direct Codex agent testing, basic correctness checks, and Rylan Wade's feedback. Do not require benchmark datasets, model judges, RAGAS scores, or evaluation framework setup in the first milestone. Select a formal evaluation checkpoint after working research and financial-analysis capabilities clarify the intended behavior, then follow the spec's evaluation approach and complete the assignment-required report before submission.
- Resolve the spec's open decisions when the relevant work requires them. Verify external tools, model IDs, pricing, and access before selecting or configuring them.
- Keep the extracted instructor references (`docs/cost_analysis.md`, `docs/frontend_vibecode_prompt.md`, and `docs/alternative_*.md`) separate from student-authored deliverables. They are reference guidance, not completed project documentation.
- Pin selected framework dependencies to exact versions in `requirements.txt` when implementation begins. The scaffold intentionally installs no dependencies.
- Verify current deployable model IDs and pricing when selecting providers; assignment examples are not verification.
- Keep `docs/architecture.md` and `docs/evaluation.md` factual. Do not fill placeholders with invented decisions, measurements, or evaluation results.
- Keep `PROCESS_LOG.md` as a template until Rylan Wade supplies his reflection. The final log is 200–300 words across the four required sections.
- The project spec's final completion checklist ends with Rylan Wade completing `PROCESS_LOG.md` after deployment and deployed retesting. Remind him at that final checkpoint, keep submission readiness pending until it is complete, and include the completed log in the submission archive.
- Do not copy HW1 implementation, credentials, deployment configuration, generated artifacts, or personal reflections into HW2.

## 7. Idea Documents

- Keep product exploration in `docs/ideas/`, with one Markdown document per idea. The selected project spec lives in `docs/planning/PROJECT_SPEC.md` and governs the selected scope where the original exploration differs.
- The law and ski ideas remain unselected alternatives. Selection and documentation alone do not authorize implementation.
- Idea documents:
  - `docs/ideas/course-grounded-law-study.md`: law study tool with course-material, recent-case, and outline agents.
  - `docs/ideas/ski-road-trip-planner.md`: US/Canada ski road-trip planner with resort data, resort review, and ski itinerary agents. Resort fit and review reasoning are central; driving estimates come from existing services.
  - `docs/ideas/public-company-research-assistant.md`: original exploration for the chosen company research assistant; see the planning spec for current scope, agents, evaluation direction, and open decisions.
- Keep product purpose, student experience, agent responsibilities, scope, open decisions, and assignment fit together in each idea document. Leave engineering design and implementation plans for after selection and authorization.
- Follow the assignment specification if an idea document conflicts with it.
