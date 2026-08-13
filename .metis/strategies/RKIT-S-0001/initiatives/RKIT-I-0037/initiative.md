---
id: deterministic-match-resolve-and
level: initiative
title: "Deterministic Match, Resolve, and Inspect UX"
short_code: "RKIT-I-0037"
created_at: 2026-08-13T20:41:37.828792+00:00
updated_at: 2026-08-13T20:41:37.828792+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0036", "RKIT-I-0002", "RKIT-I-0018", "RKIT-I-0026"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Deterministic Match, Resolve, and Inspect UX Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. Deterministic scoring is real — `resume_core.scoreMatch` is called and honest — but the command surfaces around it invent, downgrade, or hardcode domain state:

- `_inspect_requirement` fabricates `resolution_state` via `"exact_match" if requirement_id == "req_react" else "unknown"` (`resume_cli/__init__.py:338`) — verified to return exact_match with no match ever run, violating the code-owned JobRequirement invariant and `cli_surface.json`'s own must_not `invent_requirement_resolution`.
- Match reports mutate core-owned ResolutionState: related_match/possible_match are downgraded to `unknown` and per-requirement status fields rewritten (`resume_cli/__init__.py:160-167`) — presentation must reflect domain results, not reclassify them (CONTRACT_SURFACE_ALIGNMENT.md).
- Interview topic selection is re-implemented in the CLI with fixture-tuned priority tables: `_resolution_priority`/`_topic_for_requirement` hardcode `{'aws':0,'graphql':1,...}` with 'AWS'/'req_aws' defaults (`resume_cli/__init__.py:799, 809-823`), while `resume_core.getUnresolvedRequirements` — the owning surface per the responsibility matrix ("Next interview topic") — is never imported.
- Match never blocks or routes on unresolved hard requirements despite core exposing `can_continue`; `match` on an empty workspace returns ok/0.0 (verified).
- Resolve is not interactive: it consumes one pre-supplied stdin string; `_explicit_confirmation` is a keyword regex standing in for explicit user confirmation (`resume_cli/__init__.py:848-850, 173-207`); the CLI pre-declares `verification_state: 'user_verified'` on fact proposals before store validation (`:841`). Off-fixture answers persist nothing: a clear "Yes, I have used Terraform for four years" produced no fact proposals.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- `inspect` reports only persisted, code-owned state: requirement resolution comes from persisted match/resolution artifacts, with a typed no-data result otherwise. The `req_react` fabrication path is deleted.
- Match reports pass through core ResolutionState verbatim, using the RKIT-A-0006 item 2 vocabulary (including `not_applicable`); the downgrade/rewrite block is deleted.
- Match consumes the section 4.3 MatchResult as realigned by RKIT-A-0006 item 4 (`threshold`, `hardRequirementsResolved`, `dimensions`, tri-state `decision`) and enforces it: `blocked` blocks continuation, `resolve_gaps` routes to resolve — the config policy `matching.requireHardRequirementsResolved` is actually honored.
- Topic selection is delegated: the CLI calls `resume_core.getUnresolvedRequirements` and uses its ranked `selected_requirement`; the CLI priority tables are deleted.
- Resolve is genuinely interactive (vision 14.D): a question/answer/confirmation loop over the RKIT-I-0035 TerminalIO seam, with question phrasing and answer interpretation from resume-agent (RKIT-I-0018 per RKIT-A-0003); verification authority stays with career-store — the CLI stops pre-declaring `user_verified` and stops regex-matching confirmations.

**Non-Goals:**
- The multi-step resolve-until-threshold loop inside `run` — RKIT-I-0040, driven through workflow's loop orchestration (RKIT-I-0026).
- Scoring, resolution-state computation, ranked-requirement internals — resume-core (RKIT-I-0002).
- Question/interpretation model behavior — resume-agent (RKIT-I-0018).
- Checkpoint gating of command order — RKIT-I-0040.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- `inspect requirement <id>` returns persisted state or a typed no-data result; no code path can return a resolution state that core never computed (`cli_surface.json` must_not `invent_requirement_resolution` becomes testable; deletes `resume_cli/__init__.py:338`).
- The match report the CLI persists carries the full section 4.3 fields and byte-identical ResolutionStates from core output (deletes `:160-167`).
- With `matching.requireHardRequirementsResolved: true` and an unresolved required requirement, match produces the blocked/routed outcome with nonzero exit — not ok (TEST_SPEC match: "Blocks or routes to resolve when hard requirement policy demands it").
- Resolve asks the core-selected requirement's question via agent phrasing, records the answer, requires an explicit confirmation exchange (not a regex over one string), and persists facts only through store validation with store-owned verification state (removes `:841`, `:848-850`).
- An off-fixture affirmative answer with substance produces a fact proposal that persists — killing the Terraform-answer-persists-nothing behavior.
- Every asked/answered exchange is recorded via the RKIT-A-0001 interaction APIs (`question_asked`, `answer_recorded`) so RKIT-I-0040 can reconstruct and RKIT-I-0041 can suppress duplicates.

### Dependencies
- RKIT-I-0036 (real ingested requirements/facts to match against).
- RKIT-I-0002 Resume-Core Deterministic Requirement Resolution And Match Scoring (section 4.3 MatchResult, getUnresolvedRequirements).
- RKIT-I-0018 Resume-Agent Targeted Interview Question and Answer Interpretation Adapter (RKIT-A-0003 surfaces).
- RKIT-I-0026 Workflow Requirement Resolution Loop Orchestration (the loop surface `run` will drive; resolve must emit compatible results).

### Blocked Status
- Blocked by RKIT-I-0036, RKIT-I-0002, RKIT-I-0018, RKIT-I-0026 (frontmatter matches). RKIT-A-0003 is decided, so agent Q&A surfaces are specified; no ADR block remains.

## Detailed Design **[REQUIRED]**

- **Match.** `_match` calls scoreMatch, persists the full MatchResult (score, threshold, hardRequirementsResolved, dimensions, per-requirement ResolutionState, decision) as match.json, and maps `decision` to CLI behavior: `continue` → ok; `resolve_gaps` → ok with a routing hint naming the core-selected unresolved requirement; `blocked` → domain-failure exit code listing the blocking requirements. The report renderer displays states verbatim.
- **Inspect.** Reads persisted artifacts only (match.json, resolution records, store facts by id). Requirement inspection = the persisted ResolutionState plus supporting evidence refs; absent artifacts yield `{status: no_data}`. No computation, no defaults.
- **Resolve.** Loop: `getUnresolvedRequirements` → selected requirement → agent question phrasing → `TerminalIO.ask` → agent answer-interpretation proposal (structured claim/duration/evidence) → core validation → `TerminalIO.confirm` showing the exact fact text to persist → career-store persistence, with the store assigning verification state per its own confirmation gate. Negative/unknown answers record resolution outcomes — explicit absence is modeled in requirement resolution per RKIT-A-0006 item 1, not as a verification state. Each exchange is recorded through `recordInteraction`.
- **Deletions.** `_resolution_priority`, `_topic_for_requirement`, `_explicit_confirmation`, the report-downgrade block at `:160-167`, and the `:338` fabrication.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Inspect honesty test: fresh workspace, `inspect requirement req_react` must return no_data — directly killing the fabrication; plus an assertion that inspect output states are a subset of persisted core output.
- Report fidelity test: core returns related_match/possible_match/not_applicable; the persisted report and stdout must carry them unchanged.
- Hard-requirement policy test: `requireHardRequirementsResolved: true` plus an unresolved required requirement → blocked outcome and nonzero exit; empty-workspace match is a typed failure, not ok/0.0. TEST_SPEC previously defined no blocking case — the looseness that certified never-blocking match.
- Interactive resolve test over scripted TerminalIO: a multi-exchange script (question → answer → confirmation) with the fake adapter; asserts store-validated fact persistence and recorded interactions; an off-fixture-vocabulary answer case asserts a fact persists.
- Strengthen the resolve spec: the single-stdin-string contract is replaced by an exchange script; confirmation must be an explicit affirmative step, not keyword presence in the answer.

## Alternatives Considered **[REQUIRED]**

- Keep CLI topic tables as a tie-breaker over core ranking: rejected — the responsibility matrix assigns next-topic selection to resume-core/workflow; a CLI tie-breaker is duplicated domain logic, and the current tables are fixture-tuned.
- Let inspect compute a best-effort estimate when no match has run: rejected — "The official state of a requirement is code-owned"; an estimate from the presentation layer is indistinguishable from invention, which is the current defect.
- Contract resolve as one-shot Q→A with pre-supplied answers (current shape): rejected — vision 14.D requires targeted interviewing with explicit confirmation; one-shot cannot express confirmation or follow-ups and is what forced the regex stand-in.

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Match passthrough: full section 4.3 MatchResult persistence + verbatim state reporting (delete the downgrade block).
2. Decision enforcement: blocked/resolve_gaps mapping with config-driven hard-requirement policy.
3. Inspect from persisted artifacts with typed no_data (delete the fabrication).
4. Topic delegation to getUnresolvedRequirements (delete the priority tables).
5. Interactive resolve loop: agent phrasing/interpretation, TerminalIO exchanges, store-gated persistence, interaction recording.
6. TEST_SPEC strengthening: blocking case, inspect honesty, exchange-script resolve, off-fixture answer persistence.
