"""Seal matched SCPMT source and both immutable local native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INDEX = HERE / "evidence-index.json"
RUN_IDS = ("j09-var05-pmt-control-v101-ssh-20261004-01", "j09-var05-pmt-scaled-v101-ssh-20261004-01")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_record(run_id: str) -> dict:
    run = HERE / "runs" / run_id
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    if closure["error"] is not None or closure["invocation_sha256"] != sha(run / "invocation.json"):
        raise ValueError(f"incomplete run or invocation seal: {run_id}")
    for name, seal in closure["raw"].items():
        file = run / name
        if file.stat().st_size != seal["bytes"] or sha(file) != seal["sha256"]:
            raise ValueError(f"raw seal differs: {run_id}/{name}")
    return {"state": "accepted_candidate", "run_id": run_id, "local_path": str(run),
            "closure_sha256": sha(run / "closure.json"),
            "invocation_sha256": closure["invocation_sha256"], "raw": closure["raw"]}


def build() -> dict:
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and
                   "runs" not in p.relative_to(HERE).parts and
                   "__pycache__" not in p.relative_to(HERE).parts and
                   p.name not in {"evidence-index.json", "cli-scope-signoff-2026-10-04.md"})
    source = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in files]
    parent = ROOT / "D03-calendar-pm-v1.0.0"
    diagnostic = ROOT / "J09-var05-pm-tat-scale-v1.0.0"
    return {"schema": "simlox-j09-var05-pmt-fallback-pair-evidence-index/v1", "case_id": "J09",
            "variant_id": "J09.var05", "version": "1.0.1", "publication_state": "not_published",
            "source": source,
            "accepted_parent": {"package": parent.name, "input_sha256": sha(parent / "native-input.json"),
                                "closure_sha256": sha(parent / "runs/d03-calendar-v100-ssh-20261001-02/closure.json")},
            "excluded_diagnostic": {"package": diagnostic.name,
                                     "closure_sha256": sha(diagnostic / "runs/j09-var05-scpmt2-v100-ssh-20261004-01/closure.json")},
            "runs": [run_record(run_id) for run_id in RUN_IDS],
            "raw_location_policy": "local_only_ignored_runs_not_committed"}


if __name__ == "__main__":
    raw = (json.dumps(build(), indent=2) + "\n").encode()
    INDEX.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
