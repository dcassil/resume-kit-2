---
id: add-career-mcp-policy-scope-and
level: initiative
title: "Add Career-MCP Policy, Scope, and Confirmation Enforcement"
short_code: "RKIT-I-0012"
created_at: 2026-08-13T20:41:37.084689+00:00
updated_at: 2026-08-17T19:44:54.605896+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0010]
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: add-career-mcp-policy-scope-and
---

# Add Career-MCP Policy, Scope, and Confirmation Enforcement Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. Policy and confirmation are half-real today. What exists: mutations and `career.get_unverified` set `confirmation_required` flags (`career_mcp/__init__.py:312-322, :346-352`), and `career.propose_fact` keeps proposals unverified pending confirmation. What is missing: nothing enforces those flags; `get_unverified` marks `confirmation_required` unconditionally; and no scope/authorization code exists at all — the `policy` argument is stored and forwarded, the `context` argument is merely echoed back (`:56-57`), while `tool_surface.json:21` claims `tools/call` "enforces scope policy". The audit called this out as a machine-readable contract overstating implemented behavior.

RKIT-A-0002 item 2 (decided) settles the posture: v1 is single-user local, consistent with product section 17; no multi-user authorization layer; until real scope enforcement exists the manifest must not claim it. RKIT-I-0009 performs the interim removal of the false claim; this initiative delivers the enduring policy behavior — implement what the decision keeps, honestly omit what it defers — and the truthful manifest statement that replaces the removed claim.

Boundary with RKIT-I-0010: 0010 owns validation mechanics (typed envelopes, argument fidelity, evidence-requirement rejection); this initiative owns policy semantics — which operations require confirmation, how confirmation is satisfied, and what the policy vocabulary means. Blocked by RKIT-I-0010 because policy rejections ride the typed `policy_error` envelope it builds.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Confirmation enforcement is real: mutations that require confirmation are actually gated until confirmed, not merely flagged.
- A defined single-user policy model per RKIT-A-0002 item 2: no principals or scopes in v1; policy = confirmation policy plus capability policy (read vs mutate).
- `confirmation_required` is computed from policy instead of hardcoded true (`career_mcp/__init__.py:346-352`).
- The manifest carries a truthful policy statement — an accurate scoped claim or nothing — closing the `tool_surface.json:21` misalignment permanently.

**Non-Goals:**
- Multi-user authorization — rejected for v1 by RKIT-A-0002; revisited when a remote host appears (RKIT-I-0014's transport ADR records the trigger).
- Validation mechanics and envelope construction — RKIT-I-0010.
- Recording confirmation decisions in audit events — RKIT-I-0013 records the `confirmation_required` values this initiative defines.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: A policy evaluation step runs before every store mutation, producing `{allowed, requires_confirmation, reason}`. An unconfirmed mutation that requires confirmation returns status `rejected` with `error.type = policy_error` (envelope per RKIT-I-0010) and does not touch the store.
- R2: The confirmation-satisfaction contract is defined: a `confirmed: true` argument (host-mediated user confirmation) on mutating tools, advertised in the manifest schemas; absent or false means the mutation is gated when policy requires confirmation.
- R3: `career.get_unverified`'s `confirmation_required` flag (`:346-352`) reflects the policy evaluation for verifying each fact rather than constant true.
- R4: The `context` argument's semantics are made honest: either it feeds policy evaluation or it is removed from the schema; the pure echo at `career_mcp/__init__.py:56-57` is eliminated.
- R5: Manifest policy language matches implementation exactly, replacing the claim RKIT-I-0009 removed; satisfies RKIT-A-0002 item 2 and closes the audit's contract-misalignment finding on `tool_surface.json:21`.
- R6: The single-user posture is recorded: no scope enforcement is advertised anywhere in v1.

### Dependencies
- RKIT-I-0010 (typed `policy_error` envelope). RKIT-A-0002 is decided — the single-user decision is an input, not a blocker.

### Blocked Status
- Yes (blocked_by: ["RKIT-I-0010"]).

## Status Updates

- 2026-08-17: COMPLETE. T-0106 (ebe141a): pure evaluate_policy w/ classification derived from manifest mutates flags; call_tool gates after validation/before dispatch (store-spy zero-call proof, independently probed); confirmed arg on all 4 mutating schemas (byte-copy via sync tool, consumed-arguments covered); get_unverified flag policy-computed; context echo/parameter REMOVED (no schema, no semantics). T-0107 (c68b6d5): exact gated_tools parity test, access-control vocabulary scan (sole exception: role fact-type enum), per-gated-tool behavioral rejection loop, TEST_SPEC binding claims-require-tests rule; both mutation probes failed named tests. tool_surface.json:21 misalignment closed permanently. Zero protected edits; gates green throughout; version bumped 0.24.0.

## Detailed Design **[REQUIRED]**

**Policy model.** A pure function `evaluate_policy(tool, arguments, confirmed) -> PolicyDecision {allowed, requires_confirmation, reason}`. Capability classes: read tools are always allowed; mutating tools (`career.propose_fact`, `career.verify_fact`, `career.add_evidence`, `career.add_relationship`) require host-mediated confirmation, preserving the product rule that agents propose and the user confirms. No principals, scopes, or roles exist in the v1 model — by decision, not omission.

**Enforcement point.** `call_tool` evaluates policy after validation and before store dispatch. Denied-pending-confirmation calls return `policy_error` with reason `confirmation_required` and never reach the store (store authority is preserved: the store remains the final validator of state transitions; MCP policy gates earlier for the host confirmation UX). Confirmed calls proceed and expose `confirmation_required: true, confirmed: true` in the result — the values RKIT-I-0013's audit events record.

**Flag rationalization.** `get_unverified` computes per-fact `confirmation_required` from the same policy function, replacing the unconditional true at `:346-352`, so the flag means "verifying this fact will require confirmation" rather than being decoration.

**Manifest statement.** The canonical manifest (single copy per RKIT-I-0009) gains a policy block stating the v1 posture — single-user local; mutations gated on host-mediated confirmation; no scope enforcement — and a parity test asserts the statement matches the implemented behavior so the manifest can never overstate again.

**Migration note.** No store or data changes. Hosts currently calling mutating tools without `confirmed` will begin receiving `policy_error`; resume-cli orchestration must pass confirmation explicitly, which is the intended product behavior.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract tests: unconfirmed mutation yields `policy_error` and zero store calls (assert via store spy); confirmed mutation proceeds; read tools are unaffected; `get_unverified`'s flag varies with policy.
- Manifest policy-statement parity test (statement text and mutation gating agree).
- TEST_SPEC strengthening for this scope: TEST_SPEC.md:35 lists "authorization/scope policy if added later" as optional — the weakest of the three governing documents, which let the manifest overstate without a failing test (the audit's finding). Strengthen the spec to require that any policy claim in the manifest has corresponding executable tests, and add explicit confirmation-enforcement items (gated unconfirmed mutation, satisfied confirmation, computed flags).

## Alternatives Considered **[REQUIRED]**

- **Build multi-user scopes/principals now.** Rejected by RKIT-A-0002: contradicts the product's section 17 single-user local posture, carries large cost with no multi-user deployment, and drags auth burden into the stdio transport prematurely.
- **Advisory-only flags (status quo, documented as host responsibility).** Rejected: flags nobody enforces are the audit's "well-guarded but shallow" pattern; the DoD workflow expects the MCP boundary to survive a real mutating agent, and host goodwill is not enforcement.
- **Enforce confirmation inside career-store instead of MCP.** Rejected: the store cannot see host confirmation context, and CONTRACT_SURFACE_ALIGNMENT.md assigns the narrow semantic-tool boundary to career-mcp; the store keeps state-transition authority while MCP owns caller-facing policy.

## Implementation Plan **[REQUIRED]**

1. Implement the policy module and `PolicyDecision`, with the capability classification of the eight tools.
2. Wire policy evaluation into `call_tool` mutation dispatch; add `confirmed` to mutating tool schemas.
3. Rationalize `get_unverified`'s flag and resolve the `context` argument (feed policy or remove).
4. Add the truthful manifest policy statement plus the parity test.
5. Contract tests and TEST_SPEC strengthening; run the canonical package gate.