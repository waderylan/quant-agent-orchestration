# AGENTS.md

CSCI 599 Assignment 2 — canonical shared instructions.

## 1. Assignment Ground Truth

- `docs/assignment/Assignment_2_Description.md` governs requirements, grading, academic integrity, and deliverables. The PDF beside it governs visual formatting.
- Consult the assignment directly rather than chat summaries. Identify conflicts before proceeding; user and platform instructions take precedence.

## 2. Required Agent Workflow

At the start of each session:

1. Read this file and the assignment Markdown completely.
2. Read `docs/planning/PROJECT_SPEC.md` before project decisions or changes.
3. The top-level agent generates one session UUID for working context; no session-start entry.
4. Complete the authorized work within the assignment contract.
5. Immediately before responding, append one consolidated transcript event only if §3 qualifies, following §4.

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

## 5. Repository Guardrails

- Never commit or expose credentials; use environment variables and ignored secret files.
- Claim success only for actions actually performed and inspected.
- Preserve user-authored and unrelated changes.
- Keep `CLAUDE.md` as the single-line import `@AGENTS.md`.
- Keep documentation factual; never invent decisions, measurements, or personal reflections.
- Keep project documentation synchronized with the current verified scope, decisions, implementation status, and gaps. State the active policy directly; omit superseded plans and chat-history explanations. Preserve dates and version relationships needed for source evidence.

## 6. Project Workflow

- Chosen project: **Public-Company Research Assistant**. [Project spec](docs/planning/PROJECT_SPEC.md) defines scope, five application agents, providers, local integration, open decisions, and the final checklist. The assignment takes precedence over the spec.
- Current stage: M1 scope and source feasibility complete; application implementation and M2 are unstarted. Initial scope is NVIDIA, AMD, Intel, and Qualcomm with a 41-document collection target. Broader company coverage is planned after source checks, working demonstrations, and feedback. [M1 source evidence](docs/planning/M1_SCOPE_AND_SOURCE_FEASIBILITY.md) records verified access and remaining collection gaps. Follow the spec's M2–M12 skeleton; record completed milestones factually and refine later scopes through feedback.
- Implement only the authorized increment. Provide a runnable demonstration and correctness evidence; get Rylan Wade's feedback before starting the next milestone unless he authorizes another sequence.
- Develop/test locally through Codex/Claude Code subscriptions. Test individual agents directly in Codex; Kessel supports full-application runs and compatible judges. Keep those results distinct.
- Defer Nebius/NVIDIA generation and separate paid judge calls to final integration. Verify provider integration locally, then deploy to Cloud Run and retest. Keep Kessel outside the deployed image.
- Begin with exploratory demos and basic correctness checks. Select formal evaluations after working research/financial-analysis capabilities clarify expected behavior; complete required evaluation reporting before submission.
- Resolve open decisions when needed. Verify current model IDs, pricing, access, and external-tool compatibility; pin framework dependencies exactly in `requirements.txt`.
- Instructor files (`docs/cost_analysis.md`, `docs/frontend_vibecode_prompt.md`, `docs/alternative_*.md`) are reference guidance, separate from student-authored deliverables.
- Keep `PROCESS_LOG.md` a template until Rylan Wade supplies his actual reflection. After deployment/retesting, remind him to complete 200–300 words across its four sections as the final checklist step. Submission readiness remains pending until the completed log is included in the archive.
- Do not copy HW1 implementation, credentials, deployment configuration, artifacts, or reflections.

## 7. Idea Documents

- `docs/ideas/` contains product exploration. The company idea is selected; law and ski remain alternatives. The planning spec governs selected scope.
- Keep one document per idea. Idea revisions do not authorize implementation; all ideas remain subject to the assignment.
