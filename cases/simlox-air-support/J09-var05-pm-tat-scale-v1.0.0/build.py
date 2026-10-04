"""Add only global PM TAT scale factor to accepted D03 calendar PM."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUTPUT = HERE / "scaled-input.json"
FIELDS = ("SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted D03 input changed")
    doc = copy.deepcopy(json.loads(PARENT_INPUT.read_bytes()))
    tables = doc["model"]["tables"]
    if any(t["name"] == "ScaleFactors" for t in tables):
        raise ValueError("D03 parent already has ScaleFactors")
    control = next(t for t in tables if t["name"] == "Control")
    cf = [c["name"] for c in control["columns"]]
    cr = control["instances"][0]["rows"]
    if len(cr) != 1 or (cr[0][cf.index("SIMPE")], cr[0][cf.index("RCEND")],
                        cr[0][cf.index("RSEED")], cr[0][cf.index("ENPM")]) != (60, 60, "1", "Y"):
        raise ValueError("unexpected D03 control")
    pm = next(t for t in tables if t["name"] == "MaterielPM")
    pf = [c["name"] for c in pm["columns"]]
    pr = pm["instances"][0]["rows"]
    if len(pr) != 1 or (pr[0][pf.index("PMID")], pr[0][pf.index("PMINT")],
                        pr[0][pf.index("OPID")]) != ("CAL24", 24, "CALHOURS"):
        raise ValueError("unexpected D03 calendar PM")
    tables.append({"name": "ScaleFactors", "columns": [{"datatype": "double", "name": f} for f in FIELDS],
                   "instances": [{"instance_name": "", "rows": [[1.0, 1.0, 1.0, 1.0, 2.0, 1.0]]}]})
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen scaled input differs")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
