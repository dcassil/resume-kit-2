---
id: migrate-resume-audit-onto
level: task
title: "Migrate resume audit onto reconstruction; no-createRun boundary; I-0024 close-out"
short_code: "RKIT-T-0067"
created_at: 2026-08-15T03:39:09.940741+00:00
updated_at: 2026-08-15T04:03:26.554525+00:00
parent: workflow-checkpoint-result
blocked_by: [RKIT-T-0066]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0024
---

# Migrate resume audit onto reconstruction; no-createRun boundary; I-0024 close-out

## Parent Initiative

[[RKIT-I-0024]]

## Objective

Close out RKIT-I-0024 (Requirement 6's CLI half + Testing Strategy): resume-cli `resume audit` consumes `reconstructRunManifest` from workflow-owned persisted run state instead of fabricating a fresh run via createRun at audit time (old resume_cli/__init__.py:347-360 defect); an unprotected boundary test proves audit performs no createRun; three-gate close-out with mutation probe.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] resume-cli `resume audit` calls reconstructRunManifest over the workspace's persisted run(s); the audit-time createRun fabrication is REMOVED — this also resolves the chunk-1 residual (audit minting fresh runs so run_identity drifted).
- [ ] The audit report presents reconstructed manifest content honestly, including "not recorded" markers for pre-migration runs; no value invented CLI-side.
- [ ] Unprotected boundary/contract test: the audit path performs NO createRun (e.g. count run files before/after audit; assert unchanged; or instrument via run index).
- [ ] Audit with no persisted runs is a typed/honest error or empty report — never a fabricated run.
- [ ] Gap check the initiative's Testing Strategy: durable-blocked-event restart test (T-0065), ref-resolution/hash test (T-0065), adversarial substring regression (T-0065), reconstruction equality + unknown-id (T-0066), on-disk log assertions (T-0066), this task's no-createRun boundary — all named; add anything missing.
- [ ] Mutation probe documented: re-fabricating refs via substring scan (or reintroducing audit-time createRun) fails the suite; restored green.
- [ ] New unit modules listed for the protected run_tests.py batch; close-out gates ALL green: --pr, --smoke, --future-contract; counts reported.

## Implementation Notes

### Technical Approach

CLI reads the run index (config_hash → run_ids from I-0022 chunk 1) to locate the workspace's runs; picks the latest for the report (document the selection rule). Established close-out pattern for the rest.

### Dependencies

RKIT-T-0066 (reconstruction surface).

### Risk Considerations

The chunk-1 residual noted resume-cli `_init` calls createRun from every command — do NOT fix that broader misuse here (RKIT-I-0040 scope); only the audit path.

### Execution profile

Recommended Agent: opus + medium

Rationale: consumer migration onto a decided surface plus standard close-out.

## Status Updates

*To be added during implementation*