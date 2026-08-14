"""Internal lifecycle and pointer semantics for resume change operations."""

from __future__ import annotations

import copy
from typing import Any

from .pointers import _append_already_present, _pointer_parent_exists, _pointer_value, _set_pointer
from .schemas import ChangeOperationStatus, JsonObject


CHANGE_OPERATION_STATUS_TRANSITIONS = {
    ChangeOperationStatus.PROPOSED.value: {ChangeOperationStatus.VALIDATED.value},
    ChangeOperationStatus.VALIDATED.value: {
        ChangeOperationStatus.APPLIED.value,
        ChangeOperationStatus.REJECTED.value,
    },
    ChangeOperationStatus.APPLIED.value: {
        ChangeOperationStatus.ACCEPTED.value,
        ChangeOperationStatus.MODIFIED.value,
    },
    ChangeOperationStatus.REJECTED.value: set(),
    ChangeOperationStatus.ACCEPTED.value: set(),
    ChangeOperationStatus.MODIFIED.value: set(),
}
CHANGE_OPERATION_OPS = {"replace", "rewrite", "insert", "remove", "move"}
CHANGE_OPERATION_STATUSES = {status.value for status in ChangeOperationStatus}
MANDATORY_CHANGE_OPERATION_FIELDS = {
    "reason": "missing_reason",
    "linked_requirement_ids": "missing_linked_requirement_ids",
    "linked_fact_ids": "missing_linked_fact_ids",
    "provenance": "missing_provenance",
}


def mandatory_operation_field_errors(operation: JsonObject) -> list[JsonObject]:
    errors: list[JsonObject] = []
    for field_name, code in MANDATORY_CHANGE_OPERATION_FIELDS.items():
        value = item(operation, field_name)
        if not _mandatory_operation_field_present(field_name, value):
            errors.append(issue(code, f"ResumeChangeOperation requires non-empty {field_name}.", field_name))
    return errors


def change_validation_shape_errors(resume: JsonObject, operation: JsonObject) -> tuple[list[JsonObject], str, bool, Any, str]:
    errors = mandatory_operation_field_errors(operation)
    operation_status = str(item(operation, "status", ""))
    if "status" in operation and operation_status not in CHANGE_OPERATION_STATUSES:
        errors.append(issue("invalid_status", _status_message(), "status"))
    elif "status" in operation:
        transition_error = operation_status_transition_error(operation_status, ChangeOperationStatus.VALIDATED.value)
        if transition_error:
            errors.append(transition_error)

    path = operation_path(operation)
    if not path.startswith("/"):
        errors.append(issue("invalid_path", "Operation path must be a JSON pointer.", "path"))
    path_exists, current_value = _pointer_value(resume, path)
    parent_exists = _pointer_parent_exists(resume, path)
    operation_kind = str(item(operation, "op", "replace" if path_exists else "insert"))
    if "op" in operation and operation_kind not in CHANGE_OPERATION_OPS:
        errors.append(issue("invalid_op", "Operation op must be insert, move, remove, replace, or rewrite.", "op"))
    if not parent_exists:
        errors.append(issue("invalid_path", "Operation path parent does not exist in the canonical resume.", "path"))
    errors.extend(_operation_path_errors(resume, operation, path, path_exists, current_value, operation_kind))
    return errors, path, path_exists, current_value, operation_kind


def _apply_operation(resume: JsonObject, operation: JsonObject) -> tuple[bool, JsonObject, Any, str | None]:
    operation_kind = str(item(operation, "op", "replace"))
    candidate = copy.deepcopy(resume)
    path = operation_path(operation)
    before = item(operation, "before")
    after = copy.deepcopy(item(operation, "after"))
    path_exists, current = _pointer_value(candidate, path)

    if operation_kind in {"replace", "rewrite"}:
        if not path_exists:
            return False, resume, None, "missing_target"
        if before != current:
            return False, resume, None, "before_mismatch"
        return _set_pointer(candidate, path, after), candidate, after, None
    if operation_kind == "insert":
        if path_exists and current == after:
            return False, candidate, None, "already_applied"
        if before is not None and before != current:
            return False, resume, None, "before_mismatch"
        return _insert_pointer(candidate, path, after), candidate, after, None
    if operation_kind == "remove":
        if not path_exists:
            return False, candidate, None, "already_applied"
        if before != current:
            return False, resume, None, "before_mismatch"
        return _remove_pointer(candidate, path), candidate, None, None
    if operation_kind == "move":
        return _apply_move(candidate, resume, operation, path, before, after)
    return False, resume, None, "invalid_op"


def _apply_preflight_errors(operation: JsonObject) -> tuple[list[JsonObject], str]:
    status = str(item(operation, "status", ""))
    transition_error = operation_status_transition_error(status, ChangeOperationStatus.APPLIED.value)
    if transition_error:
        return [transition_error], "operation_not_validated"
    mandatory_errors = mandatory_operation_field_errors(operation)
    if mandatory_errors:
        return mandatory_errors, "missing_mandatory_operation_fields"
    return [], ""


def grounding_operation_status_errors(operations: list[JsonObject]) -> tuple[list[JsonObject], list[JsonObject]]:
    errors: list[JsonObject] = []
    grounding_operations: list[JsonObject] = []
    allowed = {
        ChangeOperationStatus.APPLIED.value,
        ChangeOperationStatus.ACCEPTED.value,
        ChangeOperationStatus.MODIFIED.value,
    }
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            errors.append(issue("invalid_applied_operation", "Applied operations must be objects.", f"applied_operations/{index}"))
            continue
        status = str(item(operation, "status", ""))
        if status not in allowed:
            errors.append(
                issue(
                    "invalid_applied_operation_status",
                    "Final validation grounding accepts only applied, accepted, or modified operations.",
                    f"applied_operations/{index}/status",
                    {"operation_id": str(item(operation, "operation_id", "")), "status": status, "allowed_statuses": sorted(allowed)},
                )
            )
            continue
        grounding_operations.append(operation)
    return errors, grounding_operations


def operation_status_transition_error(from_status: str, to_status: str) -> JsonObject | None:
    if from_status not in CHANGE_OPERATION_STATUSES:
        return issue("invalid_status", _status_message(), "status", {"from_status": from_status, "to_status": to_status})
    if to_status not in CHANGE_OPERATION_STATUSES:
        return issue("invalid_status", "Operation target status must be proposed, validated, rejected, applied, accepted, or modified.", "status", {"from_status": from_status, "to_status": to_status})
    if to_status not in CHANGE_OPERATION_STATUS_TRANSITIONS.get(from_status, set()):
        return issue("invalid_status_transition", f"Invalid operation status transition from {from_status} to {to_status}.", "status", {"from_status": from_status, "to_status": to_status})
    return None


def operation_path(operation: JsonObject) -> str:
    return str(item(operation, "path") or item(operation, "target_path") or "")


def operation_from_path(operation: JsonObject) -> str:
    metadata = item(operation, "metadata", {})
    return str(item(operation, "from_path") or item(metadata, "from_path") or "")


def append_already_present(document: Any, pointer: str, value: Any) -> bool:
    return _append_already_present(document, pointer, value)


def pointer_parent_exists(document: Any, pointer: str) -> bool:
    return _pointer_parent_exists(document, pointer)


def pointer_value(document: Any, pointer: str) -> tuple[bool, Any]:
    return _pointer_value(document, pointer)


def item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def issue(code: str, message: str, field_path: str | None = None, details: JsonObject | None = None) -> JsonObject:
    error: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path is not None:
        error["field_path"] = field_path
    if details:
        error["details"] = details
    return error


def _operation_path_errors(resume: JsonObject, operation: JsonObject, path: str, path_exists: bool, current_value: Any, operation_kind: str) -> list[JsonObject]:
    if operation_kind in {"replace", "rewrite"}:
        errors = [] if path_exists else [issue("missing_target", "Replace and rewrite operations require an existing target path.", "path")]
    elif operation_kind == "insert":
        errors = [issue("target_exists", "Insert operations require a new object member, list index, or array append path.", "path")] if path_exists and not _pointer_parent_is_list(resume, path) else []
    elif operation_kind == "remove":
        errors = [] if path_exists else [issue("missing_target", "Remove operations require an existing target path.", "path")]
    elif operation_kind == "move":
        return _move_validation_errors(resume, operation)
    else:
        errors = []
    before = item(operation, "before")
    if operation_kind != "move" and "before" in operation and before != current_value and not (before is None and not path_exists):
        errors.append(issue("before_mismatch", "Operation before value does not match current content.", "before"))
    return errors


def _move_validation_errors(resume: JsonObject, operation: JsonObject) -> list[JsonObject]:
    errors: list[JsonObject] = []
    from_path = operation_from_path(operation)
    if not from_path:
        return [issue("missing_from_path", "Move operations require a from_path source pointer.", "from_path")]
    if not from_path.startswith("/"):
        return [issue("invalid_path", "Move operation from_path must be a JSON pointer.", "from_path")]
    source_exists, source_value = _pointer_value(resume, from_path)
    if not source_exists:
        errors.append(issue("missing_source", "Move operations require an existing source path.", "from_path"))
    if "before" in operation and item(operation, "before") != source_value:
        errors.append(issue("before_mismatch", "Operation before value does not match source content.", "before"))
    if "after" in operation and item(operation, "after") is not None and item(operation, "after") != source_value:
        errors.append(issue("after_mismatch", "Move operation after value must match source content.", "after"))
    return errors


def _apply_move(candidate: JsonObject, original: JsonObject, operation: JsonObject, path: str, before: Any, after: Any) -> tuple[bool, JsonObject, Any, str | None]:
    from_path = operation_from_path(operation)
    source_exists, source_value = _pointer_value(candidate, from_path)
    expected_after = copy.deepcopy(after if after is not None else before)
    if not source_exists:
        destination_exists, destination_value = _pointer_value(candidate, path)
        if destination_exists and destination_value == expected_after:
            return False, candidate, None, "already_applied"
        return False, original, None, "missing_source"
    if before != source_value:
        return False, original, None, "before_mismatch"
    moved_value = copy.deepcopy(after if after is not None else source_value)
    if moved_value != source_value:
        return False, original, None, "after_mismatch"
    if from_path == path:
        return False, candidate, None, "already_applied"
    if not _remove_pointer(candidate, from_path):
        return False, original, None, "missing_source"
    if not _insert_pointer(candidate, path, moved_value):
        return False, original, None, "invalid_path"
    return True, candidate, moved_value, None


def _mandatory_operation_field_present(field_name: str, value: Any) -> bool:
    if field_name == "reason":
        return isinstance(value, str) and bool(value.strip())
    if field_name in {"linked_requirement_ids", "linked_fact_ids"}:
        return isinstance(value, list) and any(isinstance(entry, str) and entry.strip() for entry in value)
    if field_name == "provenance":
        return isinstance(value, list) and bool(value)
    return value is not None


def _pointer_parent(document: Any, pointer: str) -> tuple[bool, Any, str]:
    tokens = _pointer_tokens(pointer)
    if not tokens:
        return False, None, ""
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False, None, tokens[-1]
    return True, current, tokens[-1]


def _pointer_tokens(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        return []
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer.strip("/").split("/")]


def _pointer_parent_is_list(document: Any, pointer: str) -> bool:
    parent_exists, parent, _final = _pointer_parent(document, pointer)
    return bool(parent_exists and isinstance(parent, list))


def _insert_pointer(document: JsonObject, pointer: str, value: Any) -> bool:
    parent_exists, parent, final = _pointer_parent(document, pointer)
    if not parent_exists:
        return False
    if isinstance(parent, dict):
        if final in parent:
            return False
        parent[final] = value
        return True
    if isinstance(parent, list):
        if final == "-":
            parent.append(value)
            return True
        if final.isdigit() and int(final) <= len(parent):
            parent.insert(int(final), value)
            return True
    return False


def _remove_pointer(document: JsonObject, pointer: str) -> bool:
    parent_exists, parent, final = _pointer_parent(document, pointer)
    if not parent_exists:
        return False
    if isinstance(parent, dict) and final in parent:
        del parent[final]
        return True
    if isinstance(parent, list) and final.isdigit() and int(final) < len(parent):
        parent.pop(int(final))
        return True
    return False


def _status_message() -> str:
    return "Operation status must be proposed, validated, rejected, applied, accepted, or modified."
