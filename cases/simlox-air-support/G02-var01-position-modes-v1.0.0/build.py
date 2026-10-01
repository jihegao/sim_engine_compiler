"""Derive a second position-specific failure mode from accepted D06."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
OUTPUT = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return matches[0]


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D06 parent fingerprint differs")
    doc = json.loads(raw)
    description = table(doc, "ProblemDescription")
    fields = [c["name"] for c in description["columns"]]
    description["instances"][0]["rows"][0][fields.index("PDESC")] = (
        "G02 position-specific explicit modes on the same LRU, direct local CM"
    )
    modes = table(doc, "FailureMode")["instances"][0]["rows"]
    locations = table(doc, "CMLocation")["instances"][0]["rows"]
    if len(modes) != 1 or modes[0][0:3] != ["FM-POS-A", "Position A direct repair", "POS-A"]:
        raise ValueError("unexpected D06 failure-mode parent")
    if len(locations) != 1 or locations[0][0:3] != ["FM-POS-A", "TEACH-AIR-01", "BASE-01"]:
        raise ValueError("unexpected D06 CM mapping parent")
    modes.append(["FM-POS-B", "Position B direct repair", "POS-B", 600000.0,
                  "OPHOURS", 1.0, None, None, None])
    locations.append(["FM-POS-B", "TEACH-AIR-01", "BASE-01", 0.5,
                      None, None, 1.0, None, None, None])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen G02 probe input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": len(raw)}))


if __name__ == "__main__":
    main()
