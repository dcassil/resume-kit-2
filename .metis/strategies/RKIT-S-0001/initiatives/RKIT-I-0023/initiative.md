---
id: workflow-deterministic-checkpoint
level: initiative
title: "Workflow Deterministic Checkpoint State Machine and Policy Gates"
short_code: "RKIT-I-0023"
created_at: 2026-08-13T20:41:37.382760+00:00
updated_at: 2026-08-15T03:12:29.746945+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0022]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: workflow-deterministic-checkpoint
---

# Workflow Deterministic Checkpoint State Machine and Policy Gates Initiative

## Context **[REQUIRED]**

Package: `workflow`. The state-machine skeleton is real: ordered checkpoint blocking, per-checkpoint evidence keys, determinism_key hashing, and completion-gate routing exist (workflow/__init__.py:74-131, 215-232) and pass 16 contract/boundary tests. But enforcement is honor-system, and the audit verified defects that break the canonical path:

- **Evidence is honor-system.** advanceCheckpoint accepts caller-supplied truthiness on evidence keys with no artifact, DTO, or persisted-state verification (workflow/__init__.py:99-101, 263-269); a bare `{'config_validated': True}` advances any transition (verified by execution). This violates CONTRACT_SURFACE_ALIGNMENT.md:281 — "Every transition is based on persisted state, validated DTOs, or deterministic package output" — and makes checkpoint authority advisory.
- **blocking_reasons is always empty.** getNextCheckpoint returns `blocking_reasons: []` unconditionally (workflow/__init__.py:88); the machine never computes actual blockers.
- **The RESOLVE_GAPS loop never terminates.** The loop-back keys off cumulative `facts_verified` (workflow/__init__.py:76-77); once any fact is verified, getNextCheckpoint returns MATCH_BASE forever and BUILD_SELECTION_PLAN through COMPLETE is permanently unreachable (verified by simulation). Termination must be tracked as new-facts-since-last-match per PRODUCT_VISION_AND_CONTRACTS.md section 14.D.9.
- **The hallucination-rejection completion gate is missing.** TEST_SPEC's invalid-transition rule "Cannot mark run complete with failed hallucination rejection gate" (workflow/TEST_SPEC.md:70) has no corresponding entry in assertCanComplete's required_gates (workflow/__init__.py:216-224). That gate is assigned to this initiative.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Transitions advance only on grounded evidence — persisted run state, validated DTOs, or recorded deterministic package output — never bare caller booleans.
- getNextCheckpoint computes concrete blocking_reasons from unmet, named evidence requirements and policy-gate holds.
- The RESOLVE_GAPS -> MATCH_BASE loop-back terminates: run state tracks facts verified since the last completed match, so the section-14 tail is reachable after gap resolution.
- assertCanComplete gains the hallucination-rejection gate, reading persisted rejection outcomes.

**Non-Goals:**
- Audit-event persistence, real artifact writing, and manifest reconstruction — RKIT-I-0024.
- Resolution-loop policy (which gaps to pursue, exhaustion rules, threshold satisfaction) — RKIT-I-0026 owns loop policy; this initiative delivers only the state-machine substrate (new-facts-since-last-match tracking, terminating loop-back condition).
- Grounding the tailoring/render/completion stages in real artifacts and the overflow loop — RKIT-I-0027 (it consumes both the grounded-evidence model and the hallucination gate delivered here).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Replace honor-system evidence checking (workflow/__init__.py:99-101, 263-269): each evidence key resolves to a typed EvidenceRef that workflow verifies against persisted state or recorded package output before advancing (satisfies CONTRACT_SURFACE_ALIGNMENT.md:281). A caller passing literal booleans is rejected with a typed error.
2. getNextCheckpoint (workflow/__init__.py:88) returns the actual unmet requirements as blocking_reasons; an advance blocked for reason R must surface R by name.
3. Fix the non-terminating loop-back (workflow/__init__.py:76-77): run state records a facts-verified watermark at each completed MATCH_BASE; loop-back fires only when facts exist beyond the watermark. After the rerun, BUILD_SELECTION_PLAN must be reachable (regression for the verified deadlock).
4. assertCanComplete (workflow/__init__.py:216-224) gains a hallucination_rejection gate: completion fails while any hallucination-flagged proposal lacks a persisted rejected status (satisfies workflow/TEST_SPEC.md:70).
5. No checkpoint may be skipped because agent output appears plausible; the checkpoint-skip guardrail must test this invariant structurally, not via keyword blocklist.

### Dependencies
- RKIT-I-0022: unique run identity and validated run-state/manifest schemas that grounded evidence and match watermarks persist into.
- RKIT-A-0006 (decided) authorizes rewriting the contract tests that currently certify honor-system behavior, provided assertion strength only increases.

### Blocked Status
- Blocked by RKIT-I-0022 (frontmatter blocked_by enforces the ordering). No ADR blocks remain; the relevant ADRs are decided.

## Detailed Design **[REQUIRED]**

**Grounded evidence model.** Evidence stops being `dict[str, bool]`. Each checkpoint declares required evidence as typed refs, verified by workflow before transition:
- `{'kind': 'artifact', 'path': ..., 'sha256': ...}` — file must exist and hash-match;
- `{'kind': 'dto', 'schema_id': ..., 'payload': ...}` — payload must validate against the named schema;
- `{'kind': 'run_state', 'key': ...}` — value must exist in persisted run state written by a prior recorded checkpoint result.
advanceCheckpoint verifies every required ref, then persists the verified refs into run state so downstream gates and audit reconstruction read the same grounding. Migration note: existing persisted runs holding boolean evidence maps are treated as ungrounded and cannot advance without re-supplying grounded evidence; no silent upgrade.

**Blocking reasons.** getNextCheckpoint computes blocking_reasons as the named unmet evidence requirements of the next checkpoint plus policy-gate holds (e.g., hard-requirement policy configured through the section 13 vocabulary, contractual under RKIT-A-0006 item 6).

**Loop-termination substrate.** Run state gains `last_match_fact_watermark` (snapshot of facts_verified at the most recent completed MATCH_BASE). The loop-back condition becomes "facts beyond watermark exist"; MATCH_BASE completion updates the watermark. This is mechanism only — RKIT-I-0026 defines when resolution is finished.

**Hallucination-rejection gate.** required_gates gains `hallucination_rejection`: it reads persisted operation statuses (lifecycle owned by resume-core per RKIT-A-0006 item 3) and fails completion if any proposal flagged as ungrounded is not in a rejected terminal state.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Rewrite tests/contract/test_workflow_contract.py:113-131, which currently advances the machine with literal booleans; under the grounded model those cases must fail, and replacements advance with real refs (RKIT-A-0006 authorizes the strengthening).
- TEST_SPEC strengthening (audit-flagged): workflow/TEST_SPEC.md:50-61 state-machine cases are evidence-presence-only — weaker than CONTRACT_SURFACE_ALIGNMENT.md:281 — and certified the honor-system code; rephrase them as grounding obligations (evidence must resolve against persisted artifacts/DTOs).
- Add the loop-termination case missing at workflow/TEST_SPEC.md:57: resolve a gap, rerun match, then assert BUILD_SELECTION_PLAN is reachable (regression for the verified deadlock).
- Strengthen the checkpoint-skip guardrail (tools/workflow_guardrails.py:87-102) from a keyword blocklist ('agent_says_ok', 'skip_checkpoint', 'looks_correct') to a structural check that no path reaches a checkpoint's successor without a recorded grounded transition.
- Contract test: a blocked advance returns non-empty blocking_reasons naming each unmet requirement.
- Contract test: completion with a hallucination-flagged, non-rejected proposal fails.

## Alternatives Considered **[REQUIRED]**

- **Keep caller-asserted evidence and document caller responsibility.** Rejected: CONTRACT_SURFACE_ALIGNMENT.md:281 makes grounding a contract rule, and the audit proved the honor system lets `resume run` claim traversal it never performed.
- **Package-signed evidence tokens (packages issue attestations workflow verifies).** Rejected: heavier machinery that still verifies assertions rather than persisted state; hash-verified artifacts and schema-validated DTOs satisfy the contract rule using state workflow already persists.
- **Terminate the loop by clearing facts_verified after each match rerun.** Rejected: facts_verified is cumulative audit data consumed by the manifest; destroying it to fix control flow trades an audit defect for a loop fix. A watermark preserves both.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. EvidenceRef types plus verification in advanceCheckpoint, with typed rejection of bare booleans.
2. Per-checkpoint required-evidence declarations and computed blocking_reasons in getNextCheckpoint.
3. Match watermark in run state, terminating loop-back condition, and the deadlock regression test.
4. hallucination_rejection gate in assertCanComplete.
5. Contract-test rewrite plus TEST_SPEC:50-61/:57 strengthening and the structural skip guardrail.