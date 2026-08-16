---
id: manifest-runtime-parity-store
level: task
title: "Manifest/runtime parity + store-contract enum subset tests; smoke registry expectation; guardrail re-path patch for approval batch"
short_code: "RKIT-T-0080"
created_at: 2026-08-16T18:48:24.187029+00:00
updated_at: 2026-08-16T18:48:24.187029+00:00
parent: make-career-mcp-importable-and
blocked_by: ["RKIT-T-0079"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0009
---

# Manifest/runtime parity + enum-subset tests; guardrail re-path patch — I-0009 close-out

## Parent Initiative

[[RKIT-I-0009]]

## Objective **[REQUIRED]**

Prove the canonical manifest cannot silently drift from either the runtime or the store contract: (1) a parity contract test — every advertised tool is callable and every callable tool advertised (names AND schemas one-to-one against `list_tools()`); (2) an enum-subset assertion — every relationship-type value the manifest advertises is in career-store's `store_surface.json` `relationship_types` (today NOTHING fails when the manifest advertises capability the store rejects — the audit-confirmed gap); (3) a root/package byte-identity test so generated-copy drift fails loudly; (4) the verbatim `tools/career_mcp_guardrails.py` re-path patch authored for Daniel's approval batch. Initiative close-out.

## Acceptance Criteria **[REQUIRED]**

- [ ] Contract test module (tests/contract/, unprotected, discovered or bridged into a gate-run module like the T-0078 bridge idiom if the runner list is static): manifest↔`list_tools()` one-to-one on names and schemas; a manifest tool without a registered handler and a registered handler without a manifest entry BOTH fail.
- [ ] Enum-subset test: manifest relationship-type vocabulary (all occurrences, including add_relationship schema enum) ⊆ career-store `store_surface.json` `relationship_types`; a fixture-mutated manifest with `parent` re-added fails.
- [ ] Byte-identity test: root `tool_surface.json` == package copy; drift fails with a message naming the sync tool.
- [ ] Smoke registry-load expectation strengthened to load the registry from the canonical PACKAGE manifest specifically — ONLY if achievable without editing protected tools/run_smoke.py; run_smoke.py is protected, so if the expectation lives there, author the change as a deferred patch instead and note it (real-server smoke is RKIT-I-0014's scope).
- [ ] Verbatim unified-diff patch for `tools/career_mcp_guardrails.py` (path constant → package copy, plus a copies-identical assertion while the root artifact exists) included in the task report/Status Updates for the approval batch. Do NOT apply it.
- [ ] Existing 19 career-mcp contract tests green; `--pr`, `--smoke`, `--future-contract` green; `straight-jacket verify` clean.
- [ ] Mutation probes reported: remove a tool from the manifest → parity fails; re-add `parent` → subset fails; alter root copy → identity fails.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Reuse the T-0078 bridge idiom if the new module isn't in the static gate list: import its TestCase into a module the gate already runs, with a comment noting the deferred run_tests.py wiring.
- Recommended Agent: opus + medium

### Dependencies
RKIT-T-0079 (canonical manifest + honesty edits). Final task; after it: initiative → completed, version bump 0.15.0, push develop, handoff update.

### Risk Considerations
- PROTECTED (read-only): tools/career_mcp_guardrails.py, tools/run_smoke.py, tools/run_tests.py, tests/boundary/*. All changes to them are authored-as-patches only.

## Status Updates **[REQUIRED]**

*To be added during implementation*
