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
- Reject invalid verification states.
- Reject relationships with unsupported types.
- Reject missing evidence for verification operations that require evidence.
- Return typed errors without leaking SQL details.

### Search behavior

- `career.search_facts` returns matching facts for React/API/responsive terms.
- Search responses include minimum necessary evidence.
- Search ordering is deterministic.
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

- `career.find_matches` maps Job A requirements to known facts.
- It returns exact/alias/verified/related/possible/unknown states distinctly.
- It resolves AWS and GraphQL for Job B using facts learned in Job A.

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

