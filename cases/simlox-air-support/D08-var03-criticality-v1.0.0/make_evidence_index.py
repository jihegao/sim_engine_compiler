"""Index D08.var03 source files and the two sealed local native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"
RUNS = {
    "d08-var03-traditional-v100-ssh-20261002-01": "512f30614f3ce25ea4253afa6d708008f5c182a76366464709700f209879ffe0",
    "d08-var03-failure-mode-v100-ssh-20261002-01": "47a0f9aa98a0682afa4a997de86e880ea0f9e654cee16587b9f6e309d8196fbe",
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
    index = {"schema": "simlox-d08-var03-criticality-v100-evidence-index/v1", "case_id": "D08", "variant_id": "D08.var03", "version": "1.0.0", "publication_state": "not_published", "source": source, "accepted_runs": accepted, "accepted_raw_count": sum(len(run["raw"]) for run in accepted), "traditional_control_closure_sha256": "3642d558e98abd31f4510e213286182f9ce0d6eda0a86f6185c64f439f7e79f0", "failure_mode_control_closure_sha256": "afd8689161874d247dee92a6f6265211733375b8933f3fcd30bfb297cfe975c7", "catalog_parent_closure_sha256": "fdb0c93c2a59313392587378665115baa26cb23de01e48d543b56eaa33abfbb8", "raw_location_policy": "local_only_ignored_runs_not_committed"}
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "accepted_raw": index["accepted_raw_count"], "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
