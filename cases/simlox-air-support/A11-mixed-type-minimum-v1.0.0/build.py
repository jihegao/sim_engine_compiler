"""Build A11 mixed-type minimum pair from published A03 1.0.1."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def set_field(tab: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in tab["columns"]].index(field)] = value


def build(required: bool) -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published A03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    t = table(doc, "ProblemDescription")
    t["instances"][0]["rows"][0][0] = (
        "A11 two aircraft types with one minimum of each type"
        if required else "A11 two aircraft types with only an untyped two-aircraft total"
    )
    t = table(doc, "System")
    first = t["instances"][0]["rows"][0]
    second = copy.deepcopy(first)
    set_field(t, second, "SID", "TEACH-AIR-02")
    set_field(t, second, "DESCR", "Alternate teaching aircraft")
    t["instances"][0]["rows"].append(second)
    t = table(doc, "SystemDeployment")
    first = t["instances"][0]["rows"][0]
    second = copy.deepcopy(first)
    set_field(t, second, "SID", "TEACH-AIR-02")
    set_field(t, second, "QTYPS", 1)
    t["instances"][0]["rows"].append(second)
    t = table(doc, "Unit")
    set_field(t, t["instances"][0]["rows"][0], "DESCR", "Three-aircraft mixed-type unit")
    if required:
        names = ["MTID", "SID", "PRI", "NOS", "MNOS", "MNOSA", "NOTE"]
        types = ["string", "string", "integer", "integer", "integer", "integer", "string"]
        doc["model"]["tables"].append({
            "name": "MissionSystem",
            "columns": [{"name": n, "datatype": ty, **({"key": True} if i < 2 else {})} for i, (n, ty) in enumerate(zip(names, types))],
            "instances": [{"instance_name": "", "rows": [
                ["BASIC-MISSION", "TEACH-AIR-01", 1, 1, 1, None, "one required A aircraft"],
                ["BASIC-MISSION", "TEACH-AIR-02", 2, 1, 1, None, "one required B aircraft"],
            ]}],
        })
    return doc


def main() -> None:
    for label, req in (("required", True), ("control", False)):
        raw = (json.dumps(build(req), ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{label}-input.json"
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError(f"frozen {label} input differs")
        else:
            target.write_bytes(raw)
        print(label, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
