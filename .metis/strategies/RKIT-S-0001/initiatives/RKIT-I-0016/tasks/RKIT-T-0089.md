---
id: agent-config-block-schema
level: task
title: "agent config block: schema validation, defaults, run-manifest config hash"
short_code: "RKIT-T-0089"
created_at: 2026-08-16T19:46:40.588276+00:00
updated_at: 2026-08-16T19:46:40.588276+00:00
parent: resume-agent-proposal-model
blocked_by: ["RKIT-T-0087", "RKIT-T-0088"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0016
---

# agent config block: schema validation, defaults, run-manifest config hash

## Parent Initiative

[[RKIT-I-0016]]

## Objective **[REQUIRED]**

Add the schema-validated `agent` block to workspace `config.json` per RKIT-A-0003 item 3: `{model, schema_mode, timeout_ms, max_retries, cost_ceiling}` validated at load by a schema shipped in resume-agent; unknown keys FAIL validation (config strictness per RKIT-A-0006 decision 6 — consistent with the guardrails.*/matching.*/resume.*/workflow.* namespace discipline); documented defaults apply when the block is absent; the validated block's stable hash is exposed for the workflow run manifest and participates in the run-manifest config hash.

## Acceptance Criteria **[REQUIRED]**

- [ ] `agent` config schema shipped in resume-agent (stdlib validator, same idiom as T-0087); typed errors on violations; unknown keys rejected (test: `agent.bogus_key` fails load).
- [ ] Defaults documented in the schema/module and applied when the block is absent (Sonnet-class default model name; explicit values for schema_mode/timeout_ms/max_retries/cost_ceiling); a test asserts the applied default set.
- [ ] Stable config hash exposed via a public-enough seam for workflow (follow how workflow/config.py + createRun compute config_hash today — the agent block must CHANGE the run-manifest config hash when it changes; add the wiring in workflow config consumption if that is where config hashing lives, keeping workflow guardrail constraints in mind).
- [ ] Hash stability test: identical configs → identical hash; changed model name → different hash; run-manifest config_hash reflects it (workflow-level test).
- [ ] Adapters consume the validated block for runtime_config metadata (T-0087 result field) — construction from raw unvalidated dicts is not possible through the public path.
- [ ] `--pr` and `--smoke` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Read workflow/config.py (unprotected) and how createRun hashes config before wiring; workflow_guardrails pins surface names — no new workflow public functions.
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0087/0088. Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. workflow/__init__.py at 1499/1500 line cap — any workflow-side wiring goes in workflow/config.py or private modules.

## Status Updates **[REQUIRED]**

*To be added during implementation*
