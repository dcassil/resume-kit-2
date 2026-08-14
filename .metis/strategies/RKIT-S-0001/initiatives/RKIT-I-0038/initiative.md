---
id: grounded-tailoring-operation
level: initiative
title: "Grounded Tailoring Operation Lifecycle"
short_code: "RKIT-I-0038"
created_at: 2026-08-13T20:41:37.860659+00:00
updated_at: 2026-08-13T20:41:37.860659+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0037", "RKIT-I-0004", "RKIT-I-0019"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Grounded Tailoring Operation Lifecycle Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. The tailor loop is the most genuinely implemented part of resume-cli: content ranking (`rankResumeContent`), rewrite proposals (`proposeRewrite`), operation validation/application (`validateChange`/`applyChange`), and an active base-immutability check all flow through the owning packages. Three parts are gamed or fixture-tuned:

- `_hallucinated_operation` injects a synthetic "20 million users" hallucination into every tailor run so a rejection is always present in output (`resume_cli/__init__.py:250-252, 968-977`). DoD 11 "hallucination rejection" is therefore staged by the CLI itself and proves nothing about the proposal pipeline's gating. TEST_SPEC smoke item 9 permitted this by not requiring the rejected operation to originate from the agent proposal path.
- `_target_path` maps exactly two hardcoded fixture paths and silently rewrites ANY unrecognized agent target path to `/sections/1/items/0/bullets/1` (`resume_cli/__init__.py:945-952`); `_best_rewrite_target` keyword-matches 'api'/'responsive'/'web app' with a hardcoded pointer fallback (`:858-871`). On real resumes this misapplies operations, breaking the ResumeChangeOperation invariant (valid target path, matching before value).
- `_prohibited_additions`/`_safe_rewrite_term` hardcode the Honesty Gate example strings — 'Staff Software Engineer', '20 million users', '30 engineers', aws/graphql filters (`resume_cli/__init__.py:890-907`) — a blocklist tuned to the documented examples rather than a general grounding policy.

RKIT-A-0006 item 3 additionally realigns ResumeChangeOperation to the section 4.5 shape (verbs replace/rewrite/insert/remove/move; statuses proposed/validated/rejected/applied/accepted/modified; mandatory reason, requirementIds, factIds, provenance), which the tailor loop must adopt end to end.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- DoD 11 proven from the agent proposal path: `_hallucinated_operation` is deleted from product code; the adversarial hallucinated proposal moves to the test flow per SMOKE_TEST step 10 — the fixture-pinned DeterministicFakeAdapter emits it, and the core validation/grounding pipeline must reject it.
- Target paths are proposal-supplied and validated: operations with unknown or non-matching target paths are rejected with typed errors, never silently retargeted. `_target_path` and `_best_rewrite_target` are deleted; path/before-value validation belongs to core against the canonical resume.
- Prohibited-additions generalized: added claims are gated by core grounding — every addition traces to verified facts via requirementIds/factIds/provenance — not by a string blocklist. The example-string lists are deleted.
- The tailor loop adopts the RKIT-A-0006 item 3 operation shape; every rejected operation is audited with reason and adapter provenance (RKIT-A-0003 item 6 metadata).
- Selection/rewrite entry accepts an optional reduction constraint input (character-count `required_reduction`) so RKIT-I-0039's overflow handling can re-enter the loop.
- Base immutability remains enforced and tested.

**Non-Goals:**
- Detecting overflow and returning constraints from export — RKIT-I-0039 owns that side of the loop; this initiative only provides the re-entry input.
- Rewrite proposal quality/grounding generation — resume-agent RKIT-I-0019 (per RKIT-A-0003).
- Change validation/grounding internals — resume-core RKIT-I-0004.
- Final validation and export — RKIT-I-0039.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- No product code path constructs, injects, or retargets operations: proposals come from the agent surface, validation from core `validateChange`, application from core `applyChange` — resume-cli orchestrates only (CONTRACT_SURFACE_ALIGNMENT.md resume-cli must-not row).
- An operation whose target path does not exist in working.json, or whose before value does not match, is rejected by core validation and surfaced as a typed, audited rejection — the `resume_cli/__init__.py:945-952` silent-retarget behavior is removed.
- A fabricated claim absent from the documented example strings (e.g. an invented certification) is rejected by the grounding gate — proving generality beyond the `:890-907` blocklist.
- All operations carry reason, requirementIds, factIds, provenance and legal verbs/statuses per section 4.5/RKIT-A-0006 item 3, enforced by `validateChange`.
- Tailor output includes the audited rejection list (operation, status `rejected`, machine-readable reason, adapter provenance) sourced exclusively from pipeline decisions.
- `base.json` is byte-identical across any tailor run; only `working.json` changes, and only via `applyChange`.

### Dependencies
- RKIT-I-0037 (match/resolve substrate the tailor loop consumes).
- RKIT-I-0004 Resume-Core Grounded Change Lifecycle And Final Validation (operation validation, grounding, application).
- RKIT-I-0019 Resume-Agent Grounded Rewrite Proposal Adapter (proposal surface per RKIT-A-0003).

### Blocked Status
- Blocked by RKIT-I-0037, RKIT-I-0004, RKIT-I-0019 (frontmatter matches). RKIT-A-0003 is decided (adapter surfaces, fake-adapter gates), so no ADR block remains.

## Detailed Design **[REQUIRED]**

- **Tailor loop.** select (core ranking with config weights) → agent rewrite proposals (ModelAdapter surface; fake adapter in official gates) → core `validateChange` (schema, target-path existence, before-value match, grounding against verified facts) → user-visible decision where required → core `applyChange` to working.json → operation audit record (full section 4.5 DTO with terminal status). base.json is never written.
- **Rejection audit.** Every rejected proposal persists with status `rejected`, a machine-readable reason (`ungrounded_claim`, `invalid_target_path`, `before_mismatch`, ...), and provenance identifying the proposing adapter (id/version/model per RKIT-A-0003 item 6). The tailor report renders rejections from this record only.
- **Hallucination fixture (SMOKE_TEST step 10).** The smoke fixture pins a fake-adapter proposal set containing one ungrounded quantified claim; the smoke assertion requires exactly that operation rejected with `ungrounded_claim` and adapter provenance. Product code contains no injection path — a source-level guardrail asserts `_hallucinated_operation` (and any equivalent) is gone.
- **Constraint re-entry.** `tailor --reduce <chars>` (and the programmatic equivalent) passes the character-count constraint into core selection so RKIT-I-0039 can re-invoke tailoring on overflow (`required_reduction` semantics per RKIT-A-0006 item 7).
- **Migration note.** Existing workspaces hold operation artifacts in the drifted DTO; new runs write the realigned shape and old artifacts are not migrated — re-running tailor is the upgrade path.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Strengthen smoke item 9 — the exact looseness that allowed the staging: the rejected hallucination must originate from the (fake) agent proposal path, asserted via adapter provenance on the rejected operation, plus a source-level guardrail that product code contains no operation-injection function.
- Invalid-target-path contract test: a proposal targeting a nonexistent path is rejected `invalid_target_path`; working.json is unchanged (byte-compare); no retargeting occurred.
- Grounding generality test: a fabricated claim using vocabulary absent from the documented example strings is rejected — kills the blocklist.
- Operation DTO conformance: every persisted operation has reason/requirementIds/factIds/provenance and a legal verb/status from the RKIT-A-0006 sets.
- Base-immutability guardrail stays; add a before/after hash assertion across a full tailor run.
- Constraint re-entry test: `--reduce` yields a working.json whose measured length decreased via selection/rewrite, not truncation.

## Alternatives Considered **[REQUIRED]**

- Keep the injection but gate it behind a test-only flag/env var: rejected — product code still owns fake behavior, DoD 11 still proves nothing about real proposals, and flag drift would silently reintroduce the staging.
- Expand `_prohibited_additions` into a larger curated blocklist: rejected — blocklists cannot generalize to arbitrary fabrications; grounding via fact provenance is the documented Honesty Gate mechanism and already exists in core.
- Fuzzy-match unknown target paths to the nearest plausible bullet: rejected — misapplied operations on real resumes are silent truth mutations; the invariant demands rejection, and rejection feeds the honest audit trail.

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Adopt the RKIT-A-0006 operation DTO through the tailor loop (proposal → validation → application → audit).
2. Delete `_target_path`/`_best_rewrite_target`; route path/before validation through core; surface typed rejections.
3. Delete `_prohibited_additions`/`_safe_rewrite_term`; wire the grounding gate for additions.
4. Delete `_hallucinated_operation`; build the SMOKE_TEST step 10 fake-adapter fixture and provenance-checked rejection assertions.
5. Add the reduction-constraint re-entry input to selection/rewrite.
6. TEST_SPEC strengthening: agent-origin rejection, invalid-path, grounding generality, DTO conformance, immutability hash.
