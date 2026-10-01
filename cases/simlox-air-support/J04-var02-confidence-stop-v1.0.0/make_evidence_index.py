"""Bind J04.var02 accepted runs and four excluded source-sealed probes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402

ACCEPTED = (
    "j04-var02-confidence-stop-accepted-20261001-01",
    "j04-var02-confidence-stop-accepted-20261001-02",
)
PROBES = (
    ("", "j04-var02-confidence-stop-probe-20261001-01", 32, "excluded_cap_diagnostic"),
    ("009", "j04-var02-confidence-stop-009-probe-20261001-01", 32, "excluded_cap_diagnostic"),
    ("030", "j04-var02-confidence-stop-030-probe-20261001-01", 19, "excluded_high_threshold_diagnostic"),
    ("256", "j04-var02-confidence-stop-256-probe-20261001-01", 81, "excluded_stopping_diagnostic"),
)
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
PARENT = ROOT / "J04-var01-fixed-replications-v1.0.0/probe-input.json"
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def run_record(run_id: str, role: str, suffix: str = "", expected_nrep: int = 81) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if closure.get("run_id") != run_id or closure.get("state") != "native_steps_complete" or closure.get("invocation_sha256") != sha(run / "invocation.json"):
        raise ValueError(f"invocation/closure differs: {run_id}")
    sources = {
        "parent-input.json": PARENT,
        "database-dictionary.txt": DICTIONARY,
        "manual.pdf": MANUAL,
    }
    if role == "current_accepted":
        sources.update({name: HERE / name for name in (
            "contract.json", "build_256.py", "probe256-diff.json", "run_native_ssh.ps1",
            "validate.py", "validate_pair.py", "probe256-input.json",
        )})
        if load(run / "validation.json").get("passed") is not True:
            raise ValueError(f"author validation differs: {run_id}")
        manifest = load(run / "run-manifest.json")
        if manifest.get("closure_sha256") != sha(run / "closure.json") or manifest.get("validation_sha256") != sha(run / "validation.json"):
            raise ValueError(f"manifest differs: {run_id}")
    else:
        names = (f"probe{suffix}-contract.json", f"build_{suffix}.py", f"probe{suffix}-diff.json",
                 f"probe{suffix}_native_ssh.ps1", f"probe{suffix}-input.json") if suffix else (
                     "probe-contract.json", "build.py", "probe-diff.json", "probe_native_ssh.ps1", "probe-input.json")
        sources.update({name: HERE / name for name in names})
    if set(closure.get("post_source_sha256", {})) != set(sources):
        raise ValueError(f"source set differs: {run_id}")
    for name, path in sources.items():
        if closure["post_source_sha256"].get(name) != sha(path):
            raise ValueError(f"source seal differs: {run_id}/{name}")
    if set(closure.get("raw", {})) != RAW:
        raise ValueError(f"raw set differs: {run_id}")
    for name, record in closure["raw"].items():
        path = run / name
        if path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    summary = native.table_rows(load(run / "report-raw.json"), "ResultSummary")
    if len(summary) != 1 or summary[0].get("NREP") != expected_nrep:
        raise ValueError(f"native replication count differs: {run_id}")
    record = {
        "run_id": run_id, "role": role, "local_path": str(run.resolve()),
        "input_sha256": sha(run / "input.json"),
        "invocation_sha256": sha(run / "invocation.json"),
        "closure_sha256": sha(run / "closure.json"),
        "report_sha256": sha(run / "report-raw.json"),
        "nrep": summary[0]["NREP"], "rsmtmf": summary[0]["RSMTMF"],
        "raw": closure["raw"],
    }
    if role == "current_accepted":
        record["validation_sha256"] = sha(run / "validation.json")
        record["manifest_sha256"] = sha(run / "run-manifest.json")
    return record


def main() -> None:
    author = load(HERE / "review/author-pair-validation-2026-10-01.json")
    reviewer = load(HERE / "review/independent-readonly-2026-10-01.json")
    if author.get("passed") is not True or [item["run_id"] for item in author.get("runs", [])] != list(ACCEPTED):
        raise ValueError("author pair verdict differs")
    if reviewer.get("verdict") != "GO":
        raise ValueError("independent reviewer GO missing")
    accepted = [run_record(run_id, "current_accepted") for run_id in ACCEPTED]
    probes = [run_record(run_id, role, suffix, nrep) for suffix, run_id, nrep, role in PROBES]
    source_files = sorted(path for path in HERE.rglob("*") if path.is_file()
                          and "runs" not in path.relative_to(HERE).parts
                          and "__pycache__" not in path.relative_to(HERE).parts
                          and path.name != "evidence-index.json")
    evidence = {
        "schema": "simlox-j04-var02-confidence-stop-evidence-index/v1",
        "case_id": "J04", "variant_id": "J04.var02", "version": "1.0.0",
        "scope": "two fresh same-seed NREPS256 TCLEV0.09 accepted runs stopped at NREP81; aggregate report and first-only ENLOG",
        "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in source_files},
        "accepted_runs": accepted,
        "excluded_diagnostics": probes,
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted": len(accepted),
                      "accepted_raw_seals": sum(len(item["raw"]) for item in accepted),
                      "diagnostics": len(probes)}))


if __name__ == "__main__":
    main()
