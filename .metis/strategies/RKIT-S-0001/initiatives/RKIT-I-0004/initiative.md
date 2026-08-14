---
id: resume-core-grounded-change
level: initiative
title: "Resume-Core Grounded Change Lifecycle And Final Validation"
short_code: "RKIT-I-0004"
created_at: 2026-08-13T20:41:36.895877+00:00
updated_at: 2026-08-14T23:55:20.697588+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0001, RKIT-I-0002]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-core-grounded-change
---

# Resume-Core Grounded Change Lifecycle And Final Validation Initiative

## Context **[REQUIRED]**

Package: `resume-core`. Change lifecycle and final validation. Substantial lifecycle code genuinely exists: validated-only application, deep-copy immutability, idempotent operation application, safe JSON path handling, and audit records are real. But the two surfaces this initiative owns are respectively broken and gamed:

- `validateFinalResume` hardcodes `applied_operations=[]` when calling grounding (domain.py:611), so a legitimately validated-and-applied AWS addition FAILS final validation — verified empirically. DoD steps 10-14 (grounded tailoring, then final validation pass) are broken through the official surface.
- The honesty gate is a lookup table of exactly the five fixture claims (`_GUARDED_TERMS`: aws, graphql, staff title, "20 million", "30 engineers"; domain.py:47-53, 1103-1105). Verified empirically: "Served 50 million users daily", "Principal Engineer leading 100 people", and "Kubernetes expert" all validate ungrounded.

Further fixture-tuning and gaps: `_title_inflation` guards only the word "staff" — inflation to "Principal Software Engineer" passes (domain.py:1136-1143); years-claim support is exact-phrase matching that rejects a truthful "AWS, six years" against a `user_verified` "6 years of AWS" fact (domain.py:989-995, 1146-1161), while `_years_met` takes the max years number found anywhere in the resume (domain.py:799-812); `_fact_negates_claim` is a naive substring scan (domain.py:1126-1133); `_missing_provenance` is all-or-nothing — one provenance entry anywhere silences all checking (domain.py:1295-1303); duplicate detection is skills-only and the keyword-stuffing check breaks after the first repeated term (domain.py:1306-1326). The operation DTO has no `reason` field and `validateChange` checks neither reason nor provenance (schemas.py:166-179, domain.py:435-519), despite section 4.5 and CONTRACT_SURFACE_ALIGNMENT.md:207-209 making them mandatory. The section 13 `guardrails.*` keys are unwired. Gates pass, but the official final-validation path is broken for the legitimate tailoring path and the gate rejects only what the fixtures enumerate — this is neither scaffold nor working product.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Fix the `validateFinalResume` applied-operations defect so grounded, applied changes pass final validation, restoring DoD steps 10-14.
- Generalize the honesty gate to reject ANY ungrounded claim (CONTRACT_SURFACE_ALIGNMENT.md:330), with title-inflation laddering beyond the word "staff" and years matching that accepts truthful numeric-vs-word variants.
- Replace all-or-nothing grounding with claim-level provenance checking over the ResumeField weaving RKIT-I-0001 delivers.
- Enforce the section 4.5 operation lifecycle: mandatory reason/requirementIds/factIds/provenance and the full verb/status machine per RKIT-A-0006 item 3.
- Wire the section 13 `guardrails.*` config keys per A-0006 item 6.

**Non-Goals:**
- No DTO shape definition — RKIT-I-0001 restores the operation fields; this initiative enforces their semantics.
- No scoring or threshold policy (RKIT-I-0002) and no selection planning (RKIT-I-0003 — the former dependency on it was artificial and is removed).
- No LLM or semantic-model equivalence checking — deterministic grounding only; semantic-equivalence surfaces belong to resume-agent.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. `validateFinalResume` threads the actual applied operations into grounding instead of hardcoding `applied_operations=[]` (domain.py:611); an E2E test proves a validated-and-applied grounded addition passes final validation (DoD steps 10-14).
2. The honesty gate grounds every claim-bearing operation against facts and provenance; `_GUARDED_TERMS` (domain.py:47-53) is demoted from mechanism to regression fixture. The audit's three empirically passing fabrications ("Served 50 million users daily", "Principal Engineer leading 100 people", "Kubernetes expert") are rejected by the general mechanism.
3. Title-inflation checking uses a seniority ladder (engineer < senior < staff < principal < distinguished) against the highest evidenced title instead of the single word "staff" (domain.py:1136-1143); "Principal Software Engineer" inflation is rejected.
4. Years-claim support normalizes number words and digits and scopes evidence to the claim's subject: truthful "AWS, six years" matches a "6 years of AWS" fact (fixes domain.py:989-995, 1146-1161), and an unrelated "10 years" elsewhere in the resume cannot satisfy a requirement threshold (fixes domain.py:799-812).
5. Grounding is claim-level: per-claim missing-provenance detection over ResumeField replaces the resume-level check where one provenance entry silences everything (domain.py:1295-1303; section 4.1 ResumeField key invariant).
6. `validateChange` rejects operations missing `reason`, `requirementIds`, `factIds`, or `provenance` and enforces the section 4.5 status machine including `accepted`/`modified` transitions (schemas.py:166-179, domain.py:435-519; A-0006 item 3). All five verbs (replace/rewrite/insert/remove/move) have defined apply semantics.
7. Section 13 `guardrails.*` keys are wired and validated; the `allow_inferred_facts` flat key migrates and is removed (A-0006 item 6). `inferred` facts never silently ground a claim requiring verification.
8. Duplicate and stuffing checks generalize: experience/bullet repetition is detected, keyword-stuffing counts all repeated terms instead of breaking after the first (domain.py:1306-1326), and `_fact_negates_claim` moves from substring scanning to structured comparison against fact fields (domain.py:1126-1133).

### Dependencies
- RKIT-I-0001 — restored operation DTO fields (reason/provenance/verbs/statuses) and claim-level ResumeField provenance from normalization.
- RKIT-I-0002 — requirement/fact linkage in match results that operations reference via requirementIds/factIds.
- RKIT-A-0006 (decided) — authorizes the protected-test realignment this work needs; no open ADR blockers remain.

### Blocked Status
- Blocked by RKIT-I-0001 and RKIT-I-0002 (frontmatter `blocked_by: ["RKIT-I-0001", "RKIT-I-0002"]`). The former dependency on RKIT-I-0003 was artificial — change validation and application consume contracts and resolution linkage, not selection plans — and is removed to unserialize the package.

## Detailed Design **[REQUIRED]**

**Applied-operations threading.** `validateFinalResume` accepts the applied operation list (or reads the audit trail `applyChanges` already records) and passes it to `validateGrounding`; the final resume's claim set is grounded as base claims (provenance from normalization) plus applied-operation claims (provenance from each op's `provenance`/`factIds`). This deletes the hardcoded empty list at domain.py:611 — the smallest change with the highest severity in this scope.

**Claim-level grounding model.** Claims are extracted per ResumeField; each requires a provenance chain to a fact whose VerificationState is acceptable for the claim type. `inferred` may assist discovery but cannot ground a resume claim without confirmation (VerificationState key invariant). An operation grounded at validate time stays grounded at final-validation time because the same per-claim check runs over the same provenance.

**Generalized honesty mechanisms.** Quantity claims (digit or number-word scale statements) require a fact asserting a compatible quantity after word-digit normalization; title claims compare ladder position against the highest evidenced title; negation checks compare claims against structured fact fields rather than scanning for "no "/"not ". The five fixture guards become regression fixtures that must pass through the general path — assertion strength preserved per the A-0006 authorization, fixture truth content unchanged.

**Lifecycle enforcement.** Status machine: proposed → validated → applied → accepted/modified, with validated → rejected; invalid transitions are typed errors. `applyChanges` continues to refuse non-validated operations and now also refuses operations missing mandatory fields.

**Config.** The `guardrails.*` namespace is parsed and validated through the shared section 13 config layer; unknown keys fail validation.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- E2E regression: the DoD 10-14 grounded-tailoring path (validate, apply, final validation) passes through the official surface — the audit's highest-severity break.
- Adversarial honesty suite beyond fixtures: novel fabricated scale/title/skill claims are rejected; truthful numeric-vs-word years phrasing is accepted (currently rejected); an unrelated years figure elsewhere in the resume does not satisfy thresholds.
- Per-claim provenance tests: one provenanced claim does not silence checking of the others.
- Operation lifecycle matrix: missing reason/requirementIds/factIds/provenance rejected; the full verb table and status-transition table covered, including invalid-transition rejection.
- TEST_SPEC strengthening: TEST_SPEC.md:128 references rejecting operations "when the reason depends on them" while the DTO lacks a reason field — update the spec to enumerate the mandatory operation fields, and implement this scope's unit cases in the currently empty tests/unit.

## Alternatives Considered **[REQUIRED]**

- **Grow `_GUARDED_TERMS` incrementally as new fabrications are discovered.** Rejected: fabrication is open-world; an enumerate-the-lies list can never certify honesty. The gate must default-deny claims without grounding, which is what CONTRACT_SURFACE_ALIGNMENT.md:330 requires.
- **Use an LLM judge for semantic claim-fact equivalence.** Rejected: resume-core is deterministic and stdlib-only; the Honesty Gate must be reproducible in CI and offline. Deterministic normalization (word-digit numbers, title ladder, structured negation) covers the audited failure classes; deeper semantic equivalence is resume-agent proposal-side territory.
- **Keep resume-level provenance checking but require N entries.** Rejected: still gameable by padding provenance anywhere; the section 4.1 ResumeField key invariant requires per-claim grounding, and RKIT-I-0001 provides exactly that substrate.

## Implementation Plan **[REQUIRED]**

**Progress 2026-08-13 (session resuming from `.agents/HANDOFF.md`):** Chunk 1 execution started per Daniel's "continue" green-light on the handoff's proposed next step. Confirmed the defect live: `domain.py:611` calls `validateGrounding(resume, career_fact_dtos or [], [], config)` with applied operations hardcoded to `[]`, so `linked_fact_ids` from applied operations never reach `_claim_support`. No `applyChanges` aggregate exists — only per-op `applyChange`, which returns `applied_operation` (status `applied`) and an audit dict but does not store a trail on the resume; the fix therefore threads an applied-operations list parameter into `validateFinalResume`. Constraint mapping (contract docs, protected tests, `core_surface.json`, guardrails, CLI/workflow call sites) fanned out to parallel readers before design. Protected-test/manifest edits, if needed, proceed under RKIT-A-0006 strengthen-only authorization.

**Progress 2026-08-13 (later, same session) — chunk 1 implemented, gates green, adversarial review in flight.** TDD sequence completed: (1) RED — new `tests/e2e/test_grounded_tailoring_final_validation.py` (six tests, DoD steps 10-14 through the official `resume_core` surface: grounded op validates+applies, hallucinated op rejected, re-score shows `req_aws` upgrading to `exact_match`, final validation with applied ops, ungrounded-guarded-claim converse, determinism) failed with `TypeError: validateFinalResume() takes from 2 to 4 positional arguments but 5 were given` — the surface lacked the input. (2) GREEN — `domain.py` `validateFinalResume` gained trailing optional `applied_operations=None`, threaded into `validateGrounding` in place of the hardcoded `[]`; all six tests pass. (3) Alignment edits: `core_surface.json` validateFinalResume `input_contract.required_fields` += `applied_operations` (mirrors validateGrounding's own convention; manifest is not straight-jacket-protected; input contracts are declared-but-unenforced by tooling); `tests/suite_manifest.json` `runner_commands` += `"e2e"` entry (protected `run_tests.py` module lists cannot include the new suite, so it registers here; requires `pip install -e .` per HANDOFF §7). No protected file was edited. Verification evidence: PR gate 188 tests OK, smoke gate OK, `tools/tests_guardrails.py` OK, e2e suite 6/6 OK. Scoring semantics note for chunk-1 test design: `_resolve_requirement` resolves requirements from verified facts alone, so the score does not increase when the resume gains the term — the observable step-13 improvement is the resolution-state upgrade to `exact_match` (score-side depth remains RKIT-I-0002's scope). Out-of-scope finding reconfirmed for the owners: the same hardcoded-`[]` defect exists at `resume-cli/resume_cli/__init__.py:275` inside `_validate` (RKIT-I-0039/0040 scope), and CLI `_validate` also still calls `validateFinalResume` without the ops list — the CLI path stays broken until those initiatives land. A three-skeptic adversarial review (contract compliance, test genuineness incl. mutation probes, blast radius) returned **0 refutations at high confidence**; mutation probes confirmed the suite fails on both a full revert and a partial revert (parameter kept, threading dropped), and that no alternate path (unlinked facts in `career_fact_dtos`) can ground a guarded claim. **Chunk 1 is COMPLETE** (uncommitted; test renamed to `test_rescore_after_apply_upgrades_requirement_resolution` for honest naming; all gates re-verified green after the rename). Residuals recorded from the review: (a) the e2e suite is executed by NO automated gate — the release_candidate tier that `suite_manifest.json` declares is unimplemented, so a revert would pass PR/main gates; wiring the e2e gate is RKIT-I-0051 Wave 1 scope. (b) `validateFinalResume` does not verify that passed operations carry `applied`/`validated` status — inherited from `validateGrounding`'s trust model; chunk 2 (lifecycle enforcement) should decide whether final validation filters by status. (c) The `core_surface.json` input-contract edit rests on Daniel's session green-light plus an extended reading of RKIT-A-0006 (its enumerated drift inventory does not name this parameter) — **RATIFIED by Daniel 2026-08-13** ("Do it" on the chunk-1 completion report that explicitly requested this ratification). (d) The CLI's own 4-arg `validateFinalResume` call and its direct hardcoded-`[]` `validateGrounding` call (`resume_cli/__init__.py:274-275`) now nominally under-supply the declared input contract — correct pressure toward RKIT-I-0039/0040, which own that fix.

**COMPLETE 2026-08-14 (continuous mode).** Chunks 2-6 executed as tasks RKIT-T-0034..0038 (serial codex chain, all committed on develop): T-0034 lifecycle enforcement (change_operations.py: per-field typed errors, transition table, 5-verb apply semantics, final-validation status filtering — residual (b) resolved); T-0035 claim-level grounding (grounding.py: per-claim walk over claim_fields weaving, pointer-carrying findings, inferred-never-grounds; CLI validate now threads applied ops — old resume_cli:275 defect fixed); T-0036 generalized honesty (honesty.py: mechanism over enumeration — lookup-neutralized tests prove the audit's three fabrications reject; quantity word↔digit, seniority ladder, subject-scoped years, structured negation; truthful fixture linkage strengthened); T-0037 guardrails.* config (guardrails_config.py per section 13 precedents; flat allow_inferred_facts removed as typed error; quality_warnings.py: generalized duplicates, all-terms stuffing); T-0038 adversarial suite + TEST_SPEC strengthening + run_tests wiring (PR gate 307→344; mutation probe evidenced). All requirements 1-8 satisfied; every task independently driver-probed. Gates at close: --pr 344 OK, --smoke OK, --future-contract 351 OK. Protected edits pending Daniel's approve/update-locks commit: tools/TEST_SPEC.md, tools/run_tests.py (+ his own pre-commit hook edit).

Decomposition guidance (dependency-ordered chunks; actual Metis task decomposition happens later):
1. `validateFinalResume` applied-operations threading fix plus the DoD 10-14 E2E regression test (highest severity, smallest change — first).
2. Operation lifecycle enforcement: mandatory fields, verb semantics, status machine.
3. Claim-level grounding over ResumeField provenance.
4. Generalized honesty heuristics: quantity normalization, title ladder, scoped years evidence, structured negation.
5. `guardrails.*` config wiring plus duplicate/stuffing generalization.
6. Adversarial honesty suite plus TEST_SPEC strengthening.