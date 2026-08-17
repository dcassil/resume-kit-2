---
id: resume-agent-proposal-model
level: initiative
title: "Resume-Agent Proposal Model Adapter Foundation"
short_code: "RKIT-I-0016"
created_at: 2026-08-13T20:41:37.188390+00:00
updated_at: 2026-08-17T16:25:20.969737+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-agent-proposal-model
---

# Resume-Agent Proposal Model Adapter Foundation Initiative

## Context **[REQUIRED]**

Package: `resume-agent`. The package is no longer a scaffold: all five public functions are implemented (~7,500 lines in `resume_agent/__init__.py`) and the 16 contract/boundary tests pass. Genuinely done: the proposal-only surface (no mutation, persistence, scoring, or forbidden imports), proposal DTO envelopes with `requires_validation`, deterministic sha1-derived evidence-linked IDs, typed errors, and a functional static guardrail tool.

What is missing is the actual agent. There is zero model integration: no adapter, no prompt/input builders, no structured-output schema validators, no fake runtime, no model/config metadata anywhere — every item in TEST_SPEC.md Expected Structure (:17-26) and Determinism Strategy (:91-93) is absent. The five functions are backed by a fixture-tuned regex/keyword engine instead.

The machine-readable contract has drifted: `agent_surface.json:246-257` `operation_fields` omit the section 4.5-mandatory `reason` field (so the guardrail grep can never catch operations shipping without one), and `agent_surface.json:27-33` declares `verification_states` that no proposal ever carries (fact proposals in `__init__.py:73-92` have no `verification_state` field).

RKIT-A-0003 is decided: resume-agent owns a provider-neutral `ModelAdapter` protocol; Anthropic Claude is the first live runtime; a `DeterministicFakeAdapter` backs all official gates; an `agent` config block lives in workspace `config.json`; every result carries adapter/model metadata. RKIT-A-0006 authorizes the protected-manifest edits the drift fixes require.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Ship the `ModelAdapter` protocol: context plus output JSON schema in, schema-validated structured proposal out, with adapter id/version, model id, and runtime config as metadata on every result (RKIT-A-0003 item 1).
- Ship the Anthropic Claude adapter via the official SDK: configurable model name with a Sonnet-class default, temperature 0 for extraction/interpretation calls (RKIT-A-0003 item 2).
- Ship a `DeterministicFakeAdapter` with fixture-pinned outputs that every official gate (contract, boundary, smoke, E2E) runs against — no live model in protected suites (RKIT-A-0003 item 4).
- Structured-output schema validation that rejects out-of-schema model output with typed errors using the A-0003 failure taxonomy (`timeout`, `schema_invalid`, `refused`, `provider_error`).
- A schema-validated `agent` block in workspace `config.json` (model name, schema mode, timeout, retries, cost ceilings), included in the run-manifest config hash (RKIT-A-0003 item 3).
- Remediate `agent_surface.json` drift: `operation_fields` gains `reason`; fact proposals emit a `verification_state` from the declared set (as suggestions requiring resume-core validation) so manifest and emitted DTOs agree.

**Non-Goals:**
- Extraction prompts/quality (RKIT-I-0017), question phrasing and answer interpretation (RKIT-I-0018), rewrite grounding and full section 4.5 DTO reshaping (RKIT-I-0019), the `proposeEquivalences` surface (RKIT-I-0020), and call-audit records plus eval fixtures (RKIT-I-0021). This initiative builds the seam those five plug into, not their behavior.
- No opt-in live eval harness content — RKIT-I-0021 owns the harness that exercises the live adapter.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

1. `ModelAdapter` protocol exists with two implementations (Claude, DeterministicFake); every result carries adapter id, adapter version, model id, and runtime config (RKIT-A-0003 items 1-2).
2. Official gates never call a live model: contract/boundary/smoke/E2E suites are wired to `DeterministicFakeAdapter` only, and a gate-profile test asserts the live adapter cannot be constructed there (RKIT-A-0003 item 4; Determinism Gate).
3. Model output failing the declared output schema is rejected with a typed `schema_invalid` error; provider failures map onto the four-value taxonomy — never silent fallback output.
4. The `agent` config block is schema-validated at load; unknown keys fail validation (consistent with RKIT-A-0006 decision 6 on config strictness); the validated block participates in the run-manifest config hash (RKIT-A-0003 item 3).
5. `agent_surface.json` `operation_fields` includes `reason` (fixing :246-257), and every fact-proposal DTO emits a `verification_state` drawn from the set declared at :27-33 — closing both verified manifest-drift findings. Protected-manifest edits are authorized by RKIT-A-0006 and must strengthen, never weaken, assertions.
6. The Anthropic SDK is a dependency of the live path only; constructing the fake adapter requires no API key and no network.
- Outputs remain schema-constrained proposals requiring validation; no official score, persistence, verification authority, direct mutation, or workflow decisions.

## Detailed Design **[REQUIRED]**

- **Protocol.** `ModelAdapter.complete(request) -> AdapterResult`. The request carries the prompt/input payload plus the output JSON schema id; the result carries the parsed, schema-validated proposal payload plus `adapter_id`, `adapter_version`, `model_id`, `runtime_config`, retry count, and usage counters. Validation happens inside the adapter boundary so no caller ever sees unvalidated model output.
- **Claude adapter.** Official Anthropic SDK; structured output enforced via the configured schema mode; model name from config with a Sonnet-class default; temperature 0; timeout/retry policy from config; retries surface in result metadata (consumed by RKIT-I-0021 audit records).
- **DeterministicFakeAdapter.** Returns fixture-pinned outputs keyed by a stable hash of (prompt template id, schema id, canonical input). Unknown keys raise a typed error rather than improvising — a fake that fails loudly keeps gates honest.
- **Config.** `config.json` gains an `agent` block `{model, schema_mode, timeout_ms, max_retries, cost_ceiling}` validated at load by a schema shipped in this package; the hash of the validated block is exposed for the workflow run manifest.
- **Typed errors.** The existing package error envelope is extended with the four-value failure taxonomy; adapters may fail only through it.
- **Manifest migration.** `agent_surface.json` is updated in the same change as the DTO emission fix so the guardrail grep and the emitted shapes never disagree mid-stream.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Adapter-protocol contract tests: metadata present on every result; schema-invalid fake output rejected with `schema_invalid`; retry count surfaced.
- Gate-isolation test: official suites construct only `DeterministicFakeAdapter`; assert the live adapter is not constructible under the gate profile.
- Config tests: valid `agent` block loads; unknown key fails validation; documented defaults apply when absent; config hash is stable across identical configs.
- TEST_SPEC strengthening (the audit-flagged manifest gap): add assertions that `operation_fields` contains `reason` and that emitted fact proposals carry a `verification_state` in the manifest-declared set — the two missing assertions that let the current drift ship green.
- The live adapter gets an opt-in, non-gating smoke check only (RKIT-A-0003 item 4).

## Alternatives Considered **[REQUIRED]**

- **Direct SDK calls inside each public function, no adapter seam.** Rejected: makes the Determinism Gate unsatisfiable (no fake substitution point), scatters provider coupling across five functions, and denies RKIT-I-0017/0018/0019 a single tested boundary.
- **Third-party abstraction layer (LiteLLM/LangChain-style).** Rejected: a heavyweight dependency for what is one interface and two implementations; owning the seam preserves provider-neutrality more cheaply, per RKIT-A-0003's chosen option.
- **Local model first (Ollama or similar).** Rejected in RKIT-A-0003: materially weaker semantic quality — the package's entire purpose — while requiring identical adapter work.
- **Record/replay of live calls as the official-gate mechanism.** Rejected here: replay fixtures rot with prompt changes and leak provider wire formats into gates; fixture-pinned fake outputs are the gate mechanism (record/replay is evaluated separately in RKIT-I-0021 for the eval harness).

## Implementation Plan **[REQUIRED]**

1. `ModelAdapter` protocol, request/result DTOs, typed failure taxonomy.
2. `DeterministicFakeAdapter`, gate wiring, gate-isolation test.
3. Structured-output schema validators shared by both adapters.
4. `agent` config block: schema, load-time validation, config-hash exposure.
5. Anthropic Claude adapter (live path, opt-in non-gating smoke check).
6. `agent_surface.json` drift fixes (`reason` in operation_fields; emitted verification_states) with strengthened contract assertions, under RKIT-A-0006 authorization.

## Dependencies / Blocked Status

Not blocked (`blocked_by: []`). RKIT-A-0003 (decided 2026-08-13) settles the adapter architecture, provider, config location, and gate policy this initiative implements; RKIT-A-0006 authorizes the protected-manifest realignment. All five other resume-agent initiatives (RKIT-I-0017 through RKIT-I-0021) block on this one.