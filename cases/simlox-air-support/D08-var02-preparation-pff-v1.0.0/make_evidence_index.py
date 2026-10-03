"""Seal source files and both local D08.var02 native closures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "d08-var02-zero-v100-ssh-20261003-01": "e2c2e31d2b3aedb68a8088826ce1b2dcc44bf02af7008c2c127b9906c20a82ad",
    "d08-var02-positive-v100-ssh-20261003-01": "bb57af9fe2f2125846f99a999765820c0105244ac96cdd95bc371a614c2a4119",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or path.name.startswith("cli-scope-signoff-") or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
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
    index = {
        "schema": "simlox-d08-var02-pff-v100-evidence-index/v1",
        "case_id": "D08",
        "variant_id": "D08.var02",
        "version": "1.0.0",
        "publication_state": "not_published",
        "source": source,
        "accepted_runs": accepted,
        "accepted_raw_count": sum(len(run["raw"]) for run in accepted),
        "direct_parent_closure_sha256": "9b715b36af0625ef6b59283b0f865b188670d93db5aedf60ee82e61714843593",
        "catalog_parent_closure_sha256": "fdb0c93c2a59313392587378665115baa26cb23de01e48d543b56eaa33abfbb8",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": index["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
