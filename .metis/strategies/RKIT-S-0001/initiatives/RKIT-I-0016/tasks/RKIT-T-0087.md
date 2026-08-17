---
id: modeladapter-protocol-request
level: task
title: "ModelAdapter protocol, request/result DTOs, failure taxonomy, shared schema validators"
short_code: "RKIT-T-0087"
created_at: 2026-08-16T19:46:40.467010+00:00
updated_at: 2026-08-16T19:54:40.129497+00:00
parent: resume-agent-proposal-model
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0016
---

# ModelAdapter protocol, request/result DTOs, failure taxonomy, shared schema validators

## Parent Initiative

[[RKIT-I-0016]]

## Objective **[REQUIRED]**

Build the provider-neutral seam RKIT-A-0003 decided: a `ModelAdapter` protocol (`complete(request) -> AdapterResult`) in the resume-agent package, with request DTOs carrying prompt/input payload + output JSON-schema id, result DTOs carrying the parsed SCHEMA-VALIDATED proposal payload + `adapter_id`, `adapter_version`, `model_id`, `runtime_config`, retry count, usage counters — validation INSIDE the adapter boundary so no caller ever sees unvalidated model output. Typed failure taxonomy `timeout | schema_invalid | refused | provider_error` extends the existing package error envelope; adapters may fail only through it.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `ModelAdapter` protocol + `AdapterRequest`/`AdapterResult` DTOs in a new private module (resume_agent package; do not grow the monolithic `__init__.py` — it is ~7,500 lines; new code in submodules with narrow public exports consistent with the guardrail's allowed surface).
- [ ] Stdlib-only structured-output schema validator shared by all adapters (reuse the repo's existing stdlib schema-walker idiom from resume-core validateResume rather than adding a jsonschema dependency); out-of-schema payload → typed `schema_invalid` error carrying the violation list; never silent fallback output.
- [ ] Four-value failure taxonomy as typed errors/results; provider failures map onto it; unknown failure shapes map to `provider_error` — nothing raises through the seam untyped.
- [ ] Every `AdapterResult` carries adapter_id, adapter_version, model_id, runtime_config, retries, usage — a contract test asserts presence on every result path (success AND failure results carry adapter/model metadata).
- [ ] No mutation/persistence/scoring/forbidden imports (resume_agent_guardrails must pass); proposals remain `requires_validation`.
- [ ] `--pr` and `--smoke` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Check `tools/resume_agent_guardrails.py` (READ-ONLY) for module/surface constraints before choosing module names; check `resume-agent/agent_surface.json` for declared structure.
- No Anthropic SDK in this task (T-0090); no fake fixtures yet (T-0088) — one trivial in-test adapter double may drive the protocol tests.
- Recommended Agent: opus + high

### Dependencies
None (first task). T-0088/0089/0090 build on the seam. Serial chain.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

- 2026-08-16: I-0011 complete (v0.17.0 pushed dab725b — career-mcp tier DONE, 19 initiatives). I-0016 decomposed T-0087..0090; T-0090 grounded against current Anthropic SDK docs via the claude-api skill (claude-sonnet-4-6 default, output_config.format structured outputs, typed SDK exceptions). Codex launched on the protocol/DTO/taxonomy/validator substrate.