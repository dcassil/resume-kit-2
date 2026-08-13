---
id: 001-career-mcp-transport-auth-policy
level: adr
title: "Career-MCP Transport, Auth, Policy, and State Vocabulary"
number: 1
short_code: "RKIT-A-0002"
created_at: 2026-08-13T20:41:36.752909+00:00
updated_at: 2026-08-13T20:41:36.752909+00:00
decision_date: 
decision_maker: 
parent: 
archived: false

tags:
  - "#adr"
  - "#phase/draft"
  - "#adr"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Career-MCP Transport, Auth, Policy, and State Vocabulary

## Context **[REQUIRED]**

career-mcp is currently an in-process adapter. Full MCP runtime work needs a transport, policy model, store injection/opening contract, audit fields, and authoritative verification/relationship vocabulary. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

Pending. Resolve the open questions below before decomposing blocked initiatives into tasks or implementing runtime-specific behavior.

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Risk Level | Implementation Cost |
|--------|------|------|------------|---------------------|
| Minimal local contract | Keeps first build small and testable | May require later migration | Medium | Low |
| Full production runtime now | Clarifies packaging and acceptance early | Higher design/dependency risk | Medium | Medium |
| Defer capability | Avoids premature assumptions | Leaves listed initiatives blocked | Low | Low |

## Rationale **[REQUIRED]**

The available docs establish boundaries and invariants, but not this concrete product/runtime decision. Capturing it as an ADR prevents hidden assumptions from leaking into implementation tasks.

## Consequences **[REQUIRED]**

### Positive
- Blocked scope is explicit before task decomposition.
- Unblocked hardening initiatives can still proceed.

### Negative
- Some initiatives cannot be decomposed until this ADR is resolved.

### Neutral
- Revisit this ADR when planning the blocked initiatives.

## Open Questions

- Which MCP transport is first: stdio, HTTP/SSE, streamable HTTP, or host-specific adapter?
- Is the first release single-user local only, or multi-user authorization now?
- May MCP open career-store by database path, or must workflow inject a store service?
- Which verification and relationship vocabulary is authoritative across store and MCP?
- Which audit fields are mandatory for workflow run-manifest reconstruction?

## Blocks

- Add Career-MCP Policy, Scope, and Confirmation Enforcement
- Provide Real MCP Transport and Host Runtime
- Align MCP Semantics with Career-Store State and Relationship Contracts
