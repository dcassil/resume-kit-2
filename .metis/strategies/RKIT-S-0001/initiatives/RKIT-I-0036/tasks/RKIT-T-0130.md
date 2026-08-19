---
id: off-fixture-ingest-fixture
level: task
title: "Off-fixture ingest fixture, fabrication guards, DTO conformance, boundary guardrail, TEST_SPEC strengthening; close-out"
short_code: "RKIT-T-0130"
created_at: 2026-08-19T17:52:19.077872+00:00
updated_at: 2026-08-19T18:59:30.571235+00:00
parent: resume-and-job-ingest-orchestration
blocked_by: [RKIT-T-0127, RKIT-T-0128, RKIT-T-0129]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: true
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0036
---

# Off-fixture ingest fixture, fabrication guards, DTO conformance, boundary guardrail, TEST_SPEC strengthening; close-out

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0036]]

## Objective **[REQUIRED]**

Prove the fixture-independence, no-fabrication, and DTO-conformance claims of I-0036 with a full second-vocabulary ingest fixture set, permanent boundary guardrails against CLI domain-logic regrowth, and TEST_SPEC strengthening covering the previously unspecified URL/pasted-text and fabrication cases. Close out the initiative.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [x] A complete off-fixture ingest fixture set exists (second vocabulary: e.g. Python/Spark/Kafka data-engineer resume + matching JD): source documents under `fixtures/`, pinned fake-adapter extraction fixtures under `fixtures/resume-agent/fake-adapter/`, and expected artifacts. End-to-end test: `resume ingest` + `resume job ingest` over these produce faithful base.json/job.json and persist the fixture-defined facts — asserting zero dependence on the original smoke vocabulary (no React/TypeScript/Azure keyword required for any behavior).
- [x] Fabrication guard tests: a resume with no stated title and no experience section ingests to a typed outcome or an honest artifact — base.json contains no "Software Engineer", "Source Resume", "Software Developer", or any string absent from the source document + extraction fixture.
- [x] DTO conformance tests: persisted base.json validates against `CANONICAL_RESUME_SCHEMA` (per-field ResumeField provenance present for extraction-derived claims); persisted job.json requirements validate against the JobRequirement schema (type/years/importance/weight fields, no renames).
- [x] Boundary guardrail (AST-level, in `tools/resume_cli_guardrails.py` — protected, lockstep edit, commit `--no-verify`): resume-cli defines no date-parsing (month-name/regex date tables), no requirement-keyword vocabulary, and no canonical-schema-construction literals (`"schema_version": "canonical-resume.v1"` / `"job-model.v1"` construction) — verified by attempting-regrowth negative tests in the guardrail's own test coverage if present, else by guardrail failure messages exercised in a boundary test.
- [x] TEST_SPEC strengthening (`resume-cli/TEST_SPEC.md` ingest sections): URL input case, pasted-text input case, fabrication guard ("Does not allow agent-generated unsupported content into base" now cites the observable test), off-fixture independence sentence. `cli_surface.json` must_not entries updated if the surface wording changed.
- [x] All gates green at close-out: `--pr`, `--future-contract`, `--smoke`. Snapshot regeneration ×2 no-drift verified.
- [x] Initiative close-out: version bump in root `pyproject.toml` (minor), CHANGELOG entry, I-0036 exit criteria checked.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Fake-adapter fixture keys are sha256(prompt_template_id, output_schema_id, canonical_input_json) — the off-fixture resume text must be byte-stable; generate the key with the existing helper (`deterministic_fake_key`) in a small fixture-authoring step, envelope schema `resume-agent.fake-adapter-fixture.v1` with `reviewed: true` + `expected_observations`.
- Follow `fixtures/TEST_SPEC.md` conventions for new fixture documentation; add entries to `fixtures/fixture_manifest.json`.
- The boundary guardrail extends the existing FORBIDDEN_TERMS/AST scan machinery in `resume_cli_guardrails.py` — reuse its Failure/scan patterns; keep messages actionable ("owned by resume-core dates.py", etc.).
- Bridge every new test module into gates via the `test_tests_contract` subprocess pattern — codex historically forgets this; verify each new module actually runs under `--pr` by breaking it once locally.

### Dependencies
RKIT-T-0127, RKIT-T-0128, RKIT-T-0129 all landed.

### Risk Considerations
Guardrail regexes that are too broad will false-positive on legitimate orchestration strings (e.g. reading `schema_version` from artifacts is fine; constructing it is not) — scope patterns to construction sites. Protected-file edits (`resume_cli_guardrails.py`, possibly `run_smoke.py`) ride the no-verify workflow and must be listed for Daniel's approval pass.

### Execution profile
Recommended Agent: opus + medium

## Status Updates **[REQUIRED]**

### 2026-08-19 Implementation Checkpoint

- Added fixture-backed off-fixture data-engineer resume/JD source files, deterministic fake-adapter extraction fixtures, manifest metadata, and expected ingest artifact subsets.
- Strengthened `tests/integration/test_resume_ingest_fact_proposals_integration.py` for end-to-end resume/job ingest, career fact persistence, DTO conformance, and no-fabrication behavior.
- Added `tests/boundary/test_resume_cli_domain_regrowth.py` for non-protected guardrail failure-path coverage and bridged it through `tests/contract/test_tests_contract.py`.
- Extended the authorized protected `tools/resume_cli_guardrails.py` AST scan for CLI-owned date parsing, requirement vocabulary lists, and canonical resume/job schema-version construction.
- Removed remaining CLI requirement-topic vocabulary prioritization and the CLI job-model schema literal; bumped root version to `0.35.0` and added the I-0036 changelog entry.
- Focused validation passed: ingest integration, domain-regrowth boundary test, tests contract, shared DTO contract, job ingest modes, resume-agent adapter contract, resume-cli contract, fixtures guardrail, and resume-cli guardrail.

### 2026-08-19 Verification Close-Out

- Full gates passed: `python3 tools/run_gate.py --pr --root .` (659 tests), `python3 tools/run_gate.py --future-contract --root .` (666 tests), and `python3 tools/run_gate.py --smoke --root .`.
- Snapshot regeneration ran twice with identical `fixtures/expected` checksums and no `git diff -- fixtures/expected`.
- Bridge proof completed: temporarily broke `tests/boundary/test_resume_cli_domain_regrowth.py`; `python3 tools/run_gate.py --pr --root .` failed through `tests.contract.test_tests_contract`; restored and reran PR green.
- Guardrail negative probe completed: temporary `resume-cli/resume_cli/_guardrail_probe_tmp.py` month-name table failed with the actionable `Date parsing belongs to resume-core dates.py` message; scratch file removed.
- Straight Jacket final verify reports expected pending protected approval for `tools/resume_cli_guardrails.py`; `tools/resume_core_guardrails.py` remains the known pre-existing mismatch.