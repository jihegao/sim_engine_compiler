"""Explicit byte custody for root's one SSH0 helper test and pure method audit.

Default is read-only. --write makes the first owned copies and map exactly once.
The original tmp paths remain distinct, optional-if-present historical identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "helper-root-custody.json"
SOURCES = (
    "tmp/i03-var06-helper-ssh0-proof-20261008.py",
    "tmp/i03-var06-helper-ssh0-proof-20261008/guard-before-stderr.bin",
    "tmp/i03-var06-helper-ssh0-proof-20261008/guard-before-stdout.bin",
    "tmp/i03-var06-helper-ssh0-proof-20261008/helper-test-stderr.bin",
    "tmp/i03-var06-helper-ssh0-proof-20261008/helper-test-stdout.bin",
    "tmp/i03-var06-helper-ssh0-proof-20261008/receipt.json",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/async-drain-error-large.stderr.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/async-drain-error-large.stdout.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/drain-setup-error.stderr.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/drain-setup-error.stdout.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/exit0.stderr.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/exit0.stdout.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/exit7.stderr.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/exit7.stdout.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/observed-error.stderr.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/observed-error.stdout.bin",
    "tmp/i03-var06-helper-ssh0-fixture-20261008/receipt.json",
    "tmp/i03-var06-helper-existing-proof-audit-20261008.py",
    "tmp/i03-var06-helper-existing-proof-audit-20261008/guard-after-stderr.bin",
    "tmp/i03-var06-helper-existing-proof-audit-20261008/guard-after-stdout.bin",
    "tmp/i03-var06-helper-existing-proof-audit-20261008/receipt.json",
    "tmp/i03-var06-root-independent-pure-20261008.py",
    "tmp/i03-var06-root-independent-pure-20261008/control-only-stderr.bin",
    "tmp/i03-var06-root-independent-pure-20261008/control-only-stdout.bin",
    "tmp/i03-var06-root-independent-pure-20261008/mutation-probes-stderr.bin",
    "tmp/i03-var06-root-independent-pure-20261008/mutation-probes-stdout.bin",
    "tmp/i03-var06-root-independent-pure-20261008/receipt.json",
)


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def records() -> list[dict]:
    result = []
    for original in SOURCES:
        source = REPO / original
        assert source.is_file(), original
        owned = "preserved-helper-context/" + original.replace("/", "__")
        result.append({"original_path": original, "owned_copy": owned,
                       **seal(source.read_bytes()), "original_if_present_must_match": True})
    return result


def verify() -> dict:
    doc = json.loads(MAP.read_text(encoding="utf-8"))
    assert doc["schema"] == "i03-var06-helper-root-custody/v1"
    assert [x["original_path"] for x in doc["records"]] == list(SOURCES)
    assert len(doc["records"]) == 27
    for item in doc["records"]:
        expected = {k: item[k] for k in ("bytes", "sha256")}
        assert item["original_if_present_must_match"] is True
        assert seal((HERE / item["owned_copy"]).read_bytes()) == expected
        original = REPO / item["original_path"]
        if original.exists():
            assert seal(original.read_bytes()) == expected
    return {"schema": "i03-var06-helper-root-custody-check/v1", "passed": True,
            "records": len(doc["records"]), "original_tmp_required": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        assert not MAP.exists() and not (HERE / "preserved-helper-context").exists()
        items = records()
        for item in items:
            target = HERE / item["owned_copy"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / item["original_path"]).read_bytes())
        MAP.write_bytes((json.dumps({"schema": "i03-var06-helper-root-custody/v1",
                                    "records": items}, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(verify(), ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
