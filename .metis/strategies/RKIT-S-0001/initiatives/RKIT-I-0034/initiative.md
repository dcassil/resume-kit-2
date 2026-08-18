---
id: render-gate-integration-fixtures
level: initiative
title: "Render Gate Integration, Fixtures, and Audit Evidence"
short_code: "RKIT-I-0034"
created_at: 2026-08-13T20:41:37.729923+00:00
updated_at: 2026-08-18T22:52:30.160043+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0030, RKIT-I-0032]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: render-gate-integration-fixtures
---

# Render Gate Integration, Fixtures, and Audit Evidence Initiative

## Context **[REQUIRED]**

Package: `resume-render`. Real progress exists at the boundary this initiative gates: resume-cli already consumes renderMarkdown/renderDocx/validateRenderedOutput (`resume-cli/resume_cli/__init__.py:16`) and writes real .docx bytes to `output/`, and a smoke gate already runs (`tools/run_smoke.py` via `run_tests.py`). But the proof layer this initiative owns is hollow, per the audit:

- **`tests/e2e` and `tests/integration` are empty directories**, despite TEST_SPEC promising both (including "overflow causes orchestration to re-run content reduction and final validation" and "final artifacts are included in audit reports").
- **The smoke harness never exercises `measureLayout` or any overflow path**, even though TEST_SPEC's smoke coverage requires proving "overflow is reported rather than silently deleted". No caller of `measureLayout` exists anywhere in the repo.
- **The smoke DOCX target is currently satisfied by a `.docx.json` wrapper instead of a real `.docx` file** — the gate certifies a JSON stand-in, not artifact bytes.
- Audit-evidence fields (template version, artifact fingerprints, layout reports, validation results) are unproven in run manifests.

Dependency correction per RKIT-A-0004 item 5: this initiative was serialized behind PDF (RKIT-I-0033) and must not be — the release Render Gate is Markdown + DOCX, none of which needs the PDF decision. It is blocked instead by RKIT-I-0030 (real DOCX structure to assert against) and RKIT-I-0032 (bytes-derived validation, without which gate assertions would certify the sidecar shortcut).

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- `tests/integration` and `tests/e2e` are populated with the suites TEST_SPEC promises, exercising real CLI-produced artifacts.
- Smoke exercises `measureLayout` with an overflow fixture and asserts overflow is reported, not silently deleted.
- The smoke DOCX target is satisfied only by a real `.docx` zip validated from its bytes — the `.docx.json` wrapper shortcut is retired.
- Run manifests carry the Audit Gate evidence for rendering: template version, artifact fingerprints, layout report, validation results.

**Non-Goals:**
- Measurement fidelity (RKIT-I-0031), parse-back mechanics (RKIT-I-0032), DOCX structure (RKIT-I-0030), PDF policy (RKIT-I-0033 — explicitly unserialized per RKIT-A-0004 item 5).
- Overflow routing into selection/rewrite — owned by workflow/resume-cli and wired by RKIT-I-0027/0039; this initiative supplies the fixtures and the E2E assertions that prove the round trip once wired.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1. `tests/integration` populated: the render boundary is exercised with artifacts actually produced through resume-cli export — renderMarkdown, renderDocx, and validateRenderedOutput over real bytes from `output/`, not synthetic dicts.
- R2. `tests/e2e` populated: a full-pipeline fixture in which render overflow occurs, asserting overflow constraints surface to orchestration and content reduction re-runs with final validation (TEST_SPEC's promised E2E case). The routing is wired by RKIT-I-0027/0039; this initiative owns the fixture and the assertion.
- R3. Smoke exercises `measureLayout`: an overflow fixture runs through `tools/run_smoke.py`, and smoke asserts the overflow report exists, `fits: false`, and content length is unchanged — proving "overflow is reported rather than silently deleted".
- R4. The smoke DOCX assertion requires a real `.docx` zip whose bytes decode and pass the RKIT-I-0032 bytes-derived validator, replacing the `.docx.json` wrapper.
- R5. Run manifests include `template_version`, artifact fingerprints, the layout report, and validation results, asserted by audit-gate tests ("final artifacts are included in audit reports"; Audit Gate fields in CONTRACT_SURFACE_ALIGNMENT.md).
- R6. Fixture and assertion changes are strengthen-only per RKIT-A-0006; no existing assertion is weakened to make a gate pass.

### Dependencies
- RKIT-I-0030 and RKIT-I-0032 (blocking): real DOCX structure and trustworthy bytes-derived validation are the substrate the gates assert against.
- RKIT-I-0031 (coordination): its char-based overflow values are what the overflow fixtures assert; smoke shape assertions can land against the RKIT-I-0029 DTO first.
- RKIT-I-0027/0039 (cross-package): wire overflow consumption in workflow/resume-cli; the E2E round-trip assertion completes when they land.
- RKIT-I-0033 is NOT a dependency (RKIT-A-0004 item 5).

### Blocked Status
- Yes: RKIT-I-0030, RKIT-I-0032 (frontmatter `blocked_by: ["RKIT-I-0030", "RKIT-I-0032"]`). No ADR blockers — RKIT-A-0004 and RKIT-A-0006 are decided.

## Detailed Design **[REQUIRED]**

**Fixture set.** (a) A resume that fits one page under the default template; (b) an overflow variant with a known character excess (values from RKIT-I-0031's model); (c) the adversarial tampered-DOCX artifact shared from RKIT-I-0032, ensuring the gate itself proves tamper detection end to end.

**Integration harness.** Drive resume-cli export against fixture (a), capture the `output/` artifacts, and feed the actual bytes back through validateRenderedOutput — asserting pass verdicts, deterministic fingerprints across two runs, and provenance absence in the artifact bytes.

**Smoke additions.** New smoke steps in `tools/run_smoke.py`: run `measureLayout` on fixture (b) and assert the report (fits/estimated_pages/required_reduction/constraints) with unchanged content; assert the DOCX smoke artifact starts with the zip magic (`PK`), unzips, and passes byte validation — a `.docx.json` wrapper can no longer satisfy the target.

**Audit evidence.** Map the render fields into the run manifest the workflow owns: `template_version` and metrics version from the layout report, artifact fingerprints, and the validation result summary — matching the Audit Gate's reconstruction list. The manifest write is workflow/CLI-owned; this initiative asserts presence and correctness at the render boundary.

**E2E skeleton.** The overflow round-trip E2E is structured so its orchestration steps activate when RKIT-I-0027/0039 land, with the render-side assertions (constraints produced, honesty preserved) active immediately.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

This initiative IS test work; the TEST_SPEC-strengthening items it owns (audit-flagged looseness that certified shallow behavior):
- Implement the smoke-coverage claim TEST_SPEC already makes: overflow reported rather than silently deleted — currently claimed but never executed.
- Redefine the smoke DOCX target as real artifact bytes, killing the `.docx.json` wrapper pathway.
- Relocate the cross-package case "overflow routes back to selection/rewrite workflow" from renderer unit scope to E2E (shared respecification with RKIT-I-0031), where it is actually provable.
- Add audit-evidence assertions so missing manifest fields fail the gate instead of passing silently.
- Boundary guardrails stay green throughout; all edits strengthen-only per RKIT-A-0006.

## Alternatives Considered **[REQUIRED]**

- **Rely on package contract tests alone and drop the e2e/integration suites.** Rejected: TEST_SPEC explicitly promises both, and the Render/Audit Gates are cross-package properties — contract tests cannot prove that CLI-produced bytes validate or that manifests carry evidence.
- **Keep the initiative serialized behind PDF (the old 0033 → 0034 chain).** Rejected by RKIT-A-0004 item 5: the release target is Markdown + DOCX; waiting on PDF delays the release-gate proof for no reason.
- **House all render fixtures in the workflow package.** Rejected: render-boundary fixtures belong with the renderer's package gate so the package can certify itself; only the shared pipeline E2E lives at repo level per test-infra conventions.

## Implementation Plan **[REQUIRED]**

1. Build the fixture set and the integration suite over real CLI-produced artifacts (R1).
2. Add the smoke overflow steps and the real-DOCX-bytes assertion (R3, R4).
3. Add audit-evidence manifest assertions at the render boundary (R5).
4. Land the E2E round-trip fixture with render-side assertions active, orchestration assertions keyed to RKIT-I-0027/0039 (R2).
5. Apply the TEST_SPEC strengthening set and run the canonical package gate.