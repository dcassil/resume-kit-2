---
id: voice-length-constraint-plumbing
level: task
title: "Voice/length constraint plumbing + grounding/DTO/constraint batteries + TEST_SPEC reason fix — close-out"
short_code: "RKIT-T-0100"
created_at: 2026-08-17T17:23:40.603493+00:00
updated_at: 2026-08-17T17:43:59.438644+00:00
parent: resume-agent-grounded-rewrite
blocked_by: [RKIT-T-0098, RKIT-T-0099]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0019
---

# Voice/length constraints + batteries + TEST_SPEC reason fix — I-0019 close-out

## Parent Initiative

[[RKIT-I-0019]]

## Objective **[REQUIRED]**

Finish the constraint honesty and pin the spec: (1) `voice_constraints` — currently required in input then never referenced (audit ref :682) — enter the prompt contract AND get deterministic post-checks where checkable (tense/person heuristics); length limits are a generation parameter with a deterministic post-check that REJECTS (typed error), never truncates (:743-745's naive truncation dies); the prohibited-additions substring filter (:301-303) stops being the only defense — prohibited additions enter the prompt contract and the T-0099 grounding guard's term analysis covers paraphrase-adjacent cases via the fact-mapping requirement. (2) `resume-agent/TEST_SPEC.md`: `reason` added to the rewrite-return list (the :66-67 omission that licensed the drift), fixture-phrase grounding checks replaced with fact-mapping assertions, voice/length constraint assertions added (currently zero coverage). Initiative close-out.

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] Voice constraints flow into the builder/prompt and are post-checked deterministically where feasible (e.g. past-tense requirement violated by pinned fixture → typed constraint error; document which checks are deterministic vs model-trusted).
- [ ] Length: over-limit generated text → typed constraint error result; grep-proof that the truncation path is gone; a length-violating pinned fixture drives the test.
- [ ] Prohibited additions: present in the prompt contract; deterministic check retained as defense-in-depth; a fixture with a prohibited term added → rejected with a typed error naming the term.
- [ ] resume-agent/TEST_SPEC.md: rewrite-return list includes `reason`; fact-mapping grounding assertions named; voice/length assertions named; each item names its covering test.
- [ ] Mutation probes (mutate → named failing test → revert): re-add truncation → length test fails; drop the voice post-check → voice test fails; remove reason from an emitted op → DTO test fails; remove the grounding guard → ungrounded test fails.
- [ ] `--pr`, `--smoke`, `--future-contract` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Only resume-agent/TEST_SPEC.md (unprotected).
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0098/0099. Final task; after: initiative → completed, bump 0.21.0, push, handoff update (driver).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

- 2026-08-17: T-0099 committed (adapter-backed proposeRewrite, template/insertion/truncation/fabricated-target deleted, grounding guard w/ token-based added-content detection + allowed-set check, responsive-design regression, volatile-evidence key stabilization, validateChange-compatible ops; gates 515/smoke/verify green; driver probed missing-target typed error). Codex launched on the close-out: deterministic voice/length post-checks, prohibited-addition defense-in-depth, TEST_SPEC reason fix + constraint assertions, mutation probes.