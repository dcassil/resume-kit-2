"""Internal JSON Pointer helpers for resume-core change operations."""

from __future__ import annotations

from typing import Any

from .schemas import JsonObject


def _pointer_value(document: Any, pointer: str) -> tuple[bool, Any]:
    if not pointer.startswith("/"):
        return False, None
    current = document
    for token in pointer.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        elif isinstance(current, list) and token == "-":
            return False, None
        else:
            return False, None
    return True, current


def _pointer_parent_exists(document: Any, pointer: str) -> bool:
    if not pointer.startswith("/"):
        return False
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer.strip("/").split("/")]
    if not tokens:
        return False
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False
    final = tokens[-1]
    return isinstance(current, dict) or (isinstance(current, list) and (final == "-" or final.isdigit()))


def _append_already_present(document: Any, pointer: str, value: Any) -> bool:
    if not pointer.endswith("/-"):
        return False
    parent_pointer = pointer[:-2]
    exists, parent = _pointer_value(document, parent_pointer)
    return bool(exists and isinstance(parent, list) and value in parent)


def _set_pointer(document: JsonObject, pointer: str, value: Any) -> bool:
    if not pointer.startswith("/"):
        return False
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer.strip("/").split("/")]
    current: Any = document
    for token in tokens[:-1]:
        if isinstance(current, dict):
            if token not in current:
                current[token] = {}
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False
    final = tokens[-1] if tokens else ""
    if isinstance(current, dict):
        current[final] = value
        return True
    if isinstance(current, list):
        if final == "-":
            current.append(value)
            return True
        if final.isdigit() and int(final) < len(current):
            current[int(final)] = value
            return True
    return False
