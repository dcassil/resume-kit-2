# resume-agent Test Spec

## Contract

`resume-agent` handles language and semantic proposal work only. It may extract semantics, phrase questions, interpret answers into structured proposals, suggest semantic equivalences, and propose rewrites. It must not own truth, scoring, persistence, validation, or mutation.

Relevant public surfaces:

- `extractResumeSemantics(rawText)`
- `extractJobSemantics(rawJobText)`
- `generateClarificationQuestion(context)`
- `interpretUserAnswer(answer, context)`
- `proposeRewrite(context)`

## Expected Structure

Tests should isolate the agent behind deterministic fixtures and schema validators:

- prompt/input builders
- structured output schemas
- extraction proposal adapters
- question generation
- answer interpretation
- rewrite proposal generation
- uncertainty/confidence handling
- forbidden-addition filters

## Contract Test Cases

### Resume semantic extraction

- Extract resume facts from noisy resume text into schema-constrained proposals.
- Preserve source evidence for extracted claims.
- Do not invent AWS, GraphQL, Staff title, metrics, or management scope when absent.
- Mark uncertainty explicitly when extraction is ambiguous.
- Return proposals rather than canonical final resume objects.

### Job semantic extraction

- Extract job title, company if present, seniority, industries, domains, requirements, preferred items, and terminology.
- Preserve source text for every requirement.
- Distinguish required, preferred, and contextual requirements.
- Preserve `8+ years`, React, TypeScript, API architecture/design, responsive design, SaaS, AWS, GraphQL, and tech leadership concepts from fixtures.
- Return schema-constrained proposal output for core validation.

### Clarification questions

- Receive one code-selected unresolved requirement or tight cluster.
- Phrase a targeted question without choosing the requirement itself.
- Ask about AWS, GraphQL, or architecture only when the context selects those topics.
- Avoid broad fishing expeditions.
- Avoid asking again about facts already verified unless new specificity is required.

### Answer interpretation

- Interpret AWS answer into fact/evidence proposals with about six years and listed AWS services.
- Interpret GraphQL answer into verified-use proposals with around five years and production API context where supported.
- Interpret architecture answer into architecture/API-design fact proposals and explicit non-Staff-title information.
- Keep proposals structured.
- Do not directly persist anything.
- Do not mark verification final without store/core validation.

### Rewrite proposals

- Accept context containing original text, allowed facts, job terminology, requirements, prohibited additions, and length/voice constraints.
- Return `ResumeChangeOperation` proposals only.
- Include candidate text, facts used, requirements targeted, terminology changes, and uncertainty where applicable.
- Propose responsive terminology alignment without unsupported scope.
- Propose API-design emphasis only when verified facts support it.
- Propose AWS/GraphQL additions only where supplied verified facts and selection rules allow.

### Forbidden proposals

- Must not output a mutated full resume as the final authority.
- Must not update SQLite or files.
- Must not set official score.
- Must not silently upgrade inferred facts.
- Must not change actual employment title to match a target JD title.
- Must not inflate years, metrics, team size, user scale, or outcomes.

### Schema and validation handoff

- Every agent output validates against expected structured schema.
- Invalid JSON or malformed schema output is rejected before downstream use.
- Missing fact IDs, requirement IDs, target paths, or grounding metadata block operation use.
- Agent uncertainty is preserved and visible to validators.

## Determinism Strategy

Because language models may vary, official tests should stabilize behavior through:

- fixed model/config metadata in manifests,
- structured output schemas,
- golden fixture inputs,
- tolerant assertions on question wording,
- strict assertions on structured proposal fields,
- code-owned deterministic downstream decisions.

The agent may vary phrasing. It may not vary official score, fact verification state, mutation application, or workflow transition.

## Smoke Coverage

The smoke fixture must prove:

- agent extraction returns proposals,
- agent asks a targeted question when selected by code,
- user answer interpretation is structured,
- rewrite output is a change operation,
- hallucinated rewrite is rejected by core rather than trusted.

## E2E Coverage

The E2E fixture must prove:

- semantic equivalence proposals are validated before use,
- interview loop resolves AWS/GraphQL/architecture gaps,
- rewrite operations are grounded,
- invalid adversarial proposals enter audit as rejected,
- second-job run does not repeat questions for learned facts.

