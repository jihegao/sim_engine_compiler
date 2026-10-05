"""Pin publishable source bytes and both immutable native raw inventories."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "I07-var09-strategy-switch-v1.0.0"
RUN = HERE / "runs/i07-var09-time-to-stock-v101-ssh-20261005-01"
OLD_RUN = OLD / "runs/i07-var09-time-to-stock-v100-ssh-20261005-02"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


source = {
    path.relative_to(HERE).as_posix(): seal(path)
    for path in HERE.rglob("*")
    if path.is_file() and "runs" not in path.relative_to(HERE).parts
    and "__pycache__" not in path.relative_to(HERE).parts
    and path.name != "evidence-index.json"
}
old_closure, closure = read(OLD_RUN / "closure.json"), read(RUN / "closure.json")
assert len(old_closure["raw"]) == len(closure["raw"]) == 10
for directory, record in ((OLD_RUN, old_closure), (RUN, closure)):
    for name, expected in record["raw"].items():
        assert seal(directory / name) == expected, (directory, name)
assert closure["error"] is None
assert read(HERE / "author-validation-2026-10-05.json")["passed"] is True
review = read(HERE / "review/independent-postrun-2026-10-05.json")
assert review["checks_passed"] == review["checks_total"] == 234 and review["failures"] == []
assert review["verdict"] == "GO_BOUNDED_CONVERTER_REJECTION"
index = {
    "schema": "simlox-i07-var09-strategy-switch-evidence-index/v1",
    "case_id": "I07", "variant_id": "I07.var09", "version": "1.0.1",
    "publication_state": "not_published",
    "source": dict(sorted(source.items())),
    "excluded_diagnostic": {
        "package": OLD.name,
        "evidence_index": seal(OLD / "evidence-index.json"),
        "run_id": OLD_RUN.name,
        "closure": seal(OLD_RUN / "closure.json"),
        "raw_files_total": 10,
        "raw": old_closure["raw"],
        "publication_state": "excluded_diagnostic",
    },
    "run": {
        "run_id": RUN.name,
        "local_directory": str(RUN),
        "invocation": seal(RUN / "invocation.json"),
        "closure": seal(RUN / "closure.json"),
        "raw_files_total": 10,
        "raw": closure["raw"],
    },
}
(HERE / "evidence-index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode())
print(json.dumps({"source": len(source), "old_raw": 10, "new_raw": 10,
                  "index_sha256": seal(HERE / "evidence-index.json")["sha256"]}))
