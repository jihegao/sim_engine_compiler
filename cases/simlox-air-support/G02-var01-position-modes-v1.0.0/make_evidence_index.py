"""Freeze source and raw native seals after independent G02.var01 acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0"
IDS = ("g02-var01-two-position-accepted-20261001-01",
       "g02-var01-two-position-accepted-20261001-02")
PROBE = "g02-var01-two-position-probe-20261001-01"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record(run_id: str, accepted: bool) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    if invocation["run_id"] != closure["run_id"] or closure["run_id"] != run_id:
        raise ValueError(f"run identity differs: {run_id}")
    if closure["invocation_sha256"] != sha(run / "invocation.json") or closure["error"] is not None:
        raise ValueError(f"closure differs: {run_id}")
    if [s["name"] for s in steps] != ["import", "export", "calc", "jsonreport", "check_import_export"]:
        raise ValueError(f"step names differ: {run_id}")
    if any(s["exit_code"] != 0 or s["status"] != "completed" or not s["gui_preserved"] for s in steps):
        raise ValueError(f"native step failed: {run_id}")
    expected_sources = {"input": HERE / "native-input.json", "parent": PARENT / "native-input.json",
                        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
                        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
                        "contract": HERE / "contract.json", "builder": HERE / "build.py",
                        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
                        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
                        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")}
    before = invocation["source_hashes_before"]
    if before != closure["source_hashes_before"] or before != closure["source_hashes_after"]:
        raise ValueError(f"source closure differs: {run_id}")
    if set(before) != set(expected_sources) or any(before[k] != sha(p) for k, p in expected_sources.items()):
        raise ValueError(f"source fingerprint differs: {run_id}")
    if set(closure["raw"]) != RAW:
        raise ValueError(f"raw file set differs: {run_id}")
    for name, seal in closure["raw"].items():
        path = run / name
        if path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    result = {"run_id": run_id, "role": "accepted" if accepted else "excluded_diagnostic",
              "local_path": str(run.resolve()), "invocation_sha256": sha(run / "invocation.json"),
              "closure_sha256": sha(run / "closure.json"),
              "input_sha256": sha(run / "input.json"),
              "report_sha256": sha(run / "report-raw.json"),
              "model_log_sha256": sha(run / "model.log"), "raw": closure["raw"]}
    if accepted:
        validation, manifest = load(run / "validation.json"), load(run / "run-manifest.json")
        if validation["passed"] is not True or validation["run_id"] != run_id:
            raise ValueError(f"accepted validation differs: {run_id}")
        if manifest["run_id"] != run_id or manifest["closure_sha256"] != result["closure_sha256"] \
                or manifest["validation_sha256"] != sha(run / "validation.json") \
                or manifest["validator_sha256"] != sha(HERE / "validate.py"):
            raise ValueError(f"accepted manifest differs: {run_id}")
        result["validation_sha256"] = sha(run / "validation.json")
        result["manifest_sha256"] = sha(run / "run-manifest.json")
    elif (run / "validation.json").exists() or (run / "run-manifest.json").exists():
        raise ValueError("diagnostic unexpectedly accepted")
    return result


def main() -> None:
    author = load(HERE / "review/author-pair-validation-2026-10-01.json")
    reviewer = load(HERE / "review/independent-readonly-2026-10-01.json")
    if author.get("passed") is not True or [x["run_id"] for x in author["accepted_runs"]] != list(IDS):
        raise ValueError("author pair differs")
    if reviewer.get("verdict", reviewer.get("decision")) not in ("GO", "GO_BOUNDED_POSITION_MODES"):
        raise ValueError("independent bounded GO missing")
    accepted = [record(run_id, True) for run_id in IDS]
    probe = record(PROBE, False)
    if len({x["report_sha256"] for x in accepted}) != 1 or len({x["model_log_sha256"] for x in accepted}) != 1:
        raise ValueError("accepted native output differs")
    parent_review = load(PARENT / "review/independent-position-2026-09-30.json")
    if parent_review.get("passed") is not True:
        raise ValueError("accepted D06 parent review missing")
    source_files = sorted(path for path in HERE.rglob("*") if path.is_file()
                          and "runs" not in path.relative_to(HERE).parts
                          and "__pycache__" not in path.relative_to(HERE).parts
                          and path.name != "evidence-index.json")
    evidence = {"schema": "simlox-g02-var01-position-modes-evidence-index/v1",
                "case_id": "G02", "variant_id": "G02.var01", "version": "1.0.0",
                "scope": "two fixed-seed position-specific failure modes on the same LRU with matched direct CM",
                "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in source_files},
                "accepted_runs": accepted, "excluded_diagnostic": probe,
                "parent": {"case_id": "D06", "accepted_run_id": parent_review["run_id"],
                           "input_sha256": sha(PARENT / "native-input.json"),
                           "independent_review_sha256": sha(PARENT / "review/independent-position-2026-09-30.json")}}
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted": len(accepted),
                      "accepted_raw_seals": sum(len(x["raw"]) for x in accepted), "excluded": 1}))


if __name__ == "__main__":
    main()
