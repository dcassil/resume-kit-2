---
id: 001-select-resume-plugin-host-runtime
level: adr
title: "Select Resume-Plugin Host Runtime and Manifest Contract"
number: 1
short_code: "RKIT-A-0005"
created_at: 2026-08-13T20:41:36.809397+00:00
updated_at: 2026-08-13T20:41:36.809397+00:00
decision_date: 
decision_maker: 
parent: 
archived: false

tags:
  - "#adr"
  - "#phase/draft"
  - "#adr"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Select Resume-Plugin Host Runtime and Manifest Contract

## Context **[REQUIRED]**

resume-plugin is an optional host/chat/IDE adapter, but no concrete host runtime, manifest schema, skill layout, permission model, tool protocol, or distribution target is selected. This ADR blocks only the initiative portions that would otherwise require guessing. Unblocked initiative work may proceed using existing product contracts and package boundaries.

## Decision **[REQUIRED]**

Pending. Resolve the open questions below before decomposing blocked initiatives into tasks or implementing runtime-specific behavior.

## Alternatives Analysis **[CONDITIONAL: Complex Decision]**

| Option | Pros | Cons | Risk Level | Implementation Cost |
|--------|------|------|------------|---------------------|
| Minimal local contract | Keeps first build small and testable | May require later migration | Medium | Low |
| Full production runtime now | Clarifies packaging and acceptance early | Higher design/dependency risk | Medium | Medium |
| Defer capability | Avoids premature assumptions | Leaves listed initiatives blocked | Low | Low |

## Rationale **[REQUIRED]**

The available docs establish boundaries and invariants, but not this concrete product/runtime decision. Capturing it as an ADR prevents hidden assumptions from leaking into implementation tasks.

## Consequences **[REQUIRED]**

### Positive
- Blocked scope is explicit before task decomposition.
- Unblocked hardening initiatives can still proceed.

### Negative
- Some initiatives cannot be decomposed until this ADR is resolved.

### Neutral
- Revisit this ADR when planning the blocked initiatives.

## Open Questions

- What is the first real host target?
- What manifest filename/schema must that host load?
- Are skills Codex SKILL.md files, plain Markdown, host-native instructions, or generated assets?
- Should tools call resume_cli.main, workflow APIs, subprocess commands, or a host bridge?
- What permission boundaries are declared for local files, career DB access, and external model/network calls?
- What artifact is distributed: Python package, local plugin bundle, Codex plugin bundle, or multiple adapters?

## Blocks

- Host Plugin Manifest and Runtime Bundle
- Host Skill and Instruction Assets
- Real Plugin Tool Registration and Workflow Delegation
- Plugin Packaging, Distribution, and Upgrade Safety
- Plugin Contract, Smoke, and E2E Parity Gates
