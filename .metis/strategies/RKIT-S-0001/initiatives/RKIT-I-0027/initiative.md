---
id: workflow-tailoring-validation
level: initiative
title: "Workflow Tailoring, Validation, Render, and Completion Orchestration"
short_code: "RKIT-I-0027"
created_at: 2026-08-13T20:41:37.507312+00:00
updated_at: 2026-08-15T04:30:48.850529+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0026]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: workflow-tailoring-validation
---

# Workflow Tailoring, Validation, Render, and Completion Orchestration Initiative

## Context **[REQUIRED]**

Package: `workflow`. Completion gating already exists — assertCanComplete covers final match, grounding, ATS, render validation, audit ref, and hard-requirement policy (workflow/__init__.py:215-232) — but those gates read honor-system evidence, and the orchestration around them is missing. Verified by the alignment audit:

- **Nothing in the repo calls resume-render's measureLayout.** The render-overflow loop-back required by CONTRACT_SURFACE_ALIGNMENT.md:283 ("Rendering overflow returns constraints to orchestration; renderer does not truncate") has no implementation anywhere.
- **The product path never drives these checkpoints.** resume-cli `resume run` executes stages and then returns `'checkpoints': list(CHECKPOINT_ORDER)` as if traversed, never calling advanceCheckpoint or assertCanComplete (resume-cli/resume_cli/__init__.py:316-324), violating vision section 10 ("resume run ... must still use the same internal checkpoints as individual commands").
- The prior version of this document never stated what workflow "coordination" means versus resume-cli's "local workflow orchestration" (CONTRACT_SURFACE_ALIGNMENT.md:41) and workflow's must-not-own-package-private-logic rule (CONTRACT_SURFACE_ALIGNMENT.md:43).

Boundary statement (explicit, required): workflow owns the checkpoint sequence, gate evaluation, and loop-back decisions for selection -> proposals -> validation -> application -> final checks -> render -> completion. resume-cli owns invoking package APIs in sequence, workspace artifacts, and user-facing reporting, and must drive every stage through workflow's checkpoint surface — the CLI-side wiring itself is RKIT-I-0040's scope. Semantic mutation stays in resume-core; rendering and layout measurement stay in resume-render.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Orchestrate the tailoring tail — selection plan, proposal validation/application, final checks, render, completion — coordinating only through public package surfaces.
- Implement the render-overflow loop-back: overflow constraints from measureLayout flow back to selection/rewrite checkpoints with requiredReduction as a fine-grained character-count quantity (RKIT-A-0006 item 7), bounded and honest on failure.
- Ground every assertCanComplete gate in real persisted artifacts (the RKIT-I-0024 ref model) so completion cannot pass on asserted booleans.
- Expose stage-level checkpoint decisions in a shape RKIT-I-0040 can drive `resume run` through without duplicating orchestration logic.

**Non-Goals:**
- The hallucination-rejection gate itself — implemented by RKIT-I-0023; this initiative consumes it as one completion gate among the set.
- CLI integration (making `resume run` actually drive the machine) — RKIT-I-0040.
- The gap-resolution loop — RKIT-I-0026.
- Owning selection, validation, mutation, or rendering logic — resume-core and resume-render; workflow sequences and gates, nothing more (CONTRACT_SURFACE_ALIGNMENT.md:43).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Render-overflow loop-back: a render checkpoint result carrying overflow constraints from resume-render measureLayout (currently uncalled anywhere in the repo) routes the machine back to selection/rewrite checkpoints, with requiredReduction expressed as a character count per RKIT-A-0006 item 7 — not a page delta. Renderer truncation is forbidden (CONTRACT_SURFACE_ALIGNMENT.md:283).
2. Overflow iterations are bounded (bound configured via the section 13 vocabulary); exhausting the bound yields an honest blocked outcome with persisted reasons — never silent truncation, never completion.
3. Every completion gate in assertCanComplete (workflow/__init__.py:215-232) reads persisted artifact/report refs — final match report, grounding audit, ATS report, render validation report — via the RKIT-I-0024 ref model, not caller-supplied booleans.
4. Orchestration calls only public package surfaces; a boundary test enforces the absence of package-private imports.
5. Stage-level checkpoint decisions are exposed so `resume run` can traverse the same checkpoints as individual commands (vision section 10), closing the gap where the CLI reports traversal it never performed (resume-cli/resume_cli/__init__.py:316-324).

### Dependencies
- RKIT-I-0026: the resolution loop must terminate before the tailoring tail is reachable at all.
- RKIT-I-0023/0024 (transitively): grounded evidence and real artifact refs are what these stages' gates consume.
- RKIT-A-0006 (decided): character-count requiredReduction semantics and the enforced config vocabulary.

### Blocked Status
- Blocked by RKIT-I-0026 (frontmatter blocked_by enforces the ordering). No ADR blocks remain.

## Detailed Design **[REQUIRED]**

**Stage evidence declarations.** Each tail checkpoint declares grounded evidence per the RKIT-I-0023 model: BUILD_SELECTION_PLAN requires a persisted selection-plan artifact; proposal/validation/application checkpoints require operation ids in the correct lifecycle states (proposed/validated/applied — lifecycle owned by resume-core per RKIT-A-0006 item 3); final checks require grounding and ATS report refs; the render checkpoint requires the render output plus the measureLayout result; COMPLETE requires assertCanComplete.

**Overflow loop.** The render checkpoint result DTO includes overflow constraints: {requiredReduction: character count, offending_sections}. On overflow, workflow records the constraint artifact, transitions back to the selection-plan checkpoint with the constraint as required input evidence, and increments overflow_iteration in run state. Exceeding the configured bound produces a blocked outcome with persisted reasons. The renderer is never asked to truncate; selection/rewrite (resume-core) absorbs the reduction.

**Grounded completion.** required_gates map each gate to a persisted ref: final_match -> match report artifact, grounding -> grounding audit artifact, ats -> ATS report, render_validation -> render validation report, audit_ref -> RKIT-I-0024 audit trail, hallucination_rejection -> RKIT-I-0023 gate, hard_requirements -> policy state. COMPLETE is unreachable while any ref is missing or hash-mismatched.

**Interruption surface.** Every stage boundary persists state before returning, so RKIT-I-0025 (which deliberately follows this initiative) can compute recovery reruns for the proposed-operations, partially-applied-operations, and render-overflow interruption points.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract test: an overflow render result routes the machine back to the selection-plan checkpoint carrying a character-count requiredReduction (regression for the currently unimplemented CONTRACT_SURFACE_ALIGNMENT.md:283 rule).
- Contract test: overflow bound exhaustion produces a blocked outcome with persisted reasons; no path reaches COMPLETE.
- Contract test: completion fails when any gate ref is missing or hash-mismatched, and succeeds only with all real artifacts present — replacing the boolean-evidence completion tests that certified the honor system.
- Boundary test: workflow imports only public surfaces of resume-core/resume-render.
- TEST_SPEC strengthening (audit-flagged): the state-machine section has no render-overflow loop-back case and its completion cases are evidence-presence-only; add overflow loop-back and grounded-completion cases aligned with CONTRACT_SURFACE_ALIGNMENT.md:281/283. RKIT-A-0006 authorizes the protected-spec strengthening.

## Alternatives Considered **[REQUIRED]**

- **Let resume-render truncate content to fit.** Rejected: CONTRACT_SURFACE_ALIGNMENT.md:283 forbids it explicitly; truncation silently destroys semantic content the grounding gates certified.
- **Handle the overflow loop inside resume-cli.** Rejected: the loop-back is a checkpoint transition, owned by workflow (CONTRACT_SURFACE_ALIGNMENT.md:43); CLI-side handling forks orchestration truth and repeats the audited pattern where the CLI simulates workflow behavior.
- **Keep page-delta requiredReduction (the current DTO drift).** Rejected by decided RKIT-A-0006 item 7: the contract example implies a fine-grained quantity actionable by selection/rewrite; a page delta cannot direct a targeted reduction.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. Stage evidence declarations for the tailoring tail (selection plan through completion).
2. Overflow-constraint DTO consumption, loop-back transition, and the iteration bound with honest blocked outcome.
3. Grounded completion gates over RKIT-I-0024 refs, replacing boolean gate evidence.
4. Boundary tests plus TEST_SPEC overflow/completion strengthening.
5. Checkpoint-driving surface review with RKIT-I-0040 as the consumer — interface shape only, no CLI code in this initiative.