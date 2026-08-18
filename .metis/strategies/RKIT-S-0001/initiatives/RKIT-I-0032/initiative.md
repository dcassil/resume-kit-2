---
id: rendered-output-parse-back-and-ats
level: initiative
title: "Rendered Output Parse-Back and ATS Validation"
short_code: "RKIT-I-0032"
created_at: 2026-08-13T20:41:37.665427+00:00
updated_at: 2026-08-18T22:39:41.848829+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0030]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: rendered-output-parse-back-and-ats
---

# Rendered Output Parse-Back and ATS Validation Initiative

## Context **[REQUIRED]**

Package: `resume-render`. The originally written outcome is mostly done: `validateRenderedOutput` performs real DOCX parse-back (base64 decode, zip part checks, XML text extraction with corruption diagnostics) and already detects missing headings, a fixed ATS-unsafe character set, empty output, and omitted expected text. What remains is the package's most serious verified defect — the trust model — and it is the core scope of this initiative:

- **Sidecar trust.** For DOCX, `text_extracted` is the renderer's self-reported sidecar, not the parsed bytes (`return artifact_text or docx_text`, `resume_render/__init__.py:493-495`); for any other artifact kind, any dict with `artifact.text` validates its own claimed text (`__init__.py:496-497`).
- **No addition detection.** `semantic_differences` only checks omissions — expected terms missing from the text (`__init__.py:563-567`) — and the byte containment check is one-directional. Consequence, demonstrated at runtime: a DOCX whose bytes were tampered to ADD an inflated claim passes validation with status `pass`. This violates the Render Gate — "rendered semantics match canonical working resume" (`CONTRACT_SURFACE_ALIGNMENT.md:342-349`).
- **`unsupported` is never returned** although `render_surface.json` allows it (`__init__.py:583-591`).
- **TEST_SPEC looseness legalized all of this:** the spec never requires compared text to derive from artifact bytes and requires only loss detection, not addition detection — so the sidecar-trusting implementation satisfies the spec while failing the alignment doc's gate.

Dependency correction from the audit: this initiative is NOT blocked by RKIT-I-0031 — parse-back validation does not need layout measurement, and the prior serialization was unjustified. It is blocked by RKIT-I-0030 because parse-back must handle the real styles/numbering DOCX structure that initiative introduces.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Trust-model repair: every validation verdict derives exclusively from the artifact bytes; renderer-supplied sidecar text can never satisfy a check.
- Bidirectional semantic comparison: additions are detected and fail validation, alongside the existing omission detection; the byte-tampered inflated-claim DOCX becomes a permanent failing fixture.
- `unsupported` becomes reachable for artifact kinds with no byte-level parse-back path, per the RKIT-I-0029 status vocabulary.
- TEST_SPEC is strengthened so the sidecar shortcut can never re-certify a future implementation.

**Non-Goals:**
- PDF parse-back — none exists in MVP per RKIT-A-0004 (pdf-kind artifacts yield `unsupported`; the future pypdf validator arrives via ADR amendment, coordinated with RKIT-I-0033).
- ATS-check breadth and DOCX generation — RKIT-I-0030.
- Layout measurement — RKIT-I-0031 (explicitly not a dependency).
- Smoke/E2E gate wiring and adversarial fixtures at pipeline level — RKIT-I-0034 (it reuses the tamper fixtures built here).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1. For DOCX artifacts, `text_extracted` and every verdict input derive exclusively from decoding and parsing the artifact bytes; sidecar text (`artifact.text`) is demoted to diagnostic metadata and cannot influence any check (fixes `__init__.py:493-495`).
- R2. Semantic comparison is bidirectional: material content present in the artifact but absent from the expected canonical resume is reported as an addition-class difference and fails validation, alongside omission detection (fixes `__init__.py:563-567`). Satisfies the Render Gate at `CONTRACT_SURFACE_ALIGNMENT.md:342-349`.
- R3. Artifact kinds with no byte-level parse-back path return status `unsupported` with a reason — never a sidecar-based `pass` (fixes `__init__.py:496-497` and makes `__init__.py:583-591` honest per the RKIT-I-0029 vocabulary).
- R4. Corruption diagnostics are preserved: unreadable zip/XML still yields `failed` with a cause.
- R5. TEST_SPEC is strengthened (audit item): parse-back comparisons MUST derive from artifact bytes; loss AND addition detection are both required; the adversarial tamper fixtures are named in the spec so no future implementation can pass without them. Edits follow the RKIT-A-0006 strengthen-only authorization.

### Dependencies
- RKIT-I-0030: parse-back must understand the styles/numbering DOCX structure it introduces.
- RKIT-I-0029 defined the status vocabulary (`unsupported` conditions) implemented here.
- RKIT-I-0033 coordination: pdf-kind artifacts validate as `unsupported` under MVP policy.

### Blocked Status
- Yes: RKIT-I-0030 (frontmatter `blocked_by: ["RKIT-I-0030"]`). Explicitly not blocked by RKIT-I-0031; no ADR blockers — RKIT-A-0004 and RKIT-A-0006 are decided.

## Detailed Design **[REQUIRED]**

**Extraction pipeline.** base64 → zip → `word/document.xml` (list/style-aware after RKIT-I-0030) → normalized text lines. The verdict function takes only this bytes-derived text plus the expected canonical resume; by construction it has no access to `artifact.text`. The sidecar is retained in the report as `renderer_reported_text` for debugging only.

**Comparison model.** Normalize both sides (casefold, whitespace collapse, punctuation-stable tokenization), then compare token/line multisets in both directions. Differences are classified material vs cosmetic — formatting characters, bullet glyphs, and within-section ordering permitted by the template are cosmetic; any token sequence carrying claims (numbers, titles, technologies, employers, dates) is material. Any material addition or omission → `fail` with itemized `semantic_differences` entries tagged `added` or `omitted`.

**Trust boundary.** Validator and renderer live in the same package but must not share the text pathway: validation re-derives everything from bytes, so it catches renderer bugs (wrong content rendered) as well as post-render tampering. This is what makes the Render Gate a gate rather than the renderer grading its own homework.

**Status mapping.** Parseable + clean → `pass`; parseable + material differences or ATS violations → `fail`; unreadable bytes → `failed` with corruption cause; kind without a parse-back path (e.g. pdf in MVP) → `unsupported` with reason.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Adversarial fixtures: (a) DOCX bytes tampered to add an inflated claim — must fail (the audit's runtime demonstration made permanent); (b) bytes tampered to remove content — must keep failing; (c) sidecar lies in both directions while bytes are honest — verdict must be `pass`, tracking bytes; (d) honest sidecar with tampered bytes — must fail.
- Contract test that `artifact.text` is inert: mutating the sidecar cannot change any verdict.
- `unsupported` path test: a pdf-kind artifact returns `unsupported` with a reason, not a sidecar-based `pass`.
- Regression suite over RKIT-I-0030's list/style DOCX structure (bullets and styled headings extract correctly).
- TEST_SPEC strengthening per R5 — the spec names the bytes-derivation requirement, the addition-detection requirement, and the tamper fixtures. All edits strengthen-only per RKIT-A-0006.

## Alternatives Considered **[REQUIRED]**

- **Renderer-signed sidecar (checksum) instead of re-parsing.** Rejected: renderer and checksum live in the same trust domain — tampering re-computes the checksum — and it cannot catch renderer bugs, only post-hoc edits.
- **Re-render and byte-compare.** Rejected: self-comparison certifies the renderer's own defects (a renderer that drops or adds content reproduces the error identically) and proves nothing about ATS readability of the actual artifact bytes.
- **Move parse-back validation to CLI/workflow.** Rejected: parse-back is renderer-owned per the package TEST_SPEC and the CONTRACT_SURFACE_ALIGNMENT.md ownership table; only gate orchestration lives outside the package.

## Implementation Plan **[REQUIRED]**

1. Build the bytes-only extraction path and demote the sidecar to diagnostic metadata.
2. Implement bidirectional comparison with material/cosmetic classification and `added`/`omitted` difference tagging.
3. Integrate the status vocabulary (`unsupported` for non-parseable kinds; corruption → `failed` with cause).
4. Create the adversarial tamper fixture suite (shared onward with RKIT-I-0034).
5. Apply the TEST_SPEC strengthening and run the canonical package gate.