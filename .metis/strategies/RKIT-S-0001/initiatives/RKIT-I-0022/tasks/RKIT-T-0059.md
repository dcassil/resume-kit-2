---
id: manifest-schema-validation-in
level: task
title: "Manifest schema validation in buildRunManifest with minLength identity constraints"
short_code: "RKIT-T-0059"
created_at: 2026-08-15T02:48:33.781066+00:00
updated_at: 2026-08-15T03:03:19.788285+00:00
parent: workflow-artifact-schemas-and-run
blocked_by: [RKIT-T-0058]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0022
---

# Manifest schema validation in buildRunManifest with minLength identity constraints

## Parent Initiative

[[RKIT-I-0022]]

## Objective

Make buildRunManifest self-gating (RKIT-I-0022 Requirement 5, Detailed Design "Manifest validation"): validate the assembled manifest against RUN_MANIFEST_SCHEMA before returning; identity fields (base_resume_id, base_resume_hash, job_id, renderer_template_version) gain minLength constraints so today's silent empty-string defaults become typed validation failures.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] buildRunManifest validates its output against RUN_MANIFEST_SCHEMA at the build site (stdlib walker per repo convention — no jsonschema dependency) and raises a typed error on violation; every caller is gated, not just tests.
- [ ] RUN_MANIFEST_SCHEMA gains minLength(1) constraints on base_resume_id, base_resume_hash, job_id, renderer_template_version; the old empty-string defaults now fail with typed errors naming the field.
- [ ] Contract test: buildRunManifest raises typed validation errors on each empty identity field and on any placeholder version value (extends T-0058's assertion into the validation layer).
- [ ] Legitimate producers (CLI/workflow smoke paths) supply real identity values — fix producers minimally where they relied on empty defaults; never loosen the schema.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Reuse the stdlib schema-walking validation pattern resume-core's validateResume established. Validation lives inside buildRunManifest so production paths are gated (the initiative's decided alternative rejection: no test-only validation).

### Dependencies

RKIT-T-0058 (real versions land first so validation doesn't trip on placeholders).

### Risk Considerations

Smoke's manifest-building path must supply real identity fields — check what the CLI currently passes and fix honestly (the chunk-1 residual noted resume-cli calls createRun promiscuously; do NOT fix that misuse here — only the manifest inputs, the rest is RKIT-I-0040/0024 scope).

### Execution profile

Recommended Agent: opus + medium

Rationale: focused validation work on an established pattern; judgment is in producer fixes.

## Status Updates

- 2026-08-15: Implemented builder-side manifest validation in `workflow.buildRunManifest` with a local stdlib schema walker and typed `RunManifestValidationError`; added `minLength: 1` identity constraints plus `0.0.0` placeholder rejection for version fields in `RUN_MANIFEST_SCHEMA`. Fixed `resume-cli audit` manifest inputs to pass persisted resume id/hash, job id, and configured renderer template version. Added contract tests for empty identity fields, placeholder versions, and schema minLength assertions. Required gates passed: PR gate, smoke gate, and `python3 -m unittest discover -s tests/unit -v`. Straight Jacket verify remains blocked by pre-existing protected checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`.