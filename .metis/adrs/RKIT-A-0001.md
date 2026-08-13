---
id: 001-career-store-migration-state-and
level: adr
title: "Career-Store Migration State and Preference History Contract"
number: 1
short_code: "RKIT-A-0001"
created_at: 2026-08-13T20:38:59.471700+00:00
updated_at: 2026-08-13T20:38:59.471700+00:00
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

# Career-Store Migration State and Preference History Contract

## Context **[REQUIRED]**

career-store exposes MigrationState and references preference history, but the public function surface does not define how migration state or accepted/modified/rejected rewrite preferences are queried or written. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

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

- Should migration state be exposed through existing operation audit metadata, store-open metadata, or a new public API?
- Is rewrite preference history required in career-store now, or deferred until workflow/agent learning is implemented?
- If required now, what minimal DTO avoids overlapping resume-core change operations and workflow audit?

## Blocks

- Durable Career-Store Package and Migration Foundation
- Conflict, Audit, Recovery, and Optional Preference History
