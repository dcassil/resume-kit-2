---
id: write-path-smoke-extension
level: task
title: "Write-path smoke extension (protected run_smoke edit), TEST_SPEC strengthening, audit-reconstruction E2E wiring"
short_code: "RKIT-T-0122"
created_at: 2026-08-18T23:10:05.170939+00:00
updated_at: 2026-08-18T23:45:24.690881+00:00
parent: integrate-career-mcp-smoke-and-e2e
blocked_by: [RKIT-T-0121]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0015
---

# Write-path smoke extension (protected run_smoke edit), TEST_SPEC strengthening, audit-reconstruction E2E wiring

## Parent Initiative

[[RKIT-I-0015]]

## Objective

Close initiative R2 + the TEST_SPEC-strengthening set: `tools/run_smoke.py` (authorized protected edit, no-verify workflow) extends its read-only career-mcp coverage with a real-store write round trip (propose → verify with evidence → add_relationship → search reflecting the writes, all with confirmed:true), and career-mcp/TEST_SPEC.md gets the audit-flagged wording repairs.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] PROTECTED EDIT (authorized, joins Daniel's pass — after this task the command is `straight-jacket update tools/resume_core_guardrails.py tools/run_smoke.py`): extend the career-mcp smoke section (the read-path block around the search/get + raw-SQL-rejection checks) with the write round trip through `call_tool`: propose_fact (evidence, confirmed) → verify_fact (evidence_id, confirmed) → add_relationship (confirmed) → search_facts showing the written+verified fact. Assert typed ok envelopes and the audit sink capturing full mutation events (I-0013 fields present on at least one event). Minimal surgical diff, reported verbatim.
- [ ] career-mcp/TEST_SPEC.md strengthening (NOT protected): (a) :89-93 Job A→B rewritten to REQUIRE a real store (satisfying it with a canned fake dict is explicitly insufficient; names T-0121's covering scenarios); (b) :111-118 E2E items name the now-executable tests (alignment, gap resolution, audit reconstruction); (c) the forbidden list at :18-25 gains the missing `truncate_table` entry (guardrail + manifest already have it — the spec is the outlier). Strengthen-only.
- [ ] Smoke green end to end in the installed-venv harness; the write round trip must be idempotent-safe for repeat smoke runs (fresh temp store per run — follow the existing smoke store setup).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. straight-jacket shows exactly the two expected mismatches (resume_core_guardrails.py, run_smoke.py).

## Implementation Notes

### Technical Approach
Read the existing career-mcp smoke block first; mirror its require() style. The writes go through the SAME adapter instance the read checks use (or a fresh one on the same store) — no SQL, no store internals.

### Dependencies
RKIT-T-0121 (scenarios/fixture shapes), I-0012 confirmed arg, I-0013 audit events.

### Risk Considerations
run_smoke.py already carries the T-0120 additions — take care not to disturb them; keep the new block additive.

Recommended Agent: opus + medium

## Status Updates

- 2026-08-18: Added the authorized `tools/run_smoke.py` career-mcp write-path round trip through the existing real-store adapter/audit sink, after the main workflow assertions to avoid changing deterministic rewrite fixture inputs. Strengthened `career-mcp/TEST_SPEC.md` with `truncate_table`, real-store-only Job A/B wording, and named executable E2E coverage. Verified `--smoke`, `--pr`, and `--future-contract` green; `straight-jacket verify --json` reports exactly `tools/resume_core_guardrails.py` and `tools/run_smoke.py` checksum mismatches.