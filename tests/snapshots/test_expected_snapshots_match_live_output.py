from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any

from tests.support.snapshot_compare import compare
from tools.regenerate_expected_snapshots import _install_import_paths, generate_snapshots


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DIR = ROOT / "fixtures" / "expected"


def _load_expected_envelopes() -> list[tuple[str, Path, dict[str, Any]]]:
    envelopes: list[tuple[str, Path, dict[str, Any]]] = []
    for path in sorted(EXPECTED_DIR.glob("*.json")):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        fixture_id = envelope.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            raise AssertionError(f"{path} must define a non-empty fixture_id")
        envelopes.append((fixture_id, path, envelope))
    return envelopes


class ExpectedSnapshotsMatchLiveOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _install_import_paths(ROOT)
        cls.live_snapshots = generate_snapshots(ROOT)


def _add_snapshot_test(fixture_id: str, path: Path, envelope: dict[str, Any]) -> None:
    def test_snapshot(self: ExpectedSnapshotsMatchLiveOutputTest) -> None:
        expected_data = envelope.get("data")
        if expected_data is None:
            self.skipTest(f"{fixture_id} has data:null; no reviewed data block to compare")

        if fixture_id not in self.live_snapshots:
            self.fail(f"{fixture_id} live snapshot missing at /")

        result = compare(expected_data, self.live_snapshots[fixture_id])
        if result:
            return

        first = result.differences[0]
        self.fail(
            f"{fixture_id} differs at {first.pointer}: {first.message}\n"
            f"expected: {first.expected!r}\n"
            f"live: {first.live!r}\n"
            f"snapshot: {path}"
        )

    safe_name = re.sub(r"[^0-9a-zA-Z_]+", "_", fixture_id).strip("_")
    setattr(
        ExpectedSnapshotsMatchLiveOutputTest,
        f"test_{safe_name}_matches_live_output",
        test_snapshot,
    )


for _fixture_id, _path, _envelope in _load_expected_envelopes():
    _add_snapshot_test(_fixture_id, _path, _envelope)

