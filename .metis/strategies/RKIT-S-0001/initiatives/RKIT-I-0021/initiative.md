---
id: resume-agent-auditability
level: initiative
title: "Resume-Agent Auditability, Determinism, and Evaluation Fixtures"
short_code: "RKIT-I-0021"
created_at: 2026-08-13T20:41:37.326228+00:00
updated_at: 2026-08-17T19:07:52.616373+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0016]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-agent-auditability
---

# Resume-Agent Auditability, Determinism, and Evaluation Fixtures Initiative

## Context **[REQUIRED]**

Package: `resume-agent`. This document previously carried Detailed Design bullets copied verbatim from the rewrite-adapter siblings ("Prompt/schema assets / Model adapter/fake runtime / Structured output validation") — off-topic for an auditability initiative and replaced wholesale here.

What already exists and is NOT this initiative's work: sha1-derived stable proposal IDs and identical-input determinism are implemented and passing for the current deterministic engine. What is genuinely missing, per the audit: (1) model/config metadata in manifests — TEST_SPEC Determinism Strategy (:91) requires "fixed model/config metadata in manifests" but neither the spec's contract cases nor `agent_surface.json` define where that metadata lives or a test for it, leaving the requirement unenforceable and unimplemented; (2) model-call audit records — no call-level audit trail of any kind exists (there are no model calls yet); (3) golden eval fixtures and any record/replay strategy for the fake runtime; (4) the Audit Gate fields (schema/package/model/template versions) from CONTRACT_SURFACE_ALIGNMENT.md have no agent-side source.

RKIT-A-0003 item 6 decided the audit-record fields: every model call records adapter id/version, model id, prompt/schema hashes, retry count, and a failure taxonomy (`timeout`, `schema_invalid`, `refused`, `provider_error`); run manifests reference these records. Item 4 decided the eval split: official gates run the `DeterministicFakeAdapter`; live-model quality checks live in a separate opt-in, non-gating eval harness.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Model/config metadata in run manifests with a DEFINED location and a test enforcing it — closing the TEST_SPEC :91 enforceability gap.
- Call-audit records per RKIT-A-0003 item 6 (adapter id/version, model id, prompt/schema hashes, retry count, failure taxonomy), emitted for every adapter call — live and fake — and referenced by run manifests, supplying the Audit Gate's schema/package/model/template version fields.
- Golden eval fixtures (inputs plus expected-output rubrics) for extraction, interview, rewrite, and equivalence surfaces, powering the opt-in live eval harness.
- A defined fake-runtime record/replay strategy: how live outputs may be captured into fixture candidates, and the human review step before any capture becomes a pinned fake output.

**Non-Goals:**
- The adapter protocol, fake runtime, and config block themselves (RKIT-I-0016) — this initiative consumes their metadata, it does not build the seam.
- The semantic behavior being evaluated: extraction (RKIT-I-0017), interview (RKIT-I-0018), rewrites (RKIT-I-0019), equivalences (RKIT-I-0020). Their golden fixtures deepen as those initiatives land; the harness and record schema do not wait for them.
- No run-manifest writing: workflow owns manifests; this package exposes the metadata and records workflow embeds.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

1. A defined manifest location for agent model/config metadata (adapter id/version, model id, config hash from the RKIT-I-0016 `agent` block, prompt-template versions), documented in TEST_SPEC and asserted by a contract test — the location-plus-test pair whose absence made TEST_SPEC :91 unenforceable.
2. Every `ModelAdapter` call emits a call-audit record with the RKIT-A-0003 item 6 fields; failed and retried calls are recorded with their taxonomy classification — failures are audit events, not silences.
3. Audit records are deterministic under the fake adapter: identical input yields byte-identical records (hashes included), keeping the Determinism Gate intact for agent-involved runs.
4. Golden eval fixtures exist per public surface with graded rubrics; the eval harness runs them against the live adapter strictly opt-in and non-gating (RKIT-A-0003 item 4).
5. Record/replay: captured live outputs land in a quarantine area and become pinned `DeterministicFakeAdapter` fixtures only through explicit human promotion; no automatic fixture refresh from live calls.
6. An Audit Gate reconstruction check passes: from a run manifest plus audit records, the exact adapter, model, config, prompt versions, and failure history of an agent-involved run are recoverable.

## Detailed Design **[REQUIRED]**

- **Call-audit record.** `{call_id, adapter_id, adapter_version, model_id, prompt_hash, schema_hash, config_hash, retry_count, outcome: ok | timeout | schema_invalid | refused | provider_error, timestamps, usage}`. Emitted through a package-owned sink interface; workflow subscribes and embeds references in run manifests. Prompt/schema hashes come from the versioned template assets (RKIT-I-0016/0017 build them as hashable).
- **Manifest metadata block.** A single agent-metadata structure (adapter/model/config/template versions) exposed by the package for workflow to place at the defined manifest location; the contract test asserts presence and shape at that location so the requirement is enforceable, not aspirational.
- **Eval harness.** Opt-in runner (explicit env/config switch, never in protected gates) that executes golden fixtures against the live adapter and scores against rubrics; output is a report artifact, never a pass/fail gate on protected suites.
- **Record/replay.** Capture mode wraps the live adapter, writing candidate fixtures keyed by the same (template id, schema id, canonical input) hash the fake uses; promotion is a reviewed, deliberate fixture change — the mechanism that prevents the eval loop from quietly rewriting gate truth.
- **Migration note.** Existing sha1 ID determinism is untouched; audit plumbing layers beside it, and the fake adapter emits the same record shape so gates exercise the audit path end to end.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **TEST_SPEC strengthening (the audit-flagged :91 gap this initiative owns):** define the manifest metadata location in the spec and add the contract case asserting it — converting an unenforceable sentence into a test.
- Contract tests: every fake-adapter call yields a complete audit record; forced `timeout`/`schema_invalid`/`refused`/`provider_error` produce records with correct taxonomy and retry counts; identical inputs yield identical records.
- Reconstruction test: manifest reference plus records recover the full model/config/prompt identity of a run (Audit Gate).
- Gate-safety tests: eval harness and capture mode are unreachable under the protected-gate profile; promotion of a captured fixture changes gate fixtures only via an explicit reviewed diff.
- Boundary guardrails stay green; no protected assertion is weakened by the new plumbing.

## Alternatives Considered **[REQUIRED]**

- **Provider-side logging (rely on Anthropic console/request logs) instead of package-owned records.** Rejected: the Audit Gate requires reconstruction from workspace artifacts alone; provider logs are external, unqueryable from manifests, absent for the fake adapter, and silent on prompt/schema hashes.
- **Automatic record/replay refresh as the fixture strategy.** Rejected: auto-promoted live outputs would let model drift rewrite official gate expectations without review — the exact test-fidelity failure class the audit documented; human-promoted fixtures keep gate truth deliberate.
- **Make live eval scores a protected gate.** Rejected by RKIT-A-0003 item 4: live calls are nondeterministic and costly; protected gates stay on the fake adapter, with quality measured in the opt-in harness.

## Implementation Plan **[REQUIRED]**

1. Call-audit record schema, sink interface, and emission from both adapters (fake first).
2. Manifest metadata block plus the defined-location contract test and TEST_SPEC :91 strengthening.
3. Failure-taxonomy and reconstruction tests (Audit Gate check).
4. Golden eval fixture format, rubrics, and the opt-in harness runner.
5. Capture/quarantine/promotion tooling for record/replay with gate-safety tests.

## Status Updates

- 2026-08-17: Decomposed into RKIT-T-0101 (call-audit record/sink/emission, opus+high) → RKIT-T-0102 (agent-metadata manifest block + defined-location contract test + TEST_SPEC :91 + Audit Gate reconstruction, opus+high) → RKIT-T-0103 (golden eval fixtures + opt-in harness + capture/quarantine/promotion, opus+medium), serial chain. Grounding checks done: workflow manifest already carries `agent_model_config` (workflow/schemas.py:59) and `audit_refs` (:73) — T-0102 reuses (no new manifest field, no protected edit); resume_agent guardrail surface untouched (metadata exposed through existing channels, surface advertisement deferred to approval batch if needed). T-0101 dispatched to codex.
- 2026-08-17 (later): ALL THREE TASKS COMPLETE — T-0101 (6d4d94c), T-0102 (fa172a3), T-0103 (cfcdbca). All six initiative requirements satisfied: (1) defined manifest location = agent_model_config five-field block + contract test; (2) every adapter call emits an audit record incl. all four failure taxonomies; (3) byte-identical records under the fake adapter (independently probed); (4) golden fixtures per surface + opt-in non-gating harness; (5) quarantine + explicit human promotion with --replace guard; (6) Audit Gate reconstruction test recovers full identity + failure history. Zero protected-file edits. Gates green at every commit. Initiative complete; version bumped to 0.22.0.

## Dependencies / Blocked Status

Blocked by RKIT-I-0016 (`blocked_by: ["RKIT-I-0016"]`) — audit records and manifest metadata are built on the adapter result metadata, config hash, and versioned templates the foundation provides. The previous prose dependency on RKIT-I-0019 is dropped: audit plumbing depends on the foundation, not the rewrite adapter; per-surface eval fixtures simply deepen as RKIT-I-0017/0018/0019/0020 land. The former RKIT-A-0003 block is lifted: the ADR was decided 2026-08-13 and fixes the audit-record fields and the gate/eval split this initiative implements.