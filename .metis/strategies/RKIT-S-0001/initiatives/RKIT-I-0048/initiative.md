---
id: plugin-packaging-distribution-and
level: initiative
title: "Plugin Packaging, Distribution, and Upgrade Safety"
short_code: "RKIT-I-0048"
created_at: 2026-08-13T20:41:38.219462+00:00
updated_at: 2026-08-13T20:41:38.219462+00:00
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

# Plugin Packaging, Distribution, and Upgrade Safety Initiative

## Context **[REQUIRED]**

Package: `resume-plugin`. No distribution or upgrade story exists. The bundle this would distribute does not exist yet (RKIT-I-0042 creates it), there is no install/upgrade path, and there is no upgrade-safety verification design at all — TEST_SPEC's rule that plugin-only version changes must not alter resume truth semantics (resume-plugin/TEST_SPEC.md:56) has nothing verifying it. The version-reporting requirement this initiative leans on is currently satisfied only nominally: `PACKAGE_VERSIONS` maps every package to the literal `public-api` and `CONFIG_HASH` is `delegated-to-workflow` (`resume_plugin/__init__.py:11-23`), stamped via `_metadata()`, and the contract test checks key presence only — hardcoded placeholders pass the gate.

RKIT-A-0005 (decided) fixes the distribution model: an in-repo Claude Code plugin bundle (item 2) with Python package distribution of the underlying packages unchanged, permissions limited to local workspace files and the career DB with no plugin-declared network access (item 6), and real version/config identities from workflow run manifests (item 7). The former dependency on RKIT-I-0047 is replaced: upgrade-safety verification exercises the delegation path (RKIT-I-0044), not the presentation layer.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- An installable, upgradeable, uninstallable Claude Code plugin bundle distribution with a documented, scripted procedure.
- An executable upgrade-safety verification: plugin-only version changes provably cannot alter resume truth semantics (TEST_SPEC.md:56 made mechanical).
- REAL version identities enforced at the gate level: key-presence-only checks closed.

**Non-Goals:**
- Creating the bundle/manifest structure and removing the placeholder constants — RKIT-I-0042 (this initiative pins the gate that keeps them out).
- The general CLI-vs-plugin parity harness — RKIT-I-0049 (whose parity dimensions define "identical domain results" and are reused here).
- Tool handlers — RKIT-I-0044.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: Documented, scripted install/upgrade/uninstall for the in-repo bundle into Claude Code (RKIT-A-0005 item 2); the plugin bundle carries its own version, independent of the underlying package versions.
- R2: Permission declarations ship in the distributed artifact and survive upgrade: local workspace files and the career DB only, no network (RKIT-A-0005 item 6).
- R3: Upgrade-safety verification: running the same fixture workflow through the plugin before and after a plugin-only version bump yields identical domain results — scores, requirement resolution, operations, final canonical resume, audit reconstruction (dimensions shared with RKIT-I-0049). Any difference fails.
- R4: Version-reporting gates assert real, reconstructable identities per the Audit Gate (CONTRACT_SURFACE_ALIGNMENT.md:353-366): reported package/schema versions match `importlib.metadata`/manifest ground truth and the config hash matches the run manifest — closing the key-presence loophole that let `public-api`/`delegated-to-workflow` (`__init__.py:11-23`) pass.
- R5: The plugin is verifiably stateless: no resume, career, or config state lives in the bundle, so upgrade cannot migrate or corrupt user data.

### Dependencies
- RKIT-I-0044 (Real Plugin Tool Registration and Workflow Delegation): upgrade-safety verification exercises the real delegation path; without it there is nothing meaningful to verify.

### Blocked Status
- Yes: RKIT-I-0044. RKIT-A-0005 is decided — its items 2/6/7 are the design authority, not a blocker.

## Detailed Design **[REQUIRED]**

Distribution: the bundle lives in-repo with its own semantic version; install places/links it into Claude Code's plugin location; upgrade is bundle replacement and never touches the career DB or workspace files. The underlying Python packages continue distributing normally — the bundle declares compatible ranges, and reports of any run always carry the actually-installed versions (RKIT-I-0042's identity plumbing).

Upgrade-safety mechanism: a fixture workspace plus pinned underlying packages; the harness runs a workflow scenario via plugin tools at bundle version N, bumps only the bundle version metadata (N+1), reruns, and structurally diffs domain results across the parity dimensions. Because the underlying packages are pinned, any diff is by construction plugin-caused and fails the check.

Version assertion mechanism: the gate resolves ground truth from `importlib.metadata` and the owning packages' surface manifests, then compares report/audit-summary metadata values for equality — presence is not compliance.

Migration notes: none for user data (statelessness is R5 and is itself asserted); the weakened key-presence contract check is strengthened under RKIT-A-0006's strengthen-only authorization.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Install/upgrade/uninstall smoke script run in the package gate.
- Upgrade-safety fixture test (N vs N+1 identical-domain-results check) — the executable form of TEST_SPEC.md:56.
- Strengthened version-report assertions comparing values to ground truth — closes the audit-flagged TEST_SPEC upgrade-safety loophole (key presence permitting placeholders).
- Post-install permission test: the installed artifact declares exactly local-files plus career-DB and no network.

## Alternatives Considered **[REQUIRED]**

- Distribute via PyPI with host entry points: rejected — RKIT-A-0005 chose the in-repo Claude Code bundle; the underlying packages keep their Python distribution unchanged, and a PyPI plugin adds release surface with no host to consume it.
- Treat upgrade safety as review policy rather than an executable check: rejected — the audit demonstrated that policy-only requirements get satisfied nominally (the placeholder version strings); TEST_SPEC.md:56 needs a mechanical gate to mean anything.

## Implementation Plan **[REQUIRED]**

Decomposition guidance:
1. Bundle versioning scheme plus install/upgrade/uninstall scripting.
2. Statelessness assertion and permission-persistence checks.
3. Upgrade-safety fixture harness (N vs N+1 domain-result identity, reusing RKIT-I-0049 dimensions).
4. Real-value version gate assertions replacing key-presence checks.
