---
id: extraction-output-schemas-resume
level: task
title: "Extraction output schemas (resume + job) with evidence/confidence; fake-adapter fixtures for legacy + non-fixture goldens"
short_code: "RKIT-T-0091"
created_at: 2026-08-17T16:26:26.925580+00:00
updated_at: 2026-08-17T16:26:26.925580+00:00
parent: resume-agent-model-based-resume
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0017
---

# Extraction output schemas + fake-adapter fixtures (legacy + non-fixture goldens)

## Parent Initiative

[[RKIT-I-0017]]

## Objective **[REQUIRED]**

Land the substrate for model-based extraction: versioned resume-extraction and job-extraction OUTPUT schemas aligned to the section 4.2 shapes (CanonicalResume-shaped resume proposal; JobModel-shaped job proposal with requirement entries carrying classification/seniority/industry/domain), every extracted item carrying source-evidence references (text span/line) and model-sourced confidence; versioned prompt-template assets + deterministic prompt/input builders (RKIT-I-0021 will hash them); and DeterministicFakeAdapter fixtures for BOTH the legacy fixture inputs AND new non-fixture golden inputs — including the audit's ML-engineer probe profile (Python, TensorFlow, Kubernetes, GCP, Go, PhD) whose current extraction yields only the title line.

## Acceptance Criteria **[REQUIRED]**

- [ ] Resume-extraction and job-extraction output schemas registered with the T-0087 schema registry/validator (stdlib idiom); schemas require per-item `evidence` refs (source span/line) and `confidence` fields; requirement entries carry classification + seniority + industries + domains.
- [ ] Versioned prompt templates as assets (files with template ids/versions, not inline strings) + deterministic builders assembling (raw text, schema id, template id) into AdapterRequest.
- [ ] Fake fixtures under fixtures/resume-agent/fake-adapter/ (data envelope, sha256 keying from T-0088) for: the legacy resume/job fixture inputs, AND non-fixture goldens — at minimum the ML-engineer resume probe and a JD golden containing "5+ years with Python, Spark..." (unknown+known co-occurrence) and a GraphQL+API-design JD. Golden fake outputs must have EVERY populated section/skill represented (they define the generalization bar for T-0092/0093).
- [ ] All fixtures pass the fixture self-validation walk (schema-valid by construction).
- [ ] Contract tests: schema registration + validation behavior; builder determinism (same input → same AdapterRequest); fixture completeness assertions for the goldens (every named skill in the golden JD appears in some requirement entry of the pinned output).
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Read resume-core's canonical schema shapes (section 4.2 DTOs) for alignment; check agent_surface.json declared proposal structures.
- No behavior change to the five public functions yet (T-0092/0093 rewire them); this task is schemas + templates + fixtures + builders.
- Recommended Agent: opus + high

### Dependencies
None within I-0017 (first task). Serial chain T-0091→0092→0093→0094.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.

## Status Updates **[REQUIRED]**

*To be added during implementation*
