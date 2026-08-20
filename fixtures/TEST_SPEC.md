# fixtures Test Spec

## Contract

`fixtures` owns stable, versioned test inputs and expected observations. Fixtures must support contract tests, smoke tests, and E2E tests without depending on inherited implementation behavior.

Fixtures should be small enough to debug but rich enough to prove truth, determinism, persistence, and adapter boundaries.

## Expected Structure

Future fixture files should be grouped by intent:

```text
fixtures/
  resumes/
  jobs/
  answers/
  operations/
  expected/
  migrations/
```

This file defines the required fixture content before implementation.

## Required Migration Fixtures

`fixtures/migrations/` contains the stable career-store migration fixture set.
These fixtures are authored for migration checkers only; migration runner/checker
logic lives under `tools/` and is outside this fixture contract.

### Previous-schema career DB

`fixtures/migrations/seed_previous_schema.py` must generate
`fixtures/migrations/previous-schema-career.db` with no network access and no
wall-clock values. Running the generator twice must produce identical DB bytes.

The fixture DB represents `career-store.v0`, which is strictly older than the
current career-store schema version `career-store.v1`. The previous schema keeps
the original durable surfaces:

- `migrations`
- `facts`
- `evidence`

It intentionally lacks current `career-store.v1` tables:

- `relationships`
- `conflicts`
- `job_matches`

The fixture content must include deterministic rows for:

- one imported AWS fact with six years of evidence,
- one source-stated GraphQL fact with five years of evidence,
- one imported API architecture fact with 10+ years of evidence.

All IDs, timestamps, JSON strings, and insertion order are fixed by the seed
script. The DB must not use autoincrement primary keys.

### Expected post-migration state

`fixtures/migrations/expected-post-migration.json` is the reviewed expected state
after a `career-store.v0` fixture is upgraded to `career-store.v1`.
The checker should evaluate this expected state with fixture clock
`2026-01-01T00:00:00Z` so the current migration record is deterministic.

Expected post-upgrade state:

- `migrations` preserves the previous `000_previous_schema_fixture` row.
- `migrations` includes the current `001_initial` row for `career-store.v1`.
- Existing `facts` and `evidence` rows are preserved exactly.
- Current empty tables `relationships`, `conflicts`, and `job_matches` exist.
- The resulting observed schema version is `career-store.v1`.

### Migration checker cases

The release migration checker should consume these fixtures as follows:

- Fresh migrate: input is a missing or empty temp `career.db`; expected output is
  a valid `career-store.v1` DB with `001_initial` recorded and all current
  tables present.
- Idempotent re-run: input is the fresh migrated DB from the prior case;
  expected output is unchanged schema state and exactly one `001_initial`
  migration record.
- Upgrade-from-previous: input is a copy of
  `fixtures/migrations/previous-schema-career.db`; expected output is byte-stable
  fixture data migrated to the explicit state in
  `fixtures/migrations/expected-post-migration.json`.
- Destructive-failure: input is a copy of the previous-schema fixture with
  populated `facts` and `evidence`; expected output is a failed migration if any
  candidate migration would drop populated tables, remove populated columns,
  rewrite fixture facts/evidence, or otherwise destroy stored career truth
  without an explicit audited policy.

## Required Resume Fixture

The main resume fixture should include:

- Senior Software Developer profile.
- 10-12 years software development experience.
- Full-stack SaaS background.
- React.
- TypeScript.
- Node.js.
- PostgreSQL.
- REST/API work.
- Workflow automation.
- Release tooling.
- Responsive apps.
- Small-team leadership where source text supports it.
- Formatting noise: smart quotes, non-breaking space, odd bullet, inconsistent dates.

It must not include:

- AWS.
- GraphQL.
- exact `responsive design` wording unless a specific fixture variant says so.
- formal Staff Software Engineer title.
- 20 million users.
- 30 direct reports.
- unsupported enterprise/global scale claims.
- unsupported outcome metrics.

## Required Job A Fixture

Job A should be a Staff Software Engineer style posting with:

- required `8+ years`,
- required React,
- required TypeScript,
- required API architecture/design,
- required responsive design,
- required SaaS,
- preferred AWS,
- preferred GraphQL,
- preferred technical leadership.

Every requirement should retain source text and normalized terms.

## Required Job B Fixture

Job B should be a Senior Full Stack Engineer style posting with:

- required React,
- required Node.js,
- required GraphQL,
- required AWS,
- preferred PostgreSQL,
- preferred SaaS.

This fixture proves persistent learning from Job A.

## Required Off-Fixture Ingest Fixture

`fixtures/resumes/off-fixture-data-engineer.txt` and
`fixtures/jobs/job-c-data-engineer.txt` define the second-vocabulary ingest
fixture set for RKIT-I-0036 close-out. The pair must use Python, Spark, Kafka,
Airflow, SQL, and data-pipeline vocabulary rather than the original smoke
fixture vocabulary.

Expected:

- resume and job extraction use pinned DeterministicFakeAdapter fixtures under
  `fixtures/resume-agent/fake-adapter/` with reviewed envelopes,
- `resume ingest` persists every declared source-stated fact ID from
  `fixture_manifest.json.off_fixture_ingest_fixture.required_fact_ids`,
- `resume job ingest` persists JobRequirement DTOs with
  `requirement_id`, `classification`, `concept`, `importance`, `weight`,
  `source_text`, `normalized_terms`, and `years`,
- generated base/job subset artifacts match
  `fixtures/ingest-expected/off-fixture-data-engineer-base.json` and
  `fixtures/ingest-expected/off-fixture-data-engineer-job.json`,
- no behavior depends on React, TypeScript, release tooling, or any other original smoke
  fixture keyword.

## Required Answer Fixtures

### AWS

```text
Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM.
```

Expected:

- AWS fact persisted.
- Six years represented according to schema.
- User evidence attached.
- Verification becomes `user_verified`.
- AWS service details may become child/related facts if configured.

### GraphQL

```text
Yes, around five years. I've built and maintained GraphQL APIs in production.
```

Expected:

- GraphQL fact persisted.
- Around five years represented according to schema.
- Production usage recorded only to the level supported by answer evidence.
- Verification becomes `user_verified`.

### Architecture

```text
I've designed APIs and application architecture for more than ten years, but I haven't had Staff Engineer as my formal title.
```

Expected:

- API/application architecture fact persisted.
- `10+` or equivalent schema representation used.
- Formal Staff title is explicitly not added as employment history.
- Requirement can benefit from architecture evidence without title fabrication.

## Required Invalid Operation Fixtures

### Unsupported scale

After text claims service to 20 million users with no evidence. Expected rejection.

### Unsupported management

After text claims management of 30 engineers with no evidence. Expected rejection.

### Title inflation

After value changes actual employment title to Staff Software Engineer solely because the job uses that title. Expected rejection.

### Years inflation

After value changes AWS from six years to ten years. Expected rejection.

### Related-skill overreach

After value treats Azure as proof of AWS. Expected rejection as exact/verified AWS claim.

## Expected Snapshot Fixtures

Snapshots should be reviewed contract artifacts, not accidental implementation output:

- normalized resume snapshot,
- normalized Job A snapshot,
- normalized Job B snapshot,
- initial Job A match result,
- post-AWS match result,
- post-GraphQL match result,
- final Job A match result,
- Job B initial match result using persisted facts,
- selection plan snapshot,
- valid operations snapshot,
- rejected operations snapshot,
- run manifest snapshot,
- audit report snapshot.

Starting with the REQ-001a snapshot substrate, each expected snapshot uses this envelope:

```json
{
  "schema_version": "expected-snapshot.v1",
  "config_hash": "fixture-config-v1",
  "reviewed": true,
  "comment": ["human review intent formerly stored as expected_observations"],
  "data": {}
}
```

Existing metadata fields are preserved. `data` carries the actual canonicalized output from the relevant public package surface. `comment` carries the former prose `expected_observations` review intent so the human reason for the fixture is retained when the data block is regenerated.

Canonical snapshot comparison sorts all object keys deterministically and preserves array order. It drops only this documented volatile-field allowlist at any object depth:

- RKIT-I-0022 per-invocation run identity: `run_id`, `run_identity`.
- Per-call/request identity: `invocation_id`, `request_id`, `trace_id`, `span_id`, `call_id`, `session_id`.
- Process/thread identity: `process_id`, `pid`, `thread_id`.
- Wall-clock audit fields: `created_at`, `updated_at`, `deleted_at`, `timestamp`, `timestamps`, `started_at`, `finished_at`, `completed_at`, `generated_at`, `observed_at`, `recorded_at`.

Domain identity is not volatile. Snapshot comparison must keep `resume_id`, `job_id`, `fact_id`, `requirement_id`, and `operation_id` because those IDs are part of the fixture contract.

Regeneration procedure:

1. Run `python3 tools/regenerate_expected_snapshots.py --root .` to print the canonical data blocks for all 13 snapshot IDs. The generator is stdlib-only, uses no network or LLM calls, uses fixture `config_hash` `fixture-config-v1`, and drives live `resume_core.normalizeResume`, `normalizeJobModel`, `scoreMatch`, and `rankResumeContent`.
2. Prove determinism by running the generator twice and diffing the outputs.
3. Human-review each changed `data` block against the snapshot `comment` and fixture intent.
4. Commit reviewed envelope updates only after review; do not treat generator output alone as approval.

## Fixture Validation Tests

- Fixture resumes parse as text.
- Fixture jobs parse as text.
- Fixture answers are stable and exact.
- Invalid operations target existing canonical paths where applicable.
- Expected snapshots include schema version, config hash, reviewed status, comment, and data.
- Fixture IDs are deterministic.
- No fixture contains accidental unsupported truth that would weaken hallucination tests.
