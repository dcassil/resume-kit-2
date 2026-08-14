---
id: plugin-contract-smoke-and-e2e
level: initiative
title: "Plugin Contract, Smoke, and E2E Parity Gates"
short_code: "RKIT-I-0049"
created_at: 2026-08-13T20:41:38.256285+00:00
updated_at: 2026-08-13T20:41:38.256285+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0044", "RKIT-I-0047"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Plugin Contract, Smoke, and E2E Parity Gates Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. Verification baseline, verified by the alignment audit: `tests/e2e` is empty; `tools/run_smoke.py` only import-checks the `resume_plugin` module (`run_smoke.py:29`); and the contract fixtures are hand-crafted to the plugin's invented DTO field names (`tests/contract/test_resume_plugin_contract.py:143-169`), so presenters that render real CLI output as empty pass the 188-test gate untouched. On this basis a ~30%-complete package was logged "complete". Three spec loopholes certified the shallow code: version checks that assert key presence only (hardcoded `public-api`/`delegated-to-workflow` pass), mapping requirements satisfiable by returning a command *string* with no invocation path (the fictional `resume report` passed), and "optional" framing of smoke/E2E coverage that let the empty harness hide behind a green PR gate.

TEST_SPEC's E2E section (TEST_SPEC.md:79-87) defines the required parity: the plugin path must produce results identical to the CLI path. RKIT-A-0005 item 5 additionally requires parity tests to feed presenters real resume-cli output. The old chain position (last, behind packaging RKIT-I-0048) is corrected: parity gates now depend on RKIT-I-0044 (invocation path) and RKIT-I-0047 (real-shape presenters and real-output fixtures) so they co-evolve with the work they gate.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- An executable smoke plus E2E parity harness proving plugin-invoked workflows produce domain results identical to direct CLI runs, across every TEST_SPEC.md:79-87 dimension.
- The three spec loopholes closed so nominal compliance is structurally impossible.
- "Complete" logging for resume-plugin requires the full gate: contract, smoke, and E2E parity.

**Non-Goals:**
- Fixing the presenters/DTO shapes themselves — RKIT-I-0047 delivers those; this initiative gates them.
- Implementing tool handlers — RKIT-I-0044.
- The upgrade-safety harness — RKIT-I-0048 (which reuses this initiative's parity dimensions).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: Smoke actually invokes a workflow through plugin tool handlers against a fixture workspace, replacing the import-only check (`run_smoke.py:29`); smoke is mandatory in the canonical package gate — the "optional" framing loophole is removed from TEST_SPEC.
- R2: The E2E parity suite asserts identity between the plugin path and the CLI path on each TEST_SPEC.md:79-87 dimension, enumerated here as acceptance criteria:
  - match score;
  - requirement resolution states;
  - verification states;
  - applied operations;
  - final canonical resume;
  - rendered semantic content;
  - audit reconstruction.
- R3: Fixtures are generated from real resume-cli output and reuse the same fixture expectations as the CLI E2E suite; the hand-crafted invented-shape fixtures (the `tests/contract/test_resume_plugin_contract.py:143-169` pattern) are replaced under RKIT-A-0006's strengthen-only authorization.
- R4: Version checks assert real identity values against ground truth, never key presence.
- R5: Mapping satisfaction requires dispatch: the gate proves a mapped command executed via the public-API path (not merely that a string was returned) and that every mapped command is in `cli_surface.json` `required_commands`.

### Dependencies
- RKIT-I-0044 (Real Plugin Tool Registration and Workflow Delegation): the invocation path the harness exercises.
- RKIT-I-0047 (Plugin Diff, Report, Export, and Audit Presentation): real-shape presenters and the real-output fixture generator.

### Blocked Status
- Yes: RKIT-I-0044 and RKIT-I-0047. The RKIT-A-0005 block is lifted (decided); the old serialization behind RKIT-I-0048 is removed so parity co-evolves with delegation and presentation.

## Detailed Design **[REQUIRED]**

Harness shape: a fixture workspace (source resume, job description, career DB) runs one scenario twice — once via resume-cli command functions, once via plugin tool handlers. Both runs collect the domain artifacts: match result, requirement resolutions, verification states, operations, final canonical resume JSON, rendered output, and the audit manifest. The suite asserts structural equality on the seven parity dimensions; presentation output is additionally checked to be a faithful view of — never a substitute for — the underlying domain artifacts.

Negative control: a deliberately broken presenter (one returning empty lists, i.e. the pre-RKIT-I-0047 behavior) must fail the parity suite — regression proof that the failure mode the 188-test gate missed is now caught.

Spec changes (strengthen-only per RKIT-A-0006): smoke made mandatory; the seven parity dimensions made normative acceptance criteria; presentation-input requirements reference the section 4.3/4.5 DTO shapes; version assertions specified by value; mapping requirements specified as dispatched-and-in-`required_commands`.

Gate wiring: the canonical package gate from IMPLEMENTATION_PLAN.md runs contract, smoke, and E2E parity for resume-plugin; work-log "complete" claims require all three. E2E stays cheap: one or two golden scenarios, since parity is structural rather than breadth-seeking.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

This initiative is itself the testing work; its own verification is: the dual-run parity suite passes against the RKIT-I-0044/RKIT-I-0047 implementations; the negative control fails as designed; the strengthened TEST_SPEC text matches what the harness enforces (no requirement satisfiable by key presence, command strings, or import checks); and the package gate refuses "complete" with any of the three layers missing.

## Alternatives Considered **[REQUIRED]**

- Presentation-level snapshot tests only, with no dual CLI-vs-plugin run: rejected — snapshots of plugin output are exactly how the fixture-tuned 188-test gate went blind; parity must compare against CLI ground truth per TEST_SPEC E2E and RKIT-A-0005 item 5.
- Keep the old ordering (parity gates after packaging, blocked by RKIT-I-0048): rejected — the audit showed parity fixtures must co-evolve with delegation (0044) and presentation (0047); deferring gates to the end is how a 30%-complete package logged as complete.

## Implementation Plan **[REQUIRED]**

Decomposition guidance:
1. Real-output scenario harness sharing RKIT-I-0047's fixture generator (workspace, job, and career DB fixtures).
2. Smoke rewrite: real workflow invocation via plugin handlers, made mandatory in the gate.
3. Dual-run E2E parity suite across the seven dimensions plus the broken-presenter negative control.
4. TEST_SPEC strengthening edits and canonical-gate wiring.
