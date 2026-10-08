"""Full 36-table authored/native roundtrip check. Read-only except stdout."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys
from build import parse, typed_equal, topology

HERE=Path(__file__).resolve().parent
INPUT_SHA="38a2b5c0e7f75ec477557e87c200424cdabc859e11c9e5db3ca15ecaace4bb05"
SCHEMA="i03-var08-idle-maxut-roundtrip/v1"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def row_equal(columns,authored,exported):
    if len(authored)!=len(exported):return False
    for arow,erow in zip(authored,exported):
        if len(arow)!=len(columns) or len(erow)!=len(columns):return False
        for col,a,e in zip(columns,arow,erow):
            dt=col["datatype"]
            if a is None:
                if e is not None:return False
            elif dt=="double":
                if type(a) not in (int,float) or type(e) not in (int,float) or not math.isfinite(e) or a!=e:return False
            elif not typed_equal(a,e):return False
    return True

def check(run:Path):
    assert digest(HERE/"native-input.json")==digest(run/"input.json")==INPUT_SHA
    authored=parse((HERE/"native-input.json").read_bytes())
    exported=parse((run/"roundtrip-raw.json").read_bytes())
    assert set(authored)==set(exported)=={"model"}
    am,em=authored["model"],exported["model"]
    assert set(am)==set(em)=={"database_version","tables"}
    assert type(am["database_version"]) is int and typed_equal(am["database_version"],em["database_version"])
    assert am["database_version"]==20160627
    at,et=am["tables"],em["tables"]
    assert topology(am)["tables"]==topology(em)["tables"]==36
    assert [x["name"] for x in at]==[x["name"] for x in et]
    assert at[23]["name"]==et[23]["name"]=="ResourceTransfer"
    placeholders={}
    for a,e in zip(at,et):
        assert set(a)==set(e)=={"name","columns","instances"}
        assert typed_equal(a["columns"],e["columns"]),(a["name"],"columns")
        assert len(a["instances"])==len(e["instances"])==1
        ai,ei=a["instances"][0],e["instances"][0]
        assert set(ai)==set(ei)=={"instance_name","rows"}
        assert typed_equal(ai["instance_name"],ei["instance_name"])
        if ai["rows"]:
            assert row_equal(a["columns"],ai["rows"],ei["rows"]),(a["name"],"rows")
        else:
            placeholders[a["name"]]=len(a["columns"])
            assert ei["rows"]==[[None]*len(a["columns"])],a["name"]
    assert placeholders=={
        "Item":29,"ItemStructure":9,"StationStructure":11,"SystemRepair":15,
        "ItemRepair":16,"ItemReorder":11,"TaskResource":8,"MaterielPM":14,
        "PMLocation":9,"StockAllocation":9,"ItemReplacement":10}
    assert topology(am)=={"tables":36,"rows":28,"cells":242,"empty_table_widths":placeholders}
    assert topology(em)=={"tables":36,"rows":39,"cells":383,"empty_table_widths":{}}
    for name,marker in (("import.log","Import completed!"),("export.log","Export completed!")):
        assert marker in (run/name).read_text(encoding="utf-8-sig",errors="strict")
    return {"schema":SCHEMA,"passed":True,"issues":[],"input_sha256":INPUT_SHA,
            "export_sha256":digest(run/"roundtrip-raw.json"),"tables":36,
            "authored_rows":28,"exported_rows":39,"authored_cells":242,"exported_cells":383,
            "all_null_placeholder_tables":11}

if __name__=="__main__":
    try:
        assert len(sys.argv)==2
        result=check(Path(sys.argv[1]))
    except Exception as exc:
        result={"schema":SCHEMA,"passed":False,"issues":[f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result,separators=(",",":")))
    sys.exit(0 if result["passed"] else 1)
