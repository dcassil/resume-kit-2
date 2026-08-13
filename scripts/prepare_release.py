#!/usr/bin/env python3
"""Prepare release metadata for GitHub Actions.

This script updates the project version in pyproject.toml, prepends a
changelog entry, and writes release notes for `gh release create`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
BUMP_CHOICES = {"major", "minor", "patch"}


def run_git(root: Path, args: list[str], allow_failure: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode and not allow_failure:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value)
    if not match:
        raise ValueError(f"version must use MAJOR.MINOR.PATCH format: {value!r}")
    return tuple(int(part) for part in match.groups())


def bump_version(current: str, bump: str) -> str:
    if bump not in BUMP_CHOICES:
        raise ValueError(f"bump must be one of {sorted(BUMP_CHOICES)}")

    major, minor, patch = parse_version(current)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def read_project_version(pyproject: Path) -> str:
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str):
        raise ValueError("[project].version must be a string")
    return version


def update_project_version(pyproject: Path, version: str) -> None:
    lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
    in_project = False
    replaced = False
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
        elif stripped.startswith("[") and stripped.endswith("]"):
            in_project = False

        if in_project and stripped.startswith("version = "):
            output.append(f'version = "{version}"\n')
            replaced = True
        else:
            output.append(line)

    if not replaced:
        raise ValueError("could not find [project] version in pyproject.toml")

    pyproject.write_text("".join(output), encoding="utf-8")


def last_release_tag(root: Path) -> str | None:
    tag = run_git(root, ["describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"], allow_failure=True)
    return tag or None


def release_commits(root: Path, previous_tag: str | None) -> list[str]:
    revision = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
    log = run_git(root, ["log", "--no-merges", "--format=%s (%h)", revision], allow_failure=True)
    return [line for line in log.splitlines() if line.strip()]


def render_release_notes(version: str, previous_tag: str | None, commits: list[str]) -> str:
    heading = f"## v{version} - {date.today().isoformat()}"
    if commits:
        body = "\n".join(f"- {item}" for item in commits)
    else:
        body = "- Maintenance release."

    if previous_tag:
        body = f"{body}\n\nChanges since `{previous_tag}`."
    else:
        body = f"{body}\n\nInitial tagged release."

    return f"{heading}\n\n{body}\n"


def update_changelog(changelog: Path, release_notes: str) -> None:
    if changelog.exists():
        existing = changelog.read_text(encoding="utf-8")
        if existing.startswith("# Changelog\n\n"):
            changelog.write_text("# Changelog\n\n" + release_notes + "\n" + existing[len("# Changelog\n\n") :], encoding="utf-8")
            return
        changelog.write_text("# Changelog\n\n" + release_notes + "\n" + existing, encoding="utf-8")
        return

    changelog.write_text("# Changelog\n\n" + release_notes, encoding="utf-8")


def write_github_output(version: str, tag: str, notes_file: Path) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"version={version}\n")
        handle.write(f"tag={tag}\n")
        handle.write(f"notes_file={notes_file}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    version_source = parser.add_mutually_exclusive_group(required=True)
    version_source.add_argument("--version", help="Release version in MAJOR.MINOR.PATCH format.")
    version_source.add_argument("--bump", choices=sorted(BUMP_CHOICES), help="Bump current version by this release type.")
    parser.add_argument("--notes-file", default=".release-notes.md", help="Where to write GitHub Release notes.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    pyproject = root / "pyproject.toml"
    changelog = root / "CHANGELOG.md"
    notes_file = (root / args.notes_file).resolve()

    try:
        current_version = read_project_version(pyproject)
        parse_version(current_version)
        version = args.version.removeprefix("v") if args.version else bump_version(current_version, args.bump)
        tag = f"v{version}"
        parse_version(version)
        if parse_version(version) <= parse_version(current_version):
            raise ValueError(f"release version {version} must be greater than current version {current_version}")

        previous_tag = last_release_tag(root)
        commits = release_commits(root, previous_tag)
        notes = render_release_notes(version, previous_tag, commits)

        update_project_version(pyproject, version)
        update_changelog(changelog, notes)
        notes_file.write_text(notes, encoding="utf-8")
        write_github_output(version, tag, notes_file)
    except (RuntimeError, ValueError) as exc:
        print(f"prepare release failed: {exc}", file=sys.stderr)
        return 1

    print(f"prepared {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
