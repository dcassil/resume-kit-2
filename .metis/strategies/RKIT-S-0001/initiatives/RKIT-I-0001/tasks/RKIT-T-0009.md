---
id: weave-claim-level-resumefield
level: task
title: "Weave claim-level ResumeField provenance and verification through normalizeResume"
short_code: "RKIT-T-0009"
created_at: 2026-08-14T03:12:22.672535+00:00
updated_at: 2026-08-14T03:12:22.672535+00:00
parent: resume-core-canonical-contracts
blocked_by: ["RKIT-T-0003","RKIT-T-0006"]
archived: false

tags:
  - "#task"
  - "#phase/todo"
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0001
---

# Weave claim-level ResumeField provenance and verification through normalizeResume

## Parent Initiative

[[RKIT-I-0001]]

## Objective

This task upgrades `normalizeResume` from copy-only provenance handling to real per-claim `ResumeField` provenance/verification weaving, so that every atomic claim (experience bullet, skill entry, summary line) carries a value, a stable `claim_id`, a provenance list, and a `verification_state`. This per-claim substrate is the single most load-bearing RKIT-I-0001 deliverable for RKIT-I-0004's per-claim honesty gate (REQ-5): without it, the downstream honesty enforcement has no per-claim structure to read.

## Acceptance Criteria

- [ ] `normalizeResume` output carries per-claim `ResumeField`-shaped structure (value + `claim_id` + provenance + `verification_state`) for experience bullets, skills, and summary lines.
- [ ] A claim with no matching provenance entry is emitted with `provenance == []` and `verification_state == 'unknown'`, asserted explicitly; NO claim defaults to `'source_stated'` unless a real source-stated provenance entry exists.
- [ ] `claim_id`s are stable and deterministic across repeated normalization of the same input.
- [ ] No grounding/honesty ENFORCEMENT logic is added (that is RKIT-I-0004); `normalizeResume` remains a normalization function, not a validator.
- [ ] Existing provenance-copy behavior (pre-tagged `claim_id` entries) still round-trips into `provenance_map`.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the task defines a load-bearing cross-package invariant (honest empty/unknown defaults that RKIT-I-0004 depends on) and requires careful judgment about the scope boundary between substrate and enforcement; it is not a mechanical change.

### Technical Approach

Upgrade `normalizeResume` (`domain.py:171-211`) from copy-only provenance handling to real per-claim `ResumeField` provenance/verification weaving. Today `normalizeResume` only COPIES pre-tagged provenance entries into `provenance_map` (`domain.py:201-204`) and never synthesizes claim-level structure.

- Target: for each atomic claim (experience bullet, skill entry, summary line) normalize it into/alongside a `ResumeField` carrying `value`, a stable `claim_id`, a `provenance` list, and a `verification_state`.
- **APPROVED DECISION (binding):** this ships in THIS initiative (RKIT-I-0001), not deferred.
- **CRITICAL INVARIANT (binding):** a claim with NO identifiable source gets EMPTY provenance + `verification_state='unknown'`, NEVER a silent `'source_stated'`. `normalizeResume` must not fabricate a source. Do not manufacture source attributions it cannot prove.
- This weaving is the substrate RKIT-I-0004 REQ-5 checks per-claim; without it, RKIT-I-0004's honesty gate has nothing to read (it replaces the all-or-nothing check at `domain.py:1295-1303`).
- **SCOPE BOUNDARY:** RKIT-I-0001 provides the substrate (per-claim `ResumeField` with honest empty/unknown defaults); RKIT-I-0004 provides the honesty ENFORCEMENT semantics. Do not add grounding enforcement here. This is the single most load-bearing RKIT-I-0001 deliverable for RKIT-I-0004 REQ-5, and it is easy to under-scope as a stub — do not.
- NOTE: claim IDENTITY synthesis (spans, source attribution) is an extraction concern; this task assigns stable deterministic `claim_id`s and honest defaults only — it does NOT manufacture source attributions it cannot prove.

### Files

- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/domain.py` (PROTECTED)
- `/Users/danielcassil/Code/resume-kit-2/resume-core/resume_core/schemas.py` (PROTECTED)

### Dependencies

- [[RKIT-T-0003]] — restores canonical enum members (`VerificationState`, `ResolutionState`) and reconciles cross-package readers; `verification_state='unknown'` and the honest defaults require the canonical enum members to be present and consistent.
- [[RKIT-T-0006]] — adds schema-backed structural validation of `validateResume` against exported constants; the per-claim `ResumeField` structure this task emits must validate against those exported constants.
- Downstream semantic link: RKIT-I-0004 (REQ-5) consumes this substrate for its per-claim honesty ENFORCEMENT gate, which replaces the all-or-nothing check at `domain.py:1295-1303`. Enforcement semantics belong to RKIT-I-0004, not this task.

### Risk Considerations

- **Protected-surface constraint:** `domain.py` and `schemas.py` are protected (straight-jacket) surfaces; changes must respect the existing contract shape and pass structural validation rather than reshaping the surface freely.
- **The load-bearing invariant is a correctness risk, not a style risk:** if any code path silently defaults an unsourced claim to `'source_stated'`, RKIT-I-0004's honesty gate becomes a lie. Assert the empty-provenance / `'unknown'` default explicitly in tests.
- **Cross-package blast radius:** the per-claim `ResumeField` structure and enum values are read across packages; a mismatch with the canonical enums (RKIT-T-0003) or exported constants (RKIT-T-0006) can break downstream readers.
- **Determinism:** `claim_id`s must be stable and deterministic across repeated normalization of the same input, or downstream per-claim tracking and diffing break.
- **Scope-boundary bleed:** the strongest pull is to start adding grounding/honesty enforcement here. Do NOT — that is RKIT-I-0004. Keep `normalizeResume` a normalization function; provide substrate and honest defaults only, never enforcement.

## Verification Steps

1. Unit test: `normalizeResume(<resume with one bullet that has a matching provenance entry and one bullet with none>)`: the matched bullet's `ResumeField` has non-empty provenance; the unmatched bullet's `ResumeField` has `provenance==[]` and `verification_state=='unknown'`.
2. Determinism test: two runs on the same input produce identical `claim_id`s.
3. Regression: a resume with pre-tagged provenance entries still populates `provenance_map` as before.
4. PR gate green: `python3 tools/run_gate.py --pr --root .`

## Status Updates

*To be added during implementation*