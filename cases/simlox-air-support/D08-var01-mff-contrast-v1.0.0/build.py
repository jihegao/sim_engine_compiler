"""Freeze the D08.var01 default and mission-specific low-MFF sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0/native-input.json"
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
ARMS = {"default": None, "low": 0.000001}
EXPECTED = {
    "default": "5be5592989ac38349141d22c9b9bd5f9db11029182f66bbb456207bb908ae030",
    "low": "f4e82b497668a016f79fd2e8f54f7c6df59e1b8a5a9a1f0c084eb8cfcb6b2d66",
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1
    return found[0]


def build(arm: str) -> bytes:
    assert sha(PARENT.read_bytes()) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    description = table(doc, "ProblemDescription")
    dc = [col["name"] for col in description["columns"]]
    assert len(description["instances"]) == 1 and len(description["instances"][0]["rows"]) == 1
    description["instances"][0]["rows"][0][dc.index("PDESC")] = f"D08.var01 RISK-MISSION MFF {'omitted default 1' if arm == 'default' else 'explicit 0.000001'}"
    mission = table(doc, "MissionType")
    names = [col["name"] for col in mission["columns"]]
    rows = [row for inst in mission["instances"] for row in inst["rows"]]
    assert len(rows) == 2 and [row[names.index("MTID")] for row in rows] == ["BASIC-MISSION", "RISK-MISSION"]
    assert rows[0][names.index("MFF")] == 0 and rows[1][names.index("MFF")] == 1.0
    rows[1][names.index("MFF")] = ARMS[arm]
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    result = {}
    for arm in ARMS:
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        if write:
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw, f"frozen source differs: {path}"
            assert sha(raw) == EXPECTED[arm]
        result[arm] = sha(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs_sha256": result}))


if __name__ == "__main__":
    main()
