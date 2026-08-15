---
id: interactions-substrate-table
level: task
title: "Interactions substrate: table migration, recordInteraction/listInteractions, no-write-path boundary"
short_code: "RKIT-T-0054"
created_at: 2026-08-15T02:07:49.663909+00:00
updated_at: 2026-08-15T02:09:16.694579+00:00
parent: conflict-audit-recovery-and
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0008
---

# Interactions substrate: table migration, recordInteraction/listInteractions, no-write-path boundary

## Parent Initiative

[[RKIT-I-0008]]

## Objective

Build the RKIT-A-0001 item 2-3 interactions substrate (RKIT-I-0008 Requirements 2-3): append-only interactions table via the migration registry, public recordInteraction/listInteractions with the decided vocabulary, and executable enforcement that no write path exists from interaction records to fact verification state.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Registry migration creates `interactions(id, interaction_type, subject_id, input_json, result_json, created_at)` — append-only (no UPDATE/DELETE paths); migration checker realigned additively.
- [ ] `recordInteraction()` validates interaction_type against the decided vocabulary (question_asked, answer_recorded, fact_confirmed, rewrite_accepted, rewrite_modified, rewrite_rejected) with typed errors for unknown types/malformed shapes; subject_id is an opaque ref (resume-core operation ids, career-store fact ids — no dereferencing/validation against foreign stores).
- [ ] `listInteractions(filter)` filters by interaction_type, subject_id, and time range with deterministic ordering; malformed filters raise typed errors; absent values return empty.
- [ ] Interaction ids are content-hashed over (interaction_type, subject_id, input_json) with INSERT OR IGNORE — duplicate replays produce single rows (tested).
- [ ] The RKIT-A-0001-mandated boundary enforcement: behavioral probe (recordInteraction of fact_confirmed does not alter the referenced fact's verification state) AND structural assertion (the interactions module has no import path to fact-verification mutation helpers). Module-level separation per the Detailed Design.
- [ ] Writes run on the transaction substrate; store surface entries for the two functions DEFERRED to the protected approval batch (established pattern).
- [ ] PR + smoke gates green; migration checks green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

New `career_store/interactions.py` module (structural separation is the point — it must not import verification/state-mutation helpers); store exposes thin recordInteraction/listInteractions delegating to it. Migration 008 appends the table.

### Dependencies

I-0006 complete (fact_confirmed interactions reference its confirmation evidence conceptually; no code dependency beyond the store). First task of the I-0008 serial chain.

### Risk Considerations

Keep interactions strictly append-only — no update path even for corrections (corrections are new rows). The structural import assertion must be robust to refactors (assert on module attributes/imports, not line numbers).

### Execution profile

Recommended Agent: opus + high

Rationale: new substrate with an ADR-mandated boundary invariant; the module-separation design is the enforcement mechanism.

## Status Updates

*To be added during implementation*

- 2026-08-15: Implemented migration 008, `career_store.interactions`, store `recordInteraction`/`listInteractions`, additive migration fixture realignment, and focused interaction boundary tests. Focused interaction tests and migration checks pass locally; full required gates pending.
- 2026-08-15: Required verification is green: PR gate, smoke gate, unit discovery, and migration checks all passed.
