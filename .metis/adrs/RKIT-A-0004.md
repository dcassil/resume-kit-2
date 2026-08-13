---
id: 001-pdf-rendering-support-policy-and
level: adr
title: "PDF Rendering Support Policy and Runtime"
number: 1
short_code: "RKIT-A-0004"
created_at: 2026-08-13T20:41:36.790129+00:00
updated_at: 2026-08-13T20:41:36.790129+00:00
decision_date: 
decision_maker: 
parent: 
archived: false

tags:
  - "#adr"
  - "#phase/draft"
  - "#adr"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# PDF Rendering Support Policy and Runtime

## Context **[REQUIRED]**

resume-render exposes renderPdf, but product docs allow PDF only where supported and do not select a runtime or release policy. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

Pending. Resolve the open questions below before decomposing blocked initiatives into tasks or implementing runtime-specific behavior.

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Risk Level | Implementation Cost |
|--------|------|------|------------|---------------------|
| Minimal local contract | Keeps first build small and testable | May require later migration | Medium | Low |
| Full production runtime now | Clarifies packaging and acceptance early | Higher design/dependency risk | Medium | Medium |
| Defer capability | Avoids premature assumptions | Leaves listed initiatives blocked | Low | Low |

## Rationale **[REQUIRED]**

The available docs establish boundaries and invariants, but not this concrete product/runtime decision. Capturing it as an ADR prevents hidden assumptions from leaking into implementation tasks.

## Consequences **[REQUIRED]**

### Positive
- Blocked scope is explicit before task decomposition.
- Unblocked hardening initiatives can still proceed.

### Negative
- Some initiatives cannot be decomposed until this ADR is resolved.

### Neutral
- Revisit this ADR when planning the blocked initiatives.

## Open Questions

- Is PDF a release target or best-effort after Markdown and DOCX?
- Which runtime is allowed: DOCX-to-PDF, HTML/CSS-to-PDF, ReportLab, LibreOffice, browser print, or explicit unsupported?
- Must the runtime work in clean local installs, CI, plugin hosts, and CLI contexts?
- What PDF text-extraction validator is acceptable for parse-back?
- Are new Python or system dependencies allowed?

## Blocks

- Production PDF Rendering and Parse-Back Validation
