"""Terminal presentation layer for resume-cli."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from resume_cli import InteractiveTerminalIO
from resume_cli import main as dispatch


JsonObject = dict[str, Any]

_USAGE = """resume — deterministic resume tailoring CLI

usage: resume [--json] <command> [args]

commands:
  init                       initialize the workspace (config, store, run state)
  status                     show workspace status
  ingest <resume-file>       ingest a resume document
  job ingest <file-or-url-text>
                             ingest a job description
  match                      score the working resume against the current job
  resolve                    interactively resolve unresolved requirements
  tailor                     apply validated tailoring operations
  validate                   validate the working resume
  export [--format FORMAT]   export the resume (markdown or docx)
  run <resume> <job>         run the tailoring workflow end to end
  inspect fact <id>          inspect a career fact
  inspect requirement <id>   inspect a job requirement
  audit                      show the audit report

options:
  --json      emit the machine-readable result envelope on stdout
  -h, --help  show this help and exit"""


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(_USAGE, file=out)
        return 0
    json_mode = "--json" in args
    args = [arg for arg in args if arg != "--json"]

    envelope = dispatch(
        argv=args,
        cwd=Path.cwd(),
        stdout=out,
        stderr=err,
        terminal_io=InteractiveTerminalIO(stdin=stdin or sys.stdin, stdout=out, stderr=err),
    )
    if json_mode:
        print(json.dumps(envelope, sort_keys=True), file=out)
    else:
        _render_report(envelope, out)
    _render_errors(envelope, err)
    return _exit_code(envelope)


def _render_report(envelope: JsonObject, stdout: TextIO) -> None:
    report = envelope.get("report")
    if not isinstance(report, dict):
        return
    title = str(report.get("title") or "resume")
    print(title, file=stdout)
    print("=" * len(title), file=stdout)
    summary = str(report.get("summary") or "").strip()
    if summary:
        print(summary, file=stdout)
    for section in report.get("sections", []):
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        if heading:
            print("", file=stdout)
            print(heading, file=stdout)
            print("-" * len(heading), file=stdout)
        for line in section.get("lines", []):
            print(str(line), file=stdout)


def _render_errors(envelope: JsonObject, stderr: TextIO) -> None:
    for error in envelope.get("errors", []):
        if not isinstance(error, dict):
            continue
        typed = {
            "type": "resume_cli.error",
            "code": str(error.get("code") or "validation_error"),
            "message": str(error.get("message") or ""),
            "ref": str(error.get("offending_input_ref") or error.get("ref") or "input"),
        }
        print(json.dumps(typed, sort_keys=True), file=stderr)


def _exit_code(envelope: JsonObject) -> int:
    exit_code = envelope.get("exit_code")
    if isinstance(exit_code, int) and exit_code in {0, 1, 2}:
        return exit_code
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
