"""Index source Git bytes and locally sealed native raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/i07-var04-old-cycle-v100-ssh-20261005-01"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


closure = read(RUN / "closure.json")
assert closure["error"] is None and len(closure["raw"]) == 13
for name, expected in closure["raw"].items():
    assert seal(RUN / name) == expected, name
assert read(HERE / "author-validation-2026-10-05.json")["passed"] is True
review = read(HERE / "review/independent-verdict.json")
assert review["checks_passed"] == review["checks_total"] == 574 and review["failures"] == []
assert review["verdict"] == "GO_BOUNDED_FIRST_CYCLE"
source = {
    path.relative_to(HERE).as_posix(): seal(path)
    for path in HERE.rglob("*")
    if path.is_file() and "runs" not in path.relative_to(HERE).parts
    and "__pycache__" not in path.relative_to(HERE).parts
    and path.name != "evidence-index.json"
}
index = {
    "schema": "simlox-i07-var04-old-cycle-evidence-index/v1",
    "case_id": "I07", "variant_id": "I07.var04", "version": "1.0.0",
    "publication_state": "not_published",
    "source": dict(sorted(source.items())),
    "accepted_parent": {
        "package": "E15-var01-time-based-cycle-v1.0.1",
        "input": seal(HERE.parent / "E15-var01-time-based-cycle-v1.0.0/native-input.json"),
        "signoff": seal(HERE.parent / "E15-var01-time-based-cycle-v1.0.1/cli-scope-signoff-2026-10-05.md"),
        "event_log": seal(HERE.parent / "E15-var01-time-based-cycle-v1.0.0/runs/e15-var01-timecycle-v100-ssh-20261005-01/model.log"),
        "selected_report": seal(HERE.parent / "E15-var01-time-based-cycle-v1.0.1/runs/e15-var01-timecycle-report-v101-ssh-20261005-01/selected-report-raw.json"),
    },
    "run": {"run_id": RUN.name, "local_directory": str(RUN),
            "invocation": seal(RUN / "invocation.json"),
            "closure": seal(RUN / "closure.json"),
            "raw_files_total": 13, "raw": closure["raw"]},
}
(HERE / "evidence-index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode())
print(json.dumps({"source": len(source), "raw": 13,
                  "index_sha256": seal(HERE / "evidence-index.json")["sha256"]}))
