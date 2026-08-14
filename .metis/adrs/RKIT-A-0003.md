---
id: 001-resume-agent-live-model-runtime
level: adr
title: "Resume-Agent Live Model Runtime and Semantic Equivalence Surface"
number: 1
short_code: "RKIT-A-0003"
created_at: 2026-08-13T20:41:36.772033+00:00
updated_at: 2026-08-13T21:40:48.766320+00:00
decision_date: 2026-08-13
decision_maker: Daniel Cassil
parent: 
archived: false

tags:
  - "#adr"
  - "#adr"
  - "#phase/decided"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Resume-Agent Live Model Runtime and Semantic Equivalence Surface

## Context **[REQUIRED]**

resume-agent can be provider-neutral with deterministic fakes, but live model binding and semantic-equivalence API placement are not specified. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

1. **Adapter architecture.** resume-agent owns a provider-neutral `ModelAdapter` protocol: context plus output JSON schema in, schema-validated structured proposal out. Adapters carry model id, adapter version, and runtime config as metadata on every result.
2. **First live runtime: Anthropic Claude API** via the official SDK. Model name is configurable with a current Sonnet-class default; temperature 0 (or minimum supported variability) for extraction/interpretation calls.
3. **Configuration.** Model name, schema mode, timeout, retries, and cost ceilings live in a resume-agent-owned `agent` block of workspace `config.json`, schema-validated at load and included in the run-manifest config hash.
4. **Official gates never call live models.** Contract, boundary, smoke, and E2E suites run against a `DeterministicFakeAdapter` with fixture-pinned outputs. Live-model quality checks live in a separate opt-in eval harness that is not part of protected gates.
5. **Semantic equivalence surface: a new public API.** `proposeEquivalences(context)` returns proposal DTOs (term pair, direction, rationale, evidence refs, confidence). resume-core validates every proposal before use, and confirmed equivalences persist as career-store relationships. (Open question 4 was already settled by the CONTRACT_SURFACE_ALIGNMENT responsibility matrix — resume-core validates, career-store stores relationships — restated here, not re-decided.) Entailment review remains optional post-MVP; RKIT-I-0020's mandatory scope is equivalence proposals only.
6. **Model-call audit metadata.** Every call records adapter id/version, model id, prompt/schema hashes, retry count, and a failure taxonomy (timeout, schema_invalid, refused, provider_error); run manifests reference these records.

Decided 2026-08-13 by Daniel Cassil (provider ratified in session; architecture derived from PRODUCT_VISION_AND_CONTRACTS.md sections 8 and 12 and the Determinism Gate).

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Outcome |
|--------|------|------|---------|
| Claude API behind a provider-neutral adapter | Best available semantic extraction/rewrite quality; neutral seam preserves provider optionality; deterministic fakes keep gates reproducible | API key management and per-call cost | **Chosen** |
| Local model first (Ollama or similar) | No key or per-call cost | Materially weaker semantic extraction — the package's entire purpose; still needs the same adapter work | Rejected |
| Defer live binding indefinitely | Zero cost now | Product stays fixture-only; the DoD's semantic steps (arbitrary resume/JD extraction, real rewrites) stay unreachable | Rejected |
| Embed equivalence proposals inside existing extraction/rewrite outputs | No new public surface | Conflates unrelated proposal types; untestable in isolation; TEST_SPEC already requires the behavior but defines no surface — the reason it was never built | Rejected (new public API chosen) |

## Rationale **[REQUIRED]**

Sections 8 and 12 make the agent a proposal engine whose outputs are schema-validated before use; a provider-neutral adapter with a deterministic fake satisfies the Determinism Gate (same state/config, same official outputs) while the Claude API supplies the real semantic capability the current fixture-tuned regex engine lacks. Separating protected gates (fake adapter) from quality evaluation (opt-in live harness) keeps the test suite deterministic without pretending the product has no model. A dedicated `proposeEquivalences` surface makes a currently-untestable TEST_SPEC requirement testable.

## Consequences **[REQUIRED]**

### Positive
- All six resume-agent initiatives unblock: the adapter/fake foundation (RKIT-I-0016) and its dependents, RKIT-I-0020's surface placement, and RKIT-I-0021's audit metadata are all decided.
- Protected gates stay deterministic (fake adapter), satisfying the Determinism Gate while enabling real semantic capability.

### Negative
- The Anthropic SDK becomes a runtime dependency of the live path; API-key management and cost controls become real operational concerns.
- `agent_surface.json` and contract tests need extension for adapter metadata and the new `proposeEquivalences` surface (protected-surface edits authorized by RKIT-A-0006).

### Neutral
- Additional providers can be added behind the same adapter without a new ADR unless contracts change.
- The opt-in live eval harness is new, non-gating infrastructure.

## Resolved Questions

- First provider/runtime → Anthropic Claude API behind a provider-neutral `ModelAdapter`.
- Configuration location → a resume-agent-owned `agent` block in workspace `config.json`, validated at load and included in the config hash.
- Equivalence embedded vs new API → a new public `proposeEquivalences(context)` surface.
- Which package validates equivalences → already settled by the CONTRACT_SURFACE_ALIGNMENT responsibility matrix (resume-core validates; career-store stores confirmed relationships); restated, not re-decided.
- Audit metadata for failed/retried calls → adapter id/version, model id, prompt/schema hashes, retry count, failure taxonomy (timeout, schema_invalid, refused, provider_error).

## Blocks

- RKIT-I-0016 Resume-Agent Proposal Model Adapter Foundation — lifted (decided)
- RKIT-I-0020 Resume-Agent Semantic Equivalence and Entailment Proposal Handoff — lifted (decided)
- RKIT-I-0021 Resume-Agent Auditability, Determinism, and Evaluation Fixtures — lifted (decided)
- Transitive via the prose dependency chain: RKIT-I-0017, RKIT-I-0018, RKIT-I-0019 — lifted (decided)