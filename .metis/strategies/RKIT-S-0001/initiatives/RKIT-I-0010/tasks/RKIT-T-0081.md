---
id: typed-error-envelope-structural
level: task
title: "Typed error envelope + structural classification (R1, R2)"
short_code: "RKIT-T-0081"
created_at: 2026-08-16T19:05:18.749033+00:00
updated_at: 2026-08-16T19:12:53.405416+00:00
parent: harden-career-mcp-tool-argument
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0010
---

# Typed error envelope + structural classification (R1, R2)

## Parent Initiative

[[RKIT-I-0010]]

## Objective **[REQUIRED]**

Fix the two audit-confirmed error-path defects in `career-mcp/career_mcp/__init__.py`: (R1) `_mutation` (~312-322) passes store rejections through with `status: rejected|error` but NO `error: {type, message}` object — empirically `career.verify_fact` with `imported` returned status `error` with no `error` key, crashing any agent that checks `result['error']['type']`; (R2) exception→error-type classification keyword-matches message text ('confirmation'→policy_error, 'not found'→not_found at ~359-365) — works only for the fake's exact ValueError wording. Centralize response construction so the invariant `status != "ok" ⇒ well-formed error object` is structurally unbreakable, and classify structurally (typed store rejection reason codes + exception classes), never from message text.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] One result-construction helper builds EVERY tool response with shape `{"tool", "status": "ok"|"rejected"|"error", "data"?, "error"?: {"type", "message"}}`; the `status != ok ⇒ error present` invariant is enforced inside the helper (no code path can emit an envelope-less rejection).
- [ ] Store-returned rejection dicts map their reason codes to the taxonomy `validation_error | policy_error | not_found | store_error`; raised exceptions map by exception CLASS (store validation → validation_error, missing entity → not_found, confirmation/policy signal types → policy_error, anything else → store_error). Message text used only as the post-scrub human-readable `message`, never for classification.
- [ ] Regression: `career.verify_fact` driven to a real-store rejection (e.g. disallowed target state) returns a well-formed `error.type`/`error.message` — the audit's envelope-less failure has a named test against store-shaped rejected dicts (NOT only raised exceptions — the fake-only blind spot that shipped the defect).
- [ ] Keyword classifier at ~359-365 is deleted; tests prove classification is wording-independent (same exception class with different message classifies identically).
- [ ] All existing career-mcp contract tests green; new tests exercise dict-rejection paths against the REAL store where feasible (RKIT-I-0011 later deletes the snake_case fake branch — write store-shaped tests).
- [ ] `--pr` and `--smoke` green; verify clean.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Inspect career-store's typed rejection shapes (verification transition engine results, TransactionResult payloads, typed exceptions in career_store) to map reason codes structurally; if the store lacks a needed typed signal, map that case to store_error honestly and note it for RKIT-I-0011/0012 — do not re-introduce text matching.
- Recommended Agent: opus + high

### Dependencies
None (first task). T-0082/0083 build on the envelope helper.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. career-mcp package files and tests/contract/ are unprotected.
- Keep the manifest (canonical package tool_surface.json + generated copy, RKIT-I-0009) in sync if descriptions change; run career-mcp/tools/sync_tool_surface.py after any manifest edit.

## Status Updates **[REQUIRED]**

- 2026-08-16: I-0009 complete (v0.15.0 pushed b07770b). I-0010 decomposed T-0081..0083 (serial, all touch career_mcp/__init__.py). Codex launched on this task: envelope helper w/ structural invariant, class/reason-code taxonomy mapping, keyword classifier deleted, store-shaped rejected-dict tests against the real store. Scrub rewrite explicitly deferred to T-0083.