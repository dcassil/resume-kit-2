---
id: req-001c-snapshot-comparison-test
level: task
title: "REQ-001c: Snapshot-comparison test diffing live outputs against baselines"
short_code: "RKIT-T-0013"
created_at: 2026-08-14T03:14:05.508491+00:00
updated_at: 2026-08-14T17:59:03.998371+00:00
parent: executable-release-gate-e2e
blocked_by: [RKIT-T-0011, RKIT-T-0012]
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-001c: Snapshot-comparison test diffing live outputs against baselines

## Parent Initiative

[[RKIT-I-0051]]

## Objective

This task makes the snapshots executable rather than prose: for every snapshot carrying a non-null data block, it regenerates the live output deterministically and asserts canonicalized deep-equality against the committed baseline via the REQ-001a comparator. It is the test that turns the reviewed data baselines into an enforced contract — failing loudly and naming the divergent pointer the moment a live output drifts from what was reviewed.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] For every snapshot with `data != null`, the test regenerates the live output and asserts canonical deep-equality; snapshots with `data: null` are explicitly skipped with a reason (not silently passed).
- [ ] A deliberate mutation of one snapshot's data block causes the test to FAIL with a message naming the divergent JSON pointer (mutation probe demonstrated in the task's verification, then reverted).
- [ ] The new test is included in the PR gate command output (`python3 tools/run_gate.py --pr --root .` executes it).
- [ ] If `tools/run_tests.py` is edited, the `.straight-jacket` manifest is re-registered per RKIT-A-0006 (strengthen-only: this ADDS coverage, weakens nothing).
- [ ] PR gate green with all real snapshots matching current deterministic output.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the proposal marks this task codexSuitable: false; it spans a protected surface (`tools/run_tests.py`) with a straight-jacket re-registration constraint and requires judgment about where the test lands relative to the auto-discovered contract set.

### Technical Approach

Add an executable test that makes the snapshots enforceable rather than descriptive. For each snapshot with a non-null data block, the test regenerates the live output deterministically and asserts canonicalized deep-equality against the committed data via the REQ-001a comparator. Snapshots whose `data` is null must be explicitly skipped with a stated reason — never silently passed.

Placement options (either is acceptable):
- Extend the unblocked, NON-protected `tests/contract/test_fixtures_contract.py`, or
- Add a new `tests/snapshots` module wired into the suite.

The test must fail loudly, naming the divergent JSON pointer, whenever a live output drifts from the reviewed baseline.

Binding guidance from the approved decision: prove the test actually catches drift by running a mutation probe — deliberately mutate one snapshot's data block, confirm the test FAILS naming the pointer, then revert. If the test lands OUTSIDE the auto-discovered contract set and therefore must edit `tools/run_tests.py` (PROTECTED) to register the new module into `CURRENT_TEST_MODULES`, you MUST re-register the straight-jacket manifest. This is a strengthen-only change (it adds coverage and weakens nothing), consistent with RKIT-A-0006.

Registration wiring: add the new test to `tests/suite_manifest.json` `runner_commands` (NON-protected), and, only if placed under `tests/snapshots` and outside the already-discovered contract set, into the PR gate's module list in `tools/run_tests.py`.

### Files

- `tests/snapshots/test_expected_snapshots_match_live_output.py` (new) OR extension of `tests/contract/test_fixtures_contract.py` (non-protected)
- `tests/suite_manifest.json` — add snapshot test to `runner_commands` (NON-protected)
- `tools/run_tests.py` (PROTECTED) — add module to `CURRENT_TEST_MODULES` only if the test lands outside the already-discovered contract set; requires straight-jacket re-registration

### Dependencies

- [[RKIT-T-0011]] — provides the REQ-001a snapshot data envelope, the shared canonicalizing comparator, and the generator this test relies on to regenerate and compare live output.
- [[RKIT-T-0012]] — populates the 13 expected/*.json snapshots with reviewed data (and moves prose to comment); this test asserts live output against those reviewed baselines, so they must exist first.

Cross-initiative/semantic links: the enforced snapshot baselines are what downstream RKIT-I-0004 (applied-operations threading) validates against; any xfail wiring belongs to the owning package/suite initiative that owns `tools/run_tests.py`, which is why edits there carry the straight-jacket re-registration obligation rather than being made ad hoc here.

### Risk Considerations

- Protected-surface / straight-jacket constraint: editing `tools/run_tests.py` touches a PROTECTED file. Only strengthen-only edits are permitted (adding a module = adding coverage), and the `.straight-jacket` manifest MUST be re-registered per RKIT-A-0006. Prefer landing the test inside the auto-discovered contract set to avoid touching the protected file at all.
- Cross-package blast radius: the test regenerates live output across the snapshot surface; a broad or non-canonical comparison could couple this test to incidental formatting rather than reviewed content, producing brittle cross-package failures. Rely strictly on the REQ-001a canonicalizing comparator.
- Determinism: regeneration must be deterministic, or the test will flake. Any non-deterministic input (timestamps, ordering, run identity) must be canonicalized away by the comparator, and the mutation probe must demonstrate a true failure rather than incidental noise.
- Scope-boundary bleed: this task adds the comparison test and its registration only. It must not modify the snapshot data (RKIT-T-0012's job) nor the comparator/envelope/generator (RKIT-T-0011's job); doing so would blur task boundaries and undermine the reviewed baselines.

## Verification Steps

1. `python3 -m unittest tests.snapshots.test_expected_snapshots_match_live_output` (or the contract module) — passes.
2. Mutation probe: temporarily edit `fixtures/expected/normalized-resume.json` data, rerun the test, confirm it FAILS naming the pointer, then `git checkout` the file.
3. `python3 tools/run_gate.py --pr --root .` (green).
4. `npx --yes @straight-jacket/cli verify` (or the repo's straight-jacket verify) if `run_tests.py` was touched.

## Status Updates

*To be added during implementation*