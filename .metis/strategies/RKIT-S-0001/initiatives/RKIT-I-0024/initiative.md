---
id: workflow-checkpoint-result
level: initiative
title: "Workflow Checkpoint Result Recording, Audit Trail, and Manifest Reconstruction"
short_code: "RKIT-I-0024"
created_at: 2026-08-13T20:41:37.413289+00:00
updated_at: 2026-08-15T03:40:21.678400+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0023]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: workflow-checkpoint-result
---

# Workflow Checkpoint Result Recording, Audit Trail, and Manifest Reconstruction Initiative

## Context **[REQUIRED]**

Package: `workflow`. recordCheckpointResult and the audit surface exist, but their output is cosmetic — this initiative is corrective, not additive. Verified by the alignment audit:

- **Blocked-transition audit events are built but never persisted.** advanceCheckpoint constructs an audit event for a blocked transition but never appends it to run_state.audit_events nor writes it durably (workflow/__init__.py:108-116; verified: 0 events persisted after a blocked advance). "What deterministic rules rejected agent proposals" (vision section 15) is unanswerable from durable state.
- **Validation/render refs are fabricated.** validation_refs and render_refs are produced by substring-matching the words 'validation'/'render' in the JSON-serialized checkpoint result (workflow/__init__.py:145-146); any payload containing the word 'render' anywhere yields a render ref.
- **artifact_refs point at never-written files.** recordCheckpointResult returns `['workflow/<checkpoint>.json']`, a path never written to disk (workflow/__init__.py:157).
- **The operation log and question/answer log do not exist as written artifacts** (workflow/TEST_SPEC.md:42-43) — only fabricated ref strings; and buildRunManifest drops question_answer_log_refs and unresolved requirements required by the Audit Gate (workflow/__init__.py:166-195; CONTRACT_SURFACE_ALIGNMENT.md:353-366).
- **Audit reconstruction is simulated, not reconstructed.** resume-cli `resume audit` fabricates a fresh run via createRun at audit time and assembles manifest inputs from report files (resume-cli/resume_cli/__init__.py:347-360) instead of the persisted `.workflow/runs` state. CONTRACT_SURFACE_ALIGNMENT.md:298 assigns the run manifest to workflow — audit reconstruction must come from workflow-owned persisted run state.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Every transition decision — allowed and blocked — persists an audit event that survives process exit.
- Refs are recorded only for artifacts actually written, with hashes; the substring fabrication is deleted.
- The operation log and question/answer log exist as written, append-only artifacts under the run directory.
- Workflow exposes manifest/audit reconstruction from persisted run state (`reconstructRunManifest(run_id)`), and resume-cli's audit path consumes it instead of fabricating runs.

**Non-Goals:**
- Manifest schema shape and validation — delivered by RKIT-I-0022; this initiative populates the fields.
- Evidence grounding of transitions — RKIT-I-0023 (this initiative persists what that model verifies).
- Recovery semantics that read these logs — RKIT-I-0025.
- E2E proof of audit reconstruction — RKIT-I-0028; CLI wiring of `resume run` onto the state machine — RKIT-I-0040.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Fix unpersisted blocked-transition events (workflow/__init__.py:108-116): every advanceCheckpoint decision appends an audit event (checkpoint, decision, blocking_reasons, timestamp) to run_state.audit_events and flushes durable JSON before returning (satisfies vision section 15's rejected-proposals question).
2. Delete substring-based ref fabrication (workflow/__init__.py:145-146): validation/render refs may only come from explicit, typed refs handed in from recorded package outputs.
3. Fix never-written artifact_refs (workflow/__init__.py:157): recordCheckpointResult writes the checkpoint result payload to `.workflow/runs/<run_id>/checkpoints/<checkpoint>.json` and returns refs only to files that exist, with sha256 hashes.
4. Create the operation log and question/answer log as append-only written artifacts (satisfies workflow/TEST_SPEC.md:42-43); career-store interaction ids (RKIT-A-0001 interactions table) are recorded as refs, not duplicated content.
5. buildRunManifest populates question_answer_log_refs and unresolved_requirements (fields added by RKIT-I-0022) from the persisted logs (satisfies CONTRACT_SURFACE_ALIGNMENT.md:353-366).
6. Provide `reconstructRunManifest(run_id)` reading only persisted run state and logs; it errors on unknown run ids and never invents values. resume-cli `resume audit` (resume-cli/resume_cli/__init__.py:347-360) migrates onto it — run-manifest ownership stays with workflow per CONTRACT_SURFACE_ALIGNMENT.md:298.

### Dependencies
- RKIT-I-0023: grounded evidence and computed blocking_reasons are the content this initiative persists.
- RKIT-I-0022 (transitively): manifest fields and unique run identity that reconstruction depends on.
- RKIT-A-0001 (decided): interaction ids as the audit-ref currency for question/answer history.

### Blocked Status
- Blocked by RKIT-I-0023 (frontmatter blocked_by enforces the ordering). No ADR blocks remain.

## Detailed Design **[REQUIRED]**

**Audit-event persistence.** AuditEvent DTO: {event_id, run_id, checkpoint, decision (advanced|blocked), blocking_reasons, evidence_refs, timestamp}. advanceCheckpoint appends and flushes durably at decision time — not at completion — so interrupted and blocked runs retain their trail. Blocked events carry the blocking_reasons computed by RKIT-I-0023.

**Ref grounding.** recordCheckpointResult accepts explicit typed refs (artifact path + sha256, validation report ref, render report ref) supplied from recorded package outputs. It writes the checkpoint payload under the run directory and returns refs describing only what it wrote or verified on disk. The substring scan of serialized payloads is removed outright, not patched.

**Operation and question/answer logs.** Append-only JSONL under `.workflow/runs/<run_id>/`: `operations.jsonl` (operation id and status transitions — proposed/validated/rejected/applied; lifecycle owned by resume-core) and `questions.jsonl` (question asked, answer recorded, fact refs, career-store interaction id per RKIT-A-0001). Workflow records refs and status observations; it never owns the underlying truth.

**Manifest reconstruction.** reconstructRunManifest(run_id) loads persisted run state, audit events, and logs; fills the RKIT-I-0022-extended manifest including question_answer_log_refs and unresolved_requirements; validates against RUN_MANIFEST_SCHEMA; raises a typed error for unknown run ids. Migration note: runs persisted before this initiative reconstruct with explicit "not recorded" markers rather than fabricated values.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract test: a blocked advance persists exactly one audit event with its blocking reasons, and a process-restart simulation still finds it (regression for workflow/__init__.py:108-116).
- Contract test: every ref returned by recordCheckpointResult resolves to an existing file whose hash matches.
- Adversarial contract test: a checkpoint payload containing the strings 'render' and 'validation' in unrelated content produces no render/validation refs (regression for the substring fabrication at workflow/__init__.py:145-146).
- Contract test: reconstructRunManifest over a recorded run equals the manifest built during the run, and raises on unknown run_id.
- Boundary test: resume-cli's audit path performs no createRun at audit time (regression for resume-cli/resume_cli/__init__.py:347-360).
- TEST_SPEC strengthening (audit-flagged): the artifact expectations at workflow/TEST_SPEC.md:42-43 gain assertions that operation/question-answer logs exist on disk with content — not merely as ref strings — closing the looseness that certified fabricated refs.

## Alternatives Considered **[REQUIRED]**

- **Infer refs from payload content with a stricter parser instead of explicit refs.** Rejected: still fabrication by inspection; refs must be produced by the writer of the artifact, or the audit trail attests to things no one wrote.
- **Persist audit events only into the manifest at completion.** Rejected: interrupted and blocked runs are precisely when the audit trail matters; events must be durable at decision time.
- **Let resume-cli keep assembling audit output from report files.** Rejected: violates workflow's run-manifest ownership (CONTRACT_SURFACE_ALIGNMENT.md:298) and produces a simulation of a run rather than a reconstruction of it — the exact defect the audit verified.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. Durable audit-event persistence for allowed and blocked decisions, with restart-survival regression test.
2. Real checkpoint artifact writes plus explicit typed refs; delete substring ref fabrication.
3. operations.jsonl / questions.jsonl append-only logs with RKIT-A-0001 interaction-id refs.
4. reconstructRunManifest(run_id) from persisted state, with schema validation and typed unknown-run errors.
5. Migrate resume-cli `resume audit` onto reconstruction, plus the boundary test that audit never creates runs.