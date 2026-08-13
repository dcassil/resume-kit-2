---
id: 001-career-store-migration-state-and
level: adr
title: "Career-Store Migration State and Preference History Contract"
number: 1
short_code: "RKIT-A-0001"
created_at: 2026-08-13T20:38:59.471700+00:00
updated_at: 2026-08-13T21:40:47.357505+00:00
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

# Career-Store Migration State and Preference History Contract

## Context **[REQUIRED]**

career-store exposes MigrationState and references preference history, but the public function surface does not define how migration state or accepted/modified/rejected rewrite preferences are queried or written. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

Career-store exposes migration state through a new public API, and preference history is required now as a thin append-only substrate that can never alter fact verification.

1. **Migration state — new public API.** Add `getMigrationState()` to the store surface returning the existing `MigrationState` DTO (schema version, applied migration ids, pending migration ids). `openStore` may embed the same DTO in its result for convenience, but `getMigrationState()` is the contract surface. Workflow run manifests obtain `careerDbVersion` from it. Opening a database with an incompatible schema version fails with a typed error; no silent upgrade or downgrade.
2. **Preference history — required now.** Create the vision section 6 `interactions` table (id, interaction_type, subject_id, input_json, result_json, created_at), append-only, with public `recordInteraction()` and `listInteractions(filter)` APIs. Initial interaction_type vocabulary: `question_asked`, `answer_recorded`, `fact_confirmed`, `rewrite_accepted`, `rewrite_modified`, `rewrite_rejected`.
3. **Minimal DTO without overlap.** Interaction records reference resume-core `ResumeChangeOperation` ids and career-store fact ids as opaque `subject_id` values only. Operation status lifecycle stays owned by resume-core; workflow audit refs point at interaction ids. No store code path may write `facts.verification_status` from interaction records — a boundary test must enforce the absence of such a path (Persistence Gate: preference learning cannot alter fact verification).

Decided 2026-08-13 by Daniel Cassil (options ratified in session; details derived from PRODUCT_VISION_AND_CONTRACTS.md sections 6 and 15 and E2E Phase 16).

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Outcome |
|--------|------|------|---------|
| Migration state via new public `getMigrationState()` API | Explicit contract; re-queryable at any time; independently testable; run manifests read a real `careerDbVersion` | One more public surface to maintain | **Chosen** |
| Migration state via store-open metadata only | No new surface | State unavailable after open without reopening; audit reconstruction cannot re-query; hides schema identity inside an unrelated result | Rejected |
| Migration state via operation audit metadata | Reuses existing audit plumbing | Conflates schema identity with mutation history; unavailable before the first mutation | Rejected |
| Defer preference history entirely | Less schema now | E2E Phase 16 and section 6 require the substrate; retrofitting append-only history later costs a migration; the Persistence Gate rule needs a concrete enforcement point now | Rejected |
| Full preference-learning model now (rankers, weights) | Complete feature | Premature — consumers (workflow/agent learning) do not exist yet; thin substrate suffices | Rejected |

## Rationale **[REQUIRED]**

The Audit Gate requires `careerDbVersion` and interaction history to be reconstructable from persisted state, and section 6 lists migrations, user confirmation history, and optional preference history as career-store responsibilities. A dedicated read API keeps schema identity queryable at any time without coupling it to mutation audit. Requiring the interactions substrate now — thin and append-only — gives the Persistence Gate rule ("preference learning cannot alter fact verification") a structural enforcement point instead of a promise, at low cost.

## Consequences **[REQUIRED]**

### Positive
- RKIT-I-0005 and RKIT-I-0008 can decompose; the transitive block on RKIT-I-0006/0007 is lifted.
- Workflow run manifests get a real, re-queryable `careerDbVersion`.
- The Persistence Gate rule (preference learning cannot alter verification) gains a structural enforcement point and a boundary test.

### Negative
- career-store scope grows: migration registry, `getMigrationState()`, the `interactions` table, two new public APIs, and `store_surface.json`/contract-test extensions (protected-surface edits authorized by RKIT-A-0006).
- The interaction_type vocabulary is a new mini-contract to version.

### Neutral
- Interaction types may grow later; additions are additive migrations.
- ChangeOperation `accepted`/`modified` statuses (restored by RKIT-A-0006) describe operation lifecycle; interaction records describe user history — the two coexist without overlap.

## Resolved Questions

- Migration state exposure → a new public API (`getMigrationState()`); store-open metadata may mirror it; operation audit metadata does not carry schema identity.
- Preference history now or deferred → required now as a thin append-only substrate; its consumers (workflow/agent learning) may land later.
- Minimal DTO without overlap → `interactions` rows referencing operation/fact ids as opaque subject ids; operation status stays in resume-core; verification writes from interaction records are structurally forbidden.

## Blocks

- RKIT-I-0005 Durable Career-Store Package and Migration Foundation — lifted (decided)
- RKIT-I-0008 Conflict, Audit, Recovery, and Optional Preference History — lifted (decided)
- Transitive via the package chain: RKIT-I-0006, RKIT-I-0007 — lifted (decided)