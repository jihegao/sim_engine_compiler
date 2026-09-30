"""Derive operational crew-failure inputs with and without one idle spare."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
PARENT_SHA = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"
SCHEMA_PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
SCHEMA_PARENT_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"


def build() -> dict[str, dict]:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(SCHEMA_PARENT.read_bytes()).hexdigest() == SCHEMA_PARENT_SHA
    parent = json.loads(PARENT.read_bytes())
    schema = json.loads(SCHEMA_PARENT.read_bytes())
    t = {table["name"]: table for table in parent["model"]["tables"]}
    s = {table["name"]: table for table in schema["model"]["tables"]}
    assert "ResourceStationData" not in t
    assert t["ResourceAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]]
    assert t["Resource"]["instances"][0]["rows"][0][5] == "SPECIAL"
    template = copy.deepcopy(s["ResourceStationData"])
    assert [col["name"] for col in template["columns"]] == ["RID", "STID", "PRICE", "SUSTC", "MUTILF", "RMTBF", "RFTT", "RMDT", "RMDTD", "SHPID", "NOTE"]
    template["instances"][0]["rows"] = [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, None, None]]
    result = {}
    for variant, qty in (("oper-no-spare", 2), ("oper-one-spare", 3)):
        child = copy.deepcopy(parent)
        tables = {table["name"]: table for table in child["model"]["tables"]}
        tables["ProblemDescription"]["instances"][0]["rows"][0][0] = f"C10 resource operation-time failures; crew pool {qty}; seed 1"
        tables["ResourceAllocation"]["instances"][0]["rows"][0][3] = qty
        child["model"]["tables"].append(copy.deepcopy(template))
        result[variant] = child
    return result


def main() -> None:
    for variant, doc in build().items():
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} input differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
