---
id: per-function-render-status
level: task
title: "Per-function render status vocabulary, required_reduction/ok-bytes spec wording, strengthen-only contract tests"
short_code: "RKIT-T-0114"
created_at: 2026-08-18T21:28:11.302297+00:00
updated_at: 2026-08-18T21:55:55.385926+00:00
parent: resume-render-template-and-result
blocked_by: [RKIT-T-0113]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0029
---

# Per-function render status vocabulary, required_reduction/ok-bytes spec wording, strengthen-only contract tests

## Parent Initiative

[[RKIT-I-0029]]

## Objective

Close initiative R2–R5 spec-side: `render_surface.json` gains a per-function status table (ok/failed/unsupported with exact conditions per function, incl. when `validateRenderedOutput` must return `unsupported` — for RKIT-I-0032 to implement), the two audit-flagged wording gaps are pinned (`required_reduction` is a character count; `ok` requires an artifact whose bytes match its claimed `media_type`), all mirrored in TEST_SPEC with strengthen-only contract tests.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] FIRST verify current state — much has landed since re-baselining: I-0027 realigned measureLayout to character-count requiredReduction; I-0033 made renderPdf honest with the three-reason enum. This task must NOT redo those; it specifies and pins. Report what was already satisfied vs newly added.
- [ ] `render_surface.json`: per-function status table mapping each of the five functions (renderMarkdown, renderDocx, renderPdf, measureLayout, validateRenderedOutput) to allowed statuses + exact conditions for each; `unsupported` semantics = format/artifact-kind not supported under current policy/template with machine-readable `reason` (fold in I-0033's existing reason enum, don't duplicate it); the conditions under which validateRenderedOutput returns `unsupported` (pdf-kind artifacts under MVP policy) are SPECIFIED here for I-0032 to implement — specification only, no validateRenderedOutput behavior change in this task.
- [ ] `required_reduction` unit pinned: schema/manifest/TEST_SPEC all state integer CHARACTER count (RKIT-A-0006 item 7); a value-level contract test against a known-overflow fixture asserts the value is a character count, not a page delta (if I-0027's tests already do this, cite them and strengthen if any hole remains).
- [ ] "ok requires genuine bytes": manifest + TEST_SPEC state that ok always implies an artifact whose bytes match the claimed media_type; contract test asserts schema-level representability of `unsupported` with `reason` across functions.
- [ ] Per-function status table parity test: the manifest table's allowed-status sets are asserted against what each function can actually emit (drive each function's reachable statuses; unreachable claimed statuses or emittable unclaimed statuses fail by name) — the mechanism that prevents the "declared but never returned" drift from recurring.
- [ ] resume-render/TEST_SPEC.md mirrored wording, each item naming covering tests. Strengthen-only everywhere (RKIT-A-0006); no fixture truth content changes.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits (check whether any guardrail pins render_surface.json's exact structure before adding the table; defer if it trips).

## Implementation Notes

### Technical Approach
Mostly declarative + tests. The parity test is the load-bearing piece — build it by invoking each function across the fixture matrix and collecting emitted statuses.

### Dependencies
RKIT-T-0113 (shapes settled first so the table describes the final surface).

### Risk Considerations
validateRenderedOutput returning unsupported is I-0032's implementation — the parity test must treat "specified for future" statuses distinctly (e.g. table marks it specified-not-yet-implemented) rather than failing green work or blessing the gap silently. Make that explicit and honest.

Recommended Agent: opus + medium

## Status Updates

*To be added during implementation*