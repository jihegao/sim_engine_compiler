"""Index exact diagnostic source bytes and sealed local native raw."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var02-rosiz-v100-ssh-20261005-01"
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


closure = read(RUN / "closure.json")
assert closure["error"] is None and len(closure["raw"]) == 24
for name, pin in closure["raw"].items():
    assert seal(RUN / name) == pin, name
author, review = read(HERE / "author-validation-2026-10-05.json"), read(HERE / "review/independent-verdict.json")
assert author["passed"] is True and author["checks"] == 224 and author["differences"] == []
assert review["verdict"] == "GO_DIAGNOSTIC_ONLY" and review["checks_passed"] == review["checks_total"] == 1138 and review["failures"] == []
source = {
    path.relative_to(HERE).as_posix(): seal(path)
    for path in HERE.rglob("*")
    if path.is_file() and "runs" not in path.relative_to(HERE).parts
    and "__pycache__" not in path.relative_to(HERE).parts
    and path.name != "evidence-index.json"
}
index = {
    "schema": "simlox-i07-var02-v100-diagnostic-evidence-index/v1",
    "case_id": "I07", "variant_id": "I07.var02", "version": "1.0.0",
    "publication_state": "excluded_diagnostic",
    "source": dict(sorted(source.items())),
    "accepted_model_parent": {
        "package": PARENT.name,
        "input": seal(PARENT / "native-input-explicit-three.json"),
        "signoff": seal(PARENT / "cli-scope-signoff-2026-10-02.md"),
        "evidence_index": seal(PARENT / "evidence-index.json"),
        "event_log": seal(PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01/model.log"),
        "selected_report": seal(PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json"),
    },
    "run": {"run_id": RUN.name, "local_directory": str(RUN),
            "invocation": seal(RUN / "invocation.json"),
            "closure": seal(RUN / "closure.json"),
            "raw_files_total": 24, "raw": closure["raw"]},
}
(HERE / "evidence-index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode())
print(json.dumps({"source": len(source), "raw": 24,
                  "index_sha256": seal(HERE / "evidence-index.json")["sha256"]}))
