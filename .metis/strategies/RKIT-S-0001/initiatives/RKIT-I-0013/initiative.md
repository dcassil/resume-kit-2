---
id: implement-career-mcp-mutation
level: initiative
title: "Implement Career-MCP Mutation Audit and Operation Traceability"
short_code: "RKIT-I-0013"
created_at: 2026-08-13T20:41:37.110612+00:00
updated_at: 2026-08-13T20:41:37.110612+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0010"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Implement Career-MCP Mutation Audit and Operation Traceability Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. An audit sink already exists but is nominal: every call — read or mutation — records only `{'tool': name, 'status': status}` (`career_mcp/__init__.py:179-186`). That cannot identify which facts changed, with what arguments, or when; the TEST_SPEC E2E expectation "audit can identify which MCP operations changed career knowledge" (TEST_SPEC.md:111-118) has no executable coverage and cannot have any against the current sink. This initiative is a repair of an insufficient existing sink, not greenfield audit work.

It was previously gated on an undeclared open question — which audit fields are mandatory — that RKIT-A-0002 item 5 (decided) now answers: mutation events carry tool name, operation id, redacted arguments, affected fact ids, mutation flag, resulting verification state, conflict flag, confirmation_required, and timestamp; read calls log tool name and status only. These fields are the substrate workflow run-manifest reconstruction consumes. With the ADR decided, the only remaining dependency is RKIT-I-0010, whose typed result envelopes supply the resulting-state and rejection data the events record.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Replace the two-field sink payload with the full RKIT-A-0002 item 5 field set for every mutating call, including rejected mutations.
- Redaction: audit events never contain sensitive fields (reusing the DTO strip rules) or persistence internals.
- Reads stay minimal (tool + status) per the ADR — no read-amplification of the audit stream.
- An executable reconstruction proof: from the audit stream alone, determine which facts changed and their resulting verification state.

**Non-Goals:**
- Cross-package run manifests, checkpoints, and recovery semantics — the workflow package owns those (CONTRACT_SURFACE_ALIGNMENT.md ownership table); this initiative emits the per-operation substrate they consume.
- Defining confirmation semantics — RKIT-I-0012 defines `confirmation_required`; this initiative records it (before RKIT-I-0012 lands, the existing flag value is recorded).
- Transport-side request logging — RKIT-I-0014.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: Mutation audit events carry exactly the RKIT-A-0002 item 5 mandatory fields: tool name, operation id, redacted arguments, affected fact ids, mutation flag, resulting verification state, conflict flag, confirmation_required, timestamp. This replaces the `{tool, status}` payload at `career_mcp/__init__.py:179-186`.
- R2: Read calls emit tool name and status only (RKIT-A-0002 item 5).
- R3: Rejected and errored mutations still emit full events (mutation flag true, affected ids empty, error type included) so failed writes are traceable — today a rejected mutation is indistinguishable in audit from a successful read.
- R4: Argument redaction reuses the sensitive-field strip rules; no sensitive input value ever appears in an event.
- R5: Events are structured, JSON-serializable dicts through the injectable sink — sufficient for workflow run-manifest reconstruction without persistence leakage (no SQL, no store-internal identifiers).
- R6: The TEST_SPEC E2E item "audit can identify which MCP operations changed career knowledge" (TEST_SPEC.md:111-118) gains executable coverage.

### Dependencies
- RKIT-I-0010 (typed result envelopes feed affected ids, resulting state, and error types). RKIT-A-0002 item 5 is decided — the field list is settled input; the prior undeclared ADR gate is lifted.

### Blocked Status
- Yes (blocked_by: ["RKIT-I-0010"]).

## Detailed Design **[REQUIRED]**

**AuditEvent shape.** `{operation_id, timestamp, tool, is_mutation, status, args_redacted, affected_fact_ids, resulting_verification_state, conflict_flag, confirmation_required, error_type?}` — the nine mandatory fields plus `status`/`error_type` for failure traceability. `operation_id` is a uuid4 minted per `call_tool` invocation; `timestamp` is UTC ISO-8601. For read tools the event is `{tool, status}` only.

**Construction.** One emit site at the end of `call_tool`, after response construction, so success and failure paths converge and no dispatch branch can skip auditing. `args_redacted` is the validated argument dict passed through the same sensitive-field strip used for response DTOs (plus RKIT-I-0010's scrub rules). `affected_fact_ids`, `resulting_verification_state`, and `conflict_flag` are read from the typed result envelope rather than re-querying the store — audit reflects what the caller was told.

**Sink.** The sink interface stays injectable: in-memory list by default (tests), an append-only JSONL sink option for CLI/host use. The sink contract is documented as part of the package surface so workflow can consume it for run manifests.

**Migration note.** Existing sink consumers (smoke tooling) receive strictly more fields; the two current keys keep their names, so this is additive for readers and breaking only for tests that assert the exact two-key shape — those assertions are strengthened, not weakened.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Per-mutating-tool contract tests asserting all mandatory fields are present and correctly valued (ids match the mutated facts, state matches the result envelope).
- Read-call minimal-event test and a rejection-path event test (regression for the current audit blindness to failed writes).
- Redaction test: a sensitive argument value planted in a mutation never appears anywhere in the emitted event.
- Reconstruction test — the TEST_SPEC-strengthening item for this scope: run a scripted sequence (propose, verify, add_relationship, one rejected verify), then from the audit stream alone assert exactly which facts changed and their resulting states, making TEST_SPEC.md:111-118's audit E2E line executable for the first time.

## Alternatives Considered **[REQUIRED]**

- **Log full raw arguments for maximum fidelity.** Rejected: leaks sensitive fields the DTO layer strips everywhere else and violates the no-persistence-leakage requirement; redacted arguments preserve traceability without leakage.
- **Push audit into career-store (triggers/log table).** Rejected: the store cannot know the MCP tool name, operation id, or confirmation context, and CONTRACT_SURFACE_ALIGNMENT.md assigns cross-package audit to workflow with each boundary emitting its own events; MCP owns its boundary.
- **Unstructured log lines instead of structured events.** Rejected: run-manifest reconstruction requires machine-readable events; parsing prose logs is exactly the fragility the reconstruction test exists to prevent.

## Implementation Plan **[REQUIRED]**

1. Define the AuditEvent construction and single emit site in `call_tool`.
2. Wire mutation metadata from the typed envelopes, including rejection paths.
3. Apply redaction via the shared strip rules; add the redaction test.
4. Add the JSONL sink option and document the sink contract for workflow consumption.
5. Add the reconstruction contract test and the TEST_SPEC E2E coverage; run the canonical package gate.
