---
id: resume-agent-semantic-equivalence
level: initiative
title: "Resume-Agent Semantic Equivalence and Entailment Proposal Handoff"
short_code: "RKIT-I-0020"
created_at: 2026-08-13T20:41:37.296716+00:00
updated_at: 2026-08-13T20:41:37.296716+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0016"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Resume-Agent Semantic Equivalence and Entailment Proposal Handoff Initiative

## Context **[REQUIRED]**

Package: `resume-agent`. Unlike its siblings, this surface is not fixture-tuned — it does not exist at all. No function, schema, or code path for semantic equivalence proposals is anywhere in the package, despite vision section 8 listing "Semantic equivalence suggestions missed by deterministic aliases" as a package responsibility and TEST_SPEC requiring the behavior in its contract sentence (:5) and E2E coverage (:113, "semantic equivalence proposals are validated before use").

The root cause is a spec gap: TEST_SPEC's "Relevant public surfaces" list (:9-13) defines no function for equivalence, making the responsibility untestable — so it was never built. The rest of the package (a full fixture-tuned implementation with a populated `agent_surface.json`) means this initiative extends an existing manifest and spec rather than creating them.

RKIT-A-0003 item 5 decided the placement question: a NEW public API `proposeEquivalences(context)`, not equivalence data embedded in extraction/rewrite outputs. Downstream ownership was already settled by the CONTRACT_SURFACE_ALIGNMENT.md responsibility matrix and is restated in the ADR: resume-core validates every proposal before use; career-store persists confirmed equivalences as relationships. Entailment review remains optional post-MVP.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- A new public `proposeEquivalences(context)` API on the resume-agent surface, powered by the RKIT-I-0016 `ModelAdapter`, emitting schema-constrained equivalence proposal DTOs: term pair, direction, rationale, evidence refs, confidence (RKIT-A-0003 item 5).
- Proposals cover equivalences deterministic aliases miss (e.g. "responsive web apps" ↔ "responsive design") without ever becoming official truth — resume-core validates, career-store stores confirmed relationships.
- The spec and manifest extensions the surface needs: `proposeEquivalences` added to TEST_SPEC's public-surfaces list (:9-13) with contract cases backing the existing :5/:113 requirements, and `agent_surface.json` extended to declare the new surface (protected-surface edits authorized by RKIT-A-0006).

**In scope / out of scope split (mandatory vs optional):**
- IN (MVP-mandatory): equivalence proposals — the vision section 8 required responsibility, the `proposeEquivalences` surface, its DTOs, spec, and manifest entries.
- OUT (optional post-MVP, per RKIT-A-0003 item 5 and vision section 8): semantic entailment review for difficult claim validation. Explicitly deferred; nothing here may depend on it.

**Non-Goals:**
- Adapter/fake/config plumbing (RKIT-I-0016). Extraction (RKIT-I-0017), interview (RKIT-I-0018), rewrites (RKIT-I-0019) — equivalence proposals are their own surface, not a side channel of those outputs.
- No validation logic (resume-core owns it) and no relationship persistence (career-store owns it); this package emits proposals only.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

1. `proposeEquivalences(context)` exists as a public function; context carries the candidate terms/snippets code selected (resume wording, JD wording, existing alias misses); output is a list of equivalence proposal DTOs, each with term pair, direction (equivalent / narrower-than / broader-than), rationale, evidence refs into the supplied context, and model-sourced confidence (RKIT-A-0003 item 5).
2. Every proposal is marked `requires_validation`; no proposal creates, scores, or persists a relationship — the handoff target is resume-core validation, then career-store persistence of confirmed pairs (CONTRACT_SURFACE_ALIGNMENT.md responsibility matrix).
3. Proposals carry deterministic evidence-linked IDs consistent with the package's existing ID discipline.
4. TEST_SPEC is extended: `proposeEquivalences` joins the public-surfaces list (:9-13); contract cases make the currently untestable :5/:113 sentences testable; the E2E case exercises proposal → resume-core validation with fixture-pinned fake-adapter outputs.
5. `agent_surface.json` declares the new function and its DTO fields so the guardrail tool covers the surface from day one — no repeat of the manifest-lag drift found elsewhere in the package.
6. Entailment review ships nothing: no function, schema, or manifest entry, and no dormant half-surface.

## Detailed Design **[REQUIRED]**

- **DTO.** `{id, term_a, term_b, direction, rationale, evidence_refs, confidence, requires_validation: true}`. Direction distinguishes true equivalence from subsumption so resume-core can validate asymmetrically (a "React" claim supports "JavaScript framework experience"; the reverse does not).
- **Context contract.** Code supplies the candidate material — the agent does not trawl whole documents for pairs on its own initiative, keeping the surface aligned with the code-selects/agent-phrases division used across the package.
- **Behavior.** Prompt/schema assets versioned like the package's other templates (hashable by RKIT-I-0021); adapter output is schema-validated inside the RKIT-I-0016 boundary; empty candidate context returns an empty proposal list, not an error.
- **Handoff.** Confirmed equivalences become career-store relationships using the section 6 relationship vocabulary as realigned by RKIT-A-0006 decision 5; this package needs no knowledge of storage — the DTO's evidence refs are what resume-core needs to validate.
- **Manifest.** `agent_surface.json` gains the function entry and DTO field list in the same change that lands the surface.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **TEST_SPEC extension (the audit-flagged gap this initiative owns):** define the function in the public-surfaces list and add contract cases — DTO schema conformance, `requires_validation` always set, direction vocabulary enforced, evidence refs resolving into supplied context — turning the spec's orphaned :5/:113 requirements into enforceable tests.
- Contract tests over fake-adapter fixtures: alias-miss pairs produce proposals; deterministic IDs stable across identical inputs; empty context yields empty list.
- Boundary tests: no imports or calls into resume-core/career-store; proposals never carry persisted-relationship or official-truth markers.
- E2E fixture: proposal emitted → resume-core validates → only then does a relationship exist anywhere.

## Alternatives Considered **[REQUIRED]**

- **Embed equivalence suggestions inside extraction/rewrite outputs.** Rejected by RKIT-A-0003: conflates unrelated proposal types, is untestable in isolation, and is precisely the shape the spec gap left unbuildable — the dedicated surface is the decided fix.
- **Grow the deterministic alias table instead of a semantic surface.** Rejected: the product already has deterministic aliases; this responsibility exists precisely for the pairs aliases miss, and a closed table cannot propose novel equivalences (the same closed-world failure the audit documented in extraction).
- **Bundle entailment review into this initiative since both are "semantic relationship" work.** Rejected: entailment is explicitly optional post-MVP (vision section 8; RKIT-A-0003 item 5); bundling a speculative capability with a required one invites scope creep — the in/out split above is the boundary.

## Implementation Plan **[REQUIRED]**

1. Equivalence proposal DTO plus prompt/schema assets and fake-adapter fixtures.
2. `proposeEquivalences(context)` implementation through the adapter with deterministic IDs.
3. `agent_surface.json` extension plus guardrail coverage for the new surface.
4. TEST_SPEC extension (public-surfaces entry, contract cases) and package contract tests.
5. E2E fixture wiring the proposal → resume-core validation handoff.

## Dependencies / Blocked Status

Blocked by RKIT-I-0016 (`blocked_by: ["RKIT-I-0016"]`) — consumes the `ModelAdapter`, fake runtime, and schema-validation seam. The former RKIT-A-0003 block is lifted: the ADR was decided 2026-08-13 and settles the surface placement (new public API) and the validate/store ownership this initiative implements against; RKIT-A-0006 authorizes the TEST_SPEC/manifest extensions.
