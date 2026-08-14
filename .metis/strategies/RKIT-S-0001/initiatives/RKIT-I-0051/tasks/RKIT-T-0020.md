---
id: req-007b-migration-checker-tool
level: task
title: "REQ-007b: Migration-checker tool for the four migration cases"
short_code: "RKIT-T-0020"
created_at: 2026-08-14T03:14:05.799098+00:00
updated_at: 2026-08-14T03:14:05.799098+00:00
parent: executable-release-gate-e2e
blocked_by: ["RKIT-T-0019"]
archived: false

tags:
  - "#task"
  - "#phase/todo"
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-007b: Migration-checker tool for the four migration cases

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Implement the missing migration-checker tool (`tools/run_migration_checks.py`) that exercises career-store's migration surface across the four migration cases specified in `tools/TEST_SPEC.md` (lines 47-52). Today the `tool_manifest` declares a `migration_checkers` capability with no implementing tool; this task supplies that real tool so the release gate can prove migrations behave correctly.

## Acceptance Criteria

- [ ] `tools/run_migration_checks.py` implements all four cases; exits non-zero if any fails and prints which case failed.
- [ ] Fresh-migrate creates a DB at the current schema version; idempotent re-run leaves the DB unchanged (schema version + state stable); upgrade-from-previous transforms the REQ-007a previous-schema DB into the expected post-migration state; destructive-migration-without-policy is detected as a failure.
- [ ] The tool invokes career-store's public migration API and contains NO scoring/validation/migration business logic of its own (passes tools boundary check).
- [ ] Runs deterministically with isolated temp sqlite (no network, no wall-clock dependence); running twice yields the same result.
- [ ] The tool is registered in `tool_manifest.json` (via REQ-010a) with kind `migration_checker`.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the task crosses the tools/career-store boundary, depends on the public migration API contract, and must satisfy the tools-boundary guardrail against hidden business logic; these architectural constraints require reasoning that is not mechanical.

### Technical Approach

Implement `tools/run_migration_checks.py` as a `migration_checker`-kind tool covering the four cases from `tools/TEST_SPEC.md` lines 47-52 against career-store's migration surface:

1. **Fresh DB migrate** — migrate an empty DB and confirm it lands at the current schema version.
2. **Idempotent re-run** — re-running migration on an already-migrated DB leaves the schema version and state stable (unchanged).
3. **Upgrade-from-previous** — using the REQ-007a previous-schema fixture, confirm the migration transforms the previous-schema DB into the expected post-migration state.
4. **Destructive-migration failure without explicit audited policy** — a destructive migration lacking an explicit audited policy is detected as a failure.

The tool must record the schema version and return non-zero on any failure, printing which case failed.

Binding guidance (approved decision): the tool MUST invoke career-store's PUBLIC migration API only. It must contain NO reimplemented migration/business logic — no raw SQL reimplementation of migration steps, no scoring/validation logic — because that would be hidden business logic living in `tools/` and is blocked by the tools boundary (`tools_guardrails`). Execution must be deterministic: isolated temp directories, isolated temp sqlite databases, no network access, and no wall-clock dependence, so that running the tool twice yields identical output. This tool is the implementing tool that REQ-010a's manifest retains for the `migration_checkers` capability, so it must exist as a real `tools/` entry, and it is registered in `tool_manifest.json` (via REQ-010a / RKIT-T-0016) with kind `migration_checker`.

### Files

- `tools/run_migration_checks.py` (new — the migration-checker tool; kind `migration_checker`)
- career-store public migration API (PROTECTED — READ/INVOKE only, no reimplementation)
- `fixtures/migrations/*` (consumes REQ-007a fixtures)

### Dependencies

- [[RKIT-T-0019]] — REQ-007a authors the migration fixture content spec and the previous-schema `career.db` fixture that case 3 (upgrade-from-previous) consumes; the checker cannot exercise the upgrade path until that fixture exists.
- Semantic links: registration in `tool_manifest.json` is owned by REQ-010a / RKIT-T-0016 (manifest retains the `migration_checkers` capability pointing at this tool). The career-store migration API is owned by its package initiative and is treated as a protected, invoke-only surface here; any xfail/expectation on that surface belongs to the owning package initiative, not this tool. This checker feeds the downstream executable release gate that RKIT-I-0004 threads applied operations through.

### Risk Considerations

- **Protected-surface / boundary constraint**: career-store's migration API is invoke-only. The strongest failure mode is drifting into reimplementing migration logic inside `tools/` to "make it work"; this is hidden business logic, is blocked by `tools_guardrails`, and must be avoided — always call the public API.
- **Cross-package blast radius**: the tool depends on the career-store public migration API contract. If that API shape is unclear, coordinate with the owning package initiative rather than working around it in the tool.
- **Determinism**: any leak of wall-clock, network, or non-isolated filesystem state will make the checker flaky and break the "run twice, identical output" guarantee. Use isolated temp dirs and isolated temp sqlite.
- **Scope-boundary bleed**: fixture authoring (REQ-007a) and manifest registration (REQ-010a) belong to their own tasks; this task consumes the fixtures and is registered by the manifest task — do not duplicate or re-own that work here.

## Verification Steps

1. `python3 tools/run_migration_checks.py --root .` (exit 0, all four cases reported pass)
2. Run twice, confirm identical output (determinism)
3. `python3 tools/tools_guardrails.py --root .` (no hidden-business-logic block)
4. Negative probe: point upgrade-from-previous at a mismatched expected-state, confirm non-zero exit

## Status Updates

*To be added during implementation*