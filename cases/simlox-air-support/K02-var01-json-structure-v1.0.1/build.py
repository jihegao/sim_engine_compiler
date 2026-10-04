"""Build two isolated JSON-structure probes from accepted K01.var04."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K01-var04-parent-child-model-diff-v1.0.0" / "native-input.json"
PARENT_SHA = "d1ff80f7e0de8259b6f38b6373c7ad4797d897e17c4397a7060dfbefbeb851dc"


def build(arm):
    assert arm in ("inactive2", "named")
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA
    doc = json.loads(raw)
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(tables) == len(doc["model"]["tables"]) == 31
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert description == ["K01.var04 v1.0.0 A01-derived three-hour model comparison"]
    description[0] = f"K02.var01 v1.0.1 JSON {arm} probe"
    station = tables["Station"]
    names = [c["name"] for c in station["columns"]]
    assert len(station["instances"]) == 1 and names[:4] == ["STID", "DESCR", "QTY", "TYPE"]
    default = station["instances"][0]
    assert default["instance_name"] == "" and len(default["rows"]) == 1
    parent_row = default["rows"][0]
    assert len(parent_row) == 21 and parent_row[:4] == ["BASE-01", "Teaching base", 1, "WS"]
    if arm == "inactive2":
        inactive = parent_row.copy()
        inactive[:2] = ["K02-INACTIVE", "Unused inactive station"]
        default["rows"].append(inactive)
        default["inactive_rows"] = [2]
    else:
        default["instance_name"] = "K02-BASE"
        named = parent_row.copy()
        named[:2] = ["K02-NAMED", "Unused named-instance station"]
        station["instances"].append({"instance_name": "K02-AUX", "rows": [named]})
    op = tables["OperationProfile"]["instances"][0]["rows"][0]
    op_names = [c["name"] for c in tables["OperationProfile"]["columns"]]
    assert op[op_names.index("DTIM")] == 0.3333333333333333
    return doc


if __name__ == "__main__":
    outputs = {}
    for arm in ("inactive2", "named"):
        raw = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{arm}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, "frozen source changed"
        else:
            path.write_bytes(raw)
        outputs[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs_sha256": outputs}))
