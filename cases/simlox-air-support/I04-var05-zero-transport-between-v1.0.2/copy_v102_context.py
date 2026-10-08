"""Exact owned copies of the v102 contract and root method history."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from model_common import encode, pin, read, verify_expected

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEST = HERE / "preserved-v102-context"
MAP = HERE / "v102-context-custody.json"
SOURCES = (
    "tmp/i04-var05-prospective-recovery-v102-20261008.json",
    "tmp/i04-var05-prospective-recovery-v102-revision2-20261008.json",
    "tmp/i04-var05-recovery-design-v102-20261008.py",
    "tmp/i04-var05-recovery-design-v102-revision2-20261008.py",
    "tmp/i04-var05-recovery-design-capture-v102-20261008.py",
    "tmp/i04-var05-recovery-design-capture-v102-revision2-20261008.py",
    "tmp/i04-var05-independent-recovery-contract-audit-v102-revision2-20261008.py",
    "tmp/i04-var05-independent-recovery-contract-capture-v102-revision2-20261008.py",
    "tmp/i04-var05-independent-recovery-contract-go-v102-revision2-20261008.md",
    "tmp/i04-var05-root-phase-capture-v102-20261008.py",
    "tmp/i04-var05-root-fresh-guard-v102-20261008.py",
    "tmp/i04-var05-recovery-design-proof-v102-20261008-01/receipt.json",
    "tmp/i04-var05-recovery-design-proof-v102-20261008-01/stdout.bin",
    "tmp/i04-var05-recovery-design-proof-v102-20261008-01/stderr.bin",
    "tmp/i04-var05-recovery-design-proof-v102-revision2-20261008-01/receipt.json",
    "tmp/i04-var05-recovery-design-proof-v102-revision2-20261008-01/stdout.bin",
    "tmp/i04-var05-recovery-design-proof-v102-revision2-20261008-01/stderr.bin",
    "tmp/i04-var05-independent-recovery-contract-proof-v102-revision2-20261008-01/receipt.json",
    "tmp/i04-var05-independent-recovery-contract-proof-v102-revision2-20261008-01/stdout.bin",
    "tmp/i04-var05-independent-recovery-contract-proof-v102-revision2-20261008-01/stderr.bin",
)
FIXED = {
    0: {"bytes": 921609, "sha256": "7277ad06355d45d729fe867800a571612c765ca4ff0d47cc91a68e4da33af491"},
    1: {"bytes": 922508, "sha256": "2353d18f907803c9023089e70202e7381cad266a0b8c7795bf98586ee067f292"},
    8: {"bytes": 3762, "sha256": "090904a928ee7929d8a76b5ca1ace63e9c08db661e9cbdaa925a1f567b87e0e4"},
    9: {"bytes": 6508, "sha256": "5125e0f63f4a33d4cbcc0c48974dbe2c4a3f90357e5d889d7764cc46d946fe8e"},
    10: {"bytes": 3427, "sha256": "fc36fadd47ba1bb1c09ef28df219e1ff33aa4a4493a5942dac0a76b860e03361"},
}


def expected_record(index: int, original: Path) -> dict:
    return {"original_path": str(original),
            "original_relative_path": SOURCES[index],
            "owned_copy": f"preserved-v102-context/context-{index:03d}.bytes",
            **pin(original), "original_if_present_must_match": True}


def write() -> dict:
    assert not MAP.exists()
    DEST.mkdir(exist_ok=False)
    rows = []
    for index, relative in enumerate(SOURCES):
        source = REPO / relative
        assert source.is_file(), relative
        row = expected_record(index, source)
        verify_expected(HERE / row["owned_copy"], source.read_bytes(), True)
        rows.append(row)
    document = {"schema": "i04-var05-v102-context-custody/v1",
                "records": rows, "record_count": len(rows),
                "originals_optional_after_publication": True,
                "scope": "safe recovery and construction history only; no private app snapshot"}
    verify_expected(MAP, encode(document), True)
    return verify()


def verify() -> dict:
    document = read(MAP)
    assert set(document) == {"schema", "records", "record_count",
                             "originals_optional_after_publication", "scope"}
    assert document["schema"] == "i04-var05-v102-context-custody/v1"
    assert document["scope"] == "safe recovery and construction history only; no private app snapshot"
    assert document["originals_optional_after_publication"] is True
    assert type(document["record_count"]) is int and document["record_count"] == len(SOURCES)
    rows = document["records"]
    assert len(rows) == len(SOURCES)
    for index, row in enumerate(rows):
        assert set(row) == {"original_path", "original_relative_path", "owned_copy",
                            "bytes", "sha256", "original_if_present_must_match"}
        assert row["original_relative_path"] == SOURCES[index]
        assert row["owned_copy"] == f"preserved-v102-context/context-{index:03d}.bytes"
        assert row["original_if_present_must_match"] is True
        assert type(row["bytes"]) is int and row["bytes"] >= 0
        assert type(row["sha256"]) is str and len(row["sha256"]) == 64
        assert all(ch in "0123456789abcdef" for ch in row["sha256"])
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        if index in FIXED:
            assert expected == FIXED[index]
        assert pin(HERE / row["owned_copy"]) == expected
        original = Path(row["original_path"])
        if original.is_file():
            assert pin(original) == expected
    return {"schema": document["schema"], "copies": len(rows), "map": pin(MAP)}


if __name__ == "__main__":
    assert sys.argv[1:] in ([], ["--write"])
    print(json.dumps(write() if sys.argv[1:] else verify(), sort_keys=True))
