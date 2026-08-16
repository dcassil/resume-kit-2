---
id: anthropic-claude-adapter-opt-in
level: task
title: "Anthropic Claude adapter (opt-in live), agent_surface drift fixes (reason, verification_state) — close-out"
short_code: "RKIT-T-0090"
created_at: 2026-08-16T19:46:40.646046+00:00
updated_at: 2026-08-16T19:46:40.646046+00:00
parent: resume-agent-proposal-model
blocked_by: ["RKIT-T-0087", "RKIT-T-0088", "RKIT-T-0089"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0016
---

# Anthropic Claude adapter + agent_surface drift fixes — I-0016 close-out

## Parent Initiative

[[RKIT-I-0016]]

## Objective **[REQUIRED]**

Ship the live path and close the manifest drift: (1) the Anthropic Claude `ModelAdapter` via the official `anthropic` Python SDK — configurable model with Sonnet-class default, structured output via the configured schema mode, timeout/retry from config, retries surfaced in result metadata, an opt-in NON-GATING live smoke check, and the SDK a dependency of the live path only (fake constructs with no API key/network); (2) `resume-agent/agent_surface.json` drift fixes — `operation_fields` gains section-4.5-mandatory `reason` (~:246-257; today the guardrail grep can never catch operations shipping without one) and fact-proposal DTOs emit a `verification_state` from the declared set (~:27-33) as suggestions requiring resume-core validation — with strengthened contract assertions per RKIT-A-0006.

## Acceptance Criteria **[REQUIRED]**

- [ ] Claude adapter implements the T-0087 protocol in a private module importing `anthropic` LAZILY (import inside construction/call so the package is a live-path-only dependency; do NOT add it to install requirements — document as an optional extra). Constructing it under the gate profile raises the T-0088 typed error; constructing it without an API key raises a typed provider_error/config error, never a bare SDK exception.
- [ ] Config-driven: model name (default `claude-sonnet-4-6` — exact string, no date suffix), schema_mode, timeout_ms, max_retries, cost_ceiling from the T-0089 validated agent block. Structured output requested via the SDK's `output_config`/parse mechanisms per schema_mode; regardless of provider-side enforcement, the T-0087 shared validator ALWAYS validates the parsed payload before it leaves the adapter (schema_invalid on mismatch).
- [ ] SDK typed exceptions map to the taxonomy structurally: APITimeoutError→timeout; RateLimitError/APIStatusError(5xx)/APIConnectionError→provider_error (retryable per config); refusal stop_reason→refused; everything else→provider_error. NO message-text classification. Retry count + usage recorded in result metadata.
- [ ] Opt-in live smoke check: a standalone script/test excluded from ALL gates (guarded by an explicit env opt-in, e.g. RESUME_AGENT_LIVE_SMOKE=1 + API key), one temperature-conservative extraction call proving the seam. Gate-isolation test proves gates cannot reach it.
- [ ] `agent_surface.json` (verify it is unprotected; the protected files are tools/* and tests/boundary/*): `operation_fields` += `reason`; fact-proposal emission includes `verification_state` drawn from the manifest's declared set (honest default `inferred` or `unknown` for agent-derived proposals — pick per the declared set's semantics, suggestions only, `requires_validation` stays true). Contract tests assert both (the two missing assertions the audit flagged). If any needed pin lives in protected tools/resume_agent_guardrails.py, DEFER with a verbatim patch.
- [ ] Mutation probes: strip metadata from a result → protocol test fails; emit out-of-schema fake payload → schema_invalid test fails; remove `reason` from operation_fields → new manifest assertion fails; drop verification_state from emitted proposal → new DTO assertion fails.
- [ ] `--pr`, `--smoke`, `--future-contract` green (NO live calls in any); verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- SDK notes (verified against current docs): package `anthropic`; `client.messages.create(...)` with `output_config={"format": {"type": "json_schema", "schema": ...}}` for structured output (the old top-level `output_format` is deprecated); `claude-sonnet-4-6` accepts temperature (use 0 per RKIT-A-0003) — but do NOT hardcode sampling params in a way that breaks newer models if config selects one (send temperature only when the model/config allows; simplest: only attach temperature for the default schema mode and document).
- Typed exceptions: `anthropic.APITimeoutError`, `RateLimitError`, `APIStatusError`, `APIConnectionError` — class-based mapping.
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0087/0088/0089. Final task; after: initiative → completed, bump 0.18.0, push, handoff update (driver).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. resume_agent_guardrails.py may pin agent_surface content — check FIRST; defer if pinned.
- Gates must never require network or ANTHROPIC_API_KEY.

## Status Updates **[REQUIRED]**

*To be added during implementation*
