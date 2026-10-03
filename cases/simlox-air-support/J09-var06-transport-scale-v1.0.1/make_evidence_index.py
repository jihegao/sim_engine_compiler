"""Seal tracked source files and both immutable local native run closures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INDEX = HERE / "evidence-index.json"
ACCEPTED_RUN = HERE / "runs/j09-var06-sctrt2-v101-ssh-20261004-01"
DIAGNOSTIC = ROOT / "J09-var06-transport-scale-v1.0.0"
DIAGNOSTIC_RUN = DIAGNOSTIC / "runs/j09-var06-sctrt2-v100-ssh-20261004-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(directory: Path) -> list[dict]:
    excluded = {"evidence-index.json", "cli-scope-signoff-2026-10-04.md"}
    paths = sorted(p for p in directory.rglob("*") if p.is_file() and
                   "runs" not in p.relative_to(directory).parts and
                   "__pycache__" not in p.relative_to(directory).parts and
                   p.name not in excluded)
    return [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in paths]


def run_entry(directory: Path, state: str) -> dict:
    closure_path = directory / "closure.json"
    closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
    raw = closure["raw"]
    for name, seal in raw.items():
        path = directory / name
        if sha(path) != seal["sha256"] or path.stat().st_size != seal["bytes"]:
            raise ValueError(f"raw seal differs: {path}")
    if closure["invocation_sha256"] != sha(directory / "invocation.json"):
        raise ValueError("invocation seal differs")
    return {"state": state, "run_id": directory.name, "local_path": str(directory),
            "closure_sha256": sha(closure_path), "invocation_sha256": closure["invocation_sha256"], "raw": raw}


def build() -> dict:
    return {"schema": "simlox-j09-var06-transport-scale-evidence-index/v1", "case_id": "J09",
            "variant_id": "J09.var06", "version": "1.0.1", "publication_state": "not_published",
            "source": files(DIAGNOSTIC) + files(HERE),
            "accepted_parent": {"package": "E04-upstream-transport-slow-v1.0.0",
                                "input_sha256": sha(ROOT / "E04-upstream-transport-slow-v1.0.0/native-input.json"),
                                "closure_sha256": sha(ROOT / "E04-upstream-transport-slow-v1.0.0/runs/e04-slow-v100-ssh-20260929-01/closure.json")},
            "diagnostic": run_entry(DIAGNOSTIC_RUN, "excluded_checker_mismatch"),
            "run": run_entry(ACCEPTED_RUN, "accepted_candidate"),
            "raw_location_policy": "local_only_ignored_runs_not_committed"}


if __name__ == "__main__":
    raw = (json.dumps(build(), indent=2) + "\n").encode()
    INDEX.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
