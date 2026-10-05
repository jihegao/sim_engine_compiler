"""Index frozen excluded diagnostic sources and sealed local raw bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
RUN = HERE / "runs/e15-var08-equal-point-v100-ssh-20261005-01"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


closure = read(RUN / "closure.json")
assert closure["error"] == "frozen equal-point event gate failed"
assert len(closure["raw"]) == 11
for name, pin in closure["raw"].items():
    assert seal(RUN / name) == pin, name
review = read(HERE / "review/independent-verdict.json")
assert review["decision"] == "GO_EXCLUDE_FROZEN_H0_HYPOTHESIS" and review["accepted_case"] is False
assert review["checks_passed"] == review["checks_total"] == 244
source = {
    path.relative_to(HERE).as_posix(): seal(path)
    for path in HERE.rglob("*")
    if path.is_file() and "runs" not in path.relative_to(HERE).parts
    and "__pycache__" not in path.relative_to(HERE).parts
    and path.name != "evidence-index.json"
}
index = {
    "schema": "simlox-e15-var08-v100-excluded-evidence-index/v1",
    "case_id": "E15", "variant_id": "E15.var08", "version": "1.0.0",
    "publication_state": "excluded_diagnostic",
    "source": dict(sorted(source.items())),
    "accepted_parent": {
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
            "raw_files_total": 11, "raw": closure["raw"]},
}
(HERE / "evidence-index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode())
print(json.dumps({"source": len(source), "raw": 11,
                  "index_sha256": seal(HERE / "evidence-index.json")["sha256"]}))
