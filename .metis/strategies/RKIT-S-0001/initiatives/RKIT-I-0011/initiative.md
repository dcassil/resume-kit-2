---
id: align-career-mcp-semantics-with
level: initiative
title: "Align Career-MCP Semantics with Career-Store State and Relationship Contracts"
short_code: "RKIT-I-0011"
created_at: 2026-08-13T20:41:37.059367+00:00
updated_at: 2026-08-16T19:45:39.295738+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0005, RKIT-I-0007]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: align-career-mcp-semantics-with
---

# Align Career-MCP Semantics with Career-Store State and Relationship Contracts Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. The alignment audit traced every confirmed runtime failure in this package to one root cause: the adapter prefers a private snake_case store dialect (`search_facts`/`get_fact`/`propose_fact`/`verify_fact`/`add_evidence`/`add_relationship`/`find_matches`/`get_unverified`, preferred at `career_mcp/__init__.py:62,82,103,118,126,137,152,163`) that only the test `FakeCareerStore` implements — no declared career-store surface defines it. All 19 contract tests exercise this fake-only path; the real camelCase fallback, where production actually runs, is nearly untested. Verified consequences against the real store:

- `career.verify_fact` with `imported` (advertised in `tool_surface.json:268-274`, canonical per section 4.6) is rejected — the store's `_VERIFICATION_STATES` lacks `imported` and adds non-canonical `explicitly_missing`/`conflicted` (`career-store/career_store/store.py:16-24`).
- `career.add_relationship` with `child`/`parent` is rejected as `invalid_relationship_type`.
- The `types` filter is a complete no-op: the adapter maps only `types[0]` and `store.searchFacts` ignores a `type` filter key entirely (`career-store/career_store/store.py:176-178`).
- `career.get_unverified` queries only `verification_state='unknown'` (`career_mcp/__init__.py:167-176`) and misses inferred facts — an inferred Kubernetes fact returned an empty result — though vision section 7 line 524 requires "unresolved/inferred facts".
- `career.find_matches` concatenates the store's `matches` and `unresolved` lists (`:156-159`) while the store places weak matches in both (`store.py:516-525`), so each weak requirement appears twice with contradictory classifications, one with `fact_ids: []` and misleading reasoning (`:337-343`).
- Non-canonical `ResolutionState` `conflicted` leaks through `find_matches` untranslated (`:325-334`) while the manifest promises the section 4.4 set including `not_applicable`.

RKIT-A-0002 item 4 and RKIT-A-0006 (both decided) settle direction: the camelCase `store_surface.json` interface is the only store surface career-mcp may call; the snake_case dialect is removed; contract tests must exercise the real store surface; enums realign to the canonical section 4.4/4.6 sets with `parent`/`child` restored and `contradicts` retained as a recorded extension. This initiative is blocked by the career-store work that lands those semantics: RKIT-I-0005 (durable store package/migration foundation carrying the enum realignment) and RKIT-I-0007 (relationship-aware matching and restored relationship types).

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- The adapter speaks only the declared camelCase store surface; the private snake_case dialect and its dual-dispatch are deleted.
- Contract tests exercise the real store surface; each empirically confirmed failure above becomes a permanent regression test.
- `career.find_matches` returns exactly one coherent classification per requirement; `career.get_unverified` returns unresolved, inferred, and unknown facts; the `types` filter actually filters.
- Advertised enums, canonical contract sets (RKIT-A-0006), and store-accepted values agree three ways — including re-advertising `imported` and `parent`/`child` once the store supports them, reversing RKIT-I-0009's interim removal.

**Non-Goals:**
- Error-envelope and classification mechanics — RKIT-I-0010 (runs in parallel; this initiative builds on its envelope).
- Confirmation/policy semantics — RKIT-I-0012.
- Fixture/E2E product scenarios — RKIT-I-0015 proves scenarios end-to-end; this initiative makes the semantics they exercise correct.
- The store-side enum/matching implementation itself — RKIT-I-0005 and RKIT-I-0007 own career-store.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: Dual dispatch removed — the adapter calls only `searchFacts`/`getFact`/`upsertFact`/`verifyFact`/`addEvidence`/`addRelationship`/`findCandidateMatches` per `store_surface.json` (RKIT-A-0002 item 4, RKIT-A-0006 item 9); the snake_case preference sites (`career_mcp/__init__.py:62,82,103,118,126,137,152,163`) are deleted.
- R2: Contract tests are rewritten against the real store surface; any remaining fake must be a verified fake whose conformance to `store_surface.json` is itself asserted. Protected-test edits are authorized by RKIT-A-0006; assertion strength must be preserved or increased.
- R3: `career.find_matches` returns one classification per requirement (fixes the merge at `:156-159`) with `resolution_state` drawn only from the canonical section 4.4 set; `conflicted` never leaks — conflicting evidence surfaces as conflict records per RKIT-A-0006 item 2.
- R4: `career.get_unverified` returns unresolved, inferred, and unknown facts (fixes `:167-176`; vision section 7 line 524; TEST_SPEC "unresolved, inferred, or unknown facts").
- R5: `types` and `verification` filters demonstrably filter against the real store (building on RKIT-I-0010's full-list mapping): a search filtered to `types=['experience']` never returns a `skill` fact.
- R6: After the store restoration lands, the manifest re-advertises `imported` and `parent`/`child`, and a parity test asserts manifest enums == canonical sets == store-accepted values.

### Dependencies
- RKIT-I-0005 and RKIT-I-0007 (career-store enum realignment and relationship/matching restoration must exist before MCP can align to them).
- RKIT-A-0002 and RKIT-A-0006 are decided — direction inputs, not blockers.

### Blocked Status
- Yes (blocked_by: ["RKIT-I-0005", "RKIT-I-0007"]).

## Detailed Design **[REQUIRED]**

**Single-dialect adapter.** A per-tool mapping table routes each `career.*` tool to its declared store function. DTO conversion at the boundary is shape-only (key naming, sensitive-field stripping); vocabulary passes through untranslated because store and MCP share the canonical enums once RKIT-I-0005/0007 land. No translation shim, by design — translation would hide drift, which is precisely what RKIT-A-0006 forbids.

**find_matches result shape.** One row per requirement: `{requirement_id, resolution_state, fact_ids, reasoning}` constructed from `findCandidateMatches` output without the matches+unresolved concatenation; weak states (`possible_match`, `unknown`) appear once, retaining their candidate `fact_ids` instead of the current second empty-handed row with "No confirmed career fact matched" reasoning.

**get_unverified breadth.** Query the declared surface for facts with `verification_state` in `{unknown, inferred}` plus unresolved proposals; coordinate with RKIT-I-0005 if the declared surface needs a listing/filter capability to express this without SQL.

**Test architecture.** Two tiers: (a) real-store contract tests over a temp SQLite store built via the public store API — the authoritative tier; (b) optionally a verified fake whose method signatures and vocabulary are asserted against `store_surface.json` in a conformance test, so the fake can never again drift into a private dialect.

**Migration note.** The rewrite deletes production dual-dispatch branches, so RKIT-I-0010's envelope and filter fixes must be merged or rebased onto the single-dialect path; both initiatives touch `call_tool` dispatch and should coordinate at decomposition time.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- A named regression test per empirical failure: `imported` accepted end-to-end; `parent`/`child` accepted post-restoration; multi-type filter excludes non-matching facts; inferred facts present in `get_unverified`; `find_matches` emits unique requirement rows; no response ever contains a non-canonical state.
- The fake-conformance test (tier b) and the three-way enum parity test (manifest / canonical contract / store-accepted).
- TEST_SPEC strengthening for this scope: TEST_SPEC.md:51 ("Reject invalid verification states") must be tested against the real store and acknowledge the canonical enum — today it silently coexists with a store that rejects advertised states; and the spec language for the Job A→B matching cases (TEST_SPEC.md:89-93) must require a real store, since the current wording is satisfiable by the hardcoded fake dict (`tests/contract/test_career_mcp_contract.py:139-158`). Fixture delivery for those cases is RKIT-I-0015's scope; the spec-language fix that forbids fake-only satisfaction lands here.

## Alternatives Considered **[REQUIRED]**

- **Keep the fake and add real-store tests alongside.** Rejected: the dual dispatch would remain in production code and the private dialect would remain a second de-facto contract that drifts again; RKIT-A-0002 explicitly rejected retaining the snake_case dialect.
- **Translate enums in the adapter (map `imported` → `source_stated`, `child` → `related`, etc.).** Rejected: it hides drift instead of fixing it, violates RKIT-A-0006's documented-contracts-win decision, and misrepresents user data — an imported fact is not source-stated.
- **Rewrite tests against a verified fake only, no real-store runs.** Rejected: fake fidelity is exactly the failure class being repaired; only empirical real-store execution proves the advertised surface works.

## Implementation Plan **[REQUIRED]**

1. Delete the snake_case dispatch; route every tool through the declared camelCase surface.
2. Rewrite the contract tests: real-store tier plus verified-fake conformance test.
3. Fix `find_matches` row coherence and `get_unverified` breadth.
4. Make `types`/`verification` filtering real against the store (with RKIT-I-0010's list mapping).
5. Re-advertise `imported`/`parent`/`child` and add the three-way enum parity test once RKIT-I-0005/0007 land.
6. Strengthen the TEST_SPEC language (real-store requirement, canonical enum acknowledgment); run the canonical package gate.