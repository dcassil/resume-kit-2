---
id: model-sourced-uncertainty
level: task
title: "Model-sourced uncertainty/confidence mapping + TEST_SPEC generalization goldens — close-out"
short_code: "RKIT-T-0094"
created_at: 2026-08-17T16:26:27.104094+00:00
updated_at: 2026-08-17T16:26:27.104094+00:00
parent: resume-agent-model-based-resume
blocked_by: ["RKIT-T-0091", "RKIT-T-0092", "RKIT-T-0093"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0017
---

# Model-sourced uncertainty/confidence + TEST_SPEC generalization goldens — I-0017 close-out

## Parent Initiative

[[RKIT-I-0017]]

## Objective **[REQUIRED]**

Finish the honesty conversion and pin the generalization bar: (1) uncertainty and confidence are MODEL-SOURCED proposal-DTO fields end-to-end — the "ambiguous|various|several" keyword grep (audit refs __init__.py:406-413) and the hardcoded "high"/"medium" confidence strings (:73-92) are deleted; items the model marks uncertain surface with explicit uncertainty fields rather than being dropped. (2) `resume-agent/TEST_SPEC.md` (unprotected) is strengthened so a keyword matcher can no longer pass it: fixture-token assertions (:43, :57-58 refs) augmented/replaced with the non-fixture golden inputs and generalization assertions, each spec item naming its covering test. Initiative close-out with mutation probes.

## Acceptance Criteria **[REQUIRED]**

- [ ] Keyword-grep uncertainty and hardcoded confidence strings deleted from production code (grep-proof); uncertainty/confidence flow from the adapter payload through every proposal surface (extraction from T-0092/0093, plus the remaining public functions where they emit confidence — generateClarificationQuestion/interpretUserAnswer/proposeRewrite keep their CURRENT behavior semantics but must not fabricate confidence values the model didn't produce; where those functions aren't yet adapter-backed (RKIT-I-0018/0019 scope), their confidence fields become honest explicit placeholders (e.g. "unscored") rather than fake "high" — document this handoff).
- [ ] Uncertain items are SURFACED with uncertainty fields, never filtered; test with a golden whose pinned output marks an item uncertain.
- [ ] `resume-agent/TEST_SPEC.md`: golden-input matrix enumerated (ML-engineer resume, unknown+known JD, GraphQL+API JD), generalization assertions stated (every named skill appears; co-occurring skills retained; both requirements kept; every populated section extracted), each naming its covering test; the old satisfiable-by-keyword-matcher wording removed.
- [ ] Mutation probes (mutate → named failing test → revert): reintroduce a closed-lexicon filter → generalization test fails; hardcode a confidence string → model-sourced test fails; drop an uncertain item → surfacing test fails.
- [ ] `--pr`, `--smoke`, `--future-contract` green; verify clean; new module names listed for the deferred run_tests.py batch if bridging was used.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Only resume-agent/TEST_SPEC.md (unprotected); tools/TEST_SPEC.md is protected — untouched.
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0091..0093. Final task; after: initiative → completed, bump 0.19.0, push, handoff update (driver).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

*To be added during implementation*
