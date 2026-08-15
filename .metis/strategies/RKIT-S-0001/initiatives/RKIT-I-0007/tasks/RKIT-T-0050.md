---
id: relationship-confirmation
level: task
title: "Relationship confirmation substrate, confirmRelationship, single match-policy function"
short_code: "RKIT-T-0050"
created_at: 2026-08-15T01:23:28.334360+00:00
updated_at: 2026-08-15T01:23:28.334360+00:00
parent: relationship-aware-matching-and
blocked_by: ["RKIT-T-0049"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0007
---

# Relationship confirmation substrate, confirmRelationship, single match-policy function

## Parent Initiative

[[RKIT-I-0007]]

## Objective

Give relationships stored confirmation status and enforce it in one place (RKIT-I-0007 Requirement 3): `fact_relationships`/`relationships` gains confirmation_status (unconfirmed/user_confirmed), confirmed_by_provenance, confirmed_at via the migration registry; addRelationship records agent rows as unconfirmed; new `confirmRelationship` (user provenance, idempotent) is the only path to user_confirmed; a single policy function maps (relationship type, confirmation status, config) → permitted matchType enforcing allowUnverifiedAliasCreation:false and allow_related_as_equivalent.

## Acceptance Criteria

- [ ] Registry migration adds confirmation_status/confirmed_by_provenance/confirmed_at to the relationships table with unconfirmed backfill; migration checker realigned additively.
- [ ] addRelationship stores agent-created relationships as unconfirmed (no more echo-only `requires_confirmation_for_equivalence` at old store.py:448 — the stored status is authoritative).
- [ ] `confirmRelationship(relationshipId, provenance)` validates user provenance (structural, per the I-0006 authority conventions), is idempotent, and is the ONLY path to user_confirmed. Typed errors for unknown ids/invalid provenance.
- [ ] ONE policy function maps (type, confirmationStatus, config) → permitted matchType; matching consults it exclusively (no scattered conditionals). Under allowUnverifiedAliasCreation:false, unconfirmed alias/equivalent contributes at most possible_match — never alias_match; after confirmRelationship, alias_match is granted. Both directions tested.
- [ ] Candidate DTO viaRelationships entries carry the stored confirmationStatus.
- [ ] Store surface entry for confirmRelationship DEFERRED to the protected approval batch (guardrail pins the function set — established pattern); method + tests work regardless.
- [ ] PR + smoke gates green; migration checks green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Migration 007 appends the columns; policy function lives beside the T-0049 candidate generation (store_support.py or a small matching_policy module). Config keys flow through the store's existing policy/config parameter conventions.

### Dependencies

RKIT-T-0049 (typed candidate generation is where the policy plugs in).

### Risk Considerations

Existing tests/fixtures may rely on unconfirmed aliases matching — realign strengthen-only (unconfirmed → possible_match is the documented contract). Smoke: workflow may create relationships; ensure its legitimate paths still work via possible_match or add confirmation with user provenance where the fixture genuinely represents user-confirmed data.

### Execution profile

Recommended Agent: opus + high

Rationale: the enforcement substrate the vision guardrail (allowUnverifiedAliasCreation:false) has lacked; single-chokepoint design decision with cross-session persistence.

## Status Updates

*To be added during implementation*
