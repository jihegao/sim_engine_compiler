"""Index sealed local native and report artifacts without copying raw files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUTPUT = HERE / "evidence-index.json"
NATIVE = {
    "a-hour-b-mission": "a15-two-unit-swap-a-v100-20261001-01",
    "a-mission-b-hour": "a15-two-unit-swap-b-v100-20261001-01",
}
REPORT = {
    "a-hour-b-mission": {selector: f"a15-two-unit-a-{selector}-20261001-01" for selector in ("all", "unit-a", "unit-b")},
    "a-mission-b-hour": {selector: f"a15-two-unit-b-{selector}-20261001-01" for selector in ("all", "unit-a", "unit-b")},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_record(run_id: str, *, native: bool) -> dict:
    path = RUNS / run_id
    closure = read(path / "closure.json")
    invocation = read(path / "invocation.json")
    assert closure["error"] is None
    assert closure["invocation_sha256"] == sha(path / "invocation.json")
    for name, record in closure["raw"].items():
        artifact = path / name
        assert artifact.stat().st_size == record["bytes"] and sha(artifact) == record["sha256"]
    result = {
        "run_id": run_id,
        "invocation_sha256": sha(path / "invocation.json"),
        "closure_sha256": sha(path / "closure.json"),
        "raw": {name: closure["raw"][name] for name in sorted(closure["raw"])},
    }
    if native:
        assert invocation["run_id"] == run_id
        result["input_sha256"] = sha(path / "input.json")
        result["sxo_sha256"] = sha(path / "model.sxo")
    else:
        assert invocation["run_id"] == run_id and closure["exit_code"] == 0
        log = (path / "report-export.log").read_text(encoding="utf-8-sig")
        assert "Report completed" in log and "Reverting to default settings" not in log
        result["source_run_id"] = invocation["source_run_id"]
        result["settings_sha256"] = invocation["source_hashes"]["settings"]
    return result


def main() -> None:
    contract = read(HERE / "contract.json")
    out = {
        "schema": "simlox-a15-two-unit-custom-exposure-evidence-index/v1",
        "case_id": "A15",
        "scope": "two separate unit-owned full fixed missions, one aircraft per unit, with swapped custom KM rate forms",
        "parent_publication_id": contract["parent_publication_id"],
        "parent_input_sha256": contract["parent_input_sha256"],
        "contract_sha256": sha(HERE / "contract.json"),
        "exact_diff_sha256": sha(HERE / "exact-diff.json"),
        "builder_sha256": sha(HERE / "build.py"),
        "native_runner_sha256": sha(HERE / "run_native_ssh.ps1"),
        "report_settings_builder_sha256": sha(HERE / "make_report_settings.py"),
        "report_runner_sha256": sha(HERE / "report_existing_sxo_ssh.ps1"),
        "author_validator_sha256": sha(HERE / "validate_native.py"),
        "author_report_sha256": sha(HERE / "author-validation-2026-10-01.json"),
        "installed_default_settings_sha256": "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d",
        "installed_executable_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
        "local_report_settings_sha256": {selector: sha(RUNS / "report-settings" / f"{selector}.sxs") for selector in ("all", "unit-a", "unit-b")},
        "native_runs": {variant: run_record(run_id, native=True) for variant, run_id in NATIVE.items()},
        "report_runs": {variant: {selector: run_record(run_id, native=False) for selector, run_id in selections.items()} for variant, selections in REPORT.items()},
        "observation": {"per_unit_km_total_accumulated": 120, "all_unit_km_total_accumulated": 240, "mission_hours": [8, 10], "simulation_horizon_hours": 36},
        "raw_location": "ignored runs/ under this package on the 4700-3 host; no native model or raw result uploaded",
        "limits": "unit-owned complete fixed missions only; shared formation, partial mission, failures, PM, other seeds, physical kilometres, GUI and cross-engine parity unverified",
    }
    data = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == data, "evidence index differs"
    else:
        OUTPUT.write_bytes(data)
    print(sha(OUTPUT))


if __name__ == "__main__":
    main()
