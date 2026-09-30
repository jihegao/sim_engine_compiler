"""Build A11 explicit-formation priority and fallback probes from published A11."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
PARENT_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"
VARIANTS = ("ab-high", "aa-high", "b-missing")


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def add_table(doc: dict, name: str, columns: list[tuple[str, str, bool]], rows: list[list]) -> None:
    doc["model"]["tables"].append({
        "name": name,
        "columns": [{"name": field, "datatype": kind, **({"key": True} if key else {})} for field, kind, key in columns],
        "instances": [{"instance_name": "", "rows": rows}],
    })


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published A11 mixed-type parent differs")
    doc = copy.deepcopy(json.loads(raw))
    description = {
        "ab-high": "A11 explicit formations: preferred AB with both types ready",
        "aa-high": "A11 explicit formations: preferred AA overrides MissionSystem B minimum",
        "b-missing": "A11 explicit formations: AB preferred but B undeployed, fallback AA",
    }[variant]
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = description
    add_table(doc, "Formation", [
        ("FID", "string", True), ("DESCR", "string", False), ("NOTE", "string", False),
    ], [
        ["FORM-AB", "One A plus one B", None],
        ["FORM-AA", "Two A", None],
    ])
    add_table(doc, "FormationSystem", [
        ("FID", "string", True), ("SID", "string", True), ("NOS", "integer", False), ("NOTE", "string", False),
    ], [
        ["FORM-AB", "TEACH-AIR-01", 1, None],
        ["FORM-AB", "TEACH-AIR-02", 1, None],
        ["FORM-AA", "TEACH-AIR-01", 2, None],
    ])
    priority = {"FORM-AB": 1, "FORM-AA": 2} if variant != "aa-high" else {"FORM-AB": 2, "FORM-AA": 1}
    add_table(doc, "MissionFormation", [
        ("MTID", "string", True), ("FID", "string", True), ("PRI", "integer", False), ("ALOAA", "string", False), ("NOTE", "string", False),
    ], [
        ["BASIC-MISSION", "FORM-AB", priority["FORM-AB"], None, None],
        ["BASIC-MISSION", "FORM-AA", priority["FORM-AA"], None, None],
    ])
    if variant == "b-missing":
        deployment = table(doc, "SystemDeployment")
        cols = [c["name"] for c in deployment["columns"]]
        deployment["instances"][0]["rows"] = [row for row in deployment["instances"][0]["rows"] if row[cols.index("SID")] != "TEACH-AIR-02"]
        unit = table(doc, "Unit")
        unit["instances"][0]["rows"][0][[c["name"] for c in unit["columns"]].index("DESCR")] = "Two deployed A aircraft; B not deployed"
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{variant}-input.json"
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError(f"frozen {variant} input differs")
        else:
            target.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
