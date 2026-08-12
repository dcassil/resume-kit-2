# Implementation Plan

This is the build playbook for agents implementing `resume-kit-2`.

Primary authority, in order:

1. Current user instructions.
2. `CONTRACT_SURFACE_ALIGNMENT.md`.
3. The target package `TEST_SPEC.md`.
4. The target package surface manifest.
5. `PRODUCT_VISION_AND_CONTRACTS.md`, `SMOKE_TEST.md`, and `E2E_TEST.md` for cross-package behavior.

Do not use prior `resume-kit` behavior as authority.

## Non-Negotiable Rules

- Do not modify guardrails, boundary tests, surface manifests, fixture truth, or suite gates without express user permission.
- Do not weaken, skip, delete, or rewrite tests to make implementation pass.
- Do not add hidden business logic to `tests/`, `tools/`, fixtures, manifests, or adapters.
- Do not bypass package ownership. If a package does not own a behavior, call the public owner API or add the missing public contract with user approval.
- Do not write direct SQLite/table mutations outside `career-store`.
- Do not mutate `resume/base.json` after ingest unless the user explicitly re-ingests.
- Do not trust agent output as truth, verification, scoring, workflow state, or mutation authority.
- Do not fabricate skills, titles, years, metrics, scale, management scope, outcomes, or equivalences.
- Do not treat related facts as exact or verified matches.
- Do not render, truncate, or rewrite semantic resume content inside renderer/export paths.
- Do not expose raw SQL tools or unrestricted mutation surfaces.

## Implementation Order

Build in this order:

1. `resume-core`
2. `career-store`
3. `career-mcp`
4. `workflow`
5. `resume-agent`
6. `resume-render`
7. `resume-cli`
8. `resume-plugin`

The reason is ownership: truth and persistence must exist before adapters and delivery surfaces.

## Package Work Loop

For each package:

1. Read `CONTRACT_SURFACE_ALIGNMENT.md`.
2. Read the package `TEST_SPEC.md`.
3. Read the package surface manifest.
4. Run the package guardrail before editing.
5. Run that package's contract suite and confirm it fails for the expected missing implementation.
6. Write the smallest contract-driven implementation that makes one contract test or one cohesive test group green.
7. Run that package's contract suite again.
8. Run that package's boundary tests and guardrail.
9. Repeat until the package contract suite is green.
10. Run the broader gate with `python3 tools/run_gate.py --pr --root .`.

Only move to the next package when the current package's contract tests, boundary tests, and guardrail are green.

## Agent Handoff Rules

When handing work to another agent, include:

- The exact package or folder being implemented.
- The authoritative files already read.
- The current expected red/green state for that package.
- The exact test command the agent should make green first.
- The exact guardrail command the agent must run before and after edits.
- The focused final command: `python -m unittest tests.contract.test_<package>*contract tests.boundary.test*<package>_guardrails`.
- Any known blockers, assumptions, or intentionally deferred behavior.

Agents receiving a handoff must:

- Implement only the named package or folder unless the user explicitly expands scope.
- Start by running the named package guardrail and package contract suite.
- Make one test group green at a time before broadening scope.
- Keep the first implementation small and contract-driven; do not write broad modules before the first focused contract group is green.
- After edits, run only `python -m unittest tests.contract.test_<package>*contract tests.boundary.test*<package>_guardrails`; if it fails, fix before final. Do not run repo-wide gates. Do not edit guardrails/manifests/tests.
- Preserve all existing guards, boundary tests, manifests, fixture truth, and suite gates.
- Report whether remaining failures are expected TDD failures or real regressions.
- Stop and ask the user before changing cross-package contracts, ownership boundaries, or fixture truth.

## Guardrail Policy

Guardrails and boundary tests are product safety infrastructure. Treat failures as design feedback.

For `resume-core`, avoid bare/helper names and method calls matching `normalize(`, `validate(`, `sanitize(`, `score(`, `get(`, `rank(`, or `apply(` unless it is an allowed public API. Public helpers with those prefixes must be private or folded behind an allowed surface.

Allowed:

- Fix implementation code to satisfy a guardrail.
- Add missing public API implementation that a contract test requires.
- Add package-local helpers behind existing public surfaces.
- Add tests for newly implemented behavior if they strengthen the contract.

Not allowed without explicit user permission:

- Editing `*_guardrails.py` to permit current implementation.
- Editing `tests/boundary/*` to remove a forbidden-behavior check.
- Editing `tests/contract/*` to reduce required behavior.
- Editing `*_surface.json`, `fixture_manifest.json`, `suite_manifest.json`, or `tool_manifest.json` to shrink scope.
- Changing fixture truth to make hallucination or persistence tests easier.
- Marking failing tests skipped, xfail, or always-green.

## Test Strategy

Work from narrow to broad:

1. Package contract suite.
2. Package boundary suite.
3. Package guardrail.
4. Related integration or fixture tests.
5. `python3 tools/run_gate.py --pr --root .`.

For focused package workers, use only the package contract plus package boundary guardrail command:

```bash
python -m unittest tests.contract.test_<package>*contract tests.boundary.test*<package>_guardrails
```

Do not run repo-wide gates from worker prompts unless the handoff explicitly says the package is complete and ready for orchestration-level validation.

Use the full future contract command only when the relevant implementations exist:

```bash
python3 -m unittest discover -s tests/contract
```

The opt-in future package acceptance gate is:

```bash
python3 tools/run_gate.py --future-contract --root .
```

It covers the resume-core and career-store contract targets plus their package boundary guardrail tests. `python3 tools/run_gate.py --pr --root .` remains the current PR gate until those future package contracts are implemented.

Until then, red contract tests for unimplemented packages are expected TDD signals, not regressions.

## Completion Criteria

A package is done when:

- Its public module imports successfully.
- Its public API matches the surface manifest.
- Its contract tests pass.
- Its boundary tests pass.
- Its guardrail passes.
- It does not introduce new failures in `python3 tools/run_gate.py --pr --root .`.
- Its behavior follows the ownership table in `CONTRACT_SURFACE_ALIGNMENT.md`.

The whole system is done when:

- All package contract suites pass.
- All guardrails pass.
- PR, main, and release-candidate gates pass.
- Smoke and E2E fixtures prove persistence, honesty, determinism, rendering neutrality, and audit reconstruction.
