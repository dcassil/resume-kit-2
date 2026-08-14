---
id: chunk-3-match-result-driven
level: task
title: "Chunk 3: Match-result-driven relevance ranking replacing the discard stub"
short_code: "RKIT-T-0031"
created_at: 2026-08-14T21:14:46.040617+00:00
updated_at: 2026-08-14T21:38:52.510738+00:00
parent: resume-core-selection-planning-and
blocked_by: [RKIT-T-0030]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0003
---

# Chunk 3: Match-result-driven relevance ranking replacing the discard stub

## Parent Initiative

[[RKIT-I-0003]]

## Objective

Remove the `del match_result` discard (domain.py:402) and make relevance ranking actually consume the I-0002 MatchResult: content linked to resolved/required requirements outranks unlinked content; ranking deterministically reflects requirement resolution state. This is the core of the initiative — relevance ranking against the job finally has substrate.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `del match_result` removed; per-item relevance derives from MatchResult requirement rows: items tied to `exact_match`/`alias_match`/`verified_fact_match` rows rank above `related_match`/`possible_match`, which rank above unlinked content; unlinked orders by stable defaults (recency, then source order) with deterministic tie-breaking.
- [ ] Sensitivity test (the standing anti-regression guard): change one requirement's resolution state in the input MatchResult and assert the plan's ranking changes accordingly; also assert two identical runs produce identical plans.
- [ ] Item↔requirement linkage derives from existing structures (requirement evidence refs, term matches over claims — reuse the terminology/claim-fields substrates; no new inference heuristics beyond deterministic term/claim matching).
- [ ] Max-overflow truncation (Chunk 2) now drops by REAL relevance; relevance values recorded in plan entries.
- [ ] Snapshots re-baselined (selection-plan ordering will change; run-manifest/audit-report possibly), no-drift proven, driver-reviewed; PR + smoke green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

### Technical Approach

- Build a requirement→content index: for each MatchResult requirement row, use its evidence/matched-term refs (and the claim-field provenance) to locate resume items (skills entries, experience bullets) that support it. Deterministic string/term matching only.
- Relevance score bands: e.g. resolved-hard 3, resolved-preferred/verified 2.5, related/possible 1.5, unlinked base 1.0 with recency/source-order tie-breakers — exact banding is implementation detail but MUST be documented in the module and stable.
- `rankResumeContent`'s signature already receives match_result; no surface change expected.

### Files

- `resume-core/resume_core/domain.py` (+ possibly a new `selection_ranking.py` module — prefer a new module over growing domain.py)
- `tests/unit/test_selection_ranking_unit.py` (new; sensitivity + determinism; mapped in suite_manifest, gate wiring deferred)
- `fixtures/expected/selection-plan.json` regenerate + review

## Verification Steps

1. `python3 -m unittest tests.unit.test_selection_ranking_unit -v`
2. `grep -n "del match_result" resume-core/resume_core/domain.py` → no match
3. Regenerate snapshots ×2 → no drift; review ordering changes
4. `python3 tools/run_gate.py --pr --root .` and `--smoke` green.

## Status Updates

- 2026-08-14: Implemented MatchResult-driven content ranking in a new `selection_ranking.py` module, wired `rankResumeContent` through it, and added focused unit coverage for resolution-state sensitivity, deterministic replay, relevance-based overflow dropping, and claim-field linkage.