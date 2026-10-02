"""Freeze exact G11.var04 parent to G11.var10 ASSY/MPID inheritance delta."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1/native-input-explicit-control.json"
INPUT = HERE / "native-input-assy-inherit.json"
OUT = HERE / "exact-diff.json"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def tables(p): return {t["name"]: t for t in json.loads(p.read_bytes())["model"]["tables"]}

def main():
    before, after = tables(PARENT), tables(INPUT)
    changed = {name: {"before": before.get(name), "after": after.get(name)} for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
    expected = {"ProblemDescription", "Item", "MaterielStructure", "Prelife", "PrelifeData", "PrelifeStructure"}
    if set(changed) != expected: raise ValueError(sorted(changed))
    document = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G11", "variant_id": "G11.var10", "parent_sha256": sha(PARENT), "input_sha256": sha(INPUT), "changed": changed}
    data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != data: raise ValueError("frozen exact diff differs")
    else: OUT.write_bytes(data)
    print(json.dumps({"diff_sha256": hashlib.sha256(data).hexdigest(), "changed_tables": sorted(changed)}))

if __name__ == "__main__": main()
