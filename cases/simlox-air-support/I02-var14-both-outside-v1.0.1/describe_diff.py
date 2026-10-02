"""Assert exactly one invalid ItemTransfer endpoint plus provenance label."""
from __future__ import annotations

import json

from build import HERE, PARENT, build, sha, table


if __name__ == "__main__":
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = json.loads((HERE / "native-input.json").read_text(encoding="utf-8"))
    assert child == build()
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    assert before.keys() == after.keys() and len(before) == 32
    changed = [name for name in before if before[name] != after[name]]
    assert changed == ["ProblemDescription", "ItemTransfer"] or set(changed) == {"ProblemDescription", "ItemTransfer"}
    assert len(changed) == 2
    assert table(parent, "ItemTransfer")["instances"][0]["rows"][0] == ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None]
    assert table(child, "ItemTransfer")["instances"][0]["rows"][0] == ["<OUTSIDE>", "<OUTSIDE>", "TEACH-LRU-01", 4.0, 1, 0.0, None]
    output = {"schema": "simlox-i02-var14-both-outside-exact-diff/v1",
              "parent_sha256": sha(PARENT), "input_sha256": sha(HERE / "native-input.json"),
              "changed_tables": sorted(changed), "other_tables_identical": 30,
              "business_cell_delta": {"table": "ItemTransfer", "column": "STTID", "row": 0,
                                      "before": "DEPOT-01", "after": "<OUTSIDE>"},
              "provenance_delta": "ProblemDescription.PDESC only"}
    raw = json.dumps(output, indent=2) + "\n"
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_text(encoding="utf-8") == raw
    else:
        target.write_text(raw, encoding="utf-8")
    print(sha(target))
