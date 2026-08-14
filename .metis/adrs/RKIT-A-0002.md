---
id: 001-career-mcp-transport-auth-policy
level: adr
title: "Career-MCP Transport, Auth, Policy, and State Vocabulary"
number: 1
short_code: "RKIT-A-0002"
created_at: 2026-08-13T20:41:36.752909+00:00
updated_at: 2026-08-13T21:40:48.066410+00:00
decision_date: 2026-08-13
decision_maker: Daniel Cassil
parent: 
archived: false

tags:
  - "#adr"
  - "#adr"
  - "#phase/decided"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Career-MCP Transport, Auth, Policy, and State Vocabulary

## Context **[REQUIRED]**

career-mcp is currently an in-process adapter. Full MCP runtime work needs a transport, policy model, store injection/opening contract, audit fields, and authoritative verification/relationship vocabulary. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

1. **Transport.** First transport is a stdio JSON-RPC MCP server. The existing in-process adapter remains supported for CLI orchestration and tests. HTTP/SSE and streamable HTTP are deferred until a remote host exists.
2. **Auth scope.** v1 is single-user local only (consistent with product section 17 local/user-scoped data). No multi-user authorization layer. Until real scope enforcement exists, `tool_surface.json` must stop claiming that `tools/call` "enforces scope policy".
3. **Store access.** The stdio server opens career-store by database path supplied at server startup (config/CLI argument); the in-process adapter accepts an injected store service. Both paths use only the public store service API — never SQL.
4. **Authoritative vocabulary and surfaces.** The canonical section 4.4/4.6 enum sets are authoritative across store and MCP (per RKIT-A-0006). career-mcp may advertise only states and relationship types the career-store contract supports. The camelCase `store_surface.json` interface is the only store interface career-mcp may call; the private snake_case dialect is removed and contract tests must exercise the real store surface. The package copy `career-mcp/career_mcp/tool_surface.json` is the single canonical manifest; the root copy is removed or generated from it.
5. **Mandatory mutation audit fields.** Tool name, operation id, redacted arguments, affected fact ids, mutation flag, resulting verification state, conflict flag, confirmation_required, timestamp. Read calls log tool name and status only. These fields are the substrate workflow run-manifest reconstruction consumes.

Decided 2026-08-13 by Daniel Cassil (vocabulary direction ratified in session; remaining points derived from PRODUCT_VISION_AND_CONTRACTS.md sections 7 and 17 and the audit's fake-vs-real interface findings).

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Outcome |
|--------|------|------|---------|
| stdio JSON-RPC server first | Standard local MCP transport; matches section 17 local-only posture; testable in CI without network | No remote host support yet | **Chosen** |
| HTTP/SSE or streamable HTTP first | Remote-ready | Premature — no remote host exists; drags multi-user auth burden forward | Rejected |
| In-process adapter only (no server) | Zero transport work | Not a consumable MCP surface; section 7 promises agent-callable tools; TEST_SPEC smoke requires a loadable server | Rejected as sole path (kept as secondary) |
| Multi-user authorization now | Future-proof | Contradicts section 17 local scope; large cost with no multi-user deployment | Rejected |
| Keep the private snake_case store dialect | No adapter changes | Contract tests would keep exercising an interface production never takes — the root cause of the audit's confirmed real-store failures | Rejected |

## Rationale **[REQUIRED]**

Transport and auth follow the product's local, user-scoped security posture (section 17) — stdio is the standard local MCP transport and requires no auth infrastructure the product does not need yet. The surface-authority decisions close the fidelity gap the audit demonstrated: all 19 career-mcp contract tests exercised a snake_case store API that only the test fake implements, while the real camelCase path failed empirically (advertised 'imported' and 'child'/'parent' rejected at runtime). Making the declared store surface and a single canonical tool manifest authoritative makes those failures structurally impossible rather than merely untested.

## Consequences **[REQUIRED]**

### Positive
- RKIT-I-0011, RKIT-I-0012, RKIT-I-0013, and RKIT-I-0014 can decompose; RKIT-I-0015's transitive block is lifted.
- The fake-vs-real interface gap (19 contract tests against a store API production never takes) gets a decided resolution: the real camelCase surface only.
- The duplicated tool_surface.json drift risk is closed (single canonical package copy).

### Negative
- The stdio server, argument redaction, and audit-field plumbing are new work; `tool_surface.json` must be corrected where it currently overstates behavior (scope-policy claim; child/parent types until the career-store relationship restoration under RKIT-A-0006 lands).
- career-mcp contract tests must be rewritten against the real store surface (protected-surface edits authorized by RKIT-A-0006).

### Neutral
- HTTP transports and multi-user authorization revisit this ADR when a remote host appears.

## Resolved Questions

- First transport → stdio JSON-RPC server; in-process adapter retained as a secondary path.
- Single vs multi-user → single-user local (product section 17).
- Open by path vs injected store → both: database path for the stdio server, injected service for the in-process adapter; identical public service API underneath.
- Authoritative vocabulary → the canonical section 4.4/4.6 sets per RKIT-A-0006; the camelCase `store_surface.json` interface is the only store surface.
- Mandatory audit fields → tool name, operation id, redacted arguments, affected fact ids, mutation flag, resulting verification state, conflict flag, confirmation_required, timestamp.

## Blocks

- RKIT-I-0011 Align Career-MCP Semantics with Career-Store State and Relationship Contracts — lifted (decided)
- RKIT-I-0012 Add Career-MCP Policy, Scope, and Confirmation Enforcement — lifted (decided)
- RKIT-I-0013 Implement Career-MCP Mutation Audit and Operation Traceability — lifted (decided; this initiative was missing from the original Blocks list although open question 5 gated it)
- RKIT-I-0014 Provide Real Career-MCP Transport and Host Runtime — lifted (decided)
- Transitive: RKIT-I-0015 — lifted (decided)