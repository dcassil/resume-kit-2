---
id: call-audit-record-schema-sink-and
level: task
title: "Call-audit record schema, sink, and emission from both adapters"
short_code: "RKIT-T-0101"
created_at: 2026-08-17T18:37:55.820964+00:00
updated_at: 2026-08-17T18:40:24.141376+00:00
parent: resume-agent-auditability
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0021
---

# Call-audit record schema, sink, and emission from both adapters

## Parent Initiative

[[RKIT-I-0021]]

## Objective

Implement the RKIT-A-0003 item 6 call-audit record: a package-owned record schema plus sink interface, emitted for EVERY `ModelAdapter` call — fake and live, success and failure — so that failed and retried calls are audit events, not silences, and identical fake-adapter inputs yield byte-identical records (Determinism Gate).

## Acceptance Criteria

## Acceptance Criteria

- [ ] New private module (e.g. `resume_agent/_call_audit.py` — workflow/__init__.py-style line caps do not apply here, but keep it private; `resume_agent/__init__.py` re-exports only the public sink-registration/reading surface if one is needed) defining the call-audit record with EXACTLY these fields per the initiative's Detailed Design: `{call_id, adapter_id, adapter_version, model_id, prompt_hash, schema_hash, config_hash, retry_count, outcome, timestamps, usage}` where `outcome ∈ {ok, timeout, schema_invalid, refused, provider_error}` — the SAME closed taxonomy `AdapterResult`/`AdapterFailure` already use (no new outcome values, no free-text status).
- [ ] `call_id` is deterministic under the fake adapter: derived from stable content (e.g. sha256 over adapter_id + prompt_hash + schema_hash + canonical input + a per-run monotonic call sequence number), NOT uuid4/wall-clock. `timestamps` must be structurally present but deterministic under the fake adapter (e.g. logical sequence counters, or fixed sentinel values documented in code) — NO `time.time()`/`datetime.now()` in the fake path. The live adapter MAY record real timestamps; the record schema treats them opaquely.
- [ ] `prompt_hash`/`schema_hash` come from the versioned template/schema assets (sha256 of the template file bytes and canonical schema JSON — reuse the existing hashing in `_fake_adapter.py` / prompt asset loaders; do not invent a second hashing scheme). `config_hash` reuses `stable_agent_config_hash`.
- [ ] Sink interface: a small protocol (`CallAuditSink.record(record) -> None`) with a default in-memory collecting sink; emission happens inside `ValidatingModelAdapter.complete` (one chokepoint — both `DeterministicFakeAdapter` and the Anthropic adapter inherit it) so no adapter call path can skip emission. Sink injection follows the existing context-injectable seam style (constructor arg, like `context["_adapter"]`).
- [ ] Failure emission: forced `timeout`, `schema_invalid`, `refused`, `provider_error` each produce a record with the correct `outcome` and the retry count from the failure; a schema-invalid result records `schema_invalid` (not `ok`), and the record is emitted even when `complete` returns a failed `AdapterResult`.
- [ ] Determinism contract test: two identical fake-adapter calls (fresh sinks) yield byte-identical serialized records, hashes included. Distinct inputs yield distinct `call_id`s.
- [ ] Unit + contract tests in `tests/unit/test_resume_agent_call_audit_unit.py` and extension of `tests/contract/test_resume_agent_adapter_contract.py` (NOT protected) covering: every-call emission (ok + all four failure taxonomies), determinism, chokepoint coverage (a subclass overriding `_complete_unchecked` still emits), and field completeness (record schema self-validates; missing field is a typed error, not a silent None).
- [ ] NO protected file edits (tools/*, tests/boundary/*, TEST_SPEC.md under tools/). resume-agent/TEST_SPEC.md (not protected) gains a call-audit section naming the covering tests.
- [ ] Gates green: `python3 tools/run_gate.py --pr --root .` and `--smoke`; no gate weakening; grep-proof that no uuid4/wall-clock enters the fake-adapter audit path.

## Implementation Notes

### Technical Approach
Emit from `ValidatingModelAdapter.complete` after the result is finalized (success or failure) so retry/validation outcomes are known. Records are plain dicts (JsonObject) validated by a module-owned schema constant, mirroring `_schema_validation.py` style. Keep the sink optional-but-default-collecting so existing callers work unchanged; workflow integration (manifest embedding) is T-0102's job — this task only guarantees records exist and are retrievable from the sink.

### Dependencies
RKIT-I-0016 substrate (already landed): `_adapters.py`, `_fake_adapter.py`, `_agent_config.py`.

### Risk Considerations
Wall-clock leakage into fake-path records would break the determinism gate — make the determinism test serialize the full record. Do not touch `workflow/__init__.py` (at 1499/1500 guardrail lines).

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*