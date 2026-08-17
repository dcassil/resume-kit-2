---
id: interpretuseranswer-via-adapter
level: task
title: "interpretUserAnswer via adapter: section-8 schema, polarity + denied-claim post-guard, negation/persistence batteries — close-out"
short_code: "RKIT-T-0097"
created_at: 2026-08-17T16:59:31.475797+00:00
updated_at: 2026-08-17T16:59:31.475797+00:00
parent: resume-agent-targeted-interview
blocked_by: ["RKIT-T-0095", "RKIT-T-0096"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0018
---

# interpretUserAnswer via adapter: polarity + denied-claim post-guard — I-0018 close-out

## Parent Initiative

[[RKIT-I-0018]]

## Objective **[REQUIRED]**

Close the Honesty Gate violation: today "No, I have never used AWS professionally" produces a POSITIVE fact proposal "AWS experience" with suggested_state possible_match (audit refs __init__.py:594-601, :623-633 — no negation gating), interpretation only covers three topic substrings with a 7-item AWS list (:594-621, :595). After this task: `interpretUserAnswer` runs through the adapter emitting the section 8 schema for ARBITRARY topics; the model classifies polarity; a DETERMINISTIC post-validation guard rejects any payload containing a positive fact proposal for a claim classified as denied (belt and suspenders — the Honesty Gate cannot rest on the model alone). Denials produce an explicit-absence requirement resolution and ZERO positive fact proposals. Initiative close-out.

## Acceptance Criteria **[REQUIRED]**

- [ ] `interpretUserAnswer` → T-0095 builder → adapter → section-8 payload mapped into the proposal envelope (requirementResolutions w/ canonical 4.4 suggested states + confidence; factProposals w/ answer-text evidence linkage + verification_state; evidenceProposals). Topic-substring paths + AWS list DELETED (grep-proof).
- [ ] Deterministic post-guard: payload with polarity=denied AND a positive fact proposal for the denied claim → typed schema_invalid/guard error result, never emitted; test drives it with a deliberately-inconsistent in-test fixture.
- [ ] Negation battery: multiple denial phrasings ("No, I have never used X", "I haven't", "not professionally", "only in school" where that constitutes denial-of-professional-use) → zero positive fact proposals + explicit-absence resolution (absence modeled as a RESOLUTION concern per RKIT-A-0006 decision 1, not a verification state). The verified AWS-denial defect has a named regression.
- [ ] Qualified answers ("yes, but only internal tools") → partial/hedged resolution with the hedge captured, never flattened to an unqualified positive (named test).
- [ ] The T-0094 "unscored" placeholders on this surface are REPLACED by model-sourced confidence (this function is now adapter-backed; update the T-0094 handoff docstring).
- [ ] resume-agent/TEST_SPEC.md: negation + persistence batteries and non-fixture interview goldens enumerated w/ covering tests; the canned-answer assertions (:57-58 refs) replaced.
- [ ] Mutation probes: remove the post-guard → inconsistent-fixture test fails; re-add a topic-substring filter → arbitrary-topic test fails; flatten a hedge → qualified test fails.
- [ ] `--pr`, `--smoke`, `--future-contract` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Same adapter seam as T-0092/0096. Smoke drives interpretUserAnswer (CLI RESOLVE_GAPS path) — pin fixtures for its exact inputs; the workflow resolution loop consumes these outputs, so run --smoke carefully and check the question_answer flow stays green.
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0095/0096. Final task; after: initiative → completed, bump 0.20.0, push, handoff update (driver).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.
- workflow/resolution_loop + resume-cli consume interpretation outputs — cross-package breakage surfaces in --smoke; fix by pinning fixtures, never by weakening.

## Status Updates **[REQUIRED]**

*To be added during implementation*
