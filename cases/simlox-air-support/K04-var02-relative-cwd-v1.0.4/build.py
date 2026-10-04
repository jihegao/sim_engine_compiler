"""Freeze a relative first include for paired calculation working directories."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K04-var01-nested-mdb-include-v1.0.0"
PARENT_MAIN_SHA = "aa0064561c2a1aa9738422c8090ca125478c0517e16010022634bd985da6fa52"
PARENT_LEVEL1_SHA = "4b2d888f039ce6303cd9fc86bc35c00c84939d433e4cbc87444907f3d5992f23"
PARENT_LEVEL2_SHA = "2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb"
RUN_ID = "k04-var02-relative-cwd-v104-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID


def read_parent(name, expected):
    raw = (PARENT / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    return json.loads(raw)


def build():
    main = read_parent("main-input.json", PARENT_MAIN_SHA)
    level1 = read_parent("level1-source.json", PARENT_LEVEL1_SHA)
    level2 = read_parent("level2-source.json", PARENT_LEVEL2_SHA)
    tables = {table["name"]: table for table in main["model"]["tables"]}
    assert len(tables) == len(main["model"]["tables"]) == 32
    row = tables["IncludeFiles"]["instances"][0]["rows"][0]
    assert row[0].endswith(r"K04-var01-nested-mdb-include-v1.0.0\runs\k04-var01-nested-mdb-v100-ssh-20261004-01\level1.mdb")
    assert row[1:] == ["Nested support organization", None]
    row[0] = "level1.mdb"
    row[1] = "Relative level1 at calculation working directory"
    assert level1 == {"table": "IncludeFiles", "columns": ["INCFN", "INCCO", "NOTE"],
                      "rows": [[str(PARENT / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01" / "level2.mdb"),
                                "Required base station", None]]}
    level1["rows"][0][0] = str(RUN / "level2.mdb")
    assert level2 == {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"],
                      "rows": [["BASE-01", "Teaching base", 1, "WS"]]}
    return main, level1, level2


if __name__ == "__main__":
    output = {}
    for name, doc in zip(("main-input", "level1-source", "level2-source"), build()):
        path = HERE / f"{name}.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} changed"
        else:
            path.write_bytes(raw)
        output[name] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_main_sha256": PARENT_MAIN_SHA, "source_sha256": output,
                      "positive_cwd": str(RUN), "negative_cwd_is_distinct": True}))
