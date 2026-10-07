"""Byte-exact custody of small post-freeze root and SSH transport evidence.

Default verifies mandatory owned copies; --write constructs an absent map once.
Original ignored tmp/transport paths are checked when present. Native run files
are deliberately excluded here and remain mandatory at their sealed paths.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "preserved-postrun-context"
MAP = HERE / "postrun-context-custody.json"

ORIGINALS = (
    "tmp/i03-var11-root-source-freeze-20261008/receipt.json",
    "tmp/i03-var11-root-source-freeze-20261008/builder-stdout.bin",
    "tmp/i03-var11-root-source-freeze-20261008/builder-stderr.bin",
    "tmp/i03-var11-root-ssh-preflight-audit-20261008.py",
    "tmp/i03-var11-root-ssh-preflight-audit-20261008.json",
    "tmp/i03-var11-independent-pure-preflight-go-20261008.md",
    "tmp/i03-var11-independent-pure-preflight-audit-v1.py",
    "tmp/i03-var11-independent-pure-preflight-proof-v1/receipt.json",
    "tmp/i03-var11-independent-pure-preflight-proof-v1/stdout.bin",
    "tmp/i03-var11-independent-pure-preflight-proof-v1/stderr.bin",
    "tmp/i03-var11-independent-actual-preflight-audit-20261008.py",
    "tmp/i03-var11-independent-actual-preflight-proof-v1/stdout.bin",
    "tmp/i03-var11-independent-actual-preflight-proof-v1/stderr.bin",
    "tmp/i03-var11-root-native-seal-audit-20261008.py",
    "tmp/i03-var11-root-native-seal-audit-v2-20261008.py",
    "tmp/i03-var11-root-postrun-helper-failure-20261008.json",
    "tmp/i03-var11-root-native-seal-proof-v2-20261008/receipt.json",
    "tmp/i03-var11-root-native-seal-proof-v2-20261008/author-sealed-stdout.bin",
    "tmp/i03-var11-root-native-seal-proof-v2-20261008/author-sealed-stderr.bin",
    "tmp/i03-var11-independent-postrun-execute-20261008.py",
    "tmp/i03-var11-independent-postrun-proof-v1/receipt.json",
    "tmp/i03-var11-independent-postrun-proof-v1/replay.stdout.bin",
    "tmp/i03-var11-independent-postrun-proof-v1/replay.stderr.bin",
    "tmp/i03-var11-independent-postrun-proof-v1/selfcheck.stdout.bin",
    "tmp/i03-var11-independent-postrun-proof-v1/selfcheck.stderr.bin",
    "tmp/i03-var11-prefreeze-live-owner-refs-20261008.json",
    "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/transport-evidence/ssh-preflight-20261007T210704457256Z-c11ed8db/ssh-stdout.bin",
    "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/transport-evidence/ssh-preflight-20261007T210704457256Z-c11ed8db/ssh-stderr.bin",
    "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/transport-evidence/ssh-preflight-20261007T210704457256Z-c11ed8db/transport-receipt.json",
    "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/transport-evidence/ssh-native-20261007T211734078985Z-8348db38/ssh-stdout.bin",
    "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/transport-evidence/ssh-native-20261007T211734078985Z-8348db38/ssh-stderr.bin",
    "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/transport-evidence/ssh-native-20261007T211734078985Z-8348db38/transport-receipt.json",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def verify() -> dict:
    doc = json.loads(MAP.read_text(encoding="utf-8"))
    assert doc["schema"] == "i03-var11-small-postrun-context/v1"
    rows = doc["records"]
    assert len(rows) == len(ORIGINALS)
    for i, (row, original) in enumerate(zip(rows, ORIGINALS)):
        assert row["original"] == original
        assert row["owned_copy"] == f"preserved-postrun-context/{i:02d}-{Path(original).name}.bytes"
        expected = {key: row[key] for key in ("bytes", "sha256")}
        assert pin((HERE / row["owned_copy"]).read_bytes()) == expected
        source = REPO / original
        if source.exists():
            assert pin(source.read_bytes()) == expected
    return {"schema": "i03-var11-small-postrun-context-check/v1", "passed": True,
            "records": len(rows), "native_started": False}


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    if sys.argv[1:] == ["--write"]:
        assert not MAP.exists() and not OUT.exists(), "preserve existing custody bytes"
        OUT.mkdir()
        rows = []
        for i, original in enumerate(ORIGINALS):
            data = (REPO / original).read_bytes()
            owned = f"preserved-postrun-context/{i:02d}-{Path(original).name}.bytes"
            (HERE / owned).write_bytes(data)
            rows.append({"original": original, "owned_copy": owned, **pin(data)})
        MAP.write_bytes((json.dumps({"schema": "i03-var11-small-postrun-context/v1",
                                     "records": rows}, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(verify(), separators=(",", ":")))


if __name__ == "__main__":
    main()
