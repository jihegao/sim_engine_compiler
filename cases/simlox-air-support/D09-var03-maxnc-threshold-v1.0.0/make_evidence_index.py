"""Seal D09.var03 sources and two immutable local native run closures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "d09-var03-limit-2-v100-ssh-20261002-01": "08ccb3f5971b38f745ced478c830bb03a52fd7f54e8df3d439437702db0af6e8",
    "d09-var03-limit-3-v100-ssh-20261002-01": "2d6d00b727f81d1e1558b82144e3b556c2b8cc6274db67a70c5f6c96b00d9514",
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
    index = {"schema": "simlox-d09-var03-maxnc-v100-evidence-index/v1", "case_id": "D09", "variant_id": "D09.var03", "version": "1.0.0", "publication_state": "not_published", "source": source, "accepted_runs": accepted, "accepted_raw_count": sum(len(run["raw"]) for run in accepted), "accepted_parent_closure_sha256": "58b040c8cef5a97ab0c65848b69bb0e022716d45934d84fcb7e9cf78014e73a3", "d08_prerequisite_closure_sha256": "512f30614f3ce25ea4253afa6d708008f5c182a76366464709700f209879ffe0", "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": index["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
