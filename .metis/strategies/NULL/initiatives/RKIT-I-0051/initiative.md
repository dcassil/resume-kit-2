---
id: executable-release-gate-e2e
level: initiative
title: "Executable Release Gate: E2E, Persistence, Recovery, Migration, and Snapshot Coverage"
short_code: "RKIT-I-0051"
created_at: 2026-08-13T21:58:49.672624+00:00
updated_at: 2026-08-13T21:58:49.672624+00:00
parent: RKIT-S-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: executable-release-gate-e2e
---

# Executable Release Gate: E2E, Persistence, Recovery, Migration, and Snapshot Coverage Initiative

## Context **[REQUIRED]**

The 2026-08-13 alignment audit found the release-blocking test strategy roughly half paper. What genuinely executes: the PR gate (188 contract/boundary/guardrail tests) and the smoke harness (tools/run_smoke.py), both green and adversarially meta-tested. What exists only as declaration: tests/unit, tests/integration, tests/e2e, and tests/snapshots are empty (.gitkeep only); no release-candidate runner exists (run_gate.py has no release flag; the CI job named "E2E release-candidate gate" runs no E2E); the mandatory Job B persistent-learning proof (E2E Phase 15, release blocker "lost_learned_facts_between_jobs") references a fixture no test loads; the duplicate-questioning blocker has no executable coverage; fixtures/migrations/ is an empty placeholder with no fixture-content spec; the 13 fixtures/expected/*.json "snapshots" contain prose sentences instead of comparable output data; 4 of 5 invalid-operation honesty fixtures are never executed through resume_core.validateChange; tool_manifest.json declares capabilities (migration_checkers, render_parse_back_validators, audit_validators, snapshot_review_helpers) with no implementing tools; and --future-contract is a vestigial alias of the PR gate (identical module lists). Two spec conflicts feed this: SMOKE_TEST.md's fixture set (resume-smoke.*, job-smoke.txt, SaaS preferred) diverges from the fixtures the harness actually uses (resume-main.txt, Job A with SaaS required), and two documents name different "canonical" test commands.

This initiative makes the documented release tiers executable. Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Every release blocker listed in PROJECT_STRUCTURE_AND_TEST_STRATEGY.md has an executable test that fails when the invariant is violated.
- A real release-candidate gate exists as a runnable command and CI job: full E2E (all 17 phases of E2E_TEST.md), renderer parse-back checks, and migration upgrade tests.
- Deterministic outputs are snapshot-compared against reviewed data baselines, so cross-commit score drift is a deliberate, reviewed change.
- All five honesty fixtures execute through resume_core.validateChange; hallucination injection moves from product code to the test flow (SMOKE_TEST.md step 10 assigns it to the test).
- The declared-but-fake capability surface is closed: tool_manifest capabilities either gain implementing tools or are removed; --future-contract either becomes a distinct gate or is retired.

**Non-Goals:**
- Building the product behavior the gates exercise (owned by the package initiatives; the full E2E tier depends on RKIT-I-0041's completed CLI flow).
- Weakening any existing assertion, fixture truth, guardrail, or manifest (strengthening only; protected-surface edits authorized by RKIT-A-0006 solely for contract realignment).
- Live-model calls inside gates (RKIT-A-0003: official gates run on the deterministic fake adapter).

## Requirements

### System Requirements
- REQ-001: Data snapshots — replace the 13 prose-stub fixtures/expected/*.json with actual normalized-resume / match-result / selection-plan / run-manifest output data (schema-versioned, config-hashed, reviewed), and add tests that compare live outputs to them (fixtures/TEST_SPEC.md lines 147-163 already require this; its weak metadata-only validation clause is strengthened to match).
- REQ-002: Honesty fixture execution — all five fixtures/operations/invalid-*.json run through resume_core.validateChange in the PR tier and must be rejected (currently only unsupported-scale executes; title inflation, management scope, years inflation, and Azure-as-AWS overreach never run).
- REQ-003: Hallucination-rejection evidence comes from the test flow injecting the invalid operation into the proposal path — the CLI's self-injection (_hallucinated_operation, removed by RKIT-I-0038) may not be what the smoke audit asserts against.
- REQ-004: Job B persistence test — an executable test reuses career.db from a Job A session, matches fixtures/jobs/job-b-senior-full-stack-engineer.txt, and asserts AWS/GraphQL resolve from user_verified facts with evidence chains, without re-asking (E2E Phase 15; Persistence Gate).
- REQ-005: Duplicate-questioning test — asserts already-verified facts are not re-asked across sessions absent new specificity (uses the RKIT-A-0001 interactions history).
- REQ-006: Recovery tests — the five interruption points of E2E Phase 17 (job ingest, user verification, proposed operations, partially applied sequence, render overflow) each have a resume-from-persisted-state test.
- REQ-007: Migration fixtures and checker — fixtures/TEST_SPEC.md gains a migration fixture content spec (a previous-schema career.db plus expected post-migration state); a migration-checker tool implements the four cases in tools/TEST_SPEC.md lines 47-52 (fresh migrate, idempotent re-run, upgrade-from-previous, destructive-migration failure), replacing the empty fixtures/migrations/ placeholder.
- REQ-008: Release-candidate runner — run_gate.py gains a release-candidate mode wired into suite_manifest.json runner_commands and CI; the "E2E release-candidate gate" workflow actually runs the E2E tier.
- REQ-009: Unit tier — the empty tests/unit gains the deterministic unit cases the package TEST_SPECs enumerate (starting with resume-core's ~60), and the PR gate's declared categories (unit, deterministic_scoring_fixtures, hallucination_rejection_fixtures) map to real modules.
- REQ-010: Manifest honesty — tool_manifest.json capabilities without implementing tools are implemented or removed; tools_guardrails gains a check that every declared capability has an implementing tool; --future-contract becomes a distinct gate or is removed from docs and manifests.
- REQ-011: Spec reconciliation — SMOKE_TEST.md's fixture set is reconciled with the fixtures the harness uses (including the SaaS preferred-vs-required truth case, which must be exercised), and the canonical-command ambiguity between PROJECT_STRUCTURE_AND_TEST_STRATEGY.md and tests/TEST_SPEC.md is resolved to one command.
- NFR-001: All gates remain deterministic (fake adapter per RKIT-A-0003, fixed fixtures, no wall-clock or network dependence).
- NFR-002: The DOCX release assertion verifies a real .docx artifact, not a .docx.json wrapper.

## Detailed Design **[REQUIRED]**

**Tiers.** The initiative delivers in two waves keyed to product readiness:

*Wave 1 — executable now (no product-code prerequisites):* data snapshots against current deterministic outputs (REQ-001); honesty-fixture execution through validateChange (REQ-002); migration fixture spec + checker tool (REQ-007); unit tier scaffolding and the resume-core unit cases whose behavior already exists (REQ-009 partial); manifest honesty (REQ-010); spec reconciliation (REQ-011). Wave 1 will surface currently-hidden failures (e.g. the Azure-as-AWS fixture will fail against today's store) — those failures are the point: they become the red TDD baseline for the package initiatives, not reasons to weaken the fixture.

*Wave 2 — after RKIT-I-0041 (working CLI flow):* the 17-phase E2E suite in tests/e2e (REQ-003/004/005/006), the release-candidate runner + CI wiring (REQ-008), and the remaining unit/integration cases for behavior delivered by the package initiatives.

**Snapshot mechanics.** Each expected/*.json becomes {schema_version, config_hash, data: <actual output object>}; a shared comparator asserts deep equality with a documented update procedure (regenerate + human review + commit). The existing prose "expected_observations" move into a comment field so review intent is preserved.

**Release-candidate gate shape.** `run_gate.py --release-candidate` = main gate + tests/e2e discovery + migration checker + renderer parse-back suite; suite_manifest.json runner_commands gains the command; .github/workflows/release-candidate.yml runs it (renaming the current job honestly until then).

**Ownership boundary.** This initiative owns test/tool/fixture/spec infrastructure only. Product defects the new gates expose are fixed by the owning package initiatives; this initiative may mark such tests expected-fail ONLY with an explicit link to the owning initiative, never silently.

## Testing Strategy

This initiative IS the testing initiative for the release tiers; its own verification is meta: each new gate must be shown to fail when its invariant is deliberately violated (mutation-style probes, mirroring the existing boundary-suite pattern of injecting violations against guardrails), and the PR gate must stay green throughout Wave 1 except for the documented red-baseline fixtures noted above.

## Alternatives Considered **[REQUIRED]**

- **Fold this work into each package initiative's testing strategy**: rejected — the audit showed exactly this diffusion left the release tier unowned; cross-package tiers (E2E, release runner, snapshots, migration fixtures) need a single owner with a coherent gate design.
- **Keep declarative manifests and add coverage later**: rejected — declared-but-unexecutable capabilities are how a 25-55%-complete implementation logged as "complete"; manifest honesty is a prerequisite for trusting any future green gate.
- **Write the full E2E suite now against the current implementation**: rejected — the canonical workflow is not traversable end-to-end yet (workflow loop deadlock, CLI checkpoint bypass), so E2E written now would either fail wholesale or be tuned to broken behavior; Wave 2 sequencing after RKIT-I-0041 avoids both.

## Implementation Plan **[REQUIRED]**

1. Wave 1a — snapshot conversion + comparator, honesty-fixture execution, manifest honesty (REQ-001, 002, 010).
2. Wave 1b — migration fixture spec + checker tool, unit-tier scaffolding + existing-behavior unit cases (REQ-007, 009 partial).
3. Wave 1c — spec reconciliation edits to SMOKE_TEST.md fixture set and canonical command (REQ-011).
4. Wave 2a — E2E phases 1-14 against the completed CLI flow, then phases 15-17 (Job B, preference boundaries, recovery) (REQ-003, 004, 005, 006).
5. Wave 2b — release-candidate runner + CI wiring; DOCX real-artifact assertion (REQ-008, NFR-002).

Task decomposition happens after this initiative passes design review; Wave 1 tasks have no cross-initiative blockers, Wave 2 tasks declare RKIT-I-0041.