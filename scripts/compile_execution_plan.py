#!/usr/bin/env python3
"""Compile canonical simulation_inputs JSON into a serialized Execution Plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim_engine_compiler.compiler import compile_aircraft_support


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--semantic-profile",
        choices=("legacy-minute-v1", "event-time-v2"),
        default="legacy-minute-v1",
    )
    args = parser.parse_args()
    plan = compile_aircraft_support(
        json.loads(args.input.read_text()), semantic_profile=args.semantic_profile
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "plan_fingerprint": plan.fingerprint,
                "source_inputs_sha256": plan.source_inputs_sha256,
                "semantic_profile": plan.semantic_profile,
                "aircraft": len(plan.aircraft),
                "missions": len(plan.missions),
                "activities": len(plan.activities),
                "unsupported_features": plan.unsupported_features,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
