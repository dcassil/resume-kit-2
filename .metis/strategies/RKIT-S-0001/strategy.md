---
id: resume-kit-2-full-product-buildout
level: strategy
title: "Resume Kit 2 Full Product Buildout"
short_code: "RKIT-S-0001"
created_at: 2026-08-13T20:32:54.704604+00:00
updated_at: 2026-08-13T20:32:54.704604+00:00
parent: resume-tailoring-platform
blocked_by: []
archived: false

tags:
  - "#strategy"
  - "#phase/shaping"
  - "#strategy"
  - "#phase/shaping"


exit_criteria_met: false
risk_level: medium
stakeholders: []
strategy_id: NULL
initiative_id: NULL
---

# Resume Kit 2 Full Product Buildout Strategy

## Problem Statement **[REQUIRED]**

The repository has a contract-first scaffold whose current gates pass, but the product vision requires production-depth behavior across eight package surfaces. The next planning milestone is to capture the initiatives needed to move from scaffold-complete to product-complete without decomposing into implementation tasks yet.

## Success Metrics **[REQUIRED]**

- Every package has Metis initiatives covering remaining product-depth work.
- Open product/runtime decisions are captured as ADR blockers before task decomposition.
- No initiative duplicates existing Metis work.
- No code implementation is mixed into planning.

## Solution Approach **[REQUIRED]**

Use the Agent Kit decomposition model adapted to Metis: Epic/Feature maps to initiative, and leaf task maps to task. This pass creates initiatives only; task decomposition comes later after blockers are resolved.

## Scope **[REQUIRED]**

**In Scope:**
- Initiatives for `resume-core`, `career-store`, `career-mcp`, `workflow`, `resume-agent`, `resume-render`, `resume-cli`, and `resume-plugin`.
- ADR blockers for missing runtime, host, policy, or contract decisions.

**Out of Scope:**
- Task decomposition.
- Code changes.
- Weakening tests, fixtures, guardrails, or surface manifests.

## Risks & Unknowns **[REQUIRED]**

- Some runtime choices are intentionally unresolved and must be decided through ADRs.
- Downstream package initiatives depend on upstream package DTO and workflow maturity.
- Metis strategy support is used as the required parent container even though the project config originally emphasized initiatives.

## Implementation Dependencies **[REQUIRED]**

The build order remains: resume-core, career-store, career-mcp, workflow, resume-agent, resume-render, resume-cli, resume-plugin. Initiative planning can happen in parallel, but implementation should follow dependency ownership.

## Change Log **[REQUIRED]**

### Initial Strategy
- **Change**: Created strategy container and initiative/ADR planning set.
- **Rationale**: Metis requires a strategy parent for initiatives, and the user requested initiative-only planning for all eight build items.
- **Impact**: Establishes planning scope without task decomposition or code changes.

### 2026-08-13 Re-Baseline
- **Change**: All six ADRs (RKIT-A-0001..0006, including the new RKIT-A-0006 contract-drift decision) moved to decided; all 49 initiatives rewritten against the 2026-08-13 alignment audit with accurate current-state deltas, known-defect scope, machine-readable blocked_by dependency graphs, corrected orderings (artificial serializations removed), and rescopes (RKIT-I-0009 verification/closure, RKIT-I-0033 PDF-unsupported policy per RKIT-A-0004); added RKIT-I-0051 to own the executable release-gate tier (E2E, Job B persistence, recovery, migration, snapshots), which no prior initiative covered.
- **Rationale**: The initiatives were authored concurrently with the 2026-08-12/13 implementation waves and still described a pre-implementation scaffold; the audit showed green gates masking 25-55% product depth, undeclared ADR blockers, and boilerplate documents that could not guide decomposition. The success metric "open decisions are captured as ADR blockers" was also violated by the undecided contract-drift question, now resolved by RKIT-A-0006.
- **Impact**: Every initiative is decomposition-ready pending design review; the dependency graph is machine-readable; remediation of verified defects is explicit initiative scope rather than invisible debt.
