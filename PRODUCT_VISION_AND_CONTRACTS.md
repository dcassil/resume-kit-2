# Resume Tailoring Platform — Product Vision, Architecture, Interfaces, and Contracts

## 1. Product Vision

Build a resume-tailoring system that improves job-specific relevance and ATS compatibility without fabricating, exaggerating, or silently mutating a candidate's career history.

The system treats a resume as a **projection of a persistent career knowledge model**, not as the source of truth itself.

Three primary domain objects drive the platform:

1. **Career Knowledge Model** — durable, evidence-backed facts about the candidate.
2. **Job Requirements Model** — normalized representation of what a particular job requests.
3. **Resume Representation** — a job-specific selection and wording of verified career facts.

The system should be reproducible, inspectable, and safe to iterate on. Agent reasoning is used only where language understanding or natural-language generation is genuinely useful. Deterministic code owns state, facts, scoring, workflow transitions, constraints, mutations, and audit trails.

### Core principle

> The agent proposes meaning and language. Code owns facts, state, scoring, constraints, mutations, provenance, and truth.

---

## 2. Product Goals

The platform should:

- Parse arbitrary resumes into a canonical structured representation.
- Detect ATS, encoding, normalization, and structural problems deterministically.
- Persist candidate career knowledge in SQLite with evidence and verification state.
- Parse job descriptions into explicit requirements, preferences, role/domain metadata, and terminology.
- Score resume/job alignment using a deterministic and explainable scoring model.
- Resolve missing matches using aliases, known career facts, and targeted user questions.
- Tailor resumes without adding unsupported facts.
- Prefer job terminology when equivalent wording can be grounded in known facts.
- Enforce configurable structure, section order, length, bullet count, and skill-count rules.
- Track every proposed and applied resume mutation.
- Learn from user-confirmed facts and accepted/modified/rejected tailoring suggestions.
- Produce ATS-safe, human-readable output.
- Support CLI, MCP, and future UI/plugin surfaces without duplicating business logic.

### Non-goals

The platform is not intended to:

- Invent experience to increase a score.
- Hide mandatory job gaps.
- Let an LLM determine the authoritative match score.
- Let agents execute arbitrary SQL against the career store.
- Treat inferred information as user-verified information.
- Couple resume rendering to career knowledge persistence.
- Put critical domain behavior inside a UI/plugin implementation.

---

# 3. Proposed Package / Surface Architecture

Initial recommended packages:

```text
resume-core
career-store
career-mcp
resume-cli
resume-agent      # extract once agent workflows grow enough
resume-render     # extract once output/rendering grows enough
resume-plugin     # optional thin host/plugin adapter
```

For MVP, `resume-agent` and `resume-render` may initially live inside the CLI application while preserving the contracts described here. They should become separate packages once they develop independent release/testing concerns.

## Dependency direction

```text
                    resume-cli
                       |
             +---------+----------+
             |         |          |
             v         v          v
        resume-agent resume-core resume-render
             |         |
             |         v
             +----> career-store
                       ^
                       |
                   career-mcp

resume-plugin -> resume-agent / resume-core / career-mcp
```

### Dependency rule

Dependencies flow **toward domain logic**, never toward delivery surfaces.

- `resume-core` must not import CLI, MCP, plugin, or renderer code.
- `career-store` must not import MCP, CLI, or agent code.
- `career-mcp` may import `career-store` and public contracts from `resume-core`.
- `resume-agent` may call public APIs in `resume-core` and `career-store`/MCP abstractions.
- `resume-render` consumes validated canonical resume output; it does not make career-truth decisions.
- `resume-cli` orchestrates workflows through public APIs only.
- `resume-plugin` is an adapter, not a business-logic package.

---

# 4. Shared Canonical Contracts

These contracts should live in `resume-core` or a very small shared contracts module owned by `resume-core`.

## 4.1 Canonical Resume

```ts
interface CanonicalResume {
  id: string;
  schemaVersion: string;
  source: SourceRef;
  contact?: ContactInfo;
  title?: ResumeField<string>;
  summary?: ResumeField<string>;
  experience: ExperienceEntry[];
  skills: SkillEntry[];
  education: EducationEntry[];
  certifications?: CertificationEntry[];
  awards?: AwardEntry[];
  projects?: ProjectEntry[];
  additionalSections?: AdditionalSection[];
  ingestWarnings: ValidationIssue[];
}
```

Every semantically meaningful field should support provenance internally.

```ts
interface ResumeField<T> {
  value: T;
  provenance: ProvenanceRef[];
  verification: VerificationState;
}
```

Output renderers may strip internal metadata.

## 4.2 Job Model

```ts
interface JobModel {
  id: string;
  schemaVersion: string;
  source: SourceRef;
  title?: string;
  company?: string;
  seniority?: string;
  industries: ConceptRef[];
  domains: ConceptRef[];
  requirements: JobRequirement[];
  preferred: JobRequirement[];
  terminology: JobTerm[];
}
```

```ts
interface JobRequirement {
  id: string;
  type: RequirementType;
  concept: string;
  importance: 'required' | 'preferred' | 'contextual';
  weight: number;
  years?: number;
  sourceText: string;
  normalizedTerms: string[];
}
```

## 4.3 Match Result

```ts
interface MatchResult {
  jobId: string;
  resumeId: string;
  score: number;
  threshold: number;
  hardRequirementsResolved: boolean;
  dimensions: MatchDimension[];
  requirements: RequirementResolution[];
  decision: 'continue' | 'resolve_gaps' | 'blocked';
}
```

The overall score never overrides unresolved hard requirements.

## 4.4 Requirement Resolution

```ts
type ResolutionState =
  | 'exact_match'
  | 'alias_match'
  | 'verified_fact_match'
  | 'related_match'
  | 'possible_match'
  | 'unknown'
  | 'explicitly_missing'
  | 'not_applicable';
```

## 4.5 Change Operation

Agents should propose operations; they should not directly mutate canonical resume state.

```ts
interface ResumeChangeOperation {
  id: string;
  operation: 'replace' | 'rewrite' | 'insert' | 'remove' | 'move';
  targetPath: string;
  before?: unknown;
  after?: unknown;
  reason: string;
  requirementIds: string[];
  factIds: string[];
  provenance: ProvenanceRef[];
  status: 'proposed' | 'validated' | 'rejected' | 'applied' | 'accepted' | 'modified';
}
```

## 4.6 Verification State

```ts
type VerificationState =
  | 'source_stated'
  | 'user_verified'
  | 'imported'
  | 'inferred'
  | 'unknown';
```

`inferred` facts may assist questioning and discovery, but may not silently become resume claims.

---

# 5. Package: resume-core

## Vision

`resume-core` is the deterministic domain engine and authoritative keeper of resume-tailoring rules.

It should be usable without an LLM, CLI, MCP server, plugin, or renderer.

If the same input state and configuration are supplied twice, `resume-core` should produce the same deterministic outputs for all deterministic operations.

## Responsibilities

`resume-core` owns:

- Canonical schemas.
- Resume normalization.
- ATS/encoding sanitation.
- Schema validation.
- Date normalization and validation.
- Duplicate detection.
- Job requirement normalization after semantic extraction.
- Match scoring.
- Requirement-resolution state machine.
- Resume selection/ranking rules.
- Template/section constraints.
- Change-operation validation and application.
- Grounding/provenance validation.
- Final ATS and structural validation.
- Explainable score breakdowns.
- Workflow transition rules.

## Explicit non-responsibilities

`resume-core` does not:

- Persist career facts to SQLite.
- Talk MCP.
- Ask users natural-language questions.
- Generate polished prose itself unless the operation is deterministic.
- Render DOCX/PDF.
- Read arbitrary files directly.
- Execute agent prompts.

## Public surface

Illustrative API:

```ts
normalizeResume(input, options): CanonicalResume
validateResume(resume, config): ValidationReport
sanitizeText(text, rules): SanitizedText
normalizeJobModel(agentExtraction): JobModel
scoreMatch(resume, job, factMatches, config): MatchResult
getUnresolvedRequirements(match): JobRequirement[]
rankResumeContent(resume, job, facts, config): ContentSelectionPlan
validateChange(operation, context): ChangeValidationResult
applyChange(resume, validatedOperation): CanonicalResume
validateGrounding(resume, facts): GroundingReport
validateFinalResume(resume, config): FinalValidationReport
```

## Contract with resume-agent

`resume-agent` may:

- Supply parsed semantic interpretations.
- Propose requirement classifications.
- Propose resume change operations.
- Propose semantic equivalences.

`resume-core` must:

- Validate schema.
- Normalize the result.
- Reject unsupported mutation.
- Compute scores itself.
- Decide workflow state transitions.

## Contract with career-store

`resume-core` consumes career facts only through stable domain DTOs. It must not depend on SQLite schemas or SQL query details.

## Contract with resume-render

`resume-core` supplies a final validated `CanonicalResume` or a renderer-safe DTO. Renderer code must not add claims or alter semantic content without returning through validation.

## Failure behavior

- Invalid canonical input: reject with typed validation errors.
- Unsupported claims: reject proposed operation.
- Missing required provenance: reject operation or mark blocked based on config.
- Unresolved hard requirement: score may be high, but `decision` cannot become `continue` unless policy explicitly permits it.

---

# 6. Package: career-store

## Vision

`career-store` is the durable career knowledge model. It provides evidence-backed, versioned, queryable career facts independent of any single resume or job.

SQLite is the source of truth.

## Responsibilities

- SQLite schema and migrations.
- CRUD for career facts.
- Evidence management.
- Fact relationships.
- Verification state.
- Conflict detection.
- Fact merging/deduplication.
- Job-specific fact associations.
- User confirmation history.
- Optional accepted/modified/rejected preference history.
- Transactional persistence.

## Recommended core tables

### facts

```text
id
canonical_name
type
description
years
verification_status
confidence
created_at
updated_at
```

### fact_relationships

```text
id
fact_id
related_fact_id
relationship_type
confidence
created_at
```

Relationship types initially:

```text
alias
related
parent
child
equivalent
```

### evidence

```text
id
fact_id
source_type
source_id
source_path
source_text
created_at
```

### jobs

Stores lightweight job identity/history, not necessarily the entire raw JD.

### job_fact_matches

```text
job_id
requirement_id
fact_id
match_type
confidence
user_confirmed
```

### interactions

Optional but recommended for auditability:

```text
id
interaction_type
subject_id
input_json
result_json
created_at
```

## Public service surface

```ts
searchFacts(query): CareerFact[]
getFact(id): CareerFact
upsertFact(proposal, evidence): UpsertResult
verifyFact(id, verification): CareerFact
addEvidence(factId, evidence): Evidence
addRelationship(a, b, relationship): FactRelationship
findCandidateMatches(requirements): FactCandidateMatch[]
recordJobMatch(...): void
findConflicts(proposal): Conflict[]
```

## Important rules

- Facts are not silently upgraded from `inferred` to `user_verified`.
- A new contradictory value should create a conflict workflow, not overwrite history.
- Evidence is append-oriented.
- Destructive merges should retain aliases/history.
- No delivery surface receives direct DB access.

## Contract with career-mcp

`career-mcp` calls service APIs, not raw SQL.

## Contract with resume-agent

Agent-originated facts are **proposals** until accepted by store rules and, where needed, user verification.

## Contract with resume-core

Expose normalized domain objects. Do not leak database row concerns into scoring logic.

---

# 7. Package: career-mcp

## Vision

`career-mcp` is a deliberately small semantic tool surface over the career knowledge model. Its job is to let agents safely query and propose changes without exposing arbitrary persistence capabilities.

## Responsibilities

- MCP tool definitions.
- Input schema validation.
- Authorization/policy checks if multi-user.
- Translation from MCP requests to `career-store` service calls.
- Structured responses optimized for agent use.
- Audit metadata for mutations.

## Initial MCP tools

### `career.search_facts`

Purpose: search known candidate facts by term/type/domain.

Input:

```json
{
  "query": "distributed systems",
  "types": ["skill", "experience", "domain"],
  "verification": ["user_verified", "source_stated"]
}
```

### `career.get_fact`

Returns full fact, relationships, verification, and evidence summary.

### `career.propose_fact`

Creates or updates a fact proposal through store validation. Agent does not directly decide whether an existing fact is overwritten.

### `career.add_evidence`

Adds evidence to an existing fact.

### `career.verify_fact`

Used only after explicit user confirmation or trusted-source verification.

### `career.add_relationship`

Adds alias/equivalent/related relationships, subject to validation.

### `career.find_matches`

Given normalized job requirements, returns candidate known facts and match classifications.

### `career.get_unverified`

Returns relevant unresolved/inferred facts useful for targeted interviews.

## Deliberately absent tools

Do not expose:

```text
execute_sql
run_query
truncate_table
raw_update
raw_delete
```

## Contract with agent callers

Every write tool returns:

- mutation status,
- resulting fact ID,
- verification state,
- any conflict,
- whether user confirmation is still required.

Agents must not interpret a successful proposal as equivalent to a verified career claim.

---

# 8. Package: resume-agent

## Vision

`resume-agent` handles the parts of resume tailoring that benefit from semantic reasoning or language generation while remaining subordinate to deterministic domain rules.

The agent is a **proposal engine**, not the authoritative state machine.

## Responsibilities

- Semantic resume extraction when deterministic parsing is insufficient.
- Semantic job-description extraction.
- Requirement classification proposals.
- Ambiguity resolution.
- Natural-language interview questions.
- Interpretation of user answers into structured proposals.
- Controlled summary/bullet rewriting.
- Terminology-alignment rewriting.
- Semantic equivalence suggestions missed by deterministic aliases.
- Optional semantic entailment review for difficult claim-validation cases.

## Explicit non-responsibilities

The agent does not:

- Set the official score.
- Decide that a hard requirement is resolved without supporting evidence.
- Directly update SQLite.
- Directly mutate `resume/working.json`.
- Declare inferred facts user verified.
- Choose unrestricted resume length/structure.
- Bypass validation.

## Primary interfaces

### `extractResumeSemantics(rawText)`

Returns a schema-constrained extraction proposal.

### `extractJobSemantics(rawJobText)`

Returns a schema-constrained job extraction proposal.

### `generateClarificationQuestion(context)`

Context is code-selected and should include one or a tightly related cluster of unresolved requirements.

### `interpretUserAnswer(answer, context)`

Returns structured proposals such as:

```json
{
  "requirementResolutions": [],
  "factProposals": [],
  "evidenceProposals": []
}
```

### `proposeRewrite(context)`

Returns one or more `ResumeChangeOperation` proposals, never a mutated resume object.

## Rewrite contract

Every rewrite must receive:

- original text,
- allowed facts,
- target job terminology,
- applicable requirements,
- prohibited additions,
- configured length/voice constraints.

Every rewrite returns:

- candidate text,
- facts used,
- requirements targeted,
- terminology changes,
- confidence/uncertainty if applicable.

## Agent-output validation

All structured output is schema validated before any downstream use.

---

# 9. Package: resume-render

## Vision

`resume-render` converts a validated canonical resume into delivery formats without changing career truth.

## Responsibilities

- Canonical resume -> Markdown/text.
- Canonical resume -> DOCX.
- Canonical resume -> PDF where supported.
- Layout templates.
- Font/spacing/bullet rendering.
- Page-length feedback.
- Renderer-specific ATS checks.
- Optional parse-back verification.

## Non-responsibilities

It does not:

- Decide which experience is relevant.
- Rewrite bullets semantically.
- Add missing skills.
- Change dates.
- Score the job match.
- Query career knowledge.

## Public surface

```ts
renderMarkdown(resume, template): RenderResult
renderDocx(resume, template): RenderResult
renderPdf(resume, template): RenderResult
measureLayout(resume, template): LayoutReport
validateRenderedOutput(file): RenderValidationReport
```

## Important contract

If renderer-driven layout pressure requires content changes, renderer returns constraints such as:

```json
{
  "status": "overflow",
  "estimatedPages": 3,
  "targetPages": 2,
  "requiredReduction": 480
}
```

It does **not** silently shorten content. Orchestration sends the constraint back through selection/rewrite and validation.

---

# 10. Package: resume-cli

## Vision

`resume-cli` is the primary workflow orchestrator and developer-facing reference client. It should make the entire system testable without a graphical UI.

## Responsibilities

- Workspace initialization.
- File discovery/input handling.
- Calling package APIs in correct sequence.
- Persisting canonical workflow artifacts.
- Interactive terminal questions.
- Showing match reports.
- Invoking agent workflows when needed.
- Invoking rendering/export.
- Enforcing workflow checkpoints.

## Proposed workspace

```text
./config.json
./resume/base.json
./resume/working.json
./job/current.json
./data/career.db
./operations/
./reports/
./output/
```

## Initial commands

```text
resume init
resume ingest <file>
resume job ingest <file-or-url-text>
resume match
resume resolve
resume tailor
resume validate
resume export --format docx
resume run <resume> <job>
resume inspect fact <id>
resume inspect requirement <id>
resume audit
```

### `resume run`

Convenience orchestration command. It must still use the same internal checkpoints as individual commands.

## Workflow orchestration

```text
INIT
  -> INGEST_RESUME
  -> VALIDATE_BASE
  -> EXTRACT/PERSIST CAREER FACTS
  -> INGEST_JOB
  -> NORMALIZE_JOB
  -> MATCH_BASE
  -> RESOLVE_GAPS if needed
  -> BUILD_SELECTION_PLAN
  -> PROPOSE_TAILORING CHANGES
  -> VALIDATE CHANGES
  -> APPLY CHANGES
  -> FINAL MATCH
  -> GROUNDING AUDIT
  -> ATS/STRUCTURE VALIDATION
  -> RENDER
  -> RENDER VALIDATION
  -> COMPLETE
```

No stage should be skipped merely because an agent says the result looks correct.

## Artifact rules

- `resume/base.json` is immutable after successful ingest unless user explicitly re-ingests.
- `resume/working.json` is recreated from base for a new tailoring session unless configuration says otherwise.
- Change operations are persisted separately.
- Job model is versioned or replaced explicitly.
- Career DB persists across jobs.

---

# 11. Package: resume-plugin (optional delivery adapter)

## Vision

`resume-plugin` exposes the platform inside an agent host, IDE, or chat product while keeping domain behavior in reusable packages.

## Responsibilities

- Host/plugin manifest.
- Tool registration.
- Skill/instruction text.
- Mapping host conversations into CLI/domain workflows.
- Presenting user confirmation requests.
- Presenting diffs and reports.

## Non-responsibilities

The plugin must not contain its own:

- scoring algorithm,
- SQLite schema,
- ATS sanitizer,
- mutation logic,
- canonical job/resume schemas,
- independent career-learning behavior.

Plugin upgrades should not change resume truth semantics unless underlying domain packages change.

---

# 12. Deterministic vs Agent Responsibility Matrix

| Capability | Code | Agent | Notes |
|---|---:|---:|---|
| JSON/schema validation | Yes | No | Deterministic |
| Unicode/ATS sanitation | Yes | No | Deterministic |
| Date normalization | Yes | No | Deterministic |
| Raw resume semantic extraction | Hybrid | Yes | Code validates |
| Raw JD semantic extraction | Hybrid | Yes | Code validates |
| Requirement weighting | Yes | Optional proposal | Config/rules authoritative |
| Match scoring | Yes | No | Explainable/reproducible |
| Alias lookup | Yes | No | Stored relationships |
| Novel semantic equivalence discovery | Validate | Yes | Agent proposes only |
| Requirement workflow state | Yes | No | State machine |
| Select next interview topic | Yes | No | Based on unresolved impact |
| Phrase natural interview question | No | Yes | Language task |
| User answer interpretation | Validate | Yes | Structured proposal |
| Persist verified facts | Yes | No | Store owns mutation |
| Select resume sections/jobs/bullets | Yes | Optional ranking aid | Config/relevance rules authoritative |
| Rewrite prose | Validate | Yes | Grounded proposal only |
| Apply resume mutation | Yes | No | Operation-based |
| Claim grounding | Yes | Optional semantic fallback | Deterministic first |
| Final ATS validation | Yes | No | Deterministic |
| Output rendering | Yes | No | Semantic-neutral |

---

# 13. Configuration Contract

Example `config.json`:

```json
{
  "schemaVersion": "1.0",
  "matching": {
    "scoreAutoThreshold": 7.5,
    "requireHardRequirementsResolved": true,
    "weights": {
      "requiredSkills": 0.30,
      "experience": 0.25,
      "roleAlignment": 0.15,
      "domainIndustry": 0.10,
      "preferredSkills": 0.10,
      "terminology": 0.10
    }
  },
  "resume": {
    "targetPages": 2,
    "skills": { "min": 8, "max": 18 },
    "experience": { "min": 3, "max": 5 },
    "bulletsPerRole": { "min": 2, "max": 6 },
    "sectionOrder": [
      "summary",
      "skills",
      "experience",
      "projects",
      "education"
    ]
  },
  "guardrails": {
    "allowInferredFactsInFinalResume": false,
    "requireGroundingForGeneratedClaims": true,
    "allowUnverifiedAliasCreation": false
  }
}
```

---

# 14. Complete Product Workflow

## A. Resume ingest

1. CLI/plugin receives resume.
2. Text/document extraction occurs at delivery layer or ingest adapter.
3. Agent assists semantic extraction if needed.
4. `resume-core` normalizes and validates canonical resume.
5. ATS sanitizer reports issues.
6. Valid base stored as `resume/base.json`.
7. Working resume initialized from base.
8. Candidate career facts are proposed.
9. `career-store` deduplicates, persists evidence, and assigns verification state.

## B. Job ingest

1. Raw JD provided.
2. Agent extracts structured requirements.
3. `resume-core` validates/normalizes.
4. `job/current.json` persisted.

## C. Match

1. `resume-core` performs direct resume/job match.
2. `career-store`/MCP searches known verified facts.
3. Alias/equivalent relationships are considered.
4. Deterministic score is calculated.
5. Hard requirement state evaluated.

## D. Gap resolution

If continuation policy is not satisfied:

1. Code ranks unresolved requirements by importance/score impact.
2. Verified facts not currently in resume are checked.
3. Possible/inferred facts are checked.
4. Code chooses next unresolved topic.
5. Agent phrases a targeted question.
6. User response is interpreted into structured proposals.
7. Store validates/persists verified facts/evidence.
8. Match reruns.
9. Continue until threshold and hard-requirement policy are satisfied or all meaningful gaps are exhausted.

## E. Tailoring

1. Code creates content selection plan.
2. Code identifies terminology-alignment opportunities.
3. Agent proposes rewrites only where language change is needed.
4. Every rewrite is emitted as change operation(s).
5. `resume-core` validates grounding and constraints.
6. Valid operations are applied to `working.json`.

## F. Final validation

1. Re-score tailored resume.
2. Confirm no unresolved forbidden claims.
3. Run grounding audit.
4. Run ATS sanitation.
5. Run structure/length rules.
6. Render.
7. Renderer validates output.
8. Persist audit report and result.

---

# 15. Auditing and Observability

Every run should be explainable after the fact.

Recommended run manifest:

```json
{
  "runId": "...",
  "baseResumeId": "...",
  "jobId": "...",
  "configHash": "...",
  "careerDbVersion": "...",
  "initialScore": 6.4,
  "finalScore": 8.2,
  "changesApplied": ["change_1", "change_4"],
  "factsAdded": ["fact_45"],
  "factsVerified": ["fact_21"],
  "validationStatus": "passed"
}
```

Reports should answer:

- Why did the score change?
- Which job requirements are covered?
- Which remain missing?
- Which career facts were used?
- Which claims were rewritten?
- What evidence grounds each generated claim?
- What user confirmations affected the result?
- What deterministic rules rejected agent proposals?

---

# 16. Versioning Strategy

Version independently where useful, but keep compatibility explicit.

At minimum version:

- canonical resume schema,
- job schema,
- career DB schema,
- change-operation schema,
- matching algorithm/config,
- renderer template.

A resume run should record all relevant versions/hashes.

---

# 17. Security and Privacy Expectations

- Career DB is local/user-scoped unless explicitly deployed otherwise.
- Do not send full career DB to an agent when narrower fact retrieval is sufficient.
- MCP search should return minimum necessary evidence.
- Sensitive data should not be included in generated prompts unless needed.
- Logs should avoid raw contact data unless explicitly configured.
- Exports should not contain internal provenance metadata.

---

# 18. Definition of Done for Initial Product

The initial product is complete enough for real use when it can:

1. Initialize a workspace.
2. Ingest a representative resume.
3. Produce valid canonical JSON.
4. Persist career facts/evidence in SQLite.
5. Ingest and normalize a JD.
6. Produce deterministic requirement-level match results.
7. Use stored facts to resolve resume omissions.
8. Ask the user about unresolved high-value requirements.
9. Persist user-verified knowledge.
10. Produce grounded tailoring operations.
11. Reject at least one deliberately hallucinated operation.
12. Produce a final working resume.
13. Re-score and explain improvement.
14. Pass final ATS/grounding checks.
15. Render at least Markdown and DOCX.
16. Produce a complete audit report.

See `SMOKE_TEST.md` and `E2E_TEST.md` for acceptance workflows.
