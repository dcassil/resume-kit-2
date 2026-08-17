---
id: renderpdf-honest-unsupported-three
level: task
title: "renderPdf honest unsupported: three-reason decision order, no fabricated artifact, surface/TEST_SPEC alignment"
short_code: "RKIT-T-0110"
created_at: 2026-08-17T20:05:02.206393+00:00
updated_at: 2026-08-17T20:13:00.154452+00:00
parent: pdf-support-policy-honest
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0033
---

# renderPdf honest unsupported: three-reason decision order, no fabricated artifact, surface/TEST_SPEC alignment

## Parent Initiative

[[RKIT-I-0033]]

## Objective

Kill the fake-PDF honesty violation per RKIT-A-0004 item 2: `renderPdf` returns `{status: "unsupported", reason, format: "pdf", template_version}` with NO fabricated artifact for all three reason paths, the reason vocabulary is enumerated in `render_surface.json`, TEST_SPEC defines "producing a PDF" as actual PDF bytes, and the Markdown+DOCX release targets are provably unaffected.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] `renderPdf` (resume_render/__init__.py:363-381 area; verify current lines) implements the decision order: (1) template missing `format_targets` → reason `format_targets_missing`; (2) `pdf` absent from `format_targets` → `not_in_format_targets`; (3) otherwise → `pdf_not_supported_in_mvp`. Result shape exactly `{status: "unsupported", reason, format: "pdf", template_version}` — NO `artifact` key, no `application/pdf` labeling of non-PDF content, no markdown-in-a-pdf-costume. The fabrication block is DELETED grep-proof.
- [ ] Invariant test (written to guard the future runtime amendment too): no renderPdf result may pair a non-ok status with an artifact, or an ok status with bytes not starting `%PDF` — asserted now even though ok is currently unreachable.
- [ ] Policy contract tests per reason path asserting `unsupported`, the exact reason, and artifact absence.
- [ ] `render_surface.json` enumerates the three-reason vocabulary on the unsupported status (extend the existing :156-160 unsupported declaration; check whether any protected guardrail pins this manifest — tools/render_guardrails.py or similar — and if an edit trips it, STOP and defer per discipline).
- [ ] resume-render/TEST_SPEC.md (not protected): "producing a PDF" defined as emitting actual PDF bytes; the "report PDF as unsupported without failing non-PDF release targets" item names its covering tests. Strengthen-only.
- [ ] Release-gate regression: Markdown and DOCX contract/smoke behavior unchanged (R5) — if the CLI export path or any fixture/smoke expectation consumed the fake-ok artifact, correct the CALLER/fixture honestly (unsupported = skip-with-notice, never pipeline error); never re-fabricate.
- [ ] No new dependencies (R4). Gates green: `--pr`, `--smoke`, `--future-contract`. New test modules bridged into a gate-run module (check bridging explicitly — run_tests.py is protected).

## Implementation Notes

### Technical Approach
Single-function change + tests + spec wording. Check how resume-cli export and any fixtures/snapshots consume renderPdf results before editing; snapshot regenerate ×2 no-drift if fixtures move.

### Dependencies
None (RKIT-A-0004 decided input). Coordinate vocabulary with I-0029's status enumeration (not yet started — this lands the reason enum first; I-0029 inherits it).

### Risk Considerations
Protected-file check: any render guardrail/boundary test pinning renderPdf's current fake-ok shape would need the no-verify lane — investigate first, report, and prefer defer if it's not a strengthen-only realignment (A-0006 authorizes realigning dishonest assertions).

Recommended Agent: opus + medium

## Status Updates

*To be added during implementation*