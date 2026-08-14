---
id: req-010a-tool-manifest-capability
level: task
title: "REQ-010a: tool_manifest capability honesty, implement two and defer two"
short_code: "RKIT-T-0016"
created_at: 2026-08-14T03:14:05.631317+00:00
updated_at: 2026-08-14T17:59:08.735579+00:00
parent: executable-release-gate-e2e
blocked_by: [RKIT-T-0011, RKIT-T-0020]
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-010a: tool_manifest capability honesty, implement two and defer two

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Make `tool_manifest.json` honest about which required capabilities are actually backed by a real tool. This task retains the two capabilities that gain a real implementing tool in Wave 1 (`snapshot_review_helpers`, `migration_checkers`) and removes the two that do not yet have an implementation (`render_parse_back_validators`, `audit_validators`), realigning the contract test and protected spec so the manifest, its tests, and its documentation all agree. It matters because the manifest is a PROTECTED release-gate artifact whose contract test asserts an exact capability set — a dishonest manifest either blocks the gate falsely or claims capabilities that do not exist.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `tool_manifest.json` `required_capabilities` no longer lists `render_parse_back_validators` or `audit_validators`; it retains `snapshot_review_helpers` and `migration_checkers`, each backed by a `tools[]` entry with a matching kind and full documentation fields (path, kind, supports_gate, invokes_surfaces, reads, writes, release_blocking, description).
- [ ] `tests/contract/test_tools_contract.py` asserts the new exact `required_capabilities` set and passes.
- [ ] `tools/TEST_SPEC.md` capability list matches the manifest.
- [ ] Straight-jacket manifest re-registered for both protected files; verify passes; change documented as RKIT-A-0006 realignment.
- [ ] PR gate green (`test_tools_contract` + boundary `test_tools_guardrails`).

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the proposal marks this task `codexSuitable: false`; it coordinates edits across a PROTECTED manifest, its PROTECTED spec, a non-protected contract test, and the straight-jacket registration in lockstep, with contract-realignment authorization (RKIT-A-0006) that requires human/agent judgment rather than mechanical execution.

### Technical Approach

Make `tool_manifest.json` honest per the open-design recommendation, following the binding APPROVED DECISION: **KEEP** `snapshot_review_helpers` and `migration_checkers`, each backed by a real `tools[]` entry — `snapshot_review_helpers` is satisfied by the RKIT-T-0011 (REQ-001a) `regenerate_expected_snapshots.py` generator, and `migration_checkers` is satisfied by the RKIT-T-0020 (REQ-007b) checker tool. **REMOVE** `render_parse_back_validators` and `audit_validators` from `required_capabilities`, deferring them to their Wave-2 owning work.

Concretely:

- In `tool_manifest.json`, remove `render_parse_back_validators` and `audit_validators` from `required_capabilities`, leaving the retained six-member set.
- Add a `tools[]` entry for each retained capability with a real `kind` (`snapshot_review_helper`, `migration_checker`) and complete documentation fields: path, kind, supports_gate, invokes_surfaces, reads, writes, release_blocking, description.
- Because `tool_manifest.json` is PROTECTED and `tests/contract/test_tools_contract.py` asserts the EXACT `required_capabilities` set (currently including the two being removed), the manifest and the test must be updated together. Edit the contract test's expected set to the new 6-member list.
- Update `tools/TEST_SPEC.md`'s "Expected Structure" capability list to match the manifest.
- This edit is authorized as **contract realignment per RKIT-A-0006** and requires straight-jacket re-registration of `tool_manifest.json` and `tools/TEST_SPEC.md`. Note `tests/contract/test_tools_contract.py` is NON-protected and needs no re-registration.

### Files

- `tools/tool_manifest.json` (PROTECTED) — remove 2 capabilities from `required_capabilities`, add `snapshot_review_helper` + `migration_checker` tool entries; re-register.
- `tests/contract/test_tools_contract.py` (NON-protected) — update the asserted `required_capabilities` set to the new 6-member list.
- `tools/TEST_SPEC.md` (PROTECTED) — update the "Expected Structure" capability list to match; re-register.
- `.straight-jacket/manifest.json` — re-register `tool_manifest.json` and `TEST_SPEC.md`.

### Dependencies

- [[RKIT-T-0011]] — REQ-001a defines the snapshot data envelope + shared canonicalizing comparator + generator (`regenerate_expected_snapshots.py`); its generator is the real tool that backs the retained `snapshot_review_helpers` capability. This task cannot honestly register that capability until the tool exists.
- [[RKIT-T-0020]] — REQ-007b implements the migration-checker tool for the four migration cases; its checker is the real tool that backs the retained `migration_checkers` capability, so this task depends on it to register that capability truthfully.
- Cross-initiative/semantic links: the deferred `render_parse_back_validators` and `audit_validators` capabilities move to their Wave-2 owning work (not this initiative). Downstream gate consumers (e.g. RKIT-I-0004 gate-threading work) rely on the manifest's `required_capabilities` being honest, so the realignment here must be complete before those consumers assert against it.

### Risk Considerations

- **Protected-surface / straight-jacket lock-step**: `tool_manifest.json` and `tools/TEST_SPEC.md` are PROTECTED. Editing either without re-registering the straight-jacket manifest will fail `straight-jacket verify`. The manifest, its spec, the non-protected contract test, and the registration must all move together in one coherent change, authorized explicitly as RKIT-A-0006 realignment.
- **Cross-package / cross-consumer blast radius**: the contract test asserts an EXACT set; a mismatch between the manifest, the test's expected set, and TEST_SPEC.md breaks the PR gate. Downstream gate consumers keyed to `required_capabilities` will also break if the set drifts from what they expect.
- **Scope-boundary bleed**: this task ONLY retains/removes the four named capabilities and registers the two real tool entries. Do not implement `render_parse_back_validators` or `audit_validators` here (they are Wave-2), and do not add or alter unrelated capabilities.
- **Determinism**: the retained `tools[]` entries must fully and stably describe their real tools (all documentation fields present) so contract and boundary tests are deterministic and the gate result is reproducible.

## Verification Steps

1. `python3 -m unittest tests.contract.test_tools_contract tests.boundary.test_tools_guardrails`
2. `python3 tools/tools_guardrails.py --root .`
3. `straight-jacket verify`
4. `python3 tools/run_gate.py --pr --root .`

## Status Updates

*To be added during implementation*