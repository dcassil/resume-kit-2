---
id: workflow-requirement-resolution
level: initiative
title: "Workflow Requirement Resolution Loop Orchestration"
short_code: "RKIT-I-0026"
created_at: 2026-08-13T20:41:37.474248+00:00
updated_at: 2026-08-15T04:06:36.160684+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0023]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: workflow-requirement-resolution
---

# Workflow Requirement Resolution Loop Orchestration Initiative

## Context **[REQUIRED]**

Package: `workflow`. A gap-resolution loop-back already exists and is defective, so this initiative fixes shipped behavior rather than adding new coordination. Verified by the alignment audit: the RESOLVE_GAPS -> MATCH_BASE loop-back keys off cumulative `facts_verified` (workflow/__init__.py:76-77) and never terminates once any fact is verified — BUILD_SELECTION_PLAN through COMPLETE is permanently unreachable for any run that resolves a gap (verified by simulation). The prior version of this document's design section never mentioned gap resolution, requirements, questions, facts, or match reruns at all.

This initiative owns the resolution-loop termination design per PRODUCT_VISION_AND_CONTRACTS.md section 14.D.9: "continue until threshold and hard-requirement policy are satisfied or all meaningful gaps are exhausted." workflow/TEST_SPEC.md:57 specifies rerun-after-new-facts but no termination condition and no advance-past-RESOLVE_GAPS case, so no existing spec case would catch the deadlock.

Boundary statement (required): workflow owns checkpoint and topic-selection state — which requirement/topic is addressed next, what has already been asked, and when the loop ends (CONTRACT_SURFACE_ALIGNMENT.md:41, 43, 241). resume-cli owns user interaction — prompting, collecting answers, and presentation — which is RKIT-I-0037's scope. Question phrasing belongs to resume-agent; answer validation and fact persistence to career-store; scoring to resume-core.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Deterministic loop termination: RESOLVE_GAPS exits when the tri-state MatchResult.decision (RKIT-A-0006 item 4: continue/resolve_gaps/blocked) is `continue`, or when every open gap is exhausted, with the exhaustion outcome recorded honestly.
- Topic selection by unresolved impact is deterministic workflow/resume-core state — never agent choice, never CLI choice.
- Each batch of newly verified facts triggers exactly one MATCH_BASE rerun (consuming the RKIT-I-0023 watermark), then the loop either exits or moves to the next topic.
- Workflow exposes loop state and next-topic decisions as a queryable surface the CLI renders; workflow never prompts.

**Non-Goals:**
- State-machine watermark mechanics — delivered by RKIT-I-0023; this initiative builds the loop policy on top of it.
- User-interaction UX and prompt flows — RKIT-I-0037 (resume-cli); this initiative owns no interactive surface.
- Tailoring/render/completion orchestration — RKIT-I-0027.
- Question phrasing (resume-agent), fact verification/persistence (career-store), match scoring (resume-core).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Implement the section 14.D.9 termination predicate: exit RESOLVE_GAPS when MatchResult.decision is `continue` (threshold met and hard-requirement policy satisfied per the section 13 config vocabulary, contractual under RKIT-A-0006 item 6), or when every open gap is marked exhausted (resolved, user-declined, or no answerable question remains). Reaching BUILD_SELECTION_PLAN after gap resolution must be demonstrated (regression for the workflow/__init__.py:76-77 deadlock).
2. Persist a loop-state DTO in run state: impact-ordered unresolved-requirement queue, per-requirement exhaustion status, and the asked-question registry (also the dedupe input RKIT-I-0025 recovery consumes).
3. `requireHardRequirementsResolved` gates loop exit: unresolved hard requirements route to the blocked outcome, never a silent continue.
4. Boundary rule: no workflow API prompts a user or phrases a question; workflow returns next-topic decisions and consumes verified-fact notifications only through recorded package outputs.
5. Exhaustion honesty: exiting with unresolved gaps records them into run state, feeding the manifest's unresolved_requirements field (RKIT-I-0022).

### Dependencies
- RKIT-I-0023: grounded transitions and the new-facts-since-last-match watermark this loop's rerun discipline runs on.
- RKIT-A-0006 (decided): tri-state MatchResult.decision and the enforced section 13 config vocabulary this termination predicate reads.

### Blocked Status
- Blocked by RKIT-I-0023 (frontmatter blocked_by enforces the ordering). No ADR blocks remain.

## Detailed Design **[REQUIRED]**

**Loop-state DTO.** `ResolutionLoopState`: {open_requirements: ordered list of {requirement_id, impact_rank, status: open|resolved|user_declined|exhausted}, asked_questions: registry of {question_id, requirement_id, interaction_ref}, facts_since_last_match: from the RKIT-I-0023 watermark, iteration_count}. Persisted in run state on every mutation so interruption at any point recovers losslessly (RKIT-I-0025 consumes it).

**Termination predicate.** Evaluated after each MATCH_BASE rerun: (a) decision == `continue` -> advance to BUILD_SELECTION_PLAN; (b) decision == `resolve_gaps` and open non-exhausted requirements remain -> select next topic by impact rank; (c) decision == `resolve_gaps` and all requirements exhausted -> advance with honest unresolved_requirements recorded; (d) decision == `blocked` (hard requirement unresolved under requireHardRequirementsResolved) -> blocked outcome with persisted reasons, no advance.

**Single-rerun discipline.** A batch of newly verified facts (watermark delta non-empty) triggers exactly one MATCH_BASE rerun; the watermark updates on rerun completion, so the same facts can never trigger a second rerun — the mechanism that ends today's infinite MATCH_BASE cycle.

**Topic selection.** Next-topic choice reads the impact-ordered queue deterministically (resume-core ranks impact; workflow holds the cursor). The agent may phrase the question for a chosen topic; it may never choose the topic.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- TEST_SPEC strengthening (audit-flagged): workflow/TEST_SPEC.md:57 has no loop-termination case and would not catch the current deadlock. Add: (a) new facts -> exactly one match rerun -> decision `continue` -> BUILD_SELECTION_PLAN reached; (b) exhaustion with unresolved non-hard gaps -> advance with unresolved_requirements recorded; (c) unresolved hard requirement with requireHardRequirementsResolved -> blocked, not advanced.
- Contract test: multi-iteration loop simulation (two successive fact batches) reaches the section-14 tail — direct regression for the verified non-termination.
- Contract test: identical fact batch cannot trigger two reruns (watermark discipline).
- Boundary test: the workflow public surface contains no user-interaction or question-phrasing API (keeps the RKIT-I-0037 boundary structural).

## Alternatives Considered **[REQUIRED]**

- **Fixed max-iteration counter as the termination condition.** Rejected: an arbitrary cap either cuts real resolution short or spins pointlessly; section 14.D.9's condition (threshold/policy satisfied or gaps exhausted) is fully decidable from persisted state, so a cap adds dishonesty without adding safety.
- **Let resume-cli own loop termination.** Rejected: termination is checkpoint state, owned by workflow (CONTRACT_SURFACE_ALIGNMENT.md:43); CLI-owned termination recreates the audited situation where the product path bypasses the state machine and workflow's authority is dead code.
- **Clear facts_verified after each rerun instead of tracking a watermark.** Rejected in RKIT-I-0023 and equally here: facts_verified is cumulative audit data; the loop must terminate without destroying the trail.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. ResolutionLoopState DTO plus persistence (queue, exhaustion status, asked-question registry).
2. Termination predicate over tri-state MatchResult.decision and hard-requirement policy.
3. Single-rerun discipline over the RKIT-I-0023 watermark, with the deadlock regression test.
4. Unresolved-gap recording into the manifest field, plus exhaustion-honesty tests.
5. TEST_SPEC:57 termination cases and the no-interaction-surface boundary test.