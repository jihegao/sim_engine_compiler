"""Seal the fifteen actual zero-native preflight originals separately."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
MAP = HERE / "preflight-custody-map.json"
RECEIPT = HERE / "review/preflight-ssh0-20261008T032845886Z.json"
PURE = HERE / "test-output/preflight-pure-20261008T0328302698632Z-b28ebc4c"
TRANSPORT = HERE / "transport-evidence/ssh-preflight-20261008T032827459487Z-ccf27eea"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def body(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def candidate() -> dict:
    paths = [RECEIPT]
    pure_names = sorted(path.name for path in PURE.iterdir() if path.is_file())
    assert len(pure_names) == 11 and "pure-proof.json" in pure_names
    paths.extend(PURE / name for name in pure_names)
    paths.extend(TRANSPORT / name for name in
                 ("ssh-stdout.bin", "ssh-stderr.bin", "transport-receipt.json"))
    assert len(paths) == 15
    rows = [{"role": "zero_native_preflight_original", "path": str(path.resolve(strict=True)),
             **pin(path.read_bytes())} for path in paths]
    assert len({row["path"].lower() for row in rows}) == 15
    return {"schema": "i03-var08-zero-native-preflight-custody/v1",
            "records": rows, "originals_mandatory": True}


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--write"])
    data = body(candidate())
    if args == ["--write"]:
        assert not MAP.exists()
        MAP.write_bytes(data)
    elif args == []:
        assert MAP.read_bytes() == data
    print(json.dumps({"schema": "i03-var08-zero-native-preflight-custody/v1",
                      "records": 15, "bytes": len(data), "sha256": pin(data)["sha256"],
                      "written": args == ["--write"]}, sort_keys=True))


if __name__ == "__main__":
    main()
