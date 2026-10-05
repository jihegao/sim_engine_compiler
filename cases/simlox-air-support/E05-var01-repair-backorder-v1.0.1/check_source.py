"""Check the accepted parent seals and the sole E05.var01 source-cell delta."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E05-local-repair-reissue-v1.0.0"
PARENT_RUN = PARENT / "runs" / "e05-v100-ssh-20260929-01"
PARENT_SHA = "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"
CHILD_SHA = "5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08"
CLOSURE_SHA = "e75836bcd99ba838d4ef247973794a2bf38fbddd4904d69337d631ba983d01ef"
SIGNOFF_SHA = "e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    assert sha(PARENT / "native-input.json") == PARENT_SHA
    assert sha(HERE / "native-input.json") == CHILD_SHA
    assert sha(PARENT / "cli-scope-signoff-2026-09-29.md") == SIGNOFF_SHA
    closure_path = PARENT_RUN / "closure.json"
    assert sha(closure_path) == CLOSURE_SHA
    closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
    assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, record in closure["raw"].items():
        path = PARENT_RUN / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], name
    parent = json.loads((PARENT / "native-input.json").read_bytes())
    child = json.loads((HERE / "native-input.json").read_bytes())
    assert len(parent["model"]["tables"]) == len(child["model"]["tables"]) == 31
    row_tables = [t for t in parent["model"]["tables"] if any(x["rows"] for x in t["instances"])]
    assert len(row_tables) == 20
    target = next(t for t in parent["model"]["tables"] if t["name"] == "ItemRepair")
    assert target["instances"][0]["rows"][0][2] == 1.0
    target["instances"][0]["rows"][0][2] = 13.0
    assert parent == child, "more than ItemRepair rec1 DIRPT changed"
    return {"schema": "simlox-e05-var01-source-preflight/v1", "passed": True,
            "parent_raw_seals": 12, "parent_row_tables": 20,
            "delta": "ItemRepair rec1 TEACH-LRU-01/BASE-01 DIRPT 1->13",
            "child_sha256": CHILD_SHA}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
