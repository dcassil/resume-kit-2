---
id: conflict-audit-recovery-and
level: initiative
title: "Conflict, Audit, Recovery, and Optional Preference History"
short_code: "RKIT-I-0008"
created_at: 2026-08-13T20:41:36.985858+00:00
updated_at: 2026-08-13T20:41:36.985858+00:00
parent: resume-kit-2-full-product-buildout
blocked_by:
  - RKIT-A-0001
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Conflict, Audit, Recovery, and Optional Preference History Initiative

## Context **[REQUIRED]**

Package: `career-store`. This initiative is part of the Resume Kit 2 full product buildout under `RKIT-S-0001`. Current contracts and guardrails pass for the scaffold, but this initiative captures product-depth work before task-level decomposition.

Outcome: Career-store represents contradictions, retries, interruptions, audit events, and optional preference history without overwriting truth.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Deliver the stated outcome through the owning package public surface.
- Preserve the product rule that agents propose while deterministic code owns facts, state, scoring, constraints, mutations, provenance, and truth.
- Keep contract, boundary, guardrail, smoke, and E2E expectations aligned.

**Non-Goals:**
- No task-level breakdown in this initiative document.
- No code implementation in this planning pass.
- No weakening of tests, fixtures, guardrails, or surface manifests.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- Conflicting years or title claims create conflict records.
- Preference learning cannot upgrade fact verification.

### Dependencies
- Relationship-Aware Matching and Cross-Job Reuse

### Blocked Status
- Yes: RKIT-A-0001

## Detailed Design **[REQUIRED]**

- Conflict lifecycle
- Interaction/audit persistence
- Retry/idempotency metadata

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Add or expand package contract tests for the described behavior.
- Keep package boundary guardrails passing.
- Add smoke/E2E fixture assertions where this initiative affects cross-package behavior.
- Use the canonical package gate from IMPLEMENTATION_PLAN.md before marking complete.

## Alternatives Considered **[REQUIRED]**

- Keep the current contract scaffold only: rejected because the vision docs require production-depth behavior beyond green scaffolding.
- Move behavior into an adapter or downstream package: rejected unless that package owns the behavior in CONTRACT_SURFACE_ALIGNMENT.md.

## Implementation Plan **[REQUIRED]**

This document stops at initiative scope. During the next planning phase, decompose this initiative into Metis tasks only after blockers are resolved and package ownership is confirmed.
