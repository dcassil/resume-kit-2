---
id: host-skill-and-instruction-assets
level: initiative
title: "Host Skill and Instruction Assets"
short_code: "RKIT-I-0043"
created_at: 2026-08-13T20:41:38.036344+00:00
updated_at: 2026-08-13T20:41:38.036344+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0042"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: S
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Host Skill and Instruction Assets Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. Current state per the alignment audit: no skill or instruction assets exist at all — the only "skill" is a one-line description string built inside `getPluginManifest` (`resume_plugin/__init__.py:137-142`). There is no SKILL.md layout, no instruction text, and nothing enforcing TEST_SPEC's forbidden-behavior rule that no host skill instruction may tell the agent it can bypass validation (resume-plugin/TEST_SPEC.md:52) — the requirement that actually governs this initiative was absent from the previous document, which instead carried irrelevant version-reporting boilerplate.

RKIT-A-0005 (decided) sets the format: Claude Code SKILL.md files living in the bundle's `skills/` directory (item 3), with the no-bypass rule stated as a hard constraint. Scope note: this work is task-sized, not initiative-sized; it is flagged as a decomposition fold-candidate into RKIT-I-0042, which owns the bundle the skills ship in. Resized to S accordingly.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Author Claude Code SKILL.md files that route users through the safe workflows (ingest, tailoring run, requirement resolution, export, audit) exclusively via registered tools and public APIs.
- Make the no-bypass-validation rule (TEST_SPEC.md:52) an enforced, testable requirement — not prose.
- Keep skill metadata synchronized with the RKIT-I-0042 manifest.

**Non-Goals:**
- Bundle/manifest structure and MCP registration — RKIT-I-0042.
- Tool handlers and delegation — RKIT-I-0044.
- Conversation-to-workflow mapping logic — RKIT-I-0045.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: `skills/` contains one SKILL.md per contracted workflow surface; every command a skill references exists in `resume-cli/cli_surface.json` `required_commands` — no references to the fictional `resume report` (RKIT-A-0005 item 4's parity discipline applies to instruction text too).
- R2: No instruction authorizes bypassing validation, hand-editing resume JSON outside edit sessions, or skipping commit/validation gates. A guard test enforces TEST_SPEC.md:52 against the whole `skills/` tree.
- R3: Skill entries listed in the plugin manifest match the `skills/` directory contents exactly (extends RKIT-I-0042's manifest parity check).
- R4: Skills instruct, never implement: no skill embeds scoring rules, mutation procedures, or schema knowledge — the adapter-only boundary applies to instruction text as well as code.

### Dependencies
- RKIT-I-0042 (Host Plugin Manifest and Runtime Bundle): provides the `skills/` directory and manifest skill index this initiative populates.

### Blocked Status
- Yes: RKIT-I-0042. RKIT-A-0005 is decided and governs the format; it is no longer a blocker.

## Detailed Design **[REQUIRED]**

SKILL.md structure: Claude Code frontmatter (name, description, trigger guidance) plus a body that (a) states which registered tool or CLI workflow the skill drives, (b) instructs the agent that deterministic code owns facts, state, scoring, mutations, and truth — the agent proposes, code disposes — and (c) never offers an escape hatch around validation. The safety language lives in one shared template so the no-bypass wording cannot drift per-skill.

Enforcement mechanism: a guard test that (1) scans `skills/` for bypass-authorizing patterns (instructions to skip validation, edit output files directly, or ignore gate failures) and fails on match, and (2) extracts backtick-quoted `resume ...` command references from skill bodies and asserts membership in `cli_surface.json` `required_commands`. Both run in the package contract gate.

Migration notes: the one-line description string in `getPluginManifest` (`__init__.py:137-142`) is replaced by the real skill index; no data migration.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Guard test for bypass-authorizing language across `skills/` (TEST_SPEC.md:52) — new coverage; nothing enforces this rule today.
- Command-reference parity test against `cli_surface.json` `required_commands` — prevents instruction-text drift of the `resume report` kind.
- Manifest/skills sync assertion (shared with RKIT-I-0042's parity test).

## Alternatives Considered **[REQUIRED]**

- Keep instructions as manifest description strings (status quo one-liner): rejected — a description string is not host-readable skill guidance, cannot be linted for the no-bypass rule, and fails RKIT-A-0005 item 3.
- Host-agnostic markdown skills (Codex-portable format): rejected for v1 per RKIT-A-0005's alternatives analysis — Claude Code is the chosen host; a second host would extend, not replace, that decision.

## Implementation Plan **[REQUIRED]**

Task-shaped chunks (likely foldable into RKIT-I-0042's decomposition):
1. Skill inventory and the shared safety-language template.
2. Author the SKILL.md set against the template.
3. Guard tests: bypass-language lint plus command-reference parity.
