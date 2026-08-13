---
id: 001-select-resume-plugin-host-runtime
level: adr
title: "Select Resume-Plugin Host Runtime and Manifest Contract"
number: 1
short_code: "RKIT-A-0005"
created_at: 2026-08-13T20:41:36.809397+00:00
updated_at: 2026-08-13T21:40:50.175384+00:00
decision_date: 2026-08-13
decision_maker: Daniel Cassil
parent: 
archived: false

tags:
  - "#adr"
  - "#adr"
  - "#phase/decided"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Select Resume-Plugin Host Runtime and Manifest Contract

## Context **[REQUIRED]**

resume-plugin is an optional host/chat/IDE adapter, but no concrete host runtime, manifest schema, skill layout, permission model, tool protocol, or distribution target is selected. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

1. **First host target: Claude Code plugin.**
2. **Distribution artifact.** A Claude Code plugin bundle maintained in-repo: plugin manifest, `skills/` directory of SKILL.md files, and MCP server registration exposing the career-mcp stdio server (per RKIT-A-0002) and workflow commands. Python package distribution of the underlying packages is unchanged.
3. **Skills.** Claude Code SKILL.md files. No skill or instruction text may tell the agent it can bypass validation (resume-plugin TEST_SPEC forbidden-behavior rule).
4. **Tool delegation.** Registered tools invoke public Python APIs (resume-cli command functions and public workflow APIs) — not subprocess string protocols. Every mapped command must exist in `resume-cli/cli_surface.json` `required_commands`, enforced by a parity check (eliminating the current fictional `resume report` mapping).
5. **Presentation DTO binding.** Presenters consume the resume-core-owned shapes: section 4.3 `MatchResult`, section 4.5 `ResumeChangeOperation` status vocabulary, and the workflow run-manifest/audit shapes. `plugin_surface.json`'s invented parallel field names are realigned (edits authorized by RKIT-A-0006), and parity tests must feed presenters real resume-cli output.
6. **Permission model.** Local workspace files and the career DB only; the plugin itself declares no network access (live model calls happen inside the resume-agent runtime under its own configuration, not under plugin permissions).
7. **Version reporting.** Reports and audit summaries must surface real package/schema versions and the config hash from workflow run manifests; hardcoded placeholder strings are removed.

Decided 2026-08-13 by Daniel Cassil (host ratified in session; delegation/permission/DTO rules derived from PRODUCT_VISION_AND_CONTRACTS.md section 11 and CONTRACT_SURFACE_ALIGNMENT.md).

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Outcome |
|--------|------|------|---------|
| Claude Code plugin | Matches the developer's daily tooling; concrete manifest/skill/permission model to design against; MCP registration reuses the RKIT-A-0002 stdio server | Host-specific bundle format to maintain | **Chosen** |
| Codex SKILL.md host | Portable markdown skills | Not the primary environment; weaker tool-registration and confirmation-presentation story | Rejected for v1 |
| Generic MCP-only bridge (no host bundle) | Host-agnostic | Loses the skills/instructions and confirmation/diff/report presentation surface section 11 requires of the plugin | Rejected |
| Defer the host decision | Zero cost now | Leaves all eight plugin initiatives blocked and unplannable; plugin is last in build order regardless, so deciding now costs nothing | Rejected (decide now, build last) |

## Rationale **[REQUIRED]**

Section 11 defines the plugin as a thin adapter over public workflow APIs with presentation duties (confirmations, diffs, reports). Targeting the host the developer actually uses makes parity gates executable against a real runtime and makes the permission model concrete. The DTO-binding and command-parity rules exist because the audit demonstrated the failure mode they prevent: presenters keyed to invented field names render real CLI output as empty, and the mapper targets a `resume report` command that does not exist in the CLI surface.

## Consequences **[REQUIRED]**

### Positive
- All eight plugin initiatives unblock with a concrete host, manifest, skill, delegation, permission, and distribution model.
- The two audit-demonstrated drifts (the fictional `resume report` mapping; presenters keyed to invented DTO shapes) get decided fixes with enforcement (cli_surface parity check; real-output parity tests).

### Negative
- A host-specific bundle format to maintain; plugin work remains last in build order, so the bundle ships late.
- `plugin_surface.json` realignment and parity-test work are added scope (protected-surface edits authorized by RKIT-A-0006).

### Neutral
- A second host (e.g. Codex) would extend, not replace, this decision — revisit only if the manifest/permission model cannot be shared.

## Resolved Questions

- First host target → Claude Code plugin.
- Manifest → Claude Code plugin manifest in an in-repo bundle.
- Skills format → Claude Code SKILL.md files; no instruction may authorize bypassing validation.
- Tool invocation → public Python APIs (resume-cli command functions / public workflow APIs); every mapped command must exist in `cli_surface.json` `required_commands`.
- Permission boundaries → local workspace files and the career DB only; no plugin-declared network access.
- Distribution artifact → Claude Code plugin bundle; Python package distribution unchanged.

## Blocks

- RKIT-I-0042 Host Plugin Manifest and Runtime Bundle — lifted (decided)
- RKIT-I-0043 Host Skill and Instruction Assets — lifted (decided)
- RKIT-I-0044 Real Plugin Tool Registration and Workflow Delegation — lifted (decided)
- RKIT-I-0048 Plugin Packaging, Distribution, and Upgrade Safety — lifted (decided)
- RKIT-I-0049 Plugin Contract, Smoke, and E2E Parity Gates — lifted (decided)
- Transitive: RKIT-I-0045, RKIT-I-0046, RKIT-I-0047 — lifted (decided; these were missing from the original Blocks list)