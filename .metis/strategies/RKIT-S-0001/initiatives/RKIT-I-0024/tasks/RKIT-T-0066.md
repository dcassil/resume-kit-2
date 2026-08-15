---
id: append-only-operation-and-question
level: task
title: "Append-only operation and question/answer logs plus reconstructRunManifest"
short_code: "RKIT-T-0066"
created_at: 2026-08-15T03:39:09.886894+00:00
updated_at: 2026-08-15T03:39:09.886894+00:00
parent: workflow-checkpoint-result
blocked_by: ["RKIT-T-0065"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0024
---

# Append-only operation and question/answer logs plus reconstructRunManifest

## Parent Initiative

[[RKIT-I-0024]]

## Objective

Create the written log artifacts and reconstruction surface (RKIT-I-0024 Requirements 4-6 minus the CLI migration; Detailed Design "Operation and question/answer logs"/"Manifest reconstruction"): append-only `operations.jsonl` and `questions.jsonl` under the run directory; buildRunManifest populates question_answer_log_refs and unresolved_requirements from persisted logs; `reconstructRunManifest(run_id)` reads only persisted state and never invents values.

## Acceptance Criteria

- [ ] `.workflow/runs/<run_id>/operations.jsonl`: append-only JSONL of operation id + status transitions (proposed/validated/rejected/applied — lifecycle owned by resume-core; workflow records observations). Written by the checkpoint-result path when operation records flow through (T-0063's persisted operation_statuses feed it).
- [ ] `.workflow/runs/<run_id>/questions.jsonl`: append-only JSONL of question asked / answer recorded / fact refs / career-store interaction id (RKIT-A-0001 refs — never duplicated content).
- [ ] buildRunManifest populates question_answer_log_refs (refs into questions.jsonl) and unresolved_requirements from persisted logs/state — the I-0022 empty defaults become real content when logs exist (satisfies CONTRACT_SURFACE_ALIGNMENT.md:353-366).
- [ ] `reconstructRunManifest(run_id)`: loads persisted run state, audit events, logs; fills the extended manifest; validates against RUN_MANIFEST_SCHEMA; typed error on unknown run_id; NEVER invents values — pre-initiative runs reconstruct with explicit "not recorded" markers. Contract test: reconstruction over a recorded run equals the manifest built during the run; unknown id raises.
- [ ] workflow/TEST_SPEC.md :42-43 strengthened: operation/question-answer logs must exist ON DISK with content, not merely as ref strings (guardrail-compatibility checked).
- [ ] PR + smoke gates green; no weakening of any existing assertion; workflow_surface.json only if guardrail-accepted (else deferral note).

## Implementation Notes

### Technical Approach

JSONL appends through a small helper (append + fsync per the durability rule from T-0065). reconstructRunManifest reuses collectVersions where values are recorded in state vs re-resolved — reconstruction READS recorded values (never re-invents); decide and document which fields come from state vs logs.

### Dependencies

RKIT-T-0065 (durable events + real refs are reconstruction inputs).

### Risk Considerations

Equality contract (reconstructed == built) forces buildRunManifest and reconstruction to draw from the same recorded sources — resist re-computing anything at reconstruct time.

### Execution profile

Recommended Agent: opus + high

Rationale: the audit-reconstruction spine; source-of-truth decisions per field are load-bearing for I-0025/I-0028/I-0040.

## Status Updates

*To be added during implementation*
