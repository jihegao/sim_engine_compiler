"""Freeze reviewed E06 source hashes and two sealed native run identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {variant: f"e06-{variant}-v100-ssh-20261002-01" for variant in ("local", "upstream")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_record(variant: str, run_id: str) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    assert invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    expected = {
        "input": HERE / f"{variant}-input.json",
        "parent": ROOT / "E05-local-repair-reissue-v1.0.0/native-input.json",
        "support": ROOT / "E04-upstream-transport-fast-v1.0.0/native-input.json",
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    assert set(closure["source_hashes_before"]) == set(expected)
    assert all(closure["source_hashes_before"][key] == sha(path) for key, path in expected.items())
    assert [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps)
    assert closure["error"] is None and load(run / "roundtrip-validation.json")["passed"]
    assert len(closure["raw"]) == 12
    assert all((run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    return {"run_id": run_id, "variant": variant, "role": "accepted_fixed_seed_boundary_arm",
            "local_path": str(run.resolve()), "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "run_log_sha256": sha(run / "run.log"),
            "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "raw": closure["raw"]}


def main() -> None:
    author = load(HERE / "author-validation.json")
    assert author["passed"] is True and author["runs"] == RUNS
    reports = sorted((HERE / "review").glob("independent*.json"))
    assert len(reports) == 1, "one independent review JSON required"
    independent = load(reports[0])
    verdict = independent.get("verdict", independent.get("decision", ""))
    passed = independent.get("passed") is True or (independent.get("checks_passed") == independent.get("checks_total")
                                                    and independent.get("checks_total", 0) > 0
                                                    and not independent.get("failures"))
    assert passed and str(verdict).upper().startswith("GO"), "independent bounded GO required"
    accepted = [run_record(variant, run_id) for variant, run_id in RUNS.items()]
    files = sorted(path for path in HERE.rglob("*") if path.is_file()
                   and "runs" not in path.relative_to(HERE).parts
                   and "__pycache__" not in path.relative_to(HERE).parts
                   and path.name != "evidence-index.json")
    index = {"schema": "simlox-e06-var01-repair-routing-evidence-index/v1",
             "case_id": "E06", "variant_id": "E06.var01", "version": "1.0.0",
             "scope": "two-level cumulative direct-repair fractions 1/1 versus 0/1",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in files},
             "accepted_runs": accepted,
             "parent_input_sha256": sha(ROOT / "E05-local-repair-reissue-v1.0.0/native-input.json"),
             "support_input_sha256": sha(ROOT / "E04-upstream-transport-fast-v1.0.0/native-input.json"),
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(reports[0])}
    raw = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_runs": len(accepted),
                      "accepted_raw_seals": sum(len(record["raw"]) for record in accepted)}))


if __name__ == "__main__":
    main()
