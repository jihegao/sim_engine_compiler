"""Freeze three independent Prelife input-rejection probes from accepted parents."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PARENTS={
 "two-blank-qty":(ROOT/"G11-var05-remaining-qty-system-prelife-v1.0.0/native-input-remaining-blank.json","056728b5db95e06d5152337c4ec4b706cc8c69981bb094fd4f8f85102875be71"),
 "overallocated-qty":(ROOT/"G11-var05-remaining-qty-system-prelife-v1.0.0/native-input-explicit-two.json","afd693a6609c2454b3ec71a1f663791b61a932831720070d164d371c6aff9be2"),
 "missing-middle":(ROOT/"G11-var04-inherit-item-prelife-v1.0.1/native-input-explicit-control.json","76cd71fe989b84a8f8c5c23007926a417c8f01c820cfc534846216e4a9fe7311"),
}
ARMS=tuple(PARENTS)
def rows(doc,name):
    ts=[t for t in doc["model"]["tables"] if t["name"]==name]
    if len(ts)!=1 or len(ts[0]["instances"])!=1:raise ValueError(name)
    return ts[0]["instances"][0]["rows"]
def make(arm):
    if arm not in ARMS:raise ValueError(arm)
    path,digest=PARENTS[arm];raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError("accepted parent changed")
    doc=copy.deepcopy(json.loads(raw));rows(doc,"ProblemDescription")[0][0]="G11.var13 prelife negative boundary; "+arm
    if arm=="two-blank-qty":
        pdata=rows(doc,"PrelifeData")
        if [r[2] for r in pdata]!=[1,1,None]:raise ValueError("remaining parent QTY changed")
        pdata[1][2]=None
    elif arm=="overallocated-qty":
        pdata=rows(doc,"PrelifeData")
        if [r[2] for r in pdata]!=[1,1,2]:raise ValueError("explicit parent QTY changed")
        pdata[2][2]=3
    else:
        prelife,pdata,structure=(rows(doc,n) for n in ("Prelife","PrelifeData","PrelifeStructure"))
        if [r[0] for r in prelife]!=["PL-SYS","PL-POS","PL-LRU"] or [r[0] for r in pdata]!=["PL-SYS","PL-POS","PL-LRU"] or structure!=[["PL-POS","PL-SYS","SYS-60",None],["PL-LRU","PL-POS","POS-INH",None]]:raise ValueError("installed parent prelife changed")
        prelife.pop(1);pdata.pop(1);structure.pop(0);structure[0][1:3]=["PL-SYS","SYS-60"]
    return doc
def main():
    p=argparse.ArgumentParser();p.add_argument("--write",action="store_true");args=p.parse_args();out={}
    for arm in ARMS:
        data=(json.dumps(make(arm),ensure_ascii=False,indent=2)+"\n").encode("utf-8");path=HERE/f"native-input-{arm}.json"
        if args.write:
            if path.exists():raise FileExistsError(path)
            path.write_bytes(data)
        elif path.read_bytes()!=data:raise ValueError(f"frozen {arm} input differs")
        out[arm]=hashlib.sha256(data).hexdigest()
    print(json.dumps({"variant_id":"G11.var13","inputs":out}))
if __name__=="__main__":main()
