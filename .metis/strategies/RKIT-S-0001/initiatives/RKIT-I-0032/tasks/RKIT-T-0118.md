---
id: bytes-only-parse-back-trust-model
level: task
title: "Bytes-only parse-back trust model: bidirectional semantic comparison, inert sidecar, reachable unsupported, tamper fixtures"
short_code: "RKIT-T-0118"
created_at: 2026-08-18T22:39:03.148530+00:00
updated_at: 2026-08-18T22:49:31.519082+00:00
parent: rendered-output-parse-back-and-ats
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0032
---

# Bytes-only parse-back trust model: bidirectional semantic comparison, inert sidecar, reachable unsupported, tamper fixtures

## Parent Initiative

[[RKIT-I-0032]]

## Objective

Repair the audit's most serious render defect — validateRenderedOutput trusting the renderer's sidecar and missing additions: every verdict input derives EXCLUSIVELY from the artifact bytes; the semantic comparison is bidirectional (material additions fail, not just omissions — the byte-tampered inflated-claim DOCX becomes a permanent failing fixture); `unsupported` becomes reachable for kinds with no parse-back path; TEST_SPEC is strengthened so the sidecar shortcut can never re-certify.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Bytes-only extraction (R1): DOCX pipeline base64 → zip → word/document.xml (aware of the I-0030 styles/numbering structure — bullets and styled headings extract correctly) → normalized text lines. The verdict function structurally CANNOT see `artifact.text` (signature takes bytes-derived text + expected resume only); the sidecar survives only as `renderer_reported_text` diagnostic metadata. The `return artifact_text or docx_text` fallback (resume_render/__init__.py:493-495 area) and the any-dict-with-text pass (:496-497) are DELETED.
- [ ] Bidirectional comparison (R2): normalized (casefold, whitespace-collapse, punctuation-stable tokenization) two-way multiset comparison; differences classified material (claim-bearing tokens: numbers, titles, technologies, employers, dates) vs cosmetic (formatting chars, bullet glyphs, template-permitted within-section ordering); ANY material addition or omission → fail with `semantic_differences` entries tagged `added`/`omitted`.
- [ ] Adversarial fixture suite (shared onward with I-0034): (a) DOCX bytes tampered to ADD an inflated claim → fail (the audit's runtime demonstration, permanent); (b) bytes tampered to REMOVE content → fail; (c) lying sidecar + honest bytes → pass (verdict tracks bytes); (d) honest sidecar + tampered bytes → fail. Plus the inert-sidecar contract test: mutating artifact.text changes NO verdict.
- [ ] `unsupported` reachable (R3): pdf-kind (and any kind without a parse-back path) → `{status: unsupported, reason}` per the I-0029/T-0114 vocabulary — never a sidecar-based pass. FLIP the T-0114 status-table row for validateRenderedOutput's unsupported from implemented:false to true (the parity test's not-yet-emitted assertion inverts to reachable — honest marker update in the same change).
- [ ] Corruption preserved (R4): unreadable zip/XML still → failed with cause (existing diagnostics kept or strengthened).
- [ ] TEST_SPEC strengthening (R5): bytes-derivation requirement, addition-detection requirement, and the tamper fixtures NAMED in resume-render/TEST_SPEC.md; strengthen-only (RKIT-A-0006).
- [ ] Existing omission/heading/ATS checks stay green (or strengthened); Markdown-kind validation path defined honestly (text artifacts: bytes ARE the text — document what "bytes-derived" means per kind).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits; new tests bridged (state where). Snapshot regenerate ×2 no-drift if fixtures shift.

## Implementation Notes

### Technical Approach
Keep extraction in a private module or beside _ooxml.py. The material/cosmetic classifier should be conservative and deterministic — when unsure, MATERIAL (fail closed; the Render Gate is a gate). Tamper fixtures: build honest DOCX via renderDocx, then unzip/modify document.xml/rezip inside the test (deterministic construction, no binary blobs committed if avoidable).

### Dependencies
I-0030 DOCX structure (landed), I-0029/T-0114 status vocabulary (landed), I-0033 pdf policy (landed).

### Risk Considerations
CLI/workflow currently call validateRenderedOutput — additions previously passed; check smoke/CLI flows for anything that now legitimately fails (a true positive means fixing the CALLER's content, never loosening the classifier). Within-section reordering permitted by template must stay cosmetic or smoke may false-positive.

Recommended Agent: opus + high

## Status Updates

- 2026-08-18: Implemented bytes-only DOCX validation path in `resume-render/resume_render/__init__.py`: `artifact.text` no longer certifies DOCX or unknown artifacts; DOCX verdicts use parsed `word/document.xml`; sidecar is diagnostic-only as `renderer_reported_text`; PDF/unknown artifacts return `unsupported`; corrupt DOCX returns `failed` with cause. Added bidirectional token multiset semantic diff tagged `added`/`omitted`.
- 2026-08-18: Added bridge tests in `tests/contract/test_resume_render_contract.py` for added inflated claim, removed content, lying sidecar with honest bytes, honest sidecar with tampered bytes, inert sidecar verdict, PDF unsupported, and corrupt DOCX cause. Focused `python3 -m unittest tests.contract.test_resume_render_contract -v` passes.
- 2026-08-18: Required gates pass: `python3 tools/run_gate.py --pr --root .`, `python3 tools/run_gate.py --smoke --root .`, and `python3 tools/run_gate.py --future-contract --root .`. No caller content fixes were needed.