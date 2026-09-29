"""Build the bounded A17 two-unit group model from accepted A03 1.0.1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PARENT_SHA256 = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} table")
    result = matches[0]
    if len(result["instances"]) != 1:
        raise ValueError(f"expected exactly one {name} instance")
    return result


def cols(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def row(t: dict, **changes: object) -> list:
    names = cols(t)
    unknown = set(changes) - set(names)
    if unknown:
        raise ValueError(f"unknown columns: {sorted(unknown)}")
    return [changes.get(name) for name in names]


def update_single(t: dict, **changes: object) -> None:
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(cols(t)):
        raise ValueError(f"unexpected {t['name']} parent rows")
    for name, value in changes.items():
        rows[0][cols(t).index(name)] = value


def add_table(model: dict, name: str, columns: list[tuple[str, str, bool]], values: list[dict]) -> None:
    if any(t["name"] == name for t in model["tables"]):
        raise ValueError(f"{name} already present in parent")
    metadata = []
    for field, dtype, is_key in columns:
        column = {"datatype": dtype}
        if is_key:
            column["key"] = True
        column["name"] = field
        metadata.append(column)
    template = {"columns": metadata, "instances": [{"instance_name": "", "rows": []}], "name": name}
    template["instances"][0]["rows"] = [row(template, **values_for_row) for values_for_row in values]
    model["tables"].append(template)


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted A03 parent input fingerprint differs")
    document = copy.deepcopy(json.loads(raw))
    model = document["model"]

    station = table(model, "Station")
    parent_station = station["instances"][0]["rows"]
    if len(parent_station) != 1:
        raise ValueError("unexpected parent Station rows")
    station["instances"][0]["rows"].append(row(station, STID="BASE-02", DESCR="Second teaching base", QTY=1, TYPE="WS"))

    unit = table(model, "Unit")
    update_single(unit, DESCR="First one-aircraft teaching unit")
    unit["instances"][0]["rows"].append(row(unit, UNID="TEACH-UNIT-2", DESCR="Second one-aircraft teaching unit", STID="BASE-02"))

    deployment = table(model, "SystemDeployment")
    update_single(deployment, QTYPS=1)
    deployment["instances"][0]["rows"].append(row(deployment, SID="TEACH-AIR-01", USTID="TEACH-UNIT-2", QTYPS=1, UTIL=1))

    update_single(table(model, "Operations"), USTID="TEACH-GROUP")
    update_single(table(model, "ProblemDescription"), PDESC="A17 two explicit units at two bases serving one group mission; no transfer")

    add_table(model, "UnitGroup", [
        ("UGID", "string", True), ("DESCR", "string", False),
        ("UNPR1", "string", False), ("NOTE", "string", False),
    ], [{"UGID": "TEACH-GROUP", "DESCR": "Two-unit teaching group", "UNPR1": "N"}])
    add_table(model, "UnitGroupMember", [
        ("UGID", "string", True), ("USTID", "string", True),
        ("PRI", "integer", False), ("XTIME", "double", False),
        ("NOTE", "string", False),
    ], [
        {"UGID": "TEACH-GROUP", "USTID": "TEACH-UNIT", "PRI": 1, "XTIME": 0.0},
        {"UGID": "TEACH-GROUP", "USTID": "TEACH-UNIT-2", "PRI": 2, "XTIME": 0.0},
    ])
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUTPUT}")
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("checked A17 input differs from pinned generator output")
    print(json.dumps({"case_id": "A17", "variant": "two-explicit-units-group", "input_sha256": sha(raw), "bytes": len(raw), "parent_sha256": PARENT_SHA256}))


if __name__ == "__main__":
    main()
