# career-store Test Spec

## Contract

`career-store` is the local SQLite source of truth for career knowledge. It owns facts, evidence, relationships, verification state, conflicts, job associations, confirmation history, optional preference history, migrations, and transactions.

It must not expose direct database access to delivery surfaces, and it must never silently promote inferred information to `user_verified`.

Relevant public surface:

- `searchFacts`
- `getFact`
- `upsertFact`
- `verifyFact`
- `addEvidence`
- `addRelationship`
- `findCandidateMatches`
- `recordJobMatch`
- `findConflicts`

## Expected Structure

Tests should expect durable storage around these data areas:

- facts
- fact relationships
- evidence
- jobs
- job fact matches
- interactions
- migrations
- transaction helpers
- conflict records

## Unit Test Cases

### Migrations and schema

- Create a fresh isolated SQLite database.
- Apply migrations from empty state.
- Assert schema version is recorded.
- Re-run migrations and assert idempotency.
- Reject incompatible schema versions with a typed error.
- Record career DB schema version for run manifests.

### Fact persistence

- Persist source-stated facts extracted from a resume.
- Store React, TypeScript, SaaS, REST/API, Node, PostgreSQL, and Azure facts from fixtures.
- Do not persist AWS or GraphQL as verified from a source resume where they are absent.
- Allow inferred/candidate facts only in non-final verification states.
- Return stable fact IDs.
- Preserve created/updated metadata deterministically where test clocks are fixed.

### Evidence

- Attach evidence to every source-stated fact.
- Preserve source location or source span where available.
- Append new evidence without overwriting previous evidence.
- Prevent destructive evidence deletion except through explicit audited behavior if later supported.
- Ensure exports do not leak internal provenance unless an audit surface requests it.

### Verification state

- Store `source_stated` facts from resume evidence.
- Store `user_verified` only after explicit simulated user confirmation.
- Store `inferred` facts as discovery-only.
- Store `unknown` when evidence is insufficient.
- Reject silent `inferred -> user_verified` escalation.
- Preserve user verification across separate job sessions.

### Relationships

- Add alias or related relationships such as `responsive web apps` to `responsive design`.
- Require validation/confirmation policy before using new relationships as equivalent.
- Keep `related` distinct from `alias/equivalent`.
- Prevent Azure from becoming proof of AWS through a related relationship.
- Retain relationship evidence or rationale.

### Search and matching

- Search by concept, normalized terms, and aliases.
- Return minimum necessary evidence.
- Return deterministic ordering for identical inputs.
- Find candidate matches for job requirements.
- Distinguish exact, alias, related, possible, unknown, and explicitly missing states in returned DTOs.

### Conflict detection

- Detect contradictory years claims, such as AWS six years versus AWS ten years.
- Detect conflicting title claims, such as actual title versus fabricated Staff title.
- Detect mutually incompatible source statements.
- Return conflict details without silently overwriting existing fact truth.

### Job associations

- Record requirement-to-fact matches for a job.
- Preserve which facts were used for Job A versus Job B.
- Reuse user-verified AWS and GraphQL facts learned during Job A when matching Job B.
- Do not pollute base resume or job-specific working resume state.

### Interaction and preference history

- Record user confirmations for AWS, GraphQL, and architecture.
- Record accepted/modified/rejected rewrite decisions separately from career facts if preference learning exists.
- Assert preference learning cannot change verification state.
- Assert rejecting phrasing does not remove the underlying career fact.

### Transactions and recovery

- Roll back partial fact/evidence writes on failure.
- Resume after interruption following user verification.
- Detect duplicate writes from retried operations.
- Preserve DB validity after simulated process interruption.

## Boundary Tests

- Fail if store imports CLI/plugin host code.
- Fail if store asks natural-language questions.
- Fail if store renders resumes or changes resume files.
- Fail if any public API exposes raw SQL execution.

## Smoke Coverage

The smoke fixture must prove:

- SQLite database is creatable,
- migrations succeed,
- resume-derived facts persist with evidence,
- verification states are not over-promoted,
- AWS becomes `user_verified` only after simulated answer,
- MCP and store search produce compatible normalized results.

## E2E Coverage

The E2E fixture must prove:

- facts survive from Job A to Job B,
- already verified AWS/GraphQL facts prevent duplicate questions,
- evidence chains identify source resume or prior user verification,
- conflicts are represented instead of hidden,
- DB state is reconstructable from audit artifacts.

