# Plugin Skill Implementation Spec

## Purpose

`src/plugin/skills/` defines the agent-facing skill policy and future `SKILL.md` template generation.

## Expected Files

```text
src/plugin/skills/policy.js
templates/plugin/SKILL.md
```

## Required Exports

From `policy.js`:

- `buildSkillPolicy()`

## Policy Shape

`buildSkillPolicy()` should return:

```js
{
  requiredFirstChecks: [
    "straight-jacket list --json",
    "straight-jacket verify --json"
  ],
  forbiddenActions: [
    "edit .straight-jacket/manifest.json",
    "edit .straight-jacket/manifest.sig",
    "edit .straight-jacket/public-key.json",
    "ask user for password in chat",
    "commit with --no-verify to bypass checks"
  ]
}
```

Additional fields are allowed if they are JSON-serializable and do not weaken the boundary.

## Test Targets

Primary:

```text
test/unit/plugin.test.mjs
```
