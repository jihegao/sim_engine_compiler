"""Freeze an E05.var01 child with only local ItemRepair.DIRPT changed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E05-local-repair-reissue-v1.0.0" / "native-input.json"
OUTPUT = HERE / "native-input.json"
PARENT_SHA256 = "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build() -> bytes:
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256, "accepted E05 parent input differs"
    document = json.loads(parent_raw)
    tables = document["model"]["tables"]
    assert len(tables) == 31
    repair = next(table for table in tables if table["name"] == "ItemRepair")
    columns = [column["name"] for column in repair["columns"]]
    assert columns == [
        "IID", "STID", "DIRPT", "SURPT", "DIRPF", "SURPF", "DIRPM", "SURPM",
        "DIRPC", "SURPC", "UDPER", "DIRPTID", "SURPTID", "DIRPD", "SURPD", "NOTE",
    ]
    rows = repair["instances"][0]["rows"]
    assert rows == [["TEACH-LRU-01", "BASE-01", 1.0, 0.0, 1.0, 1.0,
                     None, None, None, None, None, None, None, None, None, None]]
    rows[0][2] = 13.0
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    raw = build()
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == raw, "frozen E05.var01 child differs"
    else:
        OUTPUT.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA256, "child_sha256": sha(raw), "bytes": len(raw)}))
