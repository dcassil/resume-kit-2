---
id: resume-kit-2
level: vision
title: "Resume Tailoring Platform"
short_code: "RKIT-V-0001"
created_at: 2026-08-13T20:16:33.463659+00:00
updated_at: 2026-08-13T20:16:33.463659+00:00
archived: false

tags:
  - "#vision"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Resume Tailoring Platform Vision

Source: `PRODUCT_VISION_AND_CONTRACTS.md`

## Purpose **[REQUIRED]**

Build a resume-tailoring system that improves job-specific relevance and ATS compatibility without fabricating, exaggerating, or silently mutating a candidate's career history.

The system treats a resume as a projection of a persistent career knowledge model, not as the source of truth itself. It must be reproducible, inspectable, safe to iterate on, and clear about which facts are verified, inferred, missing, or unsupported.

## Product/Solution Overview **[CONDITIONAL: Product/Solution Vision]**

The platform is organized around three primary domain objects:

- Career Knowledge Model: durable, evidence-backed facts about the candidate.
- Job Requirements Model: normalized representation of what a particular job requests.
- Resume Representation: a job-specific selection and wording of verified career facts.

The system supports CLI, MCP, agent, renderer, and future plugin/UI surfaces while keeping business logic in reusable domain packages. Agent reasoning is used only where semantic understanding or natural-language generation is useful; deterministic code owns state, facts, scoring, workflow transitions, constraints, mutations, provenance, and audit trails.

## Current State **[REQUIRED]**

The repo contains the contract-first package structure, surface manifests, fixtures, guardrails, smoke/E2E documents, and implementation playbook for the target architecture. The 2026-08-12/13 implementation waves added ~7,500 lines across all eight runtime packages: the PR gate (188 contract/boundary/guardrail tests), smoke gate, and future-contract gate are green, but a full alignment audit (2026-08-13) found actual product depth at roughly 25-55% per package, with fixture-tuned honesty gates, DTO/enum drift from the section 4 contracts, a workflow state machine the CLI never drives, and a release-candidate test tier that exists only on paper. Six ADRs (RKIT-A-0001 through RKIT-A-0006) were decided on 2026-08-13 to resolve the open runtime/contract questions — including RKIT-A-0006, which rules that documented contract semantics are authoritative over implementation drift — and all initiatives were re-baselined against the audit's verified findings.

Implementation authority is intentionally document-driven: `CONTRACT_SURFACE_ALIGNMENT.md`, package `TEST_SPEC.md` files, surface manifests, `PRODUCT_VISION_AND_CONTRACTS.md`, `SMOKE_TEST.md`, and `E2E_TEST.md` define the product and test gates. Existing or prior resume-kit behavior is not authoritative.

## Future State **[REQUIRED]**

A user can initialize a workspace, ingest a resume, persist evidence-backed career facts, ingest a job description, compute deterministic requirement-level match results, resolve gaps through targeted questions, generate grounded tailoring operations, reject unsupported claims, produce a final resume, render delivery formats, and reconstruct the run through a complete audit trail.

The package architecture remains explicit:

- `resume-core`: deterministic domain engine for schemas, normalization, validation, matching, grounding, selection, and change application.
- `career-store`: local SQLite career knowledge store with evidence, verification state, conflict handling, and transactions.
- `career-mcp`: narrow semantic tool surface over career-store with no raw SQL or unrestricted mutation.
- `workflow`: state machine, checkpoints, run manifests, recovery, and audit semantics.
- `resume-agent`: proposal engine for semantic extraction, questions, answer interpretation, and grounded rewrite proposals.
- `resume-render`: semantic-neutral rendering and rendered-output validation.
- `resume-cli`: reference workflow orchestrator and developer-facing client.
- `resume-plugin`: optional thin adapter for host/chat/IDE presentation.

## Major Features **[CONDITIONAL: Product Vision]**

- Canonical resume ingest: parse arbitrary resumes into structured, provenance-aware representations and report ATS/encoding/structure problems deterministically.
- Career knowledge persistence: store durable facts, evidence, relationships, verification states, conflicts, and user confirmations in SQLite.
- Job model ingest: parse job descriptions into requirements, preferences, role/domain metadata, and terminology, then normalize them through deterministic contracts.
- Explainable matching: score resume/job alignment with reproducible requirement-level results where hard requirements cannot be hidden by a high aggregate score.
- Gap resolution: use aliases, known facts, inferred candidates, and targeted user questions to resolve missing requirements without escalating unverified facts silently.
- Grounded tailoring: agents propose change operations and language, while code validates claims, provenance, constraints, and mutation safety before applying changes.
- Rendering and validation: produce ATS-safe, human-readable Markdown/DOCX/PDF outputs without allowing renderers to alter career truth.
- Auditability: persist run manifests, change operations, fact updates, scores, validations, and rejected proposals so every final resume can be explained.

## Success Criteria **[REQUIRED]**

The initial product is complete enough for real use when it can:

1. Initialize a workspace.
2. Ingest a representative resume and produce valid canonical JSON.
3. Persist career facts and evidence in SQLite.
4. Ingest and normalize a job description.
5. Produce deterministic requirement-level match results.
6. Use stored facts to resolve resume omissions.
7. Ask targeted questions about unresolved high-value requirements.
8. Persist user-verified knowledge without silent verification escalation.
9. Produce grounded tailoring operations and reject deliberately hallucinated operations.
10. Produce a final working resume, re-score it, and explain the improvement.
11. Pass final ATS, grounding, structure, and render validation.
12. Render at least Markdown and DOCX.
13. Produce a complete audit report.

Repo-level completion means package contract suites, boundary tests, guardrails, PR/main/release gates, smoke tests, and E2E fixtures all pass without weakening tests, manifests, fixtures, or guardrails.

## Principles **[REQUIRED]**

- The agent proposes meaning and language; code owns facts, state, scoring, constraints, mutations, provenance, and truth.
- Resumes are projections of career knowledge, not the source of truth.
- Unsupported facts, inflated titles, exaggerated years, invented metrics, fabricated scope, and ungrounded equivalences must be rejected.
- Deterministic package owners expose public APIs; adapters and delivery surfaces do not own business logic.
- Dependency direction flows toward domain logic and away from CLI, MCP, plugin, UI, and renderer surfaces.
- Agent output is schema validated before downstream use and never becomes official state merely because it is plausible.
- Renderers are semantic-neutral and return layout constraints instead of silently shortening or rewriting content.
- Every meaningful decision, mutation, score change, and validation outcome should be explainable after the fact.

## Constraints **[REQUIRED]**

- `resume-core` must not import CLI, MCP, plugin, renderer, or persistence implementation concerns.
- `career-store` must not expose direct SQLite mutation to agents, MCP callers, CLI, or adapters.
- `career-mcp` must not provide raw SQL, unrestricted update/delete, or broad persistence escape hatches.
- `resume-agent` must not set official scores, directly mutate resumes or SQLite, verify inferred facts, or bypass validation.
- `resume-render` must not rewrite semantic resume content or make career-truth decisions.
- `resume-cli` orchestrates through public APIs only and must preserve workflow checkpoints.
- `resume-plugin` is an adapter and must not contain independent scoring, schemas, mutation logic, ATS sanitation, or learning behavior.
- Guardrails, boundary tests, surface manifests, fixture truth, and suite gates are product safety infrastructure and may not be weakened without explicit user permission.
- Sensitive career data should be kept local/user-scoped unless explicitly deployed otherwise, and prompts/logs should include only the minimum necessary data.