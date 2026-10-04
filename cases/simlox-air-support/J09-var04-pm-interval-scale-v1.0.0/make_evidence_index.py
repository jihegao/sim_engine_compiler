"""Seal tracked J09.var04 sources and immutable local native run evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/j09-var04-scpmi2-v100-ssh-20261004-01"
INDEX = HERE / "evidence-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and
                   "runs" not in p.relative_to(HERE).parts and
                   "__pycache__" not in p.relative_to(HERE).parts and
                   p.name not in {"evidence-index.json", "cli-scope-signoff-2026-10-04.md"})
    source = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in files]
    closure_path = RUN / "closure.json"
    closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
    for name, seal in closure["raw"].items():
        path = RUN / name
        if path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
            raise ValueError(f"raw seal differs: {name}")
    if closure["invocation_sha256"] != sha(RUN / "invocation.json"):
        raise ValueError("invocation seal differs")
    parent = ROOT / "D03-calendar-pm-v1.0.0"
    precedent = ROOT / "J09-var06-transport-scale-v1.0.1"
    return {"schema": "simlox-j09-var04-pm-interval-scale-evidence-index/v1", "case_id": "J09",
            "variant_id": "J09.var04", "version": "1.0.0", "publication_state": "not_published", "source": source,
            "accepted_parent": {"package": parent.name, "input_sha256": sha(parent / "native-input.json"),
                                "closure_sha256": sha(parent / "runs/d03-calendar-v100-ssh-20261001-02/closure.json")},
            "scale_schema_precedent": {"package": precedent.name,
                                       "evidence_index_sha256": sha(precedent / "evidence-index.json")},
            "run": {"state": "accepted_candidate", "run_id": RUN.name, "local_path": str(RUN),
                    "closure_sha256": sha(closure_path), "invocation_sha256": closure["invocation_sha256"],
                    "raw": closure["raw"]},
            "raw_location_policy": "local_only_ignored_runs_not_committed"}


if __name__ == "__main__":
    raw = (json.dumps(build(), indent=2) + "\n").encode()
    INDEX.write_bytes(raw)
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
