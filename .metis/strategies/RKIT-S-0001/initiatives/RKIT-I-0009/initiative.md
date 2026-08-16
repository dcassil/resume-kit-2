---
id: make-career-mcp-importable-and
level: initiative
title: "Make Career-MCP Importable and Contract-Loadable"
short_code: "RKIT-I-0009"
created_at: 2026-08-13T20:41:37.010123+00:00
updated_at: 2026-08-16T19:04:19.271925+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: S
strategy_id: RKIT-S-0001
initiative_id: make-career-mcp-importable-and
---

# Make Career-MCP Importable and Contract-Loadable Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. The original outcome of this initiative — `career_mcp` imports cleanly and exposes `create_career_mcp`, `list_tools`, and `call_tool` over the declared eight-tool surface — is fully implemented (`career_mcp/__init__.py:25,28,189`) and passes 19 contract tests. The importability work is genuinely done. What remains inside this initiative's "contract-loadable" scope are manifest-integrity defects the alignment audit verified:

- Two copies of `tool_surface.json` exist (repo root and `career-mcp/career_mcp/tool_surface.json`). They are currently identical, but the runtime prefers the package copy (`career_mcp/__init__.py:199-204`) while the guardrail validates the root copy (`tools/career_mcp_guardrails.py:73`) — a manual-sync drift risk where guardrails could pass while the runtime serves a different surface.
- The manifest overstates behavior: `tool_surface.json:21` claims `tools/call` "enforces scope policy" while no scope/authorization code exists (the `context` argument is merely echoed back, `career_mcp/__init__.py:56-57`).
- The manifest advertises relationship types `child`/`parent` (`tool_surface.json:31-37, 321-329`) that appear in neither vision section 7 nor career-store's `store_surface.json`; calls using them are rejected at runtime (empirically confirmed).

RKIT-A-0002 (decided) settles both structural questions: item 4 makes the package copy `career-mcp/career_mcp/tool_surface.json` the single canonical manifest (root copy removed or generated from it), and item 2 requires the manifest to stop claiming scope-policy enforcement until real enforcement exists. This initiative is rescoped to that verification-and-honesty work and resized S.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Exactly one canonical `tool_surface.json` — the package copy — read by both the runtime and the guardrail, per RKIT-A-0002 item 4.
- Manifest claims match implemented behavior: the "enforces scope policy" claim is removed (RKIT-A-0002 item 2), and `child`/`parent` relationship types are removed from the advertised surface until career-store restores them under RKIT-A-0006 item 5.
- A contract test proving manifest/runtime registry parity: every advertised tool is callable and every callable tool is advertised.

**Non-Goals:**
- No transport or server binding — that is RKIT-I-0014's scope (it consumes the canonical manifest this initiative produces).
- No enum/semantics realignment beyond removing overstated advertisements — re-advertising `imported`, `child`, and `parent` once the store supports them is RKIT-I-0011's scope.
- No scope-policy implementation — the truthful policy statement that eventually replaces the removed claim is RKIT-I-0012's scope.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: `career-mcp/career_mcp/tool_surface.json` is the single canonical manifest; the root copy is deleted or generated from it, and `tools/career_mcp_guardrails.py:73` validates the same file the runtime loads at `career_mcp/__init__.py:199-204` (RKIT-A-0002 item 4).
- R2: The manifest no longer claims `tools/call` "enforces scope policy" (`tool_surface.json:21`); the machine-readable contract must not overstate the adapter, which currently echoes `context` without any check (`career_mcp/__init__.py:56-57`) (RKIT-A-0002 item 2).
- R3: The manifest advertises only relationship types the career-store contract supports today (`alias`/`equivalent`/`related`/`contradicts`); `child`/`parent` are removed from `tool_surface.json:31-37` and `321-329` until the RKIT-A-0006 item 5 restoration lands in career-store.
- R4: `create_career_mcp`, `list_tools`, and `call_tool` remain green, and a new parity test asserts the runtime tool registry equals the canonical manifest's tool list.
- R5: Manifest edits preserve or strengthen assertion strength (authorized as honesty-only realignment by RKIT-A-0006).

### Dependencies
- None. RKIT-A-0002 and RKIT-A-0006 are decided and are design inputs, not blockers.

### Blocked Status
- No (blocked_by: []).

## Detailed Design **[REQUIRED]**

**Manifest canonicalization.** Delete the root `tool_surface.json` (preferred) or replace it with a generated artifact produced from the package copy by a small sync tool; either way the guardrail's path constant changes to the package copy so the file the guardrail certifies is byte-identical to the file the runtime serves. If the root copy is kept as a generated artifact, the guardrail additionally asserts the two copies are identical so drift fails loudly instead of silently.

**Honesty edits.** In the canonical manifest: drop the "enforces scope policy" language from the `tools/call` endpoint description (RKIT-I-0012 later adds the truthful replacement statement); remove `child`/`parent` from the relationship-type vocabulary block and the `career.add_relationship` schema so schema validation and store behavior agree — today an advertised value passes MCP validation and then fails inside the store, the worst failure shape for agent callers.

**Parity check.** A contract test loads the canonical manifest, instantiates the adapter, and asserts `list_tools()` and the manifest's tool entries are in one-to-one correspondence (names and schemas). A second assertion checks every relationship-type enum value the manifest advertises is accepted by career-store's declared contract (`store_surface.json` `relationship_types`), so advertised-but-unfulfillable surface cannot silently reappear.

**Migration note.** No data or store changes; this is manifest, guardrail-path, and test work only. Manifest edits are protected-surface edits authorized by RKIT-A-0006 for honesty-only realignment.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Add the manifest/runtime parity contract test described above; keep the existing 19 contract tests green.
- Update `tools/career_mcp_guardrails.py` to validate the canonical package copy; run the guardrail in the package gate.
- Add the manifest-enum-subset-of-store-contract assertion — the TEST_SPEC-strengthening item for this scope: today nothing fails when the manifest advertises capability the store rejects (the audit confirmed `child`/`parent` calls fail at runtime while all tests stay green).
- Strengthen the smoke expectation "MCP server/tool registry loads" to require loading the registry from the canonical package manifest specifically (making that item require a real server process is RKIT-I-0014's spec work).

## Alternatives Considered **[REQUIRED]**

- **Keep both manifest copies with a CI sync check.** Rejected: drift risk remains between check runs, and two "sources of truth" invite exactly the guardrail-passes-while-runtime-differs failure the audit flagged; RKIT-A-0002 chose a single canonical copy.
- **Make the root copy canonical instead of the package copy.** Rejected: the runtime already prefers the package copy and the package copy ships with the installed distribution; canonicalizing the root file would leave installed environments reading a non-canonical file.
- **Close this initiative as already complete.** Rejected: the importability outcome is done, but the dual-manifest drift risk and the two manifest overstatements are live defects squarely inside "contract-loadable", and no sibling initiative owns them.

## Implementation Plan **[REQUIRED]**

1. Canonicalize the manifest (delete or generate the root copy) and point the guardrail at the package copy.
2. Apply the honesty edits: remove the scope-policy claim and the `child`/`parent` advertisements.
3. Add the manifest/runtime parity contract test and the manifest-vs-store-contract enum subset assertion.
4. Update the smoke registry-load expectation and run the canonical package gate.