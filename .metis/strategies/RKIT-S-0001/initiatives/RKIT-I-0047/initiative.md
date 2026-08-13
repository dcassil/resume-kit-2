---
id: plugin-diff-report-export-and
level: initiative
title: "Plugin Diff, Report, Export, and Audit Presentation"
short_code: "RKIT-I-0047"
created_at: 2026-08-13T20:41:38.181783+00:00
updated_at: 2026-08-13T20:41:38.181783+00:00
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

# Plugin Diff, Report, Export, and Audit Presentation Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. The previous document's only quality bar ("without leaking sensitive raw data") aimed at the wrong failure mode: the audit verified the presenters make real data vanish. They read DTO field names invented by the plugin's own `plugin_surface.json`: `presentReport` reads `resolved_requirements`/`missing_requirements`/`preferred_requirements`/`unresolved_requirements`/`render_results`, while the actual CLI match report emits `requirement_results`/`requirements`/`unresolved` (`resume-cli/resume_cli/__init__.py:152-171`) and export emits `render_validation`/`artifacts` (`:287-313`) — fed real CLI output, `presentReport` returns all-empty lists (verified). `presentAuditSummary` likewise mismatches the real audit DTO: `_audit_report` returns `facts` (not `fact_changes`), `operations` as an `{applied, rejected}` dict, and `validations` as a dict (`resume-cli/resume_cli/__init__.py:342-374`); dicts fail `_copy_sequence` (`resume_plugin/__init__.py:83-86`), so real audits present as empty. `presentDiff` buckets every non-`rejected` status — `proposed`, `pending`, `validated`, or garbage — into `applied_operations` (`__init__.py:257-261`), violating the section 4.5 status vocabulary (PRODUCT_VISION_AND_CONTRACTS.md:203-221), and three shape dialects coexist (plugin `target`/`path` at `__init__.py:252`, upstream `targetPath`, CLI `operation_id`). `_operation_id` fabricates `operation_N` fallback IDs (`__init__.py:121-122`), masking malformed records. The 188-test gate notices none of this because every fixture is hand-crafted to the invented shapes (`tests/contract/test_resume_plugin_contract.py:143-169`).

This work is host-independent per the audit, so the initiative is unblocked and front-loadable. RKIT-A-0005 item 5 mandates binding to the resume-core-owned shapes; RKIT-A-0006 authorizes the `plugin_surface.json` realignment and defines the target section 4.3/4.5 shapes.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Presenters consume the real resume-core-owned DTO shapes: section 4.3 `MatchResult`, the section 4.5 `ResumeChangeOperation` status vocabulary, and the actual resume-cli match/export/audit output shapes — real CLI output produces non-empty, content-correct presentations.
- `presentDiff` status bucketing follows section 4.5 exactly: only `applied` displays as applied.
- Parity fixtures are generated from real resume-cli output; hand-crafted invented shapes are deleted.

**Non-Goals:**
- Confirmation presentation — RKIT-I-0046 (flagged fold-candidate into this initiative; the derived-redaction rule is shared).
- Tool handlers and invocation — RKIT-I-0044.
- The full CLI-vs-plugin parity harness — RKIT-I-0049 (this initiative supplies the real-output fixtures 0049 consumes).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: `plugin_surface.json`'s invented ReportPresentation/AuditPresentation field names are realigned to the resume-core-owned shapes under RKIT-A-0006 authorization; ownership per CONTRACT_SURFACE_ALIGNMENT.md:149-158 — `MatchResult` is read by the plugin, never owned or redefined by it.
- R2: `presentReport` consumes actual CLI match/export output (`requirement_results`/`requirements`/`unresolved`; `render_validation`/`artifacts` — `resume-cli/resume_cli/__init__.py:152-171, 287-313`) and yields non-empty presentations for non-empty inputs.
- R3: `presentAuditSummary` handles the real audit shape — `facts`, `operations` as `{applied, rejected}`, `validations` as a dict (`resume-cli/resume_cli/__init__.py:342-374`); the `_copy_sequence` dict failure (`resume_plugin/__init__.py:83-86`) is eliminated.
- R4: `presentDiff` maps the section 4.5 statuses exactly (`proposed`/`validated`/`rejected`/`applied`/`accepted`/`modified`); an unknown status is an explicit error, never bucketed as applied (`__init__.py:257-261`). One shape dialect per the owning contract (`targetPath`, `operation_id`), replacing the three-dialect drift (`__init__.py:252`).
- R5: `_operation_id` no longer fabricates `operation_N` fallbacks (`__init__.py:121-122`); malformed ChangeOperation records are surfaced as errors.
- R6: Sensitive raw data remains omitted, and `sensitive_fields_omitted` in `presentAuditSummary` (`__init__.py:309`) is derived from actual redaction (shared rule with RKIT-I-0046); placeholder version substitution in audit presentations (`__init__.py:300-304`) is removed — missing metadata is reported missing, never fabricated.

### Dependencies
- None. This initiative is intentionally unblocked and should be front-loaded: it is host-independent and its real-output fixtures unblock RKIT-I-0049.

### Blocked Status
- No. The formerly implied chain (0044 to 0045 to 0046 to 0047) is dissolved; RKIT-A-0005 and RKIT-A-0006 are decided and govern the target shapes.

## Detailed Design **[REQUIRED]**

Input DTO binding: presenters accept the documented contract shapes — `MatchResult` with `threshold`, `hardRequirementsResolved`, `dimensions`, and the tri-state `decision` (section 4.3, as restored by RKIT-A-0006 item 4); `ResumeChangeOperation` with mandatory `reason`/`provenance` and the six-status vocabulary (section 4.5, RKIT-A-0006 item 3); and the CLI/workflow audit manifest shape. Because the upstream 4.3/4.5 realignment is itself in flight under RKIT-A-0006, presenters bind to the *documented* contract shape; the real-output fixtures make any interim upstream mismatch visible instead of silently rendering empty.

Presentation DTOs are derived views: field names traceable to the owning contract — no parallel ontology, no renaming layer. Status rendering is an explicit six-entry mapping with an error path for unknown values.

Fixture mechanism: a fixture-generation script runs actual resume-cli match/export/audit commands against a small fixture workspace and captures golden outputs; contract tests feed those to the presenters. The hand-crafted fixture shapes in `tests/contract/test_resume_plugin_contract.py:143-169` are deleted, and test edits follow RKIT-A-0006's strengthen-only rule.

Migration notes: `plugin_surface.json` edits are protected-surface changes expressly authorized by RKIT-A-0006 for realignment; assertion strength may only increase; fixture truth content is unchanged.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Real-output parity tests: presenters fed captured resume-cli match/export/audit output must produce non-empty, content-correct presentations — killing the invisible-drift failure class where fixture-tuned tests certified empty rendering.
- Exhaustive section 4.5 status test over all six statuses plus the unknown-status error case.
- Malformed-operation test: a record missing `operation_id` fails loudly instead of receiving a fabricated ID.
- TEST_SPEC strengthening (audit-flagged): presentation-input requirements gain explicit references to section 4.3 `MatchResult` and section 4.5 `ResumeChangeOperation` so invented parallel shapes can never again satisfy the spec.

## Alternatives Considered **[REQUIRED]**

- Keep the `plugin_surface.json` shapes and add a translation layer from the real DTOs: rejected — it preserves a parallel ontology the plugin does not own, doubles the drift surface, and contradicts RKIT-A-0005 item 5's direct-binding mandate.
- Wait for the upstream 4.3/4.5 realignment to land before starting: rejected — binding to the documented contract now is exactly RKIT-A-0006's rule, this work is host-independent, and real-output fixtures expose interim mismatches rather than hiding them.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (front-load this initiative; fold RKIT-I-0046 in if convenient):
1. Realign `plugin_surface.json` presentation shapes to the owned contracts (RKIT-A-0006-authorized edit).
2. Rework `presentReport`/`presentAuditSummary` against the real CLI shapes; remove the `_copy_sequence` dict failure, placeholder substitution, and `operation_N` fabrication.
3. Fix `presentDiff` section 4.5 bucketing and collapse to one shape dialect.
4. Build the real-output fixture generator; rewrite contract tests; add the TEST_SPEC 4.3/4.5 references.
