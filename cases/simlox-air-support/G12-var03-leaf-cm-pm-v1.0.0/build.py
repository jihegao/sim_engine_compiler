"""Add direct leaf-B repair beside accepted leaf-A CAL24 PM."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "native-input.json"
PARENT_SHA = "25490c7da29019183ddc25aaed7953741bfc67261d535419941d56fc59767c7b"
OUT = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(name)
    return matches[0]


def columns(doc: dict, name: str) -> list[str]:
    return [c["name"] for c in table(doc, name)["columns"]]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def keyed(doc: dict, name: str, key: str) -> list:
    matches = [r for r in rows(doc, name) if r[0] == key]
    if len(matches) != 1:
        raise ValueError((name, key))
    return matches[0]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G12.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "ProblemDescription") != [["G12.var01 two linked subsystems with leaf calendar PM"]]:
        raise ValueError("parent description changed")
    rows(doc, "ProblemDescription")[0][0] = "G12.var03 child-B direct CM with child-A CAL24 PM"
    control = rows(doc, "Control")
    cf = columns(doc, "Control")
    if len(control) != 1 or (control[0][cf.index("NREPS")], control[0][cf.index("RSEED")],
                             control[0][cf.index("SIMPE")], control[0][cf.index("ENPM")]) != (1, "1", 60.0, "Y"):
        raise ValueError("parent control changed")
    control[0][cf.index("RSEED")] = "2"
    sf = columns(doc, "System")
    top, child_a, child_b = (keyed(doc, "System", sid) for sid in
                              ("TEACH-AIR-01", "TEACH-SUB-A", "TEACH-SUB-B"))
    if [r[sf.index("FRT")] for r in (top, child_a, child_b)] != [0, 0, 0]:
        raise ValueError("parent system rates changed")
    top[sf.index("FRT")] = None
    child_b[sf.index("FRT")] = 500000
    repair = rows(doc, "SystemRepair")
    if repair:
        raise ValueError("parent repair unexpectedly populated")
    repair.append(["TEACH-SUB-B", "BASE-01", 0.5, 0.5, 1.0, 1.0,
                   None, None, None, None, None, None, None, None, None])
    if rows(doc, "SystemStructure") != [
            ["TEACH-SUB-A", "TEACH-AIR-01", 1, 1.0, None],
            ["TEACH-SUB-B", "TEACH-AIR-01", 1, 1.0, None]]:
        raise ValueError("parent linked children changed")
    if len(rows(doc, "MaterielPM")) != 1 or len(rows(doc, "PMLocation")) != 1:
        raise ValueError("parent leaf PM changed")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(data)
    elif OUT.read_bytes() != data:
        raise ValueError("frozen native input differs")
    print(json.dumps({"variant_id": "G12.var03", "input_sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
