---
id: precise-persistence-leak-scrubbing
level: task
title: "Precise persistence-leak scrubbing + TEST_SPEC strengthening (R6) — close-out"
short_code: "RKIT-T-0083"
created_at: 2026-08-16T19:05:18.867056+00:00
updated_at: 2026-08-16T19:05:18.867056+00:00
parent: harden-career-mcp-tool-argument
blocked_by: ["RKIT-T-0081", "RKIT-T-0082"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0010
---

# Precise persistence-leak scrubbing + TEST_SPEC strengthening (R6) — I-0010 close-out

## Parent Initiative

[[RKIT-I-0010]]

## Objective **[REQUIRED]**

Replace the blunt substring blocklist scrub in `career-mcp/career_mcp/__init__.py` (~368-373) — which masks ANY message containing "update" or "delete", including legitimate validation messages — with targeted redaction of persistence artifacts (SQL statement shapes, store-internal identifiers) applied to `message` only. Strengthen `career-mcp/TEST_SPEC.md` (unprotected) with the envelope and argument-fidelity requirements whose absence certified the shallow paths as done. Initiative close-out: mutation probes, version bump handled by driver.

## Acceptance Criteria **[REQUIRED]**

- [ ] Scrub redacts persistence shapes via targeted patterns (e.g. `INSERT INTO ...`, `UPDATE <identifier> SET`, `DELETE FROM ...`, sqlite error signatures, table/column identifier leaks); matched messages replaced by a generic store-error message; everything else passes VERBATIM.
- [ ] Regression pair: a message containing a raw SQL fragment is redacted; a validation message containing the plain word "update" (e.g. "cannot update verification state without evidence") survives intact — the audit-flagged masking bug has a named test.
- [ ] Scrubbing applies to the envelope `message` only — never to `error.type` (classification is structural from T-0081) and never to `data`.
- [ ] `career-mcp/TEST_SPEC.md` gains explicit items: every non-ok result carries typed `error: {type, message}`; schema-accepted arguments must never be silently dropped; multi-value filters have union semantics; evidence-requiring verification rejects missing evidence_id; persistence details never leak while ordinary messages pass. Each item names its covering test.
- [ ] Mutation probes reported (mutate → named failing test → revert): envelope invariant broken → test fails; first-element-only filter restored → union test fails; blocklist scrub restored → masked-message regression fails.
- [ ] `--pr`, `--smoke`, `--future-contract` green; verify clean; new module names listed for the deferred run_tests.py batch if bridging was needed.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- career-mcp/TEST_SPEC.md is unprotected (tools/TEST_SPEC.md is the protected one — do not touch it).
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0081/0082. Final task; after it: initiative → completed, bump 0.16.0, push develop, handoff update (driver's job).

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

*To be added during implementation*
