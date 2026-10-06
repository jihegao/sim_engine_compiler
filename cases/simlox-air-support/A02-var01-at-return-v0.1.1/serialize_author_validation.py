"""Serialize the frozen v0.1.1 read-only validator result without changing it."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "validate_native_cli.py"
CHECKER_SHA = "c7c18335011206d253c90f0b6efe842c6102cc7aedf8817f527953d83e6085b9"


def jsonable(value):
    if isinstance(value, set):
        return sorted(jsonable(item) for item in value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    actual_sha = hashlib.sha256(CHECKER.read_bytes()).hexdigest()
    if actual_sha != CHECKER_SHA:
        raise ValueError(f"frozen checker SHA changed: {actual_sha}")
    spec = importlib.util.spec_from_file_location("frozen_a02_validator", CHECKER)
    if spec is None or spec.loader is None:
        raise RuntimeError("frozen checker cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = jsonable(module.run_checks(args.run))
    result["serializer"] = {
        "file": Path(__file__).name,
        "frozen_validator_sha256": CHECKER_SHA,
        "change": "convert sets to sorted JSON arrays only",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks_count": result["checks_count"],
                      "failed": result["failed"], "output": str(args.output)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
