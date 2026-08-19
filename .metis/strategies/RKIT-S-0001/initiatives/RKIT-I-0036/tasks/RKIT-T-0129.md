---
id: job-ingest-via-agent-extraction
level: task
title: "Job ingest via agent extraction + core requirement normalization; URL and pasted-text input; delete CLI requirement vocabulary"
short_code: "RKIT-T-0129"
created_at: 2026-08-19T17:52:19.002638+00:00
updated_at: 2026-08-19T18:27:34.868061+00:00
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

# Job ingest via agent extraction + core requirement normalization; URL and pasted-text input; delete CLI requirement vocabulary

## Parent Initiative **[CONDITIONAL: Assigned Task]**

[[RKIT-I-0036]]

## Objective **[REQUIRED]**

Route `resume job ingest` entirely through agent JD extraction (`extractJobSemantics`) plus resume-core requirement normalization (`normalizeJobModel`), deleting the CLI-owned requirement vocabulary (`_requirements_from_job_text`, `_requirements_for_text`, `_looks_like_requirement`, `_requirements_from_extraction` fallback chain, the local `_requirement` constructor with its hardcoded `weight: 1.0`, and `_job_from_text` construction). Extend input acceptance to the mandated `<file-or-url-text>` surface: existing file path, http(s) URL, or pasted text.

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `_ingest_job` (`resume-cli/resume_cli/__init__.py:396`) builds `normalizeJobModel`'s input from the `extractJobSemantics` result (which already returns `requirements`, `preferred`, `requirement_proposals`, classification proposals, `terminology`, `source_evidence`, `uncertainty`) — no CLI regex/keyword requirement extraction remains; empty/error extraction is a typed ingest failure with NO fallback branch.
- [ ] Deleted from `resume_cli/__init__.py`: `_requirements_from_job_text`, `_requirements_for_text`, `_looks_like_requirement`, `_requirements_from_extraction`, `_requirement`, `_job_from_text` construction body, `_job_section_heading` and any helpers only they used. The hardcoded `weight: 1.0` literal is gone; weights come from core config resolution (`matching_config.py` defaults / section-13 `matching.weights`).
- [ ] Persisted `job/current.json` JobRequirement entries conform to the section-4 DTO (`requirement_id`, `classification`, `concept`, `importance`, `weight`, `source_text`, `normalized_terms`, `years`) — no renamed/omitted fields; source text retained per TEST_SPEC.
- [ ] The required/preferred compatibility shim (fold `preferred` into `requirements`) is resolved per this initiative's ownership note: either properly consumed downstream or retained with the superset preserved losslessly — decide from what I-0037 match code reads TODAY and document the decision in the status update; do not silently drop preferred.
- [ ] `resume job ingest <arg>` input resolver: existing path → read file; `http://`/`https://` → fetch text (stdlib urllib, typed network-failure error); otherwise → treat the argument as pasted JD text. All three paths produce the same validated job.json artifact shape; covered by tests (URL test uses a local stub/injected fetcher — no live network in gates).
- [ ] `cli_surface.json` / argv arity (`resume_cli/_argv.py`) updated to accept the argument form without breaking the I-0035 exact-arity enforcement; `resume job ingest --help` unaffected.
- [ ] Gates green: `--pr`, `--smoke`; new tests bridged per `test_tests_contract` pattern.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- `extractJobSemantics` result already carries `job_id`, `title`, `company`, `source`, plus proposal arrays — map directly; title/company absent → omit, never default from line heuristics.
- `normalizeJobModel` accepts `requirements`/`preferred` arrays and computes weights via `_configured_default_weight` with section-13 config — pass `_config(workspace)` through as today.
- URL fetch: keep it a thin injectable seam (e.g. `fetch=` parameter or module-level function monkeypatched in tests) so gates stay hermetic; sanitize fetched text through `sanitizeText` like file input.
- Pasted-text detection order matters: path-exists check first, then URL scheme, then text — a JD pasted as one arg containing "/" must not be treated as a missing file. Document the precedence in `--help`/TEST_SPEC wording.
- Watch argv-safety lesson from I-0035: exact arity enforced BEFORE side effects; the new argument is still exactly one positional.

### Dependencies
RKIT-T-0127 (shared typed empty-extraction failure shape); independent of T-0128.

### Risk Considerations
Fixture JD extraction fixtures must propose the full requirement set smoke's match snapshots expect (requirement ids feed match/gap flows); requirement-id churn cascades into `fixtures/expected/*-match.json`. Verify snapshot diffs semantically and regenerate ×2 for no-drift.

### Execution profile
Recommended Agent: opus + medium

## Status Updates **[REQUIRED]**

### 2026-08-19 implementation update

- Routed `resume job ingest` through `extractJobSemantics` and `normalizeJobModel`; removed CLI requirement regex/vocabulary helpers and the local `weight: 1.0` constructor.
- Added file/URL/pasted-text resolver with existing-path precedence, injectable stdlib URL fetch seam, sanitation before extraction, typed URL and empty/error extraction failures, and no fallback requirements.
- Kept the lossless preferred compatibility superset in persisted `requirements` while preserving `preferred`, because `resume_core.scoreMatch` already consumes both arrays and dedupes by `requirement_id`, but protected smoke still reads `job["requirements"]`.
- Added integration coverage for file, URL-stub, and pasted-text ingest; DTO shape; config-driven weights; typed URL failure; and typed empty/error extraction failure. Bridged the module through `tests/contract/test_tests_contract.py`.
- Updated job fake-adapter fixtures to pin smoke-compatible requirement IDs and added the routed rewrite fixture needed by smoke after job extraction IDs/terms changed.
- Verification run: `python3 tools/run_gate.py --pr --root .` passed; `python3 tools/run_gate.py --smoke --root .` passed; snapshot regeneration twice produced no `fixtures/expected` diff; `wc -l resume-cli/resume_cli/__init__.py` reported 1382 lines.
- Known external issue: `straight-jacket verify --json` still reports a checksum mismatch for protected `tools/resume_core_guardrails.py`; this was present before implementation and this task did not edit protected files.
