---
id: resume-render-layout-measurement
level: initiative
title: "Resume-Render Layout Measurement and Overflow Constraint Reporting"
short_code: "RKIT-I-0031"
created_at: 2026-08-13T20:41:37.632529+00:00
updated_at: 2026-08-18T22:37:39.214689+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0030]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-render-layout-measurement
---

# Resume-Render Layout Measurement and Overflow Constraint Reporting Initiative

## Context **[REQUIRED]**

Package: `resume-render`. `measureLayout` already exists and is deterministic: it returns fits/overflow with `estimated_pages`, `target_pages`, `required_reduction`, and a constraints block, and raises typed errors on invalid `target_pages`. The gap is fidelity, unit semantics, and consumption — not existence:

- **The measurement is a hardcoded heuristic.** A fixed 45 lines/page and 90-character wrap regardless of template, measuring markdown text rather than the rendered format (`resume_render/__init__.py:400-407`). It cannot reflect template metrics because fonts/spacing/margins did not exist until RKIT-I-0030 defines them.
- **`required_reduction` is a page-count delta** (`__init__.py:406-413`), while the section 9 contract example (`requiredReduction: 480`, `PRODUCT_VISION_AND_CONTRACTS.md:680-691`) is a fine-grained quantity selection/rewrite can act on. RKIT-A-0006 item 7 decides this: character count.
- **Nothing in the repo calls `measureLayout`.** resume-cli imports only renderMarkdown/renderDocx/validateRenderedOutput (`resume-cli/resume_cli/__init__.py:16`), so the overflow contract ("Rendering overflow returns constraints to orchestration", `CONTRACT_SURFACE_ALIGNMENT.md:283`) is dead code at product level. The loop-back into orchestration is wired by RKIT-I-0027/0039 — cross-referenced here, not owned.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Page estimation is grounded in the target rendered format via the template layout metrics from RKIT-I-0030 (fonts, spacing, margins, bullet indents) — per-template capacity, not universal constants.
- `required_reduction` is implemented as the character count that must be removed to fit `target_pages`, per RKIT-A-0006 item 7, using the DTO semantics fixed in RKIT-I-0029.
- Overflow constraints are actionable: they name the overflow quantity and the sections contributing to it, so selection/rewrite can target reductions without the renderer choosing what to cut.
- The constraint report is a consumable product for RKIT-I-0027/0039's orchestration loop-back.

**Non-Goals:**
- Orchestration/routing of overflow back into selection/rewrite — owned by workflow/resume-cli and wired by RKIT-I-0027/0039 per CONTRACT_SURFACE_ALIGNMENT.md; this initiative only produces the report they consume.
- Template metrics definition — RKIT-I-0030.
- Smoke/E2E proof that overflow is exercised — RKIT-I-0034.
- Any truncation or content mutation — forbidden by the Render Gate, always.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1. Replace the fixed 45-line/90-char markdown heuristic (`__init__.py:400-407`): lines-per-page and characters-per-line are derived from the template's layout metrics (page size minus margins, body font size, line spacing, bullet indents) for the target format, per template — two templates with different metrics must yield different estimates for the same content.
- R2. `required_reduction` returns the integer character count needed to fit `target_pages` (RKIT-A-0006 item 7; `PRODUCT_VISION_AND_CONTRACTS.md:680-691`), replacing the page delta at `__init__.py:406-413`.
- R3. The constraints block itemizes per-section contribution to the overflow so downstream selection can act on it.
- R4. Determinism: same resume plus template yields an identical layout report; typed errors on invalid `target_pages` are preserved.
- R5. `measureLayout` never mutates or truncates content — it satisfies the Render Gate rule "renderer reports overflow instead of deleting content".
- R6. The report includes the template/metrics version used, so audit manifests (RKIT-I-0034) can reconstruct how the estimate was produced.

### Dependencies
- RKIT-I-0030: the template layout metrics this measurement model consumes.
- RKIT-I-0029 fixed the constraint DTO unit semantics this initiative implements.
- Consumer cross-reference: RKIT-I-0027/0039 wire the overflow loop-back in workflow/resume-cli; RKIT-I-0034 proves it in smoke/E2E.

### Blocked Status
- Yes: RKIT-I-0030 (frontmatter `blocked_by: ["RKIT-I-0030"]`). No ADR blockers — RKIT-A-0006 is decided and settles the unit question.

## Status Updates

- 2026-08-18: COMPLETE (single task T-0117, 3703add). Capacity model in resume_render/_layout.py from layout-metrics.v1 + versioned glyph-widths.v1 table (45/90 constants deleted grep-proof); required_reduction char count from the same model (value-level boundary fixtures); per_section [{id, estimated_lines, overflow_chars}] + metrics_version; template-metric discrimination tests; workflow I-0027 consumers green. DRIVER FIX: object-shaped canonical bullets were silently deleted by the renderer's schema strip (schema declares scalar bullet text; derivation emitted {id,text}) — bullets now flatten to text in toRenderableResume, with an end-to-end regression covering render AND measurement (the prior E2E used string bullets only). Zero protected edits; gates PR 629 / future 636 / smoke green; version 0.30.0.

## Detailed Design **[REQUIRED]**

**Capacity model.** For the DOCX target: usable page height = page height minus vertical margins; lines-per-page = usable height / (body size × line spacing); characters-per-line = usable width / average glyph width, taken from a small documented per-font-family width table shipped with the templates (stdlib has no font metrics, so the approximation table is explicit, versioned data — not hidden constants). Headings and bullets consume lines weighted by their own metrics (heading size, spacing-after, bullet indent narrowing the line).

**Estimation.** Content is laid out section by section against the capacity model: `estimated_pages = ceil(total_line_units / lines_per_page)`. `required_reduction` = the number of characters beyond the capacity of `target_pages`, computed from the same model, so the value is consistent with the estimate that triggered it.

**Constraint report.** Per RKIT-I-0029's DTO: `{fits, estimated_pages, target_pages, required_reduction, constraints: {per_section: [{id, estimated_lines, overflow_chars}], metrics_version}}`. Honesty note: this remains an estimate, but a template-grounded, reconstructable one — a categorical improvement over constants that ignore the template entirely.

**Migration.** No callers of `measureLayout` exist yet (`resume-cli/resume_cli/__init__.py:16` imports three functions only), so the unit change is safe to make now — one more reason this work must not wait behind additional serialization.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Boundary fixtures: content that exactly fits `target_pages` (fits: true, required_reduction: 0); content overflowing by a known character excess (value-level assertion that `required_reduction` equals it); the same content under two templates with different metrics producing different estimates — the assertion the constant heuristic can never pass.
- Determinism test: repeated measurement of the same input is byte-identical.
- Per-section constraint test: the section responsible for overflow is named with a non-zero `overflow_chars`.
- TEST_SPEC strengthening this initiative owns (audit-flagged): with the character-unit wording pinned by RKIT-I-0029, add the value-level unit assertions here; and respecify the case "Ensure overflow routes back to selection/rewrite workflow" out of renderer unit scope — it is cross-package behavior owned by workflow/resume-cli and is proven in E2E (RKIT-I-0034 with 0027/0039), not by a package test the renderer cannot own.
- Boundary guardrails stay green; no assertion weakened (RKIT-A-0006).

## Alternatives Considered **[REQUIRED]**

- **Keep the text heuristic with per-template calibrated constants.** Rejected: constants cannot respond to font/spacing/margin changes and keep measuring markdown as a proxy for DOCX pages — the exact fixture-tuned shape the audit flagged.
- **Parse the produced DOCX for a page count.** Rejected: OOXML stores no pagination — page breaks are a layout-engine artifact — so the bytes cannot answer the question without a rendering engine.
- **Adopt a layout engine (LibreOffice or a DOCX renderer) for exact pagination.** Rejected: violates the no-new-dependency MVP posture (RKIT-A-0004 item 3) for precision the selection loop does not need; the loop needs an actionable, consistent reduction quantity, not typographic exactness.

## Implementation Plan **[REQUIRED]**

1. Build the metrics-derived capacity model (consumes RKIT-I-0030's template layout metrics and glyph-width table).
2. Implement character-based `required_reduction` and per-section constraints on RKIT-I-0029's DTO.
3. Add the boundary fixture suite and determinism tests with value-level unit assertions.
4. Apply the TEST_SPEC respecification (unit assertions in; cross-package routing case moved to E2E scope) and run the canonical package gate.