"""Command entry point for the career-mcp stdio server.

Run with `python -m career_mcp --db <path>`. If `--db` is omitted, the entry
point falls back to `CAREER_MCP_DB`.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections.abc import Callable, Mapping
from typing import Any, TextIO

from career_store import openCareerStore

from . import create_career_mcp
from .server import close_store, run_stdio_server


class _CleanShutdown(Exception):
    pass


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    env: Mapping[str, str] | None = None,
    store_factory: Callable[[str], Any] = openCareerStore,
    adapter_factory: Callable[..., Any] = create_career_mcp,
    server_runner: Callable[[Any, TextIO | None, TextIO | None], int] = run_stdio_server,
) -> int:
    error_stream = stderr if stderr is not None else sys.stderr
    environment = env if env is not None else os.environ
    args = _parser().parse_args(argv)
    db_path = args.db or environment.get("CAREER_MCP_DB")
    if not db_path:
        _write_startup_error(error_stream, "missing_db", None)
        return 2

    store = None
    previous_sigterm = _install_sigterm_handler()
    try:
        store = store_factory(db_path)
        adapter = adapter_factory(store=store)
        return server_runner(adapter, stdin, stdout)
    except _CleanShutdown:
        return 0
    except Exception:
        if store is None:
            _write_startup_error(error_stream, "store_open_failed", db_path)
            return 1
        raise
    finally:
        if store is not None:
            close_store(store)
        _restore_sigterm_handler(previous_sigterm)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the career-mcp stdio JSON-RPC server.")
    parser.add_argument("--db", help="Career-store database path. Defaults to CAREER_MCP_DB.")
    return parser


def _install_sigterm_handler() -> Any:
    try:
        previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, _raise_clean_shutdown)
        return previous
    except ValueError:
        return None


def _restore_sigterm_handler(previous: Any) -> None:
    if previous is None:
        return
    try:
        signal.signal(signal.SIGTERM, previous)
    except ValueError:
        pass


def _raise_clean_shutdown(_signum: int, _frame: Any) -> None:
    raise _CleanShutdown()


def _write_startup_error(stderr: TextIO, error_type: str, supplied_path: str | None) -> None:
    parts = ["career_mcp_startup_error", f"type={error_type}"]
    if supplied_path is not None:
        scrubbed_path = supplied_path.replace("\r", "\\r").replace("\n", "\\n")
        parts.append(f"path={scrubbed_path!r}")
    stderr.write(" ".join(parts) + "\n")
    stderr.flush()


if __name__ == "__main__":
    raise SystemExit(main())
