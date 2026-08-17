---
id: resume-agent-model-based-resume
level: initiative
title: "Resume-Agent Model-Based Resume and Job Semantic Extraction"
short_code: "RKIT-I-0017"
created_at: 2026-08-13T20:41:37.214449+00:00
updated_at: 2026-08-17T16:58:31.083405+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0016]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-agent-model-based-resume
---

# Resume-Agent Model-Based Resume and Job Semantic Extraction Initiative

## Context **[REQUIRED]**

Package: `resume-agent`. Resume and job extraction are implemented but as a closed, fixture-tuned pattern engine — not extraction. Verified empirically: a non-fixture ML-engineer resume (Python, TensorFlow, Kubernetes, GCP, Go, PhD) extracts ONLY its title line — no skills, experience, education, certifications, projects, or employment structure.

The mechanisms, all in `resume_agent/__init__.py`: `_terms_for` is a closed 14-entry lexicon copied from the test fixtures (:100-125); `resume_patterns` hardcodes the literal fixture phrase "Led a small team of three developers" (:391) and fixture-specific labels (:362-394); the years-of-experience regex requires the literal phrase "software development experience" (:337-341); `_years_phrase` recognizes only word numerals one..ten (:286-290). Job side: `_requirement_concepts` recognizes exactly 11 hardcoded concepts (:247-262); the unknown-skill fallback (:268-269) fires only when no known concept matched, so "Python" silently vanished from "5+ years with Python, Spark..."; :266-267 deletes `req_api` whenever `req_graphql` matches, so a JD requiring both GraphQL and API design loses its API-design requirement; industries are hardcoded to `['SaaS']` (:514), domains to two strings (:515), seniority to a six-word regex (:513); title/company parsing splits line one on the first comma (:434-441). Uncertainty is a keyword grep for "ambiguous|various|several" (:406-413) and confidence values are hardcoded "high"/"medium" strings (:73-92).

The spec certified this: TEST_SPEC.md pins assertions to exact fixture tokens (:43, :57-58), so a hardcoded keyword matcher fully satisfies the spec while violating vision section 2's "Parse arbitrary resumes" goal — which is exactly the implementation that resulted.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Replace the fixture regex engine with model-based extraction through the RKIT-I-0016 `ModelAdapter`: arbitrary realistic resume and job text produce schema-constrained extraction proposals (skills, experience, education, certifications, projects, employment structure; JD requirements, seniority, industries, domains).
- Never silently drop content: unknown skills and terms outside any lexicon appear in proposals (with model-sourced confidence) instead of vanishing.
- Requirement-classification proposals (vision section 8) emitted as part of job extraction, with uncertainty/confidence coming from the model output — not keyword greps or hardcoded strings.
- Strengthen the extraction spec so a keyword matcher can no longer pass it.

**Non-Goals:**
- The adapter protocol, fake runtime, config block, and manifest drift fixes — RKIT-I-0016 owns the seam this initiative calls through.
- Clarification questions and answer interpretation (RKIT-I-0018); rewrite proposals (RKIT-I-0019); equivalence proposals (RKIT-I-0020); call-audit records and eval-harness infrastructure (RKIT-I-0021), though extraction golden fixtures created here feed that harness.
- No verification, scoring, or persistence: extraction outputs remain proposals that resume-core validates.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

1. A non-fixture realistic resume yields structured proposals for every populated section — fixing the verified only-the-title failure rooted in `__init__.py:362-394` and :337-341.
2. Unknown JD skills co-occurring with known concepts are never dropped — fixing the fallback bug at `__init__.py:268-269` (verified: "Python" silently lost).
3. Co-required concepts never delete each other — removing the :266-267 hack that deletes `req_api` whenever `req_graphql` matches.
4. Closed lexicons (`_terms_for` :100-125, `_requirement_concepts` :247-262, industries :514, domains :515, seniority :513, `_years_phrase` :286-290, comma-split title parsing :434-441) are retired as recall mechanisms; extraction recall comes from the model, deterministic code keeps only validation.
5. Uncertainty and confidence are model-sourced fields in the proposal DTOs, replacing the :406-413 keyword grep and the :73-92 hardcoded strings (vision section 8 ambiguity-resolution responsibility).
6. Extraction proposals preserve evidence links to source text so resume-core can validate grounding; outputs remain schema-constrained proposals requiring validation, with no scoring, persistence, or mutation.

## Detailed Design **[REQUIRED]**

- **Schemas.** Resume-extraction and job-extraction output schemas aligned to the section 4.2 shapes (CanonicalResume-shaped resume proposal; JobModel-shaped job proposal with requirement entries carrying classification, seniority, industry/domain fields). Each extracted item carries source-evidence references (the text span or line it came from) and a model-sourced confidence.
- **Prompt/input builders.** Deterministic builders assemble the extraction context (raw text plus schema id) for `ModelAdapter.complete`; prompt templates are versioned assets so RKIT-I-0021 can hash them.
- **Behavior.** The adapter's schema-validated payload is mapped into the existing proposal DTO envelopes (`requires_validation`, deterministic IDs). Items the model marks uncertain surface with explicit uncertainty fields rather than being dropped; nothing is filtered by membership in a hardcoded list.
- **Migration.** The regex/lexicon paths are deleted, not left as fallbacks — a silent deterministic fallback would reintroduce the closed-world failure mode under provider errors. Provider failure surfaces as the typed taxonomy from RKIT-I-0016.
- **Gates.** Official gates run the `DeterministicFakeAdapter` with pinned extraction outputs for both the legacy fixtures and new non-fixture golden inputs.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Spec strengthening (required by this initiative, per the audit):** TEST_SPEC's fixture-token assertions (:43, :57-58) are augmented with non-fixture golden inputs — held-out realistic resumes/JDs (including the ML-engineer probe profile) with pinned fake-adapter outputs — plus generalization assertions: every skill named in a golden JD appears in some requirement proposal; co-occurring known/unknown skills are both retained; GraphQL+API JDs keep both requirements. The current spec is satisfiable by a keyword matcher, which is exactly what happened; the strengthened spec must not be.
- Contract tests for schema conformance of both extraction surfaces, evidence-reference presence, and model-sourced confidence fields.
- Negative tests: adapter `schema_invalid`/`provider_error` propagate as typed errors, never as partial silent extraction.
- Boundary guardrails stay green; smoke/E2E fixtures updated where extraction outputs feed cross-package flows.

## Alternatives Considered **[REQUIRED]**

- **Grow the lexicons/regexes incrementally.** Rejected: the closed-world approach is the failure mode being removed — recall is bounded by the list, maintenance is unbounded, and the audit verified it drops unknowns; no list reaches "arbitrary realistic" coverage.
- **Hybrid: regex first, model fallback for unmatched text.** Rejected: the :268-269 bug demonstrates that deterministic pre-filtering silently suppresses coverage; deterministic code belongs in validation of model proposals, not in recall.
- **Fine-tuned or local extraction model.** Rejected by RKIT-A-0003's provider decision: materially weaker extraction quality with identical adapter work.

## Implementation Plan **[REQUIRED]**

1. Extraction output schemas (resume + job) with evidence and confidence fields; fake-adapter fixtures for legacy and non-fixture golden inputs.
2. Resume extraction through the adapter, replacing `resume_patterns` and the years regex; delete retired paths.
3. Job extraction through the adapter, replacing `_requirement_concepts` and fixing the drop/delete defects; requirement-classification proposals included.
4. Uncertainty/confidence mapping into proposal DTOs, replacing keyword-grep uncertainty and hardcoded confidence.
5. TEST_SPEC strengthening: non-fixture goldens plus generalization assertions; wire into contract suite.

## Dependencies / Blocked Status

Blocked by RKIT-I-0016 (`blocked_by: ["RKIT-I-0016"]`) — this initiative consumes the `ModelAdapter`, fake runtime, and schema-validation seam. The former transitive ADR block is lifted: RKIT-A-0003 was decided 2026-08-13.