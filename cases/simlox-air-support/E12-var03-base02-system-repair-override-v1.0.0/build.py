"""Freeze a BASE-02-specific SystemRepair override of the shared group default."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var02-two-fault-group-v1.0.0/native-input.json"
PARENT_SHA = "a93cfb093dc7a5b3588ac025be42d78edebf5b0c6fe2eed64b3997ea68efd5a7"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var03 BASE-02 one-hour individual SystemRepair override of BASE-GRP half-hour default"
    )
    repair = table(doc, "SystemRepair")
    assert [c["name"] for c in repair["columns"]] == ["SID", "STID", "DIRPT", "SURPT", "DIRPF", "SURPF", "DIRPM", "SURPM", "DIRPC", "SURPC", "DIRPTID", "SURPTID", "DIRPD", "SURPD", "NOTE"]
    rows = repair["instances"][0]["rows"]
    assert len(rows) == 1 and rows[0][:4] == ["TEACH-AIR-01", "BASE-GRP", 0.0, 0.5] and rows[0][11] == "E01-SURP"
    override = rows[0].copy()
    override[1] = "BASE-02"
    override[3] = 1.0
    override[11] = "E12-BASE02-SURP"
    rows.append(override)
    tasks = table(doc, "Tasks")["instances"][0]["rows"]
    assert tasks == [["E01-SURP", "Explicit local LRU system replacement", None, None, None]]
    tasks.append(["E12-BASE02-SURP", "One-hour BASE-02 local LRU replacement", None, None, None])
    breakdown = table(doc, "TaskBreakDown")["instances"][0]["rows"]
    assert len(breakdown) == 2 and [r[0] for r in breakdown] == ["E01-SURP", "E01-SURP"]
    breakdown.extend([
        ["E12-BASE02-SURP", 1, "<REMOVE>", 1 / 3, None, None],
        ["E12-BASE02-SURP", 2, "<REPLACE>", 2 / 3, None, None],
    ])
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    output = HERE / "native-input.json"
    raw = build()
    if sys.argv[1:] == ["--write"]:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: build.py [--write]")
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))
