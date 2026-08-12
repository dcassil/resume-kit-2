# Project Structure and Test Strategy

This project is organized around the contract in `PRODUCT_VISION_AND_CONTRACTS.md`, not around any inherited implementation. Each top-level folder maps to a package, workflow support area, or test-support surface named by the product contract and validated by `SMOKE_TEST.md` and `E2E_TEST.md`.

The central rule for every folder is:

> Agent language is proposal-only. Code owns facts, scoring, persistence, mutation, validation, workflow state, and auditability.

## Folder Structure

```text
resume-core/
career-store/
career-mcp/
resume-agent/
resume-render/
resume-cli/
resume-plugin/
workflow/
fixtures/
tests/
tools/
```

## Runtime Package Convention

Top-level folders keep the contract names from the product architecture. Python imports use snake_case runtime package names inside those folders.

| Folder | Python import |
|---|---|
| `resume-core/` | `resume_core` |
| `career-store/` | `career_store` |
| `career-mcp/` | `career_mcp` |
| `resume-agent/` | `resume_agent` |
| `resume-cli/` | `resume_cli` |
| `resume-plugin/` | `resume_plugin` |
| `resume-render/` | `resume_render` |
| `workflow/` | `workflow` |

Rules:

- Runtime packages are installed from the root `pyproject.toml`.
- Hyphenated folders are ownership/documentation boundaries; they are not Python import names.
- Each hyphenated package folder contains exactly one public snake_case package at `<folder>/<import_name>/`.
- Cross-package code imports public package names only, for example `import resume_core` or `from career_store import ...`.
- Private implementation modules use `_`-prefixed package paths and must not be imported across package boundaries.
- Do not add per-folder `pyproject.toml`, local `sys.path` mutation, or alternate package roots unless this contract changes.
- Shared DTOs and JSON schema fragments live in package-owned `schemas.py` modules. Import `Result`, `Error`, resume/job/match/change DTOs, and `VerificationState` from `resume_core`; import `Fact`/`CareerFact` and `Evidence` from `career_store`; import `RunManifest` from `workflow`.

The canonical current test command is:

```sh
python3 tools/run_tests.py --root .
```

That command creates an isolated editable install from `pyproject.toml` before running the current executable contract and boundary suite. Future package API contracts remain available under `tests/contract/` and should be added to the canonical runner as implementations land.

## Folder Purposes

| Folder | Purpose | Primary contract source |
|---|---|---|
| `resume-core/` | Deterministic schemas, normalization, validation, matching, grounding, selection, and change application. | Product sections 3, 4, 12, 13, 14 |
| `career-store/` | Local SQLite career knowledge, evidence, verification state, conflict detection, and transactional persistence. | Product section 5 |
| `career-mcp/` | Narrow semantic MCP surface over career-store with no raw SQL or unrestricted mutation. | Product section 6 |
| `resume-agent/` | Schema-constrained semantic extraction, questions, answer interpretation, and rewrite proposals. | Product section 8 |
| `resume-render/` | Semantic-neutral Markdown/DOCX/PDF rendering, layout measurement, and rendered-output validation. | Product section 9 |
| `resume-cli/` | Reference orchestrator and command surface for the full local workflow. | Product section 10 |
| `resume-plugin/` | Adapter surface for host/chat/IDE presentation without domain behavior. | Product section 11 |
| `workflow/` | Cross-package state machine, run manifest, checkpoints, recovery, and audit semantics. | Product sections 10, 14, 15, 16 |
| `fixtures/` | Stable resumes, job descriptions, answers, invalid proposals, expected snapshots, and migration fixtures. | `SMOKE_TEST.md`, `E2E_TEST.md` |
| `tests/` | Test-suite organization, required gates, automation tiers, and release pass/fail strategy. | `SMOKE_TEST.md`, `E2E_TEST.md` |
| `tools/` | Local developer/release utilities that run tests, validate fixtures, and enforce architecture boundaries. | Product sections 12, 16, 18 |

## Test Strategy

Tests should be written before new implementation or port adaptation. Ported pieces must pass the same contract tests as newly written pieces, and no port should be trusted merely because it was useful historically.

The test pyramid should be contract-first:

1. Unit tests for deterministic pure behavior.
2. Contract tests for public package surfaces and DTO schemas.
3. Boundary tests for dependency direction and forbidden responsibilities.
4. Integration tests for package interaction with isolated temp state.
5. Smoke test for the primary happy path and honesty guardrails.
6. E2E test for persistent learning, second-job behavior, recovery, render validation, and audit reconstruction.

## Release-Blocking Gates

The following failures block release:

- Base resume mutation after ingest.
- Verified-state escalation without explicit source support or user confirmation.
- Nondeterministic official scoring from identical state/config.
- Unsupported claim accepted into working or final resume.
- Raw SQL or unrestricted mutation exposed through MCP.
- Agent directly applying career-store or resume mutations.
- Renderer silently changing semantic content.
- Learned verified facts lost between Job A and Job B.
- Duplicate questioning for already verified equivalent facts without a legitimate new specificity need.
- Unresolved hard requirement falsely reported as resolved.

## Documentation Rule

Each folder owns exactly one Markdown test-spec document at this stage. The document describes:

- contract surface,
- expected structure,
- validation gates,
- determinism rules,
- concrete test cases,
- smoke/E2E coverage,
- non-responsibilities and forbidden behavior.
