# career-mcp Test Spec

## Contract

`career-mcp` is a narrow semantic service layer over `career-store`. It exposes career knowledge to agents and orchestrators without exposing arbitrary SQL, unrestricted mutation, or direct database internals.

Allowed tool surface:

- `career.search_facts`
- `career.get_fact`
- `career.propose_fact`
- `career.add_evidence`
- `career.verify_fact`
- `career.add_relationship`
- `career.find_matches`
- `career.get_unverified`

Forbidden tool surface:

- `execute_sql`
- `run_query`
- `truncate`
- `raw_update`
- `raw_delete`
- any equivalent unrestricted database operation

## Expected Structure

Tests should treat MCP as an adapter with:

- tool schema definitions
- argument validation
- response DTO normalization
- error mapping
- authorization/scope policy if added later
- store service dependency injection

## Contract Test Cases

### Tool discovery

- List tools and assert all allowed tools exist.
- Assert no raw SQL or unrestricted mutation tool exists.
- Assert tool descriptions do not encourage direct database modification.
- Assert write tools disclose confirmation requirements and resulting verification state.

### Argument validation

- Reject malformed fact IDs.
- Reject empty searches.
- Reject invalid verification states against the real `career-store`; the accepted set is the canonical enum (`source_stated`, `user_verified`, `imported`, `inferred`, `unknown`), and advertised states must not drift from what the store accepts.
- Reject relationships with unsupported types.
- Reject missing evidence for verification operations that require evidence; covered by `test_real_store_verify_fact_requires_and_forwards_evidence_id_for_source_document_state`.
- Return typed errors without leaking SQL details.
- Every non-ok result must carry a typed `error: {type, message}` envelope; covered by `test_envelope_helper_refuses_non_ok_without_error_object` and `test_real_store_verify_fact_rejected_dict_has_typed_error_envelope`.
- Schema-accepted arguments must never be silently dropped by dispatch; covered by `test_consumed_arguments_assertion_catches_planted_dropped_argument`, `test_propose_fact_forwards_dedupe_key_when_store_surface_accepts_it`, `test_real_store_dedupe_key_is_typed_rejected_when_upsert_fact_cannot_honor_it`, `test_real_store_get_fact_include_conflicts_observably_controls_conflict_records`, and `test_real_store_verify_fact_requires_and_forwards_evidence_id_for_source_document_state`.
- Persistence details in envelope messages must be redacted while ordinary validation messages pass verbatim; covered by `test_raw_sql_fragment_in_envelope_message_is_redacted_without_touching_type_or_data`, `test_sqlite_error_signature_in_envelope_message_is_redacted`, and `test_validation_message_with_plain_update_survives_scrub_verbatim`.

### Search behavior

- `career.search_facts` returns matching facts for React/API/responsive terms.
- Search responses include minimum necessary evidence.
- Search ordering is deterministic.
- Multi-value `verification` and `types` filters have union semantics rather than first-element-only narrowing; covered by `test_search_facts_honors_full_verification_and_type_lists_with_union_semantics` and `test_real_store_full_list_filters_post_filter_without_silent_narrowing`.
- Sensitive fields such as contact data are omitted unless explicitly required.

### Fact retrieval

- `career.get_fact` returns fact content, verification state, evidence summary, relationships, and conflicts.
- Unknown fact IDs return a typed not-found response.
- Unverified facts are clearly marked and cannot be mistaken for confirmed claims.

### Fact proposal

- `career.propose_fact` creates or returns a candidate fact without marking it user verified.
- Duplicate proposals dedupe or reference existing facts deterministically.
- Proposals from agent interpretation remain pending/unknown until validated or confirmed.

### Evidence and verification

- `career.add_evidence` appends evidence.
- `career.verify_fact` can set `user_verified` only when confirmation/evidence is explicit.
- AWS answer fixture creates verified AWS experience with six years.
- GraphQL answer fixture creates verified GraphQL production experience.
- Architecture answer fixture verifies architecture/API-design experience without creating Staff title employment history.

### Relationship creation

- Add a validated relationship from `responsive web apps` to `responsive design`.
- Prevent unverified alias creation when config forbids it.
- Keep Azure and AWS related at most, never equivalent without user-confirmed evidence.

### Match lookup

- `career.find_matches` maps Job A requirements to known facts through a real `career-store` instance; fake-only satisfaction is not sufficient.
- It returns exact/alias/verified/related/possible/unknown states distinctly.
- It resolves AWS and GraphQL for Job B using facts learned in Job A through a real `career-store` instance; fake-only satisfaction is not sufficient.

## Boundary Tests

- Fail if MCP imports plugin host presentation logic.
- Fail if MCP mutates resume files.
- Fail if MCP assigns official match scores.
- Fail if MCP allows agents to bypass `career-store` validation.

## Smoke Coverage

The smoke fixture must prove:

- MCP server/tool registry loads,
- search and get work,
- no raw SQL tool is exposed,
- write tools return mutation status, fact ID, verification state, conflicts, and confirmation-needed indicators.

## E2E Coverage

The E2E fixture must prove:

- MCP search results align with store service results,
- MCP supports targeted gap resolution,
- verified facts learned through user answers are reusable,
- audit can identify which MCP operations changed career knowledge.
