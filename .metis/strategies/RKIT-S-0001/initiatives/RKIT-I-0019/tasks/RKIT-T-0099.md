---
id: proposerewrite-through-adapter
level: task
title: "proposeRewrite through adapter with fact-mapped output; template path deleted; grounding post-guard"
short_code: "RKIT-T-0099"
created_at: 2026-08-17T17:23:40.540901+00:00
updated_at: 2026-08-17T17:43:59.173559+00:00
parent: resume-agent-grounded-rewrite
blocked_by: [RKIT-T-0098]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0019
---

# proposeRewrite through adapter; template deleted; deterministic grounding post-guard

## Parent Initiative

[[RKIT-I-0019]]

## Objective **[REQUIRED]**

Close the rewrite Honesty Gate defect: today the "after" text is `f"Built {', '.join(unique_phrases)}."` keyword salad (audit ref :739) and the generator inserts EVERY non-blocked job-terminology term regardless of fact support (:723-727 — verified: API-fact-only input still added "responsive design"). After this task: `proposeRewrite` runs through the adapter with the T-0098 fact-mapped schema; a DETERMINISTIC post-guard rejects any operation whose added terms lack a fact mapping or whose cited fact ids fall outside the allowed set; the template-concatenation path and insert-everything loop are DELETED.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `proposeRewrite` → T-0098 builder → adapter → schema-validated payload → 4.5-shaped operations in the proposal envelope (in-enum verbs, reason, requirementIds, factIds, ProvenanceRef[], model confidence — replacing the T-0094 "unscored" placeholder on this surface; update the handoff docstring).
- [ ] Deterministic grounding post-guard in code: (a) every added term/claim in `after` maps to a fact id, (b) every cited fact id ∈ the supplied allowed set; violation → typed guard error, operation never emitted. Test with the T-0098 ungrounded fixture AND an out-of-allowed-set fact id case.
- [ ] The audit's counterexample as a permanent named regression: API-fact-only input NEVER yields "responsive design" (TEST_SPEC :69-70 refs).
- [ ] Template path + insert-everything loop DELETED (grep-proof: the `Built {` f-string pattern and the terminology-insertion loop gone from production code).
- [ ] Missing target_path → typed input error end-to-end through the public function (no fabricated default anywhere).
- [ ] Adapter failure → typed error, never template fallback. Smoke inputs pinned as needed (CLI tailoring path drives proposeRewrite — keep smoke honest).
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Same adapter seam idiom. The workflow PROPOSE_TAILORING_CHANGES / smoke tailoring flow consumes these operations and resume-core validateChange gates them downstream — run --smoke and check operations still validate (the 4.5 shape should IMPROVE validation, but the CLI compat shim from I-0001 may need its emitted-op adjustments checked).
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0098. Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.
- Cross-package: resume-cli `_core_operation` shim and workflow grounded-tailoring evidence consume rewrite ops — --smoke is the tripwire; fix by pinning fixtures/aligning shapes, never by weakening.

## Status Updates **[REQUIRED]**

- 2026-08-17: T-0098 committed (rewrite-proposal.v1 w/ 4.5 dual-alias fields + required grounding map, typed input contract, 3 fixtures; gates 510/smoke/verify green). Codex launched: proposeRewrite rewire, deterministic grounding guard (map coverage + allowed-set check), template/insertion-loop deletion, responsive-design regression, smoke tailoring fixture pinning + validateChange compatibility.