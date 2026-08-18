---
id: renderableresume-dto-owned-by
level: task
title: "RenderableResume DTO owned by resume-core: schema, toRenderableResume derivation, renderer realignment, CLI alias deletion"
short_code: "RKIT-T-0113"
created_at: 2026-08-18T21:28:11.238018+00:00
updated_at: 2026-08-18T21:29:20.859616+00:00
parent: resume-render-template-and-result
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0029
---

# RenderableResume DTO owned by resume-core: schema, toRenderableResume derivation, renderer realignment, CLI alias deletion

## Parent Initiative

[[RKIT-I-0029]]

## Objective

Close initiative R1 — the "renderer rejects the documented canonical shape" audit defect: resume-core owns and exports the `RenderableResume` schema (contact/summary + ordered `sections: [{id, title, entries}]`) AND the deterministic `toRenderableResume(CanonicalResume, template)` derivation; resume-render's `_validate_resume` validates against the core-owned schema; the duplicate CLI alias (resume-cli/resume_cli/__init__.py:429-441 area) is deleted in favor of the core export. Section 4.1 CanonicalResume becomes renderable end to end for the first time.

## Acceptance Criteria

## Acceptance Criteria

- [ ] resume-core exports (via its declared surface conventions — check core_surface.json + how existing DTO schemas are exported): `RenderableResume` schema constant — `contact` (name, email, phone, links), optional `summary`, ordered `sections: [{id, title, entries: [...]}]` where entries preserve titles, dates, bullets, and skills groupings — and public `toRenderableResume(canonical_resume, template) -> RenderableResume`, deterministic (same inputs → byte-identical output; template drives section ordering with a documented default when the template is silent; reuse the §13 sectionOrder machinery from I-0003 where it exists — do NOT invent a second ordering policy).
- [ ] Derivation is total over valid CanonicalResume input: every populated 4.1 field lands somewhere in the output (no silent drops — content-preservation test comparing the set of text claims in vs out); malformed input → typed validation errors, never partial output.
- [ ] resume-render `_validate_resume` (resume_render/__init__.py:75-81 area) validates against the CORE-owned schema (import the schema constant or an exported validator — renderer stays a pure consumer; check the render guardrail's dependency-direction rules first: if importing resume_core into resume_render violates a pinned boundary, instead have resume-core export the schema as data consumed via the existing shared-DTO mechanism — look at how shared DTO schemas are shared today, tests/contract/test_shared_dto_schemas_contract.py is the map).
- [ ] The CLI convenience alias (resume-cli/resume_cli/__init__.py:429-441 area — verify current lines) is DELETED; resume-cli imports/derives through the core export; CLI behavior unchanged for already-sections-shaped input.
- [ ] Contract test: renderer accepts a RenderableResume derived by resume-core from the section 4.1 CanonicalResume fixture (end-to-end: canonical fixture → toRenderableResume → renderMarkdown ok); malformed input rejected with typed errors. Strengthen-only realignment of the shared-DTO contract test where shapes move (RKIT-A-0006).
- [ ] Determinism test: two derivations of the same canonical fixture are byte-identical.
- [ ] resume-core/TEST_SPEC.md + resume-render/TEST_SPEC.md (not protected) updated naming covering tests; fixture truth content untouched (only shapes/ownership move). Snapshot regenerate ×2 no-drift if fixtures shift.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. New tests bridged into gate-run modules (check explicitly). NO protected edits (tools/*_guardrails.py, tests/boundary/* read-only — if the render or core guardrail pins the old shape, STOP that sub-change and defer with a verbatim patch in the report).

## Implementation Notes

### Technical Approach
Read the current `_validate_resume`, the CLI alias, and test_shared_dto_schemas_contract.py FIRST to learn the established shared-schema mechanism, then mirror it. domain.py may be large — new derivation logic can live in a new resume-core private module (mirror dates.py/claim_fields.py precedent) with the public export wired through the package surface.

### Dependencies
None hard; consumes I-0003's sectionOrder config machinery.

### Risk Considerations
Cross-package: touches resume-core, resume-render, resume-cli — run --smoke early and often (the T-0005 lesson: DTO tightening breaks downstream producers). Every resume-core initiative is a serial chain on domain.py — no parallel codex.

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*