---
id: req-001a-snapshot-data-envelope
level: task
title: "REQ-001a: Snapshot data envelope, canonicalizing comparator, and generator"
short_code: "RKIT-T-0011"
created_at: 2026-08-14T03:13:54.562491+00:00
updated_at: 2026-08-14T03:13:54.562491+00:00
parent: executable-release-gate-e2e
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/todo"
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-001a: Snapshot data envelope, canonicalizing comparator, and generator

## Parent Initiative

[[RKIT-I-0051]]

## Objective

This task establishes the snapshot mechanics substrate that all 13 data snapshots and the REQ-001 comparison test depend on: a versioned on-disk envelope shape, a shared canonicalizing projection helper, a reusable deep-equality comparator, and a deterministic regeneration script. It matters because it is the load-bearing infrastructure every downstream REQ-001 task consumes — a wrong choice here in envelope shape, canonicalization allowlist, or determinism handling compounds across all thirteen fixtures and the gate wiring built on top of them.

## Acceptance Criteria

- [ ] A canonicalizer function exists that sorts object keys deterministically and drops a documented allowlist of volatile fields (run ids, per-invocation identity added by RKIT-I-0022, wall-clock timestamps) so two runs of the same input produce byte-identical canonical JSON.
- [ ] A comparator function exists that takes `(expected_data, live_data)`, canonicalizes both, and returns a structured diff / boolean equality; on mismatch it emits a human-readable diff naming the divergent JSON pointer.
- [ ] `tools/regenerate_expected_snapshots.py` runs with no network/LLM, uses the fixture `config_hash` `'fixture-config-v1'`, and prints or writes the data block for each of the 13 snapshot ids; running it twice yields identical output (determinism proof).
- [ ] `fixtures/TEST_SPEC.md` documents the envelope (metadata fields retained, `data` added, prose moved to `comment`), the canonicalization allowlist, and the regenerate/review/commit procedure.
- [ ] No existing gate is wired to the comparator yet; PR gate stays green (`python3 tools/run_gate.py --pr --root .` passes unchanged).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — this is load-bearing cross-package infrastructure requiring design judgment over the envelope shape, the volatile-field allowlist, and determinism guarantees that every downstream REQ-001 task inherits; `codexSuitable` is false and a wrong choice compounds.

### Technical Approach

Establish the snapshot mechanics substrate that all 13 data snapshots and the comparison test depend on. Concretely:

- **Define the on-disk envelope shape.** The approved decision is a hybrid canonicalized-projection deep-equality model. The envelope is `{schema_version, config_hash, reviewed, comment, data}`: existing metadata fields are PRESERVED, a new `data` field carries the actual normalized / match / selection / manifest / audit output, and a `comment` field holds the former prose `expected_observations` review intent. (Binding: `comment` = former prose; do not drop the human review intent.)
- **Write a canonicalizing projection helper** (`canonicalize`) that sorts keys and drops a documented allowlist of volatile run-identity / timestamp fields per the `suite_manifest` `determinism_requirements` (`frozen_time_for_ids` + `record_versions_and_hashes`). The allowlist MUST include the RKIT-I-0022 per-invocation identity fields, so canonicalization normalizes away per-run identity before comparison.
- **Write a reusable deep-equality comparator** (`compare`) that canonicalizes both `expected_data` and `live_data`, then asserts full equality, returning a structured diff / boolean and, on mismatch, a human-readable diff naming the divergent JSON pointer.
- **Write a regeneration script** under `tools/` that produces the canonicalized data blocks from live `resume_core` outputs (`normalizeResume` / `normalizeJobModel` / `scoreMatch` / `rankResumeContent`) under the fixture `config_hash` `'fixture-config-v1'`, so the documented update procedure (regenerate + human review + commit) is executable.

Binding scope boundaries: do NOT wire the comparator into the gate yet, and do NOT overwrite the 13 fixtures yet. This task ships only the envelope spec + comparator + generator.

### Files

- `tests/support/snapshot_compare.py` (new) — canonicalizer + deep-equality comparator.
- `tools/regenerate_expected_snapshots.py` (new) — deterministic generator driving `resume_core.normalizeResume` / `normalizeJobModel` / `scoreMatch` / `rankResumeContent` under the fixture `config_hash`.
- `fixtures/TEST_SPEC.md` — document the `{schema_version, config_hash, reviewed, comment, data}` envelope and the regenerate+review+commit update procedure; strengthen the weak metadata-only clause at the "Expected Snapshot Fixtures" section.

### Dependencies

- No task dependencies — startable once the initiative is active.
- Cross-initiative semantic link: the canonicalization allowlist MUST account for the RKIT-I-0022 per-invocation run identity — canonicalization drops those fields so snapshots remain deterministic across runs.
- Downstream: this substrate is consumed by every subsequent REQ-001 task (the 13 fixture snapshots and the comparison gate), and relates to the applied-operations / validation threading of RKIT-I-0004; those tasks build on the envelope and comparator defined here.

### Risk Considerations

- **Cross-package blast radius.** This is load-bearing infrastructure for all REQ-001 work; a wrong envelope shape or comparator contract forces rework across all 13 fixtures and downstream gate wiring. Get the envelope and comparator signatures right up front.
- **Determinism.** The canonicalizer must produce byte-identical output across runs. Missing a volatile field in the allowlist (especially the RKIT-I-0022 per-invocation identity or wall-clock timestamps) produces flaky snapshots; the generator running twice must yield identical output as a determinism proof.
- **Scope-boundary bleed.** Do not wire the comparator into the gate and do not overwrite the 13 fixtures in this task; doing so exceeds scope and couples substrate delivery to fixture regeneration.
- **Protected-surface / straight-jacket constraints.** Regeneration drives live `resume_core` outputs and must not mutate protected core surfaces; the generator reads from and normalizes `resume_core` outputs, it does not modify them. Keep the PR gate green (`python3 tools/run_gate.py --pr --root .`) as evidence no protected invariant was disturbed.

## Verification Steps

1. `python3 tools/regenerate_expected_snapshots.py --root . > /tmp/snap1.txt && python3 tools/regenerate_expected_snapshots.py --root . > /tmp/snap2.txt && diff /tmp/snap1.txt /tmp/snap2.txt` (must be identical).
2. `python3 -c "from tests.support.snapshot_compare import canonicalize, compare; print(compare({'data':{'b':1,'a':2}}, {'data':{'a':2,'b':1}}))"` (equal projections compare equal).
3. `python3 tools/run_gate.py --pr --root .` (PR gate remains green).

## Status Updates

*To be added during implementation*