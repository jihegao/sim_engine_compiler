"""Seal exact source bytes and ignored local negative-run raw bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "E15-var01-time-based-cycle-v1.0.1"
PARENT_SOURCE = ROOT / "E15-var01-time-based-cycle-v1.0.0"
RUN = HERE / "runs/e15-var09-istoh-below-v100-ssh-20261005-01"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


closure = read(RUN / "closure.json")
assert closure["error"] is None and closure["expected_negative"] is True and len(closure["raw"]) == 10
for name, expected in closure["raw"].items():
    assert seal(RUN / name) == expected, name
author = read(HERE / "author-validation-2026-10-05.json")
assert author["passed"] is True and author["checks"] == 44 and author["differences"] == []
review = read(HERE / "review/independent-verdict.json")
assert review["verdict"] == "GO_BOUNDED_REJECTION" and review["checks_passed"] == review["checks_total"] == 267 and review["failures"] == []
source = {
    path.relative_to(HERE).as_posix(): seal(path)
    for path in HERE.rglob("*")
    if path.is_file() and "runs" not in path.relative_to(HERE).parts
    and "__pycache__" not in path.relative_to(HERE).parts
    and path.name != "evidence-index.json"
}
index = {
    "schema": "simlox-e15-var09-below-nominal-v100-evidence-index/v1",
    "case_id": "E15", "variant_id": "E15.var09", "version": "1.0.0",
    "publication_state": "not_published",
    "source": dict(sorted(source.items())),
    "accepted_parent": {
        "package": PARENT.name,
        "input": seal(PARENT_SOURCE / "native-input.json"),
        "signoff": seal(PARENT / "cli-scope-signoff-2026-10-05.md"),
        "evidence_index": seal(PARENT / "evidence-index.json"),
        "event_log": seal(PARENT_SOURCE / "runs/e15-var01-timecycle-v100-ssh-20261005-01/model.log"),
        "selected_report": seal(PARENT / "runs/e15-var01-timecycle-report-v101-ssh-20261005-01/selected-report-raw.json"),
    },
    "run": {"run_id": RUN.name, "local_directory": str(RUN),
            "invocation": seal(RUN / "invocation.json"),
            "closure": seal(RUN / "closure.json"),
            "raw_files_total": 10, "raw": closure["raw"]},
}
(HERE / "evidence-index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode())
print(json.dumps({"source": len(source), "raw": 10,
                  "index_sha256": seal(HERE / "evidence-index.json")["sha256"]}))
