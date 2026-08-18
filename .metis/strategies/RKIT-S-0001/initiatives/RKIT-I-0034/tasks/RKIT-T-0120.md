---
id: smoke-overflow-step-real-docx
level: task
title: "Smoke overflow step + real-DOCX-bytes assertion (protected run_smoke edit), TEST_SPEC strengthening set"
short_code: "RKIT-T-0120"
created_at: 2026-08-18T22:51:15.430527+00:00
updated_at: 2026-08-18T23:01:37.545081+00:00
parent: render-gate-integration-fixtures
blocked_by: [RKIT-T-0119]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0034
---

# Smoke overflow step + real-DOCX-bytes assertion (protected run_smoke edit), TEST_SPEC strengthening set

## Parent Initiative

[[RKIT-I-0034]]

## Objective

Close R3/R4/R6: the smoke gate exercises `measureLayout` with an overflow fixture (asserting overflow is REPORTED, never silently deleted) and accepts only a REAL `.docx` zip validated from its bytes (the `.docx.json` wrapper shortcut is retired) — via an authorized protected edit to `tools/run_smoke.py` under the no-verify workflow — plus the TEST_SPEC strengthening set the initiative owns.

## Acceptance Criteria

## Acceptance Criteria

- [ ] PROTECTED EDIT (authorized, no-verify workflow — joins Daniel's single re-registration pass alongside tools/resume_core_guardrails.py): `tools/run_smoke.py` gains (1) an overflow smoke step — run measureLayout on the overflow fixture (T-0119's fixture (b)); assert the report exists, status/fits indicates overflow, required_reduction > 0, constraints present, and the CONTENT LENGTH of the input is unchanged after measurement (overflow reported, not silently deleted); (2) the DOCX target assertion — the smoke artifact must start with zip magic `PK`, unzip, contain word/document.xml, and pass the I-0032 bytes-derived validateRenderedOutput; a `.docx.json` wrapper can no longer satisfy the target. Minimal, surgical edits; no other smoke behavior changes.
- [ ] If the current smoke flow produces the `.docx.json` wrapper, fix the PRODUCING code (resume-cli export path — not protected) to emit the real .docx file smoke now requires; never weaken the new assertion.
- [ ] TEST_SPEC strengthening set (R6, strengthen-only, resume-render/TEST_SPEC.md + career-level TEST_SPECs as applicable — NOT tools/TEST_SPEC.md which is protected): (a) smoke-coverage claim "overflow reported rather than silently deleted" now names the executing smoke step; (b) smoke DOCX target redefined as real artifact bytes; (c) confirm the cross-package overflow-routing case is already relocated to E2E (T-0117 did the renderer side; T-0119 landed the E2E — cite both).
- [ ] Verify smoke green END TO END in the installed-venv harness (the smoke gate installs the package fresh — the overflow fixture must be reachable from the installed layout; follow how existing smoke fixtures ship).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. `straight-jacket verify` will now report TWO expected mismatches (resume_core_guardrails.py from T-0113 + run_smoke.py from this task) — report them for Daniel's single pass: `straight-jacket update tools/resume_core_guardrails.py tools/run_smoke.py`.

## Implementation Notes

### Technical Approach
Read run_smoke.py fully first — mirror its existing step/assert style (it already checks rendering + audit). The overflow fixture should ride the same fixture-shipping mechanism smoke already uses. Keep the protected diff minimal and verbatim-reportable.

### Dependencies
RKIT-T-0119 (fixtures + integration/E2E), I-0031/0032 (model + validator).

### Risk Considerations
Smoke runs from an installed venv against a temp workspace — path assumptions differ from repo-relative tests. The protected edit must not break the run_gate.py orchestration contract (run_smoke.py is invoked by it — check the calling convention).

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*