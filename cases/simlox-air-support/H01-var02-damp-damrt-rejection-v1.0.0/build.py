"""Build a mutual-exclusion probe from the accepted H01.var02 rate source."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H01-var02-rate-no-consequence-v1.0.0/rate-input.json"
PARENT_SHA = "947fe484aad8aa8a971160baaddc56489a2cea78e1b0365fe955c59de04c7d65"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> bytes:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted H01.var02 rate source fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    row = tables["MissionDamage"]["instances"][0]["rows"][0]
    columns = [c["name"] for c in tables["MissionDamage"]["columns"]]
    if row[columns.index("DAMP")] != 0 or row[columns.index("DAMRT")] != 3000000:
        raise ValueError("accepted rate row differs")
    row[columns.index("DAMP")] = 1.0
    description = tables["ProblemDescription"]["instances"][0]["rows"]
    if description != [["H01.var02 fixed-mission DAMRT high-rate probe, no consequence"]]:
        raise ValueError("accepted rate description differs")
    description[0][0] = "H01.var02 simultaneous DAMP=1 and DAMRT=3000000 rejection probe"
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = build()
    path = HERE / "simultaneous-input.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen simultaneous source differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "child_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
