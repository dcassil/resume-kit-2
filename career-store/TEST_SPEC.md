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

- shared fact/evidence DTO and JSON schema definitions in `career_store.schemas`
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
- Record applied migration IDs and pending migration IDs through `getMigrationState()`.
- Re-run migrations and assert idempotency.
- Reject incompatible schema versions with a typed error.
- Reject a database stamped above the supported schema version before applying additional migrations.
- Preserve wave-era databases by migrating existing facts, relationships, evidence, conflicts, and job matches forward without data loss.
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
- Store `imported` facts from external durable sources without treating them as user-confirmed.
- Store `inferred` facts as discovery-only.
- Store `unknown` when evidence is insufficient.
- Reject silent `inferred -> user_verified` escalation.
- Preserve user verification across separate job sessions.

Executable case names:

- Proposal validation: `tests.unit.test_career_store_interpretation_proposals_unit.CareerStoreInterpretationProposalUnitTests.test_invalid_proposal_shape_returns_typed_validation_errors`, `test_unknown_fact_id_is_typed_validation_error`, `test_audit_probe_raw_text_inputs_are_rejected_without_promotion`, and `test_audit_probe_non_affirmed_proposals_are_evidence_only`.
- Marker-table removal/raw-text gating: `tests.unit.test_career_store_interpretation_proposals_unit.CareerStoreInterpretationProposalUnitTests.test_marker_tables_are_gone_and_raw_confirmation_text_never_drives_state`.
- Transition matrix: `tests.unit.test_career_store_verification_transitions_unit.CareerStoreVerificationTransitionUnitTests.test_exported_transition_matrix_is_the_full_declared_edge_set` and `test_every_allowed_edge_requires_its_exact_authority_and_every_other_edge_is_disallowed`.
- `source_stated` gating: `tests.unit.test_career_store_verification_transitions_unit.CareerStoreVerificationTransitionUnitTests.test_verify_fact_rejects_inferred_to_source_stated_without_source_document_authority` and `test_verify_fact_allows_inferred_to_source_stated_with_source_document_evidence`.
- Downgrade protection: `tests.unit.test_career_store_verification_transitions_unit.CareerStoreVerificationTransitionUnitTests.test_verify_fact_protects_user_verified_from_downgrade_without_explicit_user_correction` and `test_verify_fact_allows_user_verified_downgrade_with_explicit_user_correction_evidence`.
- Cross-session persistence: `tests.unit.test_career_store_verification_transitions_unit.CareerStoreVerificationTransitionUnitTests.test_user_verified_persists_across_reopen_and_distinct_job_sessions`.

### Relationships

- Add alias or related relationships such as `responsive web apps` to `responsive design`.
- Require validation/confirmation policy before using new relationships as equivalent.
- Keep `related` distinct from `alias/equivalent`.
- Prevent Azure from becoming proof of AWS through a related relationship.
- Retain relationship evidence or rationale.
- Effective store behavior covers the restored A-0006 relationship vocabulary: `alias`, `equivalent`, `related`, `parent`, `child`, and `contradicts`.
- Defer `parent` and `child` relationship vocabulary coverage in `store_surface.json` until the protected career-store guardrail lock is updated with the A-0006 relationship realignment batch; the current protected parser still pins the manifest vocabulary to `alias`, `equivalent`, `related`, and `contradicts`.

Executable case names:

- Related-pollution outcome: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_related_relationship_does_not_become_equivalent_match_without_policy`.
- Dictionary-removal outcome: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_compiled_dictionary_pairs_do_not_match_without_stored_relationships`.
- Confirmation policy: `tests.unit.test_career_store_relationship_confirmation_unit.CareerStoreRelationshipConfirmationUnitTests.test_unconfirmed_then_confirmed_alias_policy_applies_in_both_relationship_directions`.
- Parent/child directionality: `tests.unit.test_career_store_relationship_confirmation_unit.CareerStoreRelationshipConfirmationUnitTests.test_parent_child_relationships_are_directional_and_never_exact_or_alias`.
- Contradicts signal: `tests.unit.test_career_store_relationship_confirmation_unit.CareerStoreRelationshipConfirmationUnitTests.test_contradicts_relationship_emits_conflict_signal_and_no_candidate`.

### Search and matching

- Search by concept, normalized terms, and aliases.
- Return minimum necessary evidence.
- Return deterministic ordering for identical inputs.
- Find candidate matches for job requirements.
- Distinguish `exact_match`, `alias_match`, `verified_fact_match`, `related_match`, `possible_match`, `unknown`, `explicitly_missing`, and `not_applicable` states in returned DTOs.
- Return conflicts as conflict records instead of encoding conflicts as verification or resolution states.

Executable case names:

- Direct verified match DTO: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_user_verified_direct_terms_emit_verified_candidate_without_relationship_path`.
- Search filters: `tests.unit.test_career_store_search_facts_unit.CareerStoreSearchFactsUnitTests.test_search_facts_filters_concept_terms_and_verification_state_composably`.
- Confirmed alias filtering: `tests.unit.test_career_store_search_facts_unit.CareerStoreSearchFactsUnitTests.test_search_facts_alias_filter_expands_terms_only_after_confirmation`.
- Evidence minimization: `tests.unit.test_career_store_search_facts_unit.CareerStoreSearchFactsUnitTests.test_search_facts_include_evidence_returns_only_rows_matching_matched_terms`.

### Conflict detection

- Detect contradictory years claims, such as AWS six years versus AWS ten years.
- Detect conflicting title claims, such as actual title versus fabricated Staff title.
- Detect mutually incompatible source statements.
- Return conflict details without silently overwriting existing fact truth.
- Replaying the same conflicting claim must not create duplicate conflict rows.

Executable case names:

- Years heuristic regressions: `tests.unit.test_career_store_conflict_heuristics_unit.CareerStoreConflictHeuristicUnitTests.test_react_version_numbers_do_not_create_years_conflict`, `test_explicit_digit_years_conflict_on_same_concept`, and `test_number_word_above_ten_years_claim_parses_and_conflicts`.
- Title heuristic regressions: `tests.unit.test_career_store_conflict_heuristics_unit.CareerStoreConflictHeuristicUnitTests.test_structured_title_claims_conflict_for_same_role_slot_outside_legacy_title_list` and `test_staff_title_fixture_conflicts_via_structured_title_model`.
- Self-claim and replay idempotency: `tests.unit.test_career_store_conflict_heuristics_unit.CareerStoreConflictHeuristicUnitTests.test_claim_fact_id_is_not_checked_against_itself_but_competing_claim_conflicts` and `test_duplicate_conflict_creation_replays_produce_single_open_conflict_row`.
- Contract conflict shape: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_conflicting_claims_are_returned_without_overwriting_history`.

### Conflict workflow

- Resolve conflicts by recording the user answer, preserving both competing claims, and marking the conflict resolved.
- Dismiss conflicts by recording the user answer without requiring a winning claim.
- Re-adjudicating with the identical decision must be idempotent; re-adjudicating with a different decision must be rejected.
- Adjudication must not overwrite stored fact text, evidence, or conflict metadata.
- Verification-changing adjudication must route through the verification transition engine.
- Agent-only adjudication must not change verification state or close the conflict.

Executable case names:

- Resolve/no-overwrite: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_resolve_conflict_records_answer_interaction_and_preserves_both_claims`.
- Dismiss: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_dismiss_conflict_records_answer_interaction_without_winner`.
- Adjudicate idempotency/no-overwrite: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_identical_readjudication_is_idempotent_but_different_readjudication_is_rejected`.
- Engine routing: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_user_adjudication_routes_verification_change_through_engine`.
- Agent authority rejection: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_agent_only_adjudication_cannot_change_verification_state_and_leaves_conflict_open`.
- Typed validation: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_unknown_conflict_invalid_decision_and_malformed_provenance_are_typed_errors`.

### Job associations

- Record requirement-to-fact matches for a job.
- Create a stable row in the `jobs` table for each source job ID seen by `recordJobMatch`.
- Backfill deterministic `jobs` rows from pre-realignment `job_matches` data during migration.
- Store job metadata separately from match metadata so job identity/history survives repeated match writes.
- Add `match_type`, `confidence`, and `user_confirmed` values to `job_fact_matches`/`job_matches` rows without changing the requirement-to-fact association.
- Preserve which facts were used for Job A versus Job B.
- Reuse user-verified AWS and GraphQL facts learned during Job A when matching Job B.
- Do not pollute base resume or job-specific working resume state.

Executable case names:

- Job metadata columns: `tests.unit.test_career_store_jobs_unit.CareerStoreJobsUnitTests.test_record_job_match_creates_stable_job_identity_row`.
- Cross-job reuse with metadata columns: `tests.unit.test_career_store_jobs_unit.CareerStoreJobsUnitTests.test_job_b_reuses_job_a_verified_facts_and_records_match_metadata_columns`.
- Per-job association retention: `tests.unit.test_career_store_jobs_unit.CareerStoreJobsUnitTests.test_record_job_match_preserves_job_associations_by_job`.
- Resume-state non-pollution: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_job_match_recording_does_not_mutate_resume_state_or_return_raw_database_handles`.

### Interaction and preference history

- Record user confirmations for AWS, GraphQL, and architecture.
- Record accepted/modified/rejected rewrite decisions separately from career facts if preference learning exists.
- Assert preference learning cannot change verification state.
- Assert rejecting phrasing does not remove the underlying career fact.

Executable case names:

- Schema and append-only storage: `tests.unit.test_career_store_interactions_unit.CareerStoreInteractionsUnitTests.test_schema_008_creates_append_only_interactions_table`.
- Vocabulary, transaction result, and replay idempotency: `tests.unit.test_career_store_interactions_unit.CareerStoreInteractionsUnitTests.test_record_interaction_uses_vocabulary_validation_transaction_and_replay_idempotency`.
- Deterministic listing/filtering: `tests.unit.test_career_store_interactions_unit.CareerStoreInteractionsUnitTests.test_list_interactions_filters_deterministically_and_rejects_malformed_filters`.
- Preference/confirmation non-promotion: `tests.unit.test_career_store_interactions_unit.CareerStoreInteractionsUnitTests.test_fact_confirmed_interaction_does_not_mutate_verification_state`.
- Boundary isolation: `tests.unit.test_career_store_interactions_unit.CareerStoreInteractionsUnitTests.test_interactions_module_has_no_verification_or_state_mutation_imports`.

### Transactions and recovery

- Execute conflict detection and fact/evidence writes inside one store-owned transaction.
- Roll back partial fact/evidence writes on failure.
- Return a `TransactionResult` for committed and rolled-back mutating operations.
- Embed transaction result details in `upsertFact`, `verifyFact`, `addEvidence`, `addRelationship`, and `recordJobMatch` mutation responses.
- Preserve evidence append-only behavior and deterministic IDs through the transaction path.
- Resume after interruption following user verification.
- Detect duplicate writes from retried operations.
- Preserve DB validity after simulated process interruption.

Executable merge-retention case names:

- Merge retention: `tests.unit.test_career_store_merge_facts_unit.CareerStoreMergeFactsUnitTests.test_merge_facts_retains_aliases_evidence_history_redirect_and_job_matches`, `test_merge_facts_preserves_user_verified_survivor_when_merged_is_inferred`, and `test_merge_facts_does_not_promote_inferred_survivor_from_user_verified_merged_fact`.
- Merge atomicity: `tests.unit.test_career_store_merge_facts_unit.CareerStoreMergeFactsUnitTests.test_merge_facts_rolls_back_after_repoint_interruption`.

Executable transaction/retry case names:

- Upsert rollback: `tests.unit.test_career_store_transactions_unit.CareerStoreTransactionUnitTests.test_upsert_rollback_after_conflict_detection_leaves_no_partial_rows_and_reports_transaction`.
- Interaction replay: `tests.unit.test_career_store_interactions_unit.CareerStoreInteractionsUnitTests.test_record_interaction_uses_vocabulary_validation_transaction_and_replay_idempotency`.
- Conflict creation replay: `tests.unit.test_career_store_conflict_heuristics_unit.CareerStoreConflictHeuristicUnitTests.test_duplicate_conflict_creation_replays_produce_single_open_conflict_row`.
- Conflict adjudication replay: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_identical_readjudication_is_idempotent_but_different_readjudication_is_rejected`.
- Adjudication rollback: `tests.unit.test_career_store_conflict_lifecycle_unit.CareerStoreConflictLifecycleUnitTests.test_adjudicate_conflict_rolls_back_when_interaction_insert_fails_after_conflict_update`.

## Boundary Tests

- Fail if store imports CLI/plugin host code.
- Fail if store asks natural-language questions.
- Fail if store renders resumes or changes resume files.
- Fail if any public API exposes raw SQL execution.
- Assert real store outputs are built without raw SQL handles, resume mutation payloads, official scores, or silent verification-promotion fields; this is a result-shape contract, not a sanitizer implementation contract.

Executable real-output case names:

- Source fact output shape: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_fact_upsert_persists_source_stated_fact_with_evidence`.
- Job match output shape: `tests.contract.test_career_store_contract.CareerStorePersistenceContractTests.test_job_match_recording_does_not_mutate_resume_state_or_return_raw_database_handles`.
- MCP match output shape: `tests.contract.test_career_mcp_contract.CareerMcpAdapterContractTests.test_find_matches_returns_resolution_states_without_official_scores`.

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
