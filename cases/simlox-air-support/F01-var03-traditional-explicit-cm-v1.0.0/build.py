"""Freeze a traditional/explicit CM pair from accepted F01.var01 and D06."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "F01-var01-two-three-level-v1.0.1/three-level-input.json"
PARENT_SHA = "ae0181581822422aaf3c8bc5b7c0352c8bf31187178408e4f211102e438c77b5"
D06 = ROOT / "D06-explicit-position-direct-repair-v1.0.0/native-input.json"
D06_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name}")
    return found[0]


def col(table: dict, name: str) -> int:
    return [c["name"] for c in table["columns"]].index(name)


def make_table(name: str, specs: list[tuple[str, str, bool]], rows: list[list[object]]) -> dict:
    columns = [{"datatype": typ, **({"key": True} if key else {}), "name": field}
               for field, typ, key in specs]
    if any(len(row) != len(columns) for row in rows):
        raise ValueError(f"nonrectangular {name}")
    return {"columns": columns, "instances": [{"instance_name": "", "rows": rows}], "name": name}


def build() -> dict:
    if digest(PARENT) != PARENT_SHA or digest(D06) != D06_SHA:
        raise ValueError("accepted source fingerprint differs")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    d06 = json.loads(D06.read_text(encoding="utf-8"))
    tables = doc["model"]["tables"]
    get_table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = "F01.var03 explicit FM on SRU with nested LRU and SRU CM replacements"
    system = get_table(doc, "System")
    system["instances"][0]["rows"][0][col(system, "FRT")] = None
    item = get_table(doc, "Item")
    for row in item["instances"][0]["rows"]:
        row[col(item, "FRT")] = None
    for name in ("ItemStructure", "SystemRepair", "ItemRepair", "ItemReplacement"):
        get_table(doc, name)["instances"][0]["rows"] = []
    reference = get_table(d06, "FailureMode")
    fm = copy.deepcopy(reference)
    fm["instances"][0]["rows"] = [["FM-SRU", "Nested SRU failure", "TEACH-SRU-01",
                                      1200000.0, "OPHOURS", 1.0, None, None, None]]
    tables.append(fm)
    ms = get_table(d06, "MaterielStructure")
    ms = copy.deepcopy(ms)
    ms["instances"][0]["rows"] = [
        ["TEACH-LRU-01", "TEACH-AIR-01", 1, 1.0, None, None],
        ["TEACH-SRU-01", "TEACH-LRU-01", 1, 1.0, None, None],
    ]
    tables.append(ms)
    cm = copy.deepcopy(get_table(d06, "CMLocation"))
    cm["instances"][0]["rows"] = [
        ["FM-SRU", "TEACH-AIR-01", "BASE-01", 0.5, None, None, 1.0, "E01-SURP", None, None],
        ["FM-SRU", "TEACH-LRU-01", "BASE-01", 0.75, None, None, 1.0, None, None, None],
        ["FM-SRU", "TEACH-SRU-01", "BASE-01", 1.0, None, None, 1.0, None, None, None],
    ]
    tables.append(cm)
    tables.append(make_table("CMReplacement", [
        ("FMID", "string", True), ("MID", "string", True), ("IID", "string", True),
        ("CMRF", "double", False), ("CMRQ", "double", False),
        ("CMRQD", "string", False), ("DISC", "double", False), ("NOTE", "string", False),
    ], [
        ["FM-SRU", "TEACH-AIR-01", "TEACH-LRU-01", 1.0, 1.0, None, None, None],
        ["FM-SRU", "TEACH-LRU-01", "TEACH-SRU-01", 1.0, 1.0, None, None, None],
    ]))
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "explicit-input.json"
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen explicit input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "explicit_input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
