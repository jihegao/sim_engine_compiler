"""Build paired A14 DTTOL boundaries from accepted A05 prepared-spare input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-var02-prepared-spare-probe-v1.0.0" / "native-input.json"
PARENT_SHA = "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d"
SCHEMA_SOURCE = HERE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
SCHEMA_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"
VARIANTS = {"control": None, "zero": 0.0, "below": 0.49, "edge": 0.5, "above": 0.51}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tab(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name}")
    return found[0]


def first(table: dict) -> list:
    rows = table["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"expected one row: {table['name']}")
    return rows[0]


def change(table: dict, record: list, field: str, before: object, after: object) -> None:
    idx = [c["name"] for c in table["columns"]].index(field)
    if record[idx] != before:
        raise ValueError(f"unexpected {table['name']}.{field}: {record[idx]!r}")
    record[idx] = after


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA or sha(SCHEMA_SOURCE.read_bytes()) != SCHEMA_SHA:
        raise ValueError("accepted A05 prepared-spare parent changed")
    doc = copy.deepcopy(json.loads(raw))
    t = tab(doc, "ProblemDescription")
    change(t, first(t), "PDESC", "A05 continuous four-hour three-aircraft fixed-preparation probe",
           f"A14 typed SUPPORT gap, EXECUTE dependence DTTOL {variant}")
    t = tab(doc, "System")
    aircraft = first(t)
    execute_aircraft = copy.deepcopy(aircraft)
    change(t, execute_aircraft, "SID", "TEACH-AIR-01", "EXEC-AIR-01")
    change(t, execute_aircraft, "DESCR", "Generic teaching aircraft", "Nonfailing execution aircraft")
    change(t, execute_aircraft, "FRT", 300000, 0)
    t["instances"][0]["rows"].append(execute_aircraft)
    t = tab(doc, "SystemDeployment")
    support_deployment = first(t)
    execute_deployment = copy.deepcopy(support_deployment)
    change(t, execute_deployment, "SID", "TEACH-AIR-01", "EXEC-AIR-01")
    change(t, execute_deployment, "QTYPS", 3, 1)
    t["instances"][0]["rows"].append(execute_deployment)
    t = tab(doc, "Unit")
    change(t, first(t), "DESCR", "Three-aircraft teaching unit", "Four-aircraft dependence unit")
    t = tab(doc, "MissionType")
    support = first(t)
    change(t, support, "MTID", "BASIC-MISSION", "SUPPORT")
    change(t, support, "DESCR", "Four-hour teaching mission", "Four-hour two-aircraft continuous support")
    execute = copy.deepcopy(support)
    change(t, execute, "MTID", "SUPPORT", "EXECUTE")
    change(t, execute, "DESCR", "Four-hour two-aircraft continuous support",
           "3.9-hour one-aircraft continuous execution")
    change(t, execute, "NOS", 2, 1)
    change(t, execute, "MNOS", 2, 1)
    change(t, execute, "DURN", 4.0, 3.9)
    t["instances"][0]["rows"] = [support, execute]
    t = tab(doc, "OperationProfile")
    support = first(t)
    change(t, support, "SPRID", "BASIC-MISSION", "SUPPORT")
    execute = copy.deepcopy(support)
    change(t, execute, "SPRID", "SUPPORT", "EXECUTE")
    t["instances"][0]["rows"] = [support, execute]
    t = tab(doc, "MissionPreparation")
    change(t, first(t), "MTID", "BASIC-MISSION", "SUPPORT")
    t = tab(doc, "Tasks")
    change(t, first(t), "DESCR", "Fixed 30-minute BASIC-MISSION preparation",
           "Fixed 30-minute SUPPORT preparation")
    names = ["MTID", "SID", "PRI", "NOS", "MNOS", "MNOSA", "NOTE"]
    types = ["string", "string", "integer", "integer", "integer", "integer", "string"]
    mission_system = {
        "name": "MissionSystem",
        "columns": [{"name": n, "datatype": ty, **({"key": True} if i < 2 else {})}
                    for i, (n, ty) in enumerate(zip(names, types))],
        "instances": [{"instance_name": "", "rows": [
            ["SUPPORT", "TEACH-AIR-01", 1, 2, 2, None, "two failing support aircraft"],
            ["EXECUTE", "EXEC-AIR-01", 1, 1, 1, None, "one nonfailing execution aircraft"],
        ]}],
    }
    donor = json.loads(SCHEMA_SOURCE.read_bytes())
    donor_schema = next(t["columns"] for t in donor["model"]["tables"] if t["name"] == "MissionSystem")
    if mission_system["columns"] != donor_schema:
        raise ValueError("accepted A11 MissionSystem schema changed")
    doc["model"]["tables"].append(mission_system)
    if variant != "control":
        names = ["DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE", "MUTD", "DTTOL", "NOTE"]
        types = ["string", "string", "double", "string", "string", "double", "string", "string", "double", "string"]
        doc["model"]["tables"].append({
            "name": "MissionDependence",
            "columns": [{"name": n, "datatype": ty, **({"key": True} if i < 6 else {})}
                        for i, (n, ty) in enumerate(zip(names, types))],
            "instances": [{"instance_name": "", "rows": [[
                "TEACH-UNIT", "EXECUTE", 8.0, "TEACH-UNIT", "SUPPORT", 8.0,
                "CONTINUOUS", "N", VARIANTS[variant], None]]}],
        })
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        out = HERE / f"{variant}-input.json"
        if out.exists():
            if out.read_bytes() != raw:
                raise ValueError(f"frozen input changed: {variant}")
        else:
            out.write_bytes(raw)
        print(variant, sha(raw))


if __name__ == "__main__":
    main()
