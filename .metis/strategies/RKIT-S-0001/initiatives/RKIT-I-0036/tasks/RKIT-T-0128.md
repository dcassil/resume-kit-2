---
id: fact-proposals-through-extraction
level: task
title: "Fact proposals through extraction, core validation, and career-store persistence; delete the hardcoded fact list"
short_code: "RKIT-T-0128"
created_at: 2026-08-19T17:52:18.931312+00:00
updated_at: 2026-08-19T18:09:30.296856+00:00
parent: resume-and-job-ingest-orchestration
blocked_by: [RKIT-T-0127]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0036
---

# Fact proposals through extraction, core validation, and career-store persistence; delete the hardcoded fact list

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0036]]

## Objective **[REQUIRED]**

Career facts persisted at ingest must originate from the agent extraction's `fact_proposals`, be validated by resume-core, and be persisted through career-store — closing DoD 4 (off-fixture resumes currently persist ZERO facts because `_facts_from_resume` is a hardcoded 12-entry smoke-fixture keyword list at `resume-cli/resume_cli/__init__.py:873`). Delete `_facts_from_resume` entirely; the CLI never authors facts.

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `_ingest_resume`'s fact-persistence loop consumes the extraction result's `fact_proposals` (shape per `resume-agent` proposal mapping: `fact_id`, `category`, `text`, `normalized_terms`, `source_evidence_ids`, `verification_state`, `review_required`) — routed through a core validation step (existing core grounding/validation surface, or the T-0127 construction surface's validated fact output; NOT ad-hoc CLI filtering) before `store.upsertFact`.
- [ ] `_facts_from_resume` and its keyword table are deleted from `resume_cli/__init__.py`; no fixture keyword list remains anywhere in resume-cli.
- [ ] Evidence passed to `upsertFact` derives from the proposal's `source_evidence` spans (real spans from the extraction), not CLI substring search; `source="resume"` retained; store-owned verification state respected — the CLI must not pre-assert states; document-derived proposals persist per the proposal's own state.
- [ ] An off-fixture resume (second vocabulary, e.g. Python/Spark/Kafka) with a pinned fake-adapter fixture persists exactly the facts its fixture defines — a failing test guards the old zero-fact behavior. (The full off-fixture fixture set is T-0130's; this task lands the minimal off-fixture fact fixture + test.)
- [ ] Facts the extraction does NOT propose are not persisted (no residual hardcoded fact ids like `fact_azure` appear for a resume that never mentions them).
- [ ] Existing smoke expectations for persisted facts still pass — if the smoke fixture's persisted-fact set changes (proposal-derived ids replace hardcoded ids), update smoke/E2E expectations deliberately and record the mapping in the status update. Protected `tools/run_smoke.py` may require a lockstep edit — apply directly, commit `--no-verify`, flag for Daniel's approval pass.
- [ ] Gates green: `--pr`, `--smoke`; new test modules bridged per the `test_tests_contract` subprocess pattern.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- `upsertFact` signature: `upsertFact(fact, evidence, source, policy)` (`career-store/career_store/store.py:272`), fact fields `fact_id/type/text/normalized_terms/verification_state`. Proposal `category` maps to fact `type` (skill→skill, experience/experience_highlight→experience, etc.) — keep the mapping as a declared table in one place, not scattered conditionals.
- Verification states available: `source_stated`, `user_verified`, `imported`, `inferred`, `unknown`. Extraction proposals arrive as `inferred`/`source_stated`; persist as proposed.
- The smoke fixture's fake-adapter extraction fixture must propose the facts smoke expects downstream (AWS/GraphQL gap-resolution flows rely on which facts exist after ingest) — grep `fixtures/expected/` for fact-id references before changing ids; prefer keeping historical fact ids in fixture payloads where smoke depends on them.
- Watch config `guardrails.allow_inferred_facts` (section 13) — if false, inferred proposals may need routing to review rather than silent persistence; follow existing core/store policy behavior, don't invent CLI policy.

### Dependencies
RKIT-T-0127 (construction surface and validated extraction path).

### Risk Considerations
Fact-id churn can break match snapshots and gap-resolution smoke steps. The temptation to "filter proposals in the CLI" recreates the removed fixture logic — validation lives in core/store only.

### Execution profile
Recommended Agent: opus + medium

## Status Updates **[REQUIRED]**

- 2026-08-19: Implemented proposal-derived ingest persistence path. `canonicalResumeFromExtraction` now returns core-validated `fact_proposals` with a single core category-to-type table and evidence derived from extraction evidence spans; `_ingest_resume` persists those proposals through `upsertFact` and removed the CLI keyword fact table/substr span lookup. Added Python/Spark/Kafka off-fixture fake-adapter fixture and integration test bridged through `test_tests_contract`. Smoke fixture now pins historical fact IDs where downstream flows require them (`fact_react`, `fact_typescript`, `fact_node`, `fact_postgresql`, `fact_azure`, `fact_api`, `fact_saas`, `fact_workflow`, `fact_responsive`, `fact_leadership`) and a new rewrite replay fixture was keyed for proposal-derived allowed facts. Focused tests and direct smoke harness pass; full gates still pending.
