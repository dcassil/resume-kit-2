---
id: host-plugin-manifest-and-runtime
level: initiative
title: "Host Plugin Manifest and Runtime Bundle"
short_code: "RKIT-I-0042"
created_at: 2026-08-13T20:41:38.001291+00:00
updated_at: 2026-08-13T20:41:38.001291+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0041"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Host Plugin Manifest and Runtime Bundle Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. The 2026-08-13 alignment audit rates the package ~30% complete: the seven contracted functions exist and the static guardrail tooling genuinely hard-blocks forbidden behavior (the negative contract is enforced at real depth), but the positive contract is scaffold. For this initiative's scope specifically: `getPluginManifest` builds an in-memory dict only — no host-format manifest artifact exists on disk; the single "skill" entry is a one-line description string (`resume_plugin/__init__.py:137-142`); and version/config metadata are hardcoded placeholders — `PACKAGE_VERSIONS` maps every package to the literal string `public-api` and `CONFIG_HASH` is `delegated-to-workflow` (`__init__.py:11-23`), stamped into every report via `_metadata()` (`__init__.py:95-100, 289`). Permission declarations exist nowhere in the package or the sibling initiatives — until this re-baseline they had no owner.

RKIT-A-0005 (decided) resolves the host question: the first host target is a Claude Code plugin, distributed as an in-repo bundle containing the plugin manifest, a `skills/` directory of SKILL.md files, and MCP server registration exposing the career-mcp stdio server (per RKIT-A-0002) plus workflow commands. This initiative builds that bundle.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Produce the in-repo Claude Code plugin bundle: on-disk manifest artifact, `skills/` directory skeleton, and MCP server registration (RKIT-A-0005 items 1-2).
- Replace placeholder version/config metadata with real identities sourced from workflow run manifests (RKIT-A-0005 item 7): actual resume-core/resume-cli/workflow package and schema versions and the real config hash.
- Own the permission declarations: local workspace files and the career DB only, no plugin-declared network access (RKIT-A-0005 item 6).

**Non-Goals:**
- SKILL.md instruction content — RKIT-I-0043 (flagged as a fold-candidate into this initiative at decomposition).
- Tool handlers and workflow delegation — RKIT-I-0044.
- Install/upgrade procedures and upgrade-safety verification — RKIT-I-0048.
- Presentation DTO alignment — RKIT-I-0046/RKIT-I-0047.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: A Claude Code plugin manifest artifact exists on disk in the repo bundle. `getPluginManifest` and the artifact are generated from one source or verified equal by a parity test, making TEST_SPEC's "metadata changes remain synchronized across supported manifests" (TEST_SPEC.md:27) testable for the first time.
- R2: The bundle registers the career-mcp stdio server per RKIT-A-0002 and exposes workflow commands (RKIT-A-0005 item 2).
- R3: The `public-api` / `delegated-to-workflow` placeholder constants (`__init__.py:11-23`) are deleted. `_metadata()` (`__init__.py:95-100`) reports real package/schema versions and the config hash carried in workflow run manifests, satisfying the Audit Gate reconstruction requirement (CONTRACT_SURFACE_ALIGNMENT.md:353-366).
- R4: The manifest declares permissions: local workspace files and the career DB only; no network (RKIT-A-0005 item 6). This initiative is the owner of permission declarations.
- R5: The bundle loads in Claude Code; the plugin remains an adapter and owns no scoring, schemas, SQLite, ATS sanitation, mutation, or learning behavior.

### Dependencies
- RKIT-I-0041 (Persistent Multi-Job CLI Flow and Release Acceptance): real run manifests must exist for version/config reporting to draw from. Now declared in frontmatter `blocked_by` — the audit found it was previously prose-only and unenforced.

### Blocked Status
- Yes: RKIT-I-0041. RKIT-A-0005 and RKIT-A-0006 are decided — they are governing constraints now, not blockers.

## Detailed Design **[REQUIRED]**

Bundle layout: a plugin root containing the Claude Code manifest (name, version, description, permissions, MCP servers, skills index), a `skills/` directory (content authored in RKIT-I-0043), and an MCP registration entry that launches the career-mcp stdio server command. The on-disk manifest is the single source of truth; `getPluginManifest` loads and returns it (or both are generated from the same data), with a parity test asserting equality so drift between the in-memory dict and the artifact is impossible.

Version identity mechanism: package versions resolved via `importlib.metadata` for resume-core, resume-cli, workflow, career-store, and resume-render; schema versions read from the owning packages' surface manifests; config hash taken from the workflow run manifest of the run being reported, never computed by the plugin. `_metadata()` changes signature to accept run-manifest input; it never fabricates a value — a missing identity is reported as missing, not substituted.

Permission model: the manifest permission block enumerates local workspace file access and the career DB path; no network permission is requested. Live model calls happen inside the resume-agent runtime under its own configuration (RKIT-A-0005 item 6) and are out of plugin scope.

Migration notes: removing the placeholders changes report metadata values; the contract tests asserting those keys are strengthened under RKIT-A-0006 authorization to assert real values (never weakened). No user-data migration — the plugin is stateless.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Manifest parity test: on-disk bundle manifest equals `getPluginManifest` output (implements TEST_SPEC.md:27).
- Version-reporting tests assert real values against `importlib.metadata`/manifest ground truth — closing the key-presence-only loophole the audit flagged (the current test lets hardcoded `public-api` pass).
- Permission test: the manifest declares exactly local-files plus career-DB, and no network permission.
- Boundary guardrails remain green; adapter-only ownership unchanged.

## Alternatives Considered **[REQUIRED]**

- Generic MCP-only bridge with no host bundle: rejected in RKIT-A-0005 — it loses the skills/instructions and confirmation/diff/report presentation surface section 11 requires of the plugin.
- Keep the in-memory manifest and emit a host artifact only at install time: rejected — the sync requirement (TEST_SPEC.md:27) becomes untestable in CI and there is no reviewable artifact in-repo.
- Freeze version strings into the manifest at release time: rejected — the Audit Gate requires identities reconstructable for the run being reported; release-time constants go stale the first time an underlying package upgrades independently.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (not tasks yet); consider folding RKIT-I-0043's skill authoring into this decomposition:
1. Bundle skeleton: manifest artifact, `skills/` directory, MCP registration entry; `getPluginManifest` parity.
2. Real version/config identity plumbing from run manifests; delete the `PACKAGE_VERSIONS`/`CONFIG_HASH` placeholders (`__init__.py:11-23`).
3. Permission declarations plus their tests.
4. Strengthened contract tests: manifest sync, real-value version assertions, permission checks.
