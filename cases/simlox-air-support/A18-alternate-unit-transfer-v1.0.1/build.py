"""Derive paired A18 controls with an explicit idle alternate from A17."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
PARENT_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def one(doc: dict, name: str) -> tuple[dict, list[str], list[list]]:
    table, = (t for t in doc["model"]["tables"] if t["name"] == name)
    instance, = table["instances"]
    return table, [c["name"] for c in table["columns"]], instance["rows"]


def update_single(columns: list[str], rows: list[list], **updates: object) -> None:
    assert len(rows) == 1 and set(updates) <= set(columns)
    for key, value in updates.items():
        rows[0][columns.index(key)] = value


def build(enabled: bool) -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]

    _, c, rows = one(doc, "ProblemDescription")
    update_single(c, rows, PDESC=f"A18 one fixed mission, idle alternate profile, ENALU={'Y' if enabled else 'N'}")

    _, c, rows = one(doc, "Control")
    assert rows[0][c.index("ENALU")] is None
    update_single(c, rows, ENALU="Y" if enabled else "N")

    _, c, rows = one(doc, "SystemDeployment")
    assert len(rows) == 2
    assert [r[c.index("USTID")] for r in rows] == ["TEACH-UNIT", "TEACH-UNIT-2"]
    assert [r[c.index("QTYPS")] for r in rows] == [1, 1]
    rows[1][c.index("QTYPS")] = 2

    _, c, rows = one(doc, "Unit")
    assert len(rows) == 2 and rows[1][c.index("UNID")] == "TEACH-UNIT-2"
    rows[1][c.index("DESCR")] = "Two-aircraft alternate teaching unit"

    _, c, rows = one(doc, "Operations")
    assert rows[0][c.index("USTID")] == "TEACH-GROUP"
    update_single(c, rows, USTID="TEACH-UNIT")
    rows.append([{"USTID": "TEACH-UNIT-2", "PRID": "ALT-IDLE"}.get(name) for name in c])

    _, c, rows = one(doc, "OperationProfile")
    assert len(rows) == 1 and rows[0][c.index("PRID")] == "BASIC-SCHEDULE"
    idle = dict(zip(c, rows[0], strict=True))
    idle.update(PRID="ALT-IDLE", IQTY=0, NOTE="Explicit idle alternate prevents generated default mission")
    rows.append([idle[name] for name in c])

    # The two explicit units are retained. The A17 group is removed because
    # AlternateUnit addresses ordinary and alternate units, never a group.
    removed = {"UnitGroup", "UnitGroupMember"}
    assert all(len(one(doc, name)[2]) > 0 for name in removed)
    model["tables"] = [t for t in model["tables"] if t["name"] not in removed]
    assert not any(t["name"] == "AlternateUnit" for t in model["tables"])
    model["tables"].append({
        "columns": [
            {"datatype": "string", "key": True, "name": "USTID"},
            {"datatype": "string", "key": True, "name": "AUNID"},
            {"datatype": "integer", "name": "PRI"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [["TEACH-UNIT", "TEACH-UNIT-2", 1, None]]}],
        "name": "AlternateUnit",
    })
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for enabled, variant in ((True, "enabled"), (False, "disabled")):
        output = HERE / f"{variant}-input.json"
        raw = (json.dumps(build(enabled), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(raw)
        else:
            assert output.read_bytes() == raw
        result[variant] = {"input_sha256": sha(raw), "bytes": len(raw)}
    print(json.dumps({"parent_sha256": PARENT_SHA, "variants": result}))


if __name__ == "__main__":
    main()
