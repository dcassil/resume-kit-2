---
id: interactive-resolve-loop-over
level: task
title: "Interactive resolve loop over TerminalIO with agent phrasing/interpretation, store-gated persistence, interaction recording; TEST_SPEC; close-out"
short_code: "RKIT-T-0133"
created_at: 2026-08-19T19:01:07.737931+00:00
updated_at: 2026-08-19T19:01:07.737931+00:00
parent: deterministic-match-resolve-and
blocked_by: ["RKIT-T-0131", "RKIT-T-0132"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0037
---

# Interactive resolve loop over TerminalIO with agent phrasing/interpretation, store-gated persistence, interaction recording; TEST_SPEC; close-out

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0037]]

## Objective **[REQUIRED]**

Make `resume resolve` genuinely interactive per vision 14.D: question → answer → explicit confirmation exchange over the I-0035 TerminalIO seam, with agent phrasing/interpretation and career-store-owned verification. Today `_resolve` consumes one pre-supplied stdin string, `_explicit_confirmation` is a keyword regex, the CLI pre-declares `verification_state: "user_verified"` before store validation, and an off-fixture "Yes, I have used Terraform for four years" persists nothing. Close out RKIT-I-0037.

## Acceptance Criteria **[REQUIRED]**

- [ ] Resolve loop: `getUnresolvedRequirements` → selected requirement → `generateClarificationQuestion` (agent phrasing) → `TerminalIO.ask` → `interpretUserAnswer` (structured claim/duration/evidence proposal) → core validation → `TerminalIO.confirm` displaying the EXACT fact text to persist → `store.upsertFact` with the store assigning verification state through its own confirmation gate. The CLI never passes `user_verified` as an input state; the `verifyFact(..., "user_verified", ...)` pre-declaration and `_explicit_confirmation` regex are deleted.
- [ ] Declined confirmation persists nothing and records the outcome; negative/unknown answers record requirement-resolution outcomes (explicit absence per RKIT-A-0006 item 1 — a resolution state, NOT a verification state).
- [ ] Every asked/answered/confirmed exchange is recorded via `store.recordInteraction` (RKIT-A-0001 `question_asked`, `answer_recorded` vocabulary) so I-0040 can reconstruct and I-0041 can suppress duplicate questions.
- [ ] Off-fixture affirmative answer with substance (e.g. Terraform, with a pinned fake-adapter interpretation fixture) produces a fact proposal that persists — killing the persists-nothing behavior; test included.
- [ ] Interactive resolve test over scripted TerminalIO: multi-exchange script (question → answer → confirmation) with the fake adapter; asserts store-validated persistence, store-owned final verification state, and recorded interactions.
- [ ] Resolve emits results compatible with workflow's resolution-loop surface (I-0026 `ResolutionLoopState` recording via `_record_latest_run_snapshot("RESOLVE_GAPS", ...)`) — the single-pass contract `run` will drive in I-0040 is preserved.
- [ ] TEST_SPEC strengthening (`resume-cli/TEST_SPEC.md` resolve + match sections, strengthen-only): exchange-script contract replaces single-stdin-string; explicit-affirmative confirmation step; blocking case (T-0131); inspect honesty (T-0132); off-fixture answer persistence.
- [ ] Initiative close-out: version bump root `pyproject.toml` 0.35.0 → 0.36.0, CHANGELOG entry, all gates green (`--pr`, `--future-contract`, `--smoke`), snapshot regen ×2 no-drift.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- TerminalIO seam (I-0035, `resume_cli/__init__.py` Protocol with `ask`/`confirm`, scripted deterministic mode) is built for exactly this — extend the scripted mode if confirm sequencing needs it, keeping driver argv-safety intact.
- `interpretUserAnswer` (I-0018) already returns polarity + denied-claim post-guard; `_fact_proposals(interpretation, context)` maps proposals — keep mapping thin, validation in core/store.
- Store confirmation gate: `upsertFact` returns `confirmation_required`; the store's `verifyFact` transition engine owns state transitions — feed it the confirmation exchange evidence, let it decide the resulting state.
- Smoke drives resolve with scripted answers (AWS/GraphQL/architecture) — the confirmation step must be added to smoke's script; this may require a lockstep edit to protected `tools/run_smoke.py` (AUTHORIZED if needed — minimal, report prominently, commit --no-verify).
- Interaction recording: `store.recordInteraction` (`career-store/career_store/store.py:892`); use its existing event vocabulary.

### Dependencies
RKIT-T-0131 (decision routing), RKIT-T-0132 (core-selected topic).

### Risk Considerations
This is the largest behavioral change to a smoke-exercised flow — the resolve exchange script must be updated everywhere it is driven (smoke, E2E, contract tests). The store's confirmation gate semantics (I-0012-adjacent) decide final states; do not simulate them in the CLI. Watch `resume_cli/__init__.py` line cap (1383/1500) — the loop may need a private `resume_cli/_resolve.py`.

### Execution profile
Recommended Agent: opus + high

## Status Updates **[REQUIRED]**

*To be added during implementation*
