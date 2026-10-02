"""Index frozen publication sources and two sealed local native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "e15-var07-above-nominal-v100-ssh-20261002-01": "0c4cbdad0dfa7a1e35fb14220b36d1061d3e0c2976db3d18cca50bdb49d4b1fb",
    "e15-var07-above-nominal-item-v100-ssh-20261002-01": "582f11d0ae5ac2a7750d3c7160e558630ef51eec6019d5252a951483a147599a",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sources = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        sources.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    accepted = []
    for run_id, closure_sha in RUNS.items():
        run = HERE / "runs" / run_id
        closure_path, invocation_path = run / "closure.json", run / "invocation.json"
        assert sha(closure_path) == closure_sha
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run_id and closure["invocation_sha256"] == sha(invocation_path) and closure["error"] is None
        for name, seal in closure["raw"].items():
            raw = run / name
            assert raw.is_file() and raw.stat().st_size == seal["bytes"] and sha(raw) == seal["sha256"]
        accepted.append({"run_id": run_id, "local_path": str(run.resolve()), "closure_sha256": closure_sha, "invocation_sha256": sha(invocation_path), "raw": closure["raw"]})
    index = {"schema": "simlox-e15-var07-above-nominal-v100-evidence-index/v1", "case_id": "E15", "variant_id": "E15.var07", "version": "1.0.0", "publication_state": "not_published", "source": sources, "accepted_runs": accepted, "accepted_raw_count": sum(len(run["raw"]) for run in accepted), "parent_native_closure_sha256": "f00b8fc07a4deb1db33b6142f0704e373a5db09197e8f6190fd0b22947e6feff", "parent_selected_report_closure_sha256": "640e77479b0930137ca7f97e1f346babc9de7132ec33cd6f9ca400fb8295b249", "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(sources), "accepted_raw": index["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
