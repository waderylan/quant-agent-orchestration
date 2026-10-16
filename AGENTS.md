# AGENTS.md

CSCI 599 Assignment 2 — canonical shared instructions.

## 1. Assignment Ground Truth

- `docs/reference/assignment/Assignment_2_Description.md` governs requirements, grading, academic integrity, and deliverables. The PDF beside it governs visual formatting.
- Consult the assignment directly rather than chat summaries. Identify conflicts before proceeding; user and platform instructions take precedence.

## 2. Required Agent Workflow

At the start of each session:

1. Read this file and the assignment Markdown completely.
2. Read `docs/project.md` before project decisions or changes.
3. The top-level agent generates one session UUID for working context; no session-start entry.
4. Complete the authorized work within the assignment contract.
5. Append an event only if §3 qualifies, following §4. For a user-authorized milestone sequence, append one event after each completed and verified milestone. Record the milestone handoff verbatim; the last milestone entry records the final user-facing response verbatim immediately before sending it.

Only the top-level agent writes transcripts. Sub-agents report qualifying work to their parent. Concurrent sessions/worktrees must use §4.2.

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
- Record the milestone handoff or final user-facing response verbatim. Draft it, append it, verify it, then send the same response. The last milestone entry in an authorized sequence records the final response.
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

## 5. Repository Guardrails

- Never commit or expose credentials; use environment variables and ignored secret files.
- Claim success only for actions actually performed and inspected.
- Keep tests slim and useful. Every test, assertion, and line of test code must protect meaningful behavior or catch a plausible failure; omit trivial checks and tests added only to increase coverage or test counts.
- Preserve user-authored and unrelated changes.
- Keep `CLAUDE.md` as the single-line import `@AGENTS.md`.
- Keep documentation factual; never invent decisions, measurements, or personal reflections.

## 6. Documentation and Communication

- Address the user as **rwade** in chat; use **Rylan Wade** in documents. Give short, direct bullet updates and final reports: outcome, verification, and decisions that need review. Cut filler.
- Write concise, plain technical English. State current behavior in the present tense. Keep the facts needed to understand or verify it; remove repetition, speculative detail, superseded plans, chat-history explanations, and pointers to obsolete paths. Preserve dates and version relationships needed to interpret evidence.
- Follow the [documentation map](docs/README.md). Keep the root README for setup and runnable commands; `docs/project.md` for scope; `docs/architecture.md` for current contracts; `docs/evaluation.md` for measured results. Put each fact in one owning page and link to it elsewhere.
- Keep M1–M13 in [one milestone index](docs/milestones/README.md), which alone owns order and status. Each milestone has one `README.md`. Future briefs specify the outcome, dependencies, scope, handoffs, acceptance checks, and decisions to verify; keep them concrete and concise. As work completes, replace the brief with verified behavior, decisions, commands, limits, and evidence.
- Keep research decisions in `docs/research/`, supplied material in `docs/reference/`, reusable cases in `tests/fixtures/`, and dated results under the owning milestone's `evidence/`. Preserve recorded evidence; write new local run output to ignored `artifacts/`.
- After changing docs, check local links, milestone coverage, runnable commands, referenced paths, and consistency with verified code and results. Update scripts that consume moved files. Documentation-only work does not trigger a transcript event under §3.

## 7. Project Workflow

- Selected product: [Public-Company Research Assistant](docs/project.md). [Architecture](docs/architecture.md) describes current behavior; [milestones](docs/milestones/README.md) own order and status. The assignment takes precedence.
- Implement only authorized increments. Demonstrate each with source checks, relevant tests, and a runnable local path; request Rylan Wade's feedback before an unauthorized next milestone.
- Use Python 3.13 with `uv sync --locked` and `uv run --locked`. Pin direct dependencies in `pyproject.toml`, commit `uv.lock`, and export `requirements.txt` using `uv export --frozen --no-dev --no-hashes --no-emit-project --output-file requirements.txt`.
- Use local Codex/Claude Code subscriptions for development and testing. Distinguish direct-worker, fixture, browser/application, Docker, and deployment-provider evidence. Keep local CLI authentication out of the deployed runtime.
- Verify Nebius/NVIDIA access, model IDs, pricing, and routing in final integration; then deploy to Cloud Run and retest. Formal evaluation requirements are in [evaluation](docs/evaluation.md).
- [Instructor references](docs/reference/instructor/README.md) are guidance, not implementation contracts. Do not copy HW1 implementation, credentials, deployment config, artifacts, or reflections.
- Leave [PROCESS_LOG.md](PROCESS_LOG.md) as a template until Rylan Wade provides his own 200–300-word reflection across four sections. Include the completed log in the final archive.

## 8. Product Ideas

- The company project is selected. [Law and ski concepts](docs/reference/alternatives/README.md) remain unselected; revisions to them do not authorize implementation.
