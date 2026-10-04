"""Freeze a one-row Access database runtime include from accepted K02."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K02-var01-json-structure-v1.0.1" / "named-input.json"
PARENT_SHA = "b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00"
RUN_ID = "k05-var05-mdb-v102-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID


def build():
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA
    parent = json.loads(raw)
    main = json.loads(raw)
    tables = {t["name"]: t for t in main["model"]["tables"]}
    assert len(tables) == len(main["model"]["tables"]) == 31
    station = tables["Station"]
    assert [x["instance_name"] for x in station["instances"]] == ["K02-BASE", "K02-AUX"]
    base = station["instances"].pop(0)
    assert base["rows"] == [["BASE-01", "Teaching base", 1, "WS"] + [None] * 17]
    assert station["instances"][0]["rows"][0][0] == "K02-NAMED"
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert description == ["K02.var01 v1.0.1 JSON named probe"]
    assert "IncludeFiles" not in tables
    main["model"]["tables"].append({
        "name": "IncludeFiles",
        "columns": [
            {"name": "INCFN", "datatype": "string", "key": True},
            {"name": "INCCO", "datatype": "string"},
            {"name": "NOTE", "datatype": "string"},
        ],
        "instances": [{"instance_name": "", "rows": [[str(RUN / "included.mdb"), "Required base station", None]]}],
    })
    return main, {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"],
                  "rows": [["BASE-01", "Teaching base", 1, "WS"]]}


if __name__ == "__main__":
    main, db = build()
    output = {}
    for name, doc in (("main-input", main), ("database-source", db)):
        path = HERE / f"{name}.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} source changed"
        else:
            path.write_bytes(raw)
        output[name] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "source_sha256": output,
                      "database": str(RUN / "included.mdb")}))
