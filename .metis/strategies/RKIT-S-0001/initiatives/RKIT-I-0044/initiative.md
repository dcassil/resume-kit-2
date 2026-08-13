---
id: real-plugin-tool-registration-and
level: initiative
title: "Real Plugin Tool Registration and Workflow Delegation"
short_code: "RKIT-I-0044"
created_at: 2026-08-13T20:41:38.072480+00:00
updated_at: 2026-08-13T20:41:38.072480+00:00
parent: resume-kit-2-full-product-buildout
blocked_by:
  - RKIT-A-0005
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

# Real Plugin Tool Registration and Workflow Delegation Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. This initiative is part of the Resume Kit 2 full product buildout under `RKIT-S-0001`. Current contracts and guardrails pass for the scaffold, but this initiative captures product-depth work before task-level decomposition.

Outcome: Plugin tools are callable in the selected host and delegate to public CLI/workflow APIs without duplicating domain behavior.

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
- Plugin remains an adapter and owns no scoring, schemas, SQLite, ATS sanitation, mutation, or learning behavior.
- Reports include package/schema/config versions and omit sensitive raw data.

### Dependencies
- Host Skill and Instruction Assets

### Blocked Status
- Yes: RKIT-A-0005

## Detailed Design **[REQUIRED]**

- Host manifest/skills/tools
- Conversation mapping and presentation
- Packaging and parity gates

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
