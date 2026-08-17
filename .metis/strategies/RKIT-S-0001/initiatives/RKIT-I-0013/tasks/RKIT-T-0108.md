---
id: auditevent-shape-single-emit-site
level: task
title: "AuditEvent shape, single emit site, envelope-fed mutation metadata, redaction"
short_code: "RKIT-T-0108"
created_at: 2026-08-17T19:46:33.789751+00:00
updated_at: 2026-08-17T19:47:36.689563+00:00
parent: implement-career-mcp-mutation
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0013
---

# AuditEvent shape, single emit site, envelope-fed mutation metadata, redaction

## Parent Initiative

[[RKIT-I-0013]]

## Objective

Replace career-mcp's two-field `{tool, status}` audit payload with the full RKIT-A-0002 item 5 AuditEvent for every mutating call — including rejected and errored mutations — emitted from ONE site at the end of `call_tool`, with metadata read from the typed result envelope (never re-queried from the store) and arguments redacted through the shared strip rules. Reads stay minimal `{tool, status}`.

## Acceptance Criteria

## Acceptance Criteria

- [ ] AuditEvent for mutating tools: `{operation_id, timestamp, tool, is_mutation, status, args_redacted, affected_fact_ids, resulting_verification_state, conflict_flag, confirmation_required, error_type?}` (per initiative Detailed Design; `error_type` present exactly when status is not ok). Read tools: `{tool, status}` ONLY — a test asserts no extra keys ever appear on read events.
- [ ] operation_id = uuid4 per call_tool invocation; timestamp = UTC ISO-8601 — BOTH via injectable seams (module-level or constructor-injectable clock/id providers) so contract tests can pin them deterministically; tests must not sleep/regex-fuzz. (The ADR fixes the production values; the seam is for testability only.)
- [ ] Mutation-flag truth: `is_mutation` derives from the same manifest `mutates` classification `policy.py` uses (I-0012) — one source of truth, no parallel list.
- [ ] Single emit site: the existing `_record_audit` calls collapse so success, rejection (incl. I-0012 policy_error gating), and error paths all converge through one construction function; a test proves a policy-rejected mutation emits a FULL mutation event (is_mutation true, affected ids [], error_type policy_error, confirmation_required true) — the current audit blindness to failed writes is a named regression.
- [ ] Envelope-fed metadata: `affected_fact_ids`, `resulting_verification_state`, `conflict_flag`, `confirmation_required` read from the typed result envelope / policy decision the caller was told — NO store re-query. Per-mutating-tool contract tests assert ids match the mutated facts and state matches the envelope.
- [ ] Redaction (R4): `args_redacted` passes the validated arguments through the SAME sensitive-field strip / scrub rules the response DTOs use (reuse the I-0010 targeted redaction, don't fork it); redaction test plants a sensitive value in a mutation argument and asserts it appears nowhere in the serialized event; a plain benign message survives verbatim (regression pair, matching I-0010 style).
- [ ] Events are JSON-serializable structured dicts (test: json.dumps round-trip); no SQL text, no store-internal identifiers (assert against the store-identifier redaction list).
- [ ] Existing sink consumers: the two current keys keep their names (additive migration); any test asserting the exact two-key shape on mutations is STRENGTHENED to the full shape, never weakened.
- [ ] career-mcp/TEST_SPEC.md (not protected) audit items updated naming covering tests.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits.

## Implementation Notes

### Technical Approach
Keep the sink interface injectable as today (in-memory default). Construction in a small private module (e.g. `career_mcp/audit.py`) so `__init__.py` only wires. `affected_fact_ids` extraction per tool comes from the envelope's data (fact/relationship ids present in the result the caller received).

### Dependencies
I-0010 envelopes, I-0012 policy decision values — both landed.

### Risk Considerations
Do not let the uuid/clock leak into any snapshot-compared fixture; if smoke asserts on audit output, pin via the injectable seams. tools/run_smoke.py is protected — if smoke consumes the sink and breaks, adapt non-protected code, else STOP and defer.

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*