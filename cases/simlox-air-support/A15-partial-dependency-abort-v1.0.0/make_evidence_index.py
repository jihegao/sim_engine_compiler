"""Seal native and report-only raw artifacts by ID/hash without uploading them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import VARIANTS

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUTPUT = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_record(run_id: str, *, native: bool) -> dict:
    path = RUNS / run_id
    closure = read(path / "closure.json")
    invocation = read(path / "invocation.json")
    assert closure["error"] is None and closure["invocation_sha256"] == sha(path / "invocation.json")
    assert invocation["run_id"] == run_id
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
        assert all(s["status"] == "completed" and s["exit_code"] == 0 for s in read(path / "steps.json"))
        result["input_sha256"] = sha(path / "input.json")
        result["sxo_sha256"] = sha(path / "model.sxo")
    else:
        assert closure["exit_code"] == 0
        log = (path / "report-export.log").read_text(encoding="utf-8-sig")
        assert "Report completed" in log and "Reverting to default settings" not in log and "could not be loaded" not in log
        result["source_run_id"] = invocation["source_run_id"]
        result["settings_sha256"] = invocation["source_hashes"]["settings"]
    return result


def main() -> None:
    contract = read(HERE / "contract.json")
    out = {
        "schema": "simlox-a15-partial-dependency-abort-evidence-index/v1",
        "case_id": "A15",
        "scope": "one CONTINUOUS EXECUTE mission completed 8-12 versus deterministic dependency abort 8-10; hourly and per-mission custom KM rates",
        "parent_publication_id": contract["direct_parent_publication_id"],
        "parent_input_sha256": {mode: item["sha256"] for mode, item in contract["parents"].items()},
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
        "local_report_settings_sha256": sha(RUNS / "report-settings" / "all.sxs"),
        "native_runs": {v: run_record(f"a15-partial-{v}-v100-20261001-01", native=True) for v in VARIANTS},
        "report_runs": {v: run_record(f"a15-partial-report-{v}-v100-20261001-01", native=False) for v in VARIANTS},
        "observation": {
            "control_km_total_accumulated": 240,
            "dependent_km_total_accumulated": 120,
            "active_hours": {"control": [8, 12], "dependent": [8, 10]},
            "simulation_horizon_hours": 16,
            "rate_forms_equal_within_each_branch": True,
        },
        "raw_location": "ignored runs/ under this package on the 4700-3 host; no raw native output uploaded",
        "limits": "one deterministic CONTINUOUS dependency abort; not a failure-driven or fixed/extendable partial mission, serial-numbered per-aircraft proof, or shared formation aggregation",
    }
    data = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == data, "evidence index differs"
    else:
        OUTPUT.write_bytes(data)
    print(sha(OUTPUT))


if __name__ == "__main__":
    main()
