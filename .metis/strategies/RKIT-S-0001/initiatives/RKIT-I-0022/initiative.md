---
id: workflow-artifact-schemas-and-run
level: initiative
title: "Workflow Artifact Schemas and Run State Contract"
short_code: "RKIT-I-0022"
created_at: 2026-08-13T20:41:37.353788+00:00
updated_at: 2026-08-15T02:48:28.911965+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/decompose"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: workflow-artifact-schemas-and-run
---

# Workflow Artifact Schemas and Run State Contract Initiative

## Context **[REQUIRED]**

Package: `workflow`. The schema layer is not greenfield: the `RunManifest` frozen dataclass plus a JSON-schema fragment with all 21 contract-required fields already exist (workflow/schemas.py:13-113), along with the 18-checkpoint enum and durable JSON run-state persistence under `.workflow/runs` (workflow/__init__.py:235-245). What remains is the contract-critical work the scaffold skipped, each item verified against code by the alignment audit:

- **Run identity collides.** `run_id = f"run_{config_hash[:16]}"` (workflow/__init__.py:41) derives identity solely from the config hash, so two runs with identical config — e.g. Job A then Job B in the same workspace — share one run_id and overwrite each other's persisted state (verified collision). This breaks section 15 per-run manifest identity and the Job A/B audit-reconstruction expectation.
- **Versions are fake.** `package_versions` is hardcoded to '0.0.0' and schema versions are inlined string literals (workflow/__init__.py:47-58); matching_algorithm_version and matching_config_version fall back to hardcoded literals (workflow/__init__.py:178-179), contrary to PRODUCT_VISION_AND_CONTRACTS.md section 16 ("record all relevant versions/hashes").
- **Manifests are never validated.** buildRunManifest performs no validation against RUN_MANIFEST_SCHEMA; empty-string defaults for base_resume_id/hash, job_id, and renderer_template_version pass silently (workflow/__init__.py:166-195).
- **Audit Gate fields are missing.** The manifest drops question/answer refs and carries no unresolved-requirements field, both required by the Audit Gate reconstruction list (CONTRACT_SURFACE_ALIGNMENT.md:353-366).

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Every run gets a unique run_id; same-config runs persist side by side, with config_hash recorded as a field rather than serving as identity.
- All manifest versions are real: package versions read from installed metadata, schema versions from schema modules, matching versions from resume-core's surface, and `careerDbVersion` from career-store `getMigrationState()` per RKIT-A-0001.
- buildRunManifest validates against RUN_MANIFEST_SCHEMA and rejects empty identity fields with typed errors.
- The manifest DTO/schema gains question/answer log refs and an unresolved-requirements field so the full Audit Gate list (CONTRACT_SURFACE_ALIGNMENT.md:353-366) is representable.

**Non-Goals:**
- Grounding transition evidence or fixing state-machine defects — RKIT-I-0023.
- Persisting audit events, writing real artifacts, or reconstructing manifests from persisted state — RKIT-I-0024 (this initiative delivers the validated shapes those consumers fill).
- Recovery and idempotency semantics — RKIT-I-0025.
- Smoke/E2E acceptance proofs — RKIT-I-0028.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Fix the run-identity collision (workflow/__init__.py:41): run_id must be unique per createRun invocation; creating two runs with identical config must yield two distinct, independently persisted run states (satisfies section 15 run-manifest identity and the Job A/B audit expectation).
2. Replace hardcoded '0.0.0' package_versions and inlined schema-version literals (workflow/__init__.py:47-58) with values read from installed package metadata and the schema modules themselves (satisfies section 16).
3. Replace hardcoded matching-version fallbacks (workflow/__init__.py:178-179) with versions obtained from resume-core's public surface; a missing source is a typed error, never a placeholder literal.
4. Record `careerDbVersion` from career-store `getMigrationState()` as decided in RKIT-A-0001; workflow must not invent store truth.
5. buildRunManifest must validate its output against RUN_MANIFEST_SCHEMA and fail with a typed error on empty base_resume_id, base_resume_hash, job_id, or renderer_template_version (workflow/__init__.py:166-195).
6. Extend RunManifest and RUN_MANIFEST_SCHEMA with `question_answer_log_refs` and `unresolved_requirements` per CONTRACT_SURFACE_ALIGNMENT.md:353-366.

### Dependencies
- None within the workflow group; this initiative heads the chain (blocked_by is empty).
- RKIT-A-0001 (decided) supplies the `getMigrationState()` contract used for careerDbVersion.
- RKIT-A-0006 (decided) authorizes strengthening protected specs, manifests, and contract tests during realignment.

### Blocked Status
- Not blocked. All previously pending ADRs are decided; the decided RKIT-A-0001 and RKIT-A-0006 are referenced above as inputs, not blockers.

## Detailed Design **[REQUIRED]**

**Run identity.** run_id becomes `run_<UTC-timestamp>_<random-suffix>` (or UUIDv7), generated at createRun time. config_hash remains a manifest field and a determinism input but never the identity. Run-state persistence keys by run_id; a small workspace index maps job_id/config_hash to run_ids for lookup. Migration note: existing `.workflow/runs` entries keyed by config-hash-derived ids stay readable, and new runs can never collide with them.

**Version recording.** A `collectVersions()` helper resolves each package version via installed-package metadata, schema versions via constants exported by the schema modules, matching algorithm/config versions via resume-core's public surface, and careerDbVersion via `getMigrationState()` (RKIT-A-0001: schema version, applied migration ids, pending migration ids). There are no literal fallbacks; an unresolvable source raises a typed error rather than emitting '0.0.0'.

**Manifest validation.** buildRunManifest validates the assembled manifest against RUN_MANIFEST_SCHEMA before returning. Identity fields (base_resume_id, base_resume_hash, job_id, renderer_template_version) gain minLength constraints so today's silent empty strings become schema violations.

**Schema additions.** RunManifest gains `question_answer_log_refs` (refs into the run's question/answer log) and `unresolved_requirements` (requirement id, resolution state, reason), with matching RUN_MANIFEST_SCHEMA entries. The producers that populate them land in RKIT-I-0024; this initiative delivers the validated shape and the schema-level obligation that they exist.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract test: two createRun calls with identical config produce distinct run_ids and both run states survive on disk (regression for the verified collision at workflow/__init__.py:41).
- Contract test: buildRunManifest raises a typed validation error on empty identity fields and on any placeholder ('0.0.0') version value.
- Contract test: manifest careerDbVersion equals career-store getMigrationState() output for the run's database.
- TEST_SPEC strengthening (audit-flagged): the run-manifest field list in workflow/TEST_SPEC.md:83-101 omits unresolved requirements and question/answer content, so a manifest can satisfy the spec while failing the Audit Gate — extend the spec list to the CONTRACT_SURFACE_ALIGNMENT.md:353-366 set. RKIT-A-0006 authorizes this protected-spec strengthening (assertion strength may only increase).

## Alternatives Considered **[REQUIRED]**

- **Keep config-hash-derived run_id and treat same-config reruns as resume-in-place.** Rejected: section 15 requires per-run manifests, and the E2E Job B proof requires two same-config runs to coexist; overwrite semantics destroy the audit trail the manifest exists to serve.
- **Validate manifests only in tests, not inside buildRunManifest.** Rejected: that repeats the honor-system pattern — production paths would still emit invalid manifests; validation must live at the build site so every caller is gated.
- **Record versions from a checked-in versions file.** Rejected: it drifts from what is actually installed and reintroduces hand-maintained literals — exactly the '0.0.0' failure mode this initiative removes.

## Implementation Plan **[REQUIRED]**

**Progress 2026-08-13 — chunk 1 (run identity) implemented via TDD, gates green, adversarial review in flight.** Daniel green-lit continuing down the audit defect table ("Do it"); this initiative is unblocked and heads its chain. Implementation: `createRun` now derives `run_id` from private `_new_run_id(workspace, config_hash)` — `run_<confighash16>_<NNNN>` where the sequence comes from scanning existing `.workflow/runs/run_<confighash16>*.json` files (collision-proofed with a while-loop), and `_index_run` maintains `.workflow/runs/index.json` mapping `config_hash → [run_ids]` (job_id mapping deferred until job_id exists in run state — RKIT-I-0024 consumers). **Design deviation, documented:** the Detailed Design sketched `run_<UTC-timestamp>_<random-suffix>` / UUIDv7, but `tests/suite_manifest.json` `determinism_requirements` includes `frozen_time_for_ids` and the repo's determinism law favors clock-free ids; the filesystem-sequence scheme is unique per invocation, deterministic under test, needs no new imports, and legacy unsuffixed `run_<hash16>` ids can never collide with new suffixed ids (they are counted into the sequence and remain recoverable via `recoverRun`). Two RED-first contract tests added to `tests/contract/test_workflow_contract.py` (both run in the PR gate): `test_same_config_runs_get_distinct_ids_and_coexisting_persisted_state` (also proves the first run's advanced checkpoint state survives the second `createRun` — the overwrite half of the defect) and `test_workspace_run_index_maps_config_hash_to_all_run_ids`. `workflow_surface.json` `createRun` description realigned from "Create or load…" to create-only (loading is `recoverRun`'s job), matching this initiative's decided rejection of same-config resume-in-place. Verification: workflow contract suite 11/11, focused contract+boundary command 18/18, PR gate OK, smoke OK, future-contract OK, `tools/workflow_guardrails.py` OK. Chunks 2-5 (real versions, careerDbVersion via `getMigrationState()`, manifest validation, schema additions) remain untouched.

**Adversarial review verdict (same day): 0 refutations from 3 skeptics at high confidence.** Mutation probes killed: the original hash-only id scheme (both tests fail), unique-ids-with-clobbering-persistence (the recoverRun checkpoint assertions catch it), no-op and order-breaking index writes. Legacy-id coexistence, determinism (identical id sequences across fresh workspaces), and section-15 conformance probe-verified. One finding taken immediately with TDD: `_index_run` crashed with untyped AttributeError when `index.json` held valid-JSON-but-non-object content (`[]`/`null`) — fixed with an `isinstance(index, dict)` guard plus regression test `test_create_run_tolerates_malformed_workspace_index` (workflow suite now 12/12, PR gate 191 OK). **Recorded residuals for later chunks/owners:** (1) TOCTOU race — concurrent same-workspace `createRun` calls can mint duplicate ids (glob-then-write, no locking); acceptable today (single-process sequential orchestrator, no concurrent caller exists) but harden with `O_CREAT|O_EXCL`+retry when concurrency arrives. (2) Manual deletion of the newest run file lets the next run reuse the deleted id (filesystem count is the counter); the system never deletes run files itself — an accepted price of the clock-free determinism choice. (3) On truly invalid JSON the index resets to `{}` losing prior mappings instead of rebuilding from the run files sitting beside it — the index is a lookup aid and run files remain the source of truth; rebuild-on-corruption is a later nicety. (4) Sequence padding breaks lexicographic ordering past 9999 runs (`_10001`); uniqueness unaffected. (5) CLI depth issue now more visible (pre-existing, RKIT-I-0040/0024 scope): `resume-cli` `_init` (resume_cli/__init__.py:81) calls `createRun` from every command and discards the returned state, so one `resume run` leaves multiple INIT-stub run files, and `_audit_report` (line 347) mints a fresh run per invocation so its reported `run_identity` drifts — previously these silently overwrote one state file; the accumulation is the honest surfacing of a misuse of `createRun` as an identity lookup.

Decomposition guidance (tasks to be created at decompose phase, in dependency order):
1. Unique run identity: generation, run-state keying, workspace index, and the same-config collision regression test.
2. collectVersions() with real package/schema/matching sources and typed errors on missing sources.
3. careerDbVersion integration via career-store getMigrationState() (RKIT-A-0001 surface).
4. RUN_MANIFEST_SCHEMA validation inside buildRunManifest plus minLength identity constraints.
5. Manifest field additions (question_answer_log_refs, unresolved_requirements) and the TEST_SPEC:83-101 field-list strengthening.