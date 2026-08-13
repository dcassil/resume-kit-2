---
id: resume-cli-runtime-and-workspace
level: initiative
title: "Resume CLI Runtime and Workspace Contract"
short_code: "RKIT-I-0035"
created_at: 2026-08-13T20:41:37.761934+00:00
updated_at: 2026-08-13T20:41:37.761934+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Resume CLI Runtime and Workspace Contract Initiative

## Context **[REQUIRED]**

Package: `resume-cli`, under `RKIT-S-0001`. The 2026-08-12/13 implementation waves left resume-cli a competent orchestration library (~35% complete against vision sections 10/13/14), not the developer-facing terminal client vision section 10 requires. Genuinely implemented: `resume_cli.main` routes commands and delegates scoring, change validation, rendering, and fact persistence to the owning packages; workspace artifacts are written; dependency direction is clean. Missing or fake in this initiative's scope:

- No terminal CLI exists. `resume-cli/pyproject.toml` has no `[project.scripts]` entry despite `cli_surface.json` declaring entrypoint `resume`; there is no `__main__.py`; stdout/stderr are discarded (`resume_cli/__init__.py:32`). Vision section 10's "Interactive terminal questions" and "Showing match reports" have zero implementation, and the prior outcome sentence named `resume_cli.main` — the library function — as the deliverable, entrenching the gap.
- The section 13 configuration contract is unimplemented: the default config (`resume_cli/__init__.py:390-395`) has no `matching.scoreAutoThreshold`, no weights, no `resume.*` structure/length/bullet/skill rules, no `guardrails` block, and no config value is ever used to enforce behavior. RKIT-A-0006 item 6 decides: the section 13 vocabulary is the config contract, the ad-hoc flat keys are removed after migration, and unknown keys fail validation.
- `init` reports `migrations: {'career_store': 'prepared'}` as a hardcoded literal (`resume_cli/__init__.py:90`) instead of store-reported status. RKIT-A-0001 item 1 decides the real surface: `career_store.getMigrationState()`.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Ship the real `resume` terminal client: `[project.scripts]` console entrypoint plus `resume_cli/__main__.py`, argument parsing, human-readable report presentation on stdout, typed errors on stderr, and meaningful exit codes. The deliverable is the terminal client, not `resume_cli.main`.
- Deliver a terminal interaction seam (prompt/confirm with a deterministic scripted mode) that RKIT-I-0037's interactive resolve and RKIT-I-0040's run loop will consume.
- `init` writes a section-13-complete default config, schema-validated at load per RKIT-A-0006 item 6: `matching.scoreAutoThreshold`, `matching.weights`, `matching.requireHardRequirementsResolved`, `resume.*` (targetPages, sectionOrder, skills/experience/bulletsPerRole min-max), `guardrails.*`, and the RKIT-A-0003 `agent` block. Unknown keys fail validation; the undocumented flat keys (`policy`, `require_hard_resolution`, `allow_inferred_facts`, `max_skills`) are migrated out.
- `init` reports real migration status from `getMigrationState()` (RKIT-A-0001), replacing the hardcoded literal.
- Stable workspace layout, result envelope, and typed error taxonomy shared by every command.

**Non-Goals:**
- Config-driven enforcement inside validate/export — RKIT-I-0039 consumes the config contract this initiative establishes.
- Per-command checkpoint gating and the run loop — RKIT-I-0040.
- Ingest, match/resolve/inspect, and tailoring semantics — RKIT-I-0036/0037/0038.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- An installed resume-cli exposes a working `resume` console command and `python -m resume_cli`; the `cli_surface.json` entrypoint declaration is exercised by a subprocess test.
- Command output goes to stdout (reports) and stderr (typed errors); the discard at `resume_cli/__init__.py:32` is removed; exit codes distinguish success (0), domain/validation failure (1), and usage/config error (2).
- `init` writes a default `config.json` containing every section 13 key; config load rejects unknown keys with a typed error (RKIT-A-0006 item 6); the run-manifest config hash covers the full validated config including the `agent` block (RKIT-A-0003 item 3).
- `init` embeds the `MigrationState` DTO returned by `getMigrationState()` (schema version, applied ids, pending ids) in its result and workspace artifact, replacing `resume_cli/__init__.py:90`; incompatible schema versions surface the store's typed error, never a silent rewrite.
- No duplicated domain rules and no direct SQLite writes (CONTRACT_SURFACE_ALIGNMENT.md resume-cli row).

### Dependencies
- None. RKIT-A-0001 (migration state surface) and RKIT-A-0006 (config contract) are decided, so this initiative can start first in the CLI chain. RKIT-I-0028's smoke/E2E coverage consumes this work; it is not a prerequisite.

### Blocked Status
- Not blocked (frontmatter blocked_by: []).

## Detailed Design **[REQUIRED]**

- **Entrypoint.** `[project.scripts] resume = "resume_cli.cli:main"` and `resume_cli/__main__.py` delegating to the same function. A presentation layer parses argv into the existing command dispatch and renders each command's result DTO: sectioned human-readable reports on stdout, a `--json` mode emitting the machine envelope for resume-plugin and tests, typed error records on stderr. The library `main()` remains callable so plugin and tests reuse one dispatch path.
- **Result envelope.** Every command returns `{status, exit_code, artifacts, report, errors[]}` where `errors[]` entries carry a stable code, message, and offending-input reference. Presentation never re-derives domain content — it renders the envelope (reports reflect domain results).
- **Terminal interaction seam.** A `TerminalIO` protocol (`ask(question) -> answer`, `confirm(summary) -> bool`) injected into command handlers; interactive mode binds the TTY, scripted mode consumes a supplied answer stream so contract/smoke gates stay deterministic. This initiative delivers the seam and wiring only; resolve semantics land in RKIT-I-0037.
- **Config.** A schema mirroring section 13 with nested `matching`, `resume`, `guardrails`, `agent` blocks. Load path: parse → schema-validate (unknown key = typed failure, per RKIT-A-0006) → freeze → hash. `init` writes the complete default. A legacy flat-key config fails load with an error naming each key's section 13 replacement — silent acceptance of undocumented keys is exactly what RKIT-A-0006 forbids.
- **Migration status.** `init` opens the store, calls `getMigrationState()`, and persists the DTO verbatim into its output and the workspace manifest; no CLI-side interpretation of migration state.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Subprocess contract test spawning the installed `resume` entrypoint for `init`/`status`: asserts stdout report content, stderr typed errors, and exit codes. This closes the TEST_SPEC hole where the Contract paragraph requires "asks interactive terminal questions" and "shows reports" but no case exercises any terminal I/O or entrypoint — the looseness that certified a library-only `main()`.
- Strengthen the init spec: the written config must contain every section 13 key (bound to the RKIT-A-0006 vocabulary), replacing the unbound "writes valid default config" assertion that an empty config satisfied.
- Config tests: unknown key rejected; legacy flat key rejected with migration guidance; config hash changes when any section 13 value changes.
- Init migration test against a store double returning pending migrations: the CLI must report the DTO verbatim (no `prepared` literal path remaining).
- TerminalIO scripted-mode determinism test; existing boundary guardrails (no SQLite, no domain rules) stay green.

## Alternatives Considered **[REQUIRED]**

- Keep `main()` library-only and make resume-plugin the sole user surface: rejected. Vision section 10 makes the CLI the developer-facing reference client with interactive questions and shown reports; the prior outcome wording proved this framing entrenches the gap rather than closing it.
- Ship a minimal config now (only keys currently read) and grow it later: rejected. RKIT-A-0006 item 6 already decides the full section 13 vocabulary with unknown-key rejection; a partial config forces a second migration and leaves RKIT-I-0039 nothing to enforce.
- Inline print statements in command handlers instead of a result envelope + presentation split: rejected. resume-plugin consumes the same command results; two rendering paths would drift and violate "reports reflect domain results".

## Implementation Plan **[REQUIRED]**

Decompose in this order (no Metis tasks created here):
1. Result envelope + typed error taxonomy + exit-code mapping across existing commands.
2. `resume` console entrypoint, `__main__.py`, stdout/stderr presentation with `--json` mode.
3. `TerminalIO` seam with scripted mode, wired into dispatch.
4. Section 13 config schema, default writer, unknown-key/legacy-key rejection, config-hash coverage.
5. `getMigrationState()` wiring in init plus workspace artifact.
6. TEST_SPEC strengthening: entrypoint subprocess cases, section-13-bound init assertions, config validation cases.
