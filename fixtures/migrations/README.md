# Migration Fixtures

This folder contains the stable career-store migration fixtures described in
`fixtures/TEST_SPEC.md`.

## Files

- `seed_previous_schema.py` generates `previous-schema-career.db`.
- `previous-schema-career.db` is a generated SQLite fixture for
  `career-store.v0`, a schema strictly older than the current
  `career-store.v1` schema.
- `expected-post-migration.json` records the reviewed expected state after the
  previous-schema fixture is upgraded to `career-store.v1`.
  It uses fixture clock `2026-01-01T00:00:00Z` for deterministic migration
  metadata.

## Determinism

The generator is stdlib-only and uses no network, wall-clock values,
autoincrement IDs, or unordered inserts. To verify byte stability:

```sh
python3 fixtures/migrations/seed_previous_schema.py
shasum fixtures/migrations/*.db > /tmp/h1
python3 fixtures/migrations/seed_previous_schema.py
shasum fixtures/migrations/*.db > /tmp/h2
diff /tmp/h1 /tmp/h2
```

The generated DB intentionally contains only the previous-schema tables
`migrations`, `facts`, and `evidence`; the expected post-migration state adds
the current empty `relationships`, `conflicts`, and `job_matches` tables while
preserving all existing fixture rows.
