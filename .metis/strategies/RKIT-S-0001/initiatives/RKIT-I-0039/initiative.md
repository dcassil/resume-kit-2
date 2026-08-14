---
id: final-validation-and-render-export
level: initiative
title: "Final Validation and Render Export Orchestration"
short_code: "RKIT-I-0039"
created_at: 2026-08-13T20:41:37.894752+00:00
updated_at: 2026-08-13T20:41:37.894752+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0038", "RKIT-I-0032"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Final Validation and Render Export Orchestration Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. Export is substantially real: `renderMarkdown`/`renderDocx` produce real artifacts (actual DOCX bytes, template version) and `validateRenderedOutput` exists. Validate, by contrast, is an actively misleading gate, and the overflow contract is unimplemented:

- `validate` can never fail: `_validate` ignores the status of `validateFinalResume` (errors/'fail' discarded), hardcodes `'ats': 'passed'` and `'structure': 'passed'` plus the inferred-fact policy as literal strings with no checks executed, and always returns exit_code 0 (`resume_cli/__init__.py:269-284`, literals at `:280-282`). The contract test only greps for substrings, so the fake satisfies it. DoD 14 and the Required Gates rule ("Final output requires match, grounding, ATS, structure ... artifacts") are not real.
- Export overflow handling is missing: `_export` never calls `measureLayout` and ignores any renderer overflow status entirely (`resume_cli/__init__.py:287-313`); no constraint is returned to selection/rewrite (vision section 9; TEST_SPEC export case "Handles overflow by returning to selection/rewrite rather than truncating").
- No config value is used to enforce structure/length: the section 13 rules (`resume.targetPages`, skills/experience/bulletsPerRole min-max, sectionOrder) appear in no check.

RKIT-A-0006 item 7 decides `required_reduction` is a fine-grained character-count quantity, not a page delta. RKIT-A-0004 decides PDF rendering policy; PDF export is explicitly out of scope for this initiative.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- `validate` becomes a real gate: it propagates `validateFinalResume` errors, runs actual ATS/structure/length/duplicate checks through the owning core/render surfaces, and fails (status fail, nonzero exit, error artifacts) when any check fails. The hardcoded 'passed' literals are deleted.
- Structure/length enforcement is config-driven from the RKIT-I-0035 section 13 config: `resume.targetPages`, sectionOrder, skills/experience/bullets min-max — changing config changes validate outcomes.
- Export runs `measureLayout`; on overflow it returns a constraint DTO (character-count `required_reduction` per RKIT-A-0006 item 7) routed to the RKIT-I-0038 selection/rewrite re-entry instead of truncating or silently shipping.
- Export success is gated on render validation: parse-back/ATS validation of rendered output (RKIT-I-0032 surface) must pass before export reports success.
- Markdown and DOCX outputs only; PDF explicitly out of scope per RKIT-A-0004.

**Non-Goals:**
- Rewrite/selection mechanics that consume the overflow constraint — RKIT-I-0038 (this initiative produces and returns the constraint).
- Renderer internals: layout measurement, parse-back, ATS analysis — the resume-render group (RKIT-I-0032 and its chain).
- Automatic overflow-loop orchestration inside `run` — RKIT-I-0040 wires the cycle; here export returns the constraint with a routed outcome.
- PDF rendering — settled by RKIT-A-0004; any future PDF work belongs to the resume-render PDF initiative.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- `validate` exit code and status reflect real check results; a final resume violating any enforced rule cannot produce exit 0 — removes the `resume_cli/__init__.py:269-284` always-pass behavior (DoD 14).
- The validation artifact records each check (match, grounding, ATS, structure, length, duplicates) with the producing package's actual output — no CLI-authored literals (Required Gates: artifacts prove the checks; replaces `:280-282`).
- `export` calls `measureLayout`; overflow yields `{status: overflow, required_reduction: <chars>, targets: [...]}` routed to selection/rewrite, and no truncated final artifact is written (fixes `:287-313`).
- Section 13 `resume.*` values parameterize structure/length checks; `guardrails.*` values drive the inferred-fact policy in final validation, replacing the hardcoded policy string.
- Export success requires `validateRenderedOutput`/parse-back to pass; failures surface as typed export errors.

### Dependencies
- RKIT-I-0038 (reduction-constraint re-entry on selection/rewrite; honest operation lifecycle upstream of final validation).
- RKIT-I-0032 Rendered Output Parse-Back and ATS Validation (render-side validation surface; the resume-render chain beneath it supplies the measureLayout/overflow constraint surface).

### Blocked Status
- Blocked by RKIT-I-0038 and RKIT-I-0032 (frontmatter matches). PDF policy is settled (RKIT-A-0004 — out of scope here) and the config vocabulary is settled (RKIT-A-0006); no ADR block remains.

## Detailed Design **[REQUIRED]**

- **Validate.** `_validate` orchestrates: core `validateFinalResume` (grounding/truth) → core structure/length checks parameterized by config (targetPages, min-max rules, sectionOrder) → render-side ATS/structure analysis via the RKIT-I-0032 surface → duplicate/repetition check. Result DTO: per-check `{name, owner_package, status, errors[]}`; overall status is fail if any required check fails; exit codes come from RKIT-I-0035's envelope. The inferred-fact policy is read from `guardrails.*` config.
- **Export.** render (Markdown/DOCX) → `measureLayout` → if overflow: write no final artifact, return the overflow constraint (character-count `required_reduction` plus offending targets) with a routed outcome pointing at `tailor --reduce`; if fit: `validateRenderedOutput`/parse-back gate → write export artifacts with template-version metadata.
- **Config wiring.** Checks read the frozen validated config from RKIT-I-0035; no check carries built-in fallback thresholds that mask missing config (missing keys are impossible after 0035's unknown-key/complete-default validation).
- **Artifact contract.** validation.json and export.json become evidence artifacts for the Audit Gate (consumed by RKIT-I-0040's reconstruction); they carry the producing packages' results verbatim.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Strengthen the validate spec with observable failure conditions — the absence that certified the hardcoded fake: a fixture final resume violating targetPages (and separately, duplicate bullets) must yield status fail and nonzero exit; assertions inspect per-check results from owning packages, not substrings.
- Propagation test: core `validateFinalResume` returns fail → CLI validate fails (kills the discarded-status path).
- Config sensitivity test: same resume, `resume.targetPages` 2→1 flips the validate/export outcome — proves config-driven enforcement.
- Export overflow contract test (TEST_SPEC export case): oversized fixture resume → overflow constraint with character-count `required_reduction` and no written final artifact; a second pass after `tailor --reduce` fits and exports.
- Render-validation gate test: a parse-back failure fails export with a typed error.
- Scope guardrail: no PDF surface appears in resume-cli (fence per RKIT-A-0004).

## Alternatives Considered **[REQUIRED]**

- Keep validate advisory (report-only, always exit 0) and enforce only at export: rejected — DoD 14 and the Required Gates rule make validate the final gate with provable artifacts; an advisory gate is the current defect with better manners.
- Truncate or auto-compress on overflow inside export: rejected — silent content mutation by the render path violates "rendering must not change semantic content"; the contract requires returning constraints to selection/rewrite, where truth-preserving reduction lives.
- Implement ATS/structure checks inside resume-cli: rejected — resume-core and resume-render own those checks (CONTRACT_SURFACE_ALIGNMENT.md); CLI-owned checks would be duplicated domain rules, the exact defect class this re-baseline removes.

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Propagate `validateFinalResume` status/errors; delete the hardcoded literals; wire exit codes.
2. Config-driven structure/length/duplicate checks through core surfaces.
3. Render-side ATS/structure validation via the RKIT-I-0032 surface inside validate.
4. `measureLayout` + overflow constraint return path (character count) with the routed outcome to `tailor --reduce`.
5. Parse-back/render-validation gating of export success; evidence-artifact contract for audit.
6. TEST_SPEC strengthening: failure conditions, config sensitivity, overflow case, propagation tests.
