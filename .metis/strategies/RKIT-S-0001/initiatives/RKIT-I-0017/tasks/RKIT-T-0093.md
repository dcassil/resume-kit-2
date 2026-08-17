---
id: job-extraction-through
level: task
title: "Job extraction through ModelAdapter; fix unknown-skill drop and co-requirement deletion; classification proposals"
short_code: "RKIT-T-0093"
created_at: 2026-08-17T16:26:27.045942+00:00
updated_at: 2026-08-17T16:26:27.045942+00:00
parent: resume-agent-model-based-resume
blocked_by: ["RKIT-T-0091", "RKIT-T-0092"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0017
---

# Job extraction through ModelAdapter; unknown-skill drop + co-requirement deletion fixed

## Parent Initiative

[[RKIT-I-0017]]

## Objective **[REQUIRED]**

Rewire `extractJobSemantics` to the ModelAdapter and delete the closed job engine: `_requirement_concepts` 11-concept lexicon (audit refs __init__.py:247-262), the unknown-skill fallback that fires only when NO known concept matched (:268-269 — verified: "Python" silently vanished from "5+ years with Python, Spark..."), the req_api-deleted-when-req_graphql-matches hack (:266-267), hardcoded industries ['SaaS'] (:514), two-string domains (:515), six-word seniority regex (:513), comma-split title/company parsing (:434-441). Requirement-classification proposals (vision section 8) are part of job extraction output.

## Acceptance Criteria **[REQUIRED]**

- [ ] `extractJobSemantics` uses the T-0091 builders/schemas; payload mapped into proposal DTO envelopes; requirement entries carry classification, seniority, industries, domains from the MODEL output (no hardcoded values).
- [ ] Named regressions: (a) unknown+known co-occurrence golden ("5+ years with Python, Spark...") retains BOTH Python and Spark in requirement proposals; (b) GraphQL+API-design golden keeps BOTH requirements; (c) every skill named in a golden JD appears in some requirement proposal (generalization assertion).
- [ ] The listed lexicon/hack paths are DELETED; grep proves the concept list and the req_api deletion are gone from production code.
- [ ] Adapter failure → typed error, never partial extraction; evidence links + model confidence on every requirement.
- [ ] Legacy job fixtures keep complete pinned outputs; smoke green (CLI ingest path may need new fake fixtures — add, don't weaken).
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Follow T-0092's adapter-injection seam exactly (same construction path).
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0091/0092. Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*.
- resume-cli `_ingest_job` compat shim (from I-0001 era) consumes this output — run --smoke and check the shim still folds preferred[] correctly.

## Status Updates **[REQUIRED]**

*To be added during implementation*
