"""Seal D09.var04 sources and three immutable local native run closures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "d09-var04-part-short-v100-ssh-20261002-01": "f78fbca87f943c5068cdb2f6fe1e98e799ca2cf6484996497cc0c45d9c345f32",
    "d09-var04-crew-short-v100-ssh-20261002-01": "2e5d547b85635d9cc2b0117a54e8a09f604ddd919086c826c2becd3bce8fe15e",
    "d09-var04-supplied-v100-ssh-20261002-01": "d1e00d178915fa9c10489c6f1934badee8a53c5dfe3b8b9a713bb7e2ed8596a9",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    accepted = []
    for run_id, closure_sha in RUNS.items():
        run = HERE / "runs" / run_id
        closure_path, invocation_path = run / "closure.json", run / "invocation.json"
        assert sha(closure_path) == closure_sha
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run_id and closure["invocation_sha256"] == sha(invocation_path) and closure["error"] is None
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        accepted.append({"run_id": run_id, "local_path": str(run.resolve()), "closure_sha256": closure_sha, "invocation_sha256": sha(invocation_path), "raw": closure["raw"]})
    index = {"schema": "simlox-d09-var04-shortage-v100-evidence-index/v1", "case_id": "D09", "variant_id": "D09.var04", "version": "1.0.0", "publication_state": "not_published", "source": source, "accepted_runs": accepted, "accepted_raw_count": sum(len(run["raw"]) for run in accepted), "accepted_parent_closure_sha256": "fb536519c47bb0d6bc1a3408066500fd310261d9c939c3796b3f62b02a7c9430", "accepted_resource_donor_closure_sha256": "06a037cce6bd8118bd3c963f026321ad604167504ecadbdc5eb409e510893de3", "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": index["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
