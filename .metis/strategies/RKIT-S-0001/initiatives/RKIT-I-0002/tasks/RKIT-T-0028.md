---
id: chunk-6-base-score-snapshots-on-i
level: task
title: "Chunk 6: Base-score snapshots on I-0051 substrate, TEST_SPEC strengthening, flat-key removal"
short_code: "RKIT-T-0028"
created_at: 2026-08-14T19:46:11.403175+00:00
updated_at: 2026-08-14T21:13:01.391402+00:00
parent: resume-core-deterministic
blocked_by: [RKIT-T-0027]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0002
---

# Chunk 6: Base-score snapshots on I-0051 substrate, TEST_SPEC strengthening, flat-key removal

## Parent Initiative

[[RKIT-I-0002]]

## Objective

Close out the initiative: record base-score snapshots for the smoke and E2E fixtures on the I-0051 snapshot substrate (approved decision: reuse the envelope/generator/comparison-test machinery, not a separate suite), strengthen the specs so the section 4.3 fields and section 13 `matching.*` keys are explicitly required (their absence is what certified binary `can_continue` with ad-hoc config), remove the deprecated flat config keys after migrating all in-repo callers (approved decision: remove at end of I-0002), and verify the initiative's guarded invariants hold end-to-end.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Base scores for the Job A and Job B smoke/E2E fixture flows are represented in `fixtures/expected/` envelopes (the existing match snapshots extended or new base-score snapshot entries added via the T-0011 generator) and enforced by the T-0013 comparison test — TEST_SPEC.md:106's requirement is met by executable assertion, not prose.
- [ ] Flat keys `policy` / `require_hard_resolution` REMOVED: all in-repo callers (resume-cli, workflow, fixtures, tests) migrated to `matching.*`; after removal, supplying a flat key is a typed validation error (unit-tested); grep shows no remaining producer.
- [ ] resume-core TEST_SPEC (and `tests/TEST_SPEC.md` where it describes match assertions) explicitly requires: all section 4.3 MatchResult fields including dimensions and tri-state decision, and the section 13 `matching.*` config vocabulary with unknown-key rejection. Strengthen-only.
- [ ] Guarded-invariant regression suite passes: related/possible never resolve hard requirements by default; identical inputs (including shuffled relationship supply) produce equivalent MatchResults; `decision:'blocked'` under requireHardRequirementsResolved with an unresolved hard requirement.
- [ ] Full verification: `--pr`, `--future-contract`, and `--smoke` gates all green; snapshot no-drift proof (regenerate twice, no diff); straight-jacket verify clean (no protected files should need editing in this chunk — if one does, stop and batch it for Daniel).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec: yes with a tight prompt; the flat-key removal sweep needs a careful grep-driven migration checklist.

### Technical Approach

- Extend `tools/regenerate_expected_snapshots.py` (NON-protected) if the base-score stages need distinct snapshot ids beyond the five existing match snapshots; follow the T-0011 envelope + T-0012 review procedure. Daniel reviews any new/changed baselines before commit.
- Migrate flat-key producers found by `grep -rn "require_hard_resolution\|'policy'\|\"policy\"" --include=*.py --include=*.json .` (excluding .metis/.agents); then delete the deprecation mapping from the Chunk 1 accessor so flat keys hit unknown-key rejection.
- Spec strengthening is additive prose + any new contract assertions in NON-protected contract tests. `tools/TEST_SPEC.md` is PROTECTED — this chunk should NOT need it; if a protected edit becomes necessary, batch for Daniel's password session rather than proceeding.
- Confirm `can_continue` disposition: keep as derived field (documented) — full removal belongs to downstream consumers' initiatives if ever.

### Files

- `fixtures/expected/` (extended/regenerated), `tools/regenerate_expected_snapshots.py` (if new stages)
- `resume-cli/resume_cli/__init__.py`, `workflow/__init__.py`, fixture/config files (flat-key migration)
- resume-core TEST_SPEC + `tests/TEST_SPEC.md` (strengthen-only)
- `tests/unit/test_matching_config_unit.py` (flat-key rejection case added)

### Dependencies

- [[RKIT-T-0027]] — all behavior chunks must be complete so the recorded base scores are final for this initiative.

### Risk Considerations

- Removal blast radius: the I-0001 lesson applies — flat-key removal hits CLI/workflow config producers; run `--smoke` after migration, before commit.
- Baseline finality: these snapshots become I-0003/I-0004's ground truth; the review must check dimension contributions look sane, not just that generation is deterministic.
- Protected-surface discipline: nothing here should touch protected files; treat any discovered need as a stop-and-batch signal, not a workaround license.

## Verification Steps

1. `python3 tools/regenerate_expected_snapshots.py --root . --write && git diff --stat fixtures/expected/` then rerun → no drift
2. `grep -rn "require_hard_resolution" --include=*.py --include=*.json . | grep -v .metis` → no producers
3. `python3 tools/run_gate.py --pr --root . && python3 tools/run_gate.py --future-contract --root . && python3 tools/run_gate.py --smoke --root .` all green
4. `straight-jacket verify` clean.

## Status Updates

### 2026-08-14 Chunk 6 implementation
- Confirmed existing expected match envelopes cover Job A initial, post-AWS, post-GraphQL, final, and Job B initial match results; snapshot comparison asserts full MatchResult data including scores, threshold, hardRequirementsResolved, decision, and dimensions.
- Removed deprecated flat matching config mapping and migrated matching-config producers in generator, CLI default config, contract tests, and E2E config to `matching.requireHardRequirementsResolved`.
- Added unit coverage for removed flat-key unknown-key rejection and strengthened non-protected test specs.
- Focused unit and snapshot comparison checks passed; full gates still pending.