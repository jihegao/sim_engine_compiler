"""Freeze two isolated K04.var04 variants from accepted K04.var01 sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K04-var01-nested-mdb-include-v1.0.0"
RUN_ID = "k04-var04-duplicate-control-key-v100-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID
PARENT_MAIN_SHA = "aa0064561c2a1aa9738422c8090ca125478c0517e16010022634bd985da6fa52"
PARENT_STATION_SHA = "2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb"


def read_parent(name, expected):
    raw = (PARENT / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    return json.loads(raw)


def source(model, path, comment):
    doc = json.loads(json.dumps(model))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    assert len(tables) == len(doc["model"]["tables"]) == 32
    include = tables["IncludeFiles"]["instances"]
    assert len(include) == 1 and len(include[0]["rows"]) == 1
    assert include[0]["rows"][0][1:] == ["Nested support organization", None]
    include[0]["rows"][0] = [str(path), comment, None]
    return doc


def build():
    model = read_parent("main-input.json", PARENT_MAIN_SHA)
    station = read_parent("level2-source.json", PARENT_STATION_SHA)
    assert station == {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"],
                       "rows": [["BASE-01", "Teaching base", 1, "WS"]]}
    control = next(t for t in model["model"]["tables"] if t["name"] == "Control")
    assert len(control["instances"]) == 1 and len(control["instances"][0]["rows"]) == 1
    control_columns = [c["name"] for c in control["columns"]]
    control_row = control["instances"][0]["rows"][0]
    assert len(control_columns) == len(control_row) == 24
    control_mdb = {"tables": [
        {"table": "Control", "columns": control_columns, "rows": [control_row]},
        station,
    ]}
    key_level1 = {"tables": [
        {"table": "IncludeFiles", "columns": ["INCFN", "INCCO", "NOTE"],
         "rows": [[str(RUN / "key-level2.mdb"), "Second BASE-01 Station source", None]]},
        {"table": "Station", "columns": station["columns"],
         "rows": [["BASE-01", "First BASE-01 Station source", 1, "WS"]]},
    ]}
    key_level2 = {"tables": [
        {"table": "Station", "columns": station["columns"],
         "rows": [["BASE-01", "Second BASE-01 Station source", 1, "WS"]]},
    ]}
    return {
        "control-main-input.json": source(model, RUN / "control.mdb", "Duplicate Control MDB probe"),
        "key-main-input.json": source(model, RUN / "key-level1.mdb", "Duplicate Station key MDB probe"),
        "control-mdb-source.json": control_mdb,
        "key-level1-source.json": key_level1,
        "key-level2-source.json": key_level2,
    }


if __name__ == "__main__":
    hashes = {}
    for name, doc in build().items():
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / name
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} changed"
        else:
            path.write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_main_sha256": PARENT_MAIN_SHA,
                      "run_id": RUN_ID, "source_sha256": hashes}))
