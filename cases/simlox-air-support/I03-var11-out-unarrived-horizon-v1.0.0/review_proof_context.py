"""Exact owned copies of small v2 independent postrun proof, read-only by default."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "preserved-independent-postrun-proof"
MAP = HERE / "independent-postrun-proof-custody.json"
ORIGINALS = (
    "tmp/i03-var11-independent-postrun-proof-v2/receipt.json",
    "tmp/i03-var11-independent-postrun-proof-v2/replay.stdout.bin",
    "tmp/i03-var11-independent-postrun-proof-v2/replay.stderr.bin",
    "tmp/i03-var11-independent-postrun-proof-v2/selfcheck.stdout.bin",
    "tmp/i03-var11-independent-postrun-proof-v2/selfcheck.stderr.bin",
    "tmp/i03-var11-independent-postrun-v2-receipt-probes-20261008.py",
    "tmp/i03-var11-independent-postrun-v2-receipt-probe-proof/receipt.json",
    "tmp/i03-var11-independent-postrun-v2-receipt-probe-proof/stdout.bin",
    "tmp/i03-var11-independent-postrun-v2-receipt-probe-proof/stderr.bin",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check() -> dict:
    rows = json.loads(MAP.read_text(encoding="utf-8"))["records"]
    assert len(rows) == len(ORIGINALS)
    for i, (row, original) in enumerate(zip(rows, ORIGINALS)):
        assert row["original"] == original
        assert row["owned_copy"] == f"preserved-independent-postrun-proof/{i:02d}-{Path(original).name}.bytes"
        expected = {key: row[key] for key in ("bytes", "sha256")}
        assert pin((HERE / row["owned_copy"]).read_bytes()) == expected
        path = REPO / original
        if path.exists():
            assert pin(path.read_bytes()) == expected
    return {"schema": "i03-var11-independent-postrun-proof-check/v1", "passed": True,
            "records": len(rows), "native_started": False}


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    if sys.argv[1:] == ["--write"]:
        assert not MAP.exists() and not OUT.exists()
        OUT.mkdir()
        rows = []
        for i, original in enumerate(ORIGINALS):
            data = (REPO / original).read_bytes()
            owned = f"preserved-independent-postrun-proof/{i:02d}-{Path(original).name}.bytes"
            (HERE / owned).write_bytes(data)
            rows.append({"original": original, "owned_copy": owned, **pin(data)})
        MAP.write_bytes((json.dumps({"schema": "i03-var11-independent-postrun-proof/v1",
                                     "records": rows}, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(check(), separators=(",", ":")))


if __name__ == "__main__":
    main()
