#!/usr/bin/env python3
"""Freeze an upstream Project JSON through spare_mvp's official Adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spare-mvp-root", type=Path, required=True)
    parser.add_argument("--project-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    root = args.spare_mvp_root.resolve()
    source = args.project_json.resolve()
    output = args.output_dir.resolve()
    sys.path.insert(0, str(root))
    from jsonschema import Draft202012Validator
    from src.spare_mvp_contract.adapter import SimulationAdapter

    project = json.loads(source.read_text())
    compiled = SimulationAdapter(root).compile_scenario(project)
    inputs = compiled["simulation_inputs"]
    schema_path = root / "contracts/aircraft_support_v1_input.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text())).validate(inputs)
    # The established 43-day headless oracle adds this after schema validation.
    inputs["disable_visualization_frames"] = True

    output.mkdir(parents=True, exist_ok=True)
    inputs_path = output / "simulation-inputs.json"
    inputs_path.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n")
    manifest = {
        "source_kind": "committed spare_mvp Project JSON via official SimulationAdapter",
        "source_path": str(source),
        "source_sha256": sha256(source),
        "spare_mvp_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            capture_output=True, check=True,
        ).stdout.strip(),
        "project_id": compiled.get("project_id"),
        "scenario_id": compiled.get("scenario_id"),
        "schema_sha256": sha256(schema_path),
        "canonical_file_sha256": sha256(inputs_path),
        "adapter": "src.spare_mvp_contract.adapter.SimulationAdapter.compile_scenario",
        "runtime_overrides": {"disable_visualization_frames": True},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
