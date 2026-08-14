---
id: workflow-backed-smoke-and-e2e
level: initiative
title: "Workflow-Backed Smoke and E2E Acceptance Coverage"
short_code: "RKIT-I-0028"
created_at: 2026-08-13T20:41:37.540121+00:00
updated_at: 2026-08-13T20:41:37.540121+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0025", "RKIT-I-0040"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Workflow-Backed Smoke and E2E Acceptance Coverage Initiative

## Context **[REQUIRED]**

Package: `workflow`. Baseline honesty first: tests/e2e is empty and the 29-line smoke harness contains zero workflow assertions, while workflow/TEST_SPEC.md:130-146 claims smoke and E2E coverage — interruption recovery, Job B career-DB reuse, audit reconstruction, adversarial rejection — that exists nowhere in the suite. This initiative builds acceptance coverage from zero and reconciles the spec's coverage claims with reality. Baseline facts the coverage must respect:

- The nine E2E proof obligations (workflow/TEST_SPEC.md:134-146): complete Job A run, targeted interview, valid tailoring, adversarial rejection, render validation, audit reconstruction, second Job B run on the same career DB, preference-learning boundaries, interruption recovery.
- The Job B and audit-reconstruction proofs are impossible until RKIT-I-0022 fixes the run-identity collision — same-config runs currently share one run_id and overwrite each other's persisted state (workflow/__init__.py:41).
- Acceptance cannot prove "a real deterministic orchestration layer" while resume-cli never calls the state machine: `resume run` reports the full checkpoint list without driving it (resume-cli/resume_cli/__init__.py:316-324). The cross-package prerequisite is now declared: RKIT-I-0040 makes the CLI actually drive workflow's checkpoints, and this initiative is blocked on it.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- E2E suites covering all nine TEST_SPEC proof obligations against the CLI-driven workflow (post RKIT-I-0040), running on fixtures with deterministic agent fakes.
- The smoke harness gains real workflow assertions: unique run created, checkpoints actually traversed in order, manifest reconstructable and schema-valid, honest failure on a gate violation.
- workflow/TEST_SPEC.md coverage sections reconciled: every claimed proof maps to a runnable test (claims are strengthened into tests, never weakened away — RKIT-A-0006).
- Preference-learning boundary coverage exercises the RKIT-A-0001 interactions substrate: interaction records append-only and structurally unable to alter fact verification.

**Non-Goals:**
- The CLI wiring itself — RKIT-I-0040.
- CLI release evidence and packaging proof — RKIT-I-0041; this initiative owns workflow-package acceptance suites only.
- Fixing workflow defects — RKIT-I-0022 through RKIT-I-0027 deliver the behavior; this initiative proves it and must not paper over gaps they leave.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. tests/e2e gains suites for the nine obligations of workflow/TEST_SPEC.md:134-146: (a) Job A INIT->COMPLETE including the post-gap-resolution tail (regression on the historical RESOLVE_GAPS deadlock); (b) targeted interview honoring deterministic topic-selection state; (c) valid tailoring with grounded operations; (d) adversarial rejection — scripted hallucinated proposals must end rejected and completion must fail while any is unrejected (RKIT-I-0023 gate); (e) render validation including the overflow loop-back (RKIT-I-0027); (f) audit reconstruction — reconstructRunManifest after a process restart equals the run's recorded truth; (g) Job B second run on the same career DB with a distinct run_id and both audit trails intact; (h) preference-learning boundaries — RKIT-A-0001 interaction records never alter facts verification state; (i) interruption recovery at the five TEST_SPEC:113-119 points (RKIT-I-0025 semantics).
2. Replace the zero-assertion smoke harness with checkpoint-traversal, manifest-validity, and honest-failure assertions.
3. E2E assertions read persisted run state and written artifacts, never CLI-printed summaries — the audit proved the current `resume run` output is printable without doing the work, so printed output is not acceptable evidence.
4. All acceptance runs use deterministic agent fakes from fixtures; no live model calls.
5. Every coverage claim remaining in workflow/TEST_SPEC.md:130-146 maps 1:1 to an implemented test.

### Dependencies
- RKIT-I-0025 (and transitively the whole 0022-0027 chain): the recovery, loop, and audit behavior these suites prove.
- RKIT-I-0040 (cross-package, now declared): the CLI must drive the state machine for acceptance to test the product path rather than a package-only simulation.
- RKIT-A-0001 (decided): the interactions substrate the preference-learning boundary suite exercises.

### Blocked Status
- Blocked by RKIT-I-0025 and RKIT-I-0040 (frontmatter blocked_by enforces both). No ADR blocks remain.

## Detailed Design **[REQUIRED]**

**Suite layout.** tests/e2e organized one module per proof obligation, sharing a workspace factory that builds a fixture workspace (base resume, job models, config) and a scripted agent fake whose proposals — including deliberately hallucinated ones for the adversarial suite — come from fixture files, keeping runs deterministic and provider-free.

**Process-restart helper.** Audit-reconstruction and interruption suites run the workflow in a subprocess, kill it at a designated checkpoint, then reconstruct/recover in a fresh process — proving durability claims against disk state, not in-memory residue.

**Job A/B pairing.** The Job B suite reuses Job A's career DB and identical config, asserting distinct run_ids (RKIT-I-0022), both persisted run states intact, and both manifests independently reconstructable.

**Evidence discipline.** Every suite asserts on `.workflow/runs` state, written logs (operations.jsonl, questions.jsonl), and rendered artifacts. CLI exit codes/output are checked only as UX, never as proof of orchestration.

**Spec reconciliation.** A final pass edits workflow/TEST_SPEC.md:130-146 so each claim names its implementing test; any obligation that cannot be implemented yet is escalated, not silently dropped (RKIT-A-0006: strengthen or preserve, never weaken).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

This initiative is itself test work; its strategy is scope and honesty:
- Build order: smoke first (fast feedback on the wired CLI path), then Job A full-path, then the artifact-heavy suites (render/overflow, audit reconstruction), then Job B, adversarial, preference-learning, and the five-point interruption matrix.
- The audit-flagged TEST_SPEC issue owned here: the Smoke/E2E Coverage sections (workflow/TEST_SPEC.md:130-146) assert proof obligations with no corresponding tests anywhere, conflicting with the Required Gates intent (CONTRACT_SURFACE_ALIGNMENT.md:300-366); this initiative closes that spec-vs-suite gap and is the group's guard against it reopening.
- Anti-gaming rule inherited from the audit: no acceptance test may pass on printed summaries or self-asserted evidence; persisted state and written artifacts only.

## Alternatives Considered **[REQUIRED]**

- **Write E2E directly against workflow's Python surface, skipping the CLI.** Rejected as the primary path: vision section 10 requires the product path to use the same checkpoints, and package-level E2E would certify orchestration the product still bypasses — the exact defect the audit found. A thin package-level layer may exist for speed but cannot substitute for CLI-driven proofs.
- **Descope to smoke-only now and defer E2E.** Rejected: the nine obligations are Required Gates material (CONTRACT_SURFACE_ALIGNMENT.md:300-366); deferring reproduces the current spec-claims-without-tests state this initiative exists to end.
- **Use live agent calls for the adversarial suite.** Rejected: non-deterministic, provider-dependent, and unnecessary — scripted hallucinated proposals from fixtures exercise the rejection gates identically and reproducibly.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. Honest smoke harness: traversal, manifest validity, honest-failure assertions on the CLI-driven path.
2. E2E scaffolding: workspace factory, fixture sets, deterministic agent fakes, process-restart helper.
3. Job A full-path, targeted-interview, and tailoring suites.
4. Render/overflow, audit-reconstruction, and Job B suites.
5. Adversarial-rejection and preference-learning boundary suites.
6. Five-point interruption-recovery matrix and the TEST_SPEC:130-146 reconciliation pass.
