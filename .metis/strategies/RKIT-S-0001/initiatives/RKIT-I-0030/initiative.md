---
id: semantic-neutral-markdown-and-docx
level: initiative
title: "Semantic-Neutral Markdown and DOCX Rendering"
short_code: "RKIT-I-0030"
created_at: 2026-08-13T20:41:37.601397+00:00
updated_at: 2026-08-13T20:41:37.601397+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0029"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Semantic-Neutral Markdown and DOCX Rendering Initiative

## Context **[REQUIRED]**

Package: `resume-render`. The outcome this initiative originally planned is largely shipped and runtime-verified: Markdown rendering, minimal-but-genuine DOCX output (a real zip with document.xml), semantic neutrality (no added/rewritten/reordered claims), template-driven section ordering, nested provenance stripping, and deterministic artifact fingerprints all work. The re-baseline rescopes this initiative to the real remaining gaps:

- **DOCX bullets lose their list formatting entirely.** Bullet markers are stripped and emitted as plain unmarked paragraphs; there is no numbering part (`resume_render/__init__.py:288-292`).
- **Referenced styles are undefined.** The generated document references `Heading2`/`Title` styles that have no `styles.xml` definition, and page size/margins are fixed (`__init__.py:295-313`).
- **The vision section 9 layout-template responsibility has no owner.** Templates today support only `template_version`, `section_order`, `format_targets`, and `target_pages` — no fonts, spacing, margins, or bullet styles exist anywhere in the repo. This re-baseline explicitly assigns the section 9 responsibilities "Layout templates" and "Font/spacing/bullet rendering" to this initiative.
- **Renderer ATS checks are a fixed 6-character deny list** (smart quotes, bullet char, NBSP — `__init__.py:29-36`, applied at `568-572`) with no encoding, font, table, or template-breakage detection.
- Secondary hardening: provenance stripping is a key-name heuristic that would leak provenance stored under other keys such as `sources` or `evidence` (`__init__.py:70-72`), and skills formatting is hardcoded to `section id == 'skills'` (`__init__.py:233-237`).

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- DOCX artifacts carry real word-processing structure: a numbering part for bullets and a `styles.xml` defining every referenced style.
- A template layout-metrics schema (fonts, spacing, margins, bullet styles) exists, is owned here per vision section 9, and drives DOCX generation — becoming the substrate RKIT-I-0031 measures against and any future PDF runtime (RKIT-A-0004 item 4) requires.
- Renderer ATS-safety checks go beyond the fixed 6-character list.
- Provenance stripping and skills formatting are schema/template-driven, not name heuristics.

**Non-Goals:**
- Layout measurement and overflow constraints — RKIT-I-0031 (it consumes the metrics defined here).
- Parse-back trust model and validation verdicts — RKIT-I-0032.
- PDF in any form — deferred per RKIT-A-0004; policy honesty is RKIT-I-0033.
- Smoke/E2E/fixture/audit-evidence work — RKIT-I-0034.
- Renderer-input DTO ownership — RKIT-I-0029 (this initiative builds on its `RenderableResume`).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1. DOCX bullets render as real Word list items: a `word/numbering.xml` part, list paragraph style, and correct relationships/content-types entries; fixes the flattening at `__init__.py:288-292`. Satisfies section 9 "Font/spacing/bullet rendering".
- R2. A generated `styles.xml` defines every style the document references (Title, headings, body, list); no undefined style references remain (`__init__.py:295-313`).
- R3. The template schema is extended with layout metrics: fonts (family/size for body and headings), spacing (line height, before/after paragraph), page margins, and bullet style/indent, with documented defaults; DOCX generation consumes them (page size/margins stop being hardcoded).
- R4. ATS-safety expands beyond the 6-character deny list (`__init__.py:29-36`): output encoding validation, detection of ATS-hostile constructs the renderer could emit (tables, text boxes, exotic fonts), and a template-breakage check that rendered headings match the expected section set. Verdict/trust mechanics of `validateRenderedOutput` remain RKIT-I-0032's scope.
- R5. Provenance stripping is driven by the core-owned `RenderableResume` schema from RKIT-I-0029 — strip everything not in the renderable schema — replacing the key-name deny list (`__init__.py:70-72`).
- R6. Skills-section formatting is selected by template/section metadata, not a hardcoded id (`__init__.py:233-237`).
- R7. Determinism preserved: same input plus template yields byte-identical artifacts and stable fingerprints.

### Dependencies
- RKIT-I-0029: the `RenderableResume` DTO and template contract this rendering work consumes.
- RKIT-A-0004 (decided) keeps this initiative Markdown+DOCX only; RKIT-A-0006 (decided) governs any contract-test edits.

### Blocked Status
- Yes: RKIT-I-0029 (frontmatter `blocked_by: ["RKIT-I-0029"]`). No ADR blockers — both relevant ADRs are decided.

## Detailed Design **[REQUIRED]**

**OOXML parts.** Add `word/styles.xml` (style definitions for Title, Heading1/Heading2, body text, and a ListParagraph style) and `word/numbering.xml` (one abstract numbering definition plus an instance for bullet lists), with matching entries in `[Content_Types].xml` and the document relationships. Bullet paragraphs reference the numbering instance via `w:numPr` instead of being emitted as bare paragraphs.

**Template layout metrics.** Extend templates with a `layout` block, e.g. `{fonts: {body: {family, size_pt}, heading: {family, size_pt}}, spacing: {line, para_after_pt}, margins_in: {top, bottom, left, right}, bullet: {style, indent_in}}`. DOCX maps these to `w:rPr`/`w:pPr`/`w:sectPr` values; the Markdown target treats them as typographic no-ops (ordering only). Metrics carry a version so layout reports and audit manifests can reference them.

**ATS check architecture.** A render-time sanitation pass (character/encoding constraints per template) plus validation-time structural checks (no tables/text boxes, headings match `section_order`). The deny list becomes one rule among several, not the whole check.

**Migration.** DOCX bytes change, so fixture fingerprints regenerate once in the same change that alters generation — truth content untouched, determinism tests re-baselined, per the RKIT-A-0006 strengthen-only rule.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract tests that unzip the produced DOCX and assert: the numbering part exists, bullet paragraphs reference it, and every referenced styleId is defined in `styles.xml` — structural assertions on bytes, not text containment.
- Metric-mapping tests: a template's font size, margins, and bullet indent appear at the expected XML locations; two templates with different metrics produce different bytes for the same resume.
- ATS tests: encoding violations, table/text-box emission, and heading/template mismatch are each detected.
- Provenance leak test: provenance stored under `sources`/`evidence` keys is still stripped (closes `__init__.py:70-72`).
- TEST_SPEC strengthening this initiative owns: "bullets preserved" must require list formatting in the DOCX XML rather than mere text containment — the looseness that certified flattened bullets.
- Determinism/fingerprint tests re-baselined alongside the byte changes; boundary guardrails stay green.

## Alternatives Considered **[REQUIRED]**

- **Adopt python-docx for generation.** Rejected: RKIT-A-0004 item 3 keeps MVP free of new dependencies, and the existing stdlib zip/XML path already produces valid DOCX — the gap is missing parts, not a generation framework.
- **Keep flattened bullets and rely on ATS parsers' leniency.** Rejected: violates the section 9 bullet-rendering responsibility, loses list structure on parse-back, and makes the RKIT-I-0032 semantic comparison weaker for list content.
- **Split typography into a new templates package.** Rejected: rendering (including typography) is resume-render's responsibility in the CONTRACT_SURFACE_ALIGNMENT.md ownership table; a new package adds a boundary with no owner benefit.

## Implementation Plan **[REQUIRED]**

1. Define the template layout-metrics schema and defaults (coordinating with RKIT-I-0029's template contract).
2. Generate `styles.xml` and wire referenced styles to definitions.
3. Add the numbering part and render bullets as real list items.
4. Expand ATS-safety checks (render-time sanitation plus structural checks).
5. Harden provenance stripping (schema-driven) and de-hardcode skills formatting.
6. Regenerate fixtures/fingerprints, apply the TEST_SPEC strengthening, and run the canonical package gate.
