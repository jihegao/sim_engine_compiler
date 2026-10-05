"""Check accepted controls, raw seals and the declared E02.var03 source delta."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "E02-zero-stock-local-backorder-v1.0.0"
PARENT_RUN = PARENT / "runs" / "e02-v100-ssh-20260929-01"
SOURCE_SHA256 = "6d2b20e4ddc92bd5dc0894537152e12dbb3598c1d725c18eb025d4c19b14f28e"
PARENT_SHA256 = "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"
PARENT_SIGNOFF_SHA256 = "c28abcac8c3b8a55d0f58adf87ec3038555102d6b7bc2b35dc84ab9793e42ad6"
PARENT_CLOSURE_SHA256 = "a8ec55f67c710be700cb4dc3663c7f79041d69c2021edb9924c1d0daddda04ef"
E01_SIGNOFF_SHA256 = "c52dd13ba1f6fab05032ebf80597940099241bb652f2c3a73a26edbf059c1110"
E05_SIGNOFF_SHA256 = "e7f4e82be24e09d258345e5f8084ac99e822e8384cb5c8698fbd1ea687105f2f"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(document: dict, name: str) -> dict:
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def verify() -> dict:
    assert sha(PARENT / "native-input.json") == PARENT_SHA256
    assert sha(PARENT / "cli-scope-signoff-2026-09-29.md") == PARENT_SIGNOFF_SHA256
    assert sha(PARENT_RUN / "closure.json") == PARENT_CLOSURE_SHA256
    assert sha(ROOT / "E01-local-spare-explicit-replacement-v1.0.0" / "cli-scope-signoff-2026-09-29.md") == E01_SIGNOFF_SHA256
    assert sha(ROOT / "E05-local-repair-reissue-v1.0.0" / "cli-scope-signoff-2026-09-29.md") == E05_SIGNOFF_SHA256
    closure = json.loads((PARENT_RUN / "closure.json").read_bytes())
    assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, record in closure["raw"].items():
        path = PARENT_RUN / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], name
    assert sha(HERE / "native-input.json") == SOURCE_SHA256
    parent = json.loads((PARENT / "native-input.json").read_bytes())
    child = json.loads((HERE / "native-input.json").read_bytes())
    control = table(parent, "Control")
    columns = [column["name"] for column in control["columns"]]
    for name in ("SIMPE", "RCEND"):
        index = columns.index(name)
        assert control["instances"][0]["rows"][0][index] == 36.0
        control["instances"][0]["rows"][0][index] = 11.0
    result = table(parent, "ResultCollection")
    columns = [column["name"] for column in result["columns"]]
    assert len(result["instances"][0]["rows"]) == 2
    for row in result["instances"][0]["rows"]:
        index = columns.index("RCEND")
        assert row[index] == 36.0
        row[index] = 11.0
    operation = table(parent, "OperationProfile")
    columns = [column["name"] for column in operation["columns"]]
    rows = operation["instances"][0]["rows"]
    assert [row[columns.index("STIM")] for row in rows] == [8.0, 20.0, 32.0]
    del rows[1:]
    assert parent == child, "undeclared authored source delta"
    return {"schema": "simlox-e02-var03-v100-source-preflight/v1", "passed": True,
            "parent_raw_seals": 12, "source_sha256": SOURCE_SHA256,
            "delta": "Control SIMPE/RCEND 36->11; two ResultCollection RCEND 36->11; remove h20/h32 OperationProfile rows"}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
