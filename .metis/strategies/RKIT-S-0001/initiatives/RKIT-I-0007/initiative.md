---
id: relationship-aware-matching-and
level: initiative
title: "Relationship-Aware Matching and Cross-Job Reuse"
short_code: "RKIT-I-0007"
created_at: 2026-08-13T20:41:36.962447+00:00
updated_at: 2026-08-15T01:23:23.228989+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0006]
archived: false

tags:
  - "#initiative"
  - "#phase/decompose"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: relationship-aware-matching-and
---

# Relationship-Aware Matching and Cross-Job Reuse Initiative

## Context **[REQUIRED]**

Package: `career-store`. Matching and cross-job persistence already exist: findCandidateMatches, recordJobMatch, and per-job requirement-to-fact persistence with deterministic ordering (store.py:539-586, 948). This initiative is rework of a misaligned layer, not new construction.

Audit-verified defects (2026-08-13):
- CRITICAL related-term pollution — the alignment doc's own named misalignment example. `_fact_match_terms` folds relationship-linked facts' terms into a fact's direct term set (store.py:975 via `_relationship_terms`, store.py:812-820), so after a merely "related" Azure→AWS relationship the Azure fact resolves an AWS requirement as exact_match even with allow_related_as_equivalent=False, and the requirement is not listed unresolved (verified empirically). Violates the ResolutionState invariant (CONTRACT_SURFACE_ALIGNMENT.md:186-188), the Honesty Gate (:329), and TEST_SPEC:78.
- The contract test that should catch it is vacuous: tests/contract/test_career_store_contract.py:180-182 asserts only the absence of the literal string "equivalent_match" — a label no code path produces — while in that exact scenario the store returns exact_match.
- A compiled-in English alias dictionary `_TERM_ALIASES`/`_AWS_SERVICE_TERMS` (store.py:103-140), tuned to fixture vocabulary, silently makes a "system design" requirement resolve an "API architecture" fact as exact_match with no stored relationship and no confirmation (verified empirically). Vision section 12 assigns alias lookup to deterministic code over stored relationships; the dictionary bypasses the relationship store, confirmation policy, and audit.
- Agent-created alias/equivalent relationships are fully trusted: addRelationship stores unconditionally (store.py:399-437), `requires_confirmation_for_equivalence` only echoes a flag in the response (store.py:448), and matching grants alias_match with no confirmation check (store.py:996-1003) — TEST_SPEC:76 and the vision guardrail allowUnverifiedAliasCreation:false (PRODUCT_VISION_AND_CONTRACTS.md:874) have no enforcement substrate.
- parent/child relationship types are unsupported (store.py:25); RKIT-A-0006 item 5 restores them and records `contradicts` as a documented extension.
- searchFacts filters only verification_state (store.py:178); TEST_SPEC:83-84 expects concept/terms/alias search and minimum-necessary evidence (include_evidence currently returns all rows).

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Match results carry honest, relationship-typed provenance: exact only from a fact's own terms; alias/equivalent only through confirmed stored relationships; related never masquerades as exact.
- Alias lookup runs over stored relationships exclusively; the compiled-in dictionary is deleted.
- Relationships carry stored confirmation status, and matching enforces allowUnverifiedAliasCreation:false.
- parent/child matching semantics restored; contradicts handled as the A-0006-documented extension feeding conflict signals.
- searchFacts supports concept/terms/alias filtering with minimum-necessary evidence.
- The vacuous Azure contract test is replaced with outcome assertions.

**Non-Goals:**
- Numeric scoring and requirement-resolution decisions — Must-Not-Own for career-store (CONTRACT_SURFACE_ALIGNMENT.md:37); the store reports typed candidates, resume-core scores and resolves. (matching.py, which contained scoring, is removed by RKIT-I-0005.)
- Verification transition gating — RKIT-I-0006; this initiative consumes gated verification states as matching inputs.
- Conflict adjudication workflow — RKIT-I-0008; contradicts relationships only surface signals here.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Fix related-term pollution at its source: `_fact_match_terms` (store.py:975) and `_relationship_terms` (store.py:812-820) no longer fold relationship-linked terms into a fact's direct term set. Direct terms produce exact candidates; relationship traversal produces candidates labeled by the relationship path. With allow_related_as_equivalent=False, a related-only Azure fact yields at most related_match for an AWS requirement and the requirement reports unresolved (TEST_SPEC:78; Honesty Gate).
2. Delete `_TERM_ALIASES` and `_AWS_SERVICE_TERMS` (store.py:103-140). Alias lookup is deterministic traversal of stored relationships only (section 12). Regression: "system design" no longer resolves "API architecture" as exact_match absent a stored, confirmed relationship.
3. Stored confirmation status on relationships (columns via RKIT-I-0005's migration registry): status unconfirmed/user_confirmed plus provenance and timestamp. addRelationship records agent-created rows as unconfirmed; a confirmRelationship API with user provenance is the only path to user_confirmed. Under allowUnverifiedAliasCreation:false, unconfirmed alias/equivalent relationships contribute at most possible_match — never alias_match or equivalent proof (TEST_SPEC:76; vision :874).
4. parent/child semantics per RKIT-A-0006 item 5: directional candidates labeled with the parent/child path (a child fact supports its parent's requirement as related-strength evidence, never exact); contradicts relationships surface as conflict signals consumed by RKIT-I-0008's workflow.
5. searchFacts accepts concept, normalized terms, alias (via stored relationships), and verification_state filters; include_evidence returns the minimum-necessary evidence rows for the match rather than all rows (TEST_SPEC:83-84).
6. Cross-job reuse preserved: Job B reuses Job A verified facts via recordJobMatch persistence, now populating the match_type/confidence/user_confirmed columns added by RKIT-I-0005.
7. Replace tests/contract/test_career_store_contract.py:180-182 with outcome assertions (see Testing Strategy) under the RKIT-A-0006 authorization — strengthening only.

### Dependencies
- RKIT-I-0006: gated verification states as matching inputs; verified_fact_match paths must reflect a trustworthy user_verified.
- RKIT-I-0005 (transitive): relationship-type enum restoration, confirmation/confidence columns, migration registry.
- RKIT-A-0006 item 5 (decided): relationship type set and the contradicts extension.

### Blocked Status
- Blocked by RKIT-I-0006. No ADR blocks; RKIT-A-0006 is decided and referenced above.

## Detailed Design **[REQUIRED]**

- Candidate DTO: `{factId, matchType: exact_match|verified_fact_match|alias_match|related_match|possible_match, viaRelationships: [{relationshipId, type, confirmationStatus}], terms}` — every non-exact candidate names the relationship chain that produced it, making the honesty rule mechanically checkable at the store boundary.
- Enforcement point: matching computes direct-term candidates first, then performs bounded relationship traversal (depth 1 initially) emitting typed candidates; a single policy function maps (relationship type, confirmation status, config) → permitted matchType, so allowUnverifiedAliasCreation and allow_related_as_equivalent are enforced in one place instead of scattered conditionals.
- Confirmation substrate: `fact_relationships` gains confirmation_status, confirmed_by_provenance, confirmed_at (migration through the RKIT-I-0005 registry); confirmRelationship validates user provenance and is idempotent.
- Unresolved reporting: when no permitted candidate reaches proof strength, the requirement reports unresolved/possible per the section 4.4 ResolutionState set (with not_applicable restored by RKIT-I-0005) — never silently satisfied.
- searchFacts: SQL-side filtering on concept/terms columns plus alias expansion via one relationship join; evidence minimization returns only rows referenced by the matched terms.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Strengthened Azure/AWS contract test (replacing the vacuous :180-182 string-absence assertion): with a related Azure→AWS relationship and allow_related_as_equivalent=False, assert the Azure candidate's matchType is at most related_match, the AWS requirement is reported unresolved, and no exact_match/alias_match appears — asserting outcomes the code actually produces, per CONTRACT_SURFACE_ALIGNMENT.md:310.
- Unconfirmed-alias enforcement: an agent-added alias yields no alias_match until confirmRelationship with user provenance; after confirmation it does.
- Dictionary-removal regressions: the fixture pairs previously satisfied by `_TERM_ALIASES` (aws/graphql/node/postgres, "system design"→"API architecture") no longer match without stored relationships.
- parent/child and contradicts tests: directional labeling; contradicts emits a conflict signal, never a match.
- searchFacts tests: concept/terms/alias filters and minimum-necessary evidence row counts.
- TEST_SPEC strengthening: realign TEST_SPEC:75-79 to the restored relationship set (with the A-0006-recorded contradicts extension); align the :87 match-type list with section 4.4 including not_applicable; replace string-absence framing with outcome-based cases for the related-pollution scenario and confirmation policy — the current framing is what certified the vacuous test.

## Alternatives Considered **[REQUIRED]**

- Ship a built-in seed alias dictionary alongside stored relationships: rejected — compiled-in equivalence bypasses confirmation and audit; if bootstrap vocabulary is ever wanted it ships as pre-confirmed relationship data rows, not code.
- Enforce confirmation purely via config echo (status quo): rejected — nothing persists which relationships were confirmed, so enforcement cannot survive sessions and the guardrail remains a response-payload decoration (store.py:448).
- Fold scoring into career-store so it can decide resolution locally: rejected — scoring/resolution is Must-Not-Own (:37); emitting typed candidates and letting resume-core decide also keeps the honesty rule testable at the store boundary.

## Implementation Plan **[REQUIRED]**

Dependency-ordered chunks for later decomposition (no Metis tasks yet):
1. Rewrite `_fact_match_terms`/`_relationship_terms` into direct-vs-traversal candidate generation with typed provenance (fixes the pollution).
2. Delete `_TERM_ALIASES`/`_AWS_SERVICE_TERMS`; stored-relationship alias lookup.
3. Relationship confirmation substrate + confirmRelationship + the single policy function enforcing allowUnverifiedAliasCreation / allow_related_as_equivalent.
4. parent/child + contradicts semantics.
5. searchFacts filtering + evidence minimization.
6. Contract/TEST_SPEC strengthening pass, including the Azure test replacement.