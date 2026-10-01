"""Freeze two independently accepted J04.var03 NREPS-cap runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402

RUNS = ("j04-var03-nreps-cap-accepted-20261001-01", "j04-var03-nreps-cap-accepted-20261001-02")
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
PARENT = ROOT / "J04-var02-confidence-stop-v1.0.0/probe256-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def record(run_id: str) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if closure.get("run_id") != run_id or closure.get("state") != "native_steps_complete" or closure.get("invocation_sha256") != sha(run / "invocation.json"):
        raise ValueError(f"invocation/closure differs: {run_id}")
    sources = {name: HERE / name for name in (
        "contract.json", "build.py", "probe-diff.json", "probe-input.json",
        "run_native_ssh.ps1", "validate.py", "validate_pair.py",
    )}
    sources.update({"parent-input.json": PARENT, "database-dictionary.txt": DICTIONARY, "manual.pdf": MANUAL})
    if set(closure.get("post_source_sha256", {})) != set(sources):
        raise ValueError(f"source set differs: {run_id}")
    for name, path in sources.items():
        if closure["post_source_sha256"].get(name) != sha(path):
            raise ValueError(f"source seal differs: {run_id}/{name}")
    if set(closure.get("raw", {})) != RAW:
        raise ValueError(f"raw set differs: {run_id}")
    for name, entry in closure["raw"].items():
        path = run / name
        if path.stat().st_size != entry.get("bytes") or sha(path) != entry.get("sha256"):
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    if load(run / "validation.json").get("passed") is not True:
        raise ValueError(f"author validation differs: {run_id}")
    manifest = load(run / "run-manifest.json")
    if manifest.get("closure_sha256") != sha(run / "closure.json") or manifest.get("validation_sha256") != sha(run / "validation.json"):
        raise ValueError(f"manifest differs: {run_id}")
    summary = native.table_rows(load(run / "report-raw.json"), "ResultSummary")
    if len(summary) != 1 or summary[0].get("NREP") != 32 or summary[0].get("RSMTMF", 0) <= 0.09:
        raise ValueError(f"cap/target differs: {run_id}")
    return {
        "run_id": run_id, "role": "current_accepted", "local_path": str(run.resolve()),
        "input_sha256": sha(run / "input.json"),
        "invocation_sha256": sha(run / "invocation.json"),
        "closure_sha256": sha(run / "closure.json"),
        "validation_sha256": sha(run / "validation.json"),
        "manifest_sha256": sha(run / "run-manifest.json"),
        "report_sha256": sha(run / "report-raw.json"),
        "nrep": summary[0]["NREP"], "rsmtmf": summary[0]["RSMTMF"],
        "raw": closure["raw"],
    }


def main() -> None:
    author = load(HERE / "review/author-pair-validation-2026-10-01.json")
    reviewer = load(HERE / "review/independent-readonly-2026-10-01.json")
    if author.get("passed") is not True or [item["run_id"] for item in author.get("runs", [])] != list(RUNS):
        raise ValueError("author pair verdict differs")
    if reviewer.get("verdict") != "GO":
        raise ValueError("independent reviewer GO missing")
    records = [record(run_id) for run_id in RUNS]
    source_files = sorted(path for path in HERE.rglob("*") if path.is_file()
                          and "runs" not in path.relative_to(HERE).parts
                          and "__pycache__" not in path.relative_to(HERE).parts
                          and path.name != "evidence-index.json")
    evidence = {
        "schema": "simlox-j04-var03-nreps-cap-evidence-index/v1",
        "case_id": "J04", "variant_id": "J04.var03", "version": "1.0.0",
        "scope": "two fresh same-seed NREPS32 TCLEV0.09 accepted runs reached cap with final RSMTMF above threshold",
        "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in source_files},
        "accepted_runs": records,
        "related_excluded_probe": {
            "package": "J04-var02-confidence-stop-v1.0.0",
            "run_id": "j04-var02-confidence-stop-009-probe-20261001-01",
            "classification": "diagnostic_only_not_var03_acceptance",
        },
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted": len(records),
                      "accepted_raw_seals": sum(len(item["raw"]) for item in records)}))


if __name__ == "__main__":
    main()
