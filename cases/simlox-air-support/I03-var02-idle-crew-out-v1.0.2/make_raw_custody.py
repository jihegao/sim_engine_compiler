"""Rebuild or verify named, original-path run byte seals without copying raw files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/i03-var02-idle-out-v102-ssh-20261007-01"
MAP = HERE / "raw-custody-map.json"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def expected_records() -> list[dict]:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    records = []
    for item in contract["source_lineage"]["accepted_original_run_records"]:
        records.append({"role": "accepted_busy_parent_or_dependency", "original_path": item["path"],
                        "bytes": item["bytes"], "sha256": item["sha256"]})
    for name in sorted(closure["raw"]):
        item = closure["raw"][name]
        records.append({"role": "sealed_v102_child_raw", "original_path": str(RUN / name),
                        "bytes": item["bytes"], "sha256": item["sha256"]})
    for name in ("invocation.json", "closure.json"):
        path = RUN / name
        records.append({"role": "sealed_v102_child_custody", "original_path": str(path), **pin(path)})
    assert len(records) == 59
    assert len({r["original_path"] for r in records}) == len(records)
    return records


def build(write: bool) -> dict:
    records = expected_records()
    for item in records:
        assert pin(Path(item["original_path"])) == {k: item[k] for k in ("bytes", "sha256")}, item
    doc = {"schema": "i03-var02-v102-raw-custody/v1", "records": records,
           "raw_location_policy": "The 34 accepted parent/context and 25 sealed child run files remain at their original paths. This package pins them and contains no raw or native binary copy. Restore exact original bytes to the named paths before replay; no synthetic substitute or native rerun."}
    data = (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if write:
        with MAP.open("xb") as stream:
            stream.write(data)
    else:
        assert MAP.read_bytes() == data
    return {"schema": "i03-var02-v102-raw-custody-check/v1", "passed": True,
            "records": len(records), "accepted_context": 34, "sealed_child": 25,
            "map_sha256": hashlib.sha256(data).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="create map only if absent")
    args = parser.parse_args()
    print(json.dumps(build(args.write), sort_keys=True, separators=(",", ":")))
