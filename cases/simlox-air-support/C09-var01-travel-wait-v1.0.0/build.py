"""Build C09.var01 short/equal/long remote travel versus local repair wait."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C09-var04-remote-maintenance-resource-v1.0.0/local-input.json"
PARENT_SHA = "1f7e87b3c7886f6b05ff2b2d9f04ee1a98e64445f8f5d6b660595eb2c5845730"
TRAVEL = {"short": 0.25, "equal": 0.5, "long": 0.75}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def put(t: dict, row: list, field: str, value) -> None:
    row[[c["name"] for c in t["columns"]].index(field)] = value


def route_schema() -> dict:
    fields = (("RID", "string", True), ("STID", "string", True),
              ("RSTID", "string", True), ("TFRS", "double", False),
              ("TTRS", "double", False), ("TTRSS", "double", False),
              ("NOTE", "string", False))
    return {"columns": [{**{"datatype": kind}, **({"key": True} if key else {}), "name": name}
                        for name, kind, key in fields],
            "instances": [{"instance_name": "", "rows": []}],
            "name": "ResourceRemoteSupport"}


def build(variant: str) -> dict:
    assert sha(PARENT) == PARENT_SHA
    if variant not in TRAVEL:
        raise ValueError(variant)
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    description = table(doc, "ProblemDescription")
    put(description, description["instances"][0]["rows"][0], "PDESC",
        f"C09.var01 remote travel {variant} versus 0.5-hour local primary repair wait")
    allocation = table(doc, "ResourceAllocation")
    local = next(r for r in allocation["instances"][0]["rows"]
                 if r[[c["name"] for c in allocation["columns"]].index("RID")] == "P-MECH")
    remote = copy.deepcopy(local)
    put(allocation, remote, "STID", "BASE-02")
    allocation["instances"][0]["rows"].append(remote)
    route = route_schema()
    route["instances"][0]["rows"].append(
        ["P-MECH", "BASE-01", "BASE-02", TRAVEL[variant], 0.5, 0.125, None])
    doc["model"]["tables"].append(route)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for variant in TRAVEL:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        dest = HERE / f"{variant}-input.json"
        if args.write:
            if dest.exists():
                raise FileExistsError(dest)
            dest.write_bytes(raw)
        elif dest.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {variant}")
        result[variant] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs_sha256": result}))


if __name__ == "__main__":
    main()
