---
id: collectversions-with-real-package
level: task
title: "collectVersions with real package/schema/matching sources and careerDbVersion via getMigrationState"
short_code: "RKIT-T-0058"
created_at: 2026-08-15T02:48:33.727838+00:00
updated_at: 2026-08-15T02:48:33.727838+00:00
parent: workflow-artifact-schemas-and-run
blocked_by: []
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0022
---

# collectVersions with real package/schema/matching sources and careerDbVersion via getMigrationState

## Parent Initiative

[[RKIT-I-0022]]

## Objective

Kill the fake versions (RKIT-I-0022 Requirements 2-4, Detailed Design "Version recording"): a `collectVersions()` helper resolves every manifest version from its real source — installed package metadata, schema-module constants, resume-core's public surface for matching versions, and career-store `getMigrationState()` for careerDbVersion. No literal fallbacks; unresolvable sources raise typed errors, never '0.0.0'.

## Acceptance Criteria

- [ ] `collectVersions()` exists in workflow: package versions via installed-package metadata (importlib.metadata), schema versions via constants exported by the schema modules (add the constants where missing — schema modules own their versions), matching_algorithm_version/matching_config_version via resume-core's public surface (add a public accessor there if none exists — realign-only, no scoring exposure).
- [ ] The hardcoded '0.0.0' package_versions and inlined schema-version literals (old workflow/__init__.py:47-58) and the matching-version fallbacks (old :178-179) are GONE; a grep for '0.0.0' in workflow returns nothing but tests asserting its absence.
- [ ] careerDbVersion is recorded from career-store `getMigrationState()` for the run's database (RKIT-A-0001); workflow never invents store truth. Contract test: manifest careerDbVersion equals getMigrationState() output.
- [ ] An unresolvable version source raises a typed error (e.g. VersionSourceUnavailableError naming the source) — never emits a placeholder.
- [ ] Contract test: buildRunManifest output contains no placeholder version values; every version field is asserted against its real source.
- [ ] PR + smoke gates green; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

`workflow/versions.py` (or similar) housing collectVersions; buildRunManifest consumes it. For editable installs, importlib.metadata reads the installed dist (pip install -e . is the repo norm — verify what metadata resolves and use the honest source). careerDbVersion needs a store handle/db path: thread from run config where the store is used; when a run has no career DB, record the documented absent-value honestly (typed 'unavailable' marker per schema, not '0.0.0') — decide from the schema and state the choice.

### Dependencies

I-0005's getMigrationState (done — method exists; its surface-manifest declaration is deferred but the API is callable). Chunk 1 of this initiative (run identity — already complete 08-13).

### Risk Considerations

Smoke builds manifests — missing-version typed errors must not break legitimate smoke paths; ensure real sources resolve in the smoke environment (pip install -e . happens in smoke). resume-core accessor addition must not expose scoring.

### Execution profile

Recommended Agent: opus + high

Rationale: cross-package version plumbing with an honesty rule (no placeholders ever) that later manifest consumers depend on.

## Status Updates

*To be added during implementation*
