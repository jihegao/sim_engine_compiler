"""Freeze matched FIXED and ONDEM downward transport policies from accepted E04."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json"
PARENT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
ARMS = {"fixed": "FIXED", "ondem": "ONDEM"}
COLUMNS = [
    ("TPRID", "string"), ("STPRID", "string"), ("STIM", "double"),
    ("IQTY", "integer"), ("IINT", "double"), ("DURN", "double"),
    ("MINBS", "integer"), ("TPTIM", "double"), ("TPTIMD", "string"),
    ("NOTE", "string"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build(arm: str) -> bytes:
    assert arm in ARMS and sha(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"E10.var01 E04 FAST depot spare; downward {ARMS[arm]} policy at h11 or on demand"
    )
    link = table(doc, "StationStructure")
    names = [c["name"] for c in link["columns"]]
    rows = [r for i in link["instances"] for r in i["rows"]]
    assert len(rows) == 1 and rows[0][names.index("STID")] == "BASE-01" and rows[0][names.index("MSTID")] == "DEPOT-01"
    assert rows[0][names.index("PFRMS")] is None and rows[0][names.index("TFRMS")] == 2.0
    rows[0][names.index("PFRMS")] = "DOWN-POLICY"
    policy = ARMS[arm]
    # Keep the parent's fixed two-hour transport in both arms. FIXED departs at h11;
    # ONDEM is active over the entire 36-hour horizon and can depart at demand.
    profile_row = ["DOWN-POLICY", policy, 11.0 if arm == "fixed" else 0.0,
                   1, 0.0, None if arm == "fixed" else 36.0, 1, 2.0, None, None]
    doc["model"]["tables"].append({
        "columns": [{**{"datatype": dtype}, **({"key": True} if name in {"TPRID", "STPRID", "STIM"} else {}), "name": name}
                    for name, dtype in COLUMNS],
        "instances": [{"instance_name": "", "rows": [profile_row]}],
        "name": "TransportPolicyProfile",
    })
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    out = {}
    for arm in ARMS:
        path = HERE / f"native-input-{arm}.json"
        raw = build(arm)
        if write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw, arm
        out[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs_sha256": out}))


if __name__ == "__main__":
    main()
