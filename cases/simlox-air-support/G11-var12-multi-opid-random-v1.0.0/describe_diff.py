"""Freeze parent delta and pairwise stock PrelifeData row-order contrast."""
import hashlib
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var03-random-system-prelife-v1.0.0/native-input-random-seed1.json"
ARMS = ("added-ophours", "calendar-override")
OUT = HERE / "exact-diff.json"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def tables(p): return {t["name"]:t for t in json.loads(p.read_bytes())["model"]["tables"]}
def compare(a,b): return {n:{"before":a.get(n),"after":b.get(n)} for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)}
def main():
    parent=tables(PARENT);paths={arm:HERE/f"native-input-{arm}.json" for arm in ARMS};arms={arm:tables(p) for arm,p in paths.items()}
    contrast=compare(arms[ARMS[0]],arms[ARMS[1]])
    if set(contrast)!={"PrelifeDataAge","ProblemDescription"}:raise ValueError(sorted(contrast))
    doc={"schema":"simlox-air-support-exact-table-diff/v1","case_id":"G11","variant_id":"G11.var12","parent_sha256":sha(PARENT),"arms":{arm:{"input_sha256":sha(path),"changed":compare(parent,arms[arm])} for arm,path in paths.items()},"arm_contrast":contrast}
    data=(json.dumps(doc,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes()!=data:raise ValueError("frozen diff differs")
    else:OUT.write_bytes(data)
    print(json.dumps({"diff_sha256":hashlib.sha256(data).hexdigest(),"arm_contrast_tables":sorted(contrast),"parent_changed_tables":{a:sorted(doc["arms"][a]["changed"]) for a in ARMS}}))
if __name__=="__main__":main()
