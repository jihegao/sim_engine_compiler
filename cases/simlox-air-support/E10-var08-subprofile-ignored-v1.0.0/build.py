"""Freeze E10.var08 subprofile wrapper fields documented as ignored."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var05-nested-repeat-v1.0.0/native-input.json"
PARENT_SHA = "02bc6ae8f42c2e98e7f217ba3a603d94a1758db9c2bbee52f5a7b6de27d18f1c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> bytes:
    assert sha(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    desc = tables["ProblemDescription"]["instances"][0]["rows"][0]
    desc[0] = "E10.var08 subprofile wrapper MINBS7 TPTIM9 TPTIMD <EXP> ignored"
    policy = tables["TransportPolicyProfile"]
    cols = [col["name"] for col in policy["columns"]]
    assert len(policy["instances"]) == 1 and len(policy["instances"][0]["rows"]) == 2
    wrapper, child = policy["instances"][0]["rows"]
    assert wrapper[cols.index("TPRID")] == "DOWN-POLICY" and wrapper[cols.index("STPRID")] == "REPEAT-FIXED"
    assert all(wrapper[cols.index(col)] is None for col in ("MINBS", "TPTIM", "TPTIMD"))
    assert child[cols.index("STPRID")] == "FIXED" and child[cols.index("TPTIM")] == 2
    wrapper[cols.index("MINBS")] = 7
    wrapper[cols.index("TPTIM")] = 9.0
    wrapper[cols.index("TPTIMD")] = "<EXP>"
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = build()
    output = HERE / "native-input.json"
    if write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
