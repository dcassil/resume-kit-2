---
id: 001-resume-agent-live-model-runtime
level: adr
title: "Resume-Agent Live Model Runtime and Semantic Equivalence Surface"
number: 1
short_code: "RKIT-A-0003"
created_at: 2026-08-13T20:41:36.772033+00:00
updated_at: 2026-08-13T20:41:36.772033+00:00
decision_date: 
decision_maker: 
parent: 
archived: false

tags:
  - "#adr"
  - "#phase/draft"
  - "#adr"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Resume-Agent Live Model Runtime and Semantic Equivalence Surface

## Context **[REQUIRED]**

resume-agent can be provider-neutral with deterministic fakes, but live model binding and semantic-equivalence API placement are not specified. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

Pending. Resolve the open questions below before decomposing blocked initiatives into tasks or implementing runtime-specific behavior.

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Risk Level | Implementation Cost |
|--------|------|------|------------|---------------------|
| Minimal local contract | Keeps first build small and testable | May require later migration | Medium | Low |
| Full production runtime now | Clarifies packaging and acceptance early | Higher design/dependency risk | Medium | Medium |
| Defer capability | Avoids premature assumptions | Leaves listed initiatives blocked | Low | Low |

## Rationale **[REQUIRED]**

The available docs establish boundaries and invariants, but not this concrete product/runtime decision. Capturing it as an ADR prevents hidden assumptions from leaking into implementation tasks.

## Consequences **[REQUIRED]**

### Positive
- Blocked scope is explicit before task decomposition.
- Unblocked hardening initiatives can still proceed.

### Negative
- Some initiatives cannot be decomposed until this ADR is resolved.

### Neutral
- Revisit this ADR when planning the blocked initiatives.

## Open Questions

- Which live model provider/runtime is supported first?
- Where are model name, schema mode, timeout, retry, and cost controls configured?
- Should semantic equivalence proposals be embedded in existing outputs or added as a new public API?
- Which package validates accepted equivalence relationships: resume-core, career-store, or both?
- What audit metadata is required for failed or retried model calls?

## Blocks

- Semantic Equivalence and Entailment Proposal Handoff
- Resume-Agent Proposal Model Adapter Foundation
- Agent Auditability, Determinism, and Evaluation Fixtures
