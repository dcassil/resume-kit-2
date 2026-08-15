---
id: parent-child-directional-semantics
level: task
title: "parent/child directional semantics and contradicts conflict signals"
short_code: "RKIT-T-0051"
created_at: 2026-08-15T01:23:28.383850+00:00
updated_at: 2026-08-15T01:49:52.959388+00:00
parent: relationship-aware-matching-and
blocked_by: [RKIT-T-0050]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0007
---

# parent/child directional semantics and contradicts conflict signals

## Parent Initiative

[[RKIT-I-0007]]

## Objective

Implement matching semantics for the restored parent/child relationship types and the contradicts extension (RKIT-I-0007 Requirement 4; RKIT-A-0006 item 5): directional candidates labeled with the parent/child path — a child fact supports its parent's requirement as related-strength evidence, never exact; contradicts relationships surface as conflict signals (consumed by RKIT-I-0008's workflow), never as matches.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] parent/child relationships (vocabulary restored in I-0005 T-0041) produce DIRECTIONAL candidates: child fact → parent-concept requirement yields related-strength support labeled with the parent/child path in viaRelationships; direction is honored (parent fact does not claim child-specific expertise as exact).
- [ ] Neither direction ever yields exact_match or alias_match through a parent/child edge; the T-0050 policy function encodes this.
- [ ] contradicts relationships NEVER produce a match candidate; they emit a typed conflict signal in the findCandidateMatches result (shape documented for I-0008 consumption) and do not silently drop.
- [ ] Tests cover both directions, the policy mapping for parent/child under both config settings, and the contradicts signal shape.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Extends the T-0049 traversal + T-0050 policy: parent/child edges map to related-strength permitted matchTypes with direction metadata; contradicts maps to a conflict-signal emission path instead of the candidate list. Keep signal shape minimal and typed (factId, relationshipId, contradictedFactId/requirement context).

### Dependencies

RKIT-T-0050 (policy function is where these semantics live).

### Risk Considerations

Direction bugs are silent honesty bugs — test both orientations explicitly. I-0008 consumes the signal shape; document it in the result contract comment.

### Execution profile

Recommended Agent: opus + medium

Rationale: focused extension of an established policy mechanism; the design (directional related-strength, signal-not-match) is fully decided.

## Status Updates

- 2026-08-15: Implemented directional parent/child relationship traversal in `career-store/career_store/store_support.py` and `store.py`.
  - Direction convention: `parent` rows mean `from_fact_id` is parent and `to_fact_id` is child; `child` rows mean `from_fact_id` is child and `to_fact_id` is parent.
  - Policy: child-to-parent traversal emits `related_match`; parent-to-child traversal emits `possible_match`; neither path is promoted by alias/related config.
  - `contradicts` now returns no policy match and `findCandidateMatches` emits deterministic `conflict_signals` instead.
  - Added unit coverage in `tests/unit/test_career_store_relationship_confirmation_unit.py`; targeted unit file passes with `PYTHONPATH=career-store:resume-core`.
- 2026-08-15: Required verification completed: PR gate, smoke gate, full unit discovery, and migration checks all pass. Straight Jacket verification still reports pre-existing protected-file checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`; this task did not edit protected files.