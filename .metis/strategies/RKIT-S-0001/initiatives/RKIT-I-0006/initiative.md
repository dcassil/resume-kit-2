---
id: evidence-backed-fact-and
level: initiative
title: "Evidence-Backed Fact and Verification Lifecycle"
short_code: "RKIT-I-0006"
created_at: 2026-08-13T20:41:36.939547+00:00
updated_at: 2026-08-15T00:37:18.562186+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0005]
archived: false

tags:
  - "#initiative"
  - "#phase/decompose"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: evidence-backed-fact-and
---

# Evidence-Backed Fact and Verification Lifecycle Initiative

## Context **[REQUIRED]**

Package: `career-store`. Fact, evidence, and verification persistence genuinely exists: facts with deterministic content-hashed ids, append-only evidence rows, a user_verified precedence rule in the upsert merge (store.py:885-905), and confirmation answers persisted as evidence. This initiative is remediation-plus-completion of that layer, not greenfield.

The 2026-08-13 alignment audit verified the honesty core is broken or absent:
- The confirmation gate is a bag-of-substrings heuristic (store.py:51-76, 1243-1254): the text "incorrect" matches the marker "correct" and "yesterday I did nothing" matches "yes", so both promote an inferred fact to user_verified via verifyFact (verified empirically). The store is interpreting raw user answer text itself, which vision section 12 forbids: "User answer interpretation — Validate | Agent proposes".
- verifyFact gates only the user_verified target: inferred→source_stated succeeds with confirmation=None from an agent source (store.py:318-345), and source_stated facts then resolve requirements as exact_match (store.py:1188) — a silent truth-escalation bypass. Downgrades of user_verified are entirely ungated, conflicting with "Preserve user verification across separate job sessions" (TEST_SPEC:71).
- Fact merging does not exist. Dedupe is identical-content hash collision only; vision section 6's "Fact merging/deduplication" responsibility and its "Destructive merges should retain aliases/history" rule have no implementation.
- Ownership of confirmation history vs the interactions table was ambiguous between this initiative and RKIT-I-0008; RKIT-A-0001 has since assigned the interactions/preference substrate to RKIT-I-0008, leaving fact-level confirmation evidence here.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Replace the substring confirmation heuristic with store-side validation of structured interpretation proposals per vision section 12: the agent proposes an interpretation, the store validates and persists.
- Gate every verification transition through one explicit transition policy — no path to source_stated without source evidence, no path to user_verified without an affirmed user-provenance confirmation, no ungated downgrade of user_verified.
- Deliver mergeFacts with alias and history retention per vision section 6.
- Own fact-level confirmation evidence: question, structured answer, resulting transition, provenance.

**Non-Goals:**
- The interactions table, recordInteraction/listInteractions, and preference history — owned by RKIT-I-0008 per RKIT-A-0001 items 2-3.
- Matching semantics, alias lookup, and relationship confirmation — RKIT-I-0007.
- Migration registry, restored enum vocabulary, and the atomic transaction substrate — consumed from RKIT-I-0005, not built here.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. Remove the affirmative/negation substring marker tables and their use (store.py:51-76, 1243-1254). The confirmation surface accepts a structured interpretation proposal DTO; the store validates it and never derives meaning from raw answer text, which is retained as evidence only. The audit's empirical probes become permanent regressions: the literal inputs "incorrect" and "yesterday I did nothing" must not promote any fact (both promote inferred→user_verified today).
2. Structured proposal validation per section 12: proposals carry an explicit outcome (affirmed/denied/unclear), the referenced fact and question ids, an optional corrected value, and ProvenanceRef-style provenance. Malformed or incomplete proposals fail with typed errors; denied and unclear outcomes never change verification state.
3. A single verification transition engine gates all transitions over the restored five-state set (source_stated/user_verified/imported/inferred/unknown per RKIT-A-0006 item 1): inferred→user_verified requires an affirmed proposal with user provenance; inferred→source_stated requires source-document evidence, closing the ungated escalation at store.py:318-345; imported enters only via the import path; user_verified never downgrades except by an explicit user-provenance correction (TEST_SPEC:70-71). Disallowed transitions fail with typed errors; every allowed transition writes an evidence row with prior state, new state, and provenance.
4. mergeFacts API: merging retains the losing fact's terms as aliases, preserves all evidence rows for both facts, records the merge in history, and leaves the merged-away id resolvable to the survivor (section 6: "Destructive merges should retain aliases/history"). The survivor's verification state follows the transition engine — merge never silently escalates.
5. All fact/evidence/verification writes run through RKIT-I-0005's atomic transaction substrate (single-connection detect+write).
6. Confirmation-history boundary: fact-level confirmation evidence lives here; once RKIT-I-0008 lands, confirmation events may additionally emit interaction records, but interaction records can never be a write path into verification state (RKIT-A-0001 item 3).

### Dependencies
- RKIT-I-0005: migration registry for new columns, restored VerificationState vocabulary, transaction substrate, canonical_name/description columns used by merge.
- RKIT-A-0001 (decided): interactions substrate assigned to RKIT-I-0008; the no-write-path boundary rule.
- RKIT-A-0006 (decided): five-state VerificationState; ProvenanceRef; surface-realignment authorization.

### Blocked Status
- Blocked by RKIT-I-0005 (foundation substrate). No ADR blocks remain: RKIT-A-0001 and RKIT-A-0006 are decided and referenced above.

## Detailed Design **[REQUIRED]**

- Interpretation proposal DTO: `{factId, questionId?, outcome: "affirmed"|"denied"|"unclear", confirmedValue?, provenance: ProvenanceRef[]}`. Validation rejects unknown outcome values, missing provenance, and references to unknown facts. This DTO is the only confirmation input; the current free-text confirmation parameter is removed from the surface (manifest edit under the RKIT-A-0006 realignment authorization).
- Transition engine: a data-declared matrix `{(from, to) → required authority}` evaluated in one chokepoint used by the verify/confirm surface, the import path, and merge. Authorities: user-provenance affirmed proposal, source-document evidence ref, import provenance. The matrix is exported so tests assert the full edge set, not samples.
- Evidence trail: each transition appends `{factId, priorState, newState, authorityKind, provenanceRefs, createdAt}` — append-only, no updates.
- Merge design: `mergeFacts(survivorId, mergedId, provenance)` moves the merged fact's terms into the survivor's alias set (alias relationships plus the canonical_name/description columns from RKIT-I-0005), re-points evidence and job-match references, writes a merge history row, and installs an id redirect so old ids resolve.
- Typed errors: `InvalidInterpretationProposalError`, `DisallowedTransitionError(from, to, requiredAuthority)`, `MergeConflictError` — all surfaced through store_surface.json.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract regressions on the audit's exact probes: "incorrect" and "yesterday I did nothing", routed as raw text or as denied/unclear proposals, leave verification unchanged — these strings promote to user_verified today and no test catches it.
- Full transition-matrix test: every disallowed (from, to) edge raises the typed error; every allowed edge requires its exact authority. Explicitly includes inferred→source_stated with agent-only provenance (currently succeeds ungated — the spec's silence on this edge is what certified the shallow gate) and user_verified persistence across store reopen and job sessions (TEST_SPEC:71).
- Merge tests: aliases retained, zero evidence rows lost, merged id resolvable, no verification escalation via merge.
- TEST_SPEC strengthening: realign the verification-state set to section 4.6 (with RKIT-I-0005) and add executable cases for downgrade protection and source_stated gating, where the spec currently names goals with no cases.
- Boundary guardrail: no store code path consumes raw confirmation text for state decisions — the marker tables are gone and the confirmation surface is validation-only.

## Alternatives Considered **[REQUIRED]**

- Fix the heuristic (negation handling, word boundaries) instead of removing it: rejected — section 12 assigns answer interpretation to the agent as proposals with store-side validation; any in-store NL interpretation violates the authority table and keeps failing on paraphrase ("not incorrect", "yes, but...").
- Harden only the user_verified target and leave other transitions open: rejected — source_stated resolves requirements as exact_match (store.py:1188), so ungated inferred→source_stated is an equivalent silent truth bypass; partial gating is exactly what produced the current hole.
- Implement merge as delete-and-recreate without retention: rejected — violates section 6's alias/history retention rule and destroys the cross-job evidence trail RKIT-I-0007 depends on.

## Implementation Plan **[REQUIRED]**

Dependency-ordered chunks for later decomposition (no Metis tasks yet):
1. Interpretation proposal DTO + validation + removal of the substring markers and free-text confirmation parameter (surface realignment under the A-0006 authorization).
2. Transition engine with data-declared matrix, typed errors, and transition evidence rows.
3. Rewire the verify/confirm surface and import path through the engine; downgrade protection.
4. mergeFacts with alias/history retention and id redirects.
5. Contract/TEST_SPEC strengthening pass: matrix tests, audit-probe regressions, cross-session persistence.