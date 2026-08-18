---
id: integration-suite-over-real-cli
level: task
title: "Integration suite over real CLI artifacts, overflow round-trip E2E, audit-evidence manifest assertions"
short_code: "RKIT-T-0119"
created_at: 2026-08-18T22:51:15.359175+00:00
updated_at: 2026-08-18T22:52:30.340212+00:00
parent: render-gate-integration-fixtures
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0034
---

# Integration suite over real CLI artifacts, overflow round-trip E2E, audit-evidence manifest assertions

## Parent Initiative

[[RKIT-I-0034]]

## Objective

Fill the empty `tests/integration` and `tests/e2e` promises (R1/R2/R5): the render boundary exercised with artifacts ACTUALLY produced through resume-cli export (real bytes from output/, not synthetic dicts), the overflow round-trip E2E with render-side assertions active (orchestration side landed with I-0027 — activate it fully), and audit-gate assertions that run manifests carry template_version, artifact fingerprints, layout report, and validation results.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Fixture set per the initiative Detailed Design: (a) fits-one-page resume under the default template; (b) overflow variant with a KNOWN character excess (values from the I-0031 model — compute, don't guess); (c) reuse of T-0118's tamper-fixture construction (deterministic in-test) so the gate proves tamper detection end to end.
- [ ] `tests/integration/` populated (R1): drive resume-cli export on fixture (a) in a temp workspace; capture output/ artifacts; feed the ACTUAL bytes back through validateRenderedOutput — assert pass verdicts, deterministic fingerprints across two runs, provenance absence in artifact bytes, and the tampered variant (c) FAILING through the same path.
- [ ] `tests/e2e/` overflow round-trip (R2): full-pipeline fixture where render overflow occurs; assert overflow constraints surface to orchestration (I-0027's loop-back — landed; drive it for real, e.g. through the workflow checkpoints or the documented `resume run` sequence in the I-0027 initiative doc) and content reduction re-runs with final validation; render-side honesty assertions (constraints produced, content length unchanged by measurement) active regardless. If any orchestration seam is still missing (I-0039/0040 CLI work), assert what IS wired and mark the remainder with an explicit owner comment — honest, not vacuous.
- [ ] Audit-evidence assertions (R5): from a completed run's manifest, assert presence + correctness of template_version, metrics_version, artifact fingerprints (match recomputed sha256 of the actual bytes), and validation result summary — missing fields FAIL. Workflow owns the manifest write; if a render field is not yet embedded, wire it through the existing manifest mechanisms (agent_metadata.py precedent; NO new manifest fields if the workflow guardrail pins the set — check first, reuse existing fields/refs, defer if truly blocked).
- [ ] All new suites bridged into gate-run modules (tests/integration + tests/e2e are NOT in the protected runner's list — bridge like prior E2E work; state where). Strengthen-only (R6).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits in THIS task (T-0120 owns the run_smoke.py edit).

## Implementation Notes

### Technical Approach
Mirror tests/e2e/test_grounded_tailoring_final_validation.py and the career-mcp subprocess harness patterns for temp-workspace CLI driving. Keep runs hermetic and fast; two-run fingerprint determinism needs identical inputs (beware wall-clock leaking into manifests — use the injectable seams where they exist).

### Dependencies
I-0030/0031/0032 substrate (all landed); I-0027 overflow loop-back (landed).

### Risk Considerations
The manifest field set is guardrail-pinned (workflow_guardrails, protected) — reuse existing fields (render evidence may already ride checkpoint refs/artifact refs from I-0023/0027; investigate before adding anything). CLI export path changed in I-0033 (pdf skip-with-notice) — integration suite covers markdown+docx only per the release gate.

Recommended Agent: opus + high

## Status Updates

### 2026-08-18 Implementation session

- Read task acceptance criteria plus RKIT-I-0034 and RKIT-I-0027 initiative docs.
- Ran `straight-jacket list --json` and `straight-jacket verify --json`; verify reports only the expected pre-existing `tools/resume_core_guardrails.py` checksum mismatch.
- Confirmed protected `tools/` runner files cannot be edited for this task. Plan is to add unprotected `tests/integration` and `tests/e2e` modules, then bridge execution through the already-gated `tests.contract.test_tests_contract` module.
- Found current manifest field set is pinned to `renderer_template_version`, `output_artifact_paths`, `render_refs`, `validation_refs`, `checkpoint_result_refs`, `artifact_refs`, and metadata field sources. No new workflow manifest fields will be added.
- Implemented integration and E2E suites over real CLI/output bytes and workflow checkpoint loop-back. Bridge lives in `tests/contract/test_tests_contract.py`, which is already in the protected PR runner module list.
- Verification: direct new modules pass (5 tests); bridge module passes; `python3 tools/tests_guardrails.py --root .` passes; required gates pass: `--pr` (636 tests), `--smoke`, `--future-contract` (643 tests). Final `straight-jacket verify --json` still reports only the expected `tools/resume_core_guardrails.py` mismatch.
