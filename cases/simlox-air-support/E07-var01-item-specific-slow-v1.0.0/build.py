"""Derive one item-specific SLOW demand policy from accepted E07 FAST."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E07-item-specific-transport-v1.0.1" / "native-input.json"
PARENT_SHA = "d42832b9e17b9a0c968a8bba7bcb1419eba06313097604fc0041baab5d132bc0"
SUPPORT = HERE.parent / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
SUPPORT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def build() -> dict:
    if sha(PARENT) != PARENT_SHA or sha(SUPPORT) != SUPPORT_SHA:
        raise ValueError("accepted parent/support fingerprint changed")
    doc = copy.deepcopy(json.loads(PARENT.read_bytes()))
    description = table(doc, "ProblemDescription")
    description["instances"][0]["rows"][0][0] = (
        "E07 item-specific SLOW route delays depot demand until faulty item arrives; "
        "one-hour down and three-hour up")
    item = table(doc, "ItemStationStructure")
    rows = item["instances"][0]["rows"]
    columns = [column["name"] for column in item["columns"]]
    if len(rows) != 1 or rows[0][columns.index("IID")] != "TEACH-LRU-01":
        raise ValueError("expected accepted one-item route")
    if rows[0][columns.index("OPOL")] != "FAST" or rows[0][columns.index("TFRMS")] != 1.0 \
            or rows[0][columns.index("TTOMS")] != 3.0:
        raise ValueError("expected accepted FAST, one-hour-down/three-hour-up route")
    rows[0][columns.index("OPOL")] = "SLOW"
    general = table(doc, "StationStructure")
    general_rows = general["instances"][0]["rows"]
    general_columns = [column["name"] for column in general["columns"]]
    if len(general_rows) != 1 or general_rows[0][general_columns.index("OPOL")] != "FAST":
        raise ValueError("expected unchanged general FAST route")
    return doc


def raw() -> bytes:
    return (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = raw()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(data)
    elif OUTPUT.read_bytes() != data:
        raise ValueError("frozen SLOW source differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "support_sha256": SUPPORT_SHA,
                      "input_sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}))


if __name__ == "__main__":
    main()
