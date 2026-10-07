"""Verify byte-identical custody of the rejected v1 postappend rebuild."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "postappend-context-custody-v2.json"
SOURCES = (
    "tmp/i03-v102-postappend-index-failure-20261007-01/replay-stdout.bin",
    "tmp/i03-v102-postappend-index-failure-20261007-01/replay-stderr.bin",
    "tmp/i03-v102-postappend-index-failure-20261007-01/builder-stdout.bin",
    "tmp/i03-v102-postappend-index-failure-20261007-01/builder-stderr.bin",
    "tmp/i03-v102-postappend-index-failure-20261007-01/unpublished-catalog491.bytes",
    "tmp/i03-v102-postappend-index-failure-20261007-01/failure-receipt.json",
    "tmp/preserve-i03-postappend-rebuild-failure-20261007.py",
    "tmp/i03-v102-root-catalog-append-20261007.json",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(write: bool = False) -> dict:
    if write:
        assert not MAP.exists()
        records = []
        for name in SOURCES:
            data = (REPO / name).read_bytes()
            copy_name = "preserved-postappend-failure/" + name.removeprefix("tmp/")
            copy = HERE / copy_name
            copy.parent.mkdir(parents=True, exist_ok=True)
            with copy.open("xb") as stream:
                stream.write(data)
            records.append({"original_path": name, "copy_path": copy_name, **pin(data)})
        MAP.write_bytes((json.dumps({"schema": "i03-var02-v102-postappend-failure-custody/v2",
                                    "records": records}, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    doc = json.loads(MAP.read_text(encoding="utf-8"))
    assert doc["schema"] == "i03-var02-v102-postappend-failure-custody/v2"
    assert [r["original_path"] for r in doc["records"]] == list(SOURCES)
    for record in doc["records"]:
        expected = {k: record[k] for k in ("bytes", "sha256")}
        assert pin((HERE / record["copy_path"]).read_bytes()) == expected, record
        original = REPO / record["original_path"]
        if original.exists():
            assert pin(original.read_bytes()) == expected, record
    return {"schema": "i03-var02-v102-postappend-context-check/v2", "passed": True,
            "historical_records": len(doc["records"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--copy", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.copy), sort_keys=True, separators=(",", ":")))
