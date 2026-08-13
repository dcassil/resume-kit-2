---
id: real-plugin-tool-registration-and
level: initiative
title: "Real Plugin Tool Registration and Workflow Delegation"
short_code: "RKIT-I-0044"
created_at: 2026-08-13T20:41:38.072480+00:00
updated_at: 2026-08-13T20:41:38.072480+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0042"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Real Plugin Tool Registration and Workflow Delegation Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. This is the most-violated contract point in the package per the alignment audit: the plugin never imports or calls `resume_cli` or any workflow API; registered tools carry no handlers or callables; and `mapConversationToWorkflow` returns a command string that nothing dispatches. The mandated dependency edge `resume-plugin -> resume-cli / public workflow APIs` (CONTRACT_SURFACE_ALIGNMENT.md:53-54) is absent rather than violated — the plugin depends on nothing. Instead, workflow-command knowledge is duplicated as string literals (`resume_plugin/__init__.py:25-74`) and has already drifted: the `resume_report` tool and the default mapping target `resume report` (`__init__.py:64, 184, 206-208`), a command that does not exist in `resume-cli/cli_surface.json` `required_commands` (its real equivalents are `resume audit` / `resume inspect`). TEST_SPEC's smoke claim that the "plugin can invoke the same local workflow" has no supporting code path.

RKIT-A-0005 (decided, item 4) settles the delegation design: registered tools invoke public Python APIs — resume-cli command functions and public workflow APIs — not subprocess string protocols, and every mapped command must exist in `cli_surface.json` `required_commands`, enforced by a parity check. The former dependency on RKIT-I-0043 was an artificial serialization (registration does not need instruction text) and is removed.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Every registered tool carries a real handler that invokes public resume-cli/workflow Python APIs and returns the raw domain DTO.
- A `cli_surface.json` parity check eliminates the fictional `resume report` mapping and structurally prevents future command drift.
- The mandated dependency edge exists in reality: declared package dependencies and actual imports of the public APIs.

**Non-Goals:**
- Interpreting conversation messages into commands — RKIT-I-0045.
- Shaping tool results for display — RKIT-I-0046/RKIT-I-0047 (handlers return raw domain DTOs).
- Bundle/manifest structure — RKIT-I-0042.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: Each registered tool resolves to a callable that delegates to a public resume-cli command function or public workflow API; no subprocess string protocol (RKIT-A-0005 item 4).
- R2: The fictional `resume report` tool and mapping targets (`__init__.py:64, 184, 206-208`) are removed or remapped to commands that exist (`resume audit` / `resume inspect`).
- R3: A parity check asserts every registered/mapped command is a member of `resume-cli/cli_surface.json` `required_commands`; it runs inside the package contract gate.
- R4: The duplicated command-literal table (`__init__.py:25-74`) is derived from or verified against `cli_surface.json` — command-surface knowledge lives in one place, honoring the dependency direction (CONTRACT_SURFACE_ALIGNMENT.md:53-54).
- R5: Handlers are thin argument marshaling only — no scoring, mutation, schema, or fallback logic; boundary guardrails continue to enforce this.

### Dependencies
- RKIT-I-0042 (Host Plugin Manifest and Runtime Bundle): tools are registered in the bundle it delivers.

### Blocked Status
- Yes: RKIT-I-0042. The RKIT-A-0005 block is lifted (decided); its item 4 is now the design authority for this initiative.

## Detailed Design **[REQUIRED]**

Handler shape: each tool maps to a function that imports the public API, marshals host-supplied arguments into API kwargs (workspace path, job identity, run context from RKIT-I-0045), invokes it, and returns the domain result unmodified. Presentation is downstream (RKIT-I-0046/0047); handlers never rename fields or synthesize defaults — the audit showed synthesized values (placeholder metadata, fabricated operation IDs) are how truth erodes.

Parity mechanism: the tool registry declares its command identifiers; a contract test loads `cli_surface.json` and asserts the registry's command set is a subset of `required_commands`. Preferred implementation derives the registry's command list from the surface file so the check cannot be bypassed by forgetting it; at minimum the test hard-fails on any unknown command.

Error propagation: typed domain errors pass through to the host unchanged; the plugin adds no retry, fallback, or silent-default behavior (the silent default to `resume report` is the anti-pattern this replaces).

Migration notes: the package gains real dependencies on resume-cli and workflow; the `resume_report` registry entry is deleted; contract tests asserting the old string-only registry are strengthened under RKIT-A-0006 (never weakened).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract test: every registered tool resolves to a callable and its command is in `required_commands` — this closes the audit-flagged TEST_SPEC loophole where returning a command *string* satisfied "registered tools map to CLI/domain workflows"; the spec text is strengthened to require an actual invocation path.
- Smoke: invoke at least one tool end-to-end against a fixture workspace and assert its domain result equals the same command run via resume-cli directly (seed for RKIT-I-0049's parity suite).
- Boundary guardrails: handlers own no domain logic; the dependency-direction check stays green with the new imports.

## Alternatives Considered **[REQUIRED]**

- Subprocess invocation of the `resume` CLI binary: rejected by RKIT-A-0005 item 4 — a string protocol loses typed DTOs and error types and makes parity testing indirect.
- Keep string-command mapping and let the host shell out itself: rejected — it perpetuates the zero-dependency adapter and the duplicated command knowledge that has already drifted to a fictional command.
- A single generic "run command" tool taking a command string: rejected — it reintroduces a string-protocol surface, defeats per-tool discoverability and permissioning in the host, and turns the parity check advisory instead of structural.

## Implementation Plan **[REQUIRED]**

Decomposition guidance:
1. Declare real dependencies on resume-cli/workflow; import the public APIs.
2. Rebuild the tool registry with handler-bearing entries; delete/remap `resume report`.
3. Implement the `cli_surface.json` parity check and strengthened contract tests.
4. Single-tool smoke invocation against a fixture workspace (parity seed for RKIT-I-0049).
