"""Add only the global transport-time scale factor to accepted E04 SLOW."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E04-upstream-transport-slow-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_SHA = "b717f88bd0581a486677e7ba60b1235228ba88e05afd9b22cee02925c8ccc317"
OUTPUT = HERE / "scaled-input.json"
FIELDS = ("SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted E04 SLOW parent input changed")
    doc = copy.deepcopy(json.loads(PARENT_INPUT.read_bytes()))
    tables = doc["model"]["tables"]
    if any(t["name"] == "ScaleFactors" for t in tables):
        raise ValueError("parent already has ScaleFactors")
    control = next(t for t in tables if t["name"] == "Control")
    cf = [c["name"] for c in control["columns"]]
    assert len(control["instances"]) == 1 and len(control["instances"][0]["rows"]) == 1
    cr = control["instances"][0]["rows"][0]
    if (cr[cf.index("SIMPE")], cr[cf.index("RCEND")], cr[cf.index("RSEED")]) != (36, 36, "1"):
        raise ValueError("unexpected E04 control")
    station = next(t for t in tables if t["name"] == "StationStructure")
    sf = [c["name"] for c in station["columns"]]
    sr = station["instances"][0]["rows"]
    if len(sr) != 1 or (sr[0][sf.index("TFRMS")], sr[0][sf.index("TTOMS")],
                        sr[0][sf.index("OPOL")]) != (2, 2, "SLOW"):
        raise ValueError("unexpected SLOW route")
    tables.append({"name": "ScaleFactors", "columns": [{"datatype": "double", "name": f} for f in FIELDS],
                   "instances": [{"instance_name": "", "rows": [[1.0, 1.0, 1.0, 1.0, 1.0, 2.0]]}]})
    return doc


def main() -> None:
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


if __name__ == "__main__":
    main()
