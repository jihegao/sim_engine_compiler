"""Freeze C09.var01 source hashes and accepted native raw seals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {v: f"c09-var01-{v}-20261002-01" for v in ("short", "equal", "long")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_record(variant: str, run_id: str) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure, steps = (load(run / x) for x in ("invocation.json", "closure.json", "steps.json"))
    assert invocation["run_id"] == closure["run_id"] == run_id
    assert invocation["variant"] == variant
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert sha(run / "input.json") == closure["source_hashes_before"]["input"]
    assert all((run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    expected = {
        "input": HERE / f"{variant}-input.json",
        "parent": ROOT / "C09-var04-remote-maintenance-resource-v1.0.0/local-input.json",
        "catalog_parent": ROOT / "C03-shared-crew-formation-v1.0.2/inputs/staffing-2.json",
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    assert set(closure["source_hashes_before"]) == set(expected)
    assert all(closure["source_hashes_before"][key] == sha(path) for key, path in expected.items())
    assert [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps)
    assert closure["error"] is None and load(run / "roundtrip-validation.json")["passed"]
    assert len(closure["raw"]) == 12
    return {"run_id": run_id, "variant": variant, "role": "accepted_fixed_seed_arm",
            "local_path": str(run.resolve()), "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "run_log_sha256": sha(run / "run.log"),
            "report_sha256": sha(run / "report-raw.json"), "raw": closure["raw"]}


def main() -> None:
    author = load(HERE / "author-validation.json")
    assert author["passed"] is True and [r["variant"] for r in author["runs"]] == list(RUNS)
    reports = sorted((HERE / "review").glob("independent*.json"))
    assert len(reports) == 1, "one independent JSON report required"
    independent = load(reports[0])
    verdict = independent.get("verdict", independent.get("decision", ""))
    passed = independent.get("passed") is True or (independent.get("checks_passed") == independent.get("checks_total")
                                                    and independent.get("checks_total", 0) > 0
                                                    and independent.get("failures") == [])
    assert passed and verdict.startswith("GO"), "independent bounded GO required"
    accepted = [run_record(variant, run_id) for variant, run_id in RUNS.items()]
    files = sorted(p for p in HERE.rglob("*") if p.is_file()
                   and "runs" not in p.relative_to(HERE).parts
                   and "__pycache__" not in p.relative_to(HERE).parts
                   and p.name != "evidence-index.json")
    index = {"schema": "simlox-c09-var01-travel-wait-evidence-index/v1",
             "case_id": "C09", "variant_id": "C09.var01", "version": "1.0.0",
             "scope": "three fixed-seed forward-travel versus local-wait arms",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in files},
             "accepted_runs": accepted,
             "parent_input_sha256": sha(ROOT / "C09-var04-remote-maintenance-resource-v1.0.0/local-input.json"),
             "catalog_parent_input_sha256": sha(ROOT / "C03-shared-crew-formation-v1.0.2/inputs/staffing-2.json"),
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(reports[0])}
    raw = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_runs": len(accepted),
                      "accepted_raw_seals": sum(len(r["raw"]) for r in accepted)}))


if __name__ == "__main__":
    main()
