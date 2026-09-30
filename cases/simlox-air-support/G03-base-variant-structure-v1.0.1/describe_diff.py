"""Verify the frozen A01-to-G03 table-level change inventory."""
import json
from pathlib import Path
from build import HERE, PARENT, build


def rows(doc):
    return {table["name"]: table["instances"][0]["rows"] for table in doc["model"]["tables"]}


def main():
    parent = rows(json.loads(PARENT.read_text(encoding="utf-8")))
    actual = {}
    for variant in ("add", "exclude"):
        child = rows(build(variant))
        actual[variant] = {name: {"parent": parent[name], "child": child[name]} for name in parent if parent[name] != child[name]}
    frozen = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    assert actual == frozen
    print("G03 exact table diff verified")


if __name__ == "__main__":
    main()
