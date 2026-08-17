---
id: resume-agent-targeted-interview
level: initiative
title: "Resume-Agent Targeted Interview Question and Answer Interpretation Adapter"
short_code: "RKIT-I-0018"
created_at: 2026-08-13T20:41:37.241414+00:00
updated_at: 2026-08-17T17:00:58.608294+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0016]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-agent-targeted-interview
---

# Resume-Agent Targeted Interview Question and Answer Interpretation Adapter Initiative

## Context **[REQUIRED]**

Package: `resume-agent`. The interview surface is implemented but shallow and actively defective. `generateClarificationQuestion` is three canned question strings keyed on "aws"/"graphql"/"architecture" substrings plus one generic template (`resume_agent/__init__.py:539-547`). `interpretUserAnswer` produces fact proposals only for those same three topic substrings; any other topic yields zero fact proposals and "unknown" resolutions (:594-621), and its AWS service list is a hardcoded 7-item fixture list (:595).

Two gate violations are live in this exact surface, both verified empirically:

1. **Honesty Gate.** The answer "No, I have never used AWS professionally" produces a POSITIVE fact proposal "AWS experience" with suggested_state `possible_match` — :594-601 has no negation gating and :623-633 only handles "staff". The agent proposes a claim the user explicitly denied (CONTRACT_SURFACE_ALIGNMENT.md:330, "any generated claim without grounding").
2. **Persistence Gate.** `generateClarificationQuestion` accepts `already_verified_fact_ids` and merely echoes them back, re-asking the identical canned question (:535-537, :556) — violating TEST_SPEC :52 and CONTRACT_SURFACE_ALIGNMENT.md:344 ("already verified facts are not re-asked").

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Model-phrased clarification questions for code-selected topics through the RKIT-I-0016 `ModelAdapter` — any topic, not three substrings; the code-owned orchestrator picks what to ask about, the agent only phrases it (no fishing expeditions).
- Model-based answer interpretation into the section 8 schema — `{requirementResolutions, factProposals, evidenceProposals}` — for arbitrary topics.
- **Negation handling (Honesty Gate):** an explicit denial produces a requirement-resolution proposal recording explicit absence and zero positive fact proposals — closing the verified AWS-denial defect.
- **`already_verified_fact_ids` honored (Persistence Gate):** verified facts are never re-asked; question generation excludes them and returns a typed no-question-needed result when the topic is already covered.

**Non-Goals:**
- Adapter protocol, fake runtime, config (RKIT-I-0016). Extraction of resumes/JDs (RKIT-I-0017). Rewrite proposals (RKIT-I-0019). Equivalence proposals (RKIT-I-0020). Audit records (RKIT-I-0021).
- No verification authority: suggested states in interpretations are proposals; resume-core decides. No topic selection: which gap to interview is code-owned upstream logic, out of scope here.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

1. **Negation:** for denial answers in multiple phrasings ("No, I have never used X", "I haven't", "not professionally", "only in school"), `interpretUserAnswer` emits no positive fact proposal for the denied claim; explicit absence is modeled in the requirement resolution per RKIT-A-0006 decision 1 (absence is a resolution concern, not a verification state). Fixes `__init__.py:594-601`/:623-633.
2. **Persistence:** `generateClarificationQuestion` never asks about facts in `already_verified_fact_ids` (fixing :535-537, :556); when all candidate facts for the code-selected topic are verified, it returns a typed no-question result instead of a redundant question (TEST_SPEC :52; CONTRACT_SURFACE_ALIGNMENT.md:344).
3. Question phrasing and answer interpretation work for arbitrary topics via the model — retiring the three-substring keying (:539-547) and the topic-limited interpretation (:594-621) with its 7-item AWS list (:595).
4. Interpretation output conforms to the section 8 schema with model-sourced confidence per proposal; all outputs are schema-constrained proposals with `requires_validation` — no verification, scoring, persistence, or mutation.
5. Qualified answers ("yes, but only internal tools") interpret into partial/hedged resolutions with the hedge captured, never flattened into unqualified positives.

## Detailed Design **[REQUIRED]**

- **Question DTO.** Input: code-selected topic, target requirement/fact ids, `already_verified_fact_ids`, context snippets. Output proposal: question text, targeted ids, rationale. A deterministic pre-filter drops targets present in `already_verified_fact_ids` before any model call; an empty remainder short-circuits to the typed no-question result — enforcement is code, not prompt goodwill.
- **Interpretation schema.** `{requirementResolutions, factProposals, evidenceProposals}` per section 8. Each resolution carries a suggested resolution state from the section 4.4 set (per RKIT-A-0006 decision 2) and confidence; each fact proposal carries evidence linkage to the user's answer text and a `verification_state` suggestion per the RKIT-I-0016 manifest fix.
- **Negation semantics.** The prompt contract instructs the model to classify answer polarity (affirmed / denied / qualified / unresponsive); a deterministic post-validation guard rejects payloads containing a positive fact proposal for a claim classified as denied — belt and suspenders, since the Honesty Gate cannot rest on the model alone.
- **Migration.** Canned question strings and topic-substring interpretation are deleted; official gates run `DeterministicFakeAdapter` fixtures covering affirmation, denial, qualification, and off-topic answers.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Negation contract tests (new):** a battery of denial phrasings asserting zero positive fact proposals and an explicit-absence resolution — the defect class the current suite never probes.
- **Persistence contract tests (strengthened):** TEST_SPEC :52's requirement gets real assertions — verified fact ids in, question targeting them never out; fully-covered topic yields the typed no-question result. The current spec let an echo implementation pass.
- **Spec strengthening:** current assertions pin canned fixture answers (AWS "about six years" + five named services, TEST_SPEC :57; GraphQL "around five years" :58) — fixture recall a string table satisfies. Add non-fixture topics and qualified-answer goldens via pinned fake-adapter outputs.
- Schema-conformance tests for the section 8 interpretation shape; guardrail and boundary suites stay green.

## Alternatives Considered **[REQUIRED]**

- **Deterministic negation keyword list ("no", "never", "haven't") bolted onto the current engine.** Rejected: same closed-world trap as the extraction lexicons — "I wish I had", sarcasm, and qualified denials evade any list; polarity is a semantic judgment (model) enforced by a structural guard (code).
- **Prompt-only enforcement of both gates.** Rejected: the Honesty and Persistence Gates are product invariants; they get deterministic pre-filters/post-guards in code, with the model handling only phrasing and semantics.
- **Move already-verified filtering entirely to the upstream orchestrator.** Rejected: defense in depth — the agent surface must be safe against a careless caller, and TEST_SPEC :52 places the observable behavior on this package's surface.

## Implementation Plan **[REQUIRED]**

1. Question/interpretation output schemas plus fake-adapter fixtures (affirm/deny/qualified/off-topic).
2. `generateClarificationQuestion` via the adapter with the deterministic `already_verified_fact_ids` pre-filter and typed no-question result.
3. `interpretUserAnswer` via the adapter emitting the section 8 schema; delete topic-substring paths.
4. Polarity classification plus the deterministic denied-claim post-guard (Honesty Gate enforcement).
5. Contract-test batteries for negation and persistence; spec strengthening with non-fixture goldens.

## Dependencies / Blocked Status

Blocked by RKIT-I-0016 (`blocked_by: ["RKIT-I-0016"]`) — consumes the `ModelAdapter`, fake runtime, and the verification_state manifest fix. The former transitive ADR block is lifted: RKIT-A-0003 was decided 2026-08-13.