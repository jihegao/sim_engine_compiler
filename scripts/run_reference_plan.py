#!/usr/bin/env python3
"""Execute a serialized plan with the independent SimPy reference runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    plan = ExecutionPlan.from_dict(json.loads(args.plan.read_text()))
    result = SimpyReferenceRuntime(plan, seed=args.seed).run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "plan_fingerprint": result["plan_fingerprint"],
                "time": result["time"],
                "stop_reason": result["stop_reason"],
                "events": len(result["trace"]),
            }
        )
    )


if __name__ == "__main__":
    main()
