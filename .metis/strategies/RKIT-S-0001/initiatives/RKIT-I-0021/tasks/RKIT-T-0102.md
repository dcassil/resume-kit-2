---
id: agent-metadata-manifest-block
level: task
title: "Agent-metadata manifest block, defined-location contract test, TEST_SPEC :91, reconstruction"
short_code: "RKIT-T-0102"
created_at: 2026-08-17T18:37:55.889471+00:00
updated_at: 2026-08-17T18:37:55.889471+00:00
parent: resume-agent-auditability
blocked_by: ["RKIT-T-0101"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0021
---

# Agent-metadata manifest block, defined-location contract test, TEST_SPEC :91, reconstruction

## Parent Initiative

[[RKIT-I-0021]]

## Objective

Close the resume-agent TEST_SPEC Determinism Strategy (:91) enforceability gap: expose ONE package-owned agent-metadata structure (adapter id/version, model id, config hash, prompt-template versions), define WHERE it lives in the workflow run manifest, assert that location with a contract test, and prove the Audit Gate: from a run manifest plus call-audit records, the exact adapter/model/config/prompt identity and failure history of an agent-involved run are recoverable.

## Acceptance Criteria

- [ ] Public package function (e.g. `resume_agent.agentMetadata(agent_config) -> JsonObject`) returning the single metadata block `{adapter_id, adapter_version, model_id, config_hash, prompt_template_versions}` where `prompt_template_versions` enumerates the packaged versioned prompt assets (`prompts/<id>@vN.txt`) with their sha256 hashes — sourced from the real files, no hardcoded lists that drift. IMPORTANT: check `resume-agent/agent_surface.json` and `tools/resume_agent_guardrails.py` FIRST — if the guardrail pins ALLOWED_SURFACES to exactly the current public functions, DO NOT add a new public surface; instead expose the block through an existing declared channel (the established pattern: workflow already embeds `agent_model_config` from `agent_config.to_dict()` — extend `AgentConfig.to_dict()`/a private helper consumed by workflow, and DEFER any surface-manifest advertisement to Daniel's approval batch, per the standing deferral discipline). State in the task report which route was taken and why.
- [ ] Defined manifest location: run manifests already carry `agent_model_config` and `audit_refs` (workflow/schemas.py:59,73). This task DEFINES (in resume-agent/TEST_SPEC.md) that `agent_model_config` is the agent-metadata location and `audit_refs` reference the call-audit records from T-0101, and enriches what workflow embeds so `agent_model_config` contains the full block above (adapter id/version + model id + config hash + prompt template versions), not just the raw config dict. `workflow/__init__.py` is at 1499/1500 guardrail lines — any new logic goes in a workflow private module (e.g. `workflow/agent_metadata.py`) with only a minimal call wired in, or entirely on the resume-agent side if the existing embed call can consume the enriched dict without new workflow lines.
- [ ] Contract test (`tests/contract/test_workflow_contract.py` extension or new non-protected contract module wired via an EXISTING gate-run module import — remember tools/run_tests.py is protected; use the direct-wiring only if it is already listed, otherwise bridge from an already-wired contract module as done for prior initiatives) asserting: an agent-involved run's manifest contains the metadata block at `agent_model_config` with all five sub-fields present and correctly shaped, and `audit_refs` is non-empty when adapter calls occurred.
- [ ] Audit Gate reconstruction test: given a completed run's manifest + the persisted audit records it references, a reconstruction assertion recovers adapter_id, adapter_version, model_id, config_hash, every prompt template version used, and the full per-call failure history (outcome taxonomy + retry counts) — matching what the run actually did. Force at least one failed+retried call in the scenario so failure history is non-trivial.
- [ ] Determinism preserved: the enriched `agent_model_config` block is byte-stable across identical-config runs (hashes only from stable content); existing manifest/config-hash tests stay green unmodified (or strengthened only).
- [ ] resume-agent/TEST_SPEC.md Determinism Strategy section (:91 area) rewritten from the unenforceable sentence into the defined location + named covering tests. tools/TEST_SPEC.md is PROTECTED — do not touch it.
- [ ] Gates green: `--pr`, `--smoke`, and `--future-contract`; snapshot regenerate ×2 no-drift if fixtures move.

## Implementation Notes

### Technical Approach
The manifest fields already exist (RKIT-I-0016 landed `agent_model_config`/`agent_config_hash`; `audit_refs` exists from I-0024) — this task upgrades their CONTENT and pins them with tests. Wire the T-0101 sink into the workflow adapter call path so records persist beside the run's other JSONL logs (append-only, same style as operations.jsonl) and `audit_refs` carries their ids/paths.

### Dependencies
RKIT-T-0101 (call-audit records must exist to reference).

### Risk Considerations
Protected-file traps: tools/run_tests.py, tools/TEST_SPEC.md, tools/workflow_guardrails.py, tools/resume_agent_guardrails.py. The workflow guardrail pins the manifest field SET — both fields being reused (not added) is what keeps this task implementable without protected edits; if a new manifest field turns out to be needed, STOP and defer it to the approval batch instead of ending red.

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*
