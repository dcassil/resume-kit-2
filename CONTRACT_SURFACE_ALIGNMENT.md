# Contract Surface Alignment

This is the agent-facing cohesion document for `resume-kit-2`. Before porting code, adapting a package, adding tests, or building a new feature, use this file to verify that every surface stays aligned with the product contract.

Primary authorities:

- `PRODUCT_VISION_AND_CONTRACTS.md`
- `SMOKE_TEST.md`
- `E2E_TEST.md`
- current user instructions in this project thread

Do not use prior `resume-kit` docs, decisions, architecture notes, or historical complexity as product authority.

## Core Product Rule

Resume tailoring improves job relevance and ATS fit without fabricating, exaggerating, silently mutating, or hiding career truth.

The resume is a projection of durable career knowledge, not the source of truth.

The agent may propose meaning and language. Code owns:

- facts,
- state,
- scoring,
- constraints,
- mutations,
- provenance,
- verification,
- truth,
- auditability.

## Package Surfaces

| Package | Owns | Must Not Own |
|---|---|---|
| `resume-core` | Schemas, normalization, validation, scoring, requirement resolution, selection, change validation/application, grounding, final validation. | SQLite persistence, MCP tools, CLI/UI orchestration, plugin behavior, rendering, agent prompting. |
| `career-store` | SQLite career facts, evidence, relationships, verification state, conflicts, migrations, transactions, confirmation/preference history. | Agent questions, scoring, resume rendering, CLI/plugin UI, direct resume mutation. |
| `career-mcp` | Narrow semantic tools over career-store. | Raw SQL, unrestricted mutation, scoring, resume mutation, plugin presentation. |
| `resume-agent` | Semantic extraction proposals, question phrasing, answer interpretation proposals, rewrite proposals, equivalence suggestions. | Official score, persistence, verification authority, direct mutation, workflow decisions. |
| `resume-render` | Markdown/DOCX/PDF rendering, layout measurement, render validation, parse-back checks. | Semantic rewrites, relevance selection, scoring, fact lookup, truth decisions. |
| `resume-cli` | Local workflow orchestration, workspace artifacts, interactive questions, reports, export invocation. | Duplicated domain rules, independent scoring, direct DB writes bypassing store, direct mutation bypassing core. |
| `resume-plugin` | Host/IDE/chat adapter, tool registration, conversation mapping, confirmation/diff/report presentation. | Any domain behavior: scoring, schemas, SQLite, ATS sanitation, mutation, rendering truth, career learning. |
| `workflow` | Cross-package state machine, checkpoints, run manifests, audit, recovery semantics. | Package-private logic or alternate truth rules. |
| `fixtures` | Stable inputs, answers, invalid operations, expected observations/snapshots. | Hidden implementation assumptions. |
| `tests` | Executable gates and suite organization. | Business logic not present in packages. |
| `tools` | Local validation/release helpers. | Hidden product behavior or alternate scoring/mutation logic. |

## Dependency Direction

Allowed dependencies should point inward toward deterministic domain behavior:

```text
resume-plugin
  -> resume-cli / public workflow APIs

resume-cli
  -> resume-core
  -> career-store or career-mcp abstractions
  -> resume-agent
  -> resume-render

resume-agent
  -> public schemas/contracts only

career-mcp
  -> career-store
  -> public resume-core contracts

career-store
  -> public contract DTOs only where needed

resume-render
  -> validated canonical resume/render DTOs

resume-core
  -> no delivery, storage, renderer, MCP, plugin, or agent runtime imports
```

Forbidden dependency examples:

- `resume-core` importing CLI, MCP, plugin, renderer, agent runtime, or SQLite.
- `career-store` importing CLI/plugin host code.
- `resume-render` importing career-store or MCP.
- `resume-plugin` importing private package internals.
- `resume-cli` writing SQLite tables directly.
- `resume-agent` applying changes or persisting facts.

## Shared DTOs and Ownership

### `CanonicalResume`

Owned by `resume-core`.

Read by:

- `resume-cli`,
- `resume-render`,
- `resume-agent` as context only,
- `resume-plugin` through public workflow/report surfaces.

Written by:

- `resume-core` during normalization and validated change application.
- `resume-cli` only as orchestrated artifact persistence.

Never written by:

- `resume-agent`,
- `resume-render`,
- `resume-plugin`,
- `career-mcp`.

Key invariant:

`resume/base.json` is immutable after successful ingest unless the user explicitly re-ingests. `resume/working.json` is a job-session projection and must never pollute base.

### `ResumeField<T>`

Owned by `resume-core`.

Every meaningful generated or source-derived claim must carry provenance and verification metadata sufficient for grounding/audit. Missing provenance blocks generated claims from final output.

### `JobModel`

Owned by `resume-core`.

Agent may propose extracted job semantics. Core validates, normalizes, assigns stable requirement structure, and preserves source text.

Key invariant:

Every requirement must retain source text and normalized terms. Required, preferred, and contextual requirements must remain distinct.

### `JobRequirement`

Owned by `resume-core`.

Used by:

- scoring,
- gap resolution,
- interview topic selection,
- rewrite grounding,
- audit reports.

Key invariant:

The official state of a requirement is code-owned. An agent may not declare a hard requirement resolved.

### `MatchResult`

Owned by `resume-core`.

Read by:

- CLI,
- plugin,
- workflow,
- reports/audit.

Never owned or computed by:

- agent,
- plugin,
- renderer,
- MCP.

Key invariant:

Overall score never overrides unresolved hard requirements. Same state/config must produce identical official score and requirement reasoning.

### `ResolutionState`

Owned by `resume-core`.

Valid states:

- `exact_match`
- `alias_match`
- `verified_fact_match`
- `related_match`
- `possible_match`
- `unknown`
- `explicitly_missing`
- `not_applicable`

Key invariant:

Related is not equivalent. Possible is not resolved. Inferred is not verified. Azure is not proof of AWS.

### `ResumeChangeOperation`

Owned by `resume-core`.

Proposed by:

- `resume-agent`,
- deterministic selection/rewrite planning if applicable.

Validated/applied by:

- `resume-core`.

Persisted/orchestrated by:

- `resume-cli` / `workflow`.

Key invariant:

Agents return operations, not mutated resumes. Every operation needs a valid target path, matching before value, valid after value, reason, requirement IDs, fact IDs, provenance, and status transition.

### `VerificationState`

Owned across `resume-core` contracts and `career-store` persistence.

Valid states:

- `source_stated`
- `user_verified`
- `imported`
- `inferred`
- `unknown`

Key invariant:

`inferred` may assist discovery but may not silently become a resume claim or `user_verified` fact. `user_verified` requires explicit user confirmation.

## Responsibility Matrix

| Capability | Official Owner | Agent Role | Alignment Test |
|---|---|---|---|
| JSON/schema validation | `resume-core` | none | Invalid DTOs rejected before downstream use. |
| Unicode/ATS sanitation | `resume-core` | none | Smart quotes/NBSP/odd bullets normalized or reported deterministically. |
| Date normalization | `resume-core` | none | Meaning preserved; impossible dates rejected. |
| Resume extraction | hybrid | proposal | Agent proposal is schema validated; unsupported content excluded. |
| Job extraction | hybrid | proposal | Source text retained; core normalizes requirements. |
| Requirement weighting | `resume-core` | optional proposal | Config/rules authoritative. |
| Match scoring | `resume-core` | none | Same inputs produce same score. |
| Alias lookup | `resume-core` + `career-store` | optional discovery | Stored/validated relationship required. |
| Novel semantic equivalence | `resume-core` validates | proposal | No unverified alias becomes truth. |
| Requirement workflow state | `workflow` + `resume-core` | none | Hard gates enforced. |
| Next interview topic | `resume-core` / `workflow` | none | Code selects topic by unresolved impact. |
| Question wording | agent | phrase only | Wording may vary; topic may not. |
| User answer interpretation | `career-store` validates | proposal | Store/core validate before persistence. |
| Persist verified facts | `career-store` | none | Explicit confirmation required. |
| Section/content selection | `resume-core` | optional ranking aid | Config min/max/order enforced. |
| Rewrite prose | `resume-core` validates | proposal | Grounding required before application. |
| Apply resume mutation | `resume-core` | none | Operation status transition enforced. |
| Claim grounding | `resume-core` | optional fallback | Provenance required. |
| Final validation | `resume-core` | none | No unsupported/inferred claims in final. |
| Rendering | `resume-render` | none | Renderer cannot change semantic content. |
| Presentation | `resume-cli` / `resume-plugin` | none | Reports reflect domain results. |

## Workflow Alignment

Canonical workflow:

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

Alignment rules:

- No stage is skipped because an agent says the output looks correct.
- Every transition is based on persisted state, validated DTOs, or deterministic package output.
- Gap resolution always returns to matching after new verified facts.
- Rendering overflow returns constraints to orchestration; renderer does not truncate.
- Final output requires match, grounding, ATS, structure, render validation, and audit artifacts.

## Artifact Ownership

| Artifact | Owner | Alignment Rule |
|---|---|---|
| `config.json` | CLI/workflow | Must validate and contribute to config hash. |
| `resume/base.json` | core output, CLI persistence | Immutable after ingest unless explicit re-ingest. |
| `resume/working.json` | core output, CLI persistence | Derived from base and applied validated operations. |
| `job/current.json` | core output, CLI persistence | Versioned or explicitly replaced. |
| `data/career.db` | career-store | Persists across jobs; transactionally valid. |
| `operations/` | workflow/CLI | Stores proposed, validated, rejected, applied operations. |
| `reports/` | workflow/CLI | Explains scores, requirements, facts, validations. |
| `output/` | renderer/CLI | Contains rendered artifacts without internal provenance metadata. |
| run manifest | workflow | Records versions, hashes, scores, facts, changes, validations, outputs. |

## Required Gates

### Contract Gate

An agent changing or porting a package must verify:

- public API matches the package `TEST_SPEC.md`,
- DTOs align with this document,
- forbidden responsibilities are absent,
- dependency direction is respected,
- smoke/E2E fixture expectations are not weakened.

### Determinism Gate

Must prove:

- same state/config yields same official score,
- same state/config yields same unresolved-topic selection,
- same state/config yields same selection plan,
- retries do not duplicate applied operations or fact writes.

### Honesty Gate

Must reject:

- unsupported scale such as `20 million users`,
- unsupported management scope such as `30 engineers`,
- title inflation to Staff Software Engineer,
- AWS years inflation from six to ten,
- Azure as proof of AWS,
- any generated claim without grounding.

### Persistence Gate

Must prove:

- base resume remains unchanged,
- user-verified facts survive across jobs,
- Job B uses AWS/GraphQL learned in Job A,
- already verified facts are not re-asked without legitimate new specificity,
- preference learning cannot alter fact verification.

### Render Gate

Must prove:

- Markdown and DOCX render succeed for release target,
- rendered semantics match canonical working resume,
- renderer reports overflow instead of deleting content,
- output excludes internal provenance metadata.

### Audit Gate

Must reconstruct:

- source resume identity,
- base resume identity/hash,
- job identity,
- config hash,
- schema/package/model/template versions,
- initial and final scores,
- unresolved requirements,
- user questions and answers,
- facts added/verified,
- proposed/rejected/applied operations,
- validation outcomes,
- output artifacts.

## Cross-Package Alignment Checklist

Use this checklist before porting or merging a piece:

- Does the piece belong in the package where it is being placed?
- Does it depend only on allowed packages?
- Does it expose only the package's public responsibility?
- Does it preserve source truth and provenance?
- Does it keep agent output proposal-only?
- Does it avoid silently upgrading verification state?
- Does it produce deterministic official outputs where required?
- Does it preserve `base.json` immutability?
- Does it keep renderer semantic-neutral?
- Does it record enough audit data?
- Does it satisfy the relevant folder `TEST_SPEC.md`?
- Does it strengthen rather than weaken smoke/E2E assertions?

## Misalignment Examples

Reject or refactor immediately if any of these appear:

- Agent returns a fully mutated canonical resume and downstream code trusts it.
- Plugin contains its own scoring formula.
- CLI directly updates SQLite fact tables.
- Renderer shortens a bullet to fit two pages without returning a constraint.
- MCP exposes a raw query tool.
- Core imports a renderer or plugin helper.
- Store marks an agent-inferred fact as `user_verified`.
- A related cloud fact resolves an AWS requirement as exact.
- A title field changes to match a job title without employment-title evidence.
- A final resume includes a generated claim without provenance.

## Traceability Map

| Area | Detailed spec |
|---|---|
| Overall structure and gates | `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md` |
| Deterministic domain engine | `resume-core/TEST_SPEC.md` |
| Career persistence | `career-store/TEST_SPEC.md` |
| MCP surface | `career-mcp/TEST_SPEC.md` |
| Agent proposal behavior | `resume-agent/TEST_SPEC.md` |
| Rendering | `resume-render/TEST_SPEC.md` |
| CLI workflow | `resume-cli/TEST_SPEC.md` |
| Plugin adapter | `resume-plugin/TEST_SPEC.md` |
| Cross-package workflow | `workflow/TEST_SPEC.md` |
| Stable fixtures | `fixtures/TEST_SPEC.md` |
| Test suite gates | `tests/TEST_SPEC.md` |
| Local validation tools | `tools/TEST_SPEC.md` |

## Agent Use Pattern

Before implementation:

1. Read this file.
2. Read the target folder's `TEST_SPEC.md`.
3. Read only the relevant authority sections in `PRODUCT_VISION_AND_CONTRACTS.md`, `SMOKE_TEST.md`, and `E2E_TEST.md`.
4. Write or update tests first.
5. Port or implement the smallest piece that satisfies the contract.
6. Run the narrow gate, then the relevant broader gate.
7. Record any intentional contract change explicitly before changing behavior.

