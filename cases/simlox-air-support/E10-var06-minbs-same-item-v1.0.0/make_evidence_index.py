"""Seal paired E10.var06 source and two guarded native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "minbs1": ("e10-var06-minbs1-v100-ssh-20261003-01", "76b5e93a5c827c988106ef5f3020f110b2686ec6372e3acc2e7c1cfcc6c81de1"),
    "minbs2": ("e10-var06-minbs2-v100-ssh-20261003-01", "7f46c364aa4556b2bce8fe008df8fe7b38aeecd7736d72fa31ff8a6bdbcc7c00"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    support = HERE.parent / contract["accepted_support"]["package"]
    support_run = support / "runs" / contract["accepted_support"]["run_id"]
    assert sha(parent / "native-input-ondem.json") == contract["accepted_parent"]["input_sha256"]
    assert sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"]
    assert sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"]
    assert sha(support / "native-input.json") == contract["accepted_support"]["input_sha256"]
    assert sha(support_run / "closure.json") == contract["accepted_support"]["native_closure_sha256"]
    assert sha(support / "cli-scope-signoff-2026-09-29.md") == contract["accepted_support"]["signoff_sha256"]
    accepted = []
    for arm, (run_id, expected) in RUNS.items():
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert sha(run / "closure.json") == expected and closure["error"] is None
        assert closure["arm"] == arm and closure["run_id"] == run_id and closure["invocation_sha256"] == sha(run / "invocation.json")
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        accepted.append({"arm": arm, "run_id": run_id, "local_path": str(run.resolve()), "closure_sha256": expected, "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    verdict = json.loads((HERE / "review/independent-verdict.json").read_text(encoding="utf-8-sig"))
    assert verdict["passed"] is True and not verdict["failures"] and verdict["checks_passed"] == verdict["checks_total"]
    result = {
        "schema": "simlox-e10-var06-minbs-same-item-v100-evidence-index/v1",
        "case_id": "E10", "variant_id": "E10.var06", "version": "1.0.0",
        "publication_state": "not_published", "source": source, "accepted_runs": accepted,
        "accepted_raw_count": sum(len(r["raw"]) for r in accepted),
        "parent_input_sha256": contract["accepted_parent"]["input_sha256"],
        "parent_closure_sha256": contract["accepted_parent"]["native_closure_sha256"],
        "parent_evidence_index_sha256": contract["accepted_parent"]["evidence_index_sha256"],
        "support_input_sha256": contract["accepted_support"]["input_sha256"],
        "support_closure_sha256": contract["accepted_support"]["native_closure_sha256"],
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": result["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
