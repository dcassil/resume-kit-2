---
id: resume-core-deterministic
level: initiative
title: "Resume-Core Deterministic Requirement Resolution And Match Scoring"
short_code: "RKIT-I-0002"
created_at: 2026-08-13T20:41:36.852663+00:00
updated_at: 2026-08-14T21:13:22.399262+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0001]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-core-deterministic
---

# Resume-Core Deterministic Requirement Resolution And Match Scoring Initiative

## Context **[REQUIRED]**

Package: `resume-core`. Requirement resolution and match scoring. Genuinely implemented after the 2026-08-12/13 waves: the resolution ladder (exact → alias → verified_fact → related → possible → unknown), deterministic sorted scoring with stable sha256 IDs, and hard-requirement blocking are real (domain.py:139-142, 279-351). Both of this initiative's previous System Requirements (related/possible never resolve hard requirements; repeated scoring is deterministic) were already satisfied by that shipped code — as written the initiative was exit-criteria-complete on day one while omitting every actual gap in its area. Those requirements are replaced below with the real gaps.

What is missing or fixture-tuned: `MatchResult` ships only a binary `can_continue` plus per-requirement rows — no `threshold`, no `hardRequirementsResolved` flag, no `dimensions`/`MatchDimension` weighted breakdown, no tri-state `decision` (schemas.py:148-162, domain.py:336-350) — so section 5's "explainable score breakdowns" responsibility has no shape to live in. The section 13 `matching.*` config contract is entirely unwired: `requireHardRequirementsResolved: true` verifiably does not gate continuation, and the code reads ad-hoc flat keys (`policy`, `require_hard_resolution`) instead (domain.py:1092-1093, 795). `_default_weight` hardcodes 10/3/2/1 although section 12 makes config authoritative for requirement weighting (domain.py:853-858). There is no terminology scoring dimension and, until RKIT-I-0001 lands JobTerm, no substrate for one. Alias and related matching only work for the closed fixture vocabularies `_TERM_VARIANTS`/`_RELATED_REQUIREMENT_TERMS`/`_GENERIC_TERMS` (react/aws/graphql/responsive design/saas/leadership; domain.py:96-142), and `_infer_classification` marks requirements "required" off the literal substring "8+" tuned to the E2E fixture — a "5+ years" requirement is not inferred required (domain.py:840). The TEST_SPEC.md:106-required base-score snapshots do not exist: tests/snapshots is empty and the smoke harness asserts only score monotonicity (tools/run_smoke.py:178,216).

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

**COMPLETED 2026-08-14** — all six chunks (RKIT-T-0023..0028) codex-implemented, driver-reviewed, committed on develop. Delivered: validated `matching.*` config (flat keys removed, typed rejection); MatchResult 4.3 complete (threshold/hardRequirementsResolved/tri-state decision — the requireHardRequirementsResolved gating defect is fixed and behaviorally probed); MatchDimension weighted breakdown with config-sourced weights; TermRelationship-driven resolution (Azure≠AWS invariant guarded, closed vocabularies demoted to seeds); live terminology dimension over JobTerm; base-score snapshots enforced via the I-0051 substrate; specs strengthened. All gates green (--pr 257, --future-contract 264, --smoke). OUTSTANDING (non-blocking): 6 new tests/unit modules (~33 tests) run standalone but are not yet in protected run_tests.py CURRENT_TEST_MODULES — accumulated for the next straight-jacket password session with Daniel.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Complete `MatchResult` per section 4.3 and RKIT-A-0006 item 4: `threshold`, `hardRequirementsResolved`, `dimensions` as a weighted `MatchDimension` breakdown, and the tri-state `decision` (`continue`/`resolve_gaps`/`blocked`).
- Wire the section 13 `matching.*` config keys per A-0006 item 6 — `scoreAutoThreshold`, `weights` (requiredSkills, experience, roleAlignment, domainIndustry, preferredSkills, terminology), `requireHardRequirementsResolved` — replacing the ad-hoc flat keys after migration, with unknown keys failing validation.
- Add the terminology scoring dimension over the `JobTerm` substrate RKIT-I-0001 delivers.
- Generalize alias/related resolution to consume career-store stored relationships supplied as input data, retiring the closed fixture vocabularies as the mechanism.
- Make every score explainable (per-dimension contributions with evidence) and record base-score snapshots per TEST_SPEC.md:106.

**Non-Goals:**
- No DTO/enum restoration — RKIT-I-0001 owns the shapes (including `ResolutionState.not_applicable`) that this initiative populates with behavior.
- No honesty gate, operation lifecycle, or final validation (RKIT-I-0004); no selection planning (RKIT-I-0003).
- No relationship persistence or confirmation UX — career-store owns stored relationships; resume-core receives them as call input, preserving the dependency-direction rule.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. `scoreMatch` returns the complete section 4.3 `MatchResult`: `threshold` (from `matching.scoreAutoThreshold`), `hardRequirementsResolved`, `dimensions: MatchDimension[]` ({name, weight, score, contribution, evidence refs}), and `decision` computed as `blocked` when `matching.requireHardRequirementsResolved` is true and a hard requirement is unresolved, `resolve_gaps` when the score is below threshold, else `continue` (fixes schemas.py:148-162, domain.py:336-350).
2. `matching.requireHardRequirementsResolved: true` actually gates continuation — the empirically verified failure at domain.py:1092-1093 is fixed and covered by a test reproducing the audit's scenario.
3. `matching.weights` drives dimension weighting; the hardcoded 10/3/2/1 `_default_weight` becomes config-sourced defaults per section 12 (domain.py:853-858). Changing a weight changes dimension contributions deterministically.
4. A terminology dimension scores resume surface wording against `JobModel.terminology`, giving the "prefer job terminology" product goal and workflow step E.2 their scoring substrate.
5. Alias and related resolution consult term relationships passed as input (sourced by callers from career-store stored relationships); `_TERM_VARIANTS`/`_RELATED_REQUIREMENT_TERMS`/`_GENERIC_TERMS` (domain.py:96-142) are demoted to seed/fixture data. Resolution keeps the ladder ordering and the "Azure is not proof of AWS" invariant.
6. `_infer_classification` generalizes: any "N+ years" style requirement phrasing marks required, not the literal "8+" (domain.py:840).
7. Regression guards: related/possible matches still never resolve hard requirements by default, and identical inputs still produce equivalent output — the two previously listed requirements remain true as guarded invariants, not as this initiative's scope.
8. Base scores for the smoke and E2E fixtures are recorded as snapshots and asserted (TEST_SPEC.md:106); tests/snapshots ceases to be empty.

### Dependencies
- RKIT-I-0001 — restored enums, the `JobTerm` substrate, and the section 13 config validation layer this initiative's `matching.*` wiring builds on.
- RKIT-A-0006 (decided) — settles the config vocabulary (item 6) and the MatchResult shape (item 4); no open ADR blockers remain.

### Blocked Status
- Blocked by RKIT-I-0001 (frontmatter `blocked_by: ["RKIT-I-0001"]`).

## Detailed Design **[REQUIRED]**

**MatchDimension and composition.** `MatchDimension` = {name (one of the section 13 weight keys), weight, score (0-1), contribution (weight × score), evidence (requirement/fact/term references)}. The overall score is the normalized weighted sum of dimensions; per-requirement resolution rows remain, so a consumer can explain both "why this score" (dimensions) and "why this requirement state" (rows).

**Decision function.** A pure function of (score, threshold, hardRequirementsResolved, config): `blocked` dominates, then `resolve_gaps`, then `continue`. `can_continue` becomes derivable and is retained only during migration.

**Config plumbing.** The `matching.*` namespace is parsed and validated through the shared section 13 config layer (A-0006 item 6): unknown keys are typed validation errors, documented keys default to section 13 values, and the flat keys (`policy`, `require_hard_resolution`) are accepted-with-deprecation for one migration window, then removed.

**Relationship-driven resolution.** A `TermRelationship` input ({from, to, kind: alias/related/parent/child/contradicts, provenance}) supplements the built-in ladder. resume-core never imports career-store (dependency direction); callers (workflow/CLI) fetch stored relationships and pass them in. Input relationships are sorted before application so resolution is stable regardless of supply order.

**Terminology dimension.** For each JobTerm, check whether the resume uses the job's surface form versus only the canonical form; the dimension score is the weighted fraction of job terms mirrored. Evidence records which terms matched in which form, feeding workflow step E.2's terminology-alignment opportunities.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract tests asserting all section 4.3 MatchResult fields exist and `decision` takes exactly the three contract values; an empirical gating test where `matching.requireHardRequirementsResolved: true` plus one unresolved hard requirement yields `decision: 'blocked'` (the audit's reproduced failure).
- Snapshot suite: record and assert base scores for the Job A/Job B smoke and E2E fixtures (TEST_SPEC.md:106 — currently unmet, tests/snapshots empty, only monotonicity asserted at tools/run_smoke.py:178,216).
- Unit cases in the currently empty tests/unit: weight-variation determinism, dimensions summing to the overall score (making "Assert score dimensions add/explain consistently", TEST_SPEC.md:103, enforceable — today it is unenforceable because dimensions do not exist), relationship-driven alias resolution, "5+ years" required inference, and the hard-requirement invariant regression.
- TEST_SPEC strengthening: explicitly require the section 4.3 fields and the section 13 `matching.*` keys — the spec's silence on both is precisely what certified binary `can_continue` with an ad-hoc config vocabulary.

## Alternatives Considered **[REQUIRED]**

- **Document and keep the implemented flat config keys.** Rejected by RKIT-A-0006 item 6: section 13 is the config contract; blessing the flat keys would codify the accident and leave `requireHardRequirementsResolved` semantics undefined.
- **Generalize alias matching with fuzzy string similarity instead of stored relationships.** Rejected: similarity thresholds are tuning-sensitive and truth-hazardous (Azure scoring as AWS evidence violates the resolution key invariant); stored, user-confirmed relationships keep resolution deterministic and auditable.
- **Report terminology alignment as a side report rather than a scoring dimension.** Rejected: section 13's weight vocabulary includes `terminology`, and without score pressure the "prefer job terminology" goal has no mechanism to influence decisions.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (dependency-ordered chunks; actual Metis task decomposition happens later):
1. Section 13 `matching.*` config wiring with validation and flat-key migration.
2. MatchResult 4.3 completion: threshold, hardRequirementsResolved, decision function.
3. Dimensions/MatchDimension weighted breakdown with explainable evidence, replacing the `_default_weight` hardcoding.
4. Relationship-driven alias/related resolution plus `_infer_classification` generalization.
5. Terminology dimension over JobTerm.
6. Base-score snapshot recording plus TEST_SPEC strengthening.