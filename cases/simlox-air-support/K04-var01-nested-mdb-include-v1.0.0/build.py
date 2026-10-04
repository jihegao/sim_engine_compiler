"""Freeze a two-level MDB IncludeFiles chain from accepted K05.var05."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K05-var05-runtime-mdb-include-v1.0.2"
PARENT_INPUT_SHA = "ed57d43da4315fcd2f4fbd5cd80840c2add42adf9227bcfc947ad99477575044"
PARENT_DB_SOURCE_SHA = "2c2fc671f6084ce90a4635526e50dc6df4b7ebd087c8fd8eca4080839c5a3ddb"
RUN_ID = "k04-var01-nested-mdb-v100-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID


def build():
    raw = (PARENT / "main-input.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_INPUT_SHA
    db_raw = (PARENT / "database-source.json").read_bytes()
    assert hashlib.sha256(db_raw).hexdigest() == PARENT_DB_SOURCE_SHA
    main = json.loads(raw)
    tables = {table["name"]: table for table in main["model"]["tables"]}
    assert len(tables) == len(main["model"]["tables"]) == 32
    row = tables["IncludeFiles"]["instances"][0]["rows"][0]
    assert row[1:] == ["Required base station", None]
    assert row[0].endswith(r"K05-var05-runtime-mdb-include-v1.0.2\runs\k05-var05-mdb-v102-ssh-20261004-01\included.mdb")
    row[0] = str(RUN / "level1.mdb")
    row[1] = "Nested support organization"
    level1 = {"table": "IncludeFiles", "columns": ["INCFN", "INCCO", "NOTE"],
              "rows": [[str(RUN / "level2.mdb"), "Required base station", None]]}
    assert len(level1["rows"][0][0]) <= 255
    level2 = json.loads(db_raw)
    assert level2 == {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"],
                      "rows": [["BASE-01", "Teaching base", 1, "WS"]]}
    return main, level1, level2


if __name__ == "__main__":
    main, level1, level2 = build()
    output = {}
    for name, doc in (("main-input", main), ("level1-source", level1), ("level2-source", level2)):
        path = HERE / f"{name}.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} source changed"
        else:
            path.write_bytes(raw)
        output[name] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_input_sha256": PARENT_INPUT_SHA, "source_sha256": output,
                      "level1_mdb": str(RUN / "level1.mdb"), "level2_mdb": str(RUN / "level2.mdb")}))
