"""Preserve additive catalog smoke proof separately from the frozen postrun map."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "catalog-regression-custody.json"
COPY = HERE / "preserved-catalog-regression"
ORIGINALS = [
    REPO / "tmp/i03-var03-root-catalog-regression-20261008.py",
    *(REPO / "tmp/i03-var03-root-catalog-regression-20261008-01" / name
      for name in ("receipt.json", "catalog-stdout.bin", "catalog-stderr.bin",
                   "tests-stdout.bin", "tests-stderr.bin")),
]


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(write: bool = False) -> dict:
    if write:
        assert not OUT.exists() and not COPY.exists()
        COPY.mkdir()
        records = []
        for index, original in enumerate(ORIGINALS):
            assert original.is_file()
            owned = COPY / f"{index:02d}.bytes"
            owned.write_bytes(original.read_bytes())
            records.append({"original": original.relative_to(REPO).as_posix(),
                            "owned_copy": owned.relative_to(HERE).as_posix(), **pin(original)})
        OUT.write_bytes((json.dumps({"schema": "i03-var03-catalog-regression-custody/v1",
                                     "records": records}, indent=2) + "\n").encode())
    mapping = json.loads(OUT.read_bytes())
    assert mapping["schema"] == "i03-var03-catalog-regression-custody/v1"
    records = mapping["records"]
    assert len(records) == 6 and len({row["original"] for row in records}) == 6
    for row in records:
        wanted = {key: row[key] for key in ("bytes", "sha256")}
        assert pin(HERE / row["owned_copy"]) == wanted
        original = REPO / row["original"]
        if original.exists():
            assert pin(original) == wanted
    receipt = json.loads((COPY / "01.bytes").read_bytes())
    assert receipt["schema"] == "i03-var03-root-planning-regression/v1"
    return {"schema": "i03-var03-catalog-regression-custody-check/v1",
            "records": len(records), "map": pin(OUT), "written": write}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.write), sort_keys=True))
