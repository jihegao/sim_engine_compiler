"""Assign one POS-B noncritical-set member only to BASIC's series mode."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G09-var01-mission-rbd-v1.0.0" / "mixed-input.json"
PARENT_SHA = "62e48b3eae86e0713e0a5c641ec28dddc3cc3cd81dc99be2659ceeee2f63475b"
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


def make() -> dict:
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
        raise ValueError("parent mission mode mappings changed")
    if rows(doc, "MaterielOperationalModes")[-1] != ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", None, 1.0, None]:
        raise ValueError("parent series mode changed")
    if rows(doc, "MaterielStructure")[1] != ["POS-B", "TEACH-AIR-01", 1, 1.0, None, None]:
        raise ValueError("parent physical B changed")
    if rows(doc, "RBDSeriesStructure") != [
        ["G09-SER-RBD", "POS-A", "G04-OPS", 1, None],
        ["G09-SER-RBD", "POS-B", "G04-OPS", 1, None],
    ]:
        raise ValueError("parent series structure changed")
    rows(doc, "ProblemDescription")[0][0] = "G09.var03 BASIC series POS-B noncritical set QTYNC1"
    rows(doc, "MaterielOperationalModes")[-1][3] = SET
    tables = doc["model"]["tables"]
    at = next(i for i, t in enumerate(tables) if t["name"] == "RBDSeries")
    tables.insert(at, table("RBDNonCriticalSet", [column("NCID", "string", True),
        column("DESCR", "string"), column("NOTE", "string")],
        [[SET, "One POS-B member noncritical in BASIC series", None]]))
    tables.insert(at + 1, table("RBDNonCriticalSetItems", [column("NCID", "string", True),
        column("MID", "string", True), column("QTYNC", "integer"),
        column("USERT", "double"), column("NOTE", "string")],
        [[SET, "POS-B", 1, 1.0, None]]))
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "nc-b1-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
