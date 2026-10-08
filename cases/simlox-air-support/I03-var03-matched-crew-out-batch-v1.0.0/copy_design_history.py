"""Byte-exact inert custody of prospective design and rejection history."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from source_gate import HERE, REPO, check, pin, unique_json

OUT = HERE / "design-history-custody.json"
COPIES = HERE / "preserved-design-history"
EXTRA = [
    ("tmp/i03-var03-prospective-contract-design-v6-20261008.json", 50697, "17ab577282e2186040d93195500e9df7565db51922b75468ffe62cc60c7fb30d"),
    ("tmp/make-i03-var03-prospective-contract-design-v6-20261008.py", 20578, "b3d041b19e33d104c7d8a9dddab2b7896b75f9c9e072e9051af0287f22dadcc6"),
    ("tmp/i03-var03-independent-contract-design-v6-go-20261008.md", 2198, "5275d9071c7121735d3ead90410ac24c1ef914b1d7ae23fd65ce11b958f7beea"),
    ("tmp/i03-var03-independent-contract-design-audit-v6-20261008.py", 7329, "4aa275a3cd2299d30211fb7c7dc6cefa466f9b7ec69df44df5dbdd220ac00393"),
    ("tmp/issue18-root-i03var03-construction-go-20261008.json", 2446, "ff3e4c1e05637be359c54dea37e05c0488521a66f5ed4fab5b2c088ac747c652"),
    ("tmp/issue18-root-i03var03-source-review-progress-20261008.md", 3937, "36ea6300cf4d3ba6118b48b7e254074d34030714ea50fe77eac42255d8c75369"),
]


def records(require_original: bool = False) -> list[dict]:
    contract = unique_json((HERE / "contract.json").read_bytes())
    source = contract["source_lineage"]["draft_history"]
    paths = {row["path"] for row in source}
    assert len(paths) == len(source) == 21
    result = []
    for row in source + [{"path": path, "bytes": size, "sha256": sha} for path, size, sha in EXTRA]:
        original = REPO / row["path"]
        owned = COPIES / (original.name + ".bytes")
        wanted = {"bytes": row["bytes"], "sha256": row["sha256"]}
        if require_original:
            check(original, wanted)
        elif original.exists():
            check(original, wanted)
        result.append({"original_path": row["path"], "owned_copy": owned.relative_to(HERE).as_posix(), **wanted})
    assert len(result) == 27 and len({r["owned_copy"] for r in result}) == 27
    return result


def verify(write: bool = False) -> dict:
    rows = records(write)
    if write:
        assert not OUT.exists() and not COPIES.exists()
        COPIES.mkdir()
        for row in rows:
            original = REPO / row["original_path"]
            target = HERE / row["owned_copy"]
            target.write_bytes(original.read_bytes())
        OUT.write_bytes((json.dumps({"schema": "i03-var03-design-history-custody/v1", "records": rows},
                                     indent=2) + "\n").encode())
    assert OUT.is_file()
    observed = unique_json(OUT.read_bytes())
    assert observed == {"schema": "i03-var03-design-history-custody/v1", "records": rows}
    for row in rows:
        check(HERE / row["owned_copy"], row)
    return {"schema": "i03-var03-design-history-custody-check/v1", "records": len(rows),
            "custody_sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(), "written": write}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.write), sort_keys=True))
