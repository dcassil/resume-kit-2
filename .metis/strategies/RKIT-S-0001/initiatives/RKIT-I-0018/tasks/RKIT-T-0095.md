---
id: question-interpretation-schemas
level: task
title: "Question/interpretation schemas + fake fixtures (affirm/deny/qualified/off-topic)"
short_code: "RKIT-T-0095"
created_at: 2026-08-17T16:59:31.355618+00:00
updated_at: 2026-08-17T17:06:38.288643+00:00
parent: resume-agent-targeted-interview
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0018
---

# Question/interpretation schemas + fake fixtures (affirm/deny/qualified/off-topic)

## Parent Initiative

[[RKIT-I-0018]]

## Objective **[REQUIRED]**

Land the interview-surface substrate on the I-0016/I-0017 pattern: (1) a question-generation output schema — question text, targeted requirement/fact ids, rationale — and an answer-interpretation output schema per section 8: `{requirementResolutions, factProposals, evidenceProposals}` with per-item model-sourced confidence, resolution states from the section 4.4 set, fact proposals carrying evidence linkage to the answer text + verification_state; the interpretation payload also carries an explicit `polarity` classification (affirmed | denied | qualified | unresponsive) the T-0097 post-guard will enforce against. (2) Versioned prompt-template assets + deterministic builders. (3) Fake-adapter fixtures covering affirmation, denial, qualification ("yes, but only internal tools"), and off-topic/unresponsive answers, PLUS a non-fixture topic (not aws/graphql/architecture) — the substrate for the negation and persistence batteries.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] Both schemas registered with the shared validator; interpretation schema REQUIRES polarity, per-resolution suggested state from the canonical 4.4 set, per-proposal confidence + evidence linkage; denial-shaped payloads representable (explicit-absence resolution with zero positive fact proposals for the denied claim).
- [ ] Prompt templates as versioned file assets (id@vN convention from T-0091) + deterministic builders producing AdapterRequests for question generation (topic, target ids, context snippets — already_verified filtering stays OUTSIDE the request, code-owned in T-0096) and interpretation (question, answer text, topic).
- [ ] Fixtures (data envelope + sha256 keying): denial golden ("No, I have never used AWS professionally" → polarity denied, explicit-absence resolution, zero positive fact proposals), qualified golden ("yes, but only internal tools" → hedged partial resolution with the hedge captured), affirmation golden, off-topic/unresponsive golden, and a NON-fixture-topic pair (question + interpretation for e.g. Terraform) — all schema-valid by the fixture walk.
- [ ] Contract tests: schema registration/validation incl. polarity requirement; builder determinism; denial fixture asserts zero positive fact proposals structurally.
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Follow _extraction_schemas.py/_extraction_requests.py idioms exactly; check agent_surface.json declared interpretation shapes and CONTRACT_SURFACE_ALIGNMENT section 8 wording.
- No public-function rewiring yet (T-0096/0097).
- Recommended Agent: opus + high

### Dependencies
None within I-0018 (first task). Serial chain T-0095→0096→0097.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

- 2026-08-17: I-0017 complete (v0.19.0 pushed 6971a66). I-0018 decomposed T-0095..0097 (serial). Codex launched on the substrate: question-generation.v1 + answer-interpretation.v1 schemas (polarity required), prompt assets + builders, denial/qualified/affirmation/unresponsive/Terraform fixtures.