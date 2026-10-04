"""Derive the K06 merge donor by removing one conflicting accepted Station instance."""

import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "K02-var01-json-structure-v1.0.1" / "named-input.json"
PARENT_SHA256 = "b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00"
OUTPUT = HERE / "source-input.json"


def main() -> None:
    parent_bytes = PARENT.read_bytes()
    assert hashlib.sha256(parent_bytes).hexdigest() == PARENT_SHA256
    source = json.loads(parent_bytes)
    donor = copy.deepcopy(source)
    stations = [table for table in donor["model"]["tables"] if table["name"] == "Station"]
    assert len(stations) == 1
    station = stations[0]
    assert [instance["instance_name"] for instance in station["instances"]] == ["K02-BASE", "K02-AUX"]
    assert station["instances"][0]["rows"][0][0] == "BASE-01"
    assert station["instances"][1]["rows"][0][0] == "K02-NAMED"
    station["instances"] = [station["instances"][1]]
    assert len(station["instances"]) == 1
    assert station["instances"][0]["rows"][0][0] == "K02-NAMED"
    data = (json.dumps(donor, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == data, "frozen derived source differs"
    else:
        OUTPUT.write_bytes(data)
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
