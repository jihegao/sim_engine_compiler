"""Build a frozen MNOCC 0/1/2 comparison from accepted D10.var02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D10-var02-multi-counter-v1.0.0" / "native-input.json"
PARENT_SHA = "0083ffd0038017be0078d9afd5a9e892b3df8c7ae5eafd89b8280950816aa829"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build(limit: int) -> bytes:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("frozen D10.var02 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    pm = tables["MaterielPM"]
    rows = pm["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][0] != "MS2":
        raise ValueError("unexpected parent PM rows")
    column_names = [column["name"] for column in pm["columns"]]
    rows[0][column_names.index("MNOCC")] = limit
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        f"D11 MNOCC={limit} cap on D10 three-counter PM"
    )
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for limit in (0, 1, 2):
        output = HERE / f"native-mnocc-{limit}.json"
        raw = build(limit)
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(raw)
        elif output.read_bytes() != raw:
            raise ValueError(f"frozen MNOCC={limit} input differs")
        hashes[str(limit)] = sha(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashes}))


if __name__ == "__main__":
    main()
