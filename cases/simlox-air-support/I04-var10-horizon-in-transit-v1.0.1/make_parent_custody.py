"""Exact inherited raw identities; no accepted simulator or checker calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import encode, pin, read, verify_expected

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I04-var03-idle-system-between-v1.0.1"
INDEX = PARENT / "evidence-index.json"
INDEX_PIN = {"bytes": 176439, "sha256": "09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff"}


def generated():
    assert pin(INDEX) == INDEX_PIN
    document = read(INDEX)
    assert document["source_count"] == len(document["source_files"]) == 401
    assert len(document["raw_files"]) == 153 and len(document["preflight_original_files"]) == 15
    assert len({r["path"].casefold() for r in document["raw_files"] + document["preflight_original_files"]}) == 168
    for row in document["raw_files"] + document["preflight_original_files"]:
        assert row["original_mandatory"] is True and row["owned_copy"] is None
        assert pin(Path(row["path"])) == {k: row[k] for k in ("bytes", "sha256")}
    return {
        "raw-custody-map.json": {"schema": "i04-var10-parent-raw-custody/v101", "source_parent_index_sha256": INDEX_PIN["sha256"],
                                 "records": document["raw_files"]},
        "preflight-custody-map.json": {"schema": "i04-var10-parent-preflight-custody/v101", "source_parent_index_sha256": INDEX_PIN["sha256"],
                                       "records": document["preflight_original_files"]},
    }


def main(write=False):
    result = {}
    for name, value in generated().items():
        result[name] = verify_expected(HERE / name, encode(value), write)
    print(json.dumps({"schema": "i04-var10-parent-custody-build/v101", "native_calls": 0, "artifacts": result}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    main(parser.parse_args().write)
