#!/usr/bin/env python3
"""Export one canonical spare_mvp simulation_inputs fixture through its public adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spare-mvp-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    root = args.spare_mvp_root.resolve()
    sys.path.insert(0, str(root))
    from jsonschema import Draft202012Validator
    from src.spare_mvp_backend.project_payload import ProjectJsonExporter
    from src.spare_mvp_backend.repository import ContractRepository
    from src.spare_mvp_contract.adapter import SimulationAdapter

    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        raw = ContractRepository(connection).get_project(args.project_id)
    project = ProjectJsonExporter().export(raw)
    inputs = SimulationAdapter(root).compile_scenario(project)["simulation_inputs"]
    schema_path = root / "contracts" / "aircraft_support_v1_input.schema.json"
    schema = json.loads(schema_path.read_text())
    Draft202012Validator(schema).validate(inputs)

    # This is the exact runtime control used by the headless 43-day oracle.
    # It is added after schema validation in the upstream benchmark as well.
    inputs["disable_visualization_frames"] = True
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_path = output_dir / "simulation-inputs.json"
    inputs_path.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n")
    manifest = {
        "fixture_version": "spare-mvp-canonical-fixture/v1",
        "project_id": args.project_id,
        "project_sha256": digest(project),
        "inputs_sha256": digest(inputs),
        "spare_mvp_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "schema_path": "contracts/aircraft_support_v1_input.schema.json",
        "schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
        "adapter": "src.spare_mvp_contract.adapter.SimulationAdapter.compile_scenario",
        "exporter": "src.spare_mvp_backend.project_payload.ProjectJsonExporter.export",
        "runtime_overrides": {"disable_visualization_frames": True},
        "source_database_recorded_separately": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
