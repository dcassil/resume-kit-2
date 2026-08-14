"""Term relationship validation and deterministic indexing."""

from __future__ import annotations

import copy
from typing import Any, Callable

from .schemas import JsonObject, TermRelationshipKind


IssueFactory = Callable[[str, str, str | None, JsonObject | None], JsonObject]
Normalizer = Callable[[Any], str]
SpecificTerms = Callable[[list[str]], list[str]]

_TERM_RELATIONSHIP_KINDS = {kind.value for kind in TermRelationshipKind}
_RELATED_TERM_RELATIONSHIP_KINDS = {
    TermRelationshipKind.RELATED.value,
    TermRelationshipKind.PARENT.value,
    TermRelationshipKind.CHILD.value,
}


def build_term_relationship_index(
    term_relationships: Any,
    term_variants: dict[str, tuple[str, ...]],
    related_requirement_terms: dict[str, tuple[str, ...]],
    issue: IssueFactory,
    normal_text: Normalizer,
) -> tuple[JsonObject, list[JsonObject]]:
    supplied, errors = _validate_term_relationships(term_relationships, issue, normal_text)
    if errors:
        return _empty_relationship_index(), errors

    index = _empty_relationship_index()
    relationships = [*_seed_term_relationships(term_variants, related_requirement_terms, normal_text), *supplied]
    for relationship in sorted(relationships, key=_term_relationship_key):
        from_term = str(relationship["from"])
        to_term = str(relationship["to"])
        kind = str(relationship["kind"])
        if kind == TermRelationshipKind.ALIAS.value:
            _add_relationship(index["alias"], to_term, from_term, normal_text)
            _add_relationship(index["alias"], from_term, to_term, normal_text)
        elif kind in _RELATED_TERM_RELATIONSHIP_KINDS:
            _add_relationship(index["related"], to_term, from_term, normal_text)
            _add_relationship(index["related"], from_term, to_term, normal_text)
        elif kind == TermRelationshipKind.CONTRADICTS.value:
            _add_relationship(index["blocked"], to_term, from_term, normal_text)
            _add_relationship(index["blocked"], from_term, to_term, normal_text)
    return index, []


def relationship_bucket(relationship_index: JsonObject | None, bucket_name: str) -> dict[str, set[str]]:
    if not isinstance(relationship_index, dict):
        return {}
    bucket = relationship_index.get(bucket_name, {})
    return bucket if isinstance(bucket, dict) else {}


def blocked_terms_for(terms: list[str], relationship_index: JsonObject | None, specific_terms: SpecificTerms) -> set[str]:
    blocked: set[str] = set()
    blocked_bucket = relationship_bucket(relationship_index, "blocked")
    for term in specific_terms(terms):
        blocked.update(blocked_bucket.get(term, set()))
    return blocked


def _validate_term_relationships(
    term_relationships: Any,
    issue: IssueFactory,
    normal_text: Normalizer,
) -> tuple[list[JsonObject], list[JsonObject]]:
    if term_relationships is None:
        return [], []
    if not isinstance(term_relationships, list):
        return [], [issue("invalid_term_relationships", "term_relationships must be an array.", "term_relationships", None)]

    relationships: list[JsonObject] = []
    errors: list[JsonObject] = []
    required_fields = {"from", "to", "kind", "provenance"}
    for index, relationship in enumerate(term_relationships):
        path = f"term_relationships/{index}"
        if not isinstance(relationship, dict):
            errors.append(issue("invalid_term_relationship", "TermRelationship must be an object.", path, None))
            continue
        missing = required_fields - set(relationship)
        for field_name in sorted(missing):
            errors.append(issue("missing_term_relationship_field", "TermRelationship requires this field.", f"{path}/{field_name}", None))
        if missing:
            continue
        kind = str(relationship.get("kind"))
        if kind not in _TERM_RELATIONSHIP_KINDS:
            errors.append(
                issue(
                    "invalid_term_relationship_kind",
                    "TermRelationship kind must be alias, related, parent, child, or contradicts.",
                    f"{path}/kind",
                    {"kind": kind},
                )
            )
            continue
        from_term = normal_text(relationship.get("from"))
        to_term = normal_text(relationship.get("to"))
        if not from_term or not to_term:
            errors.append(issue("invalid_term_relationship_term", "TermRelationship from and to must be non-empty terms.", path, None))
            continue
        relationships.append(
            {
                "from": from_term,
                "to": to_term,
                "kind": kind,
                "provenance": copy.deepcopy(relationship.get("provenance")),
            }
        )
    return relationships, errors


def _seed_term_relationships(
    term_variants: dict[str, tuple[str, ...]],
    related_requirement_terms: dict[str, tuple[str, ...]],
    normal_text: Normalizer,
) -> list[JsonObject]:
    relationships: list[JsonObject] = []
    for canonical, variants in term_variants.items():
        canonical_term = normal_text(canonical)
        for variant in variants:
            variant_term = normal_text(variant)
            if variant_term and variant_term != canonical_term:
                relationships.append(
                    {
                        "from": variant_term,
                        "to": canonical_term,
                        "kind": TermRelationshipKind.ALIAS.value,
                        "provenance": {"source": "resume-core-seed", "vocabulary": "_TERM_VARIANTS"},
                    }
                )
    for canonical, related_terms in related_requirement_terms.items():
        canonical_term = normal_text(canonical)
        for related in related_terms:
            related_term = normal_text(related)
            if related_term and related_term != canonical_term:
                relationships.append(
                    {
                        "from": related_term,
                        "to": canonical_term,
                        "kind": TermRelationshipKind.RELATED.value,
                        "provenance": {"source": "resume-core-seed", "vocabulary": "_RELATED_REQUIREMENT_TERMS"},
                    }
                )
    return relationships


def _empty_relationship_index() -> JsonObject:
    return {"alias": {}, "related": {}, "blocked": {}}


def _term_relationship_key(relationship: JsonObject) -> tuple[str, str, str]:
    return (str(relationship.get("from", "")), str(relationship.get("to", "")), str(relationship.get("kind", "")))


def _add_relationship(bucket: dict[str, set[str]], key: str, value: str, normal_text: Normalizer) -> None:
    normalized_key = normal_text(key)
    normalized_value = normal_text(value)
    if normalized_key and normalized_value:
        bucket.setdefault(normalized_key, set()).add(normalized_value)
