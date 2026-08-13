---
id: plugin-confirmation-and-resolution
level: initiative
title: "Plugin Confirmation and Resolution Presentation"
short_code: "RKIT-I-0046"
created_at: 2026-08-13T20:41:38.144836+00:00
updated_at: 2026-08-13T20:41:38.144836+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0044"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: S
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Plugin Confirmation and Resolution Presentation Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. The confirmation surface exists but reports fiction, per the alignment audit (verified against code): `presentConfirmationRequest` hardcodes `sensitive_fields_omitted = True` (`resume_plugin/__init__.py:234`) — asserted unconditionally rather than derived from any actual redaction, and the contract test only checks truthiness so the constant passes. Compounding this, `confirmation_required` is hardcoded `False` in the mapper (`__init__.py:186`), so no host ever learns a confirmation is pending — the presentation surface is unreachable in practice. And there is no answer-capture path to the public resolution workflow because no invocation path exists at all (RKIT-I-0044's gap).

The former dependency on RKIT-I-0045 was artificial and is removed — presenting confirmations does not require the intent-mapping work, only the invocation/run-state path from RKIT-I-0044. Scope note: this is task-sized (one presentation function plus answer routing); it is flagged as a decomposition fold-candidate into RKIT-I-0047 and resized to S.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- `sensitive_fields_omitted` becomes a derived fact: true only when a redaction pass actually removed or withheld fields.
- Hosts know when to present: the confirmation flow consumes the derived `confirmation_required` signal so presentation triggers exactly when workflow state has pending confirmations.
- Captured answers route to the public resolution workflow API with minimal context.

**Non-Goals:**
- Intent-rule mapping and the `confirmation_required` derivation itself — RKIT-I-0045 (this initiative consumes the signal).
- Diff/report/export/audit presentation — RKIT-I-0047 (which shares the derived-redaction rule for `presentAuditSummary`, `__init__.py:309`).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: `sensitive_fields_omitted` in `presentConfirmationRequest` (`__init__.py:234`) is computed from an explicit redaction step: true iff the redaction removed or withheld at least one field, false otherwise. The contract test asserts both branches — closing the truthiness-only loophole.
- R2: Confirmation presentation input binds to the real workflow pending-question DTO shape, not invented field names (RKIT-A-0005 item 5; RKIT-A-0006 surface-realignment authorization).
- R3: The presentation flow is driven by the derived `confirmation_required` signal so the surface is reachable — fixing the dead-surface consequence of the hardcoded `False` (`__init__.py:186`).
- R4: Answer capture marshals question id plus answer to the public resolution workflow API; prompts carry minimal evidence context and never broader career-DB context than the question needs (TEST_SPEC boundary rule).

### Dependencies
- RKIT-I-0044 (Real Plugin Tool Registration and Workflow Delegation): the public-API invocation path and pending-confirmation state source.

### Blocked Status
- Yes: RKIT-I-0044. The previously undeclared transitive ADR block is resolved — RKIT-A-0005 is decided.

## Detailed Design **[REQUIRED]**

ConfirmationPresentation DTO: question identifier, prompt text, answer options where the workflow supplies them, minimal supporting evidence context, `sensitive_fields_omitted` (derived), and the source run identifier for audit linkage.

Redaction mechanism: an explicit redaction step produces the list of removed/withheld field names; `sensitive_fields_omitted` is a function of that list being non-empty. No code path assigns the boolean directly — the constant-assertion pattern the audit flagged becomes structurally impossible.

Answer capture: the host-supplied answer plus question id are passed to the public resolution workflow API; the plugin persists nothing and interprets nothing — yes/no/fact answers are the workflow's to adjudicate.

Migration notes: contract fixtures for confirmation presentation switch from hand-crafted shapes to real workflow pending-question output; contract-test changes are strengthen-only per RKIT-A-0006.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Both-branch redaction tests: a fixture with sensitive fields yields true with those fields absent from the prompt; a fixture with nothing to redact yields false — replacing the truthiness-only check.
- Real-DTO input test: presentation fed actual workflow pending-question output, not invented fixture shapes (the audit's fixture-tuning failure class).
- Boundary test: prompt context contains no career-DB fields beyond the question's evidence set.

## Alternatives Considered **[REQUIRED]**

- Enforce redaction upstream in workflow and keep the plugin boolean constant: rejected — presentation must truthfully report what *it* surfaced (CONTRACT_SURFACE_ALIGNMENT.md:251, "reports reflect domain results"); upstream cannot know what the adapter displayed.
- Merge this work into RKIT-I-0047 immediately: rejected for this re-baseline pass (document continuity and distinct acceptance criteria are preserved), but decomposition should treat it as a fold-candidate into 0047's task set.

## Implementation Plan **[REQUIRED]**

Task-shaped chunks (likely folded into RKIT-I-0047's decomposition):
1. Bind confirmation presentation input to the real workflow pending-question shape.
2. Implement the redaction pass and derived `sensitive_fields_omitted` with both-branch tests.
3. Wire answer routing to the public resolution API plus the minimal-context boundary test.
