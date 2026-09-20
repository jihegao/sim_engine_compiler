#!/usr/bin/env python3
"""Profile the fixed upstream Project JSON -> canonical inputs boundary."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
from pathlib import Path
import pstats
import sqlite3
import statistics
import sys
import time


def _summary(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: statistics.median(row[key] for row in rows)
        for key in rows[0]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spare-mvp-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--profile-limit", type=int, default=50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")

    root = args.spare_mvp_root.resolve()
    sys.path.insert(0, str(root))
    from jsonschema import Draft202012Validator
    from src.spare_mvp_backend.project_payload import ProjectJsonExporter
    from src.spare_mvp_backend.repository import ContractRepository
    from src.spare_mvp_contract.adapter import SimulationAdapter

    database = args.database.resolve()
    load_started = time.perf_counter()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        raw = ContractRepository(connection).get_project(args.project_id)
    database_seconds = time.perf_counter() - load_started
    schema = json.loads(
        (root / "contracts" / "aircraft_support_v1_input.schema.json").read_text()
    )

    rows: list[dict[str, float]] = []
    for _repeat in range(args.repeats):
        started = time.perf_counter()
        project = ProjectJsonExporter().export(raw)
        exported = time.perf_counter()
        inputs = SimulationAdapter(root).compile_scenario(project)["simulation_inputs"]
        adapted = time.perf_counter()
        Draft202012Validator(schema).validate(inputs)
        validated = time.perf_counter()
        canonical = json.dumps(
            inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        hashlib.sha256(canonical).hexdigest()
        fingerprinted = time.perf_counter()
        rows.append(
            {
                "project_export": exported - started,
                "adapter_compile": adapted - exported,
                "canonical_schema_validation": validated - adapted,
                "canonical_fingerprint": fingerprinted - validated,
                "project_to_validated_canonical": fingerprinted - started,
            }
        )

    profiles: dict[str, str] = {}
    for name, operation in (
        ("project_export", lambda: ProjectJsonExporter().export(raw)),
        ("adapter_compile", lambda: SimulationAdapter(root).compile_scenario(project)),
    ):
        profiler = cProfile.Profile()
        profiler.enable()
        operation()
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
            "cumtime"
        ).print_stats(args.profile_limit)
        profiles[name] = stream.getvalue()

    report = {
        "status": "passed",
        "scope": "read-only fixed Project export, adapter compile, canonical validation and fingerprint; excludes process imports",
        "spare_mvp_root": str(root),
        "database": str(database),
        "project_id": args.project_id,
        "database_load_seconds": database_seconds,
        "repeats": args.repeats,
        "rows": rows,
        "median_seconds": _summary(rows),
        "sizes_bytes": {
            "raw_project": len(json.dumps(raw, ensure_ascii=False).encode()),
            "clean_project": len(json.dumps(project, ensure_ascii=False).encode()),
            "canonical_inputs": len(json.dumps(inputs, ensure_ascii=False).encode()),
        },
        "profiles": profiles,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
