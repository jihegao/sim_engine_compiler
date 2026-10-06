"""Freeze a one-cell zero first subtask child of accepted B02 1.0.2."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2/native-input.json"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted B02 input SHA differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = [t for t in doc["model"]["tables"] if t["name"] == "TaskBreakDown"]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError("TaskBreakDown shape differs")
    table = tables[0]
    cols = [c["name"] for c in table["columns"]]
    rows = table["instances"][0]["rows"]
    expected = [("PREP-FIXED", 1, "INSPECT", 1 / 6),
                ("PREP-FIXED", 2, "SERVICE", 1 / 3)]
    if len(rows) != 2 or any(len(r) != len(cols) for r in rows):
        raise ValueError("TaskBreakDown row shape differs")
    for row, expected_row in zip(rows, expected):
        actual = tuple(row[cols.index(c)] for c in ("TID", "SEQ", "SUTID", "DURN"))
        if actual != expected_row:
            raise ValueError(f"accepted B02 subtask differs: {actual}")
        if row[cols.index("DURND")] is not None:
            raise ValueError("accepted B02 subtask distribution differs")
    rows[0][cols.index("DURN")] = 0
    return doc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(data)
    elif OUTPUT.read_bytes() != data:
        raise ValueError("frozen child differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data),
                      "only_change": "TaskBreakDown SEQ1 DURN 1/6 to 0"}))


if __name__ == "__main__":
    main()
