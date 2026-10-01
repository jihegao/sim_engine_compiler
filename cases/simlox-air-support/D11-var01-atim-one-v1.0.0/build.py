"""Build ATIM=1 boundary candidate from the accepted D11.var01 control."""
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


def build() -> bytes:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted ATIM=0 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    pm = tables["MaterielPM"]
    names = [column["name"] for column in pm["columns"]]
    rows = pm["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][names.index("PMID")] != "MS4" or rows[0][names.index("ATIM")] != 0:
        raise ValueError("unexpected parent PM")
    rows[0][names.index("ATIM")] = 1.0
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        "D11 MISSIONS=4 PM at ATIM=1 boundary"
    )
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = build()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen ATIM=1 input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
