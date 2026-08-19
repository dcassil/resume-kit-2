"""Private argv arity contract for the resume CLI dispatch.

Silently ignored trailing arguments would run commands the caller did not ask
for (e.g. `resume init --help` executing init), so every command declares the
exact argv shapes it accepts and anything else is a typed usage error.
"""

from __future__ import annotations

from typing import Any, Callable

JsonObject = dict[str, Any]

COMMAND_ARITY = {
    # command tuple prefix -> exact expected argv length.
    ("init",): 1,
    ("status",): 1,
    ("ingest",): 2,
    ("job", "ingest"): 3,
    # match accepts an optional --working flag (explicit form of its default:
    # score the working resume); protected smoke drives that spelling.
    ("match", "--working"): 2,
    ("match",): 1,
    ("resolve",): 1,
    ("tailor",): 1,
    ("validate",): 1,
    ("run",): 3,
    ("inspect", "fact"): 3,
    ("inspect", "requirement"): 3,
    ("audit",): 1,
}


def unexpected_arguments_error(
    args: list[str],
    make_error: Callable[..., JsonObject],
    usage_exit_code: int,
) -> JsonObject | None:
    for prefix, expected in COMMAND_ARITY.items():
        if tuple(args[: len(prefix)]) == prefix:
            if len(args) != expected:
                extra = " ".join(args[expected:]) or " ".join(args[len(prefix):])
                return make_error(
                    "usage_error",
                    f"unexpected arguments for '{' '.join(prefix)}': {extra}",
                    ref="argv",
                    exit_code=usage_exit_code,
                )
            return None
    if args and args[0] == "export":
        rest = args[1:]
        if rest and not (len(rest) == 2 and rest[0] == "--format"):
            return make_error(
                "usage_error",
                f"unexpected arguments for 'export': {' '.join(rest)}",
                ref="argv",
                exit_code=usage_exit_code,
            )
    return None
