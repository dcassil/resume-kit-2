---
id: req-009-scaffold-unit-tier-and-i
level: task
title: "REQ-009: Scaffold unit tier and I-0001-stable resume-core unit cases"
short_code: "RKIT-T-0021"
created_at: 2026-08-14T03:14:05.840188+00:00
updated_at: 2026-08-14T17:59:02.664230+00:00
parent: executable-release-gate-e2e
blocked_by: []
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-009: Scaffold unit tier and I-0001-stable resume-core unit cases

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Populate the currently empty `tests/unit` tier (today only a `.gitkeep`) with deterministic resume-core unit cases for behavior that already exists and is stable on current code, and map the PR gate's declared `unit` category to real modules so it no longer maps to zero. Critically, this task scopes those cases ONLY to surfaces that RKIT-I-0001 will NOT change, deliberately deferring the volatile surfaces so we do not write throwaway tests against soon-to-change behavior.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `tests/unit` contains real deterministic unit modules for at least `ats_sanitation` and `scoring_math` (current, I-0001-stable behavior); each runs with no LLM/network and passes twice identically.
- [ ] The unit modules are EXECUTED by the PR gate (`python3 tools/run_gate.py --pr --root .`) — the declared `unit` category no longer maps to zero modules for the covered categories.
- [ ] `date_normalization`, `requirement_normalization`, `change_validation`, `state_transitions`, and verification/resolution-enum unit cases are EXPLICITLY DEFERRED with an in-file comment naming RKIT-I-0001 chunk 6 (RKIT-T-0010) as owner (rationale: those surfaces change under I-0001; writing them now produces throwaway tests) — they are NOT written against current behavior.
- [ ] If `run_tests.py` is edited, straight-jacket is re-registered; strengthen-only.
- [ ] PR gate green; no unit test asserts behavior RKIT-I-0001 is scheduled to change.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — the task requires judgment about which resume-core surfaces are I-0001-stable versus soon-to-change and enforcing a cross-initiative boundary, which is not mechanical enough for autonomous codex-exec.

### Technical Approach

Populate the empty `tests/unit` (currently `.gitkeep` only) with deterministic resume-core unit cases for behavior that already exists and is stable on current code, and map the PR gate's declared `unit` category to real modules. The `suite_manifest` declares these unit categories: `schema_parsing`, `ats_sanitation`, `date_normalization`, `requirement_normalization`, `scoring_math`, `state_transitions`, `change_validation`, `relationship_matching`, `config_parsing`.

CRITICAL BOUNDARY CONSTRAINT: RKIT-I-0001 is about to RESTORE `VerificationState`/`ResolutionState` members and change `validateResume`/`normalizeResume`/date-strictness/`JobModel` behavior. Unit cases written now against current behavior for those specific surfaces (verification-state acceptance, resolution ladder, date warn-vs-reject, `JobModel` fields) WILL break when I-0001 lands.

APPROVED DECISION (boundary with RKIT-I-0001): write ONLY I-0001-stable unit cases now — specifically `ats_sanitation` (`sanitizeText` determinism, ATS char normalization), `scoring_math` (`scoreMatch` determinism / missing-preferred-distinct math), and `config_parsing` (if stable). EXPLICITLY DEFER `date_normalization`, `requirement_normalization`, `change_validation`, `state_transitions`, and verification-resolution-enum unit cases to RKIT-I-0001 chunk 6 (RKIT-T-0010) — do NOT write them against current soon-to-change behavior. Document the deferral both in the test module(s) and in a note so I-0001 chunk 6 knows to add the excluded categories.

Wire only the covered categories into the gate. Leave the deferred categories declared-but-unmapped with a documented owner, OR (per the approved decision) map them to xfail placeholders that link RKIT-I-0001. Each new unit module must run with no LLM and no network, and produce identical results across two consecutive runs (determinism).

### Files

- `tests/unit/test_resume_core_ats_sanitation_unit.py` (new — `sanitizeText` determinism, ATS char normalization)
- `tests/unit/test_resume_core_scoring_math_unit.py` (new — `scoreMatch` determinism / missing-preferred-distinct math, current behavior)
- `tests/unit/test_resume_core_config_parsing_unit.py` (new — config parsing surface, if stable)
- `tests/suite_manifest.json` (map covered unit categories to modules; NON-protected)
- `tools/run_tests.py` (PROTECTED — add `tests.unit` modules to the executed set if not auto-discovered; re-register straight-jacket if edited)

### Dependencies

- No task dependencies — startable once the initiative is active.
- Cross-initiative semantic link: the deferred unit categories (`date_normalization`, `requirement_normalization`, `change_validation`, `state_transitions`, verification/resolution-enum) are OWNED by RKIT-I-0001 chunk 6 (RKIT-T-0010), which restores the behavior those cases will assert against. The in-file deferral comment and any xfail placeholders must link RKIT-I-0001 so its chunk 6 picks them up.

### Risk Considerations

- Scope-boundary bleed: the primary risk is writing unit cases against surfaces RKIT-I-0001 will change, producing throwaway tests that break when I-0001 lands. Mitigate by strictly limiting coverage to `ats_sanitation`, `scoring_math`, and (if stable) `config_parsing`, and enforcing the explicit deferral.
- Protected-surface constraint: `tools/run_tests.py` is straight-jacket protected. Any edit must be strengthen-only and followed by straight-jacket re-registration; avoid touching it at all if `tests.unit` modules are auto-discovered.
- Determinism: unit cases must be free of LLM/network and stable across repeated runs; any nondeterministic assertion would flake the PR gate.
- Cross-package blast radius: keep assertions confined to the covered resume-core surfaces so the new modules do not couple to volatile validate/normalize/JobModel behavior owned by I-0001.

## Verification Steps

1. `python3 -m unittest discover -s tests/unit` (all pass)
2. `python3 -m unittest discover -s tests/unit` (run twice; identical results — determinism)
3. `python3 tools/run_gate.py --pr --root .` (unit modules executed and green)
4. `grep -n 'RKIT-I-0001' tests/unit/*.py` (deferral note present for excluded categories)

## Status Updates

*To be added during implementation*