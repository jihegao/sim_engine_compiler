"""Build and statically check the one-field A09 nested candidate revision."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parent
PREVIOUS = LIBRARY / "A09-hierarchical-operation-profile" / "native-nested.json"
PARENT = LIBRARY / "A02-single-aircraft-repeated-missions" / "native-input.json"
FLAT = LIBRARY / "A09-hierarchical-operation-profile" / "native-flat.json"
CONTRACT = HERE / "contract.json"
OUTPUT = HERE / "native-nested.json"
PREVIOUS_SHA256 = "644cdd63463ff0dea1daefaa4d95f8b362610fdb9d568142df0c23f8dad8dcb0"
PARENT_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
FLAT_SHA256 = "65dfc84f5f17ffd83363bd61cfd35c530056c34f1e3c4478ff89525d87cf32d7"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked_source(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if sha256(raw) != expected:
        raise ValueError(f"pinned source changed: {path.name}")
    return json.loads(raw)


def root_period_cell(document: dict) -> tuple[list, int]:
    tables = [table for table in document["model"]["tables"] if table["name"] == "OperationProfile"]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError("expected one OperationProfile table and instance")
    table = tables[0]
    columns = [column["name"] for column in table["columns"]]
    if len(columns) != len(set(columns)):
        raise ValueError("duplicate OperationProfile column")
    required = {"PRID", "SPRID", "STIM", "ITYPE", "IQTY", "IPER", "DTIM"}
    if not required <= set(columns):
        raise ValueError("OperationProfile columns differ")
    rows = table["instances"][0]["rows"]
    if len(rows) != 3 or any(len(row) != len(columns) for row in rows):
        raise ValueError("previous nested candidate row shape differs")
    matching = [row for row in rows if (
        row[columns.index("PRID")] == "BASIC-SCHEDULE"
        and row[columns.index("SPRID")] == "A09-DAILY-TWO-WAVE"
        and row[columns.index("STIM")] == 0.0
    )]
    if len(matching) != 1:
        raise ValueError("expected exactly one nested root row")
    root = matching[0]
    if (root[columns.index("ITYPE")] != "SCHEDULED"
            or root[columns.index("IQTY")] != 2
            or root[columns.index("DTIM")] is not None):
        raise ValueError("nested root configuration differs")
    return root, columns.index("IPER")


def build() -> tuple[dict, dict, bytes]:
    previous = checked_source(PREVIOUS, PREVIOUS_SHA256)
    checked_source(PARENT, PARENT_SHA256)
    checked_source(FLAT, FLAT_SHA256)
    old_root, old_index = root_period_cell(previous)
    if old_root[old_index] != 24.0:
        raise ValueError("previous nested root IPER differs")
    candidate = copy.deepcopy(previous)
    new_root, new_index = root_period_cell(candidate)
    new_root[new_index] = 48.0
    raw = (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return previous, candidate, raw


def check_delta(previous: dict, candidate: dict) -> None:
    expected = copy.deepcopy(previous)
    root, index = root_period_cell(expected)
    if root[index] != 24.0:
        raise ValueError("previous nested root IPER differs")
    root[index] = 48.0
    if candidate != expected:
        raise ValueError("v1.0.1 candidate changes more than root IPER 24 to 48")


def validate() -> dict:
    previous, candidate, raw = build()
    check_delta(previous, candidate)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (contract["version"] != "1.0.1-candidate"
            or contract["previous_input_sha256"] != PREVIOUS_SHA256
            or contract["parent_input_sha256"] != PARENT_SHA256
            or contract["flat_control_sha256"] != FLAT_SHA256
            or contract["candidate_input_sha256"] != sha256(raw)):
        raise ValueError("candidate contract/source fingerprint differs")
    if OUTPUT.read_bytes() != raw:
        raise ValueError("checked candidate differs from pinned one-field builder")
    return {"schema": "simlox-a09-v101-local-validation/v1", "passed": True,
            "candidate_sha256": sha256(raw), "changed_field": "OperationProfile[root].IPER",
            "scope": "local_static_candidate_only", "native_behavior_status": "not_run",
            "gui_status": "not_run", "publication_state": "not_published"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the new candidate input once")
    args = parser.parse_args()
    if args.write:
        OUTPUT.write_bytes(build()[2])
        print(sha256(OUTPUT.read_bytes()))
    else:
        print(json.dumps(validate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
