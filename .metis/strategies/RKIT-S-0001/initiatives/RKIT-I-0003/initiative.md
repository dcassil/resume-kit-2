---
id: resume-core-selection-planning-and
level: initiative
title: "Resume-Core Selection Planning And Structural Constraints"
short_code: "RKIT-I-0003"
created_at: 2026-08-13T20:41:36.874684+00:00
updated_at: 2026-08-13T20:41:36.874684+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
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

# Resume-Core Selection Planning And Structural Constraints Initiative

## Context **[REQUIRED]**

Package: `resume-core`. This initiative is part of the Resume Kit 2 full product buildout under `RKIT-S-0001`. Current contracts and guardrails pass for the scaffold, but this initiative captures product-depth work before task-level decomposition.

Outcome: Deterministic, audit-ready resume content selection plans that improve relevance while preserving base immutability and enforcing section, skill, experience, and bullet constraints.

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
- Agent output cannot override structural maxima.
- Plans preserve requirement/fact traceability when supplied.

### Dependencies
- Resume-Core Deterministic Requirement Resolution And Match Scoring

### Blocked Status
- No

## Detailed Design **[REQUIRED]**

- Ranked content model
- Constraint handling
- Selection-plan fixture observations

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
