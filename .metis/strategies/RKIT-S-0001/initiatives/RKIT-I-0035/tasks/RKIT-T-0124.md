---
id: section-13-config-contract-unknown
level: task
title: "Section-13 config contract, unknown/legacy key rejection, config hash, real getMigrationState in init"
short_code: "RKIT-T-0124"
created_at: 2026-08-18T23:47:13.801567+00:00
updated_at: 2026-08-19T00:18:33.880508+00:00
parent: resume-cli-runtime-and-workspace
blocked_by: [RKIT-T-0123]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0035
---

# Section-13 config contract, unknown/legacy key rejection, config hash, real getMigrationState in init

## Parent Initiative

[[RKIT-I-0035]]

## Objective

Implement the section-13 configuration contract (RKIT-A-0006 item 6) and honest init (initiative plan steps 4–6): `init` writes a section-13-complete default config validated at load (unknown keys typed-fail; legacy flat keys fail with per-key migration guidance), the run-manifest config hash covers the FULL validated config including the agent block, and `init` reports the real `getMigrationState()` DTO instead of the hardcoded `prepared` literal.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria

- [ ] IMPORTANT — verify current state first: I-0002/0003/0016 already landed `matching.*`, `resume.*`, and `agent` config machinery (resume_config/matching_config/agent_config modules; FIXTURE_CONFIG uses namespaced keys; flat keys are already typed errors in core). This task's job is the CLI-SIDE contract: what `init` WRITES, what config LOAD validates, and the guardrails block. Reuse the existing schemas/validators — do NOT fork a second config vocabulary. Report already-satisfied vs new.
- [ ] `init` writes a default config.json containing EVERY section 13 key: matching.scoreAutoThreshold, matching.weights, matching.requireHardRequirementsResolved, resume.targetPages/sectionOrder/skills/experience/bulletsPerRole min-max rules, guardrails.* block, and the RKIT-A-0003 `agent` block — values matching the packages' existing defaults (consistency test against the owning modules' DEFAULT constants; no drifting duplicates).
- [ ] Config load path: parse → schema-validate (unknown key anywhere = typed failure naming the key path) → freeze → hash. Legacy flat keys (`policy`, `require_hard_resolution`, `allow_inferred_facts`, `max_skills`) fail load with an error naming each key's section 13 replacement.
- [ ] Run-manifest config hash covers the full validated config including agent block (RKIT-A-0003 item 3) — hash changes when ANY section 13 value changes (test over a sample from each block); existing workflow config-hash tests stay green or strengthen.
- [ ] `init` calls `career_store.getMigrationState()` and embeds the MigrationState DTO verbatim (schema version, applied ids, pending ids) in its result and workspace artifact — the hardcoded `migrations: {'career_store': 'prepared'}` literal (resume_cli/__init__.py:90 area) is DELETED grep-proof; a store double reporting pending migrations shows verbatim in init output; an incompatible schema version surfaces the store's typed error (no silent rewrite).
- [ ] resume-cli/TEST_SPEC.md: init spec bound to the section 13 vocabulary (the unbound "writes valid default config" assertion an empty config satisfied is replaced); config validation cases named. Strengthen-only.
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected edits (check resume_cli_guardrails pinning before touching cli_surface.json; defer if tripped). Snapshot regenerate ×2 no-drift if fixture configs shift (FIXTURE_CONFIG interactions — watch the expected-snapshot suite).

## Implementation Notes

### Technical Approach
The section 13 schema likely composes the existing per-package config resolvers (resume_config/matching_config/agent_config) plus a new guardrails block — compose, don't duplicate. Smoke drives init: expect churn there; update non-protected callers/fixtures honestly.

### Dependencies
RKIT-T-0123 (envelope/presentation in place so init's report renders).

### Risk Considerations
Config-hash semantics feed workflow createRun — do not change the hash of EXISTING valid configs unless necessary; if the hash inevitably changes (fuller default config), regenerate affected fixtures once and summarize (A-0006 strengthen-only, truth content unchanged).

Recommended Agent: opus + high

## Status Updates

*To be added during implementation*