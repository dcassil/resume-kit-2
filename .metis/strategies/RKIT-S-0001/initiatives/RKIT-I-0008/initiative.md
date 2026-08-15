---
id: conflict-audit-recovery-and
level: initiative
title: "Conflict, Audit, Recovery, and Optional Preference History"
short_code: "RKIT-I-0008"
created_at: 2026-08-13T20:41:36.985858+00:00
updated_at: 2026-08-15T02:46:51.999283+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0006]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: conflict-audit-recovery-and
---

# Conflict, Audit, Recovery, and Optional Preference History Initiative

## Context **[REQUIRED]**

Package: `career-store`. Parts of this scope genuinely exist: conflict detection for years/title/contradicts persists non-destructive open conflict rows (store.py:832-883), and retry idempotency via content-hashed IDs and INSERT OR IGNORE works (store.py:1070-1073, 735-768). The transaction/recovery substrate originally sequenced here has moved to RKIT-I-0005, where RKIT-I-0006's writes need it.

Audit-verified gaps and defects in the remaining scope (2026-08-13):
- Conflicts are detection-only: rows are only ever created with status "open"; no resolve/close/adjudicate API exists (store.py:867-883), so the vision rule "a new contradictory value should create a conflict workflow" has no workflow half.
- The interactions/preference substrate is entirely absent: no interactions table, no API to record confirmations or accepted/modified/rejected rewrite decisions, no enforcement that preference learning cannot alter verification (vision section 6; TEST_SPEC "Interaction and preference history" has zero implementation). RKIT-A-0001 items 2-3 now define exactly what to build.
- `_year_claim` treats any bare digit 1-59 in any text as a years claim (store.py:1291-1311): "React 18" vs "React 17 migration" produces a false conflicting-years record (verified empirically); number words stop at ten. A better `_YEARS_RE` regex existed in the dead matching.py and is salvaged by RKIT-I-0005 before that module's removal.
- `_title_claim` is a hardcoded 5-title list sized to the Staff-engineer honesty fixture (store.py:1314-1326); no general employment-title model.
- `_detect_conflicts` contains dead identical if/else branches (store.py:840-843), so a claim carrying its own fact_id is conflict-checked against itself — which is what makes the contract test's same-fact scenario pass.
- `_clean_result`/`_FORBIDDEN_RESULT_KEYS` (store.py:36-49, 1357-1362) strip output keys ("raw_sql", "silent_user_verified_promotion", "official_score") no code path ever produces — test-manifest appeasement, not a safeguard.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- A real conflict workflow: open conflicts can be resolved, dismissed, and adjudicated with provenance, without overwriting history.
- The RKIT-A-0001 interactions substrate: append-only interactions table, recordInteraction/listInteractions, the decided interaction_type vocabulary, and the mandated boundary test that no write path exists from interaction records to verification state.
- Honest conflict heuristics: years claims only from explicit patterns; a general title model; no self-conflict dead code.
- Retry/idempotency hardening across the new surfaces, and audit outputs that are real (remove the never-produced-key stripping).

**Non-Goals:**
- Transactions/interruption-recovery substrate — moved to RKIT-I-0005; consumed here.
- Verification transitions — RKIT-I-0006; adjudication that changes verification routes through its transition engine.
- Fact-level confirmation evidence — RKIT-I-0006 owns it; this initiative owns the interactions/preference tables per RKIT-A-0001.
- Preference-learning models/rankers — explicitly rejected by RKIT-A-0001 as premature; only the thin substrate lands.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Conflict lifecycle: conflicts transition open → resolved | dismissed via an adjudication API requiring provenance. Resolution never deletes or overwrites the competing claims — both remain as evidence with the adjudication recorded ("conflict workflow, not overwrite history"). If adjudication changes a fact's value or verification state, the change routes through RKIT-I-0006's transition engine; no direct writes.
2. interactions table per RKIT-A-0001 item 2: (id, interaction_type, subject_id, input_json, result_json, created_at), append-only, created via RKIT-I-0005's migration registry; public recordInteraction() and listInteractions(filter); initial vocabulary question_asked, answer_recorded, fact_confirmed, rewrite_accepted, rewrite_modified, rewrite_rejected. subject_id values are opaque refs to resume-core ResumeChangeOperation ids and career-store fact ids (item 3); operation status lifecycle stays in resume-core.
3. Boundary enforcement per RKIT-A-0001 item 3: no store code path writes fact verification state from interaction records; an executable boundary test enforces the absence of such a path (Persistence Gate: preference learning cannot alter fact verification).
4. Replace `_year_claim` (store.py:1291-1311): years claims come only from explicit patterns ("N years", "N+ years", number words) using the `_YEARS_RE` approach salvaged by RKIT-I-0005; bare digits adjacent to product names never register. Regression: "React 18" vs "React 17 migration" produces no conflict; "5 years" vs "8 years" for the same concept still does.
5. Replace `_title_claim`'s hardcoded 5-title list (store.py:1314-1326) with a general model: title claims come from structured claim fields (canonical_name/description columns from RKIT-I-0005), not free-text sniffing against a fixture-sized list; arbitrary titles conflict when they compete for the same role slot.
6. Remove the dead identical if/else in `_detect_conflicts` (store.py:840-843); a claim carrying its own fact_id is not conflict-checked against itself, and the contract-test scenario that currently passes because of the dead branch is rewritten to assert real semantics.
7. Remove `_clean_result`/`_FORBIDDEN_RESULT_KEYS` stripping of never-produced keys (store.py:36-49, 1357-1362); any manifest expectation depending on it is replaced with assertions about outputs the store actually produces (strengthening, per the RKIT-A-0006 authorization).
8. Retry/idempotency hardening: replaying the same logical operation produces no duplicate conflict or interaction rows (extending the existing content-hash/INSERT OR IGNORE pattern to the new tables); interrupted operations recover cleanly via the RKIT-I-0005 TransactionResult substrate.

### Dependencies
- RKIT-I-0006: adjudication routes through the verification transition engine; fact_confirmed interactions reference its confirmation evidence.
- RKIT-I-0005 (transitive): migration registry for the interactions table and lifecycle columns; transaction substrate; salvaged `_YEARS_RE`.
- RKIT-A-0001 (decided): items 2-3 are implemented here.

### Blocked Status
- Blocked by RKIT-I-0006. The former RKIT-A-0001 block is lifted — the ADR was decided 2026-08-13 and now specifies this initiative's interactions scope rather than blocking it.

## Detailed Design **[REQUIRED]**

- Conflict lifecycle: conflict rows gain status (open/resolved/dismissed), resolution_provenance, resolved_at, and winning_claim_ref — added by migration, never rewriting the original claim payloads. adjudicateConflict(conflictId, decision, provenance) validates provenance, appends the adjudication, and, when the decision affects a fact, emits a proposal into RKIT-I-0006's transition engine instead of writing state.
- Interactions: exact RKIT-A-0001 item 2 shape. recordInteraction validates interaction_type against the decided vocabulary (additions are additive migrations per the ADR); listInteractions filters by interaction_type, subject_id, and time range with deterministic ordering. Module-level separation: the interactions module has no import path to fact-verification mutation helpers, which the boundary test asserts structurally in addition to behavioral probes.
- Years/title extraction: deterministic regex extraction over structured claim fields; comparison happens on typed (concept, years) and (role, title) tuples, not raw strings.
- Idempotency: interaction ids content-hashed over (interaction_type, subject_id, input_json) with INSERT OR IGNORE, mirroring the existing fact/evidence pattern (store.py:1070-1073).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Conflict workflow tests: open→resolved with provenance; dismissal; competing claims still retrievable post-resolution; adjudication affecting a fact observed as a transition-engine call, never a direct write.
- The RKIT-A-0001-mandated boundary test: no write path from interaction records to fact verification state — behavioral probe (recordInteraction of fact_confirmed does not alter the fact) plus structural import assertion.
- Heuristic regressions from the audit's empirical probes: "React 18" vs "React 17 migration" yields no years conflict; number words above ten parse; titles outside the old 5-title list participate in conflicts.
- Same-fact scenario contract test rewritten to assert real conflict semantics instead of passing via the dead branch — the current test certifies dead code (TEST_SPEC strengthening).
- Idempotency tests: duplicate replays of recordInteraction and conflict creation produce single rows.
- TEST_SPEC strengthening: "Interaction and preference history" gains executable cases (currently zero); conflict-workflow cases for resolve/dismiss/adjudicate; expectations tied to `_FORBIDDEN_RESULT_KEYS` never-produced keys replaced by real-output assertions.

## Alternatives Considered **[REQUIRED]**

- Model contradictions as fact versioning (latest wins, history in an audit log): rejected — the vision requires a conflict workflow, not overwrite history; adjudication must be explicit and provenance-carrying.
- Smarter in-store free-text claim extraction (NLP-ish years/title detection): rejected — interpretation belongs to agent proposals per section 12; the store compares structured claims and keeps only explicit deterministic patterns.
- Defer the interactions substrate until a preference-learning consumer exists: rejected by RKIT-A-0001 — retrofitting append-only history costs a migration, and the Persistence Gate needs its concrete enforcement point now.

## Implementation Plan **[REQUIRED]**

**COMPLETE 2026-08-15 (continuous mode).** Executed as RKIT-T-0054..0057 (serial codex chain, committed on develop): T-0054 interactions substrate (migration 008 append-only table, six-type vocabulary, content-hash replay dedupe, behavioral + structural no-write-path boundary per RKIT-A-0001); T-0055 conflict lifecycle (migration 009, adjudicateConflict w/ structural provenance, idempotent/typed re-adjudication, answer_recorded trail via recordInteraction, verification changes only through the engine — agent-only adjudication cannot promote); T-0056 honest heuristics (_YEARS_RE explicit patterns — React-18 false conflict gone, twelve-years parses; structured (role,title) tuples replace the 5-title list; dead self-conflict branch removed + contract test rewritten); T-0057 _clean_result/_FORBIDDEN_RESULT_KEYS appeasement deleted (guardrail pins key absence, not the mechanism), idempotency/rollback proven on new tables, TEST_SPEC executable cases, mutation probe (interactions→verification wire fails boundary test). Gates at close: --pr 352 OK, --smoke OK, --future-contract 359 OK, migration checks 4/4. Career-store tier (I-0005..0008) is now COMPLETE. Approval batch: eleven career-store unit modules for run_tests.py + surface entries (getMigrationState, mergeFacts, confirmRelationship, recordInteraction/listInteractions, adjudicateConflict, confirmation slot, parent/child vocabulary) + guardrail allowlists.

Dependency-ordered chunks for later decomposition (no Metis tasks yet):
1. Interactions table migration + recordInteraction/listInteractions + vocabulary validation + the boundary test.
2. Conflict lifecycle columns + adjudicateConflict routing through RKIT-I-0006's engine.
3. Years/title heuristic replacement + dead-branch removal + audit-probe regressions.
4. `_clean_result` appeasement removal + real-output assertions (A-0006 authorization).
5. Idempotency hardening across new tables + TEST_SPEC strengthening pass.

### Salvaged from RKIT-I-0005 matching.py deletion

The dead `career_store/matching.py` module was removed in RKIT-T-0043. Its `_YEARS_RE` pattern is preserved verbatim here for the explicit-years heuristic replacement in this initiative:

```python
_YEARS_RE = re.compile(
    r"\b(?P<value>\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty)\+?\s+years?\b",
    re.IGNORECASE,
)
```