"""Pin all actual zero-native SSH preflight originals at their host paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import encode, pin, read, verify_expected
from source_gate import HERE, REPO

MAP = HERE / "preflight-custody-map.json"
SEAL = REPO / "tmp/i04-var03-root-preflight-seal-v101-20261008/20261008T054623786660Z-cd430084/receipt.json"
SEAL_PIN = {"bytes": 6053, "sha256": "cd38668a8f31f2946995ab78dde5339ed7af327994a2bcce64c6fd1aa9b178e9"}


def candidate():
    assert pin(SEAL) == SEAL_PIN
    source = read(SEAL)
    assert source["original_count"] == len(source["original_files"]) == 15
    records = []
    for row in source["original_files"]:
        path = Path(row["path"]).resolve(strict=True)
        expected = {key: row[key] for key in ("bytes", "sha256")}
        assert path.is_file() and pin(path) == expected
        records.append({"path": str(path), **expected, "role": "preflight_original",
                        "original_mandatory": True, "owned_copy": None})
    assert len({row["path"].lower() for row in records}) == 15
    return {"schema": "i04-var03-v101-preflight-custody/v1",
            "mandatory_original_count": 15,
            "preflight_seal_receipt": {"path": str(SEAL), **SEAL_PIN},
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
