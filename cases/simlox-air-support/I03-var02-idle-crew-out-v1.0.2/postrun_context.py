"""Preserve and verify exact root context bytes without publishing native raw runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "postrun-context-custody.json"
SOURCE_NAMES = (
    "tmp/i03-var02-v102-root-contract-freeze-v2-20261007.json",
    "tmp/freeze-i03-var02-v102-contract-v2-20261007.py",
    "tmp/i03-var02-v102-root-bundle-freeze-20261007.json",
    "tmp/freeze-i03-var02-v102-bundle-20261007.py",
    "tmp/i03-var02-v102-actual-preflight-failure-20261007.json",
    "tmp/i03-var02-root-actual-preflight-check-20261007.json",
    "tmp/check-i03-actual-preflight-20261007.py",
    "tmp/i03-var02-root-owner-refresh-v2-20261007.json",
    "tmp/i03-guard-transport-diagnostic-20261007.json",
    "tmp/i03-v102-root-launch-context-20261007.json",
    "tmp/i03-v102-root-native-seal-20261007.json",
    "tmp/seal-i03-v102-native-20261007.py",
    "tmp/i03-ssh-transport-v1-20261007.py",
    "tmp/i03-ssh-transport-v1-preflight-20261007-01/transport-receipt.json",
    "tmp/i03-ssh-transport-v1-preflight-20261007-01/ssh-stdout.bin",
    "tmp/i03-ssh-transport-v1-preflight-20261007-01/ssh-stderr.bin",
    "tmp/i03-ssh-transport-v1-native-20261007-01/transport-receipt.json",
    "tmp/i03-ssh-transport-v1-native-20261007-01/ssh-stdout.bin",
    "tmp/i03-ssh-transport-v1-native-20261007-01/ssh-stderr.bin",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def custody(write: bool = False) -> dict:
    if write:
        assert not MAP.exists(), "custody map exists; preserve it and use read-only verification"
        records = []
        for name in SOURCE_NAMES:
            original = REPO / name
            data = original.read_bytes()
            copy_name = "preserved-postrun-context/" + name.removeprefix("tmp/")
            copy = HERE / copy_name
            copy.parent.mkdir(parents=True, exist_ok=True)
            with copy.open("xb") as stream:
                stream.write(data)
            records.append({"original_path": name, "copy_path": copy_name, **pin(data)})
        MAP.write_bytes((json.dumps({"schema": "i03-var02-v102-postrun-context/v1", "records": records},
                                    sort_keys=True, indent=2) + "\n").encode("utf-8"))
    doc = json.loads(MAP.read_text(encoding="utf-8"))
    assert doc["schema"] == "i03-var02-v102-postrun-context/v1"
    assert [r["original_path"] for r in doc["records"]] == list(SOURCE_NAMES)
    for record in doc["records"]:
        expected = {key: record[key] for key in ("bytes", "sha256")}
        assert pin((HERE / record["copy_path"]).read_bytes()) == expected, record
        original = REPO / record["original_path"]
        if original.exists():
            assert pin(original.read_bytes()) == expected, record
    return {"schema": "i03-var02-v102-postrun-context-check/v1", "passed": True,
            "byte_identical_copies": len(doc["records"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--copy", action="store_true", help="one-time copy, only when map is absent")
    args = parser.parse_args()
    print(json.dumps(custody(args.copy), sort_keys=True, separators=(",", ":")))
