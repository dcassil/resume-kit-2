---
id: jsonl-sink-option-sink-contract
level: task
title: "JSONL sink option, sink contract docs, audit reconstruction E2E, TEST_SPEC coverage"
short_code: "RKIT-T-0109"
created_at: 2026-08-17T19:46:33.860201+00:00
updated_at: 2026-08-17T20:03:14.072887+00:00
parent: implement-career-mcp-mutation
blocked_by: [RKIT-T-0108]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0013
---

# JSONL sink option, sink contract docs, audit reconstruction E2E, TEST_SPEC coverage

## Parent Initiative

[[RKIT-I-0013]]

## Objective

Finish RKIT-I-0013 (R5/R6): an append-only JSONL sink option for CLI/host use, the sink contract documented as package surface for workflow's run-manifest consumption, and the executable reconstruction proof — from the audit stream ALONE, determine which facts changed and their resulting verification states — making TEST_SPEC.md:111-118's audit E2E line executable for the first time.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Append-only JSONL sink (e.g. `career_mcp/audit.py` JsonlAuditSink): one JSON object per line, append-only writes (mirror workflow's operations.jsonl style incl. flush; no rewrite-in-place), path supplied by caller; injectable through the existing create_career_mcp sink parameter unchanged.
- [ ] Sink contract documented as package surface: the AuditEvent field set and sink semantics written where the package declares surface (career-mcp/TEST_SPEC.md section + a docstring on the sink interface; if tool_surface.json has a natural metadata slot for it, use it and regenerate the byte-copy — but do NOT invent manifest structure the guardrail might pin; defer if it trips).
- [ ] Reconstruction contract test (the R6 proof): scripted sequence against a real store — propose_fact (confirmed), verify_fact (confirmed), add_relationship (confirmed), one REJECTED verify (unconfirmed → policy_error) — then, reading ONLY the emitted audit stream (no store access in the assertion phase), reconstruct exactly which facts changed and their resulting verification states, and assert the rejected verify changed nothing. This is the "audit can identify which MCP operations changed career knowledge" TEST_SPEC :111-118 line made executable — update that TEST_SPEC section to name this test.
- [ ] JSONL round-trip variant: the reconstruction also passes when events flow through the JsonlAuditSink and are re-read from disk (json.loads per line) — proving the persisted form is sufficient, not just the in-memory dicts.
- [ ] Read-amplification guard: the scripted sequence includes read calls; assert read events stay `{tool, status}` and the reconstruction needs no read-event data.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits.

## Implementation Notes

### Technical Approach
Reconstruction logic lives in the TEST (it proves stream sufficiency); do not add a public reconstruction API to career-mcp — workflow owns cross-package reconstruction. Use T-0108's injectable id/clock seams for deterministic assertions.

### Dependencies
RKIT-T-0108 (full AuditEvent emission).

### Risk Considerations
Keep the JSONL sink dependency-free and side-effect-free at import. Don't let the sink write inside the repo tree during tests — tmp dirs only.

Recommended Agent: opus + medium

## Status Updates

- 2026-08-17: Loaded task and Straight Jacket instructions. Verified current protected-file state: only the expected pre-existing `tools/resume_agent_guardrails.py` checksum mismatch. Inspected `career_mcp/audit.py`, `career_mcp.__init__`, `career-mcp/TEST_SPEC.md`, real-store mutation paths, and existing contract tests. Decision: document sink contract in TEST_SPEC and `JsonlAuditSink` docstring; defer manifest metadata because `tool_surface.json` has no natural audit-sink slot.
- 2026-08-17: Implemented `JsonlAuditSink`, added an append-only JSONL sink contract test, added real-store audit reconstruction E2E including JSONL round trip/read-event guard/rejected verify guard, and updated `career-mcp/TEST_SPEC.md`. Focused checks passed: `python3 -m unittest tests.contract.test_career_mcp_contract.CareerMcpAuditContractTests` and `python3 -m unittest tests.e2e.test_career_mcp_audit_reconstruction_e2e`.