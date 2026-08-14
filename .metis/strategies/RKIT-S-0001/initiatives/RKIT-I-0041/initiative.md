---
id: persistent-multi-job-cli-flow-and
level: initiative
title: "Persistent Multi-Job CLI Flow and Release Acceptance"
short_code: "RKIT-I-0041"
created_at: 2026-08-13T20:41:37.966652+00:00
updated_at: 2026-08-13T20:41:37.966652+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0040", "RKIT-I-0007"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Persistent Multi-Job CLI Flow and Release Acceptance Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. The E2E-visible multi-job story currently works only by fixture-keyed hardcoding, and its two load-bearing substrates do not exist:

- Cross-job reuse has nothing real to reuse: off-fixture resumes persist zero career facts (`_facts_from_resume`'s hardcoded 12-entry list — remediated by RKIT-I-0036), so the Persistence Gate scenario "Job B uses AWS/GraphQL learned in Job A" generalizes only after RKIT-I-0036's extraction work lands. The serial chain carries this transitively, but decomposition here must treat real extraction as the substantive prerequisite it is, not assume fixture vocabulary.
- Duplicate-question suppression has no substrate in current code: no questions or answers are recorded anywhere, so "already verified facts are not re-asked without legitimate new specificity" cannot be implemented, let alone tested. RKIT-A-0001 decides the substrate: the append-only `interactions` table with `recordInteraction()`/`listInteractions(filter)` and the vocabulary `question_asked`/`answer_recorded`/`fact_confirmed`/`rewrite_accepted`/`rewrite_modified`/`rewrite_rejected`. RKIT-I-0037 records at ask/answer time; this initiative consults the history before asking.
- Release-acceptance ownership overlapped RKIT-I-0028 (Workflow-Backed Smoke and E2E Acceptance Coverage) with no delineation. Boundary set here: RKIT-I-0028 owns the smoke/E2E harness and its workflow backing; RKIT-I-0041 owns the resume-cli release evidence — the passing multi-job acceptance run and its artifacts.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Multi-job session lifecycle: add/switch/replace a job in a workspace without damaging base.json, the career DB, or other jobs' artifacts; per-job working projections stay isolated.
- Duplicate-question suppression: before emitting a question, resolve consults `listInteractions` and store verification state — an already-verified fact is not re-asked unless the new requirement carries legitimate new specificity (e.g. a years threshold above what was confirmed); suppressed questions resolve from stored facts and are recorded as reuse.
- Cross-job reuse: Job B's match consumes Job A's verified facts and career-store relationships (RKIT-I-0007) with no re-interview for covered requirements — the Persistence Gate scenario, off-fixture.
- Preference history: rewrite accept/modify/reject decisions are recorded via RKIT-A-0001 interactions; recording structurally cannot alter fact verification (Persistence Gate; RKIT-A-0001 item 3).
- CLI release evidence: this initiative assembles and owns the resume-cli release-gate artifact set — the off-fixture two-job E2E run, canonical package gate results, and audit reconstruction output.

**Non-Goals:**
- The smoke/E2E harness, fixture infrastructure, and workflow backing — RKIT-I-0028 (this initiative produces evidence through that harness; it does not build it).
- Fact extraction generality — RKIT-I-0036 (named because reuse is empty without it).
- Store-side relationship semantics and relationship-aware scoring — career-store RKIT-I-0007 / resume-core.
- Interaction-recording call sites in resolve — RKIT-I-0037.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- `job add/switch/replace` operate on isolated per-job artifact sets; base.json hash and career DB fact rows are unchanged by job lifecycle operations (only resolve/tailor flows mutate them, through owned surfaces).
- In a two-job session, a requirement whose backing fact was verified in Job A produces zero new `question_asked` interactions in Job B for the same subject absent new specificity; the match/audit trail shows the reused fact's provenance.
- A requirement with genuinely new specificity (e.g. a higher years bound) is re-asked; the narrower confirmation persists append-only without erasing the prior one.
- No code path from preference/interaction recording writes `facts.verification_status` — the RKIT-A-0001 item 3 boundary rule, verified at the CLI integration level.
- The release evidence bundle exists as a persisted artifact set: two-job off-fixture E2E results, package gate output, audit reconstructions — the acceptance record for shipping resume-cli.

### Dependencies
- RKIT-I-0040 (gated run/audit/recovery substrate a multi-job session extends).
- RKIT-I-0007 Relationship-Aware Matching and Cross-Job Reuse (career-store relationship surfaces).
- Substantive transitive prerequisite: RKIT-I-0036 — cross-job reuse only generalizes once fact extraction is real; carried through the chain (0036 → ... → 0040) but named so decomposition does not assume fixture vocabulary.

### Blocked Status
- Blocked by RKIT-I-0040 and RKIT-I-0007 (frontmatter matches). RKIT-A-0001 is decided (interactions substrate, migration state), so duplicate-question suppression has a specified contract; no ADR block remains.

## Detailed Design **[REQUIRED]**

- **Session model.** Workspace holds one base + career DB and N job contexts (`jobs/<job-id>/` with job.json, working.json, match/tailor/validate/export artifacts, per-job run manifest). `job switch` re-points the active context; `job replace` archives the old context and starts fresh; nothing under `resume/base.json` or the store is touched by lifecycle commands.
- **Suppression algorithm.** For a selected unresolved requirement: query store facts by subject; if a verifying fact exists whose verification state and specificity cover the requirement, mark resolved-by-reuse, record a reuse interaction, and skip the question. If the requirement's specificity exceeds the confirmed bound, ask only the delta question. `listInteractions(subject_id)` supplies asked/answered history; "legitimate new specificity" is computed from requirement fields (type/years per the RKIT-A-0006 JobRequirement shape), not question-text similarity.
- **Cross-job matching.** Job B match runs with the full store: verified facts plus RKIT-I-0007 relationships (the RKIT-A-0006 item 5 relationship set including parent/child and the documented `contradicts` extension) feed core resolution so related evidence resolves requirements without new interviews; provenance in the match artifact names the originating facts.
- **Preference recording.** Tailor decision points (RKIT-I-0038 loop) emit `rewrite_accepted`/`rewrite_modified`/`rewrite_rejected` interactions with operation ids as opaque subject ids (per RKIT-A-0001 item 3). Recording is fire-and-forget; consumers are future learning features.
- **Release evidence.** A release assembly step gathers the two-job E2E output (via the RKIT-I-0028 harness), package gate results, audit reconstructions for both jobs, and the suppression report (questions asked in A vs suppressed in B) into a versioned evidence artifact.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Two-job off-fixture E2E — the release acceptance test this initiative owns: Job A interview persists facts (post-RKIT-I-0036 extraction); Job B asserts zero duplicate `question_asked` interactions for covered subjects, match consumption of Job A facts with provenance, and an improved-vs-uninformed score.
- New-specificity case: a Job B requirement with a higher years bound is re-asked; both confirmations persist append-only.
- Job lifecycle tests: add/switch/replace preserve base.json hash, career-store fact rows, and sibling-job artifacts.
- Boundary test at the CLI level: driving accept/modify/reject flows writes interactions but never `facts.verification_status` (RKIT-A-0001 item 3).
- Suppression unit tests over `listInteractions` filters: asked-but-unanswered, answered-negative (recorded, not re-asked within the session), verified-fact reuse, delta-specificity re-ask.
- Delineation check with RKIT-I-0028: this initiative's tests invoke the 0028 harness; harness capabilities themselves are asserted in 0028's scope, preventing double-ownership drift.

## Alternatives Considered **[REQUIRED]**

- Suppress duplicates by fuzzy-matching question text in the CLI: rejected — question phrasing varies per job and per agent call, so text matching both re-asks rephrased duplicates and wrongly suppresses distinct questions; the decided substrate (RKIT-A-0001 interactions plus fact verification state keyed by subject) is semantic, durable, and store-owned.
- Defer duplicate suppression to a post-release learning initiative: rejected — the Persistence Gate and E2E Phase 16 make no-duplicate-questioning release-blocking, and RKIT-A-0001 built the append-only substrate now precisely so this initiative would not have to invent one.
- Fold release acceptance entirely into RKIT-I-0028: rejected — 0028 owns harness/coverage infrastructure across packages, not per-package acceptance evidence; without a CLI-side owner the resume-cli release gate has no accountable initiative, which is exactly the overlap the audit flagged.

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Multi-job workspace/session lifecycle (add/switch/replace, per-job contexts, isolation guarantees).
2. Suppression algorithm in the resolve path: store-fact reuse check, listInteractions consultation, delta-specificity questions.
3. Cross-job match wiring through RKIT-I-0007 relationship surfaces with provenance reporting.
4. Preference-history recording at tailor decision points.
5. Two-job off-fixture E2E plus boundary/lifecycle tests via the RKIT-I-0028 harness.
6. Release evidence assembly artifact.
