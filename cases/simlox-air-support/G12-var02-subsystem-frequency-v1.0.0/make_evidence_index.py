"""Seal G12.var02 source, accepted native panel, and independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, SEEDS, VARIANTS

PARENT_CLOSURE = (HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "runs" /
                  "g12-var01-two-subsystems-v100-ssh-20261003-02" / "closure.json")
RAW = {"export.log", "import.log", "input.json", "model.log", "model.sxi", "model.sxo",
       "model_Prelife.log", "report-export.log", "report-raw.json", "roundtrip-raw.json",
       "roundtrip-validation.json", "run.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record(seed: int, arm: str, contract: dict, manifest: dict) -> dict:
    run_id = f"g12-var02-seed{seed:02d}-{arm}-20261003-01"
    run = HERE / "runs" / run_id
    inv, closure, steps, rt = (read(run / name) for name in
                               ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
    if (inv["run_id"], closure["run_id"], inv["seed"], closure["seed"], inv["arm"], closure["arm"]) != (
            run_id, run_id, seed, seed, arm, arm):
        raise ValueError(f"run identity differs: {run_id}")
    if (inv["session_id"], inv["execution_mode"], inv["gui"]["pid"], inv["queue_mutex"]) != (
            0, "session0_ssh_cli", 13340, "Global\\SimloxIssue18NativeQueue"):
        raise ValueError(f"SSH/GUI guard differs: {run_id}")
    if (inv["prelife_log_option_before"], closure["prelife_log_option_after"]) != ("NO", "NO"):
        raise ValueError(f"registry differs: {run_id}")
    if closure["invocation_sha256"] != sha(run / "invocation.json") or closure["error"] is not None:
        raise ValueError(f"invocation/closure differs: {run_id}")
    if [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps] != [
            (name, "completed", 0, True) for name in
            ("import", "export", "calc", "jsonreport", "check_import_export")]:
        raise ValueError(f"native steps differ: {run_id}")
    if not rt["passed"] or len(rt["populated_tables"]) != 22:
        raise ValueError(f"roundtrip differs: {run_id}")
    if (closure["native_outcome"], closure["conversion"]["errors"], closure["conversion"]["notes"],
        closure["conversion"]["warning_codes"], closure["report_present"]) != (
            "zero_error_reviewed_warnings", 0, 0, ["108", "2053", "2053"], True):
        raise ValueError(f"native outcome differs: {run_id}")
    before = closure["source_hashes_before"]
    if before != closure["source_hashes_after"] or before != inv["source_hashes_before"]:
        raise ValueError(f"source closure differs: {run_id}")
    sources = {"input": run / "input.json", "manifest": HERE / "input-manifest.json",
               "parent": PARENT, "parent_closure": PARENT_CLOSURE,
               "contract": HERE / "contract.json", "builder": HERE / "build.py",
               "manifest_builder": HERE / "make_input_manifest.py",
               "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1",
               "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
               "exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
               "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
               "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt")}
    if set(before) != set(sources) or any(before[key] != sha(path) for key, path in sources.items()):
        raise ValueError(f"source fingerprint differs: {run_id}")
    if before["input"] != manifest["entries"][str(seed)][arm]["sha256"]:
        raise ValueError(f"manifest input differs: {run_id}")
    if (before["parent"], before["parent_closure"], before["manifest"], before["exe"],
        before["manual"], before["dictionary"]) != (
            contract["accepted_parent"]["input_sha256"], contract["accepted_parent"]["native_closure_sha256"],
            contract["input_manifest_sha256"], contract["source"]["exe_sha256"],
            contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]):
        raise ValueError(f"contract source pins differ: {run_id}")
    if set(closure["raw"]) != RAW:
        raise ValueError(f"raw set differs: {run_id}")
    for name, seal in closure["raw"].items():
        path = run / name
        if (path.stat().st_size, sha(path)) != (seal["bytes"], seal["sha256"]):
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    return {"run_id": run_id, "seed": seed, "arm": arm, "role": "accepted",
            "local_path": str(run.resolve()), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "input_sha256": sha(run / "input.json"),
            "report_sha256": sha(run / "report-raw.json"), "event_log_sha256": sha(run / "model.log"),
            "raw": closure["raw"]}


def main() -> None:
    contract, manifest = read(HERE / "contract.json"), read(HERE / "input-manifest.json")
    author, independent = (read(HERE / name) for name in
                           ("author-validation.json", "review/independent-validation-2026-10-03.json"))
    if not author["passed"] or author["failed_count"] or not independent["passed"] or independent["failures"]:
        raise ValueError("author and independent GO required")
    if independent["run_count"] != 36 or independent["raw_seal_count"] != 468:
        raise ValueError("independent panel coverage differs")
    runs = [record(seed, arm, contract, manifest) for seed in SEEDS for arm in VARIANTS]
    if len(runs) != 36 or len({r["run_id"] for r in runs}) != 36:
        raise ValueError("accepted panel count differs")
    source_files = sorted(p for p in HERE.rglob("*") if p.is_file()
                          and "runs" not in p.relative_to(HERE).parts
                          and "__pycache__" not in p.relative_to(HERE).parts
                          and p.name != "evidence-index.json")
    index = {"schema": "simlox-g12-var02-subsystem-frequency-evidence-index/v1",
             "case_id": "G12", "variant_id": "G12.var02", "version": "1.0.0",
             "scope": "12 matched seeds, 3 arms each, 256 native replications per arm",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in source_files},
             "accepted_parent": contract["accepted_parent"], "accepted_runs": runs,
             "raw_file_count": sum(len(r["raw"]) for r in runs),
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_validation_sha256": sha(HERE / "review/independent-validation-2026-10-03.json")}
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists():
        if output.read_bytes() != data:
            raise ValueError("frozen evidence index differs")
    else:
        output.write_bytes(data)
    print(json.dumps({"index_sha256": sha(output), "accepted_runs": len(runs),
                      "accepted_raw_seals": index["raw_file_count"],
                      "source_file_count": len(source_files)}))


if __name__ == "__main__":
    main()
