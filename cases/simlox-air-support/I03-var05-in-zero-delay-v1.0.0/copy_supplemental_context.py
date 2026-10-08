"""Preserve additional root and independent postrun proofs as inert bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "supplemental-context-custody.json"
DEST = HERE / "preserved-supplemental-context"
FILES = (
    "tmp/i03-var05-independent-postrun-audit-20261008.py",
    "tmp/i03-var05-independent-postrun-audit-proof-20261008.py",
    "tmp/i03-var05-independent-postrun-audit-proof-20261008-01/stdout.bin",
    "tmp/i03-var05-independent-postrun-audit-proof-20261008-01/stderr.bin",
    "tmp/i03-var05-independent-postrun-audit-proof-20261008-01/receipt.json",
    "tmp/i03-var05-independent-postappend-replay-20261008.py",
    "tmp/i03-var05-independent-postappend-replay-20261008-01/stdout.bin",
    "tmp/i03-var05-independent-postappend-replay-20261008-01/stderr.bin",
    "tmp/i03-var05-independent-postappend-replay-20261008-01/receipt.json",
    "tmp/issue18-next-owner-guard-20261008.ps1",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def verify() -> dict:
    doc = json.loads(MAP.read_bytes())
    assert doc["schema"] == "i03-var05-supplemental-context-custody/v1"
    rows = doc["records"]
    assert len(rows) == len(FILES)
    for index, row in enumerate(rows):
        assert row["original_path"] == str((REPO / FILES[index]).resolve(strict=False))
        assert row["owned_copy"] == f"preserved-supplemental-context/s{index+1:03d}.bytes"
        wanted = {key: row[key] for key in ("bytes", "sha256")}
        assert pin((HERE / row["owned_copy"]).read_bytes()) == wanted
        original = Path(row["original_path"])
        if original.exists():
            assert pin(original.read_bytes()) == wanted
    return {"schema": doc["schema"], "records": len(rows)}


def write() -> dict:
    assert not MAP.exists() and not DEST.exists()
    originals = [REPO / name for name in FILES]
    assert all(path.is_file() for path in originals)
    rows = []
    for index, path in enumerate(originals, 1):
        rows.append({"original_path": str(path.resolve(strict=True)),
                     "owned_copy": f"preserved-supplemental-context/s{index:03d}.bytes",
                     "original_if_present_must_match": True, **pin(path.read_bytes())})
    DEST.mkdir()
    for row, path in zip(rows, originals, strict=True):
        (HERE / row["owned_copy"]).write_bytes(path.read_bytes())
    doc = {"schema": "i03-var05-supplemental-context-custody/v1", "records": rows,
           "original_tmp_paths_optional_after_publication": True,
           "accepted_and_child_original_raw_remain_mandatory": True}
    MAP.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    verify()
    return {"schema": doc["schema"], "records": len(rows), "map": pin(MAP.read_bytes())}


if __name__ == "__main__":
    assert sys.argv[1:] in ([], ["--write"])
    print(json.dumps(write() if sys.argv[1:] else verify(), sort_keys=True))
