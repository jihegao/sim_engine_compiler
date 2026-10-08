"""Hash mandatory original raw files without copying bulky native artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARENT = REPO / "cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1"
RUN = REPO / "tmp/native-runs/i04v05-v102-20261008-01"
SEAL = REPO / "tmp/i04-var05-root-native-transport-seal-v102-20261008/20261008T103340948911Z-e6667db8/receipt.json"
OUT = HERE / "raw-custody-map.json"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def candidate() -> dict:
    parent_raw = json.loads((PARENT / "raw-custody-map.json").read_bytes())["records"]
    parent_pref = json.loads((PARENT / "preflight-custody-map.json").read_bytes())["records"]
    assert len(parent_raw) == 153 and len(parent_pref) == 15
    rows = []
    for row in [*parent_raw, *parent_pref]:
        assert row["original_mandatory"] is True and row["owned_copy"] is None
        path = Path(row["path"])
        assert pin(path) == {k: row[k] for k in ("bytes", "sha256")}
        rows.append({"path": str(path), **pin(path), "role": "accepted_context",
                     "original_mandatory": True, "owned_copy": None})
    new_files = sorted(p for p in RUN.iterdir() if p.is_file())
    assert len(new_files) == 25
    for path in new_files:
        rows.append({"path": str(path), **pin(path), "role": "new_child_run",
                     "original_mandatory": True, "owned_copy": None})
    seal = json.loads(SEAL.read_bytes())
    assert seal["original_count"] == len(seal["original_files"]) == 14
    for row in seal["original_files"]:
        path = Path(row["path"])
        assert pin(path) == {k: row[k] for k in ("bytes", "sha256")}
        rows.append({"path": str(path), **pin(path), "role": "new_native_pure_transport",
                     "original_mandatory": True, "owned_copy": None})
    assert len(rows) == 207
    assert len({r["path"].casefold() for r in rows}) == len(rows)
    return {"schema": "i04-var05-v102-raw-custody/v1",
            "accepted_context_originals": 168, "new_child_run_originals": 25,
            "native_pure_transport_originals": 14,
            "mandatory_original_count": len(rows),
            "native_seal_receipt": {"path": str(SEAL), **pin(SEAL)},
            "records": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = candidate()
    data = encode(value)
    if args.write:
        assert not OUT.exists()
        with OUT.open("xb") as out:
            out.write(data)
    else:
        assert OUT.read_bytes() == data
    print(json.dumps({"schema": value["schema"], "records": len(value["records"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
