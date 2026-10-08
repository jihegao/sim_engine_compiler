"""Pin the fifteen zero-native SSH preflight originals separately."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEAL = REPO / "tmp/i04-var05-root-preflight-seal-v102-20261008/20261008T102656688149Z-0568f260/receipt.json"
OUT = HERE / "preflight-custody-map.json"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def candidate() -> dict:
    seal = json.loads(SEAL.read_bytes())
    assert seal["original_count"] == len(seal["original_files"]) == 15
    rows = []
    for item in seal["original_files"]:
        path = Path(item["path"])
        identity = pin(path)
        assert identity == {k: item[k] for k in ("bytes", "sha256")}
        rows.append({"path": str(path), **identity, "role": "zero_native_preflight",
                     "original_mandatory": True, "owned_copy": None})
    assert len({r["path"].casefold() for r in rows}) == 15
    return {"schema": "i04-var05-v102-preflight-custody/v1",
            "mandatory_original_count": 15,
            "preflight_seal_receipt": {"path": str(SEAL), **pin(SEAL)},
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
    print(json.dumps({"schema": value["schema"], "records": 15,
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
