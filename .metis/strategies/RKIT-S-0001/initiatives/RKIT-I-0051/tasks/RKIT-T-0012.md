---
id: req-001b-populate-13-expected
level: task
title: "REQ-001b: Populate 13 expected snapshots with reviewed data"
short_code: "RKIT-T-0012"
created_at: 2026-08-14T03:14:05.466710+00:00
updated_at: 2026-08-14T17:09:07.778618+00:00
parent: executable-release-gate-e2e
blocked_by: [RKIT-T-0011]
archived: false

tags:
  - "#task"
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0051
---

# REQ-001b: Populate 13 expected snapshots with reviewed data

## Parent Initiative

[[RKIT-I-0051]]

## Objective

Replace the prose-stub content of all 13 `fixtures/expected/*.json` snapshots with the real reviewed-baseline envelope — `{schema_version, config_hash, reviewed:true, comment:<former prose>, data:<canonicalized live output>}` — using the generator built in RKIT-T-0011. This turns the fixtures from placeholder observations into deterministic, regenerable golden data that the contract tests and PR gate can enforce, giving the executable release gate real ground truth to compare against.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] All 13 files retain `fixture_id`, `schema_version == "expected-snapshot.v1"`, `config_hash == "fixture-config-v1"`, and `reviewed == true` (so `fixtures_guardrails.validate_expected_snapshots` and `test_fixtures_contract` stay green).
- [ ] Each file gains a `data` field containing canonicalized live output for that stage, OR a documented `data:null` with an owning-initiative link in `comment` for any stage whose producer is not Wave-1-traversable (run-manifest/audit-report if applicable).
- [ ] The former `expected_observations` prose is preserved verbatim under a `comment` field (review intent not lost); the `expected_observations` key is retained if `fixtures_guardrails` still requires it, else migrated — coordinate with REQ-001d so the guardrail and this shape agree.
- [ ] Regenerating via `tools/regenerate_expected_snapshots.py` reproduces the committed `data` blocks exactly (no drift).
- [ ] PR gate stays green after this change.

## Implementation Notes

### Execution Profile

Recommended Agent: opus + medium

Codex-exec autonomously implementable: no — the task requires mandatory human review of generated baseline data before commit and judgment calls on which producers are Wave-1-traversable, which cannot be delegated to autonomous exec.

### Technical Approach

Using the generator from RKIT-T-0011 (REQ-001a), replace the prose-stub content of all 13 `fixtures/expected/*.json` files with the `{schema_version, config_hash, reviewed:true, comment:<former expected_observations prose>, data:<canonicalized live output>}` envelope.

The `data` must come from deterministic `resume_core` outputs at the fixture `config_hash`:

- `normalized-resume` / `normalized-job-a` / `normalized-job-b` — from `normalizeResume` / `normalizeJobModel`.
- The match snapshots (`initial-job-a-match`, `post-aws-match`, `post-graphql-match`, `final-job-a-match`, `job-b-initial-match`) — from `scoreMatch`.
- `selection-plan` — from `rankResumeContent`.
- `valid-operations` / `rejected-operations` — from `validateChange` over the operation fixtures.
- `run-manifest` / `audit-report` — from their current deterministic producers.

Binding approved-decision guidance: where a stage producer is not Wave-1-traversable (e.g. `run-manifest` / `audit-report`), do NOT fabricate data. Leave a documented `data:null` with a `comment` linking the owning Wave-2 initiative instead. Human review of the generated data is a required step before commit — these become the reviewed baseline, so a human must confirm each generated `data` block before it lands.

Fixtures whose data reflects a known product defect are NOT weakened (none expected here for pure normalization).

### Files

- `fixtures/expected/normalized-resume.json`
- `fixtures/expected/normalized-job-a.json`
- `fixtures/expected/normalized-job-b.json`
- `fixtures/expected/initial-job-a-match.json`
- `fixtures/expected/post-aws-match.json`
- `fixtures/expected/post-graphql-match.json`
- `fixtures/expected/final-job-a-match.json`
- `fixtures/expected/job-b-initial-match.json`
- `fixtures/expected/selection-plan.json`
- `fixtures/expected/valid-operations.json`
- `fixtures/expected/rejected-operations.json`
- `fixtures/expected/run-manifest.json` (data:null candidate — link owning Wave-2 initiative if producer is not Wave-1-traversable)
- `fixtures/expected/audit-report.json` (data:null candidate — link owning Wave-2 initiative if producer is not Wave-1-traversable)

### Dependencies

- [[RKIT-T-0011]] — provides the snapshot data envelope, the shared canonicalizing comparator, and the generator (`tools/regenerate_expected_snapshots.py`) this task consumes to produce the `data` blocks. This task cannot start until that generator exists.
- Coordinate with REQ-001d on the `expected_observations` vs `comment` key shape so the guardrail and this fixture shape agree.
- Downstream RKIT-I-0004 consumes these reviewed baselines; the `run-manifest` / `audit-report` `data:null` links point at the owning Wave-2 initiative that produces those stages.

### Risk Considerations

- **Fabrication risk / determinism**: the biggest risk is inventing plausible-looking `data` for a stage whose producer is not actually reachable in Wave 1. The approved decision (documented `data:null` + owning-initiative link) is the mitigation; never synthesize values to fill a blank.
- **Baseline correctness**: these files become the reviewed golden truth — an unreviewed or wrong `data` block silently locks in incorrect behavior. Mandatory human review before commit mitigates this.
- **Scope-boundary bleed**: `run-manifest` / `audit-report` belong to Wave-2 producing surfaces; resolving them fully here would pull Wave-2 work into this task. Keep them as `data:null` with links rather than expanding scope.
- **Cross-key/guardrail drift**: changing `expected_observations` → `comment` without coordinating with REQ-001d could break `fixtures_guardrails`; the shape must be agreed across both tasks.
- **Regeneration drift**: committed `data` must byte-match what the generator reproduces, or the no-drift acceptance criterion fails.

## Verification Steps

1. `python3 tools/regenerate_expected_snapshots.py --root . --write && git diff --stat fixtures/expected/` (regeneration reproduces committed content; empty diff after commit)
2. `python3 -m unittest tests.contract.test_fixtures_contract`
3. `python3 tools/fixtures_guardrails.py --root .`
4. `python3 tools/run_gate.py --pr --root .`

## Status Updates

- 2026-08-14: Codex-driven population of all 13 envelopes with generator data (no data:null needed — run-manifest and audit-report producers are deterministic and Wave-1-traversable). `expected_observations` retained (protected fixtures_guardrails still requires it); `comment` mirrors it verbatim pending REQ-001d migration. Guarded `--write` mode added to the generator. No-drift proven; fixtures_guardrails + PR 198 + smoke green; envelope invariants script-checked.
- Daniel REVIEWED AND APPROVED the baselines 2026-08-14, with two current-behavior quirks knowingly locked in until owning initiatives fix them: (1) job-b-initial-match resolves AWS/GraphQL with empty matched_fact_ids; (2) post-graphql-match resolves GraphQL from resume API evidence rather than fact_graphql (both shallow-scorer behavior, RKIT-I-0002/RKIT-I-0007 territory; update via regenerate + re-review). Committing; marking completed.