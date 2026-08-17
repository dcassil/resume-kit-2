---
id: generateclarificationquestion-via
level: task
title: "generateClarificationQuestion via adapter: verified-ids pre-filter, typed no-question result"
short_code: "RKIT-T-0096"
created_at: 2026-08-17T16:59:31.417619+00:00
updated_at: 2026-08-17T17:13:15.434266+00:00
parent: resume-agent-targeted-interview
blocked_by: [RKIT-T-0095]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0018
---

# generateClarificationQuestion via adapter: verified-ids pre-filter + typed no-question result

## Parent Initiative

[[RKIT-I-0018]]

## Objective **[REQUIRED]**

Close the Persistence Gate violation and retire the canned questions: `generateClarificationQuestion` currently echoes `already_verified_fact_ids` back and re-asks the identical canned question (audit refs __init__.py:535-537, :556), and its three question strings are keyed on "aws"/"graphql"/"architecture" substrings (:539-547). After this task: a DETERMINISTIC pre-filter drops targets present in `already_verified_fact_ids` BEFORE any model call; an empty remainder short-circuits to a typed no-question-needed result (no adapter call at all); the surviving targets go to the model for phrasing via the T-0095 builder — any topic, the code-owned caller picks WHAT to ask, the agent only phrases it.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] Deterministic pre-filter in code (not prompt): targets ∩ already_verified_fact_ids removed before the adapter request is built; test proves the model is NEVER consulted about a verified fact (fake adapter would raise on the unexpected key — use that).
- [ ] All-verified topic → typed no-question result (structured status, no question text, no adapter call); TEST_SPEC :52 behavior real.
- [ ] Canned question strings + substring keying deleted (grep-proof: the three canned question literals gone from production code).
- [ ] Model-phrased questions for arbitrary topics via the T-0095 fixtures (incl. the non-fixture topic golden); output carries question text, targeted ids, rationale in the proposal envelope (requires_validation, deterministic IDs).
- [ ] Adapter failure → typed error, never a canned fallback question (a silent deterministic fallback would reintroduce the closed world).
- [ ] Persistence contract battery: verified ids in → never out in question targets; partial overlap → question targets only the unverified remainder; full overlap → no-question result.
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes (smoke may need pinned fixtures for its question inputs — add, don't weaken).

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Follow T-0092's seam exactly (context["_adapter"], DeterministicFakeAdapter default via require_agent_config).
- Check smoke/CLI usage of generateClarificationQuestion for inputs needing pinned fixtures.
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0095. Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

- 2026-08-17: T-0095 committed (interview schemas w/ required polarity + canonical resolution states, prompt assets, 7 fixtures incl. denial/qualified/Terraform; gates 482/smoke/verify green). Codex launched: code-owned verified-ids pre-filter before any model call, typed no-question short-circuit, canned-question deletion, persistence battery.