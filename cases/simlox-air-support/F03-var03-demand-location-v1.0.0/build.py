"""Build a two-base risk-demand location pair from accepted F03.var02 control."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F03-var02-two-base-stock-v1.0.0" / "depot_only-input.json"
PARENT_SHA = "ed0c7e77844cc87f9f1cfe1fddc45d387072adec979dd93f99dd897d60347819"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(doc: dict, name: str) -> list[list]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1
    return matches[0]["instances"][0]["rows"]


def build() -> tuple[dict, dict]:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    assert [(r[0], r[2]) for r in rows(parent, "Unit")] == [("TEACH-UNIT", "BASE-01"), ("TEACH-UNIT-2", "BASE-02")]
    for name in ("MissionPreparation", "MissionTurnround"):
        assert [(r[0], r[2]) for r in rows(parent, name)] == [("BASIC-MISSION", "BASE-01"), ("RISK-MISSION", "BASE-01"), ("BASE2-MISSION", "BASE-02")]
    base1 = copy.deepcopy(parent)
    base2 = copy.deepcopy(parent)
    rows(base1, "ProblemDescription")[0][0] = "F03.var03 risk-fleet demand at BASE-01; second unit at BASE-02"
    rows(base2, "ProblemDescription")[0][0] = "F03.var03 risk-fleet demand at BASE-02; second unit at BASE-01"
    for row in rows(base2, "Unit"):
        row[2] = "BASE-02" if row[2] == "BASE-01" else "BASE-01"
    for name in ("MissionPreparation", "MissionTurnround"):
        for row in rows(base2, name):
            row[2] = "BASE-02" if row[2] == "BASE-01" else "BASE-01"
    assert all(rows(base1, name) == rows(base2, name) for name in ("Station", "StationStructure", "SystemRepair", "PMLocation", "ResourceAllocation", "StockAllocation", "SystemDeployment", "Operations", "OperationProfile"))
    return base1, base2


def main() -> None:
    result = {}
    for arm, doc in zip(("risk_base1", "risk_base2"), build()):
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{arm}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {arm} input changed"
        else:
            path.write_bytes(raw)
        result[arm] = sha(raw)
    print(json.dumps({"parent": PARENT_SHA, "inputs": result}))


if __name__ == "__main__":
    main()
