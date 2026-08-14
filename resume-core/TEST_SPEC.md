# resume-core Test Spec

## Contract

`resume-core` is the deterministic domain engine. It owns canonical schemas, resume/job normalization, ATS sanitation, date handling, duplicate detection, requirement normalization, scoring, resolution states, selection, change validation/application, grounding validation, final validation, and workflow decision outputs.

It must import no CLI, MCP, plugin, renderer, or SQLite implementation details.

Relevant contract surfaces:

- `CanonicalResume`
- `ResumeField<T>`
- `JobModel`
- `JobRequirement`
- `MatchResult`
- `ResolutionState`
- `ResumeChangeOperation`
- `VerificationState`
- `normalizeResume`
- `validateResume`
- `sanitizeText`
- `normalizeJobModel`
- `scoreMatch`
- `getUnresolvedRequirements`
- `rankResumeContent`
- `validateChange`
- `applyChange`
- `validateGrounding`
- `validateFinalResume`

## Restored RKIT-I-0001 Behaviors

- `VerificationState` is exactly `{source_stated, user_verified, imported, inferred, unknown}`. `validateResume` accepts `imported`; rejects `explicitly_missing` as `invalid_verification_state`; and `conflicted` is absent from this enum.
- `ResolutionState` is exactly `{exact_match, alias_match, verified_fact_match, related_match, possible_match, unknown, explicitly_missing, not_applicable}`. `explicitly_missing` and `not_applicable` are valid resolution states; `conflicted` is absent from this enum.
- `ResumeChangeOperation` structurally accepts only verbs `{replace, rewrite, insert, remove, move}` and statuses `{proposed, validated, rejected, applied, accepted, modified}`. Missing mandatory fields `reason`, `linked_requirement_ids`, `linked_fact_ids`, or `provenance` must reject with `missing_field`; an unknown verb must reject with `invalid_op`; an unknown status must reject with `invalid_status`.
- `validateResume` derives required-field enforcement from `CANONICAL_RESUME_SCHEMA.required`, which is exactly `{schema_version, resume_id, source, experience, skills, education}`. Omitting any required field, including `resume_id` or `source`, must reject with `missing_field`.
- Resume date handling is deterministic:
  - `YYYY` remains `YYYY` with no warning when the year is valid.
  - `YYYY-M` and `YYYY-MM` canonicalize to `YYYY-MM` with no warning when the month is valid.
  - `Mon YYYY` canonicalizes to `YYYY-MM` with an `ambiguous_start_date` or `ambiguous_end_date` warning.
  - `MM/YYYY` canonicalizes to `YYYY-MM` with an `ambiguous_start_date` or `ambiguous_end_date` warning.
  - `present` and `current` are valid end-date sentinels and do not invent an end date.
  - Impossible months such as `2019-13` or `13/2019` reject with `invalid_date`.
  - Any normalized start date after the normalized end date rejects with `reversed_range`.
  - Unparseable but not impossible date text remains an ambiguity warning, not a typed rejection.
- `JobModel` section-4.2 normalization deterministically populates `seniority`, `industries`, `domains`, separate `requirements` and `preferred` arrays, and `terminology: JobTerm[]`. Each `JobTerm` has non-empty `surface`, normalized `canonical`, source in `{title, requirement, description}`, and numeric `weight`; repeated normalization of identical input must produce identical output.
- `normalizeResume` wraps meaningful claims as per-claim `ResumeField` values. A source-backed claim preserves matching provenance and its valid verification state; a sourceless or malformed-provenance claim defaults to `provenance: []` and `verification_state: unknown`, never a silent `source_stated`.

## Expected Structure

Future implementation may decompose internally, but tests should assume public APIs are the stable boundary:

- shared DTO and JSON schema definitions in `resume_core.schemas`
- schemas and type validation
- resume normalization
- job normalization
- scoring and requirement resolution
- selection planning
- change operation validation/application
- grounding and final validation
- deterministic fixtures and snapshots

## Unit Test Cases

### Schema validation

- Accept a valid `CanonicalResume` with contact, summary, experience, skills, education, provenance, and verification state.
- Reject missing required array fields such as `experience[]` or `skills[]`.
- Accept `imported` as a verification state; reject `explicitly_missing`, `conflicted`, and other unknown verification states.
- Reject malformed provenance entries.
- Accept optional certifications, awards, projects, and additional sections without changing their meaning.
- Validate `JobModel` requirements with type, concept, importance, weight, source text, and normalized terms.
- Validate `ResumeChangeOperation` paths, the five canonical verbs, the six canonical statuses, before/after values, linked requirements, linked facts, mandatory reason, and provenance.

### ATS and text normalization

- Normalize smart quotes without changing semantic meaning.
- Normalize non-breaking spaces.
- Convert or report odd bullet characters.
- Preserve text meaning through Unicode sanitation.
- Flag unsupported control characters.
- Ensure sanitation is deterministic for repeated input.

### Date normalization

- Normalize inconsistent date formats into a stable representation.
- Preserve present/current roles without inventing end dates.
- Reject impossible dates with `invalid_date` and reversed ranges with `reversed_range`.
- Report ambiguous dates rather than silently changing meaning.

### Resume normalization

- Preserve all source experience entries.
- Preserve role titles and employers exactly where they are factual fields.
- Keep React, TypeScript, Node, PostgreSQL, Azure, SaaS, REST/API claims from source fixtures.
- Do not add AWS, GraphQL, Staff title, unsupported metrics, unsupported management scope, or unsupported outcomes.
- Attach provenance to meaningful claims and default sourceless claims to empty provenance plus `unknown`, never `source_stated`.
- Emit ingest warnings for normalization issues.

### Job normalization

- Classify required, preferred, and contextual requirements.
- Preserve years requirements such as `8+ years`.
- Normalize concepts such as API architecture/design without dropping source text.
- Retain exact terminology such as `responsive design`.
- Assign stable requirement IDs from deterministic input/config rules.
- Populate `JobTerm` entries deterministically with surface, canonical, source, and weight while keeping preferred requirements separate from required requirements.

### Requirement resolution

- Resolve exact source-backed matches.
- Resolve alias matches only when an alias relationship is supplied.
- Resolve verified fact matches only from supplied fact DTOs.
- Keep related matches distinct from exact or verified matches.
- Keep possible matches distinct from resolved hard requirements.
- Mark explicitly missing facts when evidence or user answer supports absence.
- Block continuation when required hard requirements remain unresolved and policy requires resolution.

### Scoring

- Run the same resume/job/fact/config input twice and assert identical `MatchResult`.
- Assert score dimensions add/explain consistently.
- Assert unresolved hard requirements dominate overall continuation decision even if numeric score is high.
- Assert preferred missing items may reduce score but do not masquerade as required failures.
- Snapshot expected base score for smoke and E2E fixtures.

### Selection planning

- Rank job-relevant experience above less relevant content.
- Respect configured section order.
- Respect skills min/max.
- Respect experience min/max.
- Respect bullets-per-role min/max.
- Never allow agent output to override structural maxima directly.
- Keep the base resume unchanged.

### Change validation

- Accept a grounded terminology rewrite from `responsive web apps` toward `responsive design`.
- Accept adding AWS/GraphQL only when verified fact DTOs support the claim.
- Reject `Served 20 million users` with no evidence.
- Reject `Managed 30 engineers` with no evidence.
- Reject employment title inflation to `Staff Software Engineer` without user-confirmed title evidence.
- Reject years inflation from six years AWS to ten years AWS.
- Reject treating Azure as proof of AWS.
- Reject operations whose `before` value does not match the current target path.
- Reject operations with missing fact IDs or missing requirement IDs when the reason depends on them.

### Change application

- Apply only validated operations.
- Enforce status transitions `proposed -> validated -> applied`.
- Ensure rejected operations never alter `working`.
- Ensure operation application is idempotent or safely detects an already-applied operation.
- Record enough result data for audit reconstruction.

### Final validation

- Confirm every generated claim has provenance.
- Confirm no inferred fact appears as a final resume claim when config forbids inferred facts.
- Confirm required requirement statuses are truthful.
- Confirm duplicate/repetition checks run.
- Confirm keyword-stuffing checks run if implemented.
- Confirm final score is deterministic.

## Boundary Tests

- Fail if `resume-core` imports `resume-cli`, `career-mcp`, `resume-plugin`, `resume-render`, or SQLite adapters.
- Fail if core reads arbitrary files as part of domain APIs.
- Fail if core calls an LLM, agent runtime, MCP server, renderer, or terminal UI.

## Smoke Coverage

The smoke fixture must prove:

- canonical resume validates,
- ATS noise is normalized/reported,
- React/API/responsive requirements resolve deterministically,
- AWS remains missing until confirmed,
- hallucinated rewrite is rejected,
- final validation prevents unsupported claims.

## E2E Coverage

The E2E fixture must prove:

- deterministic initial and final scores,
- requirement-level reasoning,
- hard requirement gating,
- selection plan constraints,
- valid tailoring operations,
- adversarial honesty rejection,
- immutable base resume,
- second-job use of persisted verified facts through supplied fact DTOs.
