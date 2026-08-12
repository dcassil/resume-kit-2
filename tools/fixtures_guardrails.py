#!/usr/bin/env python3
"""Hard-blocking guardrails for stable fixture truth and snapshot contracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_DIRS = {"resumes", "jobs", "answers", "operations", "expected", "migrations"}
UNSUPPORTED_RESUME_TRUTH = [
    "AWS",
    "GraphQL",
    "responsive design",
    "Staff Software Engineer",
    "20 million users",
    "30 direct reports",
    "30 engineers",
    "global scale",
]
INVALID_OPERATION_REASONS = {
    "unsupported_scale",
    "unsupported_management_scope",
    "title_inflation",
    "years_inflation",
    "related_skill_overreach",
}


@dataclass(frozen=True)
class Failure:
    path: Path
    message: str
    solution: str
    line: int | None = None

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        where = f"{rel}:{self.line}" if self.line else str(rel)
        return f"- {where}\n  Why it failed: {self.message}\n  Possible solution: {self.solution}"


def load_json(path: Path) -> tuple[dict, Failure | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return {}, Failure(path, f"Invalid JSON: {exc.msg}.", "Fix JSON syntax so fixture contracts are machine-checkable.", exc.lineno)


def line_for_text(text: str, needle: str) -> int:
    return text[: text.lower().find(needle.lower())].count("\n") + 1


def validate_manifest(root: Path) -> list[Failure]:
    path = root / "fixtures" / "fixture_manifest.json"
    if not path.exists():
        return [Failure(path, "Missing fixture manifest.", "Restore fixtures/fixture_manifest.json as the single fixture index.")]
    manifest, failure = load_json(path)
    if failure:
        return [failure]

    failures: list[Failure] = []
    dirs = set(manifest.get("required_directories", []))
    if dirs != REQUIRED_DIRS:
        failures.append(
            Failure(
                path,
                f"Required fixture directories are misaligned. Missing={sorted(REQUIRED_DIRS - dirs)}; extra={sorted(dirs - REQUIRED_DIRS)}.",
                "Keep fixtures grouped by resumes, jobs, answers, operations, expected, and migrations.",
            )
        )
    for directory in REQUIRED_DIRS:
        target = root / "fixtures" / directory
        if not target.exists() or not target.is_dir():
            failures.append(Failure(target, "Required fixture directory is missing.", "Create the directory so future tests have stable paths."))

    if manifest.get("schema_version") != "fixtures.v1" or not manifest.get("config_hash"):
        failures.append(
            Failure(
                path,
                "Manifest must include schema_version='fixtures.v1' and a config_hash.",
                "Add stable review metadata before using fixtures in contract/smoke/E2E tests.",
            )
        )
    return failures


def validate_resume(root: Path, manifest: dict) -> list[Failure]:
    failures: list[Failure] = []
    spec = manifest.get("resume_fixture", {})
    path = root / "fixtures" / spec.get("path", "")
    if not path.exists():
        return [Failure(path, "Required resume fixture is missing.", "Restore the main resume fixture declared in fixture_manifest.json.")]
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()

    for required in spec.get("must_include", []):
        if required.lower() not in lowered:
            failures.append(
                Failure(
                    path,
                    f"Resume fixture is missing required truth '{required}'.",
                    "Add supported source text to the resume fixture or update fixtures/TEST_SPEC.md before changing expectations.",
                )
            )
    for forbidden in UNSUPPORTED_RESUME_TRUTH:
        if forbidden.lower() in lowered:
            failures.append(
                Failure(
                    path,
                    f"Resume fixture contains unsupported truth '{forbidden}'.",
                    "Remove it from the resume fixture. AWS/GraphQL/Staff title/scale/large management claims must remain absent to preserve honesty tests.",
                    line_for_text(text, forbidden),
                )
            )

    if not any(ch in text for ch in ["\u201c", "\u201d", "\u2018", "\u2019"]):
        failures.append(Failure(path, "Resume fixture lacks smart-quote formatting noise.", "Include smart quotes so ATS sanitation is exercised."))
    if "\u00a0" not in text:
        failures.append(Failure(path, "Resume fixture lacks non-breaking-space formatting noise.", "Include NBSP so normalization is exercised."))
    if "\u25e6" not in text:
        failures.append(Failure(path, "Resume fixture lacks odd bullet formatting noise.", "Include an atypical bullet glyph so sanitation is exercised."))
    if "2013 to Dec 2017" not in text:
        failures.append(Failure(path, "Resume fixture lacks inconsistent date representation.", "Keep one inconsistent date format for date-normalization tests."))
    return failures


def validate_jobs(root: Path, manifest: dict) -> list[Failure]:
    failures: list[Failure] = []
    for job in manifest.get("job_fixtures", []):
        path = root / "fixtures" / job.get("path", "")
        if not path.exists():
            failures.append(Failure(path, "Job fixture is missing.", "Restore the job fixture declared in fixture_manifest.json."))
            continue
        text = path.read_text(encoding="utf-8").lower()
        for term in [job.get("title", ""), *job.get("required_terms", []), *job.get("preferred_terms", [])]:
            if term and term.lower() not in text:
                failures.append(Failure(path, f"Job fixture is missing expected term '{term}'.", "Keep job fixtures aligned with fixtures/TEST_SPEC.md."))
        if "required" not in text or "preferred" not in text:
            failures.append(Failure(path, "Job fixture must distinguish required and preferred requirements.", "Add explicit Required and Preferred sections."))
    return failures


def validate_answers(root: Path, manifest: dict) -> list[Failure]:
    failures: list[Failure] = []
    for answer in manifest.get("answer_fixtures", []):
        path = root / "fixtures" / answer.get("path", "")
        if not path.exists():
            failures.append(Failure(path, "Answer fixture is missing.", "Restore the exact answer fixture declared in fixture_manifest.json."))
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text != answer.get("exact_text"):
            failures.append(
                Failure(
                    path,
                    "Answer fixture text drifted from the exact contract string.",
                    "Restore the exact text so user-answer interpretation tests remain deterministic.",
                )
            )
    return failures


def validate_operations(root: Path, manifest: dict) -> list[Failure]:
    failures: list[Failure] = []
    canonical_paths = set(manifest.get("canonical_paths", []))
    seen_reasons: set[str] = set()
    for rel in manifest.get("invalid_operations", []):
        path = root / "fixtures" / rel
        if not path.exists():
            failures.append(Failure(path, "Invalid operation fixture is missing.", "Restore all invalid operation fixtures declared in the manifest."))
            continue
        operation, failure = load_json(path)
        if failure:
            failures.append(failure)
            continue
        if operation.get("expected_status") != "rejected":
            failures.append(Failure(path, "Invalid operation must expect rejection.", "Set expected_status to rejected."))
        reason = operation.get("expected_reason")
        if reason not in INVALID_OPERATION_REASONS:
            failures.append(
                Failure(
                    path,
                    f"Invalid operation expected_reason '{reason}' is not one of {sorted(INVALID_OPERATION_REASONS)}.",
                    "Use the contract-defined rejection reason so honesty tests stay stable.",
                )
            )
        else:
            seen_reasons.add(reason)
        if operation.get("target_path") not in canonical_paths:
            failures.append(
                Failure(
                    path,
                    f"Invalid operation target_path '{operation.get('target_path')}' is not in manifest canonical_paths.",
                    "Target an existing canonical path or update the canonical path list deliberately.",
                )
            )
    missing = INVALID_OPERATION_REASONS - seen_reasons
    if missing:
        failures.append(
            Failure(
                root / "fixtures" / "fixture_manifest.json",
                f"Missing invalid operation coverage for {sorted(missing)}.",
                "Add one rejected operation fixture for every required honesty failure mode.",
            )
        )
    return failures


def validate_expected_snapshots(root: Path, manifest: dict) -> list[Failure]:
    failures: list[Failure] = []
    expected = manifest.get("expected_snapshots", [])
    if len(expected) != 13:
        failures.append(
            Failure(
                root / "fixtures" / "fixture_manifest.json",
                f"Expected snapshot count is {len(expected)}, expected 13.",
                "Keep all normalized/match/selection/operation/manifest/audit snapshots declared.",
            )
        )
    for rel in expected:
        path = root / "fixtures" / rel
        if not path.exists():
            failures.append(Failure(path, "Expected snapshot fixture is missing.", "Restore the reviewed expected snapshot declared in the manifest."))
            continue
        snapshot, failure = load_json(path)
        if failure:
            failures.append(failure)
            continue
        for field in ["fixture_id", "schema_version", "config_hash", "reviewed", "expected_observations"]:
            if field not in snapshot:
                failures.append(Failure(path, f"Expected snapshot is missing '{field}'.", "Snapshots must be reviewed contract artifacts, not accidental output."))
        if snapshot.get("reviewed") is not True:
            failures.append(Failure(path, "Expected snapshot must be marked reviewed=true.", "Review and mark the snapshot before using it as a contract artifact."))
    return failures


def run(root: Path) -> list[Failure]:
    failures = validate_manifest(root)
    manifest_path = root / "fixtures" / "fixture_manifest.json"
    if not manifest_path.exists():
        return failures
    manifest, failure = load_json(manifest_path)
    if failure:
        return failures
    failures.extend(validate_resume(root, manifest))
    failures.extend(validate_jobs(root, manifest))
    failures.extend(validate_answers(root, manifest))
    failures.extend(validate_operations(root, manifest))
    failures.extend(validate_expected_snapshots(root, manifest))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("fixtures guardrails failed.\n")
        print("Fixtures must preserve stable truth, deterministic inputs, explicit invalid operations, and reviewed snapshots.")
        print("Unsupported resume truth, answer drift, missing snapshot metadata, and hidden implementation assumptions are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1
    print("fixtures guardrails passed: stable inputs, answer text, invalid operations, and expected snapshots are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
