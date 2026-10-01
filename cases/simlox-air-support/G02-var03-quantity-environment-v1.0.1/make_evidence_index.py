"""Freeze source and all 36 native raw closures after independent acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G02-var01-position-modes-v1.0.0" / "native-input.json"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record(seed: int, variant: str) -> dict:
    run_id = f"g02-var03-seed{seed:02d}-{variant}-20261002-01"
    run = HERE / "runs" / run_id
    invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    if invocation["run_id"] != closure["run_id"] or closure["run_id"] != run_id:
        raise ValueError(f"run identity differs: {run_id}")
    if invocation["seed"] != seed or invocation["variant"] != variant:
        raise ValueError(f"panel arm differs: {run_id}")
    if closure["invocation_sha256"] != sha(run / "invocation.json") or closure["error"] is not None:
        raise ValueError(f"closure differs: {run_id}")
    if [s["name"] for s in steps] != ["import", "export", "calc", "jsonreport", "check_import_export"]:
        raise ValueError(f"step names differ: {run_id}")
    if any(s["exit_code"] != 0 or s["status"] != "completed" or not s["gui_preserved"] for s in steps):
        raise ValueError(f"native step failed: {run_id}")
    expected_sources = {
        "input": run / "input.json",
        "parent": PARENT,
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json",
        "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py",
        "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
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
    roundtrip = load(run / "roundtrip-validation.json")
    if not roundtrip["passed"] or len(roundtrip["populated_tables"]) != 18:
        raise ValueError(f"roundtrip differs: {run_id}")
    return {"run_id": run_id, "role": "accepted", "seed": seed, "variant": variant,
            "local_path": str(run.resolve()), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "input_sha256": sha(run / "input.json"),
            "report_sha256": sha(run / "report-raw.json"), "model_log_sha256": sha(run / "model.log"),
            "raw": closure["raw"]}


def main() -> None:
    author = load(HERE / "review/author-panel-validation-2026-10-02.json")
    if not author["all_36_native_runs_valid"] or not author["predeclared_direction_accepted"]:
        raise ValueError("author panel acceptance absent")
    independent_files = sorted((HERE / "review").glob("independent*.json"))
    if len(independent_files) != 1:
        raise ValueError("one independent review report required")
    independent = load(independent_files[0])
    verdict = independent.get("verdict", independent.get("decision"))
    if verdict not in ("GO", "GO_BOUNDED", "GO_BOUNDED_FREQUENCY", "GO_BOUNDED_SEED_PANEL"):
        raise ValueError(f"independent bounded GO missing: {verdict}")
    runs = [record(seed, variant) for seed in range(2, 14)
            for variant in ("baseline", "qty-two", "env-two")]
    if len(runs) != 36 or len({r["run_id"] for r in runs}) != 36:
        raise ValueError("panel run count differs")
    source_files = sorted(p for p in HERE.rglob("*") if p.is_file()
                          and "runs" not in p.relative_to(HERE).parts
                          and "__pycache__" not in p.relative_to(HERE).parts
                          and p.name != "evidence-index.json")
    result = {
        "schema": "simlox-g02-var03-seed-panel-evidence-index/v1",
        "case_id": "G02", "variant_id": "G02.var03", "version": "1.0.1",
        "scope": "twelve seed-matched 256-replication native panels for separate QTYPM and ENVF contrasts",
        "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in source_files},
        "accepted_runs": runs,
        "parent_input_sha256": sha(PARENT),
        "author_validation_sha256": sha(HERE / "review/author-panel-validation-2026-10-02.json"),
        "independent_review_sha256": sha(independent_files[0]),
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_runs": len(runs),
                      "accepted_raw_seals": sum(len(r["raw"]) for r in runs)}))


if __name__ == "__main__":
    main()
