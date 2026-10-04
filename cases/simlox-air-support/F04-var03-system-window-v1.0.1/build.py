"""Freeze a System-only 0–48h collection window from accepted F04.var02."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F04-var02-stochastic-43day-v1.0.0" / "native-input.json"
PARENT_SHA = "33ec12ae0e576969673bcb0e9ccb2ade9bb3799b91e13d734e77950941645cb4"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    result = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(result) == 1, name
    return result[0]


def rows(doc: dict, name: str) -> list[list]:
    t = table(doc, name)
    assert len(t["instances"]) == 1
    return t["instances"][0]["rows"]


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    doc = json.loads(raw)
    assert len(doc["model"]["tables"]) == 33
    control = table(doc, "Control")
    names = [c["name"] for c in control["columns"]]
    value = rows(doc, "Control")[0]
    assert (value[names.index("NREPS")], value[names.index("SIMPE")],
            value[names.index("RSEED")], value[names.index("TCLEV")],
            value[names.index("RCEND")]) == (128, 1032.0, "1", 0.0, 1032.0)
    collection = table(doc, "ResultCollection")
    assert [c["name"] for c in collection["columns"]] == [
        "RTYPE", "RCINT", "RCSTA", "RCEND", "RCPID", "NOTE"]
    assert rows(doc, "ResultCollection") == [
        ["MISSION", 0.5, 0, 1032.0, None, None],
        ["SYSTEM", 0.5, 0, 1032.0, None, None]]
    rows(doc, "ProblemDescription")[0][0] = (
        "F04.var03 v1.0.1 first 48h System collection; full 1032h simulation")
    rows(doc, "ResultCollection")[1][3] = 48.0
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "native-input.json"
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
