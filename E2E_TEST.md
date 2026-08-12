# Resume Tailoring Platform — Complete End-to-End Test Specification

## Purpose

This E2E test validates the product as a user would experience it: from an existing base resume and empty career database through job analysis, targeted interview, career learning, resume tailoring, validation, rendering, and repeat use on a second job.

Unlike the smoke test, the E2E test verifies cross-run learning, state durability, boundary enforcement, scoring behavior, agent/code orchestration, and auditability.

---

# E2E Success Definition

A complete E2E run must prove that:

1. A source resume becomes a faithful canonical resume.
2. Career facts are extracted with evidence but are not over-verified.
3. A job is normalized into explicit requirements.
4. Matching is deterministic and requirement-level.
5. Known facts missing from the resume can resolve job gaps.
6. Unknown facts trigger targeted user questions.
7. User confirmations persist across future jobs.
8. Agent rewrites remain grounded.
9. Unsupported claims are rejected.
10. Final resume structure is controlled by deterministic configuration.
11. Base resume remains unchanged.
12. A second tailoring run benefits from the career DB without asking duplicate questions.
13. Every important decision is auditable.

---

# Test Environment

Use a clean temporary directory and isolated SQLite DB.

Record:

- package versions,
- schema versions,
- model identifier/config used for agent steps,
- config hash,
- renderer template version.

Agent temperature or equivalent variability should be minimized for test repeatability where supported.

---

# Fixtures

## Candidate resume fixture

Construct a realistic two-page technical resume containing:

### Summary

- Senior Software Developer
- 12 years full-stack development
- SaaS experience

### Experience A

- React
- TypeScript
- Built responsive web apps
- REST APIs
- Multi-tenant SaaS
- Led small team

### Experience B

- Node.js
- PostgreSQL
- Azure
- Workflow automation

### Skills

- React
- TypeScript
- Node.js
- PostgreSQL
- Azure

### Intentionally absent from resume

- AWS
- GraphQL
- Exact phrase `responsive design`
- Exact title `Staff Software Engineer`

### Formatting noise

Include:

- smart quotes,
- non-breaking spaces,
- atypical bullet glyph,
- one inconsistent date representation.

## User-known facts not present on resume

During interview simulation, user will verify:

- AWS: 6 years
- GraphQL: 5 years
- Has designed APIs for more than 10 years
- Has performed architecture-level work but has not held formal Staff title

## Job A fixture

Title: Staff Software Engineer

Required:

- 8+ years software engineering
- React
- TypeScript
- API architecture/design
- Responsive design
- SaaS

Preferred:

- AWS
- GraphQL
- technical leadership

## Job B fixture

Title: Senior Full Stack Engineer

Required:

- React
- Node.js
- GraphQL
- AWS

Preferred:

- PostgreSQL
- SaaS

Job B is specifically designed to prove that facts learned during Job A persist and prevent redundant questioning.

---

# Phase 1 — Initialization

Run workspace initialization.

Assertions:

- Expected directory structure exists.
- Config validates.
- Career DB schema version is current.
- Career DB contains no candidate facts.
- No job or resume state exists before ingest.

---

# Phase 2 — Resume Ingest and Canonicalization

Ingest candidate resume.

Assertions:

### Fidelity

- Every experience entry in source exists in canonical output.
- Dates preserve meaning after normalization.
- React/TypeScript/etc. remain present.
- AWS and GraphQL are not invented.
- Staff title is not invented.

### ATS normalization

- Smart quotes are normalized or accepted per policy.
- Non-breaking spaces are normalized.
- Odd bullet glyph is converted/reported.
- Inconsistent date is normalized without changing actual date meaning.

### Provenance

Sample at least five canonical claims and verify each points to source evidence.

### Immutability

Record content hash of `resume/base.json`.

---

# Phase 3 — Career Knowledge Ingest

Allow career fact extraction/persistence.

Assertions:

- React exists as source-stated fact.
- TypeScript exists as source-stated fact.
- SaaS exists as source-stated experience/domain fact.
- API work exists with resume evidence.
- AWS does not exist unless inferred as unverified; it must not be verified.
- GraphQL does not exist unless inferred as unverified; it must not be verified.

Search via MCP and direct store service in test harness; compare normalized results.

MCP must not expose raw SQL.

---

# Phase 4 — Job A Ingest

Ingest Job A.

Assertions:

- Title recognized as Staff Software Engineer.
- Required vs preferred classifications correct.
- Years requirement retained.
- `API architecture/design` normalized as a requirement concept.
- `responsive design` retained as terminology.
- Source text stored for all requirements.

---

# Phase 5 — Initial Job A Match

Run match twice.

Assertions:

- Both scores identical.
- React resolves.
- TypeScript resolves.
- SaaS resolves.
- 8+ years resolves from source-supported 12 years.
- Responsive design is exact/alias/related/possible depending relationship model, but must not be marked unsupported if equivalent evidence can legitimately establish it.
- AWS is unresolved/missing.
- GraphQL is unresolved/missing.
- Staff title itself must not be treated as mandatory experience unless JD states it as such.
- Architecture requirement may be partial/possible based on source evidence but should not invent formal title.

Record base score.

---

# Phase 6 — Known-Fact and Alias Resolution

Test terminology handling before asking user questions.

For `responsive web apps` vs `responsive design`:

- Existing relationship lookup runs first.
- If recognized as sufficiently related, requirement receives a supported resolution or candidate state.
- If semantic agent proposes relationship, code validates relationship before use.

Assertions:

- No new experience claim is added merely to satisfy terminology.
- Resolution reasoning identifies source evidence.

---

# Phase 7 — Targeted Interview for Job A

Code should rank remaining unresolved requirements by configured importance and score impact.

Expected high-value questions include AWS, GraphQL, and possibly architecture detail.

For each question:

1. Assert code selected the requirement/topic.
2. Assert agent only phrases the question.
3. Provide simulated user answer.
4. Assert agent emits structured interpretation.
5. Assert career-store validates/persists fact/evidence.
6. Assert verification becomes `user_verified` only because explicit user confirmation occurred.
7. Re-run match.

## AWS answer

```text
Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM.
```

Assertions:

- AWS fact persisted.
- 6 years persisted with user evidence.
- Technologies may be child/related facts based on configured extraction rules.
- AWS preferred requirement resolves.

## GraphQL answer

```text
Yes, around five years. I've built and maintained GraphQL APIs in production.
```

Assertions:

- GraphQL fact persisted and verified.
- Production usage may be recorded only if evidence supports exact answer.

## Architecture answer

```text
I've designed APIs and application architecture for more than ten years, but I haven't had Staff Engineer as my formal title.
```

Assertions:

- Architecture/API-design fact is verified.
- Years may be stored as `10+` representation according to schema.
- Formal Staff title is explicitly not added as employment history.
- System can still match architecture experience without fabricating title.

Continue until threshold/hard-requirement conditions are satisfied or no meaningful questions remain.

---

# Phase 8 — Content Selection Plan

Generate deterministic selection plan for Job A.

Assertions:

- Most job-relevant experience ranks highest.
- Relevant skills are included within configured min/max.
- Less relevant content can be dropped but source resume remains unchanged.
- Section order follows config.
- Maximum role/bullet counts respected.
- Agent is not allowed to override structural maxima directly.

Snapshot selection plan.

---

# Phase 9 — Tailoring Operations

Request tailored prose proposals.

Expected candidate changes:

- Senior Software Developer terminology may be adjusted in summary language toward software engineering terminology if grounded, without changing actual employment title fields.
- `responsive web apps` may be rewritten to include `responsive design` terminology.
- API bullet may emphasize `API design` if the verified fact supports it.
- AWS/GraphQL may be added to skills or summary/appropriate bullets only where supported by verified facts and selection rules.

For every operation assert:

- target path exists,
- before value matches current state,
- after value is schema valid,
- reason exists,
- requirement IDs exist,
- fact IDs exist,
- grounding validation passes before application.

---

# Phase 10 — Adversarial Honesty Checks

Inject several invalid proposals.

## A. Unsupported scale

`Served 20 million users` with no evidence.

Expected: rejected.

## B. Unsupported management

`Managed 30 engineers` with no evidence.

Expected: rejected.

## C. Title inflation

Change actual employment title to `Staff Software Engineer` solely because Job A uses that title.

Expected: rejected unless user explicitly confirms that was an actual title.

## D. Years inflation

Change AWS from six years to ten years.

Expected: rejected.

## E. Related-skill overreach

Treat Azure experience as proof of AWS without user confirmation.

Expected: not an exact/verified AWS match. Related cloud experience may be noted, but AWS claim cannot be generated.

All rejected operations must appear in audit history.

---

# Phase 11 — Apply Valid Operations

Apply all validated operations.

Assertions:

- Operation status transitions are correct.
- Working resume changes.
- Base resume hash is unchanged from Phase 2.
- No rejected operation appears in working resume.

---

# Phase 12 — Final Job A Validation

Run:

- final match,
- grounding audit,
- ATS validation,
- structure validation,
- duplicate/repetition checks,
- keyword-stuffing checks if implemented.

Assertions:

- Final score >= base score unless a documented rule intentionally lowers it for honesty/quality.
- Every generated claim is grounded.
- Required requirements are correctly represented as resolved/unresolved.
- Preferred unresolved items remain visible rather than fabricated.
- Structural constraints pass.
- No invalid characters remain.

Record final score and score delta.

---

# Phase 13 — Rendering Job A Resume

Render Markdown and DOCX.

Assertions:

- Output files exist.
- Expected sections/order present.
- Text semantics match canonical working resume.
- Employment titles/dates remain truthful.
- Renderer did not invent/remove semantic claims.
- Renderer reports page estimate/layout status.

If output exceeds target pages:

- Renderer returns overflow constraint.
- Orchestrator returns to content reduction/rewriting.
- Renderer does not silently truncate.

After any reduction cycle, rerun grounding and final validation.

---

# Phase 14 — Audit Job A Run

Audit report must allow reconstruction of:

- raw/source resume identity,
- base canonical resume identity/hash,
- job identity,
- initial score,
- unresolved requirements,
- user questions,
- facts added/verified,
- all proposed operations,
- all rejected operations and reasons,
- all applied operations,
- final score,
- validation outcomes,
- output artifacts,
- config/schema/model versions.

---

# Phase 15 — Second Job / Persistent Learning Test

Start a new tailoring session for Job B.

Critical setup:

- Reuse the same `career.db`.
- Start `resume/working.json` again from immutable base.
- Replace/version `job/current.json` with Job B.

Run Job B match.

Assertions:

- React resolves from base resume.
- Node.js resolves from base resume.
- PostgreSQL resolves from base resume.
- SaaS resolves from base resume.
- AWS resolves from persistent user-verified career fact learned during Job A.
- GraphQL resolves from persistent user-verified career fact learned during Job A.
- System does **not** ask the user again whether they know AWS or GraphQL unless conflicting/new specificity legitimately requires clarification.
- Evidence chain identifies prior user verification.

This phase is mandatory. It proves the product has a career knowledge model rather than a job-specific scratchpad.

---

# Phase 16 — Preference Learning Test (Optional for MVP, Required Later)

If accepted/modified/rejected rewrite learning is implemented:

1. Present a stylistically valid rewrite.
2. Simulate user modifying it.
3. Persist preference feedback separately from career facts.
4. Run a later rewrite opportunity.

Assertions:

- Preference learning affects phrasing/ranking only.
- It cannot upgrade facts or verification state.
- Rejecting a wording choice does not remove the underlying career fact.

---

# Phase 17 — Failure Recovery

Simulate interruption after:

- job ingest,
- user verification,
- proposed operations,
- partially applied operation sequence.

Assertions:

- Run can resume from persisted deterministic state.
- DB remains transactionally valid.
- Operation application is idempotent or safely detects already-applied changes.
- Base resume is still unchanged.

---

# Required E2E Assertions Summary

## Truth and grounding

- No fabricated skill, title, metric, years, responsibility, scale, or outcome enters final output.
- Inferred != verified.
- Related != equivalent unless explicitly modeled.
- Every generated claim has provenance.

## Determinism

- Same state/config yields same code-driven match score.
- Workflow decisions about unresolved requirements are reproducible.

## Persistence

- Career facts survive job sessions.
- Job-specific working resume changes do not pollute base resume.
- Second job benefits from prior verified learning.

## Boundaries

- Agent proposes; code validates/applies.
- MCP does not expose raw SQL.
- Renderer does not alter semantic truth.
- CLI/plugin orchestrates but does not duplicate domain rules.

## User experience

- User is asked only about meaningful unresolved gaps.
- Already verified facts are not repeatedly requested.
- Final report clearly distinguishes matched, missing, and unresolved requirements.

---

# E2E Pass/Fail Criteria

The E2E test passes only if every mandatory assertion succeeds.

Release-blocking failures include:

- base resume mutation,
- verified-state escalation without user/source support,
- nondeterministic official scoring from identical state,
- unsupported claim accepted into final resume,
- raw SQL exposed through MCP,
- learned verified facts lost between Job A and Job B,
- duplicate questioning for already verified equivalent facts without a legitimate reason,
- renderer silently changing semantic content,
- unresolved hard requirement falsely reported as resolved.

---

# Recommended Automation

Run subsets at different layers:

```text
PR:
- unit tests
- contract tests
- package-boundary tests
- deterministic scoring fixtures
- hallucination-rejection fixtures

Main branch:
- full smoke test

Release candidate:
- complete E2E test
- renderer parse-back checks
- migration upgrade test from previous DB schema
```

The E2E fixture should be stable and versioned so score and workflow changes are deliberate, reviewed changes rather than accidental drift.
