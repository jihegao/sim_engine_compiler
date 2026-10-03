"""Check the exact E11 base to E11.var05 source delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, TEMPLATE, TEMPLATE_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() == TEMPLATE_SHA
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(after) - set(before) == {"ItemStationStructure"}
    changed = {n for n in before if before[n] != after[n]}
    assert changed == {"ProblemDescription"}
    item = after["ItemStationStructure"]
    names = [c["name"] for c in item["columns"]]
    rows = [r for i in item["instances"] for r in i["rows"]]
    assert len(rows) == 1 and len(rows[0]) == len(names)
    result = {
        "schema": "simlox-e11-var05-item-route-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "template_sha256": TEMPLATE_SHA,
        "source_sha256": hashlib.sha256(build()).hexdigest(),
        "changed_tables": ["ProblemDescription"],
        "added_tables": ["ItemStationStructure"],
        "description_before": before["ProblemDescription"]["instances"][0]["rows"][0][0],
        "description_after": after["ProblemDescription"]["instances"][0]["rows"][0][0],
        "added_columns": names,
        "added_row": rows[0],
        "unchanged_parent_tables": len(before) - len(changed),
    }
    assert result["unchanged_parent_tables"] == 31
    return result


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode()
    if write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
