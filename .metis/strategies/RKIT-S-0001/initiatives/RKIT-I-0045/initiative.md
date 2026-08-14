---
id: plugin-conversation-to-workflow
level: initiative
title: "Plugin Conversation-to-Workflow Mapping and Run Context"
short_code: "RKIT-I-0045"
created_at: 2026-08-13T20:41:38.107530+00:00
updated_at: 2026-08-13T20:41:38.107530+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: ["RKIT-I-0044"]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: NULL
---

# Plugin Conversation-to-Workflow Mapping and Run Context Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. `mapConversationToWorkflow` exists but is shallow substring keyword matching with defects the alignment audit verified against code:
- Substring matching (`resume_plugin/__init__.py:196-208`): "important" matches `import`; "prune" matches `run`.
- Confirmation answers are misrouted before the yes/no branch: "yes, my last job used AWS" hits the tailoring branch first because its tokens include "job" (`__init__.py:199-205`), mapping to `resume run` instead of `resume resolve`.
- Unrecognized messages silently default to `resume report` (`__init__.py:206-208`) — a command that does not exist in `resume-cli/cli_surface.json` `required_commands`.
- `confirmation_required` is hardcoded `False` (`__init__.py:186`); it exists only to satisfy the surface contract's required-fields check, so a host can never learn that user confirmation is needed despite "presenting user confirmation requests" being a section 11 responsibility.

Nothing pins mapped commands to the CLI surface — the exact loophole that let the fictional command ship. RKIT-A-0005 (decided, item 4) requires every mapped command to exist in `required_commands` with a parity check; RKIT-I-0044 delivers the invocation path and parity mechanism this mapping feeds.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Deterministic, testable conversation-to-workflow mapping: word-boundary intent rules, pending-confirmation precedence, and explicit "unrecognized" results instead of silent defaults.
- `confirmation_required` derived from actual workflow run state, signaling hosts when to invoke RKIT-I-0046's presentation.
- Every mapped command pinned to `cli_surface.json` `required_commands`.

**Non-Goals:**
- Rendering confirmation requests and capturing answers — RKIT-I-0046.
- Diff/report/audit presentation — RKIT-I-0047.
- Tool-handler mechanics and the parity-check implementation — RKIT-I-0044 (this initiative consumes both).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: Substring matching (`__init__.py:196-208`) is replaced with tokenized, word-boundary intent matching. Named regression cases: "important" must not map to import; "prune" must not map to run.
- R2: Pending-confirmation answers are checked before command intents, fixing the misroute where "yes, my last job used AWS" maps to `resume run` instead of the resolution path (`__init__.py:199-205`).
- R3: No silent default: unrecognized input returns an explicit unrecognized/clarification result; the `resume report` fallback (`__init__.py:206-208`) is deleted.
- R4: `confirmation_required` is computed from workflow run state (pending questions/confirmations for the active run), never a constant (`__init__.py:186`).
- R5: The mapping table's commands are members of `cli_surface.json` `required_commands`, enforced through RKIT-I-0044's parity check; mapping tests assert membership.

### Dependencies
- RKIT-I-0044 (Real Plugin Tool Registration and Workflow Delegation): supplies the real command set, the parity check, and the run-state source R4 reads.

### Blocked Status
- Yes: RKIT-I-0044. No ADR blocks remain — RKIT-A-0005 is decided and governs the command-parity rule.

## Detailed Design **[REQUIRED]**

Mapper output DTO: `{command, args, run_context, confirmation_required, recognized}` where `command` is either a `required_commands` member or absent when `recognized` is false. `run_context` carries the active workspace and job identity read from workflow state so handlers (RKIT-I-0044) receive a complete invocation context.

Matching behavior, in strict order: (1) if the active run has a pending confirmation, the message is captured as an answer and routed to the resolution path — domain nouns inside the answer never re-trigger command intents; (2) tokenized word-boundary intent rules match explicit commands; (3) anything else returns `recognized: false` with no command. There is no fuzzy fallback tier.

`confirmation_required` derivation: true iff the workflow reports pending questions/confirmations for the active run — the mapper asks the workflow, it never guesses. This is the signal RKIT-I-0046's presentation waits on.

Migration notes: any existing tests blessing substring behavior or the silent default are rewritten under RKIT-A-0006's strengthen-only rule; fixture truth content unchanged.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Adversarial mapping contract tests naming the audit's cases: "important" (not import), "prune" (not run), a confirmation answer containing "job"/"AWS" (resolution path, not `resume run`), unrecognized input (explicit unrecognized, no command).
- `confirmation_required` tests in both directions: true when the workflow has pending confirmations, false when it does not.
- Command-membership assertions over the full mapping table against `required_commands`.
- TEST_SPEC strengthening (audit-flagged): the mapping requirement is restated so a returned command string alone cannot satisfy it — mapped commands must be in `required_commands` and dispatchable via the RKIT-I-0044 path.

## Alternatives Considered **[REQUIRED]**

- Delegate intent classification to the host LLM: rejected — the adapter's mapping must be deterministic and testable; the host agent already handles natural language above this layer, and the plugin declares no model access under RKIT-A-0005's permission model.
- Harden the current approach with per-command regexes: rejected — same failure class (accidental partial matches), no run-state awareness, and it cannot fix the confirmation-routing order defect.

## Implementation Plan **[REQUIRED]**

Decomposition guidance:
1. Define the mapper output DTO and the intent rule table pinned to `cli_surface.json`.
2. Implement ordered matching with pending-confirmation precedence and the explicit unrecognized result.
3. Wire `confirmation_required` derivation from workflow run state.
4. Adversarial contract tests plus the TEST_SPEC mapping-requirement strengthening.
