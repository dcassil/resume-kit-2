---
id: resume-and-job-ingest-orchestration
level: initiative
title: "Resume and Job Ingest Orchestration"
short_code: "RKIT-I-0036"
created_at: 2026-08-13T20:41:37.795106+00:00
updated_at: 2026-08-13T20:41:37.795106+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0035", "RKIT-I-0001", "RKIT-I-0017"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Resume and Job Ingest Orchestration Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. Real ingest wiring exists — sanitizeText → extractResumeSemantics → normalizeResume → validateResume, with fact persistence — but it is threaded through fixture-hardcoded, CLI-owned domain logic that produces nothing off-fixture and can fabricate content:

- `_facts_from_resume` is a hardcoded 12-entry smoke-fixture fact list keyed on fixture keywords (`resume_cli/__init__.py:474-492`); an off-fixture resume (Python/Spark/Kafka) persists zero career facts, failing DoD 4. Fact proposal generation is CLI-owned instead of agent/core-originated (vision 14.A.8).
- Job requirement extraction is CLI-implemented: `_requirements_from_job_text`/`_requirements_for_text` hardcode the smoke/E2E requirement vocabulary with fixture regexes (`resume_cli/__init__.py:653-703`) and `_looks_like_requirement` uses a fixture keyword list (`:675-678`), overriding the agent extraction path whenever it lacks requirements — section 12 assigns raw JD semantic extraction to the agent with code validation. Requirement weight is a hardcoded 1.0 (`:467`) against "Requirement weighting: Config/rules authoritative".
- `_resume_from_text` constructs the canonical resume schema inside the CLI (`resume_cli/__init__.py:412-442`) including `_normalize_date` (`:584-609`) — canonical construction and date normalization are resume-core responsibilities (vision sections 5 and 12; duplicated domain rules forbidden per CONTRACT_SURFACE_ALIGNMENT.md).
- Fabricated fallbacks can put invented claims into base.json: `_candidate_title` invents "Software Engineer" (`:503`), `_experience_entries` invents a "Source Resume"/"Software Developer" entry (`:552`), `_company_title` defaults the title (`:573-574`) — contradicting the no-fabrication principle.
- DTO drift vs section 4: the CLI-built CanonicalResume carries no per-field ResumeField provenance/verification (`:420-442`); the CLI-built JobRequirement omits type/years and renames id/importance fields.
- `resume job ingest` accepts only a file path (`resume_cli/__init__.py:43-44`); the TEST_SPEC surface mandates `<file-or-url-text>`.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Ingest = agent extraction + core normalization. Resume and JD semantic extraction come from resume-agent proposal surfaces (RKIT-I-0017, per RKIT-A-0003 — DeterministicFakeAdapter in all official gates); canonical schema construction, date normalization, and validation come from resume-core (RKIT-I-0001, with the RKIT-A-0006 DTO shapes: per-field ResumeField provenance/verification, JobRequirement with type/years, `imported` verification state available).
- Remove every CLI-owned extraction/normalization path listed in Context: `_facts_from_resume`, `_requirements_from_job_text`, `_requirements_for_text`, `_looks_like_requirement`, `_resume_from_text`'s schema construction, `_normalize_date`, and the weight literal.
- Remove fabricated-content fallbacks; missing titles/experience surface as typed validation outcomes or unknowns, never invented values in base.json.
- Career facts persist off-fixture: proposals originate from agent extraction, are core-validated, and persist through career-store (DoD 4).
- `resume job ingest` accepts a file path, a URL, or pasted text.
- base.json immutability after ingest is preserved and re-verified.

**Non-Goals:**
- Match/resolve/inspect behavior — RKIT-I-0037.
- Terminal presentation, config contract, entrypoint — RKIT-I-0035.
- Agent adapter internals and extraction quality — RKIT-I-0017 (resume-agent group); core normalization internals — RKIT-I-0001 (resume-core group).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- No requirement-vocabulary, fact-list, date-parsing, or schema-construction logic remains in resume-cli; ingest calls only public resume-agent and resume-core surfaces (section 12 split: agent proposes, code validates).
- An off-fixture resume processed through ingest (fixture-pinned fake adapter supplying its extraction) persists the facts its fixture defines — zero-fact off-fixture behavior becomes a failing test, closing DoD 4.
- base.json written by ingest contains only content traceable to the source document or validated agent proposals; no invented titles, companies, or experience entries (TEST_SPEC ingest: "Does not allow agent-generated unsupported content into base").
- Persisted CanonicalResume/JobRequirement artifacts conform to the section 4 shapes as realigned by RKIT-A-0006 (per-field provenance; JobRequirement type/years; no renamed fields); requirement weight comes from config/rules, not a literal.
- URL and pasted-text JD input produce the same validated JobDescription artifact path as file input.

### Dependencies
- RKIT-I-0035 (entrypoint, config, workspace, result envelope).
- RKIT-I-0001 Resume-Core Canonical Contracts, Validation, And Normalization (A-0006-aligned DTOs and normalization surfaces).
- RKIT-I-0017 Resume-Agent Model-Based Resume and Job Semantic Extraction (extraction proposals per RKIT-A-0003).

### Blocked Status
- Blocked by RKIT-I-0035, RKIT-I-0001, RKIT-I-0017 (frontmatter matches). Former ADR uncertainty is resolved: RKIT-A-0003 is decided (adapter architecture, fake-adapter gates), so this is ordinary initiative sequencing, not an ADR block.

## Detailed Design **[REQUIRED]**

- **Resume ingest pipeline.** file/text → `sanitizeText` → agent extraction proposal (schema-validated structured output per RKIT-A-0003 item 1) → core `normalizeResume` builds CanonicalResume with per-field ResumeField provenance (`source_stated` for document-derived content) → `validateResume` → persist base.json + provenance artifact. Fact proposals ride the same extraction result; core validates them and career-store persists with store-owned verification state — the CLI never authors facts.
- **Job ingest pipeline.** Input resolver (existing path → read file; http(s) URL → fetch text; otherwise treat the argument as pasted text) → sanitize → agent JD extraction proposal → core requirement normalization/classification (type, years, importance from the documented DTO; weight from config rules) → persist job.json.
- **Removal set.** Delete `_facts_from_resume`, `_requirements_from_job_text`, `_requirements_for_text`, `_looks_like_requirement`, `_normalize_date`, the `_candidate_title`/`_experience_entries`/`_company_title` fallbacks, and the schema-construction body of `_resume_from_text`. No CLI fallback branch exists when extraction returns nothing: empty extraction is a typed, user-visible ingest failure — a fallback branch is where the fixture tuning grew last time.
- **Migration note.** Workspaces created by the old path may hold base.json with fabricated entries or drifted DTOs; explicit re-ingest is the documented remedy (base.json is only ever replaced by explicit re-ingest, preserving the immutability rule).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- New off-fixture ingest fixture (second vocabulary, e.g. Python/Spark/Kafka) with pinned fake-adapter extraction: asserts facts persist, base.json is faithful, and no fixture-keyword dependence remains.
- Strengthen TEST_SPEC job ingest: URL and pasted-text cases — mandated by the `<file-or-url-text>` surface but previously untested/unspecified, the gap that let file-only input ship.
- Fabrication guard: ingest of a resume with no stated title/experience yields a typed outcome, and base.json contains no invented "Software Engineer"/"Source Resume" entries — makes "Does not allow agent-generated unsupported content into base" observable.
- DTO conformance assertions on persisted artifacts against the A-0006-realigned section 4 schemas.
- Boundary guardrail: resume-cli defines no date-parsing/requirement-keyword/schema-construction code (import- or AST-level check) to prevent regrowth.
- All official gates run on the DeterministicFakeAdapter (RKIT-A-0003 item 4); no live model in protected suites.

## Alternatives Considered **[REQUIRED]**

- Keep the CLI heuristics as a fallback when agent extraction is sparse: rejected — section 12 assigns extraction to the agent with code validation; the fallback branch is precisely where fixture-tuned logic accumulated, and it silently bypasses proposal validation.
- Generalize the CLI regexes instead of removing them: rejected — wrong owner regardless of quality (CONTRACT_SURFACE_ALIGNMENT.md forbids duplicated domain rules in resume-cli), and regex generality against arbitrary resumes/JDs is exactly the problem the model adapter exists to solve.
- Fabricate neutral placeholders so the pipeline always completes: rejected — the no-fabrication principle applies to base.json above all; missing data must surface as validation errors, not invented claims.

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Route resume ingest through agent extraction + core normalization with A-0006 DTOs; delete `_resume_from_text` construction and `_normalize_date`.
2. Route fact proposals through extraction → core validation → store persistence; delete `_facts_from_resume`.
3. Route JD ingest through agent extraction + core requirement normalization; delete `_requirements_*` and the weight literal.
4. Remove fabricated fallbacks; add typed empty-extraction/missing-section outcomes.
5. Add URL/pasted-text input resolution for `job ingest`.
6. Off-fixture fixture, fabrication guards, DTO conformance, and TEST_SPEC strengthening.
