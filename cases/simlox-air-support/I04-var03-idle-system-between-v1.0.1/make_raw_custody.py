"""Seal mandatory accepted and new native originals without copying bulky raw files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import encode, pin, read, verify_expected
from source_gate import HERE, REPO, RUN_ID

MAP = HERE / "raw-custody-map.json"
RUN = HERE / "runs" / RUN_ID
NATIVE_SEAL = REPO / "tmp/i04-var03-root-native-transport-seal-v101-20261008/20261008T065353412074Z-88343646/receipt.json"
NATIVE_SEAL_PIN = {"bytes": 5670, "sha256": "be0158f9d884026952c0e519ed6650d83b8bb49658d5aea8a176498eb567f35d"}


def item(path, expected, role):
    absolute = path.resolve(strict=True)
    assert absolute.is_file() and pin(absolute) == expected
    return {"path": str(absolute), **expected, "role": role,
            "original_mandatory": True, "owned_copy": None}


def candidate():
    selection = read(HERE / "preserved-context/root-selection.json")
    accepted = [item(Path(row["path"]), {k: row[k] for k in ("bytes", "sha256")},
                     "accepted_context") for row in selection["mandatory_original_raw"]]
    assert len(accepted) == 114
    assert RUN.is_dir()
    run_paths = sorted(path for path in RUN.iterdir() if path.is_file())
    assert len(run_paths) == 25
    assert {"invocation.json", "closure.json"} <= {p.name for p in run_paths}
    closure = read(RUN / "closure.json")
    assert len(closure["raw"]) == 23
    assert set(closure["raw"]) == {p.name for p in run_paths} - {"invocation.json", "closure.json"}
    for name, seal in closure["raw"].items():
        assert pin(RUN / name) == {"bytes": seal["bytes"], "sha256": seal["sha256"]}
    run = [item(path, pin(path), "new_child_run") for path in run_paths]
    assert pin(NATIVE_SEAL) == NATIVE_SEAL_PIN
    sealed = read(NATIVE_SEAL)
    assert sealed["original_count"] == len(sealed["original_files"]) == 14
    native = [item(Path(row["path"]), {k: row[k] for k in ("bytes", "sha256")},
                   "native_pure_transport") for row in sealed["original_files"]]
    records = [*accepted, *run, *native]
    assert len(records) == 153
    assert len({r["path"].lower() for r in records}) == 153
    return {"schema": "i04-var03-v101-raw-custody/v1",
            "accepted_context_originals": 114, "new_child_run_originals": 25,
            "native_pure_transport_originals": 14, "mandatory_original_count": 153,
            "native_seal_receipt": {"path": str(NATIVE_SEAL), **NATIVE_SEAL_PIN},
            "records": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = candidate()
    result = verify_expected(MAP, encode(value), args.write)
    assert result["exists"]
    print(json.dumps({"schema": value["schema"], "records": len(value["records"]),
                      "sha256": result["sha256"], "written": args.write,
                      "native_calls": 0}, sort_keys=True))
