---
id: 001-documented-contract-semantics-are
level: adr
title: "Documented Contract Semantics Are Authoritative Over Implementation Drift"
number: 1
short_code: "RKIT-A-0006"
created_at: 2026-08-13T21:39:34.320329+00:00
updated_at: 2026-08-13T21:40:50.842444+00:00
decision_date: 2026-08-13
decision_maker: Daniel Cassil
parent: 
archived: false

tags:
  - "#adr"
  - "#phase/decided"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# ADR-1: Documented Contract Semantics Are Authoritative Over Implementation Drift

## Context **[REQUIRED]**

The 2026-08-12/13 implementation waves shipped enum, DTO, and configuration semantics that drifted from the documented contracts in `PRODUCT_VISION_AND_CONTRACTS.md` (sections 4.2–4.6, 6, 9, 13). The drift is not merely latent: `tests/contract/test_shared_dto_schemas_contract.py` hard-asserts the drifted enum sets, package surface manifests codify them, and `IMPLEMENTATION_PLAN.md` forbids editing protected tests and manifests without express user permission — so the accidental drift is locked in by the very gates meant to protect the contracts, and no prior document decides which side wins.

Confirmed drift inventory (from the 2026-08-13 alignment audit, all verified against code):
- `VerificationState` drops contract-valid `imported` and adds `explicitly_missing`/`conflicted` (resume-core schemas, career-store, career-mcp manifests).
- `ResolutionState` drops `not_applicable` and adds `conflicted`.
- `ResumeChangeOperation` lacks the mandatory `reason` and `provenance` fields, the verbs `rewrite`/`insert`/`move`, and the statuses `accepted`/`modified`.
- `MatchResult` lacks `threshold`, `hardRequirementsResolved`, `dimensions`, and the tri-state `decision`.
- Relationship types drop `parent`/`child` and add `contradicts` (section 6 lists its set as "initially", i.e. extensible).
- The section 13 configuration vocabulary (`matching.scoreAutoThreshold`, `matching.weights`, `matching.requireHardRequirementsResolved`, `resume.*`, `guardrails.*`) is ignored in favor of undocumented ad-hoc flat keys (`policy`, `require_hard_resolution`, `allow_inferred_facts`, `max_skills`); verified empirically that `requireHardRequirementsResolved: true` does not gate continuation.
- `required_reduction` in render overflow constraints is a page-count delta, while the section 9 contract example (`requiredReduction: 480`) implies a fine-grained quantity actionable by selection/rewrite.
- Impossible dates produce warnings instead of the rejection resume-core's TEST_SPEC requires.
- career-mcp calls a private snake_case store interface that no declared surface defines (only the test fake implements it), and two divergent copies of `tool_surface.json` exist.

## Decision **[REQUIRED]**

**The documented contracts win.** Where shipped code, tests, or manifests conflict with `PRODUCT_VISION_AND_CONTRACTS.md` / `CONTRACT_SURFACE_ALIGNMENT.md`, the implementation, tests, and manifests are realigned to the documented contract — not the reverse. Specifically:

1. **VerificationState** returns to the section 4.6 five-state set: `source_stated`, `user_verified`, `imported`, `inferred`, `unknown`. `explicitly_missing` and `conflicted` cease to be verification states: explicit absence is modeled in requirement resolution, and conflicting evidence surfaces as conflict records, not as a fact's verification state.
2. **ResolutionState** returns to the section 4.4 set including `not_applicable`. `conflicted` is not a resolution state; a requirement with conflicting evidence resolves as `possible_match` or `unknown` with an associated conflict record until adjudicated.
3. **ResumeChangeOperation** gains the section 4.5 shape: verbs `replace`/`rewrite`/`insert`/`remove`/`move`; statuses `proposed`/`validated`/`rejected`/`applied`/`accepted`/`modified`; mandatory `reason`, `requirementIds`, `factIds`, and `provenance` (`ProvenanceRef[]`), enforced by `validateChange`.
4. **MatchResult** gains the section 4.3 fields: `threshold`, `hardRequirementsResolved`, `dimensions` (weighted `MatchDimension` breakdown), and the tri-state `decision` (`continue`/`resolve_gaps`/`blocked`).
5. **Relationship types** restore `parent`/`child`. `contradicts` is retained as a documented extension (section 6 declares its list non-exhaustive); this ADR is the record of that extension.
6. **Section 13 configuration vocabulary is the config contract.** All documented keys are wired to behavior; the ad-hoc flat keys are removed after migration. Unknown config keys fail validation rather than being silently ignored.
7. **`required_reduction` is a fine-grained character-count quantity** per the section 9 contract example, not a page delta.
8. **Impossible dates are rejected** with typed validation errors; ambiguous-but-possible formats normalize with warnings.
9. **Surface authority:** career-store's camelCase `store_surface.json` is the only store interface consumers may call; career-mcp's private snake_case dialect is removed; the package copy of `tool_surface.json` is the single canonical manifest.

**Authorization:** Daniel Cassil grants express permission (2026-08-13) to edit protected contract tests, boundary tests, and surface manifests **solely to realign them to the documented contracts above**. Every realignment must strengthen or preserve assertion strength — never weaken it — and fixture truth content is unchanged. All other protections in `IMPLEMENTATION_PLAN.md` remain fully in force.

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Outcome |
|--------|------|------|---------|
| Restore documented contract semantics | Recovers `imported` (needed for external-source facts) and `not_applicable`; separates verification from resolution concerns; ops carry auditable reason/provenance; config behaves as documented | Largest code/test/manifest churn across four packages | **Chosen** (ratified by Daniel Cassil, 2026-08-13) |
| Bless the implemented semantics (amend the contract docs) | Least code churn | Permanently drops `imported`; codifies the verification/resolution conflation; ops stay without reason/provenance; documents an accident as design | Rejected |
| Hybrid: contract plus documented extensions | Keeps useful additions | Adopted only where the contract is explicitly extensible (`contradicts` relationship type); rejected for verification/resolution enums, where the conflation is precisely the harm | Partially adopted |

## Rationale **[REQUIRED]**

The drifted semantics were produced by implementation convenience during the 2026-08-12/13 waves, not by design review — and the contract tests then hardened the accident into a gate. The documented contracts are the reviewed product design: `imported` supports the fact-import path the product plans, `not_applicable` is needed for honest requirement reporting, mandatory `reason`/`provenance` on operations is what makes the Honesty and Audit Gates enforceable rather than aspirational, and section 13 config keys are the only documented way users control matching and structure. Where the contract explicitly allows extension (section 6's "initially" relationship list), the useful addition is kept and recorded here instead of silently shipped.

## Consequences **[REQUIRED]**

### Positive
- The enum/DTO/config questions blocking clean decomposition of the resume-core, career-store, and career-mcp initiative groups are decided; RKIT-A-0002's vocabulary question resolves by reference to this ADR.
- The Honesty, Persistence, and Audit Gates gain the substrate they assume (operation reason/provenance, `imported`, honest resolution states, enforced config).
- The test-fidelity failure class demonstrated by the audit (contract tests certifying drifted or imaginary interfaces) gets a decided correction path.

### Negative
- Coordinated churn across resume-core schemas/domain, career-store, career-mcp, resume-agent operation DTOs, plugin surface, the shared-DTO contract test, and multiple surface manifests.
- Migration handling for any persisted data using the drifted vocabulary (career DBs created during the implementation waves).

### Neutral
- The affected initiatives must fold this realignment into their scope during the planned re-baseline pass; the drift inventory in the Context section is the checklist.
- Future intentional contract extensions follow the same rule this ADR applies to `contradicts`: recorded in an ADR before shipping, never silently.

## Scope Note

This ADR authorizes protected-surface edits only for realignment to the documented contracts listed above. It does not authorize weakening any assertion, changing fixture truth, or altering guardrail policy for any other purpose.