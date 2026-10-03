"""Freeze matched zero/positive preparation failure-factor inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D08-var01-mff-contrast-v1.0.0/native-input-default.json"
PARENT_SHA = "5be5592989ac38349141d22c9b9bd5f9db11029182f66bbb456207bb908ae030"
ARMS = {"zero": 0.0, "positive": 10.0}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def build(arm: str) -> bytes:
    assert digest(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"D08.var02 RISK-MISSION preparation PFF {ARMS[arm]:g}"
    )
    preparation = table(doc, "MissionPreparation")
    assert preparation["instances"][0]["rows"] == []
    assert [c["name"] for c in preparation["columns"]] == [
        "MTID", "SID", "STID", "DURN", "TID", "DURND", "NOTE"
    ]
    preparation["instances"][0]["rows"] = [
        ["RISK-MISSION", "TEACH-AIR-01", "BASE-01", 1.0, None, None, None]
    ]
    assert not any(t["name"] == "MissionReliability" for t in doc["model"]["tables"])
    doc["model"]["tables"].append(
        {
            "name": "MissionReliability",
            "columns": [
                {"name": "MTID", "datatype": "string", "key": True},
                {"name": "SID", "datatype": "string", "key": True},
                {"name": "IID", "datatype": "string", "key": True},
                {"name": "MFF", "datatype": "double"},
                {"name": "PFF", "datatype": "double"},
                {"name": "NOTE", "datatype": "string"},
            ],
            "instances": [
                {
                    "instance_name": "",
                    "rows": [
                        ["RISK-MISSION", "TEACH-AIR-01", "<SYSTEM>", None, ARMS[arm], None]
                    ],
                }
            ],
        }
    )
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
