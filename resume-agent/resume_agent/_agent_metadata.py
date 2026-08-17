"""Private agent metadata block for workflow manifests."""

from __future__ import annotations

import re
from importlib import resources
from typing import Any

from ._agent_config import AgentConfig, stable_agent_config_hash
from ._call_audit import hash_prompt_template
from ._fake_adapter import FAKE_ADAPTER_ID, FAKE_ADAPTER_VERSION, FAKE_MODEL_ID
from ._schema_validation import JsonObject


_VERSIONED_PROMPT_RE = re.compile(r"^(?P<template_id>.+)@(?P<version>v[0-9]+)\.txt$")


class _PromptTemplateRequest:
    def __init__(self, prompt_template_id: str) -> None:
        self.prompt_template_id = prompt_template_id
        self.prompt = ""


def build_agent_metadata(
    agent_config: AgentConfig,
    *,
    adapter_id: str = FAKE_ADAPTER_ID,
    adapter_version: str = FAKE_ADAPTER_VERSION,
    model_id: str = FAKE_MODEL_ID,
) -> JsonObject:
    if not isinstance(agent_config, AgentConfig):
        raise TypeError("build_agent_metadata requires a validated AgentConfig.")
    return {
        "adapter_id": str(adapter_id),
        "adapter_version": str(adapter_version),
        "model_id": str(model_id),
        "config_hash": stable_agent_config_hash(agent_config),
        "prompt_template_versions": prompt_template_versions(),
    }


def prompt_template_versions() -> list[JsonObject]:
    prompt_dir = resources.files("resume_agent").joinpath("prompts")
    versions: list[JsonObject] = []
    for prompt_file in sorted(prompt_dir.iterdir(), key=lambda item: item.name):
        match = _VERSIONED_PROMPT_RE.match(prompt_file.name)
        if match is None:
            continue
        prompt_template_id = prompt_file.name.removesuffix(".txt")
        versions.append(
            {
                "prompt_template_id": prompt_template_id,
                "template_id": match.group("template_id"),
                "version": match.group("version"),
                "path": f"prompts/{prompt_file.name}",
                "sha256": hash_prompt_template(_PromptTemplateRequest(prompt_template_id)),
            }
        )
    return versions


__all__ = ["build_agent_metadata", "prompt_template_versions"]
