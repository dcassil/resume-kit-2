---
id: workflow-recovery-and-idempotency
level: initiative
title: "Workflow Recovery and Idempotency Semantics"
short_code: "RKIT-I-0025"
created_at: 2026-08-13T20:41:37.443233+00:00
updated_at: 2026-08-16T18:46:19.006663+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0027]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: workflow-recovery-and-idempotency
---

# Workflow Recovery and Idempotency Semantics Initiative

## Context **[REQUIRED]**

Package: `workflow`. This initiative has been reordered: it now follows RKIT-I-0027 because three of the five contract interruption points (proposed operations, partially applied operation sequence, render overflow — workflow/TEST_SPEC.md:113-119) only exist once the resolution loop (RKIT-I-0026) and the tailoring/render orchestration (RKIT-I-0027) are in place. The previous sequencing made recovery unimplementable and untestable as ordered.

What genuinely exists: dedupe tracking of already_applied_operations / already_asked_questions / already_written_facts (workflow/__init__.py:134-153, 198-212). What is cosmetic, verified by the alignment audit:

- **Integrity is declared, never checked.** recoverRun hardcodes `'transactional_integrity': 'valid'` with no career-store consultation or any check at all (workflow/__init__.py:211) — workflow asserting a store truth it never verified, a form of the alternate-truth rules workflow is forbidden to own (CONTRACT_SURFACE_ALIGNMENT.md:43).
- **Reruns are hardcoded and unenforced.** required_reruns is a hardcoded set-membership check yielding at most `['FINAL_MATCH']` (workflow/__init__.py:202), with nothing enforcing that the rerun happens before COMPLETE (workflow/__init__.py:198-212); no grounding-audit/ATS/render-validation reruns, no render-overflow interruption handling.
- **recoverRun invents state.** For a nonexistent run it silently fabricates `{'run_id', 'current_checkpoint': 'INIT'}` instead of reporting an error (workflow/__init__.py:200).
- None of the five interruption points or the recovery assertions (career DB transactionally valid, base resume unchanged, rejected operations stay rejected) have any implementation.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- recoverRun verifies instead of declares: transactional integrity via career-store's decided surfaces (getMigrationState() and the store's transaction-validity surface per RKIT-A-0001), base.json hash unchanged, rejected operations still rejected.
- required_reruns computed from the checkpoint at interruption and enforced: COMPLETE is unreachable until every computed rerun has re-executed with a fresh recorded result.
- recoverRun on a nonexistent run returns a typed error, never fabricated state.
- All five TEST_SPEC interruption points handled with no duplicate questions, fact writes, or applied operations.

**Non-Goals:**
- The loops recovery re-enters — RKIT-I-0026 (resolution) and RKIT-I-0027 (tailoring/render) deliver them; this initiative deliberately follows both.
- The audit-event and log persistence substrate recovery reads — RKIT-I-0024.
- E2E interruption-recovery proofs — RKIT-I-0028.
- Career-store transaction implementation — career-store owns it; workflow only consults its public surface.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Delete the hardcoded `'transactional_integrity': 'valid'` (workflow/__init__.py:211): recovery must consult career-store — migration/schema state via getMigrationState() (RKIT-A-0001) and the store's transaction-validity surface — and report the actual result with evidence, satisfying the recovery assertion that "career DB remains transactionally valid" is proven rather than declared.
2. Replace the hardcoded FINAL_MATCH-only required_reruns (workflow/__init__.py:202): reruns are computed from the checkpoint at interruption (e.g., interruption during a partially applied operation sequence requires grounding audit plus final match; during render overflow requires re-render plus render validation), and assertCanComplete refuses completion until each computed rerun has a fresh post-recovery recorded result (fixes the unenforced-rerun gap at workflow/__init__.py:198-212).
3. recoverRun (workflow/__init__.py:200) returns a typed RunNotFound error for unknown run ids; it never fabricates state.
4. Handle the five interruption points of workflow/TEST_SPEC.md:113-119 (job ingest, user verification, proposed operations, partially applied operation sequence, render overflow) using RKIT-I-0024's persisted logs and RKIT-I-0026/0027 loop state; recovery must not re-ask answered questions, re-write facts, or re-apply applied operations.
5. Recovery asserts base-resume immutability by sha256 comparison against the manifest's base_resume_hash (validated field from RKIT-I-0022) and asserts every rejected operation id in operations.jsonl was never subsequently applied.

### Dependencies
- RKIT-I-0027 (and transitively RKIT-I-0026/0024/0023/0022): the orchestration loops and persisted logs that define and record the interruption points recovery must handle.
- RKIT-A-0001 (decided): getMigrationState() and the store surfaces integrity verification consults.

### Blocked Status
- Blocked by RKIT-I-0027 (frontmatter blocked_by enforces the reordering). No ADR blocks remain; the career-store contract this initiative needs is decided in RKIT-A-0001.

## Detailed Design **[REQUIRED]**

**Recovery contract.** `recoverRun(run_id)` returns a typed result: {checkpoint, integrity: {career_db, base_resume, rejected_operations}, required_reruns, resumable}. Each integrity field carries verified/failed plus an evidence ref — never a bare literal. Unknown run_id raises RunNotFound.

**Integrity verification.** career_db: getMigrationState() must report the schema version recorded as the run's careerDbVersion with no pending migrations, and the store's transaction-validity surface must report clean (RKIT-A-0001). base_resume: sha256 of base.json compared to the manifest's base_resume_hash. rejected_operations: operations.jsonl (RKIT-I-0024) scanned; any rejected id later applied is an integrity failure that blocks resumption.

**Rerun computation and enforcement.** A deterministic map from interruption checkpoint to rerun set, persisted into run state at recovery time. assertCanComplete gains a recovery gate: every required rerun must have a recorded result with a timestamp later than the recovery event. This makes rerun-before-COMPLETE structural rather than advisory.

**Idempotent resumption.** The existing dedupe registries (already_asked_questions, already_written_facts, already_applied_operations) become the recovery input: resumed loops consult them before asking, writing, or applying. RKIT-I-0026's asked-question registry and RKIT-I-0027's per-stage persisted state supply the checkpoint-local detail.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract-test matrix over all five interruption points (today zero such tests exist despite TEST_SPEC.md:113-119): simulate interruption at each point, recover, assert no duplicate question/fact/operation and the correct computed rerun set.
- Regression for the hardcoded integrity literal: with a store double reporting invalid transaction state, recovery must report failure — proving the store is actually consulted (workflow/__init__.py:211 regression).
- Contract test: recoverRun on an unknown run_id raises RunNotFound (workflow/__init__.py:200 regression).
- Contract test: COMPLETE is blocked until every computed rerun has a fresh post-recovery result (workflow/__init__.py:198-212 regression).
- TEST_SPEC strengthening (audit-flagged): the recovery section's assertions currently have no corresponding tests anywhere; the spec's five-point matrix gains explicit per-point cases so its claims match the suite.

## Alternatives Considered **[REQUIRED]**

- **Best-effort recovery that warns instead of blocking completion.** Rejected: the recovery assertions are gate material; warning-only reproduces exactly the cosmetic pattern the audit flagged (declared-valid integrity, unenforced reruns).
- **A workflow-owned recovery journal/WAL duplicating store transaction tracking.** Rejected: transactional truth belongs to career-store; workflow consulting the owner's public surface respects the alternate-truth prohibition (CONTRACT_SURFACE_ALIGNMENT.md:43) and avoids a second source of truth that can drift.
- **Keep FINAL_MATCH-only reruns as a conservative default.** Rejected: it is not conservative — it silently skips grounding/ATS/render-validation reruns after exactly the interruptions that invalidate them.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. Typed recoverRun contract: RunNotFound, structured integrity result, removal of invented state.
2. Integrity verification against career-store surfaces (RKIT-A-0001), base-hash comparison, rejected-operation scan.
3. Computed rerun sets per interruption checkpoint plus the completion-gate enforcement.
4. Idempotent resumption over RKIT-I-0026/0027 loop state, wired to the dedupe registries.
5. Five-point interruption contract-test matrix and TEST_SPEC recovery-section strengthening.