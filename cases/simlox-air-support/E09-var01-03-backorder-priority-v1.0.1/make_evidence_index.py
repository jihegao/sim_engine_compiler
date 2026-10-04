"""Seal reviewed E09 v1.0.1 source and both local guarded run closures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
OLD = HERE.parent / "E09-var01-03-backorder-priority-v1.0.0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sealed_run(run_id: str) -> dict:
    run = HERE / "runs" / run_id
    closure = load(run / "closure.json")
    assert closure["run_id"] == run_id and closure["error"] is None
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    for name, meta in closure["raw"].items():
        path = run / name
        assert path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
    return {
        "run_id": run_id,
        "local_path": str(run.resolve()),
        "closure_sha256": sha(run / "closure.json"),
        "invocation_sha256": sha(run / "invocation.json"),
        "raw": closure["raw"],
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    contract = load(HERE / "contract.json")
    assert sha(OLD / "runs" / "e09-backorder-priority-v100-ssh-20261004-01" / "closure.json") == contract["excluded_diagnostic_v100_closure_sha256"]
    native = sealed_run(contract["run_id"])
    selected = sealed_run(contract["selected_report_run_id"])
    report_closure = load(HERE / "runs" / contract["selected_report_run_id"] / "closure.json")
    assert report_closure["source_closure_sha256"] == native["closure_sha256"]
    author = load(HERE / "author-report-validation.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    static = load(HERE / "review" / "static-postrun-verdict.json")
    assert author["verdict"] == "GO_BOUNDED" and author["checks"] == author["passed"] and not author["failed"]
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks"] == independent["passed"] and not independent["failed"]
    assert static["verdict"] == "GO_BOUNDED"
    assert author["native_closure_sha256"] == native["closure_sha256"]
    assert author["selected_report_closure_sha256"] == selected["closure_sha256"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    result = {
        "schema": "simlox-e09-backorder-priority-v101-evidence-index/v1",
        "case_id": "E09",
        "variant_ids": contract["variant_ids"],
        "version": "1.0.1",
        "publication_state": "not_published",
        "source": source,
        "accepted_runs": [native, selected],
        "accepted_raw_count": len(native["raw"]) + len(selected["raw"]),
        "excluded_diagnostic_v100_closure_sha256": contract["excluded_diagnostic_v100_closure_sha256"],
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": result["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
