---
id: relationship-aware-matching-and
level: initiative
title: "Relationship-Aware Matching and Cross-Job Reuse"
short_code: "RKIT-I-0007"
created_at: 2026-08-13T20:41:36.962447+00:00
updated_at: 2026-08-13T20:41:36.962447+00:00
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

# Relationship-Aware Matching and Cross-Job Reuse Initiative

## Context **[REQUIRED]**

Package: `career-store`. This initiative is part of the Resume Kit 2 full product buildout under `RKIT-S-0001`. Current contracts and guardrails pass for the scaffold, but this initiative captures product-depth work before task-level decomposition.

Outcome: Career-store finds candidate matches through exact facts, aliases, equivalents, related facts, possible matches, missing states, and conflicts while reusing learned facts across jobs.

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
- Azure cannot satisfy AWS as exact proof.
- Job B reuses Job A verified AWS/GraphQL facts.

### Dependencies
- Evidence-Backed Fact and Verification Lifecycle

### Blocked Status
- No

## Detailed Design **[REQUIRED]**

- Relationship policy
- Candidate match DTOs
- Job match persistence

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
