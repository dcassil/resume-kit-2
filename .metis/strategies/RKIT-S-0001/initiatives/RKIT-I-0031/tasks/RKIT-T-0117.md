---
id: template-grounded-capacity-model
level: task
title: "Template-grounded capacity model, per-section overflow constraints, metrics-version report"
short_code: "RKIT-T-0117"
created_at: 2026-08-18T22:22:23.296181+00:00
updated_at: 2026-08-18T22:23:04.893543+00:00
parent: resume-render-layout-measurement
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0031
---

# Template-grounded capacity model, per-section overflow constraints, metrics-version report

## Parent Initiative

[[RKIT-I-0031]]

## Objective

Replace `measureLayout`'s fixed 45-line/90-char markdown heuristic with a capacity model derived from the I-0030 layout-metrics.v1 template block (page geometry, fonts, spacing, bullet indents, versioned glyph-width table), keep `required_reduction` as the character count consistent with that same model, itemize per-section overflow contributions, and stamp the metrics version into the report — the actionable, reconstructable constraint product I-0027/0039's loop-back consumes.

## Acceptance Criteria

## Acceptance Criteria

- [ ] FIRST verify current state: I-0027 already realigned `required_reduction` to character count and T-0114 pinned the unit. Do NOT regress the existing unit tests; the remaining audit gaps are the constant heuristic (R1), per-section itemization (R3), and metrics-version stamping (R6). Report already-satisfied vs new.
- [ ] Capacity model (R1) in a private module (e.g. `resume_render/_layout.py`): usable height = page height − vertical margins; lines_per_page = usable_height / (body size_pt × line spacing); chars_per_line = usable width / average glyph width from a SMALL DOCUMENTED VERSIONED per-font-family width table (explicit data constant, not hidden numbers); headings/bullets weighted by their own metrics (heading size + para_after, bullet indent narrowing the line). Consumes the layout-metrics.v1 block from I-0030 (defaults when template silent). The fixed 45/90 constants are DELETED grep-proof.
- [ ] Two templates with different layout metrics yield DIFFERENT estimates for the same content (the assertion the constant heuristic can never pass); a metrics change that increases capacity reduces estimated_pages for fixed content (directional sanity test).
- [ ] `required_reduction` (R2): integer character count beyond the capacity of target_pages, computed FROM THE SAME model (consistency assertion: rendering content reduced by exactly required_reduction characters fits, at value level on a boundary fixture). Exact-fit fixture → fits true, required_reduction 0. Known-excess fixture → value-level equality.
- [ ] Per-section constraints (R3): `constraints.per_section = [{id, estimated_lines, overflow_chars}]` — the overflowing section(s) named with non-zero overflow_chars; non-contributing sections zero. `constraints.metrics_version` carries the layout-metrics + glyph-table version (R6).
- [ ] R4/R5 preserved: deterministic byte-identical repeat reports; typed errors on invalid target_pages unchanged; measureLayout never mutates/truncates content (existing tests stay green or strengthened).
- [ ] Workflow consumers keep working: I-0027's render-overflow loop-back reads this report — run its tests and the full gates; if the report shape gains keys, additive only (no renames), and update the T-0114 status table only if statuses change (they should not).
- [ ] resume-render/TEST_SPEC.md: unit assertions named; the "overflow routes back to selection/rewrite" case RESPECIFIED out of renderer unit scope to cross-package E2E (owned by I-0034 with 0027/0039) — honest wording, strengthen-only.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits; new tests bridged (state where). Snapshot regenerate ×2 no-drift if fixture reports shift (summarize).

## Implementation Notes

### Technical Approach
Keep everything integer/deterministic (avoid float accumulation drift — round at documented points). The glyph-width table is approximation data with a version string; document its provenance in the module docstring. Measure the RenderableResume-shaped content (post I-0029), not raw markdown text.

### Dependencies
I-0030 layout-metrics.v1 (landed), I-0029 DTO semantics (landed).

### Risk Considerations
Workflow's recovery/overflow tests consume measureLayout output (I-0027) — run tests/contract/test_workflow_contract.py early. Additive-only report changes.

Recommended Agent: opus + high

## Status Updates

### 2026-08-18 implementation checkpoint
- Read RKIT-T-0117 and RKIT-I-0031 before code changes.
- Straight Jacket list/verify run; only mismatch is the expected authorized tools/resume_core_guardrails.py checksum change. Protected tools/ and tests/boundary/ remain read-only for this task.
- Verified current state: existing renderer/workflow tests already pin requiredReduction as an integer character count; remaining renderer gaps are the fixed layout heuristic, per-section overflow report, and metrics-version stamping.
- Ran early workflow consumer check with unittest: `PYTHONPATH=resume-core:career-store:career-mcp:resume-agent:resume-cli:resume-plugin:resume-render:. python3 -m unittest tests.contract.test_workflow_contract` passed 63 tests.
- Implemented private resume_render._layout capacity model, wired measureLayout additively, updated renderer spec/manifest, and added contract tests in tests.contract.test_resume_render_contract.
- Local renderer/workflow checks passed after changes: renderer contract 34 tests OK; workflow contract 63 tests OK; _layout.py and __init__.py compile.
- Grep check across resume-render and renderer contract tests found no old 45-line/90-char heuristic patterns.
- PR gate passed: `python3 tools/run_gate.py --pr --root .` ran 627 tests OK.
- Smoke gate passed: `python3 tools/run_gate.py --smoke --root .` completed installed-package smoke successfully.
- Future-contract gate passed: `python3 tools/run_gate.py --future-contract --root .` ran 634 tests OK.
- Final Straight Jacket verify still reports only the expected authorized `tools/resume_core_guardrails.py` mismatch; no protected task edits were made.
- Complete: implementation and verification finished; final response should report already-satisfied vs new, criterion-to-test mapping, grep proof, and no snapshot regeneration needed.