"""Closed host-original custody for the distinct v1.0.1 design review chain."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from model_common import encode, pin, read

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "prospective-proof-custody.json"
OUTER = "tmp/i04-var09-root-review-proofs-v100-20261008/"
PROOF_DIRS = (
    ("preserve_v100", "i04-var10-preserve-excluded-v100-20261008T125605564917Z-4db63729"),
    ("generate_v101", "i04-var10-prospective-v101-generation-20261008T125706458474Z-e8bf1bc0"),
    ("independent_audit_v1_failed", "i04-var10-independent-v101-contract-audit-20261008T125959300474Z-2cd6df2a"),
    ("independent_audit_v2_passed", "i04-var10-independent-v101-contract-audit-corrected-20261008T130145321444Z-2aa41c90"),
    ("fresh_construction_boundary", "i04-var10-v101-fresh-construction-boundary-20261008T130500954723Z-cd13c25a"),
)
SINGLES = (
    ("v100_excluded_inventory", "tmp/i04-var10-v100-excluded-construction-inventory-20261008.json"),
    ("v100_preservation_method", "tmp/i04-var10-root-preserve-v100-20261008.py"),
    ("v100_preservation_result", "tmp/i04-var10-root-preserved-v100-20261008.json"),
    ("v100_static_no_go", "tmp/i04-var10-independent-prelaunch-static-no-go-v100-20261008.md"),
    ("v101_design_generator_draft", "tmp/i04-var10-build-prospective-v101-20261008.py"),
    ("v101_design_generator", "tmp/i04-var10-build-prospective-v101-v2-20261008.py"),
    ("independent_audit_v1_source", "tmp/i04-var10-independent-contract-audit-v101-20261008.py"),
    ("independent_audit_v2_source", "tmp/i04-var10-independent-contract-audit-v102-20261008.py"),
    ("v101_design_go", "tmp/i04-var10-independent-contract-go-v101-20261008.md"),
)


def ordered():
    items = list(SINGLES)
    for role, directory in PROOF_DIRS:
        for filename in ("receipt.json", "stdout.bin", "stderr.bin"):
            items.append((f"{role}:{filename}", OUTER + directory + "/" + filename))
    assert len(items) == 24 and len({path.casefold() for _, path in items}) == len(items)
    return items


def candidate():
    records = []
    for role, relative in ordered():
        assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
        original = REPO / relative
        assert original.is_file(), (role, original)
        records.append({"role": role, "original_path": str(original),
                        **pin(original), "disposition": "mandatory_host_original"})
    return {"schema": "i04-var10-v101-prospective-proof-custody/v1",
            "records": records, "mandatory_host_original_count": 24,
            "original_binary_capture_dirs": 5,
            "failed_audit_original_capture_present": True,
            "no_manual_or_private_snapshot_copies": True}


def verify():
    document = read(MAP)
    assert set(document) == {"schema", "records", "mandatory_host_original_count",
                             "original_binary_capture_dirs", "failed_audit_original_capture_present",
                             "no_manual_or_private_snapshot_copies"}
    assert document == candidate()
    return 24


if __name__ == "__main__":
    assert sys.argv[1:] in ([], ["--write"])
    if sys.argv[1:] == ["--write"]:
        with MAP.open("xb") as stream:
            stream.write(encode(candidate()))
    print(json.dumps({"schema": "i04-var10-v101-prospective-proof-check/v1",
                      "mandatory_originals": verify(), "native_calls": 0}, sort_keys=True))
