"""Add a second RANDOM age dimension, then override the base calendar age."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/"G11-var03-random-system-prelife-v1.0.0/native-input-random-seed1.json"
PARENT_SHA="6984ce91a40a1a0c491ff7eeda4b808c314d50577ec008d1d9f65780acfac512"
ARMS=("added-ophours","calendar-override")

def make(arm):
    if arm not in ARMS:raise ValueError(arm)
    data=PARENT.read_bytes()
    if hashlib.sha256(data).hexdigest()!=PARENT_SHA:raise ValueError("accepted parent changed")
    doc=copy.deepcopy(json.loads(data));tables=doc["model"]["tables"]
    if any(t["name"]=="PrelifeDataAge" for t in tables):raise ValueError("parent already has age override")
    pdesc=next(t for t in tables if t["name"]=="ProblemDescription")
    pdesc["instances"][0]["rows"][0][0]="G11.var12 seeded multi-OPID RANDOM ages; "+arm
    pdata=next(t for t in tables if t["name"]=="PrelifeData")["instances"][0]["rows"]
    if pdata!=[["PL-SYS","RND-0-120",3,120.0,0.0,"CALHOURS","RANDOM",None]]:raise ValueError("parent RANDOM row changed")
    rows=[["PL-SYS","RND-0-120","OPHOURS",60.0,0.0,None]]
    if arm=="calendar-override":rows.append(["PL-SYS","RND-0-120","CALHOURS",90.0,0.0,None])
    age={"columns":[{"datatype":"string","key":True,"name":"PLID"},{"datatype":"string","key":True,"name":"PLIND"},{"datatype":"string","key":True,"name":"OPID"},{"datatype":"double","name":"AGE"},{"datatype":"double","name":"AGEMIN"},{"datatype":"string","name":"NOTE"}],"instances":[{"instance_name":"","rows":rows}],"name":"PrelifeDataAge"}
    i=next(i for i,t in enumerate(tables) if t["name"]=="PrelifeData")
    tables.insert(i+1,age)
    return doc

def main():
    p=argparse.ArgumentParser();p.add_argument("--write",action="store_true");args=p.parse_args();result={}
    for arm in ARMS:
        data=(json.dumps(make(arm),ensure_ascii=False,indent=2)+"\n").encode("utf-8")
        path=HERE/f"native-input-{arm}.json"
        if args.write:
            if path.exists():raise FileExistsError(path)
            path.write_bytes(data)
        elif path.read_bytes()!=data:raise ValueError(f"frozen {arm} input differs")
        result[arm]=hashlib.sha256(data).hexdigest()
    print(json.dumps({"parent_sha256":PARENT_SHA,"inputs":result}))
if __name__=="__main__":main()
