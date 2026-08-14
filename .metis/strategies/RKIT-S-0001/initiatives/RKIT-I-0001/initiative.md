---
id: resume-core-canonical-contracts
level: initiative
title: "Resume-Core Canonical Contracts, Validation, And Normalization"
short_code: "RKIT-I-0001"
created_at: 2026-08-13T20:41:36.829485+00:00
updated_at: 2026-08-14T03:08:26.349769+00:00
parent: RKIT-S-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/decompose"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-core-canonical-contracts
---

# Resume-Core Canonical Contracts, Validation, And Normalization Initiative

## Context **[REQUIRED]**

Package: `resume-core`, owner of canonical DTOs, enums, schema validation, ATS sanitation, date normalization, and normalization per CONTRACT_SURFACE_ALIGNMENT.md. The 2026-08-12/13 implementation waves left this area at roughly 40% contract completeness; the sections below are grounded in the 2026-08-13 alignment audit, which verified every claim against code.

Genuinely implemented: `sanitizeText` is real and deterministic (domain.py:145-168); the 11-function public surface exists with clean stdlib-only dependency hygiene; IDs are stable.

Fixture-tuned or stub: `normalizeResume` is string cleaning plus default backfilling that assumes near-canonical input (domain.py:171-211) and attaches no claim-level provenance; the exported JSON schema constants (`SCHEMAS`, `CANONICAL_RESUME_SCHEMA`) are never used for validation, and `validateResume` checks fewer required fields than the schema declares — no `resume_id`, no `source` (schemas.py:230-245 vs domain.py:223-226); dates get regex validation only — "Jan 2019"/"01/2019" merely warn "ambiguous" and impossible dates like 2019-13 warn instead of rejecting (domain.py:698-720, verified empirically).

Missing or drifted against the section 4 contracts: `VerificationState` rejects contract-valid `imported` at `validateResume` (domain.py:230-233) while domain.py:30 compensates by hacking the raw string into `_VERIFIED_FACT_STATES`, and it adds `explicitly_missing`/`conflicted` (schemas.py:32-38); `ResolutionState` omits `not_applicable` and adds `conflicted` (schemas.py:41-49); `ResumeChangeOperation` lacks the `rewrite`/`insert`/`move` verbs, the `accepted`/`modified` statuses, and the mandatory `reason`/`provenance` fields (schemas.py:58-62, 166-179; domain.py:463-465); `JobModel` lacks seniority, industries, domains, a separate preferred array, and any terminology/JobTerm substrate at all (schemas.py:126-133, domain.py:266-276). tests/contract/test_shared_dto_schemas_contract.py:45-62 hard-asserts the drifted enum sets inside the passing PR gate, institutionalizing the drift. RKIT-A-0006 (decided 2026-08-13) rules that the documented contracts win and grants express authorization to realign the protected contract tests and manifests.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Restore the section 4.2/4.4/4.5/4.6 DTO and enum shapes per RKIT-A-0006 items 1-3: five-state `VerificationState` including `imported`; `ResolutionState` including `not_applicable`; `ResumeChangeOperation` with verbs `replace`/`rewrite`/`insert`/`remove`/`move`, statuses `proposed`/`validated`/`rejected`/`applied`/`accepted`/`modified`, and mandatory `reason`, `requirementIds`, `factIds`, `provenance`.
- Complete `JobModel` per section 4.2: `seniority`, `industries`, `domains`, a `preferred` array separate from `required`, and the terminology/`JobTerm` substrate that RKIT-I-0002's terminology scoring dimension will consume.
- Make validation schema-backed: `validateResume`/`validateJob` actually validate against the exported JSON schema constants.
- Ship date normalization that canonicalizes ambiguous formats and REJECTS impossible dates and reversed ranges with typed errors (RKIT-A-0006 item 8).
- Weave claim-level `ResumeField` provenance/verification through `normalizeResume` so RKIT-I-0004 can ground claims individually.

**Non-Goals:**
- No scoring or resolution behavior changes (RKIT-I-0002) and no selection-planning constraints (RKIT-I-0003).
- No lifecycle/honesty enforcement of the new operation fields — this initiative defines and structurally validates the DTO shape; RKIT-I-0004 enforces the semantics.
- No migration of drifted vocabulary in persisted career DBs (career-store initiative group scope).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. `VerificationState` is exactly {`source_stated`, `user_verified`, `imported`, `inferred`, `unknown`} (section 4.6, A-0006 item 1). `validateResume` accepts `imported` (fixes domain.py:230-233); the raw-string compensation at domain.py:30 is removed; `explicitly_missing`/`conflicted` cease to be verification states — explicit absence moves to requirement resolution and conflicting evidence becomes conflict records.
2. `ResolutionState` gains `not_applicable` and drops `conflicted` (section 4.4, A-0006 item 2; schemas.py:41-49).
3. `ResumeChangeOperation` gains mandatory `reason`, `requirementIds`, `factIds`, `provenance` (ProvenanceRef list), the verbs `replace`/`rewrite`/`insert`/`remove`/`move`, and statuses including `accepted`/`modified` (section 4.5, A-0006 item 3; schemas.py:58-62, 166-179, domain.py:463-465). Structural field validation lands here; semantic lifecycle enforcement is RKIT-I-0004.
4. `JobModel` carries `seniority`, `industries`, `domains`, a separate `preferred` array, and `terminology: JobTerm[]`; `parseJobDescription` populates them deterministically (section 4.2; schemas.py:126-133, domain.py:266-276).
5. `validateResume`/`validateJob` validate against the exported schema constants so the checked required fields (including `resume_id` and `source`) match what `CANONICAL_RESUME_SCHEMA` declares (schemas.py:230-245 vs domain.py:223-226).
6. Date normalization canonicalizes `YYYY`, `YYYY-MM`, `Mon YYYY`, and `MM/YYYY` into stable `YYYY[-MM]`, and rejects impossible dates (2019-13) and reversed ranges with typed errors, replacing the warn-only path (domain.py:698-720; TEST_SPEC.md:70-71; A-0006 item 8).
7. `normalizeResume` attaches `ResumeField` provenance/verification to meaningful claims and handles non-canonical parsed shapes, not just near-canonical input (domain.py:171-211).
8. tests/contract/test_shared_dto_schemas_contract.py:45-62 is realigned to assert the contract enum sets under the A-0006 authorization, with assertion strength preserved or increased and fixture truth content unchanged.

### Dependencies
- RKIT-A-0006 (decided 2026-08-13) — supplies the enum/DTO rulings, the date-strictness decision, and the express authorization to edit protected contract tests and manifests for realignment.

### Blocked Status
- Not blocked (`blocked_by: []`). All governing ADRs are decided. This initiative is the root of the resume-core chain; RKIT-I-0002, RKIT-I-0003, and RKIT-I-0004 depend on its DTOs and substrate.

## Detailed Design **[REQUIRED]**

**Enum and DTO layer.** Enums move to the exact contract sets. Concepts the drifted enums conflated are relocated, not dropped: explicit absence is expressed as `ResolutionState.explicitly_missing` on requirement resolution, and conflicting evidence becomes a conflict record attached to the resolution row. Migration note: `_fact_resolution` currently reads a fact's `verification_state == 'explicitly_missing'` to drive a ResolutionState (domain.py:1020-1022); that signal becomes an explicit resolution input so no fact ever carries a resolution concept.

**Schema-backed validation.** The exported schema constants become the single structural source of truth. A small stdlib walker validates required fields, types, and enum membership directly against `CANONICAL_RESUME_SCHEMA`/`SCHEMAS`; domain checks (provenance shape, required arrays, ID stability) layer on top. Divergence between constants and validator behavior becomes impossible by construction because the validator reads the constants.

**Date normalization.** A deterministic parser produces canonical `YYYY[-MM]` values plus a typed result: normalized (with a warning when the source format was ambiguous but possible), `invalid_date` for impossible calendar values, `reversed_range` for end-before-start. Rejection is a validation error, not a warning (A-0006 item 8).

**JobTerm substrate.** `JobTerm` captures {`surface` (the job's literal wording), `canonical` (normalized form), `source` (title/requirement/description), `weight` hint}. `parseJobDescription` extracts terminology deterministically from job text. This initiative delivers data shape and population only — scoring over it is RKIT-I-0002.

**Claim-level provenance weaving.** `normalizeResume` wraps meaningful claims (skills, titles, dates, experience bullets) as `ResumeField` values carrying `provenance: ProvenanceRef[]` and a `VerificationState`. Claims with no source mapping get empty provenance plus `unknown` — never a silent `source_stated` — giving RKIT-I-0004 the per-claim grounding substrate the section 4.1 ResumeField key invariant requires.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Realign and strengthen tests/contract/test_shared_dto_schemas_contract.py:45-62 to hard-assert the section 4.4/4.6 enum sets, removing the institutionalized drift the audit flagged.
- Populate the empty tests/unit for this scope's TEST_SPEC "Unit Test Cases": enum accept/reject tables (including empirical `validateResume` acceptance of `imported`), schema-constant-driven validation cases, and the full date table — making TEST_SPEC.md:70-71 "Reject impossible dates and reversed ranges" executable for the first time.
- Strengthen TEST_SPEC.md itself: enumerate the exact `VerificationState`/`ResolutionState` state sets (TEST_SPEC.md:11-17 names the surfaces without enumerating states — the silence that let the gate codify drift), and convert "Attach provenance to meaningful claims" into an assertable normalization case.
- Keep boundary guardrails green; no fixture truth content changes (A-0006 scope note).

## Alternatives Considered **[REQUIRED]**

- **Bless the implemented enums by amending the contract docs.** Rejected by RKIT-A-0006: it permanently drops `imported`, codifies the verification/resolution conflation, and documents an accident as design.
- **Adopt a jsonschema library for schema-backed validation.** Rejected: resume-core's stdlib-only dependency hygiene is one of its audit-verified strengths; a hand-rolled deterministic walker over the exported constants keeps zero dependencies and identical behavior in every environment.
- **Keep warn-only date handling and let downstream consumers pick strictness.** Rejected: TEST_SPEC.md:70 and A-0006 item 8 both require rejection with typed errors; warn-only provably lets impossible dates flow into scoring and rendering.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (dependency-ordered chunks; actual Metis task decomposition happens later):
1. Enum/DTO restoration plus shared-DTO contract-test realignment (A-0006 items 1-3) — everything downstream builds on the restored shapes.
2. Schema-backed `validateResume`/`validateJob` against the exported constants.
3. Date normalization with typed rejection.
4. `JobModel` section 4.2 completion including the `JobTerm` substrate and `parseJobDescription` population.
5. Claim-level `ResumeField` provenance weaving through `normalizeResume`.
6. TEST_SPEC unit suites for this scope plus the spec-strengthening edits.

## Design Review & Approved Decisions (2026-08-13)

Design review completed 2026-08-13 via a 5-agent verification workflow, code-grounded against `develop @ 4156687`. Daniel approved the decomposition and the decisions below.

**Verification correction to the Context/Requirements framing.** `explicitly_missing` and `conflicted` are ALREADY enum members on both `VerificationState` (schemas.py:32-38) and `ResolutionState` (schemas.py:41-49) — they are not "drift to add." The RKIT-A-0006 restoration is: VerificationState → exactly {`source_stated`, `user_verified`, `imported`, `inferred`, `unknown`} (ADD `imported`, REMOVE `explicitly_missing` + `conflicted`); ResolutionState → exactly {`exact_match`, `alias_match`, `verified_fact_match`, `related_match`, `possible_match`, `unknown`, `explicitly_missing`, `not_applicable`} (ADD `not_applicable`, REMOVE `conflicted`, KEEP `explicitly_missing`). **Cross-package hazard (previously unaccounted):** `career_store.VerificationState` IS `resume_core.VerificationState` (single shared object, pinned by test_shared_dto_schemas_contract.py:78); career-store `matching.py`/`store.py` read `.CONFLICTED`/`.EXPLICITLY_MISSING` as load-bearing enum attributes and drive real conflict resolution (store.py:1166-1169). The enum edit therefore breaks career-store at import time unless its readers migrate in the SAME task — the root task is cross-package by necessity, not a resume-core-only change. Also corrected: impossible-month rejection (2019-13) is NEW behavior (today silently coerced to None, then surfaced only as a generic ambiguous warning), not a tightening of an existing reject; and there is no `reason` field on ResumeChangeOperation today (must be ADDED, not merely made mandatory). MatchResult §4.3 is explicitly OUT of scope here (owned by RKIT-I-0002) despite A-0006 item 4 listing it.

**Approved decisions:**
1. **Conflict representation:** Introduce a first-class conflict-record path in career-store; migrate `matching.py`/`store.py` to emit conflict records instead of the removed enum member. Preserves current conflict-detection behavior with correct contracts. The root enum task owns this lockstep migration.
2. **Claim-level provenance weaving:** Ships in THIS initiative. `normalizeResume` emits honest per-claim `ResumeField` (empty provenance + `unknown` for sourceless claims — NEVER silent `source_stated`); semantic enforcement stays in RKIT-I-0004.
3. **Field naming:** Preserve existing snake_case (`linked_requirement_ids`, `linked_fact_ids`); the contract doc's camelCase is notation, not a wire-format change.
4. **validateResume:** Enforce the full `CANONICAL_RESUME_SCHEMA.required` set (adds `resume_id`, `source`) via a hand-rolled stdlib walker over the exported constants — no jsonschema dependency.
5. **Dates:** Reject impossible months and reversed ranges with typed errors (`invalid_date` / `reversed_range`); ambiguous-but-possible formats normalize with a warning.

**Decomposition:** 8 tasks (see child tasks). Root task = enum restoration + cross-package reader/conflict-record migration + shared-DTO contract-test realignment under A-0006 (opus + high); everything else in the resume-core chain (RKIT-I-0002/0003/0004) depends on it.