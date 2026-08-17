---
id: resume-agent-grounded-rewrite
level: initiative
title: "Resume-Agent Grounded Rewrite Proposal Adapter"
short_code: "RKIT-I-0019"
created_at: 2026-08-13T20:41:37.268979+00:00
updated_at: 2026-08-17T17:52:35.827478+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0016]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-agent-grounded-rewrite
---

# Resume-Agent Grounded Rewrite Proposal Adapter Initiative

## Context **[REQUIRED]**

Package: `resume-agent`. The proposal-only invariant already holds — `proposeRewrite` never returns mutated resumes — but everything else about the rewrite surface is defective, and the work here is remediation-plus-build, not construction.

Verified defects, all in `resume_agent/__init__.py`: the "after" text is literally `f"Built {', '.join(unique_phrases)}."` (:739) — keyword-salad, always past-tense "Built"; the generator inserts EVERY non-blocked job-terminology term absent from the original text regardless of whether any allowed fact supports it (:723-727 — verified empirically: with only an API fact supplied, "responsive design" was still added), violating the Honesty Gate (CONTRACT_SURFACE_ALIGNMENT.md:330), vision section 12 ("Rewrite prose — grounded proposal only"), and TEST_SPEC :69-70; `voice_constraints` are required in input then never referenced (:682); length handling is naive truncation (:743-745); the prohibited-additions filter is case-insensitive substring containment (:301-303), blind to paraphrase.

DTO drift vs section 4.5 (all confirmed): operations carry no `reason` field at all (:756-773); `operation_type` is the out-of-enum `replace_text` (:758); provenance is a single metadata dict (:767-771) instead of `ProvenanceRef[]`; and when the orchestrator supplies no target, the agent fabricates a default `target_path` of `experience[0].bullets[0]` (:759) — inventing the mutation location even though target selection is code-owned (vision section 12; CONTRACT_SURFACE_ALIGNMENT.md:209). TEST_SPEC's rewrite-return list (:66-67) omits `reason`, which is how the drift shipped green.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Real grounded prose rewriting through the RKIT-I-0016 `ModelAdapter`: candidate prose whose every claim is licensed by a supplied allowed fact — no ungrounded terminology insertion.
- Full section 4.5 `ResumeChangeOperation` compliance per RKIT-A-0006 decision 3: in-enum verbs (`replace`/`rewrite`/`insert`/`remove`/`move`), mandatory `reason`, `requirementIds`, `factIds`, and `provenance` as `ProvenanceRef[]`.
- No agent-fabricated `target_path`: target selection is code-owned; the `experience[0].bullets[0]` default is removed and a missing target is a typed input error.
- Voice and length constraints honored — currently accepted then ignored — with per-operation model-sourced confidence.

**Non-Goals:**
- Adapter/fake/config plumbing (RKIT-I-0016); the `reason` entry in `agent_surface.json` `operation_fields` lands there — this initiative makes the emitted operations actually carry it.
- Resume/job extraction (RKIT-I-0017); interview interpretation (RKIT-I-0018); equivalence proposals (RKIT-I-0020); audit records and eval fixtures (RKIT-I-0021).
- No application of operations, no validation authority (resume-core's `validateChange` enforces 4.5), no scoring or workflow decisions.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

1. **Grounding (Honesty Gate):** every claim or terminology addition in proposed text is licensed by a supplied allowed fact; the :723-727 insert-everything path is removed. Acceptance probe: with only an API fact supplied, "responsive design" must not appear (the audit's verified counterexample; TEST_SPEC :69-70).
2. **Section 4.5 DTO (RKIT-A-0006 decision 3):** every operation carries an in-enum verb (retiring `replace_text` at :758), mandatory non-empty `reason` (fixing :756-773), `requirementIds`, `factIds`, and `provenance: ProvenanceRef[]` linking to the licensing evidence (replacing the metadata dict at :767-771).
3. **Code-owned targets:** the fabricated `experience[0].bullets[0]` default (:759) is deleted; a call without a valid code-supplied `target_path` fails with a typed input error (CONTRACT_SURFACE_ALIGNMENT.md:209; vision section 12).
4. **Constraints honored:** `voice_constraints` shape the generated prose (fixing the accepted-then-ignored input at :682); length limits are met by generation, not post-hoc truncation (:743-745).
5. Prohibited additions enforced semantically at generation plus deterministically at validation — the substring filter (:301-303) stops being the only line of defense.
6. Outputs remain schema-constrained proposals with `requires_validation`; per-operation confidence is model-sourced; no mutation, persistence, or scoring.

## Detailed Design **[REQUIRED]**

- **Input contract.** Code supplies: original text, valid `target_path` (mandatory — typed error if absent or malformed), allowed facts with ids, target requirement ids, voice/length constraints, prohibited additions. The agent phrases; code decides where and from what.
- **Operation DTO.** Section 4.5 shape: `{operation_type ∈ replace|rewrite|insert|remove|move, target_path, before, after, reason, requirementIds, factIds, provenance: ProvenanceRef[], confidence, status: proposed}`. Each `ProvenanceRef` points at the specific fact/evidence licensing the changed span.
- **Grounding enforcement.** The output schema requires the model to map each added claim/term to a licensing fact id; a deterministic post-validation guard rejects any operation whose added terms lack a fact mapping or whose cited fact ids are outside the allowed set — grounding cannot rest on the prompt alone.
- **Constraint handling.** Voice constraints enter the prompt contract and are checked post-generation (tense/person heuristics deterministic where checkable); length is a generation parameter with a deterministic post-check that rejects, never truncates.
- **Migration.** The template concatenation path (:739) is deleted. Emitted DTOs and `agent_surface.json` (updated in RKIT-I-0016) move in lockstep so the guardrail grep matches reality; resume-core's `validateChange` alignment to 4.5 is parallel work under RKIT-A-0006 and is consumed, not owned, here.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Grounding contract tests (new):** the verified counterexample as a permanent regression test — API-fact-only input must never yield "responsive design"; property-style assertion that every added term in `after` maps to a supplied fact id.
- **DTO contract tests (strengthened):** every operation has in-enum verb, non-empty `reason`, and non-empty `ProvenanceRef[]`; missing `target_path` produces the typed error, never a fabricated default.
- **TEST_SPEC strengthening (audit-flagged):** add `reason` to the rewrite-return list (:66-67) — the omission that licensed the drift — and replace fixture-phrase grounding checks with fact-mapping assertions the substring filter cannot satisfy; add voice/length constraint assertions (constraints currently have zero test coverage).
- Fake-adapter fixtures for grounded, ungrounded-rejected, and constraint-violating-rejected cases; guardrail and boundary suites stay green.

## Alternatives Considered **[REQUIRED]**

- **Post-hoc filtering of ungrounded terms out of template output.** Rejected: the template emits keyword salad, not prose — filtering cannot create quality; and the :301-303 substring filter already demonstrates that lexical filtering misses paraphrased inflation. Grounding must be generation-time plus structural validation.
- **Keep the metadata-dict provenance and adapt consumers.** Rejected by RKIT-A-0006: documented contract wins; `ProvenanceRef[]` is what makes the Audit and Honesty Gates enforceable per-span rather than per-operation-blob.
- **Allow agent-suggested target paths marked "advisory".** Rejected: vision section 12 makes content selection code-owned; an advisory path invites orchestrators to pass the buck back to the model — the typed error keeps the responsibility boundary honest.

## Implementation Plan **[REQUIRED]**

1. Section 4.5 operation DTO (verbs, `reason`, `requirementIds`, `factIds`, `ProvenanceRef[]`) and input-contract validation with the typed missing-target error; delete the fabricated default.
2. Rewrite generation through the adapter with fact-mapped output schema; delete the template-concatenation path.
3. Deterministic grounding post-guard (added-term-to-fact mapping check against the allowed set).
4. Voice/length constraint plumbing: prompt contract plus deterministic post-checks.
5. Contract-test batteries (grounding, DTO, constraints) and the TEST_SPEC `reason`/grounding strengthening.

## Dependencies / Blocked Status

Blocked by RKIT-I-0016 (`blocked_by: ["RKIT-I-0016"]`) — consumes the `ModelAdapter`, fake runtime, and the manifest `reason` fix. The former transitive ADR block is lifted: RKIT-A-0003 was decided 2026-08-13; RKIT-A-0006 decides the 4.5 DTO realignment this initiative implements on the agent side.