---
id: chunk-4-relationship-driven-alias
level: task
title: "Chunk 4: Relationship-driven alias/related resolution and classification generalization"
short_code: "RKIT-T-0026"
created_at: 2026-08-14T19:46:11.317799+00:00
updated_at: 2026-08-14T21:01:49.007261+00:00
parent: resume-core-deterministic
blocked_by: [RKIT-T-0025]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0002
---

# Chunk 4: Relationship-driven alias/related resolution and classification generalization

## Parent Initiative

[[RKIT-I-0002]]

## Objective

Generalize alias/related resolution beyond the closed fixture vocabularies: introduce a `TermRelationship` input ({from, to, kind: alias/related/parent/child/contradicts, provenance}) that callers supply from career-store stored relationships, demoting `_TERM_VARIANTS` / `_RELATED_REQUIREMENT_TERMS` / `_GENERIC_TERMS` (domain.py:96-142) to seed/fixture data. Also generalize `_infer_classification` so any "N+ years" phrasing marks a requirement required — not the literal "8+" tuned to the E2E fixture (domain.py:840). Resolution today only works for react/aws/graphql/responsive-design/saas/leadership; this chunk makes it work for arbitrary vocabularies without new code.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `scoreMatch` (and the resolution path) accepts an optional `term_relationships` input; a `TermRelationship` schema with {from, to, kind ∈ {alias, related, parent, child, contradicts}, provenance} is defined and validated (typed rejection for unknown kinds/missing fields).
- [ ] Supplied relationships drive resolution at the correct ladder rungs: `alias` resolves at the alias rung; `related`/`parent`/`child` resolve at the related rung ONLY (never satisfying hard requirements by default); `contradicts` never produces a positive resolution. The "Azure is not proof of AWS" invariant holds and is regression-tested with a relationship-supplied case (related Azure→AWS must NOT yield exact_match or resolve a hard AWS requirement).
- [ ] Input relationships are sorted deterministically before application — identical relationship sets in any supply order produce identical MatchResults (unit-tested with shuffled input).
- [ ] The closed vocabularies remain ONLY as seed data (fixtures keep passing without callers supplying relationships); the mechanism no longer requires editing resume-core to support a new term. resume-core does NOT import career-store (dependency direction preserved, grep-verifiable).
- [ ] `_infer_classification` generalizes: "5+ years", "10+ years", "3+ years experience" all infer required; unit test covers several phrasings plus a negative case ("preferred: 5+ years" stays preferred if the surrounding classification says so). PR + smoke green; snapshots regenerated + re-reviewed only if scores shift.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec: yes with a tight prompt; the ladder-rung mapping and the Azure/AWS invariant test need driver review.

### Technical Approach

- Add the `TermRelationship` schema to `schemas.py` and thread an optional `term_relationships` parameter through `scoreMatch`/resolution internals. Merge supplied relationships with the built-in seed vocabularies (seeds stay so existing fixtures/tests pass); sort merged relationships by a canonical key (from, to, kind) before application.
- Map kinds to ladder rungs conservatively: alias → alias rung; related/parent/child → related rung; contradicts → blocks the pair from any positive rung. Preserve ladder ordering (exact → alias → verified_fact → related → possible → unknown).
- Replace the "8+" literal in `_infer_classification` with a pattern over `N+ years` phrasings (regex on the normalized requirement text), keeping any existing explicit-classification precedence intact.
- Callers (workflow/CLI) fetching stored relationships from career-store is FUTURE work owned by those packages — this chunk only defines and consumes the input contract; tests supply relationships directly.

### Files

- `resume-core/resume_core/domain.py`, `schemas.py`
- `tests/unit/test_term_relationship_resolution_unit.py` (new): rung mapping, shuffled-input determinism, Azure/AWS invariant, contradicts behavior
- `tests/unit/test_infer_classification_unit.py` (new): N+ years generalization
- Contract test strengthen-only realignment if the public surface gains the parameter

### Dependencies

- [[RKIT-T-0025]] — serialized on the domain.py chain; dimension evidence should reference relationship-driven resolutions consistently.
- Cross-initiative: career-store relationship persistence/confirmation is RKIT-I-0007's scope; resume-core only accepts input data here.

### Risk Considerations

- Truth hazard: mapping related-kind relationships too high in the ladder would let Azure prove AWS — the invariant test is the guard; be conservative.
- Determinism: unsorted relationship application is the flake vector; sort before apply, test with shuffled input.
- Seed-vocabulary regression: existing fixtures must keep resolving identically with no relationships supplied.

## Verification Steps

1. `python3 -m unittest tests.unit.test_term_relationship_resolution_unit tests.unit.test_infer_classification_unit -v`
2. `grep -rn "import career_store\|from career_store" resume-core/` (no matches)
3. `python3 tools/run_gate.py --pr --root .` and `--smoke` green; snapshot regenerate + review only if diffs appear.

## Status Updates

- 2026-08-14: Codex-implemented, reviewed, committed. New `term_relationships.py` (TermRelationship schema + merge/sort/index) and `requirement_classification.py` (general N+ years inference). Rung mapping conservative (alias→alias; related/parent/child→related only; contradicts blocks positive resolution). Azure→AWS invariant regression-tested (related_match, score 0, blocking, hardRequirementsResolved false). Shuffled-input determinism tested. Seed vocabularies preserved: ZERO snapshot drift. core_surface.json realigned (non-protected). 8 new unit tests green; PR 257 + smoke green; no career_store import.