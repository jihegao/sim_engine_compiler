"""Compare an omitted POS-B series member without and with NCID QTYNC1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G09-var01-mission-rbd-v1.0.0" / "mixed-input.json"
PARENT_SHA = "62e48b3eae86e0713e0a5c641ec28dddc3cc3cd81dc99be2659ceeee2f63475b"
ARMS = ("omitted-control", "omitted-nc-b1")
SET = "G09-NC-B"


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def column(name: str, datatype: str, key: bool = False) -> dict:
    result = {"datatype": datatype}
    if key:
        result["key"] = True
    result["name"] = name
    return result


def table(name: str, columns: list[dict], body: list[list]) -> dict:
    return {"name": name, "columns": columns, "instances": [{"instance_name": "", "rows": body}]}


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted mixed parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if any(t["name"] in ("RBDNonCriticalSet", "RBDNonCriticalSetItems") for t in doc["model"]["tables"]):
        raise ValueError("parent already contains noncritical-set tables")
    if rows(doc, "MissionOperationalModes") != [
        ["BASIC-MISSION", "TEACH-AIR-01", "G09-SER-OPS", None],
        ["PAR-MISSION", "TEACH-AIR-01", "G04-OPS", None],
    ]:
        raise ValueError("parent mission mappings changed")
    mode = rows(doc, "MaterielOperationalModes")[-1]
    if mode != ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", None, 1.0, None]:
        raise ValueError("parent BASIC system mode changed")
    if rows(doc, "MaterielStructure")[1] != ["POS-B", "TEACH-AIR-01", 1, 1.0, None, None]:
        raise ValueError("parent B physical structure changed")
    series = rows(doc, "RBDSeriesStructure")
    if series != [["G09-SER-RBD", "POS-A", "G04-OPS", 1, None],
                  ["G09-SER-RBD", "POS-B", "G04-OPS", 1, None]]:
        raise ValueError("parent series rows changed")
    rows(doc, "ProblemDescription")[0][0] = f"G09.var03 {arm}: omitted POS-B NCID contrast"
    series.pop()  # p196: omitted physical position is in series with selected RBD
    if arm == "omitted-nc-b1":
        mode[3] = SET
        tables = doc["model"]["tables"]
        at = next(i for i, t in enumerate(tables) if t["name"] == "RBDSeries")
        tables.insert(at, table("RBDNonCriticalSet", [column("NCID", "string", True),
            column("DESCR", "string"), column("NOTE", "string")],
            [[SET, "One POS-B member noncritical in BASIC default series", None]]))
        tables.insert(at + 1, table("RBDNonCriticalSetItems", [column("NCID", "string", True),
            column("MID", "string", True), column("QTYNC", "integer"),
            column("USERT", "double"), column("NOTE", "string")],
            [[SET, "POS-B", 1, 1.0, None]]))
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
