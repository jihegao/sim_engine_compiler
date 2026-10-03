"""Freeze explicit Y/N critical-failure mission-abort inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D08-var01-mff-contrast-v1.0.0/native-input-default.json"
PARENT_SHA = "5be5592989ac38349141d22c9b9bd5f9db11029182f66bbb456207bb908ae030"
ARMS = {"yes": "Y", "no": "N"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build(arm: str) -> bytes:
    assert sha(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"D08.var04 RISK-MISSION explicit SYACF {ARMS[arm]}"
    )
    mission = table(doc, "MissionType")
    names = [c["name"] for c in mission["columns"]]
    rows = [row for inst in mission["instances"] for row in inst["rows"]]
    assert [row[names.index("MTID")] for row in rows] == ["BASIC-MISSION", "RISK-MISSION"]
    assert rows[1][names.index("SYACF")] is None
    rows[1][names.index("SYACF")] = ARMS[arm]
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    out = {}
    for arm in ARMS:
        path = HERE / f"native-input-{arm}.json"
        raw = build(arm)
        if write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw, arm
        out[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs_sha256": out}))


if __name__ == "__main__":
    main()
