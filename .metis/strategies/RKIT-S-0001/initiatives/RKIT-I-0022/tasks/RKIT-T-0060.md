---
id: manifest-audit-field-additions-and
level: task
title: "Manifest audit-field additions and TEST_SPEC field-list strengthening; I-0022 close-out"
short_code: "RKIT-T-0060"
created_at: 2026-08-15T02:48:33.833144+00:00
updated_at: 2026-08-15T03:10:15.041595+00:00
parent: workflow-artifact-schemas-and-run
blocked_by: [RKIT-T-0059]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0022
---

# Manifest audit-field additions and TEST_SPEC field-list strengthening; I-0022 close-out

## Parent Initiative

[[RKIT-I-0022]]

## Objective

Close out RKIT-I-0022 (Requirement 6 + Testing Strategy): RunManifest and RUN_MANIFEST_SCHEMA gain `question_answer_log_refs` and `unresolved_requirements` so the full Audit Gate reconstruction list (CONTRACT_SURFACE_ALIGNMENT.md:353-366) is representable; workflow/TEST_SPEC.md's manifest field list (:83-101) is strengthened to that set; three-gate close-out with mutation probe.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] RunManifest dataclass + RUN_MANIFEST_SCHEMA gain `question_answer_log_refs` (refs into the run's question/answer log) and `unresolved_requirements` (requirement id, resolution state, reason) with matching schema entries; buildRunManifest carries them (honest empty defaults are acceptable here — the PRODUCERS land in RKIT-I-0024; the validated shape and schema obligation land now).
- [ ] workflow/TEST_SPEC.md's run-manifest field list (~:83-101) extended to the CONTRACT_SURFACE_ALIGNMENT.md:353-366 set — CHECK the straight-jacket protected list first: if workflow/TEST_SPEC.md is protected (only tools/TEST_SPEC.md is known-protected), defer with line refs; package specs have been editable so far.
- [ ] Contract tests assert the new fields exist in schema + manifest output and that RUN_MANIFEST_SCHEMA rejects a manifest missing them.
- [ ] Gap check against the initiative's Testing Strategy: distinct-run-id collision regression (landed 08-13), typed-empty-identity and no-placeholder tests (T-0059/T-0058), careerDbVersion equality (T-0058) — all present and named; add anything missing.
- [ ] Mutation probe documented: reverting careerDbVersion to a literal (or dropping manifest validation) fails the suite; restored green.
- [ ] Any new workflow unit modules listed for the protected run_tests.py batch (joining the eleven queued career-store modules).
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Established close-out pattern. Schema additions are additive; TEST_SPEC edit follows the guardrail-compatibility check discipline (tools/workflow_guardrails.py may parse the spec — read it first).

### Dependencies

RKIT-T-0059 (validation layer final before schema additions freeze).

### Risk Considerations

workflow_guardrails.py (protected) may pin the manifest field list or spec framing — deferral discipline applies. Honest empty defaults for the new fields must be explicit (empty list) not missing.

### Execution profile

Recommended Agent: opus + medium

Rationale: additive schema/spec consolidation on decided shapes.

## Status Updates

- 2026-08-15: Started implementation after reading the task doc first. Straight Jacket list/verify was run before edits. `workflow/TEST_SPEC.md` is not protected, but `tools/workflow_guardrails.py` is protected and pins the old manifest field set at lines 49-70 and 174-181; protected verify also had pre-existing checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`.
- 2026-08-15: Added `question_answer_log_refs` and `unresolved_requirements` to `RunManifest`, `RUN_MANIFEST_SCHEMA`, `createRun`, and `buildRunManifest`. `buildRunManifest` emits explicit empty-list defaults when producers have not populated the fields yet. `unresolved_requirements` items require `requirement_id`, `resolution_state`, and `reason`.
- 2026-08-15: Strengthened `workflow/TEST_SPEC.md` run-manifest list to the Audit Gate reconstruction categories from `CONTRACT_SURFACE_ALIGNMENT.md:353-366`: source/base/job/config identity, versions, scores, unresolved requirements, Q/A refs, facts, proposed/rejected/applied operations, validation outcomes, and outputs. No protected package-spec deferral was needed; `tools/workflow_guardrails.py` remains read-only and still pins the old machine-readable surface list.
- 2026-08-15: Contract coverage added in existing modules only: `tests.contract.test_workflow_contract` now asserts populated audit fields, explicit empty defaults, and missing-field schema rejection; `tests.contract.test_shared_dto_schemas_contract` locks the required schema field set to the dataclass. No new workflow unit modules were added for the protected `tools/run_tests.py` batch.
- 2026-08-15: Testing Strategy gap check:
  - distinct-run-id collision regression: present as `test_same_config_runs_get_distinct_ids_and_coexisting_persisted_state` and `test_workspace_run_index_maps_config_hash_to_all_run_ids`.
  - typed-empty-identity rejection: present as `test_run_manifest_validation_rejects_each_empty_identity_field`.
  - no-placeholder version rejection: present as `test_run_manifest_versions_have_no_placeholders_and_match_real_sources` and `test_run_manifest_validation_rejects_placeholder_version_values`.
  - careerDbVersion equality: present as `test_run_manifest_career_db_version_equals_store_state`.
  - audit-field schema/output obligations: added as `test_run_manifest_records_traceability_fields`, `test_run_manifest_emits_explicit_empty_audit_field_defaults`, `test_run_manifest_schema_rejects_missing_audit_fields`, and shared DTO schema required-field coverage.
- 2026-08-15: Mutation probe completed by temporarily removing `_validate_run_manifest(manifest)` from `buildRunManifest`. PR gate failed as expected with 5 failures: empty `base_resume_id`, `base_resume_hash`, `job_id`, `renderer_template_version`, and placeholder `renderer_template_version` no longer raised `RunManifestValidationError`. Restored the validation call.
- 2026-08-15: Final validation after restore: PR gate green (`Ran 361 tests ... OK`), smoke gate green (`smoke passed`; single installed smoke flow), future-contract gate green (`Ran 368 tests ... OK`), unit discovery green (`Ran 189 tests ... OK`, run through a temporary venv so the requested `python3 -m unittest discover -s tests/unit -v` command saw the editable install). Straight Jacket verify remains blocked only by pre-existing protected checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`.