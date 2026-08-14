---
id: req-001d-strengthen-fixtures
level: task
title: "REQ-001d: Strengthen fixtures_guardrails to require data envelope"
short_code: "RKIT-T-0014"
created_at: 2026-08-14T03:14:05.548625+00:00
updated_at: 2026-08-14T03:14:05.548625+00:00
parent: executable-release-gate-e2e
blocked_by: ["RKIT-T-0012"]
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

# REQ-001d: Strengthen fixtures_guardrails to require data envelope

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Strengthen the `validate_expected_snapshots` guardrail in `tools/fixtures_guardrails.py` so the expected-snapshot manifest can never silently regress to prose-only stubs: every snapshot must now carry the structured `data` envelope (or a documented `data:null` + `comment` for deferred stages) and a `comment` field, on top of the existing metadata checks. This makes REQ-001b's populated snapshots the enforced floor, closing the loophole that let reviewed fixtures degrade back to prose without failing the gate.

## Acceptance Criteria

- [ ] `validate_expected_snapshots` requires `data` (present, may be null only with a `comment` explaining deferral) and `comment` on every snapshot, in addition to the existing metadata fields.
- [ ] A snapshot missing `data` is hard-blocked by `python3 tools/fixtures_guardrails.py --root .` with a clear remediation message.
- [ ] `tests/boundary/test_fixtures_guardrails.py` gains a case proving the guardrail rejects a prose-only (data-less) snapshot; no existing assertion is weakened.
- [ ] The straight-jacket manifest is re-registered so verify passes; the change is documented as strengthen-only realignment per RKIT-A-0006.
- [ ] PR gate green.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + high

Codex-exec autonomously implementable: no — the proposal marks this `codexSuitable: false`; it edits two PROTECTED surfaces under strengthen-only constraints, requires straight-jacket re-registration, and must keep its required-field set exactly coordinated with a sibling task, which needs judgment codex-exec should not exercise unattended.

### Technical Approach

- Extend `validate_expected_snapshots` in `tools/fixtures_guardrails.py`. Today it only checks presence of `fixture_id`, `schema_version`, `config_hash`, `reviewed`, and `expected_observations`. Add enforcement that every snapshot also carries:
  - `data` — must be present. It may be `null` **only** when accompanied by a `comment` explaining the deferral (deferred stages); otherwise a populated data envelope is required.
  - `comment` — must be present on every snapshot.
- On violation, hard-block with a clear remediation message so a data-less / prose-only snapshot cannot pass.
- Strengthen the PROTECTED boundary test `tests/boundary/test_fixtures_guardrails.py` by adding a case that proves the guardrail rejects a prose-only (data-less) snapshot. Do not weaken any existing assertion.
- Re-register both edited PROTECTED files in `.straight-jacket/manifest.json` after the change so `straight-jacket verify` passes.
- **Binding decision (approved):** Both PROTECTED files (`tools/fixtures_guardrails.py` and `tests/boundary/test_fixtures_guardrails.py`) are authorized ONLY as strengthen-or-preserve per RKIT-A-0006 — fixture truth is unchanged, and the edits must re-register the straight-jacket. The required-field set here MUST be coordinated exactly with RKIT-T-0012's envelope (REQ-001b), so the required fields and the actual snapshot shape agree exactly.

### Files

- `tools/fixtures_guardrails.py` (PROTECTED — strengthen `validate_expected_snapshots`)
- `tests/boundary/test_fixtures_guardrails.py` (PROTECTED — add assertion that the guardrail rejects a data-less snapshot; strengthen-only)
- `.straight-jacket/manifest.json` (re-register both files after edit)

### Dependencies

- [[RKIT-T-0012]] — REQ-001b populates the 13 `expected/*.json` snapshots with reviewed `data` + moves prose to `comment`. This task's required-field set (`data` / `comment`) must match RKIT-T-0012's envelope exactly, so it is blocked until that shape is settled.
- Downstream semantic link: the strengthened guardrail hardens the expected-snapshot floor consumed by the RKIT-I-0004 validation/E2E work; any xfail relaxation belongs to the owning package initiative, not this task.

### Risk Considerations

- **Protected-surface / straight-jacket constraint:** Both `tools/fixtures_guardrails.py` and `tests/boundary/test_fixtures_guardrails.py` are PROTECTED. Per RKIT-A-0006 these edits are authorized strictly as strengthen-or-preserve — no weakening of existing checks, no change to fixture truth — and require straight-jacket re-registration or `verify` will fail.
- **Coordination / scope-boundary bleed:** The required-field set must agree exactly with RKIT-T-0012's snapshot envelope. A mismatch (e.g. requiring a field REQ-001b did not produce) hard-blocks the whole manifest. Keep the field contract identical; do not introduce fields beyond `data` + `comment`.
- **Cross-package blast radius:** The guardrail gates all 13 expected snapshots; an over-strict rule blocks every fixture at once. Validate against the actual REQ-001b snapshots before finalizing.
- **Determinism:** Enforcement must be purely structural (presence / null+comment) so the gate stays deterministic and reproducible across runs.

## Verification Steps

1. `python3 tools/fixtures_guardrails.py --root .` (green against the REQ-001b snapshots)
2. Negative probe: strip `data` from one snapshot in a temp copy, run the guardrail, confirm hard-block, then restore.
3. `python3 -m unittest tests.boundary.test_fixtures_guardrails`
4. `straight-jacket verify` (manifest re-registered)
5. `python3 tools/run_gate.py --pr --root .`

## Status Updates

*To be added during implementation*