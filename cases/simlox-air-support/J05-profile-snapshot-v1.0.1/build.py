"""Build a matched J05 continuous/snapshot profile probe from accepted A01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def add_table(doc: dict, name: str, columns: list[tuple[str, str, bool]], rows: list[list]) -> None:
    assert all(t["name"] != name for t in doc["model"]["tables"])
    assert all(len(r) == len(columns) for r in rows)
    doc["model"]["tables"].append({
        "columns": [{**{"datatype": dtype}, **({"key": True} if key else {}), "name": field}
                    for field, dtype, key in columns],
        "instances": [{"instance_name": "", "rows": rows}],
        "name": name,
    })


def build() -> dict[str, dict]:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    baseline = json.loads(PARENT.read_bytes())
    assert table(baseline, "Control")["instances"][0]["rows"][0][:7] == [1, 36.0, "1", "AIR_BASIC", .5, 0, 36.0]
    assert table(baseline, "ResultCollection")["instances"][0]["rows"] == [
        ["MISSION", .5, 0, 36.0, None, None], ["SYSTEM", .5, 0, 36.0, None, None]]

    snapshot = copy.deepcopy(baseline)
    table(snapshot, "ProblemDescription")["instances"][0]["rows"][0][0] = "J05 direct snapshot times 8.25 and 10.25"
    add_table(snapshot, "SnapshotResultTimes", [("SSTIM", "double", False), ("NOTE", "string", False)],
              [[8.25, None], [10.25, None]])
    add_table(snapshot, "ReplicationResultControlSystem", [
        ("SID", "string", True), ("USTID", "string", True), ("TOTAL", "string", False),
        ("TIME", "string", False), ("SNAPS", "string", False), ("NOTE", "string", False)],
        [["TEACH-AIR-01", "TEACH-UNIT", "Y", "Y", "Y", None]])

    mixed = copy.deepcopy(snapshot)
    table(mixed, "ProblemDescription")["instances"][0]["rows"][0][0] = "J05 mixed SYSTEM profile at 7.75-8.25 and 9.75-10.25"
    table(mixed, "SnapshotResultTimes")["instances"][0]["rows"] = [[6.0, None], [14.0, None]]
    table(mixed, "ResultCollection")["instances"][0]["rows"][1] = ["SYSTEM", 1.0, 0, 36.0, "J05MIX", None]
    add_table(mixed, "ResultCollectionProfile", [
        ("RCPID", "string", True), ("SRCPID", "string", True), ("STIM", "double", True),
        ("IQTY", "integer", False), ("IINT", "double", False), ("RCINT", "double", False),
        ("DURN", "double", False), ("NOTE", "string", False)], [
            ["J05MIX", "CONTINUOUS", 7.75, 1, None, .5, .5, None],
            ["J05MIX", "SNAPSHOT", 8.25, 1, None, None, None, None],
            ["J05MIX", "CONTINUOUS", 9.75, 1, None, .5, .5, None],
            ["J05MIX", "SNAPSHOT", 10.25, 1, None, None, None, None],
        ])
    return {"baseline": baseline, "snapshot-control": snapshot, "mixed-profile": mixed}


def main() -> None:
    for variant, doc in build().items():
        raw = PARENT.read_bytes() if variant == "baseline" else (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{variant}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
