"""Build a no-breakdown scalar-preparation control from accepted B02 1.0.2."""
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
        raise ValueError("accepted B02 source SHA differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    breakdown = tables["TaskBreakDown"]
    if len(breakdown["instances"]) != 1:
        raise ValueError("TaskBreakDown instance shape differs")
    fields = [x["name"] for x in breakdown["columns"]]
    rows = breakdown["instances"][0]["rows"]
    expected = [("PREP-FIXED", 1, "INSPECT", 1 / 6),
                ("PREP-FIXED", 2, "SERVICE", 1 / 3)]
    actual = [tuple(r[fields.index(c)] for c in ("TID", "SEQ", "SUTID", "DURN"))
              for r in rows]
    if actual != expected:
        raise ValueError(f"accepted B02 breakdown differs: {actual}")
    prep = tables["MissionPreparation"]
    pfields = [x["name"] for x in prep["columns"]]
    prows = prep["instances"][0]["rows"]
    if len(prows) != 1 or prows[0][pfields.index("DURN")] != 0.75 or prows[0][pfields.index("TID")] != "PREP-FIXED":
        raise ValueError("accepted B02 scalar/task link differs")
    breakdown["instances"][0]["rows"] = []
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
                      "bytes": len(data), "only_change": "remove two TaskBreakDown rows"}))


if __name__ == "__main__":
    main()
