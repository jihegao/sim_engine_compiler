"""Check the exact E11 base to E11.var04 source delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(before) == set(after)
    changed = {n for n in before if before[n] != after[n]}
    assert changed == {"ProblemDescription", "StationStructure"}
    result = {"schema": "simlox-e11-var04-ordinary-times-exact-diff/v1",
              "parent_sha256": PARENT_SHA,
              "source_sha256": hashlib.sha256(build()).hexdigest(),
              "changed_tables": sorted(changed),
              "changes": []}
    for name in sorted(changed):
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"]
        assert len(old["instances"]) == len(new["instances"]) == 1
        old_rows, new_rows = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert len(old_rows) == len(new_rows)
        columns = [c["name"] for c in old["columns"]]
        for ri, (a, b) in enumerate(zip(old_rows, new_rows)):
            for ci, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    result["changes"].append({"table": name, "row": ri, "column": columns[ci], "before": x, "after": y})
    assert [(x["table"], x["column"], x["before"], x["after"]) for x in result["changes"]] == [
        ("ProblemDescription", "PDESC", "E11 base E10.var03 support gap; BASE-01 AUTOM, bidirectional policy", "E11.var04 AUTOM ordinary times 7h up/11h down versus parent 2h/2h"),
        ("StationStructure", "TFRMS", 2.0, 7.0),
        ("StationStructure", "TTOMS", 2.0, 11.0),
    ]
    result["unchanged_parent_tables"] = len(before) - len(changed)
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
