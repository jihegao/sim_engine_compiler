"""Insert an inherited ASSY above the accepted inherited MPID and fixed-age LRU."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1/native-input-explicit-control.json"
PARENT_SHA = "76cd71fe989b84a8f8c5c23007926a417c8f01c820cfc534846216e4a9fe7311"

def table(doc, name):
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1: raise ValueError(name)
    return matches[0]

def rows(doc, name): return table(doc, name)["instances"][0]["rows"]

def make():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA: raise ValueError("accepted parent changed")
    doc = copy.deepcopy(json.loads(raw))
    rows(doc, "ProblemDescription")[0][0] = "G11.var10 inherited ASSY and MPID above fixed-age LRU"
    item = table(doc, "Item")
    cols = [c["name"] for c in item["columns"]]
    assy = [None] * len(cols)
    for name, value in {"IID": "TEACH-ASSY-01", "DESCR": "Structural inherited-age assembly", "TYPE": "ASSY"}.items(): assy[cols.index(name)] = value
    rows(doc, "Item").append(assy)
    physical = rows(doc, "MaterielStructure")
    if physical != [["POS-A", "TEACH-AIR-01", 1, 1.0, None, None], ["TEACH-LRU-01", "POS-A", 1, 1.0, None, None]]: raise ValueError("parent physical structure changed")
    physical[0][1] = "TEACH-ASSY-01"
    physical.insert(0, ["TEACH-ASSY-01", "TEACH-AIR-01", 1, 1.0, None, None])
    prelife = rows(doc, "Prelife")
    if [r[0] for r in prelife] != ["PL-SYS", "PL-POS", "PL-LRU"]: raise ValueError("parent prelife IDs changed")
    prelife.insert(1, ["PL-ASSY", "Assembly inherits system", "TEACH-ASSY-01", None])
    pdata = rows(doc, "PrelifeData")
    if [(r[0], r[1], r[6]) for r in pdata] != [("PL-SYS", "SYS-60", "FIXED"), ("PL-POS", "POS-INH", "INHERIT"), ("PL-LRU", "LRU-20", "FIXED")]: raise ValueError("parent ages changed")
    pdata.insert(1, ["PL-ASSY", "ASSY-INH", 1, 0.0, None, "CALHOURS", "INHERIT", None])
    structure = rows(doc, "PrelifeStructure")
    if structure != [["PL-POS", "PL-SYS", "SYS-60", None], ["PL-LRU", "PL-POS", "POS-INH", None]]: raise ValueError("parent PrelifeStructure changed")
    structure[0][1:3] = ["PL-ASSY", "ASSY-INH"]
    structure.insert(0, ["PL-ASSY", "PL-SYS", "SYS-60", None])
    return doc

def main():
    p = argparse.ArgumentParser();p.add_argument("--write", action="store_true");args=p.parse_args()
    data = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "native-input-assy-inherit.json"
    if args.write:
        if path.exists(): raise FileExistsError(path)
        path.write_bytes(data)
    elif path.read_bytes() != data: raise ValueError("frozen input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__": main()
