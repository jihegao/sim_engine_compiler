"""Replay the exact table delta against each accepted G03 parent."""
import json
from build import HERE, PARENTS, VARIANTS, build


def rows(doc):
    return {table["name"]: table["instances"][0]["rows"] for table in doc["model"]["tables"]}


def main():
    expected = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    actual = {}
    for variant, (branch, _, _) in VARIANTS.items():
        parent = rows(json.loads(PARENTS[branch][0].read_text(encoding="utf-8")))
        child = rows(build(variant))
        actual[variant] = {name: {"parent": parent[name], "child": child[name]} for name in parent if parent[name] != child[name]}
    assert actual == expected
    print("G03 effective-item exact table diff verified")


if __name__ == "__main__":
    main()
