"""Identify every byte in the excluded first copier's short-path relocation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_PREFIX = "preserved-postrun-context-v1-failed/"
NEW_PREFIX = "p-v1x/"
OUT = HERE / "failed-copier-relocation.json"
FAILED_SCRIPT_SHA = "6918be58db6107eebf1377c55b12e84d32865aa50833f5f4979d8397db916728"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    files = sorted((HERE / "p-v1x").rglob("*"))
    rows = []
    for path in files:
        if path.is_file():
            rel = path.relative_to(HERE).as_posix()
            assert rel.startswith(NEW_PREFIX)
            rows.append({"old_relative_path": OLD_PREFIX + rel[len(NEW_PREFIX):],
                         "current_relative_path": rel, **pin(path)})
    assert len(rows) == 74 and len({row["current_relative_path"] for row in rows}) == 74
    failed = [row for row in rows if row["current_relative_path"].endswith("copy_postrun_context-v1-failed.py.bytes")]
    assert len(failed) == 1 and failed[0]["sha256"] == FAILED_SCRIPT_SHA
    return {"schema": "i03-var03-excluded-copier-relocation/v1",
            "decision": "NO_GO_DEVELOPMENT_DRAFT",
            "original_long_prefix": OLD_PREFIX, "current_short_prefix": NEW_PREFIX,
            "failure": "Windows long destination path after 72 small copies; no map produced; stderr tool transcript only",
            "records": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    doc = candidate()
    data = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode()
    if args.write:
        assert not OUT.exists()
        OUT.write_bytes(data)
    elif OUT.exists():
        assert OUT.read_bytes() == data
    print(json.dumps({"records": len(doc["records"]), "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(), "written": args.write}, sort_keys=True))
