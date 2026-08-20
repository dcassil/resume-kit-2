# resume-cli Test Spec

## Contract

`resume-cli` is the local reference orchestrator. It initializes workspaces, accepts files/input, calls package APIs in order, persists workflow artifacts, asks interactive terminal questions, shows reports, invokes agents when needed, invokes render/export, and enforces checkpoints.

It must orchestrate through public APIs only. It must not duplicate scoring, persistence rules, schemas, mutation logic, renderer semantics, or plugin behavior.

Required command surface:

- `resume init`
- `resume ingest <file>`
- `resume job ingest <file-or-url-text>`
- `resume match`
- `resume resolve`
- `resume tailor`
- `resume validate`
- `resume export --format docx`
- `resume run <resume> <job>`
- `resume inspect fact <id>`
- `resume inspect requirement <id>`
- `resume audit`

## Expected Workspace

```text
./config.json
./resume/base.json
./resume/working.json
./job/current.json
./data/career.db
./operations/
./reports/
./output/
```

## Command Test Cases

### terminal entrypoint and envelope

- `python -m resume_cli init` renders a sectioned human report on stdout and returns exit code 0.
- `python -m resume_cli status` renders initialized workspace state on stdout after `init`.
- `python -m resume_cli --json init` emits the machine envelope with `status`, `exit_code`, `artifacts`, `report`, and `errors`.
- Domain validation failures emit typed error records on stderr and return exit code 1.
- Usage/config failures emit typed error records on stderr and return exit code 2.
- The install metadata declares `[project.scripts] resume = "resume_cli.cli:main"`; installed console-script smoke may exercise it when the editable environment exposes it.
- Presentation renders the returned envelope only; it does not reconstruct domain content from workspace files.

### init

- Creates the expected workspace folders/files.
- Writes the section-13-complete default `config.json`: `matching.scoreAutoThreshold`, `matching.weights.*`, `matching.requireHardRequirementsResolved`, `resume.targetPages`, `resume.sectionOrder`, `resume.skills.{min,max}`, `resume.experience.{min,max}`, `resume.bulletsPerRole.{min,max}`, `guardrails.allow_inferred_facts`, and the RKIT-A-0003 `agent` block.
- Default config values are sourced from the owning package defaults (`resume_core.matching_config`, `resume_core.resume_config`, `resume_core.guardrails_config`, `resume_agent._agent_config`) with a consistency test so CLI defaults cannot drift.
- Loads config through parse -> schema validation -> freeze -> hash before commands consume it.
- Creates SQLite database or prepares it for migration through career-store.
- Embeds career-store `getMigrationState()` verbatim in the result and persisted workspace run artifact.
- Records config/schema versions.
- Re-running init is safe and does not destroy existing data.
- Returns the stable result envelope: `{status, exit_code, artifacts, report, errors}`.

### config validation

- Unknown top-level keys fail with a typed error naming the key path.
- Unknown nested keys in `matching`, `matching.weights`, `resume`, resume min/max ranges, `guardrails`, and `agent` fail with owning resolver typed errors naming the key path.
- Legacy flat keys fail with section-13 replacement guidance: `policy` -> `matching.scoreAutoThreshold`/`matching.weights`, `require_hard_resolution` -> `matching.requireHardRequirementsResolved`, `allow_inferred_facts` -> `guardrails.allow_inferred_facts`, `max_skills` -> `resume.skills.max`.
- The run-manifest config hash covers the full validated config including `agent`; a sampled change in each section-13 block changes the hash.

### ingest resume

- Accepts fixture resume input.
- Runs file read -> `sanitizeText` -> `extractResumeSemantics` -> `canonicalResumeFromExtraction` -> `normalizeResume` -> `validateResume` before persistence.
- Produces `resume/base.json`.
- Produces `resume/working.json` semantically equal to base.
- Records base hash.
- Runs canonical validation.
- Runs ATS sanitation.
- Persists candidate career facts through career-store from core-validated extraction `fact_proposals`, not CLI keyword lists or substring searches.
- Off-fixture fake-adapter resume input persists exactly the proposed facts and does not persist unproposed fixture facts such as `fact_azure`; observable coverage:
  `tests/integration/test_resume_ingest_fact_proposals_integration.py::ResumeIngestFactProposalPersistenceTests::test_off_fixture_resume_and_job_ingest_persist_fixture_defined_facts_and_artifacts`.
- Off-fixture ingest is independent of original smoke vocabulary: Python/Spark/Kafka data-engineer fixtures must ingest without requiring React, TypeScript, or Azure terms.
- Empty or failed extraction returns the typed ingest error envelope with `status`, `exit_code`, `errors[]`, `extraction`, `validation`, `sanitation`, `career_facts`, and `checkpoints`; it must not construct fallback resume content.
- Does not allow agent-generated unsupported content into base; observable fabrication guard coverage:
  `tests/integration/test_resume_ingest_fact_proposals_integration.py::ResumeIngestFactProposalPersistenceTests::test_resume_without_stated_title_or_experience_does_not_fabricate_base_content`.
- Does not fabricate default title, company, role, or experience values when the source/extraction omits them.

### job ingest

- Accepts `<file-or-url-text>` as exactly one positional argument.
- URL input case: `http://`/`https://` arguments fetch text through the injectable stdlib URL seam; URL tests stub the fetcher and gates use no live network.
- Pasted-text input case and precedence: existing paths are resolved before URL detection, and any non-path non-URL argument is treated as pasted JD text before sanitation/extraction.
- Sanitizes file, URL, and pasted-text input before extraction.
- Accepts fixture JD input.
- Persists `job/current.json`.
- Classifies required/preferred/contextual requirements.
- Retains source text.
- Normalizes concepts and terminology.
- Validates schema through core.
- Empty or failed job extraction returns the typed ingest error envelope and must not write fallback requirements.

### match

- Runs official scoring through core.
- Searches career-store/MCP for known facts.
- Emits requirement-level reasoning.
- Produces deterministic output for identical state/config.
- Shows missing/preferred/unresolved requirements distinctly.
- Blocks or routes to resolve when hard requirement policy demands it.
- Persists the full section-4.3 MatchResult fields: `score`, `threshold`, `hardRequirementsResolved`, `dimensions`, `requirement_results`, and tri-state `decision`.
- Passes core `resolution_state` vocabulary through verbatim in persisted JSON and the stdout report, including `related_match`, `possible_match`, and `not_applicable`.
- Treats an empty workspace without resume/job artifacts as a typed failure naming the missing artifact, not an ok zero-score match.

### resolve

- Delegates unresolved requirement/topic selection to `resume-core.getUnresolvedRequirements` without CLI ordering, tie-breaking, or fallback requirement IDs.
- Uses agent only to phrase questions.
- Accepts simulated answers through the `TerminalIO` seam.
- Interprets answers into structured proposals.
- Persists verified facts through career-store only after explicit confirmation.
- Re-runs match after each resolution.
- Returns a typed no-unresolved result when core has no selected unresolved requirement.

### TerminalIO seam

- `TerminalIO.ask(question) -> answer` and `TerminalIO.confirm(summary) -> bool` are injected into command dispatch.
- Interactive mode binds stdin/stdout/stderr for real TTY usage.
- Scripted mode consumes a fixed answer stream deterministically for contract and smoke tests.
- Resolve semantics beyond seam wiring are owned by RKIT-I-0037.

### tailor

- Builds deterministic selection plan.
- Invokes agent for rewrite proposals only.
- Persists operations separately.
- Validates operations through core before applying.
- Does not mutate `resume/base.json`.
- Applies only valid operations to `resume/working.json`.
- Records rejected operations in audit.

### validate

- Runs final match.
- Runs grounding audit.
- Runs ATS checks.
- Runs structure and length checks.
- Runs duplicate/repetition checks.
- Confirms no unverified inferred fact is in the final resume.
- Confirms unresolved requirements are not falsely marked resolved.

### export

- Invokes renderer.
- Writes Markdown and DOCX outputs for smoke/release targets.
- Records renderer template version.
- Handles overflow by returning to selection/rewrite rather than truncating.
- Runs render validation.

### run

- Executes the same checkpoints as individual commands.
- Does not skip validation because an agent says output looks correct.
- Produces the same final artifacts as explicit command sequence when state/config are equivalent.

### inspect and audit

- `inspect fact` shows fact, verification state, evidence, relationships, and conflicts.
- `inspect requirement` reads persisted artifacts only: `reports/match.json` for the requirement `resolution_state` and evidence, plus store `getFact` lookups for referenced fact IDs.
- `inspect requirement` never computes or defaults a requirement resolution state; a fresh workspace or missing persisted match state returns `status: no_data` with `exit_code: 0`.
- `audit` reconstructs run identity, config hash, schema/model versions, scores, questions, facts, operations, validations, and outputs.

## Boundary Tests

- Fail if CLI contains independent scoring logic.
- Fail if CLI writes career DB tables directly.
- Fail if CLI applies resume mutations without `resume-core`.
- Fail if CLI renderer path changes semantic content.
- Fail if CLI/plugin behavior diverges for the same domain workflow.

## Smoke Coverage

The smoke fixture must run through:

1. init
2. ingest
3. career fact persistence
4. MCP/store search
5. job ingest
6. match
7. resolve
8. tailor
9. hallucination rejection
10. apply valid changes
11. validate
12. match working
13. export Markdown and DOCX
14. audit

## E2E Coverage

The E2E fixture must prove:

- complete Job A flow,
- immutable base,
- persisted facts,
- grounded operations,
- final validation,
- render validation,
- audit reconstruction,
- Job B reuse of learned facts without duplicate questioning,
- failure recovery from persisted deterministic state.
