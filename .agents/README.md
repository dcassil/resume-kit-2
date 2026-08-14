# Agent Implementation Entry

Use this entry for every implementation agent before assigning package work.

## Starter Instruction

Read `IMPLEMENTATION_PLAN.md`, `CONTRACT_SURFACE_ALIGNMENT.md`, and your package `TEST_SPEC.md`.

Do not modify guards, boundaries, manifests, fixtures, or gates without express user permission.

Make one contract test group green at a time. Keep the first implementation small and contract-driven, then broaden only after the package guardrail and boundary tests pass.

Before handing back, run the package guardrail itself, not just a smoke check, and report the result.

After edits, run only `python3 -m unittest tests.contract.test_<package>_contract tests.boundary.test_<package>_guardrails` (explicit module names — unittest does not glob dotted names; requires a prior `pip install -e .` from the repo root); if it fails, fix before final. Do not run repo-wide gates. Do not edit guardrails/manifests/tests.

For `resume-core`, avoid bare/helper names and method calls matching `normalize(`, `validate(`, `sanitize(`, `score(`, `get(`, `rank(`, or `apply(` unless it is an allowed public API. The guard scanner inspects public definitions/exports, but workers should still avoid names that make ownership unclear.

## Required Handoff Note

Every agent must leave a handoff note with:

- Package or folder implemented.
- Tests made green.
- Remaining failures and whether they are expected TDD failures or real regressions.
- Guardrail status before and after edits.
- Boundary test status.
- Contract questions or ownership concerns.
- Files changed.

## Frozen Package Imports

Do not invent import names or package layout.

Use the import names frozen in `pyproject.toml`:

- `resume_core`
- `career_store`
- `career_mcp`
- `resume_agent`
- `resume_cli`
- `resume_plugin`
- `resume_render`
- `workflow`

If a package boundary or import name seems wrong, stop and ask the user before changing it.
