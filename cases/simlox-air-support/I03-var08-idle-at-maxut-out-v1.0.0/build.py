"""Deterministic I03.var08 source delta. Default invocation reads only."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C08-exact-limit-v1.0.0" / "exact-limit-input.json"
CONTRACT = HERE / "contract.json"
CHILD = HERE / "native-input.json"
DIFF = HERE / "exact-diff.json"
PARENT_SHA = "dc75e99a8007fe74c7a830633657c32957877b9eb0a162588f7dedc6bc1f428b"
CONTRACT_SHA = "f23c6284afdaf25c7115f293907411ab941c0603b11d8bbf45d7fd8a5e671b41"

def pin(b: bytes) -> dict:
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}

def strict_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise AssertionError(f"duplicate JSON key {k}")
        out[k] = v
    return out

def reject_constant(x):
    raise AssertionError(f"nonfinite JSON constant {x}")

def finite(x):
    if isinstance(x, float):
        import math
        assert math.isfinite(x)
    elif isinstance(x, dict):
        for v in x.values(): finite(v)
    elif isinstance(x, list):
        for v in x: finite(v)

def parse(b: bytes):
    x = json.loads(b.decode("utf-8-sig"), object_pairs_hook=strict_pairs, parse_constant=reject_constant)
    finite(x)
    return x

def typed_equal(a, b):
    if type(a) is not type(b): return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
    return a == b

def topology(model):
    ts = model["tables"]
    assert len({t["name"] for t in ts}) == len(ts)
    rows = 0; cells = 0; empty = {}
    for t in ts:
        assert set(t) == {"name","columns","instances"}
        assert len(t["instances"]) == 1
        assert len({c["name"] for c in t["columns"]}) == len(t["columns"])
        inst = t["instances"][0]
        assert inst["instance_name"] == ""
        if not inst["rows"]: empty[t["name"]] = len(t["columns"])
        for row in inst["rows"]:
            assert len(row) == len(t["columns"])
            rows += 1; cells += len(row)
    return {"tables":len(ts),"rows":rows,"cells":cells,"empty_table_widths":empty}

def construct(parent, contract):
    d = contract["source_delta"]
    assert set(parent) == {"model"}
    original = parent["model"]
    assert set(original) == {"database_version","tables"}
    assert original["database_version"] == 20160627
    assert topology(original) == {"tables":35,"rows":27,"cells":235,
                                   "empty_table_widths":contract["lineage"]["parent"]["authored"]["empty_table_widths"]}
    assert all(t["name"] != "ResourceTransfer" for t in original["tables"])
    result = copy.deepcopy(parent)
    ts = result["model"]["tables"]
    assert ts[0]["name"] == "ProblemDescription"
    p = ts[0]
    assert p["columns"] == [{"name":"PDESC","datatype":"string"}]
    assert p["instances"] == [{"instance_name":"","rows":[[d["old_pdesc"]]]}]
    p["instances"][0]["rows"][0][0] = d["new_pdesc"]
    pos = d["insert_at_zero_based_index"]
    assert pos == 23 and ts[pos-1]["name"] == d["insert_after"] and ts[pos]["name"] == d["insert_before"]
    new_table = {"name":d["insert_table"],"columns":d["columns"],
                 "instances":[{"instance_name":d["instance_name"],"rows":[d["one_row"]]}]}
    assert new_table["columns"] == [
        {"name":"STFID","datatype":"string","key":True},
        {"name":"STTID","datatype":"string","key":True},
        {"name":"RID","datatype":"string","key":True},
        {"name":"TFTIME","datatype":"double","key":True},
        {"name":"TFQTY","datatype":"integer"},
        {"name":"TFDT","datatype":"double"},
        {"name":"NOTE","datatype":"string"}]
    assert new_table["instances"][0]["rows"] == [["BASE-01","<OUTSIDE>","P-CREW",24.75,1,0.0,None]]
    ts.insert(pos,new_table)
    assert topology(result["model"]) == {"tables":36,"rows":28,"cells":242,
                                         "empty_table_widths":topology(original)["empty_table_widths"]}
    for i,t in enumerate(original["tables"]):
        new = ts[i if i < pos else i+1]
        if i == 0:
            old_copy = copy.deepcopy(t)
            old_copy["instances"][0]["rows"][0][0] = d["new_pdesc"]
            assert typed_equal(new,old_copy)
        else:
            assert typed_equal(new,t), (i,t["name"])
    return result

def make_diff(parent, child):
    before=parent["model"]["tables"]; after=child["model"]["tables"]; pos=23
    assert len(before)==35 and len(after)==36
    return {"schema":"i03-var08-exact-source-diff/v1","parent":pin(PARENT.read_bytes()),
            "contract":pin(CONTRACT.read_bytes()),"child_authored_topology":topology(child["model"]),
            "changed_existing_cell":{"table":"ProblemDescription","row":0,"column":"PDESC",
                                     "before":before[0]["instances"][0]["rows"][0][0],
                                     "after":after[0]["instances"][0]["rows"][0][0]},
            "inserted_table":{"index":pos,"table":after[pos]},
            "all_other_existing_tables_metadata_and_cells_type_exact":True}

def emit(path: Path, body: bytes, write: bool):
    if path.exists():
        assert path.read_bytes() == body, f"existing {path.name} differs"
    elif write:
        with path.open("xb") as f: f.write(body)
    return {"path":path.name,**pin(body),"exists":path.exists()}

def run(write=False):
    pb=PARENT.read_bytes();cb=CONTRACT.read_bytes()
    assert hashlib.sha256(pb).hexdigest()==PARENT_SHA
    assert hashlib.sha256(cb).hexdigest()==CONTRACT_SHA
    parent=parse(pb); contract=parse(cb)
    assert contract["schema"]=="simlox-i03-var08-prospective-contract-design/v2"
    child=construct(parent,contract)
    child_bytes=(json.dumps(child,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    diff_bytes=(json.dumps(make_diff(parent,child),ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    return {"schema":"i03-var08-build/v1","input":emit(CHILD,child_bytes,write),
            "diff":emit(DIFF,diff_bytes,write),"native_calls":0}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--write",action="store_true")
    print(json.dumps(run(ap.parse_args().write),sort_keys=True))

