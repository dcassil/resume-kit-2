---
id: proposeequivalences-surface-dto
level: task
title: "proposeEquivalences surface: DTO, prompt/schema assets, adapter implementation, guardrail+manifest lockstep, TEST_SPEC, contract tests"
short_code: "RKIT-T-0104"
created_at: 2026-08-17T19:08:37.872604+00:00
updated_at: 2026-08-17T19:20:26.748790+00:00
parent: resume-agent-semantic-equivalence
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0020
---

# proposeEquivalences surface: DTO, prompt/schema assets, adapter implementation, guardrail+manifest lockstep, TEST_SPEC, contract tests

## Parent Initiative

[[RKIT-I-0020]]

## Objective

Build the entire missing `proposeEquivalences(context)` public surface per RKIT-A-0003 item 5, landing the function, its versioned prompt/schema assets, fake-adapter fixtures, `agent_surface.json` declaration, resume-agent TEST_SPEC public-surfaces entry, AND the protected `tools/resume_agent_guardrails.py` ALLOWED_SURFACES edit in ONE lockstep change — day-one manifest coverage, no drift window. Protected edits are authorized under the no-verify workflow (commit `--no-verify`; Daniel re-registers straight-jacket locks in one later pass).

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] Versioned output schema `resume-agent.equivalence-proposal.v1` (in a new `_equivalence_schemas.py`, mirroring sibling schema modules): list of proposal DTOs, each EXACTLY `{id, term_a, term_b, direction, rationale, evidence_refs, confidence, requires_validation}` with `direction ∈ {equivalent, narrower_than, broader_than}` (closed enum), `requires_validation` const `true`, non-empty rationale, `evidence_refs` non-empty and resolving into the supplied context, model-sourced `confidence` (same confidence vocabulary as sibling surfaces — check `_rewrite_schemas.py`/`_interview_schemas.py` and match).
- [ ] Versioned prompt asset `prompts/resume-agent.equivalence-proposal@v1.txt` + deterministic builder module (mirror `_rewrite_requests.py` style); packaged via existing package-data glob (verify it's included; extend pyproject only if the glob misses it).
- [ ] `proposeEquivalences(context)` public function in `resume_agent/__init__.py`: context carries code-selected candidate material (resume wording, JD wording, alias misses); typed validation_error on missing/malformed context; EMPTY candidate context returns `[]` (empty list, NOT an error, NO adapter call); runs through the ModelAdapter with the `context["_adapter"]` injectable seam like siblings; deterministic evidence-linked proposal IDs consistent with the package's existing sha-based ID discipline; deterministic post-guard: every proposal's `evidence_refs` must resolve into the supplied context and `direction`/`requires_validation` are re-checked in code (belt and suspenders like I-0019's grounding guard) — violations are typed errors, never silently dropped.
- [ ] Fake-adapter fixtures under `fixtures/resume-agent/fake-adapter/` covering: an alias-miss pair (e.g. "responsive web apps" ↔ "responsive design", equivalent), a subsumption pair (React narrower_than JavaScript framework experience), and an empty-candidates input if a fixture is even needed for it (it must NOT call the adapter). Self-validating like existing fixtures.
- [ ] LOCKSTEP protected edits (direct edit + `git commit --no-verify`, per the approved workflow): `tools/resume_agent_guardrails.py` ALLOWED_SURFACES += `"proposeEquivalences"` (line ~23, alongside proposeRewrite) AND the guidance string at line ~247 updated to name the six functions. NO other guardrail logic changes. `resume-agent/agent_surface.json` gains the function entry + DTO field list matching the guardrail's schema expectations (study how the five existing entries are shaped, incl. any per-surface required text like the :174 "validation" mention rule — check whether proposeEquivalences trips any name-based rule).
- [ ] resume-agent/TEST_SPEC.md: `proposeEquivalences` joins the public-surfaces list (:9-13 area); contract cases added making the :5/:113 sentences testable (DTO conformance, requires_validation always true, direction vocabulary enforced, evidence refs resolve, empty context → empty list, deterministic IDs across identical inputs), each naming its covering test.
- [ ] Contract/unit tests (non-protected; bridge via test_resume_agent_adapter_contract or own gate-run module): all the TEST_SPEC cases above + alias-miss fixture produces proposals + no persisted-relationship/official-truth markers on any proposal + call-audit records emitted for equivalence calls (T-0101 chokepoint covers it automatically — assert once).
- [ ] Entailment ships NOTHING: no function, schema field, manifest entry, or dormant half-surface (grep-proof "entail" absent from new code).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. `straight-jacket verify` will report mismatches for the 2 protected files — EXPECTED and authorized; report them for Daniel's single re-registration pass.

## Implementation Notes

### Technical Approach
Mirror the I-0019 rewrite surface end to end (schema module, request builder, public function with typed input contract, deterministic post-guard, fixtures) — it is the closest sibling and already passed audit scrutiny. The guardrail's :114/:133 checks compare TEST_SPEC's declared functions and agent_surface.json entries against ALLOWED_SURFACES — all three must move in this one commit or gates go red.

### Dependencies
RKIT-I-0016 adapter substrate; T-0101 call-audit (already emits for every adapter call).

### Risk Considerations
The guardrail parses TEST_SPEC to extract declared public functions — match the exact declaration format of the existing five. Check tests/boundary/test_resume_agent_guardrails.py (protected, READ-ONLY) for the expectations the guardrail test itself pins; if that boundary test hardcodes the five-function set, it too needs the lockstep edit (add to the no-verify batch and report it).

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*