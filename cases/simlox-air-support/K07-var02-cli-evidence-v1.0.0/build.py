"""Derive the K07 normal/error CLI sources from accepted K02.var01."""
import copy
import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "K02-var01-json-structure-v1.0.1" / "named-input.json"
expected_parent = "b94e367d46665d4d58f2fb8d15771a61a6d51369070db85ab9bda851c3e76b00"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == expected_parent
normal = parent.read_bytes()
source = json.loads(normal)
negative = copy.deepcopy(source)
station = next(t for t in negative["model"]["tables"] if t["name"] == "Station")
assert [x["instance_name"] for x in station["instances"]] == ["K02-BASE", "K02-AUX"]
assert station["instances"][0]["rows"][0][:4] == ["BASE-01", "Teaching base", 1, "WS"]
station["instances"][0]["inactive_rows"] = [1]
negative_bytes = (json.dumps(negative, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
for name, data in (("normal-input.json", normal), ("inactive-base-input.json", negative_bytes)):
    path = case / name
    if path.exists():
        assert path.read_bytes() == data, f"derived source differs: {name}"
    else:
        path.write_bytes(data)
    print(name, hashlib.sha256(data).hexdigest())
