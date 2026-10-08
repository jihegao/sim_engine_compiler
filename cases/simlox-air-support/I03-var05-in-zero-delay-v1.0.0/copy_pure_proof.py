"""Preserve both original author PURE proof streams, including the first failure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
DEST = HERE / "preserved-pure-proof"
MAP = HERE / "pure-proof-custody.json"
MAP_SHA = "b6c89d87f373abd477f16bd080e398fb111970edf9e7ae5ce14b6f5d213144ad"
PROOFS = (
    ("pure-proof-20261008T010430744267Z-da4b86e5", "83ec4df8b2e60619b8c3711b74d1024f8bd6062a6a57251cb1d46c3b9ec4b8d0"),
    ("pure-proof-20261008T010544172605Z-5120dd48", "a182eb64923de89ba3bd9568e550d57ff4dcb0d9ea8f2e5b280246d346772b0d"),
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(*, write: bool = False) -> dict:
    if write:
        DEST.mkdir(exist_ok=True)
    expected_rows = None
    if not write:
        assert pin(MAP.read_bytes())["sha256"] == MAP_SHA
        expected_rows = {row["owned_copy"]: row for row in json.loads(MAP.read_bytes())["records"]}
    rows = []
    for proof_number, (directory, receipt_sha) in enumerate(PROOFS, 1):
        source = HERE / "test-output" / directory
        original_receipt = source / "receipt.json"
        owned_receipt = DEST / f"p{proof_number:01d}-01.bytes"
        receipt_data = original_receipt.read_bytes() if write else owned_receipt.read_bytes()
        assert pin(receipt_data)["sha256"] == receipt_sha
        receipt = json.loads(receipt_data)
        assert receipt["schema"] == "i03-var05-author-pure-proof/v1"
        assert receipt["all_exits_zero"] is (proof_number == 2)
        named = ["receipt.json"] + [f"{step['name']}.{stream}.bin" for step in receipt["steps"]
                                      for stream in ("stdout", "stderr")]
        assert len(named) == len(set(named))
        for file_number, name in enumerate(named, 1):
            original = source / name
            owned = DEST / f"p{proof_number:01d}-{file_number:02d}.bytes"
            wanted = pin(original.read_bytes()) if write else pin(owned.read_bytes())
            if write:
                assert not owned.exists(), owned
                owned.write_bytes(original.read_bytes())
            assert pin(owned.read_bytes()) == wanted
            if original.exists():
                assert pin(original.read_bytes()) == wanted, original
            rows.append({"original_path": str(original), "owned_copy": owned.relative_to(HERE).as_posix(),
                         "original_if_present_must_match": True, **wanted})
            if expected_rows is not None:
                assert rows[-1] == expected_rows[rows[-1]["owned_copy"]]
    return {"schema": "i03-var05-author-pure-proof-custody/v1", "records": rows,
            "first_proof": "NO_GO_PURE_TEST_HARNESS; converter subprocess could not resolve Get-FileHash; original stderr captured",
            "second_proof": "PASS_PURE; seven subprocesses actual exit0 and original stderr empty",
            "native_calls": 0}


def main() -> None:
    write = sys.argv[1:] == ["--write"]
    assert not sys.argv[1:] or write
    result = candidate(write=write)
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if MAP.exists():
        assert MAP.read_bytes() == data
    else:
        assert write
        MAP.write_bytes(data)
    print(json.dumps({"schema": result["schema"], "records": len(result["records"]), "map": pin(data)}, sort_keys=True))


if __name__ == "__main__":
    main()
