"""Freeze two stock prelife row orders against accepted installed-LRU PM parent."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1/native-input-explicit-control.json"
PARENT_SHA = "76cd71fe989b84a8f8c5c23007926a417c8f01c820cfc534846216e4a9fe7311"
ARMS = ("age10-first", "age70-first")

def table(doc, name):
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1: raise ValueError(name)
    return matches[0]
def rows(doc, name): return table(doc, name)["instances"][0]["rows"]

def make(arm):
    if arm not in ARMS: raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA: raise ValueError("accepted parent changed")
    doc = copy.deepcopy(json.loads(raw))
    rows(doc, "ProblemDescription")[0][0] = "G11.var11 stocked LRU prelife row order; " + arm
    stock = table(doc, "StockAllocation")
    scol = [c["name"] for c in stock["columns"]]
    sr = rows(doc, "StockAllocation")
    if len(sr) != 1 or sr[0][scol.index("STSIZ")] != 1: raise ValueError("parent stock differs")
    sr[0][scol.index("STSIZ")] = 2
    sr[0][scol.index("PLID")] = "PL-STOCK"
    ctl = table(doc, "Control")
    cc = [c["name"] for c in ctl["columns"]]
    cr = rows(doc, "Control")[0]
    for key in ("SIMPE", "RCEND"):
        if key in cc: cr[cc.index(key)] = 140.0
    coll = table(doc, "ResultCollection")
    nc = [c["name"] for c in coll["columns"]]
    for r in rows(doc, "ResultCollection"):
        if "RCEND" in nc: r[nc.index("RCEND")] = 140.0
    rows(doc, "Prelife").append(["PL-STOCK", "Two initially stocked LRU ages", "TEACH-LRU-01", None])
    pair = [["PL-STOCK", "STOCK-10", 1, 10.0, None, "CALHOURS", "FIXED", None], ["PL-STOCK", "STOCK-70", 1, 70.0, None, "CALHOURS", "FIXED", None]]
    if arm == "age70-first": pair.reverse()
    rows(doc, "PrelifeData").extend(pair)
    return doc

def main():
    p = argparse.ArgumentParser();p.add_argument("--write", action="store_true");args=p.parse_args()
    result = {}
    for arm in ARMS:
        data = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists(): raise FileExistsError(path)
            path.write_bytes(data)
        elif path.read_bytes() != data: raise ValueError(f"frozen {arm} input differs")
        result[arm] = hashlib.sha256(data).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs": result}))

if __name__ == "__main__": main()
