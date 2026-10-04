"""Seal the excluded E09 v1.0.0 diagnostic without publishing it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    contract = load(HERE / "contract.json")
    run = HERE / "runs" / contract["run_id"]
    closure = load(run / "closure.json")
    verdict = load(HERE / "review" / "independent-verdict.json")
    assert closure["run_id"] == run.name and closure["error"] is None
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert verdict["verdict"] == "NO_GO_FULL_CONTRACT" and verdict["checks"] == verdict["passed"] and not verdict["failed"]
    for name, meta in closure["raw"].items():
        path = run / name
        assert path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT or "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        source.append({"path": path.relative_to(HERE).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    result = {
        "schema": "simlox-e09-v100-excluded-diagnostic-index/v1",
        "case_id": "E09", "version": "1.0.0", "publication_state": "excluded_diagnostic",
        "reason": "Default JSON lacked per-station ItemResults required by frozen contract.",
        "source": source,
        "diagnostic_run": {"run_id": run.name, "local_path": str(run.resolve()), "closure_sha256": sha(run / "closure.json"), "raw": closure["raw"]},
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "diagnostic_raw": len(closure["raw"]), "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
