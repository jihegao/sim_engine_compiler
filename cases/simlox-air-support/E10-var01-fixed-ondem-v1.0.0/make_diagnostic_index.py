"""Seal the frozen E10.var01 v1.0.0 NO-GO diagnostic without promoting it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "diagnostic-evidence-index.json"
RUNS = {
    "e10-var01-ondem-v100-ssh-20261003-01": "2161792a0fdaa137dd61f81c60993a81a5600733d3e892b595cc082c3fe05d7b",
    "e10-var01-fixed-v100-ssh-20261003-01": "8333fbb14994a90cffdb39bb7d5bd83241328458dc10305b48729f471f619145",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    diagnostic = []
    for run_id, expected in RUNS.items():
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert sha(run / "closure.json") == expected and closure["error"] is None
        assert closure["run_id"] == run_id and closure["invocation_sha256"] == sha(run / "invocation.json")
        for name, seal in closure["raw"].items():
            path = run / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
        diagnostic.append({"run_id": run_id, "local_path": str(run.resolve()), "closure_sha256": expected, "invocation_sha256": sha(run / "invocation.json"), "raw": closure["raw"]})
    result = {
        "schema": "simlox-e10-var01-v100-diagnostic-evidence-index/v1",
        "case_id": "E10", "variant_id": "E10.var01", "version": "1.0.0",
        "verdict": "NO_GO_frozen_contract_resource_report_unmet",
        "publication_state": "not_published",
        "source": source, "diagnostic_runs": diagnostic,
        "diagnostic_raw_count": sum(len(r["raw"]) for r in diagnostic),
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "diagnostic_raw": result["diagnostic_raw_count"], "diagnostic_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
