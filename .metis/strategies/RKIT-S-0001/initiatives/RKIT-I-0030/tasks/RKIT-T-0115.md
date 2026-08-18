---
id: ooxml-depth-styles-xml-numbering
level: task
title: "OOXML depth: styles.xml, numbering part, real bullet lists, template layout metrics driving DOCX"
short_code: "RKIT-T-0115"
created_at: 2026-08-18T21:57:45.433704+00:00
updated_at: 2026-08-18T21:58:54.011654+00:00
parent: semantic-neutral-markdown-and-docx
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0030
---

# OOXML depth: styles.xml, numbering part, real bullet lists, template layout metrics driving DOCX

## Parent Initiative

[[RKIT-I-0030]]

## Objective

Give DOCX artifacts real word-processing structure (initiative R1–R3, R7): a `word/numbering.xml` part with bullets rendered as genuine list items, a generated `word/styles.xml` defining EVERY referenced style, and a versioned template `layout` metrics block (fonts/spacing/margins/bullet style) that drives DOCX generation — the section 9 typography substrate RKIT-I-0031 will measure against. Stdlib-only (RKIT-A-0004 item 3: no python-docx).

## Acceptance Criteria

## Acceptance Criteria

- [ ] `word/numbering.xml` part: one abstract numbering definition + a bullet-list instance; bullet paragraphs reference it via `w:numPr` + ListParagraph style (the flattening at resume_render/__init__.py:288-292 area is gone); `[Content_Types].xml` and document relationships gain matching entries. Contract test UNZIPS the artifact and asserts structurally (numbering part exists, bullet paragraphs carry w:numPr, relationships/content-types entries present) — no text-containment shortcuts.
- [ ] Generated `word/styles.xml` defines every styleId the document references (Title, Heading1/Heading2, body, ListParagraph); contract test collects referenced styleIds from document.xml and asserts each is defined — zero undefined references (closes :295-313).
- [ ] Template `layout` block per the initiative Detailed Design: `{fonts: {body: {family, size_pt}, heading: {family, size_pt}}, spacing: {line, para_after_pt}, margins_in: {top,bottom,left,right}, bullet: {style, indent_in}}` with documented defaults and a layout-metrics VERSION (for I-0031 reports/audit manifests). Unknown layout keys → typed validation error (no silent tolerance). DOCX maps metrics to w:rPr/w:pPr/w:sectPr (page size/margins stop being hardcoded); Markdown treats layout as typographic no-op.
- [ ] Metric-mapping tests: a template's font size, margins, and bullet indent appear at the expected XML locations (value-level XML assertions); two templates with different metrics produce different bytes for the same resume; template WITHOUT a layout block uses documented defaults producing today's-equivalent sane output.
- [ ] Determinism (R7): same input+template → byte-identical artifact + stable fingerprint; determinism tests re-baselined alongside the byte change in the SAME commit (fixture truth untouched — only bytes/fingerprints regenerate; snapshot regenerate ×2 no-drift; summarize per-snapshot changes).
- [ ] Semantic neutrality preserved: no added/rewritten/reordered claims — existing neutrality tests stay green unmodified.
- [ ] resume-render/TEST_SPEC.md: "bullets preserved" REWRITTEN to require list formatting in the DOCX XML (w:numPr), not text containment — the audit-flagged looseness that certified flattened bullets. Strengthen-only.
- [ ] render_surface.json template contract extended for the layout block if templates are schema-pinned there (check first; also check the T-0114 status table needs no touch). Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits (if resume_render_guardrails pins template keys or DOCX structure, STOP and defer verbatim).

## Implementation Notes

### Technical Approach
Stay in the existing stdlib zip/XML generation path — the gap is missing parts, not a framework. Put OOXML part builders in a new private module (e.g. resume_render/_ooxml.py) if __init__.py is getting long. Validate the output opens in a real word processor mentally via spec-correct XML (w:abstractNum/w:num, w:styles w:style/@w:styleId, w:sectPr w:pgMar).

### Dependencies
I-0029's RenderableResume + template contract (landed).

### Risk Considerations
Byte changes ripple to any fixture fingerprints — regenerate once in the same change. DOCX parse-back (validateRenderedOutput) may read document.xml text; make sure list items still parse back (I-0032 owns trust mechanics but don't break current parse-back tests).

Recommended Agent: opus + high

## Status Updates

- 2026-08-18: Read task + initiative first. Straight Jacket pre-check reports the expected single protected mismatch in `tools/resume_core_guardrails.py`; `tools/resume_render_guardrails.py` does not pin template layout keys or DOCX internals, and the T-0114 status table only pins public status rows. Added stdlib-only private OOXML builder draft (`resume_render/_ooxml.py`), wired DOCX rendering to generated styles/numbering parts with deterministic zip entries, and added contract tests in `tests/contract/test_resume_render_contract.py` for numbering, styles, metric mapping, layout validation, and byte determinism.
- 2026-08-18: Focused renderer contract tests passed (`python3 -m unittest tests.contract.test_resume_render_contract -v`). Resume-render guardrails passed. Required gates passed: `python3 tools/run_gate.py --pr --root .` (612 tests), `python3 tools/run_gate.py --smoke --root .`, and `python3 tools/run_gate.py --future-contract --root .` (619 tests). `fixtures/expected/` has no diff, so no snapshot rebaseline was needed; determinism/fingerprint coverage is in the renderer contract test. Final Straight Jacket verification still shows only the expected `tools/resume_core_guardrails.py` mismatch.
