"""Exact owned copies of safe recovery-review and construction proof history."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from model_common import encode, pin, read, verify_expected

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEST = HERE / "preserved-extra"
MAP = HERE / "extra-context-custody.json"
SOURCES = (
    "tmp/i04-var05-recovery-design-v101-revision2-20261008.py",
    "tmp/i04-var05-recovery-contract-proof-v101-revision2-20261008-01/receipt.json",
    "tmp/i04-var05-recovery-contract-proof-v101-revision2-20261008-01/stdout.bin",
    "tmp/i04-var05-recovery-contract-proof-v101-revision2-20261008-01/stderr.bin",
    "tmp/i04-var05-independent-recovery-contract-audit-v2-20261008.py",
    "tmp/i04-var05-independent-recovery-contract-capture-v2-20261008.py",
    "tmp/i04-var05-independent-recovery-contract-proof-v2-20261008-01/receipt.json",
    "tmp/i04-var05-independent-recovery-contract-proof-v2-20261008-01/stdout.bin",
    "tmp/i04-var05-independent-recovery-contract-proof-v2-20261008-01/stderr.bin",
    "tmp/i04-var05-independent-recovery-contract-go-v101-20261008.md",
    "tmp/i04-var05-v101-author-context-capture-20261008-01/receipt.json",
    "tmp/i04-var05-v101-author-context-capture-20261008-01/stdout.bin",
    "tmp/i04-var05-v101-author-context-capture-20261008-01/stderr.bin",
    "tmp/i04-var05-v101-author-build-capture-20261008-01/receipt.json",
    "tmp/i04-var05-v101-author-build-capture-20261008-01/stdout.bin",
    "tmp/i04-var05-v101-author-build-capture-20261008-01/stderr.bin",
    "tmp/i04-var05-v101-source-gate-probe-20261008-01/receipt.json",
    "tmp/i04-var05-v101-source-gate-probe-20261008-01/stdout.bin",
    "tmp/i04-var05-v101-source-gate-probe-20261008-01/stderr.bin",
    "tmp/i04-var05-v101-source-gate-probe-20261008-02/receipt.json",
    "tmp/i04-var05-v101-source-gate-probe-20261008-02/stdout.bin",
    "tmp/i04-var05-v101-source-gate-probe-20261008-02/stderr.bin",
)


def expected_record(index: int, original: Path) -> dict:
    return {"original_path": str(original),
            "original_relative_path": SOURCES[index],
            "owned_copy": f"preserved-extra/extra-{index:03d}.bytes",
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
    document = {"schema": "i04-var05-v101-extra-context-custody/v1",
                "records": rows, "record_count": len(rows),
                "originals_optional_after_publication": True,
                "scope": "safe recovery and construction history only; no private app snapshot"}
    verify_expected(MAP, encode(document), True)
    return verify()


def verify() -> dict:
    document = read(MAP)
    assert set(document) == {"schema", "records", "record_count",
                             "originals_optional_after_publication", "scope"}
    assert document["schema"] == "i04-var05-v101-extra-context-custody/v1"
    assert document["scope"] == "safe recovery and construction history only; no private app snapshot"
    assert document["originals_optional_after_publication"] is True
    assert type(document["record_count"]) is int and document["record_count"] == len(SOURCES)
    rows = document["records"]
    assert len(rows) == len(SOURCES)
    for index, row in enumerate(rows):
        assert set(row) == {"original_path", "original_relative_path", "owned_copy",
                            "bytes", "sha256", "original_if_present_must_match"}
        assert row["original_relative_path"] == SOURCES[index]
        assert row["owned_copy"] == f"preserved-extra/extra-{index:03d}.bytes"
        assert row["original_if_present_must_match"] is True
        assert type(row["bytes"]) is int and row["bytes"] >= 0
        assert type(row["sha256"]) is str and len(row["sha256"]) == 64
        assert all(ch in "0123456789abcdef" for ch in row["sha256"])
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert pin(HERE / row["owned_copy"]) == expected
        original = Path(row["original_path"])
        if original.is_file():
            assert pin(original) == expected
    return {"schema": document["schema"], "copies": len(rows), "map": pin(MAP)}


if __name__ == "__main__":
    assert sys.argv[1:] in ([], ["--write"])
    print(json.dumps(write() if sys.argv[1:] else verify(), sort_keys=True))
