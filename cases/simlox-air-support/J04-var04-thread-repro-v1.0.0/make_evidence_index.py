"""Bind current two-thread acceptance and excluded J04.var04 native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402

ACCEPTED = ("j04-var04-thread2-accepted-20261001-02", "j04-var04-thread2-accepted-20261001-03")
SUPERSEDED = "j04-var04-thread2-accepted-20261001-01"
PROBE = "j04-var04-thread2-probe-20261001-01"
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}
PARENT = ROOT / "J04-var03-nreps-cap-v1.0.0/probe-input.json"
PARENT_RUNS = ROOT / "J04-var03-nreps-cap-v1.0.0/runs"
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def record(run_id: str, role: str) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if closure.get("run_id") != run_id or closure.get("state") != "native_steps_complete" or closure.get("invocation_sha256") != sha(run / "invocation.json"):
        raise ValueError(f"invocation/closure differs: {run_id}")
    archive = HERE / "review/superseded-first-acceptance"
    sources = {"probe-input.json": HERE / "probe-input.json", "probe-diff.json": HERE / "probe-diff.json",
               "parent-input.json": PARENT, "database-dictionary.txt": DICTIONARY, "manual.pdf": MANUAL}
    if role == "excluded_diagnostic":
        sources.update({"probe-contract.json": HERE / "probe-contract.json",
                        "build.py": archive / "build.py", "probe_native_ssh.ps1": HERE / "probe_native_ssh.ps1"})
        if (run / "validation.json").exists() or (run / "run-manifest.json").exists():
            raise ValueError("probe unexpectedly has acceptance files")
    else:
        base = HERE if role == "current_accepted" else archive
        sources.update({name: base / name for name in (
            "contract.json", "build.py", "run_native_ssh.ps1", "validate.py", "validate_pair.py")})
        if role == "current_accepted":
            if load(run / "validation.json").get("passed") is not True:
                raise ValueError(f"accepted validation differs: {run_id}")
            manifest = load(run / "run-manifest.json")
            if manifest.get("closure_sha256") != sha(run / "closure.json") or manifest.get("validation_sha256") != sha(run / "validation.json"):
                raise ValueError(f"accepted manifest differs: {run_id}")
        elif (run / "validation.json").exists() or (run / "run-manifest.json").exists():
            raise ValueError("superseded validation/manifest unexpectedly exists")
    if set(closure.get("post_source_sha256", {})) != set(sources):
        raise ValueError(f"source set differs: {run_id}")
    for name, path in sources.items():
        if closure["post_source_sha256"].get(name) != sha(path):
            raise ValueError(f"source seal differs: {run_id}/{name}")
    if set(closure.get("raw", {})) != RAW:
        raise ValueError(f"raw file set differs: {run_id}")
    for name, entry in closure["raw"].items():
        path = run / name
        if path.stat().st_size != entry.get("bytes") or sha(path) != entry.get("sha256"):
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    result = {
        "run_id": run_id, "role": role, "local_path": str(run.resolve()),
        "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
        "closure_sha256": sha(run / "closure.json"), "report_sha256": sha(run / "report-raw.json"),
        "first_replication_log_sha256": sha(run / "model.log"), "raw": closure["raw"],
    }
    if role == "current_accepted":
        result["validation_sha256"] = sha(run / "validation.json")
        result["manifest_sha256"] = sha(run / "run-manifest.json")
    else:
        result["exclusion_reason"] = ("diagnostic probe" if role == "excluded_diagnostic"
                                      else "native steps complete, but author validator crashed before validation/manifest")
    return result


def main() -> None:
    author = load(HERE / "review/author-pair-validation-2026-10-01.json")
    reviewer = load(HERE / "review/independent-readonly-2026-10-01.json")
    if author.get("passed") is not True or [item["run_id"] for item in author.get("runs", [])] != list(ACCEPTED):
        raise ValueError("author accepted pair differs")
    if reviewer.get("verdict") != "GO":
        raise ValueError("independent GO missing")
    accepted = [record(run_id, "current_accepted") for run_id in ACCEPTED]
    superseded = record(SUPERSEDED, "superseded_not_published")
    probe = record(PROBE, "excluded_diagnostic")
    parent_ids = load(HERE / "contract.json")["expected_observation"]["parent_thread_one_run_ids"]
    parent = []
    for run_id in parent_ids:
        run = PARENT_RUNS / run_id
        if load(run / "validation.json").get("passed") is not True:
            raise ValueError(f"parent acceptance differs: {run_id}")
        parent.append({"run_id": run_id, "input_sha256": sha(run / "input.json"),
                       "report_sha256": sha(run / "report-raw.json"),
                       "first_replication_log_sha256": sha(run / "model.log")})
    if len({item["report_sha256"] for item in accepted + parent}) != 1 or len({item["first_replication_log_sha256"] for item in accepted + parent}) != 1:
        raise ValueError("cross-thread report/log fingerprints differ")
    source_files = sorted(path for path in HERE.rglob("*") if path.is_file()
                          and "runs" not in path.relative_to(HERE).parts
                          and "__pycache__" not in path.relative_to(HERE).parts
                          and path.name != "evidence-index.json")
    evidence = {
        "schema": "simlox-j04-var04-thread-repro-evidence-index/v1",
        "case_id": "J04", "variant_id": "J04.var04", "version": "1.0.0",
        "scope": "two fresh calc-threads-2 runs match two accepted calc-threads-1 parents by report and first-only ENLOG bytes",
        "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in source_files},
        "accepted_runs": accepted, "parent_thread_one_runs": parent,
        "excluded_diagnostic": probe, "superseded_run": superseded,
    }
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted": len(accepted),
                      "accepted_raw_seals": sum(len(item["raw"]) for item in accepted),
                      "excluded": 2}))


if __name__ == "__main__":
    main()
