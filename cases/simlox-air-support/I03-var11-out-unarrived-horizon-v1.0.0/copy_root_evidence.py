"""Copy declared small construction receipts once; default verifies owned bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "root-evidence-custody.json"
FILES = (
    "tmp/build-i03-var11-contract-draft-v1-failed-key-20261008.py.bytes",
    "tmp/build-i03-var11-contract-draft-v1-20261008.py",
    "tmp/revise-i03-var11-contract-draft-v2-20261008.py",
    "tmp/revise-i03-var11-contract-draft-v3-20261008.py",
    "tmp/revise-i03-var11-contract-draft-v4-20261008.py",
    "tmp/i03-var11-prospective-contract-draft-v1-20261008.json",
    "tmp/i03-var11-prospective-contract-draft-v2-20261008.json",
    "tmp/i03-var11-prospective-contract-draft-v3-20261008.json",
    "tmp/i03-var11-model-lineage-draft-v1-20261008.md",
    "tmp/i03-var11-model-lineage-draft-v2-20261008.md",
    "tmp/i03-var11-root-selection-20261008.py",
    "tmp/i03-var11-live-selection-api-20261008.json",
    "tmp/i03-var11-root-contract-freeze-v3-20261008.py",
    "tmp/i03-var11-root-contract-freeze-v3-20261008.json",
    "tmp/i03-var11-root-contract-freeze-v4-20261008.py",
    "tmp/i03-var11-root-contract-freeze-v4-20261008.json",
    "tmp/i03-var11-root-input-delta-20261008.py",
    "tmp/i03-var11-root-input-delta-v2-20261008.py",
    "tmp/i03-var11-root-input-delta-v2-20261008.json",
    "tmp/i03-var11-independent-contract-audit-v4-20261008.py",
    "tmp/i03-var11-independent-contract-audit-v4-20261008.stdout",
    "tmp/i03-var11-independent-contract-audit-v4-20261008.stderr",
    "tmp/i03-var11-independent-contract-go-v4-20261008.md",
    "tmp/i03-var11-independent-contract-audit-v4-draft1-20261008.py",
    "tmp/i03-var11-independent-contract-audit-v4-draft1.stdout",
    "tmp/i03-var11-independent-contract-audit-v4-draft1.stderr",
    "tmp/i03-var11-independent-contract-audit-v4-draft2-20261008.py",
    "tmp/i03-var11-independent-contract-audit-v4-draft2.stdout",
    "tmp/i03-var11-independent-contract-audit-v4-draft2.stderr",
    "tmp/i03-var11-independent-contract-audit-v4-draft3-20261008.py",
    "tmp/i03-var11-independent-contract-audit-v4-draft3.stdout",
    "tmp/i03-var11-independent-contract-audit-v4-draft3.stderr",
    "tmp/i03-var11-independent-contract-audit-v4-draft4-20261008.py",
    "tmp/i03-var11-independent-contract-audit-v4-draft4.stdout",
    "tmp/i03-var11-independent-contract-audit-v4-draft4.stderr",
    "tmp/i03-var11-independent-contract-audit-v4-draft5-20261008.py",
    "tmp/i03-var11-independent-contract-audit-v4-draft5.stdout",
    "tmp/i03-var11-independent-contract-audit-v4-draft5.stderr",
)


def seal(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def copy_name(original: str) -> str:
    return "preserved-root-evidence/" + original.replace("/", "__").replace("\\", "__") + ".bytes"


def verify() -> dict:
    document = json.loads(MAP.read_text(encoding="utf-8"))
    assert document["schema"] == "i03-var11-root-evidence-custody/v1"
    assert [row["original_path"] for row in document["records"]] == list(FILES)
    for row in document["records"]:
        assert row["owned_copy"] == copy_name(row["original_path"])
        wanted = {key: row[key] for key in ("bytes", "sha256")}
        assert seal((HERE / row["owned_copy"]).read_bytes()) == wanted
        original = REPO / row["original_path"]
        if original.exists():
            assert seal(original.read_bytes()) == wanted
    return {"schema": "i03-var11-root-evidence-custody-check/v1", "passed": True,
            "owned_context_records": len(FILES), "original_tmp_required_if_absent": False}


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    if sys.argv[1:] == ["--write"]:
        assert not MAP.exists(), "custody map already exists"
        rows = []
        for original in FILES:
            data = (REPO / original).read_bytes()
            copy = copy_name(original)
            destination = HERE / copy
            destination.parent.mkdir(parents=True, exist_ok=True)
            assert not destination.exists()
            destination.write_bytes(data)
            rows.append({"original_path": original, "owned_copy": copy,
                         "original_if_present_must_match": True, **seal(data)})
        MAP.write_bytes((json.dumps({"schema": "i03-var11-root-evidence-custody/v1",
                                    "records": rows}, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(verify(), separators=(",", ":")))


if __name__ == "__main__":
    main()
