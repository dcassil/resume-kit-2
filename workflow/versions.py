"""Version collection for workflow run manifests."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from career_store import CAREER_STORE_SCHEMA_VERSION, openCareerStore
from resume_core import (
    CANONICAL_RESUME_SCHEMA_VERSION,
    JOB_MODEL_SCHEMA_VERSION,
    RESUME_CHANGE_OPERATION_SCHEMA_VERSION,
    matchingVersions,
)

from .schemas import CAREER_DB_VERSION_UNAVAILABLE_STATUS, RUN_MANIFEST_SCHEMA_VERSION


JsonObject = dict[str, Any]

PACKAGE_IMPORTS = {
    "workflow": "workflow",
    "resume-core": "resume_core",
    "career-store": "career_store",
}
PACKAGE_DISTRIBUTIONS = {
    "workflow": ("resume-kit",),
    "resume-core": ("resume-kit",),
    "career-store": ("resume-kit",),
}
CAREER_DB_VERSION_UNAVAILABLE: JsonObject = {
    "status": CAREER_DB_VERSION_UNAVAILABLE_STATUS,
    "reason": "career_db_not_configured",
}


class VersionSourceUnavailableError(RuntimeError):
    """Raised when a manifest version cannot be read from its source."""

    def __init__(self, source: str, detail: str) -> None:
        self.source = source
        self.detail = detail
        super().__init__(f"Version source unavailable: {source}: {detail}")


def collectVersions(
    *,
    workspace: str | Path | None = None,
    config: JsonObject | None = None,
    run_state: JsonObject | None = None,
    career_store: Any | None = None,
) -> JsonObject:
    versions: JsonObject = {
        "package_versions": {
            package: _installed_package_version(package, import_name)
            for package, import_name in PACKAGE_IMPORTS.items()
        },
        "schema_versions": {
            "canonical_resume": _required_version(
                "schema_versions.canonical_resume",
                CANONICAL_RESUME_SCHEMA_VERSION,
            ),
            "job": _required_version("schema_versions.job", JOB_MODEL_SCHEMA_VERSION),
            "career_db": _required_version("schema_versions.career_db", CAREER_STORE_SCHEMA_VERSION),
            "change_operation": _required_version(
                "schema_versions.change_operation",
                RESUME_CHANGE_OPERATION_SCHEMA_VERSION,
            ),
            "run_manifest": _required_version("schema_versions.run_manifest", RUN_MANIFEST_SCHEMA_VERSION),
        },
    }
    versions.update(_matching_versions())
    versions["careerDbVersion"] = _career_db_version(
        workspace=workspace,
        config=config,
        run_state=run_state,
        career_store=career_store,
    )
    return versions


def _installed_package_version(package: str, import_name: str) -> str:
    source = f"package_versions.{package}"
    candidates = [
        *importlib_metadata.packages_distributions().get(import_name, ()),
        *PACKAGE_DISTRIBUTIONS.get(package, ()),
    ]
    for distribution in _dedupe(candidates):
        try:
            return _required_version(source, importlib_metadata.version(distribution))
        except importlib_metadata.PackageNotFoundError:
            continue
    raise VersionSourceUnavailableError(source, f"no installed distribution found for import package {import_name}")


def _matching_versions() -> JsonObject:
    source = "resume_core.matchingVersions"
    try:
        versions = matchingVersions()
    except Exception as exc:  # pragma: no cover - defensive wrapper keeps source named.
        raise VersionSourceUnavailableError(source, str(exc)) from exc
    if not isinstance(versions, dict):
        raise VersionSourceUnavailableError(source, "expected a mapping")
    return {
        "matching_algorithm_version": _required_version(
            "matching_algorithm_version",
            versions.get("matching_algorithm_version"),
        ),
        "matching_config_version": _required_version(
            "matching_config_version",
            versions.get("matching_config_version"),
        ),
    }


def _career_db_version(
    *,
    workspace: str | Path | None,
    config: JsonObject | None,
    run_state: JsonObject | None,
    career_store: Any | None,
) -> JsonObject:
    source = "careerDbVersion"
    store = career_store or (run_state or {}).get("career_store")
    if store is not None:
        return _migration_state(source, store)

    database_path, configured = _career_db_path(workspace=workspace, config=config, run_state=run_state)
    if database_path is None:
        return dict(CAREER_DB_VERSION_UNAVAILABLE)
    if database_path.exists():
        return _migration_state(source, openCareerStore(str(database_path)))
    if configured:
        raise VersionSourceUnavailableError(source, f"configured career DB does not exist: {database_path}")
    return dict(CAREER_DB_VERSION_UNAVAILABLE)


def _migration_state(source: str, store: Any) -> JsonObject:
    getter = getattr(store, "getMigrationState", None)
    if not callable(getter):
        raise VersionSourceUnavailableError(source, "career store does not expose getMigrationState")
    state = getter()
    if is_dataclass(state):
        payload = asdict(state)
    elif isinstance(state, dict):
        payload = dict(state)
    else:
        raise VersionSourceUnavailableError(source, "getMigrationState returned unsupported state")
    if payload.get("status") == CAREER_DB_VERSION_UNAVAILABLE_STATUS:
        return payload
    for field in ["schema_version", "database_path", "applied_migrations", "pending_migrations", "status", "metadata"]:
        if field not in payload:
            raise VersionSourceUnavailableError(source, f"getMigrationState missing {field}")
    return payload


def _career_db_path(
    *,
    workspace: str | Path | None,
    config: JsonObject | None,
    run_state: JsonObject | None,
) -> tuple[Path | None, bool]:
    config = config or {}
    run_state = run_state or {}
    recorded_career_db = run_state.get("careerDbVersion")
    if isinstance(recorded_career_db, dict) and recorded_career_db.get("database_path"):
        return Path(str(recorded_career_db["database_path"])), True
    for source in (run_state, config, config.get("paths") if isinstance(config.get("paths"), dict) else {}):
        for key in ("career_db_path", "careerDbPath", "career_db", "careerDb"):
            raw = source.get(key)
            if raw:
                return Path(str(raw)), True

    workspace_value = workspace or run_state.get("workspace")
    if workspace_value:
        return Path(str(workspace_value)) / "data" / "career.db", False
    return None, False


def _required_version(source: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise VersionSourceUnavailableError(source, "source returned an empty or non-string version")
    return value


def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
