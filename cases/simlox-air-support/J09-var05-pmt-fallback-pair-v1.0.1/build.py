"""Freeze matched PMT fallback control and SCPMT=2 inputs from accepted D03."""
from __future__ import annotations

import copy
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_INPUT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
FIELDS = ("SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT")


def frozen(path: Path, raw: bytes) -> str:
    if not path.exists() or path.read_bytes() != raw:
        raise ValueError(f"frozen input differs: {path}")
    return hashlib.sha256(raw).hexdigest()


def make_pair() -> tuple[dict, dict]:
    if hashlib.sha256(PARENT_INPUT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D03 source changed")
    control = copy.deepcopy(json.loads(PARENT_INPUT.read_bytes()))
    tables = control["model"]["tables"]
    if len(tables) != 31 or any(t["name"] == "ScaleFactors" for t in tables):
        raise ValueError("unexpected D03 tables")
    pm = next(t for t in tables if t["name"] == "PMLocation")
    names = [c["name"] for c in pm["columns"]]
    rows = pm["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][names.index("TID")] != "PM-CAL24" or rows[0][names.index("PMT")] != 1.0:
        raise ValueError("unexpected D03 PM location")
    rows[0][names.index("TID")] = None
    control["model"]["tables"].append({
        "name": "ScaleFactors",
        "columns": [{"datatype": "double", "name": field} for field in FIELDS],
        "instances": [{"instance_name": "", "rows": [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]]}],
    })
    scaled = copy.deepcopy(control)
    scaled["model"]["tables"][-1]["instances"][0]["rows"][0][FIELDS.index("SCPMT")] = 2.0
    return control, scaled


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    control, scaled = make_pair()
    for name, data in (("control-input.json", control), ("scaled-input.json", scaled)):
        raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if (HERE / name).exists():
                raise FileExistsError(HERE / name)
            (HERE / name).write_bytes(raw)
        print(name, frozen(HERE / name, raw))
