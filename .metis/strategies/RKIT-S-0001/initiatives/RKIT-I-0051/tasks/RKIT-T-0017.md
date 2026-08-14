---
id: req-010b-tools-guardrails
level: task
title: "REQ-010b: tools_guardrails capability-has-tool backstop"
short_code: "RKIT-T-0017"
created_at: 2026-08-14T03:14:05.672153+00:00
updated_at: 2026-08-14T17:59:09.450363+00:00
parent: executable-release-gate-e2e
blocked_by: [RKIT-T-0016]
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-010b: tools_guardrails capability-has-tool backstop

## Parent Initiative

[[RKIT-I-0051]]

## Objective

This task installs the durable enforcement backstop in the tools guardrail so the tool manifest can never again declare a phantom capability. For every entry in `required_capabilities` it asserts that at least one `tools[]` entry supplies a matching implementing kind, hard-blocking otherwise. This is what makes the REQ-010 honesty fix (RKIT-T-0016) self-enforcing rather than a one-time cleanup.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `tools_guardrails.py` maps each `required_capabilities` entry to an expected tool kind and hard-blocks if no `tools[]` entry has that kind, with a clear remediation message naming the orphaned capability.
- [ ] Running the guardrail against the current (RKIT-T-0016-corrected) manifest passes.
- [ ] A negative probe (add a phantom capability with no tool to a temp manifest copy) is hard-blocked.
- [ ] `tests/boundary/test_tools_guardrails.py` gains a case for the orphaned-capability rejection; no existing assertion weakened.
- [ ] Straight-jacket re-registered; verify passes; PR gate green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the proposal marks this task `codexSuitable: false`; it edits PROTECTED, strength-only guardrail surfaces that carry cross-package blast radius and a straight-jacket re-registration step, which demand human-supervised judgment.

### Technical Approach

Add the capability-has-tool enforcement to `tools/tools_guardrails.py`:

- For every entry in the manifest's `required_capabilities`, derive an expected tool kind (capability name singularized / mapped to kind) and assert at least one `tools[]` entry declares that kind. If none does, hard-block.
- The hard-block failure must emit a clear remediation message that names the orphaned capability, so a future manifest edit that re-introduces a phantom capability is caught immediately with actionable output.
- This is the durable fix that makes REQ-010's manifest honesty self-enforcing: once landed, the guardrail structurally prevents any declared capability from lacking an implementing tool.

Binding approved-decision guidance: `tools/tools_guardrails.py` and `tests/boundary/test_tools_guardrails.py` are PROTECTED. Per RKIT-A-0006 they are strengthen-only — add the new check and its test case, never weaken or remove an existing assertion — and both must be re-registered with straight-jacket after editing. This task MUST land AFTER RKIT-T-0016 so the manifest already satisfies the new capability-has-tool check; landing it first (or against an un-corrected manifest) would red-fail the whole repo.

### Files

- `tools/tools_guardrails.py` (PROTECTED — add capability-has-tool check; re-register)
- `tests/boundary/test_tools_guardrails.py` (PROTECTED — add a case proving a capability with no implementing tool is hard-blocked; strengthen-only; re-register)
- `.straight-jacket/manifest.json` (re-register)

### Dependencies

- [[RKIT-T-0016]] — REQ-010a resolves the tool_manifest capability honesty (implement two, defer two) and realigns the contract test. Its correction must land first so the manifest already satisfies the new capability-has-tool check; running this guardrail against an un-corrected manifest would hard-block and red-fail the repo.
- Downstream: this backstop protects the honesty invariant that RKIT-I-0004 (applied-operations threading) and other consumers of the manifest rely on. The PROTECTED surfaces belong to the guardrail/boundary layer whose owning package initiative governs the xfail policy.

### Risk Considerations

- **Protected-surface / strengthen-only constraint**: Both edited files are PROTECTED under RKIT-A-0006. Any weakening of an existing assertion or a missed re-registration breaks the straight-jacket contract. Add-only; re-register after every edit.
- **Cross-package blast radius**: The guardrail runs in the PR gate. A too-strict or mis-mapped capability→kind rule can hard-block the whole repo for unrelated work, so the singularization/mapping must exactly match the corrected manifest.
- **Ordering / determinism**: Landing before RKIT-T-0016 red-fails the repo. The check must be deterministic — same manifest, same verdict — with no ordering-dependent or environment-dependent behavior.
- **Scope-boundary bleed**: This task adds only the capability-has-tool backstop. It must not re-open the manifest content decisions owned by RKIT-T-0016 or expand into unrelated guardrail rules.

## Verification Steps

1. `python3 tools/tools_guardrails.py --root .` (green)
2. Negative probe: add `"phantom_validators"` to a temp copy of `tool_manifest.json` `required_capabilities` with no matching tool, run the guardrail, confirm hard-block, discard the temp copy.
3. `python3 -m unittest tests.boundary.test_tools_guardrails`
4. `straight-jacket verify && python3 tools/run_gate.py --pr --root .`

## Status Updates

*To be added during implementation*