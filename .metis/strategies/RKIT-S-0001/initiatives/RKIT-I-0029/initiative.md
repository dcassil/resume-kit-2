---
id: resume-render-template-and-result
level: initiative
title: "Resume-Render Template and Result Contract Hardening"
short_code: "RKIT-I-0029"
created_at: 2026-08-13T20:41:37.570664+00:00
updated_at: 2026-08-13T20:41:37.570664+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Resume-Render Template and Result Contract Hardening Initiative

## Context **[REQUIRED]**

Package: `resume-render`. The five-function surface (renderMarkdown, renderDocx, renderPdf, measureLayout, validateRenderedOutput) is implemented, manifest-locked in `render_surface.json`, stdlib-only, and clean on dependency direction: the renderer never rewrites content, computes scores, applies operations, or queries career knowledge. This initiative is therefore not about establishing DTO stability from scratch — it is about fixing four verified contract drifts:

1. **The renderer rejects the documented canonical shape.** `_validate_resume` requires a non-empty `sections` list (`resume_render/__init__.py:75-81`), while section 4.1 `CanonicalResume` (`PRODUCT_VISION_AND_CONTRACTS.md:110-127`) has top-level `experience`/`skills`/`education` arrays and no `sections`. The renderer-safe DTO the package actually consumes is defined implicitly by resume-render plus a CLI convenience alias (`resume-cli/resume_cli/__init__.py:429-441`) instead of being owned by resume-core, as section 4 requires ("These contracts should live in resume-core").
2. **`required_reduction` unit drift.** `measureLayout` returns a page-count delta (`__init__.py:406-413`), but the section 9 overflow-contract example (`requiredReduction: 480`, `PRODUCT_VISION_AND_CONTRACTS.md:680-691`) is a fine-grained quantity that selection/rewrite can act on. RKIT-A-0006 item 7 decides this drift: character count wins.
3. **The `unsupported` status is unreachable.** `render_surface.json:156-160` declares `unsupported` an allowed status, but `validateRenderedOutput` never returns it (`__init__.py:583-591`) and `renderPdf` fabricates `ok` where `unsupported` is the honest answer.
4. **`renderPdf` result-status dishonesty.** It reports status `ok` with markdown text labeled `media_type: application/pdf` and no PDF bytes, and is default-permissive when a template omits `format_targets` (`__init__.py:363-381`). RKIT-A-0004 item 2 authorizes the honest `unsupported` fix immediately, with no runtime decision.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- The renderer-input DTO (a sections-based, renderer-safe resume shape) is defined and owned by resume-core with a documented derivation from section 4.1 `CanonicalResume`; resume-render consumes it and the CLI alias is retired.
- The overflow-constraint DTO carries `required_reduction` as a character count per RKIT-A-0006 item 7.
- The render status vocabulary is fully specified: each function's conditions for `ok`, `failed`, and `unsupported` are written down and `unsupported` is reachable.
- `renderPdf`'s status contract is honest per RKIT-A-0004: `unsupported` with a reason, including when `format_targets` is absent.

**Non-Goals:**
- DOCX styles/numbering, template typography, and ATS-check depth — RKIT-I-0030.
- The measurement model behind the constraint DTO — RKIT-I-0031.
- Parse-back trust-model repair inside validateRenderedOutput — RKIT-I-0032.
- The renderPdf behavior change and its policy tests — RKIT-I-0033 (this initiative fixes the contract text; 0033 implements it).
- Fixtures, smoke, E2E, and audit evidence — RKIT-I-0034.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1. resume-core owns and exports the renderer-input DTO schema (working name `RenderableResume`): header/contact fields plus an ordered `sections` list of `{id, title, entries}`; the derivation from `CanonicalResume` is deterministic and owned by resume-core. `_validate_resume` (`__init__.py:75-81`) validates against the core-owned schema; the duplicate alias at `resume-cli/resume_cli/__init__.py:429-441` is deleted in favor of the core export. Satisfies section 4 DTO ownership.
- R2. The overflow-constraint DTO specifies `required_reduction` as an integer character count (RKIT-A-0006 item 7; `PRODUCT_VISION_AND_CONTRACTS.md:680-691`); `render_surface.json` and TEST_SPEC.md state the unit explicitly so a page-delta implementation can no longer pass.
- R3. `render_surface.json` gains per-status semantics: `unsupported` means the format or artifact kind is not supported under current policy/template, with a machine-readable `reason`; the conditions under which `validateRenderedOutput` returns it are specified here for RKIT-I-0032 to implement.
- R4. The `renderPdf` contract states: no `ok` without actual PDF bytes; a template missing `format_targets` yields `unsupported`, never a permissive `ok` (RKIT-A-0004 item 2). Implementation and policy tests land in RKIT-I-0033.
- R5. All contract-test and manifest realignments follow the RKIT-A-0006 authorization: assertions may only be strengthened or preserved, never weakened; fixture truth content is unchanged.

### Dependencies
- Coordination with the resume-core initiative group: the DTO schema lands in resume-core; this initiative specifies it and realigns the renderer side.
- RKIT-A-0004 and RKIT-A-0006 are decided and are inputs, not blockers.

### Blocked Status
- No. `blocked_by: []`.

## Detailed Design **[REQUIRED]**

**RenderableResume DTO.** resume-core exports a schema with `contact` (name, email, phone, links), optional `summary`, and `sections: [{id, title, entries: [...]}]` where entries preserve titles, dates, bullets, and skills groupings. resume-core also owns `toRenderableResume(CanonicalResume, template) -> RenderableResume`, encapsulating default section ordering; the renderer stays a pure consumer and keeps rejecting non-conforming input with typed errors. This removes the current situation where the real input contract exists only as renderer validation code plus a CLI alias, and makes the documented section 4.1 shape renderable end to end.

**Overflow-constraint DTO.** `{fits: bool, estimated_pages, target_pages, required_reduction: <char count>, constraints: {...}}`. Only the unit semantics and schema are settled here; the measurement model that populates the values is RKIT-I-0031.

**Status vocabulary.** A per-function table in `render_surface.json`, mirrored in TEST_SPEC.md, mapping each of the five functions to its allowed statuses and the exact conditions for each — in particular when `unsupported` is required. `ok` always implies a genuine artifact whose bytes match the claimed `media_type`.

**Migration.** resume-cli switches to the core-owned DTO import; the shared-DTO contract test and `render_surface.json` are updated under the RKIT-A-0006 authorization; fixture truth content is untouched — only shapes and key ownership move.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract test: the renderer accepts a `RenderableResume` derived by resume-core from the section 4.1 `CanonicalResume` fixture, and rejects malformed input with typed errors — closing the "renderer rejects the documented shape" gap end to end.
- Contract test: `measureLayout`'s report schema asserts `required_reduction` is a character count via a value-level assertion against a fixture with known overflow, not mere key presence.
- Contract test: `unsupported` is representable and carries a `reason` (schema-level here; the renderPdf and validator paths are exercised in RKIT-I-0033/0032).
- TEST_SPEC strengthening this initiative owns (audit-flagged looseness): pin `required_reduction` units to characters, and state that `ok` requires an artifact whose bytes match its claimed `media_type` — the two wording gaps that legalized the page-delta and fake-PDF implementations.
- Boundary guardrails stay green; no manifest assertion is weakened (RKIT-A-0006 scope note).

## Alternatives Considered **[REQUIRED]**

- **Keep the implicit renderer-local DTO plus CLI alias.** Rejected: violates section 4 ownership ("These contracts should live in resume-core"), leaves two definitions free to drift independently, and keeps the documented CanonicalResume shape un-renderable — the exact defect the audit verified.
- **Make the renderer accept raw CanonicalResume and derive sections internally.** Rejected: pushes section-ordering/derivation policy into the renderer, blurring its semantic-neutrality rule and duplicating derivation logic that resume-core and the CLI already need for other consumers.
- **Bless the page-delta `required_reduction` by amending the vision doc.** Rejected by RKIT-A-0006 (documented contracts win); a page delta is not actionable by selection/rewrite, the consumer the contract example was written for.

## Implementation Plan **[REQUIRED]**

1. Define `RenderableResume` and the overflow-constraint DTO in resume-core (schema plus deterministic derivation from CanonicalResume), with schema exports.
2. Realign `_validate_resume` and `render_surface.json` to the core-owned schema; delete the resume-cli alias and switch its import.
3. Change `required_reduction` schema, manifest, and TEST_SPEC wording to character-count semantics (value implementation follows in RKIT-I-0031).
4. Specify the per-function status vocabulary including `unsupported` conditions and the honest renderPdf contract (implementation in RKIT-I-0033).
5. Update contract tests under the RKIT-A-0006 strengthen-only authorization and run the canonical package gate from IMPLEMENTATION_PLAN.md.
