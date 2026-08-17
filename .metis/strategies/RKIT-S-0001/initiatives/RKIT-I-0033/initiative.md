---
id: pdf-support-policy-honest
level: initiative
title: "PDF Support Policy: Honest Unsupported Status (Runtime Deferred per RKIT-A-0004)"
short_code: "RKIT-I-0033"
created_at: 2026-08-13T20:41:37.697247+00:00
updated_at: 2026-08-17T20:05:36.427258+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: S
strategy_id: RKIT-S-0001
initiative_id: pdf-support-policy-honest
---

# PDF Support Policy: Honest Unsupported Status (Runtime Deferred per RKIT-A-0004)

## Context **[REQUIRED]**

Package: `resume-render`. RKIT-A-0004 is decided (2026-08-13): PDF is not an MVP release target; the release Render Gate remains Markdown + DOCX; no new dependencies for PDF in MVP; the future runtime candidate (fpdf2/ReportLab with pypdf parse-back) will be adopted by amending or superseding that ADR once the section 9 layout/typography substrate exists. This initiative is therefore RESCOPED per RKIT-A-0004 item 5 from "production PDF rendering" to the honest unsupported policy — and re-sized S.

Current state, verified by the audit: `renderPdf` is a fake-PDF stub. It returns status `ok` with an artifact `{kind: pdf, media_type: application/pdf, text: <markdown>}` and no PDF bytes (`resume_render/__init__.py:363-381`, fabrication at `372-381`), and it is default-permissive — reporting `ok` when the template omits `format_targets` instead of `unsupported`. This is an active honesty-gate violation: the `unsupported` status exists in `render_surface.json:156-160` for exactly this case and is never used. RKIT-A-0004 item 2 authorizes the fix immediately — no runtime decision, no dependency. The former ADR block is lifted.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- `renderPdf` reports status `unsupported` with a machine-readable reason and never fabricates an artifact — including when the template omits `format_targets`.
- Policy contract tests pin every unsupported path so the fake-`ok` stub can never return.
- The Markdown+DOCX release target is provably unaffected by PDF being unsupported.

**Non-Goals:**
- No PDF runtime selection and no PDF bytes — that is a future ADR amendment per RKIT-A-0004 item 4, gated on the RKIT-I-0030 layout substrate existing.
- No PDF parse-back validator — none is needed while unsupported (RKIT-A-0004 resolved question); `validateRenderedOutput`'s handling of pdf-kind artifacts (`unsupported`) is RKIT-I-0032's implementation.
- No gate/fixture/audit work — RKIT-I-0034, which RKIT-A-0004 item 5 explicitly unserializes from this initiative.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1. `renderPdf` returns `{status: "unsupported", reason}` and no artifact; it never emits `ok` without actual PDF bytes and never labels non-PDF content `application/pdf` (fixes `__init__.py:363-381`; RKIT-A-0004 item 2).
- R2. A template omitting `format_targets` yields `unsupported` with reason `format_targets_missing`, replacing the default-permissive `ok` (RKIT-A-0004 item 2).
- R3. A template whose `format_targets` excludes `pdf` yields `unsupported` with reason `not_in_format_targets`; a template including `pdf` still yields `unsupported` under MVP policy with reason `pdf_not_supported_in_mvp`.
- R4. No new Python or system dependencies (RKIT-A-0004 item 3).
- R5. Release targets unaffected: Markdown/DOCX gates pass while renderPdf reports unsupported — implementing TEST_SPEC's "Report PDF as unsupported without failing non-PDF release targets".
- R6. `render_surface.json`/TEST_SPEC define "producing" a PDF as emitting actual PDF bytes, closing the audit-flagged looseness that let a status-`ok` no-bytes artifact pass.

### Dependencies
- RKIT-A-0004 (decided) — input, not blocker; this initiative implements its item 2 and inherits its items 3-5.
- RKIT-I-0029 specifies the status vocabulary this behavior uses; coordination only, since the reason enumeration can land with this initiative.
- RKIT-I-0032 coordination: pdf-kind artifacts in validateRenderedOutput return `unsupported` under the same policy.

### Blocked Status
- No. `blocked_by: []` — the ADR block is lifted (RKIT-A-0004 decided 2026-08-13).

## Detailed Design **[REQUIRED]**

**Result shape.** `{status: "unsupported", reason, format: "pdf", template_version}` with no `artifact` key fabricated. The `reason` vocabulary (`format_targets_missing`, `not_in_format_targets`, `pdf_not_supported_in_mvp`) is enumerated in `render_surface.json` so callers can branch on it deterministically.

**Decision order.** (1) Template missing `format_targets` → `format_targets_missing`. (2) `pdf` absent from `format_targets` → `not_in_format_targets`. (3) Otherwise → `pdf_not_supported_in_mvp`. The order makes template defects distinguishable from policy, which matters for CLI messaging and for the future runtime: when a PDF runtime ADR amendment lands, only branch (3) is replaced — the policy layer in front of real rendering survives.

**Caller behavior.** resume-cli export treats `unsupported` as skip-with-notice for non-PDF release targets, never as a pipeline error; the Markdown+DOCX Render Gate is computed independently of the PDF result.

**Migration.** Any existing fixture or smoke expectation built on the fake-`ok` artifact is corrected in the same change — a strengthening edit under RKIT-A-0006 (a dishonest `ok` assertion is precisely the kind of drifted assertion that ADR authorizes realigning).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Policy contract tests for each reason path: missing `format_targets`, `pdf` excluded, `pdf` included but MVP policy — each asserting `unsupported`, the exact reason, and the absence of any artifact.
- Invariant test: no `renderPdf` result may ever pair a non-`ok` status with an artifact, or an `ok` status with bytes that are not a real PDF (asserting on the leading `%PDF` bytes when a future runtime lands — the assertion is written now so it guards the amendment).
- Release-gate regression: Markdown and DOCX smoke/contract runs are unchanged by renderPdf's unsupported status (R5).
- TEST_SPEC strengthening per R6: define "producing a PDF" as actual PDF bytes; strengthen-only per RKIT-A-0006.

## Alternatives Considered **[REQUIRED]**

(Per the RKIT-A-0004 alternatives analysis, summarized for this initiative's scope.)
- **Ship a pure-Python PDF now (fpdf2/ReportLab + pypdf parse-back).** Rejected for MVP: first third-party runtime dependency in an otherwise stdlib-only repo, and the section 9 layout/typography substrate does not exist yet, so output would be low-fidelity. Named the default future candidate.
- **DOCX→PDF via LibreOffice.** Rejected: heavyweight external binary with an environment-detection burden in CI and plugin hosts.
- **Keep the fake-`ok` stub until a runtime is chosen.** Rejected: it is an active Honesty Gate violation, and the `unsupported` status already exists in the surface manifest for exactly this case — honesty costs nothing and requires no decision.

## Implementation Plan **[REQUIRED]**

Sized S: a single-function behavior change plus tests and spec wording.
1. Implement the unsupported decision order in `renderPdf` (all three reasons, no fabricated artifact).
2. Add the policy contract tests and the no-artifact/real-bytes invariant test.
3. Update `render_surface.json` reason enumeration and TEST_SPEC "producing a PDF" wording (R6).
4. Verify the Markdown+DOCX release gates are unaffected and run the canonical package gate.