---
id: section-4-5-rewrite-operation
level: task
title: "Section-4.5 rewrite operation schema, input-contract validation (typed missing-target error), fake fixtures"
short_code: "RKIT-T-0098"
created_at: 2026-08-17T17:23:40.476835+00:00
updated_at: 2026-08-17T17:32:52.861947+00:00
parent: resume-agent-grounded-rewrite
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0019
---

# Section-4.5 rewrite operation schema + input contract + fixtures

## Parent Initiative

[[RKIT-I-0019]]

## Objective **[REQUIRED]**

Land the rewrite substrate: (1) a rewrite-proposal output schema whose operations are FULL section 4.5 `ResumeChangeOperation` shapes — `operation_type ∈ replace|rewrite|insert|remove|move` (retiring `replace_text`), mandatory non-empty `reason`, `requirementIds`, `factIds`, `provenance: ProvenanceRef[]` pointing at licensing evidence, `confidence`, `status: proposed` — PLUS a fact-mapping structure: every added claim/term maps to a licensing fact id (the T-0099 post-guard enforces it deterministically). (2) Input-contract validation: code supplies original text, MANDATORY valid `target_path` (typed input error if absent/malformed — the fabricated `experience[0].bullets[0]` default at audit ref :759 dies), allowed facts with ids, requirement ids, voice/length constraints, prohibited additions. (3) Prompt template asset + builder. (4) Fake fixtures: grounded rewrite golden (every added term fact-mapped), an ungrounded fixture (added term without fact mapping — for the post-guard test), and a constraint-carrying golden.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `resume-agent.rewrite-proposal.v1` schema registered: 4.5 operation shape as above; schema REQUIRES the added-term→fact-id mapping structure; resume-core's ResumeChangeOperation shape (resume-core section 4.5 DTO / validateChange expectations) is the alignment reference — read it first.
- [ ] Input validation in code: missing/malformed target_path → typed validation_error naming the field; no default target fabrication anywhere.
- [ ] Prompt asset (id@vN) + deterministic builder carrying original text, target_path, allowed facts, requirement ids, constraints, prohibited additions.
- [ ] Fixtures (envelope + keying): grounded golden (API-fact-only input whose after-text contains ONLY API-licensed claims), ungrounded in-suite fixture (term with no fact mapping), constraint golden (voice/length fields populated).
- [ ] Contract tests: schema registration (in-enum verbs enforced, reason required non-empty, provenance array required); input-contract typed errors; builder determinism.
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Follow the I-0017/I-0018 substrate idiom exactly (_extraction_schemas/_interview_schemas siblings). Check resume-core change_operations.py / validateChange for the exact 4.5 field names so proposals validate downstream.
- No proposeRewrite rewiring yet (T-0099).
- Recommended Agent: opus + high

### Dependencies
None within I-0019 (first task). Serial chain T-0098→0099→0100.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

- 2026-08-17: I-0018 complete (v0.20.0 pushed b4c319b — both gate violations closed). I-0019 decomposed T-0098..0100 (serial). Codex launched on the substrate: rewrite-proposal.v1 schema (full 4.5 ops + required grounding map; schema-valid/guard-violating split documented), input contract w/ typed missing-target error, prompt asset + builder, grounded/ungrounded/constraint fixtures.