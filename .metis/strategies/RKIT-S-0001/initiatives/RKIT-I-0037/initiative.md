---
id: deterministic-match-resolve-and
level: initiative
title: "Deterministic Match, Resolve, and Inspect UX"
short_code: "RKIT-I-0037"
created_at: 2026-08-13T20:41:37.828792+00:00
updated_at: 2026-08-13T20:41:37.828792+00:00
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

# Deterministic Match, Resolve, and Inspect UX Initiative

## Context **[REQUIRED]**

Package: `resume-cli`. This initiative is part of the Resume Kit 2 full product buildout under `RKIT-S-0001`. Current contracts and guardrails pass for the scaffold, but this initiative captures product-depth work before task-level decomposition.

Outcome: CLI exposes deterministic matching, targeted gap resolution, and inspect commands without owning scoring, topic authority, or fact truth.

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
- CLI orchestrates through public APIs only.
- No direct SQLite/table writes or duplicated domain rules.

### Dependencies
- Resume and Job Ingest Orchestration

### Blocked Status
- No

## Detailed Design **[REQUIRED]**

- Command routing
- Workspace artifacts
- Reports/export/audit orchestration

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
