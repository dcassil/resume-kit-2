"""Confirmation policy for the local career MCP adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str | None = None


_TOOL_MUTATION_MAP: dict[str, bool] | None = None


def evaluate_policy(tool: str, arguments: JsonObject, confirmed: bool) -> PolicyDecision:
    """Evaluate v1 local policy for a tool call.

    RKIT-A-0002 item 2 intentionally keeps v1 single-user and local. There are
    no principal, role, or authorization-scope checks here; policy is limited to
    the manifest-declared read/mutate capability and host confirmation.
    """
    del arguments
    tool_mutates = _tool_mutation_map()
    if tool not in tool_mutates:
        return PolicyDecision(allowed=False, requires_confirmation=False, reason="unknown_tool")
    if not tool_mutates[tool]:
        return PolicyDecision(allowed=True, requires_confirmation=False)
    if not confirmed:
        return PolicyDecision(allowed=False, requires_confirmation=True, reason="confirmation_required")
    return PolicyDecision(allowed=True, requires_confirmation=True)


def tool_mutates(tool: str) -> bool:
    return bool(_tool_mutation_map().get(tool, False))


def _tool_mutation_map() -> dict[str, bool]:
    global _TOOL_MUTATION_MAP
    if _TOOL_MUTATION_MAP is None:
        surface_path = Path(__file__).with_name("tool_surface.json")
        surface = json.loads(surface_path.read_text(encoding="utf-8"))
        _TOOL_MUTATION_MAP = {
            str(tool["name"]): bool(tool.get("mutates"))
            for tool in surface.get("tools", [])
            if isinstance(tool, dict) and isinstance(tool.get("name"), str)
        }
    return dict(_TOOL_MUTATION_MAP)


__all__ = ["PolicyDecision", "evaluate_policy", "tool_mutates"]
