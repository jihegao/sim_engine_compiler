"""Set ATIM=0.3 on the frozen D11 four-mission PM control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D11-var01-atim-control-v1.0.0" / "native-input.json"
PARENT_SHA = "94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("frozen D11 control differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    desc = tables["ProblemDescription"]
    desc["instances"][0]["rows"][0][0] = "D11 four-mission PM with ATIM 0.3"
    pm = tables["MaterielPM"]
    names = [c["name"] for c in pm["columns"]]
    rows = pm["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][names.index("PMID")] != "MS4":
        raise ValueError("unexpected PM control")
    rows[0][names.index("ATIM")] = 0.3
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
        raise ValueError("frozen ATIM input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
