# Resume Tailoring Platform — Complete Smoke Test

## Purpose

The smoke test verifies that all major packages are wired together correctly and that the primary happy path plus critical honesty guardrails work after installation, build, migration, or deployment.

This is not intended to prove every scoring or language edge case. It proves the system is operational and that critical package boundaries are functioning.

## Target runtime

The test should run against:

- `resume-core`
- `career-store`
- `career-mcp`
- `resume-agent`
- `resume-render`
- `resume-cli`

A plugin adapter may optionally be tested after the core smoke test passes.

---

# Fixture Set

## Resume fixture

Use a small deterministic resume containing:

- Candidate title: Senior Software Developer
- 10+ years software development
- React explicitly listed
- REST API work explicitly listed
- AWS not present
- A bullet using the phrase `responsive web apps`
- At least one smart quote/non-breaking-space/odd bullet character to test sanitation

## Job fixture

Use a job description containing:

Required:

- Senior Software Engineer
- React
- API design
- Responsive design

Preferred:

- AWS
- SaaS

The fixture should deliberately use wording that differs slightly from the resume while remaining legitimately equivalent.

---

# Smoke-Test Flow

## 1. Build and package import

Run all package builds.

Expected:

- No compile/type errors.
- Public package imports resolve.
- No circular package dependency violating architecture rules.

## 2. Initialize workspace

Run:

```text
resume init ./smoke-workspace
```

Expected files:

```text
config.json
resume/
job/
data/
operations/
reports/
output/
```

Expected:

- Valid default `config.json`.
- SQLite DB created or creatable on first store access.
- DB migrations succeed.

## 3. Ingest resume

Run:

```text
resume ingest fixtures/resume-smoke.*
```

Expected:

- `resume/base.json` exists.
- `resume/working.json` exists.
- Working initially equals base semantically.
- Canonical schema validates.
- Odd ATS characters are either normalized or reported.
- Source provenance exists for meaningful parsed fields.

Failure condition:

- Agent-generated content appears in base that is not present or semantically supported in the source resume.

## 4. Verify career-store ingest

Query career facts through service or MCP.

Expected facts include:

- software development
- React
- REST/API experience

Expected:

- Evidence points to resume source locations.
- Verification is `source_stated` or equivalent, not `user_verified` unless fixture explicitly includes user verification.

## 5. Test MCP surface

Call:

```text
career.search_facts("React")
career.get_fact(<react-id>)
```

Expected:

- React returned.
- Evidence summary available.
- No raw SQL details leaked.

Attempt an unsupported raw SQL-style tool call.

Expected:

- Tool does not exist.

## 6. Ingest job

Run:

```text
resume job ingest fixtures/job-smoke.txt
```

Expected:

- `job/current.json` exists.
- Required/preferred requirements correctly classified.
- Source text retained.
- Required React/API/responsive-design concepts exist.

## 7. Initial match

Run:

```text
resume match
```

Expected:

- Deterministic score returned.
- React resolves.
- API design resolves or becomes a legitimate related/verified-fact match.
- Responsive design is recognized as exact/alias/related or becomes a resolution candidate.
- AWS remains missing/unresolved.
- SaaS status follows fixture truth.
- Requirement-level reasoning is visible.

Run the same score again without changing state.

Expected:

- Same deterministic score and requirement states.

## 8. Gap resolution

If AWS is preferred only, system may continue depending on configured threshold.

If score is below threshold, ensure code selects an unresolved requirement and agent generates the question.

Expected:

- Code, not agent, selects what needs resolution.
- Agent question references only selected requirement context.

Answer fixture question with a known confirmation, for example:

```text
Yes, I used AWS for about 6 years, primarily EC2, S3, Lambda, and RDS.
```

Expected:

- Agent produces structured fact/evidence proposal.
- Career store persists AWS fact.
- Verification becomes `user_verified` because the answer explicitly confirms it.
- Match reruns.
- Score improves or requirement resolution changes accordingly.

## 9. Tailoring proposal

Run:

```text
resume tailor
```

Expected:

- Agent does not directly modify `working.json`.
- One or more `ResumeChangeOperation` records are produced.
- A legitimate terminology rewrite can transform `responsive web apps` toward `responsive design` language without adding unsupported scope/results.
- Every change references grounding facts and target requirements.

## 10. Hallucination rejection test

Inject/propose a deliberately invalid operation:

```text
Before: Built React applications.
After: Architected enterprise React platforms serving 20 million users globally.
```

Fixture does not contain enterprise scale or 20 million users.

Expected:

- `resume-core.validateChange` rejects operation.
- Working resume remains unchanged.
- Audit log records rejection reason.

This is a mandatory smoke-test assertion.

## 11. Apply valid changes

Expected:

- Valid changes move through `proposed -> validated -> applied`.
- `resume/base.json` remains unchanged.
- `resume/working.json` reflects only validated operations.

## 12. Final validation

Run:

```text
resume validate
```

Expected:

- Grounding audit passes.
- ATS character checks pass or have no blocking errors.
- Section min/max rules pass.
- No unverified inferred fact appears in final resume.
- No unresolved required requirement is falsely marked resolved.

## 13. Final score

Run:

```text
resume match --working
```

Expected:

- Score is deterministic.
- Expected terminology/verified additions improve or maintain score.
- Report explains change from base score.

## 14. Render

Run:

```text
resume export --format markdown
resume export --format docx
```

Expected:

- Both outputs created.
- Renderer does not modify semantic content.
- Render validation passes.
- If target-page constraints cannot be satisfied, renderer reports overflow rather than silently deleting content.

## 15. Audit

Run:

```text
resume audit
```

Expected report includes:

- initial score,
- final score,
- job requirement statuses,
- persisted/verified facts,
- applied changes,
- rejected hallucinated change,
- validation results,
- versions/config hash.

---

# Smoke-Test Pass Criteria

The smoke test passes only if all of the following are true:

- All packages load/build.
- SQLite migration succeeds.
- Resume and job canonical schemas validate.
- Base resume is immutable after ingest.
- Career facts are persisted with evidence.
- MCP surface can search facts without raw SQL exposure.
- Match score is reproducible.
- User confirmation updates the career model correctly.
- Agent outputs are treated as proposals.
- Valid grounded rewrite can be applied.
- Deliberately hallucinated rewrite is rejected.
- Final resume passes grounding and ATS validation.
- At least one render format succeeds; release target should require Markdown + DOCX.
- Audit report explains the run.

Any failure in the hallucination rejection, base immutability, DB verification state, or deterministic scoring tests is release-blocking.
