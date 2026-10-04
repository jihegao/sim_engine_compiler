"""Freeze a default-Station K02 control and the ODBC null-row patch."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K02-var01-json-structure-v1.0.1"
PARENT_SHA = "b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00"


def build():
    raw = (PARENT / "named-input.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA
    parent = json.loads(raw)
    station = next(t for t in parent["model"]["tables"] if t["name"] == "Station")
    assert len(station["instances"]) == 2
    first, second = station["instances"]
    assert first["instance_name"] == "K02-BASE" and second["instance_name"] == "K02-AUX"
    assert first["rows"][0][:4] == ["BASE-01", "Teaching base", 1, "WS"]
    assert second["rows"][0][:4] == ["K02-NAMED", "Unused named-instance station", 1, "WS"]
    station["instances"] = [{"instance_name": "", "rows": [first["rows"][0], second["rows"][0]]}]
    database = {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"],
                "rows": [["BASE-01", "ODBC merged teaching base", None, None]]}
    return {"baseline-input.json": parent, "database-source.json": database}


if __name__ == "__main__":
    hashes = {}
    for name, doc in build().items():
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / name
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} changed"
        else:
            path.write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "source_sha256": hashes}))
