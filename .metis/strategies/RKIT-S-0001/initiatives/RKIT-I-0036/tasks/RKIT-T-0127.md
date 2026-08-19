---
id: resume-ingest-via-agent-extraction
level: task
title: "Resume ingest via agent extraction + core canonical construction; delete CLI schema construction and fabricated fallbacks"
short_code: "RKIT-T-0127"
created_at: 2026-08-19T17:52:18.855363+00:00
updated_at: 2026-08-19T18:09:29.488342+00:00
parent: resume-and-job-ingest-orchestration
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0036
---

# Resume ingest via agent extraction + core canonical construction; delete CLI schema construction and fabricated fallbacks

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0036]]

## Objective **[REQUIRED]**

Make `resume ingest` build its canonical resume from the agent extraction proposal via a resume-core-owned construction surface, instead of the CLI's fixture-tuned text parser. Delete the CLI-owned schema construction (`_resume_from_text` body), date normalization (`_normalize_date`), and every fabricated fallback (`_candidate_title` inventing "Software Engineer", `_experience_entries` inventing "Source Resume"/"Software Developer", `_company_title` default title). Missing data becomes a typed, user-visible outcome — never an invented claim in base.json.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] A new resume-core public surface (e.g. `canonicalResumeFromExtraction(extraction, source, config)` in `resume_core`, name final per core conventions) converts a `resume_semantic_extraction` proposal result (`fact_proposals` + `source_evidence` per `resume-agent/resume_agent/__init__.py:318` mapping) plus source metadata into the structured input `normalizeResume` accepts, carrying per-field `ResumeField` provenance (`resume-core/resume_core/schemas.py:109`) with `source_stated` verification for document-derived content. Guardrail/manifest lockstep edits for the new core surface follow the T-0104 pattern (protected `tools/resume_core_guardrails.py` edited directly, commit `--no-verify`; Daniel approves in one straight-jacket pass).
- [ ] `_ingest_resume` (`resume-cli/resume_cli/__init__.py:357`) pipeline becomes: read → `sanitizeText` → `extractResumeSemantics` → core construction surface → `normalizeResume` → `validateResume` → persist base.json/working.json + hash. No CLI-side field parsing remains.
- [ ] `_resume_from_text` schema-construction body, `_normalize_date`, `_candidate_title`, `_experience_entries`, `_company_title`, `_section_text`/`_skills_from_resume`/`_education_items` text-parsing helpers are deleted from `resume_cli/__init__.py` (dead helpers they alone used go too).
- [ ] Empty or error extraction yields a typed ingest failure in the result envelope (status/error surface per I-0035 envelope: `{status, exit_code, errors[]}`); there is NO fallback branch that constructs resume content in the CLI.
- [ ] A resume with no stated title/experience ingests to either a typed validation outcome or a base.json with those fields absent/unknown — asserted by test that base.json contains no "Software Engineer"/"Source Resume"/"Software Developer" strings not present in the source document.
- [ ] Persisted base.json conforms to the section-4 CanonicalResume shape (A-0006-aligned; per-field provenance woven by core), verified by a DTO conformance assertion against `CANONICAL_RESUME_SCHEMA`.
- [ ] Existing smoke/E2E fixture ingest still passes with the fake-adapter fixture supplying extraction (`fixtures/resume-agent/fake-adapter/`, key = sha256(prompt_template_id, output_schema_id, canonical_input_json)); base.json immutability rule preserved (write only in ingest/re-ingest path with explicit guard, per `tools/resume_cli_guardrails.py` scan).
- [ ] `resume_cli/__init__.py` stays ≤1500 lines (currently 1483 — deletions here should net negative; new logic goes to private modules like `resume_cli/_ingest.py` if needed).
- [ ] Gates green: `python3 tools/run_gate.py --pr` and `--smoke`; new test modules bridged per the `test_tests_contract` subprocess pattern.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Extraction result shape: `{proposals/fact_proposals, source_evidence, uncertainty, model_metadata, requires_validation}`; fact proposals carry `category` (basics keys, skill, experience, experience_highlight, education, certification, project, employment), `text`, `normalized_terms`, `source_evidence_ids`, `verification_state`, plus category extras (`employment` start/end dates, `skill_category`). The core construction surface groups by category into CanonicalResume sections; employment/experience dates go through core's `dates.py` canonicalization (T-0007) — this is where `_normalize_date`'s job lands.
- Name/basics: from `basics` category proposals only; absent → omit/empty, never default.
- Keep `resume ingest` result envelope fields (`base_hash`, `extraction`, `validation`, `sanitation`, `checkpoints`) stable; smoke depends on them.
- Fake-adapter fixtures for the existing smoke resume already exist; if the core construction changes canonical output, expected snapshots (`fixtures/expected/normalized-resume.json`) and snapshot suite will churn — review diffs deliberately, regenerate ×2 to prove no drift.
- FORBIDDEN protected files (edit directly + `--no-verify` only when task-required, list in prompt): `tools/resume_core_guardrails.py` (required here, lockstep), everything else protected untouched.

### Dependencies
RKIT-I-0035 envelope/entrypoint (landed); RKIT-I-0017 extraction surfaces (landed); RKIT-I-0001 core DTOs (landed). Blocks T-0128 (facts) and T-0130 (close-out).

### Risk Considerations
The core construction surface is new public API on a guardrail-pinned package — wrong shape cascades into T-0128/0129/0130 and I-0037+. Keep it minimal: one function, JSON-in/JSON-out, no CLI-specific concepts. Snapshot churn is expected; verify semantic equivalence, not byte identity, when reviewing.

### Execution profile
Recommended Agent: opus + high

## Status Updates **[REQUIRED]**

- 2026-08-19: Task activated; codex dispatched with full prompt (scratchpad t0127_prompt.md) covering: new core surface `canonicalResumeFromExtraction`, `_ingest_resume` rewire, CLI parser deletion set, authorized lockstep edit to protected `tools/resume_core_guardrails.py`, gate-bridging requirement, snapshot ×2 no-drift verification. Driver will independently probe the fabrication guard and empty-extraction typed failure on review.
- 2026-08-19: Added `resume_core.canonicalResumeFromExtraction` with source-evidence-backed ResumeField provenance, exported it through the core public surface/manifest, and made the authorized minimal `tools/resume_core_guardrails.py` allowlist update. Rewired `_ingest_resume` to call extraction -> core construction -> normalize -> validate and removed the CLI resume parser/default-fabrication helpers. Focused core constructor unit tests pass (`python3 -m unittest tests.unit.test_canonical_resume_from_extraction_unit`).
- 2026-08-19: Verification checkpoint: PR gate passed (`python3 tools/run_gate.py --pr --root .`, 656 tests OK), smoke gate passed (`python3 tools/run_gate.py --smoke --root .`), snapshot generator wrote 13 expected blocks twice with identical checksums and no `fixtures/expected` git diff, and `wc -l resume-cli/resume_cli/__init__.py` is 1351. Fabrication guard passed, and a negative injected-default check failed as expected on `Software Engineer`. Final Straight Jacket verify reports only the task-authorized `tools/resume_core_guardrails.py` checksum mismatch pending human `straight-jacket update tools/resume_core_guardrails.py`.