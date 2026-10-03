"""Seal E10.var05 candidate source and guarded raw native run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUN_ID = "e10-var05-nested-v100-ssh-20261003-01"
CLOSURE_SHA = "d6daf2d9163fa478112722075b6968435d2007e0f5d3ca59f5ab6da58e895f5e"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    assert sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"]
    assert sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"]
    assert sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"]
    run = HERE / "runs" / RUN_ID
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    assert sha(run / "closure.json") == CLOSURE_SHA and closure["error"] is None
    assert closure["run_id"] == RUN_ID and closure["invocation_sha256"] == sha(run / "invocation.json")
    for name, seal in closure["raw"].items():
        path = run / name
        assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    verdict = json.loads((HERE / "review/independent-verdict.json").read_text(encoding="utf-8-sig"))
    assert verdict["passed"] is True and not verdict["failures"] and verdict["checks_passed"] == verdict["checks_total"]
    result = {
        "schema": "simlox-e10-var05-nested-repeat-v100-evidence-index/v1",
        "case_id": "E10", "variant_id": "E10.var05", "version": "1.0.0",
        "publication_state": "not_published", "source": source,
        "accepted_runs": [{"run_id": RUN_ID, "local_path": str(run.resolve()), "closure_sha256": CLOSURE_SHA, "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]}],
        "accepted_raw_count": len(closure["raw"]),
        "parent_input_sha256": contract["accepted_parent"]["input_sha256"],
        "parent_closure_sha256": contract["accepted_parent"]["native_closure_sha256"],
        "parent_evidence_index_sha256": contract["accepted_parent"]["evidence_index_sha256"],
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": result["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
