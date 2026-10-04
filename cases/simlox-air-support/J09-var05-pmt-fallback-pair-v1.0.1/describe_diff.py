"""Certify exactly one TID removal and one ScaleFactors row across matched arms."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json

from build import HERE, PARENT_INPUT, PARENT_SHA, FIELDS


def describe() -> dict:
    parent = json.loads(PARENT_INPUT.read_bytes())
    control = json.loads((HERE / "control-input.json").read_bytes())
    scaled = json.loads((HERE / "scaled-input.json").read_bytes())
    original = copy.deepcopy(parent)
    pm = next(t for t in original["model"]["tables"] if t["name"] == "PMLocation")
    names = [c["name"] for c in pm["columns"]]
    pm["instances"][0]["rows"][0][names.index("TID")] = None
    original["model"]["tables"].append({
        "name": "ScaleFactors",
        "columns": [{"datatype": "double", "name": f} for f in FIELDS],
        "instances": [{"instance_name": "", "rows": [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]]}],
    })
    if original != control:
        raise ValueError("control has more than TID removal and all-one ScaleFactors")
    expected = copy.deepcopy(control)
    expected["model"]["tables"][-1]["instances"][0]["rows"][0][FIELDS.index("SCPMT")] = 2.0
    if expected != scaled:
        raise ValueError("scaled arm has an unexpected delta")
    return {
        "schema": "simlox-j09-var05-matched-exact-diff/v1",
        "parent_input_sha256": PARENT_SHA,
        "control_input_sha256": hashlib.sha256((HERE / "control-input.json").read_bytes()).hexdigest(),
        "scaled_input_sha256": hashlib.sha256((HERE / "scaled-input.json").read_bytes()).hexdigest(),
        "control_delta": {"table": "PMLocation", "key": ["CAL24", "TEACH-AIR-01", "BASE-01"], "field": "TID", "before": "PM-CAL24", "after": None, "appended_scale_row": [1.0] * 6},
        "scaled_delta": {"table": "ScaleFactors", "field": "SCPMT", "before": 1.0, "after": 2.0},
        "other_changes": [],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(describe(), indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    if not path.exists() or path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(hashlib.sha256(raw).hexdigest())
