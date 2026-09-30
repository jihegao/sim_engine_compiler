"""Derive fixed/denied demands beside accepted A07 regenerative relief."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A07-regenerative-relief-v1.0.0" / "native-input.json"
PARENT_SHA = "fed4f8343d203fc250d8b3508f3f5f9fe76ecbd1a86646d5965531d246b89240"
OUTPUT = HERE / "native-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def one(document: dict, name: str) -> tuple[list[str], list[list]]:
    table, = (t for t in document["model"]["tables"] if t["name"] == name)
    instance, = table["instances"]
    return [c["name"] for c in table["columns"]], instance["rows"]


def row(columns: list[str], **updates: object) -> list:
    assert set(updates) <= set(columns)
    return [updates.get(c) for c in columns]


def build() -> dict:
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    doc = copy.deepcopy(json.loads(parent_raw))
    description_columns, description_rows = one(doc, "ProblemDescription")
    assert description_columns == ["PDESC"] and description_rows == [["A07 regenerative two-aircraft relief, eight-hour period"]]
    description_rows[0][0] = "J07 four regenerative children plus one successful and one denied fixed mission"

    mission_columns, missions = one(doc, "MissionType")
    assert len(missions) == 1
    original = dict(zip(mission_columns, missions[0], strict=True))
    assert original["MTID"] == "BASIC-MISSION" and original["NOS"] == original["MNOS"] == 1 and original["DURN"] == 4
    success = copy.deepcopy(original)
    success.update(MTID="FIXED-OK", DESCR="One-aircraft fixed demand after relief")
    denied = copy.deepcopy(original)
    denied.update(MTID="FIXED-DENY", DESCR="Three-aircraft fixed demand after relief", NOS=3, MNOS=3)
    missions.extend([[data[c] for c in mission_columns] for data in (success, denied)])

    profile_columns, profiles = one(doc, "OperationProfile")
    assert len(profiles) == 1
    regeneration = dict(zip(profile_columns, profiles[0], strict=True))
    assert regeneration["ITYPE"] == "REGENERATIVE" and regeneration["STIM"] == 8 and regeneration["IPER"] == 8
    for mission, start in (("FIXED-OK", 20.0), ("FIXED-DENY", 28.0)):
        scheduled = copy.deepcopy(regeneration)
        scheduled.update(SPRID=mission, STIM=start, ITYPE="SCHEDULED", IQTY=1, IQTYD=None, IPER=0, IDISP=None, DTIM=1 / 3)
        profiles.append([scheduled[c] for c in profile_columns])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(json.dumps({"input_sha256": sha(raw), "parent_sha256": PARENT_SHA, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
