"""Exact original zero-native SSH preflight transport custody; default verifies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
DIRECTORY = HERE / "transport-evidence/ssh-preflight-20261008T012917878040Z-af3006e6"
FILES = ("ssh-stdout.bin", "ssh-stderr.bin", "transport-receipt.json")
MAP = HERE / "preflight-transport-custody.json"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    rows = []
    for name in FILES:
        path = DIRECTORY / name
        rows.append({"role": "zero_native_preflight_transport_original",
                     "path": str(path.resolve(strict=True)), **pin(path.read_bytes())})
    assert len({row["path"].lower() for row in rows}) == 3
    return {"schema": "i03-var05-preflight-transport-original-custody/v1",
            "original_count": 3, "native_child_started": False,
            "records": rows, "copies_cannot_substitute_for_originals": True}


def body(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--write"])
    data = body(candidate())
    if args == ["--write"]:
        assert not MAP.exists()
        MAP.write_bytes(data)
    elif args == []:
        assert MAP.read_bytes() == data
    print(json.dumps({"schema": "i03-var05-preflight-transport-original-custody/v1",
                      "originals": 3, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"]}, sort_keys=True))


if __name__ == "__main__":
    main()
