"""Index report-only source and both original and new local raw seals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "E15-var08-equal-point-v1.0.0"
OLD_RUN = OLD / "runs/e15-var08-equal-point-v100-ssh-20261005-01"
RUN = HERE / "runs/e15-var08-report-only-v101-ssh-20261005-01"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


old_index, old_closure, closure = (read(p) for p in (OLD / "evidence-index.json", OLD_RUN / "closure.json", RUN / "closure.json"))
assert old_index["publication_state"] == "excluded_diagnostic"
assert old_closure["error"] == "frozen equal-point event gate failed" and len(old_closure["raw"]) == 11
assert closure["error"] is None and len(closure["raw"]) == 4
for directory, raw in ((OLD_RUN, old_closure["raw"]), (RUN, closure["raw"])):
    for name, pin in raw.items():
        assert seal(directory / name) == pin, name
author, review = read(HERE / "author-validation-2026-10-05.json"), read(HERE / "review/independent-verdict.json")
assert author["passed"] is True and author["checks"] == 127 and author["differences"] == []
assert review["checks_passed"] == review["checks_total"] == 531 and review["failures"] == []
source = {
    path.relative_to(HERE).as_posix(): seal(path)
    for path in HERE.rglob("*")
    if path.is_file() and "runs" not in path.relative_to(HERE).parts
    and "__pycache__" not in path.relative_to(HERE).parts
    and path.name != "evidence-index.json"
}
index = {
    "schema": "simlox-e15-var08-v101-report-evidence-index/v1",
    "case_id": "E15", "variant_id": "E15.var08", "version": "1.0.1",
    "publication_state": "not_published",
    "source": dict(sorted(source.items())),
    "accepted_model_parent": old_index["accepted_parent"],
    "excluded_diagnostic": {
        "package": OLD.name, "evidence_index": seal(OLD / "evidence-index.json"),
        "run_id": OLD_RUN.name, "closure": seal(OLD_RUN / "closure.json"),
        "event_log": seal(OLD_RUN / "model.log"), "sxo": seal(OLD_RUN / "model.sxo"),
        "raw_files_total": 11, "raw": old_closure["raw"],
    },
    "report_only_run": {
        "run_id": RUN.name, "local_directory": str(RUN),
        "invocation": seal(RUN / "invocation.json"), "closure": seal(RUN / "closure.json"),
        "raw_files_total": 4, "raw": closure["raw"],
    },
}
(HERE / "evidence-index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode())
print(json.dumps({"source": len(source), "old_raw": 11, "new_raw": 4,
                  "index_sha256": seal(HERE / "evidence-index.json")["sha256"]}))
