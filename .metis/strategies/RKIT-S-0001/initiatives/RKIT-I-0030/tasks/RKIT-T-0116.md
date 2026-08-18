---
id: ats-safety-expansion-schema-driven
level: task
title: "ATS-safety expansion, schema-driven provenance stripping, skills de-hardcode, TEST_SPEC strengthening"
short_code: "RKIT-T-0116"
created_at: 2026-08-18T21:57:45.503363+00:00
updated_at: 2026-08-18T22:07:47.516047+00:00
parent: semantic-neutral-markdown-and-docx
blocked_by: [RKIT-T-0115]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0030
---

# ATS-safety expansion, schema-driven provenance stripping, skills de-hardcode, TEST_SPEC strengthening

## Parent Initiative

[[RKIT-I-0030]]

## Objective

Close initiative R4–R6: ATS-safety grows beyond the fixed 6-character deny list into render-time sanitation + validation-time structural checks; provenance stripping becomes schema-driven off the core-owned RenderableResume (strip everything NOT in the renderable schema); skills formatting is selected by template/section metadata instead of a hardcoded id.

## Acceptance Criteria

## Acceptance Criteria

- [ ] ATS check architecture (R4): render-time sanitation pass (character/encoding constraints per template — the old 6-char list at resume_render/__init__.py:29-36 becomes ONE rule among several) + validation-time structural checks: output encoding validation (artifact bytes decode as declared encoding), detection of ATS-hostile constructs the renderer could emit (tables `w:tbl`, text boxes `w:txbxContent`, fonts outside the template's declared families), and a template-breakage check (rendered headings match the template's `section_order`-derived expected set). Each check has a positive-detection test (violation caught by name) and a clean-pass test. NOTE: verdict/trust mechanics of validateRenderedOutput stay RKIT-I-0032's scope — these checks report findings through the existing result shapes; if the status table (T-0114) needs an implemented-marker flip for anything, do it honestly.
- [ ] Provenance stripping (R5): the key-name deny list (:70-72 area) replaced by schema-driven stripping — everything not in the core-owned RENDERABLE_RESUME_SCHEMA is stripped. Leak regression: provenance stored under `sources`/`evidence`/arbitrary keys is stripped; legitimate schema fields survive verbatim (regression pair).
- [ ] Skills formatting (R6): the hardcoded `section id == 'skills'` (:233-237 area) replaced by template/section metadata (e.g. a section `kind`/`format` field flowing from toRenderableResume or template metadata — coordinate with the shape landed in I-0029; do NOT invent a parallel mechanism). A renamed skills-like section formats correctly; a non-skills section never gets skills formatting (pair).
- [ ] resume-render/TEST_SPEC.md updated: ATS checks enumerated with covering tests; provenance stripping described as schema-driven; strengthen-only.
- [ ] Determinism preserved; snapshot regenerate ×2 no-drift if bytes change (summarize).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits. New tests bridged (check explicitly).

## Implementation Notes

### Technical Approach
Build on T-0115's layout metrics (declared font families feed the exotic-font check). Keep every check deterministic and stdlib-only. Findings ride existing warnings/errors shapes — no new statuses without updating the T-0114 status table honestly.

### Dependencies
RKIT-T-0115 (layout metrics, styles/numbering parts).

### Risk Considerations
Schema-driven stripping must not strip legitimate unknown-but-schema-valid content — the schema is the single arbiter; test both directions. The headings/template-breakage check must use the same section-title derivation the renderer uses, or it will false-positive on custom titles.

Recommended Agent: opus + medium

## Status Updates

- 2026-08-18: Implemented R4-R6. Added schema-driven renderable stripping in `resume_render`, render-time ATS character sanitation, validation-time DOCX encoding/structure/font/heading warning checks, and section `format` metadata from `resume_core.toRenderableResume` with schema/test coverage. Added renderer contract tests for each positive ATS finding by name plus clean pass, provenance leak/survival, and skills-format metadata behavior. Updated `resume-render/TEST_SPEC.md`; no fixture/snapshot diff. Focused renderer/core contract tests passed. Required gates passed: `python3 tools/run_gate.py --pr --root .` (623 tests), `python3 tools/run_gate.py --smoke --root .`, and `python3 tools/run_gate.py --future-contract --root .` (630 tests). Final Straight Jacket verification still shows only the expected `tools/resume_core_guardrails.py` mismatch.
