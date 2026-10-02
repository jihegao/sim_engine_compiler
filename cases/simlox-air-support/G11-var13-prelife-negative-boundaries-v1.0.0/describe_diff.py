"""Freeze exact individual negative Prelife deltas against accepted parents."""
import hashlib
import json
from pathlib import Path
from build import ARMS,PARENTS
HERE=Path(__file__).resolve().parent;OUT=HERE/"exact-diff.json"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tables(p):return {t["name"]:t for t in json.loads(p.read_bytes())["model"]["tables"]}
def main():
    expected={"two-blank-qty":{"PrelifeData","ProblemDescription"},"overallocated-qty":{"PrelifeData","ProblemDescription"},"missing-middle":{"Prelife","PrelifeData","PrelifeStructure","ProblemDescription"}}
    arms={}
    for arm in ARMS:
        parent=PARENTS[arm][0];child=HERE/f"native-input-{arm}.json";a,b=tables(parent),tables(child)
        changed={n:{"before":a.get(n),"after":b.get(n)} for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)}
        if set(changed)!=expected[arm]:raise ValueError((arm,sorted(changed)))
        arms[arm]={"parent_sha256":sha(parent),"input_sha256":sha(child),"changed":changed}
    document={"schema":"simlox-air-support-multi-parent-exact-table-diff/v1","case_id":"G11","variant_id":"G11.var13","arms":arms}
    data=(json.dumps(document,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes()!=data:raise ValueError("frozen diff differs")
    else:OUT.write_bytes(data)
    print(json.dumps({"diff_sha256":hashlib.sha256(data).hexdigest(),"changed_tables":{a:sorted(arms[a]["changed"]) for a in ARMS}}))
if __name__=="__main__":main()
