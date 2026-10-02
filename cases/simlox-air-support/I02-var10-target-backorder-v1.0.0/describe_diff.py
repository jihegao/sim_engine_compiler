"""Verify parent-to-arm and matched-pair TFTIME-only business deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from build import HERE, PARENT, PARENT_SHA, ARMS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    found = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(found) == len(doc["model"]["tables"]) == 32
    return found


def transfer_rows(tables: dict) -> tuple[list[str], list[list]]:
    tab = tables["ItemTransfer"]
    assert len(tab["instances"]) == 1
    return [c["name"] for c in tab["columns"]], tab["instances"][0]["rows"]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = tables(PARENT)
    cols, old = transfer_rows(parent)
    assert len(old) == 2 and cols.index("TFTIME") == 3
    arms = {arm: tables(HERE / f"{arm}-input.json") for arm in ARMS}
    for arm, hour in ARMS.items():
        child = arms[arm]
        assert set(child) == set(parent)
        changed = sorted(name for name in parent if parent[name] != child[name])
        assert changed == ["ItemTransfer", "ProblemDescription"]
        new_cols, rows = transfer_rows(child)
        assert new_cols == cols and len(rows) == 2 and rows[0] == old[0]
        delta = [(cols[i], a, b) for i, (a, b) in enumerate(zip(old[1], rows[1])) if a != b]
        assert delta == [("TFTIME", 6.0, hour)]
    ecols, early = transfer_rows(arms["early"])
    lcols, late = transfer_rows(arms["late"])
    assert ecols == lcols == cols and early[0] == late[0]
    pair_delta = [(cols[i], a, b) for i, (a, b) in enumerate(zip(early[1], late[1])) if a != b]
    assert pair_delta == [("TFTIME", 9.0, 11.0)]
    result = {"schema": "simlox-i02-var10-target-backorder-exact-diff/v1",
              "parent_sha256": PARENT_SHA,
              "arm_sha256": {arm: sha(HERE / f"{arm}-input.json") for arm in ARMS},
              "changed_tables_per_arm": ["ItemTransfer", "ProblemDescription"],
              "unchanged_table_count": 30, "fixed_in_row": old[0],
              "parent_between_time": 6.0, "arm_between_time": ARMS,
              "matched_pair_delta": pair_delta}
    raw = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    out = HERE / "exact-diff.json"
    if out.exists():
        assert out.read_bytes() == raw, "frozen exact diff differs"
    else:
        out.write_bytes(raw)
    print(sha(out))


if __name__ == "__main__":
    main()
