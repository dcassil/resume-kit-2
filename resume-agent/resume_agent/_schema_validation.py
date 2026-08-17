"""Stdlib JSON-schema subset checks for adapter payloads."""

from __future__ import annotations

from typing import Any


JsonObject = dict[str, Any]
JsonSchemaRegistry = dict[str, JsonObject]


def validate_json_schema(value: Any, schema: JsonObject, field_path: str = "") -> list[JsonObject]:
    """Return structured violations for the schema subset used by agent adapters."""

    violations: list[JsonObject] = []

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        violations.append(
            _violation("invalid_enum", "Value is not one of the allowed values.", field_path, {"allowed": enum_values})
        )

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_any_type(value, expected_type):
        violations.append(
            _violation(
                "invalid_type",
                f"Expected {_type_label(expected_type)}.",
                field_path,
                {"actual": type(value).__name__, "expected": expected_type},
            )
        )
        return violations

    min_length = schema.get("minLength")
    if isinstance(min_length, int) and isinstance(value, str) and len(value) < min_length:
        violations.append(_violation("min_length", f"Expected at least {min_length} character(s).", field_path))

    max_length = schema.get("maxLength")
    if isinstance(max_length, int) and isinstance(value, str) and len(value) > max_length:
        violations.append(_violation("max_length", f"Expected at most {max_length} character(s).", field_path))

    minimum = schema.get("minimum")
    if isinstance(minimum, (int, float)) and isinstance(value, (int, float)) and not isinstance(value, bool) and value < minimum:
        violations.append(_violation("minimum", f"Expected at least {minimum}.", field_path, {"minimum": minimum}))

    if _is_object_schema(schema) and isinstance(value, dict):
        violations.extend(_object_violations(value, schema, field_path))

    if _is_array_schema(schema) and isinstance(value, list):
        violations.extend(_array_violations(value, schema, field_path))

    return violations


def validate_schema_id(value: Any, schema_id: str, schemas: JsonSchemaRegistry) -> list[JsonObject]:
    schema = schemas.get(schema_id)
    if not isinstance(schema, dict):
        return [
            _violation(
                "unknown_schema",
                "No output schema is registered for the requested schema id.",
                "output_schema_id",
                {"schema_id": schema_id},
            )
        ]
    return validate_json_schema(value, schema)


def _object_violations(value: JsonObject, schema: JsonObject, field_path: str) -> list[JsonObject]:
    violations: list[JsonObject] = []
    properties = schema.get("properties", {})
    property_schemas = properties if isinstance(properties, dict) else {}

    for field_name in schema.get("required", []):
        if isinstance(field_name, str) and field_name not in value:
            violations.append(_violation("missing_field", f"Object requires {field_name}.", _join_path(field_path, field_name)))

    for field_name, field_schema in property_schemas.items():
        if field_name in value and isinstance(field_schema, dict):
            violations.extend(validate_json_schema(value[field_name], field_schema, _join_path(field_path, str(field_name))))

    additional_schema = schema.get("additionalProperties")
    if additional_schema is False:
        for field_name in sorted(set(value) - set(property_schemas)):
            violations.append(
                _violation(
                    "additional_property",
                    "Field is not declared by this schema.",
                    _join_path(field_path, str(field_name)),
                )
            )
    elif isinstance(additional_schema, dict):
        for field_name, item in value.items():
            if field_name not in property_schemas:
                violations.extend(validate_json_schema(item, additional_schema, _join_path(field_path, str(field_name))))

    return violations


def _array_violations(value: list[Any], schema: JsonObject, field_path: str) -> list[JsonObject]:
    violations: list[JsonObject] = []
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(value) < min_items:
        violations.append(_violation("min_items", f"Expected at least {min_items} item(s).", field_path))

    item_schema = schema.get("items")
    if isinstance(item_schema, dict):
        for index, item in enumerate(value):
            violations.extend(validate_json_schema(item, item_schema, _join_path(field_path, str(index))))
    return violations


def _is_object_schema(schema: JsonObject) -> bool:
    return schema.get("type") == "object" or "properties" in schema or "required" in schema


def _is_array_schema(schema: JsonObject) -> bool:
    return schema.get("type") == "array" or "items" in schema


def _matches_any_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, str):
        return _matches_type(value, expected_type)
    if isinstance(expected_type, list):
        return any(isinstance(item, str) and _matches_type(value, item) for item in expected_type)
    return True


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _type_label(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " or ".join(str(item) for item in expected_type)
    return str(expected_type)


def _violation(code: str, message: str, field_path: str, details: JsonObject | None = None) -> JsonObject:
    violation: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path:
        violation["field_path"] = field_path
    if details:
        violation["details"] = details
    return violation


def _join_path(parent: str, child: str) -> str:
    return f"{parent}/{child}" if parent else child


__all__ = ["JsonObject", "JsonSchemaRegistry", "validate_json_schema", "validate_schema_id"]
