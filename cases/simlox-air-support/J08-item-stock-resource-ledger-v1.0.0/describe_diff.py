"""Freeze the complete authored delta from the accepted F02 risk input."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, build, table


def main() -> None:
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    child = build()
    assert [t["name"] for t in child["model"]["tables"]] == [t["name"] for t in parent["model"]["tables"]]
    changed = [a["name"] for a, b in zip(parent["model"]["tables"], child["model"]["tables"]) if a != b]
    assert changed == ["Item", "ResultCollection"], changed
    item_parent, item_child = table(parent, "Item"), table(child, "Item")
    names = [c["name"] for c in item_parent["columns"]]
    track = names.index("TRACK")
    assert item_parent["columns"] == item_child["columns"]
    assert all([b if i != track else "Y" for i, b in enumerate(before)] == after
               for before, after in zip(item_parent["instances"][0]["rows"], item_child["instances"][0]["rows"]))
    collection_parent = table(parent, "ResultCollection")
    collection_child = table(child, "ResultCollection")
    assert collection_child["instances"][0]["rows"] == collection_parent["instances"][0]["rows"] + [["ITEM", 0.5, 0, 60.0, None, None]]
    out = {"schema": "simlox-j08-exact-diff/v1", "changed_tables": changed,
           "item_track": [{"iid": r[0], "before": None, "after": "Y"} for r in item_parent["instances"][0]["rows"]],
           "result_collection_appended": ["ITEM", 0.5, 0, 60.0, None, None],
           "other_28_tables": "exactly unchanged"}
    raw = (json.dumps(out, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_bytes() == raw, "frozen diff changed"
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
