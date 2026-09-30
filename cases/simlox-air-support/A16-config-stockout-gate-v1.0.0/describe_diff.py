"""Check the frozen two-table stockout delta against A16 baseline."""
import json
from build import HERE, PARENT, build


def rows(doc):
    return {t["name"]: t["instances"][0]["rows"] for t in doc["model"]["tables"]}


def main():
    before = rows(json.loads(PARENT.read_text(encoding="utf-8")))
    after = rows(build())
    actual = {name: {"parent": before.get(name), "child": after[name]} for name in after if before.get(name) != after[name]}
    assert actual == json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    print("A16 stockout exact diff verified")


if __name__ == "__main__":
    main()
