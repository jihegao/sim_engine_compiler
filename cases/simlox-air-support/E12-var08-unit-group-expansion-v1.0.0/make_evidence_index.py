"""Seal E12.var08 source and raw guarded run after independent acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUN_ID = "e12-var08-unit-group-expansion-v100-ssh-20261004-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    assert sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"]
    assert sha(parent / "runs" / contract["accepted_parent"]["run_id"] / "closure.json") == contract["accepted_parent"]["native_closure_sha256"]
    assert sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"]
    run = HERE / "runs" / RUN_ID
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == RUN_ID and closure["error"] is None
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    for name, meta in closure["raw"].items():
        path = run / name
        assert path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
    author = json.loads((HERE / "author-validation-2026-10-04.json").read_text(encoding="utf-8-sig"))
    independent = json.loads((HERE / "review/independent-verdict.json").read_text(encoding="utf-8-sig"))
    assert author["passed"] and independent["passed"] and not author["failures"] and not independent["failures"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    result = {
        "schema": "simlox-e12-var08-unit-group-expansion-v100-evidence-index/v1",
        "case_id": "E12", "variant_id": "E12.var08", "version": "1.0.0", "publication_state": "not_published", "source": source,
        "accepted_runs": [{"run_id": RUN_ID, "local_path": str(run.resolve()), "closure_sha256": sha(run / "closure.json"),
                           "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]}],
        "accepted_raw_count": len(closure["raw"]),
        "parent_input_sha256": contract["accepted_parent"]["input_sha256"],
        "parent_closure_sha256": contract["accepted_parent"]["native_closure_sha256"],
        "parent_evidence_index_sha256": contract["accepted_parent"]["evidence_index_sha256"],
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": len(closure["raw"]), "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
