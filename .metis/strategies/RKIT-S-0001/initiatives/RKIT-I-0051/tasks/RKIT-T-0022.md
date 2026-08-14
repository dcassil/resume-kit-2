---
id: req-011-reconcile-smoke-test-md
level: task
title: "REQ-011: Reconcile SMOKE_TEST.md fixtures, SaaS truth case, and canonical command"
short_code: "RKIT-T-0022"
created_at: 2026-08-14T03:14:05.882837+00:00
updated_at: 2026-08-14T17:34:15.788616+00:00
parent: executable-release-gate-e2e
blocked_by: []
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-011: Reconcile SMOKE_TEST.md fixtures, SaaS truth case, and canonical command

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Reconcile `SMOKE_TEST.md` with what `tools/run_smoke.py` actually exercises: the doc names non-existent fixtures (`resume-smoke.*`, `job-smoke.txt`) and misclassifies SaaS as "Preferred", while the real smoke run uses `fixtures/resumes/resume-main.txt`, `fixtures/jobs/job-a-staff-software-engineer.txt` (where SaaS is a **required** qualification), and `fixtures/answers/aws.txt`. This task fixes the documentation to reference real fixtures and the correct SaaS classification, and strengthens `run_smoke.py` so the SaaS required-vs-preferred truth case (REQ-011) is actually *exercised* rather than merely ingested — closing a documentation/behavior drift that otherwise silently invalidates the smoke gate's REQ-011 coverage.

## Acceptance Criteria

## Acceptance Criteria

- [ ] `SMOKE_TEST.md` references the fixtures `run_smoke.py` actually uses (`resume-main.txt`, `job-a-staff-software-engineer.txt`, `answers/aws.txt`); no reference to non-existent `resume-smoke.*` / `job-smoke.txt` remains.
- [ ] `SMOKE_TEST.md` classifies SaaS as Required, matching `fixtures/jobs/job-a-staff-software-engineer.txt`.
- [ ] `tools/run_smoke.py` asserts `req_saas` is classified required (the SaaS required-vs-preferred truth case is exercised, not just ingested); the smoke gate fails if SaaS is misclassified as preferred.
- [ ] All three docs (SMOKE_TEST.md context aside) plus `suite_manifest.runner_commands.canonical` name exactly one canonical command (`--pr`); any stale alternate wording removed.
- [ ] `run_smoke.py` re-registered in straight-jacket if edited; smoke gate green against current fixtures.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — the task touches a PROTECTED runner (`run_smoke.py`) with a strengthen-only constraint plus straight-jacket re-registration, and requires judgment on classification correctness against fixture truth; `codexSuitable` is false.

### Technical Approach

- **SMOKE_TEST.md (NON-protected):** Edit to reference the real fixtures used by `run_smoke.py` — `fixtures/resumes/resume-main.txt`, `fixtures/jobs/job-a-staff-software-engineer.txt`, and `fixtures/answers/aws.txt` — removing every mention of the non-existent `resume-smoke.*` and `job-smoke.txt`. Correct the SaaS classification from "Preferred" to **Required**, matching the Job A fixture (line 4/9 of `fixtures/jobs/job-a-staff-software-engineer.txt`).
- **tools/run_smoke.py (PROTECTED):** Add an assertion that `req_saas` is classified as **required** (not merely ingested), so the SaaS required-vs-preferred truth case that REQ-011 demands is actually exercised. The smoke gate must fail if SaaS is ever misclassified as preferred. Per the APPROVED-DECISION NOTE, this assertion is **strengthen-only** under RKIT-A-0006 — it adds a stricter check without loosening any existing behavior — and `run_smoke.py` must be **re-registered** in straight-jacket after the edit.
- **Canonical command (light confirmation pass only):** Per the APPROVED-DECISION NOTE, the canonical-command sub-item is essentially already satisfied — `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md` (lines 50–56) and `tests/TEST_SPEC.md` (line 41) both already name `python3 tools/run_gate.py --pr --root .` as canonical, and there is no live conflict. Limit this work to confirming both docs plus `suite_manifest.runner_commands.canonical` agree, and removing any stale alternate-command wording only if a spot-check during execution finds one. Do not manufacture changes here.

### Files

- `SMOKE_TEST.md` — fix fixture names `resume-smoke.*` / `job-smoke.txt` → real fixtures; correct SaaS Preferred → Required. (NON-protected)
- `tools/run_smoke.py` **(PROTECTED)** — add `req_saas` required-classification assertion; strengthen-only; re-register.
- `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md` and `tests/TEST_SPEC.md` — confirm single canonical command; edit only if a stale alternate is found.
- `.straight-jacket/manifest.json` — re-register `run_smoke.py` if edited.

### Dependencies

No task dependencies — startable once the initiative is active. Note: the SaaS required-classification behavior this task exercises depends on the required-vs-preferred classification owned by its package initiative (any related xfail must be resolved in that owning initiative, not here); and downstream REQ work under RKIT-I-0004 relies on the smoke gate accurately exercising the required truth case, so keep this task's scope confined to reconciliation and the strengthen-only assertion.

### Risk Considerations

- **Protected-surface constraint:** `run_smoke.py` is PROTECTED; the assertion must be strictly strengthen-only per RKIT-A-0006 (no loosening, no behavioral removal) and requires straight-jacket re-registration. A non-strengthen-only edit will be rejected.
- **Scope-boundary bleed:** Do not "fix" the SaaS classification logic itself here — that lives in the owning package initiative. This task only documents truth and asserts it.
- **Canonical-command over-reach:** The docs already agree; resist manufacturing edits. Only remove genuinely stale alternate wording found during spot-check.
- **Determinism:** The smoke gate must remain deterministic and green against the current fixtures; the new assertion must key off the real fixture truth (Job A, SaaS required), not a hardcoded expectation that could drift.

## Verification Steps

1. `grep -n 'resume-smoke\|job-smoke' SMOKE_TEST.md` (no matches after fix)
2. `grep -n -i 'saas' SMOKE_TEST.md` (appears under Required)
3. `python3 tools/run_gate.py --smoke --root .` (green; SaaS required assertion exercised)
4. `grep -rn 'run_gate.py --pr\|run_tests.py' PROJECT_STRUCTURE_AND_TEST_STRATEGY.md tests/TEST_SPEC.md tests/suite_manifest.json` (single canonical `--pr` command)
5. `straight-jacket verify` (if `run_smoke.py` edited)

## Status Updates

*To be added during implementation*