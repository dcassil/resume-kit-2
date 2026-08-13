---
id: 001-pdf-rendering-support-policy-and
level: adr
title: "PDF Rendering Support Policy and Runtime"
number: 1
short_code: "RKIT-A-0004"
created_at: 2026-08-13T20:41:36.790129+00:00
updated_at: 2026-08-13T21:40:49.650778+00:00
decision_date: 2026-08-13
decision_maker: Daniel Cassil
parent: 
archived: false

tags:
  - "#adr"
  - "#adr"
  - "#phase/decided"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# PDF Rendering Support Policy and Runtime

## Context **[REQUIRED]**

resume-render exposes renderPdf, but product docs allow PDF only where supported and do not select a runtime or release policy. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

1. **PDF is not an MVP release target.** The release Render Gate remains Markdown + DOCX, as the product contracts already state.
2. **Honest unsupported status now.** `renderPdf` must report status `unsupported` (with a reason) instead of fabricating an `ok` text artifact labeled `application/pdf`. This fix is authorized immediately — it requires no runtime decision and no dependency, and it repairs an active honesty-gate violation. A template missing `format_targets` must also yield `unsupported`, not permissive `ok`.
3. **No new Python or system dependencies for PDF in MVP.**
4. **Future runtime candidate.** When PDF becomes a release target, the default candidate is a pure-Python renderer (fpdf2 or ReportLab) with pypdf-based parse-back, selected by amending or superseding this ADR after verifying clean-install, CI, and plugin-host operation.
5. **Initiative impact.** RKIT-I-0033 rescopes to the unsupported-policy behavior and its tests; RKIT-I-0034 (Markdown/DOCX gate integration, fixtures, audit evidence) does not depend on PDF and must not be serialized behind it.

Decided 2026-08-13 by Daniel Cassil (MVP scope ratified in session; policy derived from the documented Markdown+DOCX release target).

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Outcome |
|--------|------|------|---------|
| Defer PDF; report `unsupported` honestly | Matches the documented Markdown+DOCX release target; zero dependencies; immediately repairs the fake-'ok' honesty violation | No PDF artifact in MVP | **Chosen** |
| Pure-Python PDF now (fpdf2/ReportLab + pypdf parse-back) | Real PDFs; parse-back feasible | First third-party runtime dependency in an otherwise stdlib-only repo; the section 9 layout/typography substrate (fonts, spacing, templates) does not exist yet, so output would be low-fidelity | Deferred — named default future candidate |
| DOCX→PDF via LibreOffice | Highest fidelity by reusing the DOCX path | Heavyweight external binary; environment detection burden in CI and plugin hosts | Rejected for MVP |
| HTML/CSS-to-PDF or browser print | Good typography control | Requires a new HTML render path plus a headless-browser dependency | Rejected for MVP |

## Rationale **[REQUIRED]**

The release gate is already defined as Markdown + DOCX; nothing in the DoD requires PDF. The only urgent PDF problem is the dishonest stub — `renderPdf` returning `ok` with markdown text labeled `application/pdf` — which is a policy fix, not a runtime choice, and the `unsupported` status already exists in `render_surface.json` for exactly this purpose. Choosing a real runtime before the layout/typography substrate exists would lock in a low-fidelity path prematurely.

## Consequences **[REQUIRED]**

### Positive
- The active honesty violation (fake-'ok' PDF) has an authorized, dependency-free fix.
- RKIT-I-0033 rescopes small and decomposable; RKIT-I-0034's Markdown/DOCX gate work is explicitly unserialized from PDF.
- The repo stays stdlib-only for MVP.

### Negative
- No PDF artifact in MVP; users needing PDF must convert the DOCX externally for now.

### Neutral
- The future pure-Python candidate depends on the section 9 layout/typography substrate (fonts, spacing, templates) existing first; revisit when that lands.

## Resolved Questions

- Release target or best-effort → not a release target for MVP; Markdown + DOCX remain the gate.
- Which runtime allowed → explicit `unsupported` for MVP; future default candidate is fpdf2/ReportLab with pypdf parse-back, adopted via ADR amendment.
- Must the runtime work in clean installs/CI/plugin hosts → yes — a binding requirement on whatever future runtime is chosen; part of the revisit criteria.
- Acceptable parse-back validator → pypdf (future candidate); none needed while unsupported.
- New dependencies allowed → none for MVP.

## Blocks

- RKIT-I-0033 Production PDF Rendering and Parse-Back Validation — lifted (decided; rescoped to unsupported-policy behavior and tests)
- Transitive: RKIT-I-0034 — never PDF-dependent; explicitly unserialized by this decision