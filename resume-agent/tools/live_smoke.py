"""Opt-in Anthropic live smoke for the resume-agent adapter.

This script is intentionally excluded from official gates. It runs only when
all three environment gates are present:

- RESUME_AGENT_LIVE_SMOKE=1
- RESUME_AGENT_ALLOW_LIVE=1
- ANTHROPIC_API_KEY
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "resume-agent"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from resume_agent._adapters import AdapterRequest, create_live_model_adapter  # noqa: E402


SMOKE_SCHEMA_ID = "resume-agent.live-smoke.v1"
SMOKE_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "proposal_type", "requires_validation", "fact_proposals"],
    "properties": {
        "schema_version": {"enum": [SMOKE_SCHEMA_ID]},
        "proposal_type": {"enum": ["resume_semantic_extraction"]},
        "requires_validation": {"enum": [True]},
        "fact_proposals": {"type": "array"},
    },
    "additionalProperties": False,
}


def main() -> int:
    if os.environ.get("RESUME_AGENT_LIVE_SMOKE") != "1":
        print("live smoke skipped: set RESUME_AGENT_LIVE_SMOKE=1 to opt in.")
        return 0
    missing = [
        name
        for name in ("RESUME_AGENT_ALLOW_LIVE", "ANTHROPIC_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        print(f"live smoke not run: missing {', '.join(missing)}.", file=sys.stderr)
        return 2

    adapter = create_live_model_adapter(output_schemas={SMOKE_SCHEMA_ID: SMOKE_SCHEMA})
    result = adapter.complete(
        AdapterRequest(
            prompt_template_id="resume-agent.live-smoke.v1",
            prompt=(
                "Extract one source-grounded fact proposal from this resume sentence. "
                f"Use schema_version {SMOKE_SCHEMA_ID}, proposal_type resume_semantic_extraction, "
                "requires_validation true, and fact_proposals as an array."
            ),
            input_payload={"resume_text": "Built React front ends for SaaS products."},
            output_schema_id=SMOKE_SCHEMA_ID,
        )
    )
    if result.status != "ok":
        print(result.to_dict(), file=sys.stderr)
        return 1
    print("live smoke passed: Anthropic adapter returned schema-valid proposal JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
