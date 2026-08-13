---
id: full-run-equivalence-audit-and
level: initiative
title: "Full Run Equivalence, Audit, and Recovery"
short_code: "RKIT-I-0040"
created_at: 2026-08-13T20:41:37.929985+00:00
updated_at: 2026-08-13T20:41:37.929985+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0039", "RKIT-I-0023", "RKIT-I-0024", "RKIT-I-0025"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Full Run Equivalence, Audit, and Recovery Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. Nothing in resume-cli drives the workflow state machine today, and audit is synthesized rather than reconstructed:

- `workflow.getNextCheckpoint`/`advanceCheckpoint` are never imported or called anywhere in the package; any command runs in any order (verified: `match` on an empty workspace returns ok/0.0). Vision section 10 "Enforcing workflow checkpoints" has zero implementation, and no sibling initiative claims it — this one does.
- `_run` never calls `_resolve` yet reports RESOLVE_GAPS, and returns `list(CHECKPOINT_ORDER)` unconditionally as its checkpoints (`resume_cli/__init__.py:316-324`, echo at `:324`) — an echo of the workflow constant, not executed-state tracking. The contract test's checkpoint-equality assertion is satisfied by the echo, and the audit trail asserts stages that never ran, violating "Every transition is based on persisted state, validated DTOs, or deterministic package output". The section 14.D resolution loop (resolve until threshold/hard-requirement policy satisfied, rerun match) is absent.
- Audit is synthesized: `_audit_report` regenerates run state via `createRun` at audit time (`resume_cli/__init__.py:347`); run_id derives solely from the config hash (`workflow/__init__.py:40-41`), so distinct runs share identity. No user questions/answers are recorded anywhere. Initial and final scores are the same value read from one match.json (`:352-353`), making DoD 13 ("re-score and explain improvement") impossible. validation_status is mere file existence (`:356`).

RKIT-A-0001 supplies the substrate this initiative consumes: `getMigrationState()` for manifest `careerDbVersion`, and the append-only `interactions` table (`question_asked`, `answer_recorded`, ...) for Q&A reconstruction.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- This is THE initiative that makes the CLI actually drive the workflow state machine. Per-command checkpoint gating: every workflow-ordered command consults `getNextCheckpoint` against persisted run state, fails out-of-order invocations with typed errors, and records completion via `advanceCheckpoint` with its result payload.
- `run` executes the real loop including RESOLVE_GAPS (section 14.D): resolve → rerun match until threshold/hard-requirement policy is satisfied or the user stops; reported checkpoints are exactly the executed, persisted ones — the CHECKPOINT_ORDER echo is deleted.
- Run equivalence is real: `run` and the explicit command sequence produce identical artifacts because both drive the same gated, persisted state machine.
- Audit reconstructs from persisted state only: run identity from the persisted manifest (never regenerated via `createRun` at audit time), initial vs final scores from distinct persisted match artifacts (DoD 13), Q&A history from RKIT-A-0001 interaction records, validation status from RKIT-I-0039's validation artifact contents — not file existence. Manifest `careerDbVersion` comes from `getMigrationState()`.
- Recovery: an interrupted run resumes from persisted checkpoint state; re-executing a completed checkpoint is idempotent per workflow's RKIT-I-0025 semantics.

**Non-Goals:**
- Workflow-package internals — state machine, checkpoint recording, recovery semantics are owned by workflow (RKIT-I-0023/0024/0025); this initiative wires the CLI to those surfaces, it does not reimplement them.
- Resolve UX and interaction-recording call sites — RKIT-I-0037 (this initiative consumes its recorded interactions).
- Multi-job flow and duplicate-question suppression — RKIT-I-0041.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- Every workflow-ordered command is gated: invoking a command whose checkpoint is not next fails with a typed out-of-order error naming the expected checkpoint — kills empty-workspace `match` returning ok/0.0.
- Executed checkpoints are persisted with results and timestamps via `advanceCheckpoint`; `run`'s reported checkpoints are read back from persisted state; a run that never resolved must not report RESOLVE_GAPS (removes `resume_cli/__init__.py:316-324`).
- Two runs with different inputs/answers have distinct persisted run identities; auditing run N reads run N's manifest (removes the `:347` regeneration and the config-hash-only identity at `workflow/__init__.py:40-41`).
- Audit output contains initial score, final score, and per-resolution deltas sourced from separate persisted match artifacts (DoD 13), the Q&A transcript from interaction records, and validation status from artifact contents (replaces `:352-353` and `:356`).
- After a simulated crash mid-run, rerunning completes the remaining checkpoints from persisted state without repeating completed side effects.

### Dependencies
- RKIT-I-0039 (the full command chain must be honest before equivalence/audit over it means anything).
- RKIT-I-0023 Workflow Deterministic Checkpoint State Machine and Policy Gates.
- RKIT-I-0024 Workflow Checkpoint Result Recording, Audit Trail, and Manifest Reconstruction.
- RKIT-I-0025 Workflow Recovery and Idempotency Semantics.

### Blocked Status
- Blocked by RKIT-I-0039, RKIT-I-0023, RKIT-I-0024, RKIT-I-0025 (frontmatter matches). RKIT-A-0001 is decided (migration state, interactions substrate), so the audit inputs are specified; no ADR block remains.

## Detailed Design **[REQUIRED]**

- **Run-state wiring.** `init` (RKIT-I-0035) creates the persisted run manifest through workflow's surface: run id, config hash, `careerDbVersion` from `getMigrationState()`, fixture/template versions. Every command loads the manifest, asks `getNextCheckpoint`, and either proceeds — recording via `advanceCheckpoint` with the command's result DTO — or fails typed. The gating table lives in workflow, not the CLI.
- **Run loop.** `run` iterates `getNextCheckpoint` to terminal: ingest → match → (RESOLVE_GAPS: while decision is resolve_gaps and policy permits, invoke the RKIT-I-0037 resolve flow — interactive over TerminalIO or scripted — then re-match, persisting each match artifact separately) → tailor → validate → export → audit. Each iteration's artifacts and checkpoint records are what audit later reads.
- **Audit reconstruction.** `audit` loads the persisted manifest and checkpoint records and renders: run identity, careerDbVersion, config hash, per-checkpoint results, initial/final scores with per-resolution improvements, the Q&A transcript via `listInteractions` filtered to the run, operation audit (RKIT-I-0038 records), and validation/export evidence (RKIT-I-0039 artifacts). No `createRun`, no synthesis: missing state makes audit report a reconstruction failure — itself a meaningful signal.
- **Recovery.** On startup with an incomplete manifest, commands resume from `getNextCheckpoint`; completed checkpoints are skipped per workflow idempotency rules; an explicit `--restart` re-inits. Recovery semantics are delegated to RKIT-I-0025; the CLI contributes faithful persistence and re-entry only.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Strengthen the run-equivalence spec so it cannot be satisfied by echoing CHECKPOINT_ORDER — the exact looseness the audit flagged: assert persisted per-checkpoint records (results, timestamps) exist for every reported checkpoint, and that a scripted run with zero unresolved gaps does NOT report RESOLVE_GAPS.
- Out-of-order gating tests: `match` before ingest fails typed; empty-workspace match can no longer return ok/0.0.
- Resolution-loop test: fixture with unresolved gaps plus scripted answers → at least two persisted match artifacts with a strictly improved final score; audit explains the improvement (DoD 13 becomes provable).
- Audit reconstruction tests: two runs with different scripted answers yield distinct run identities; auditing run A after run B reports A's data; deleting a checkpoint record makes audit report reconstruction failure (no silent synthesis).
- Crash-recovery E2E: kill after checkpoint N; rerun completes N+1..end from persisted state; completed side effects are not repeated.
- Run-vs-explicit-commands artifact equality on the smoke fixture (normalized comparison).

## Alternatives Considered **[REQUIRED]**

- CLI-owned checkpoint tracking (its own state file) instead of workflow surfaces: rejected — workflow owns the cross-package state machine and audit; a parallel CLI tracker is an alternate truth rule, exactly what CONTRACT_SURFACE_ALIGNMENT.md forbids, and would fork recovery semantics.
- Gate only `run`, leave individual commands ungated: rejected — vision section 10 assigns checkpoint enforcement to the CLI command surface; ungated commands mutate workspace state behind the manifest's back, corrupting both equivalence and audit.
- Keep audit synthesis but enrich it (regenerate more state at audit time): rejected — that is the current gamed behavior; the Audit Gate requires reconstruction from persisted state, and synthesis makes distinct runs indistinguishable (config-hash identity) by construction.

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Manifest lifecycle in the CLI: create at init (careerDbVersion via getMigrationState), load/validate on every command.
2. Per-command gating via getNextCheckpoint/advanceCheckpoint with typed out-of-order errors.
3. Run loop with the RESOLVE_GAPS iteration and separately persisted match artifacts.
4. Audit reconstruction from persisted manifest/checkpoints/interactions/artifacts; delete createRun-at-audit and the checkpoint echo.
5. Recovery re-entry per workflow idempotency semantics plus `--restart`.
6. TEST_SPEC strengthening: persisted-checkpoint assertions, gating cases, DoD 13 improvement case, distinct-identity audit cases, crash-recovery E2E.
