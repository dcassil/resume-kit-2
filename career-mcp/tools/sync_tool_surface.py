#!/usr/bin/env python3
"""Copy the canonical package tool surface to generated artifacts."""

from __future__ import annotations

from pathlib import Path


PACKAGE_SURFACE = Path(__file__).resolve().parents[1] / "career_mcp" / "tool_surface.json"
SOURCE_ROOT_SURFACE = Path(__file__).resolve().parents[1] / "tool_surface.json"


def main() -> int:
    payload = PACKAGE_SURFACE.read_bytes()
    target = SOURCE_ROOT_SURFACE
    if not target.exists() or target.read_bytes() != payload:
        target.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
