"""Freeze two accepted transfers at a horizon strictly before completion."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARMS = {
    "transit": (
        ROOT / "I02-var04-between-delay-v1.0.0" / "native-input.json",
        "607b5d5bc9d3c850b533b4bc50e202e6719c23182b47038fdf056222bfce2f39",
        7.0,
        ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 2.0, None],
    ),
    "backorder": (
        ROOT / "I02-var05-zero-source-v1.0.0" / "native-input.json",
        "00cebb18be952522b1bbfd1885edc40f2c9b4da148d000cf5326309360cc6453",
        3.0,
        ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 2.0, 1, 0.0, None],
    ),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    return matches[0]


def build(arm: str) -> dict:
    parent, parent_sha, horizon, transfer = ARMS[arm]
    assert sha(parent) == parent_sha, f"accepted {arm} source changed"
    doc = copy.deepcopy(json.loads(parent.read_text(encoding="utf-8")))
    assert table(doc, "ItemTransfer")["instances"][0]["rows"][1] == transfer
    control = table(doc, "Control")
    names = [c["name"] for c in control["columns"]]
    row = control["instances"][0]["rows"][0]
    assert row[names.index("SIMPE")] == 36.0
    assert row[names.index("RCEND")] == 36.0
    row[names.index("SIMPE")] = horizon
    row[names.index("RCEND")] = horizon
    collection = table(doc, "ResultCollection")
    names = [c["name"] for c in collection["columns"]]
    for r in collection["instances"][0]["rows"]:
        assert r[names.index("RCEND")] == 36.0
        r[names.index("RCEND")] = horizon
    profile = table(doc, "OperationProfile")
    original = profile["instances"][0]["rows"]
    assert [r[2] for r in original] == [8.0, 20.0, 32.0]
    assert [r[4] for r in original] == [1, 1, 1]
    # Keep the referenced profile defined while suppressing all mission
    # initiation. D02.var05 v1.0.2 established IQTY=0 as accepted syntax.
    single = copy.deepcopy(original[0])
    single[2] = 0.0
    single[4] = 0
    profile["instances"][0]["rows"] = [single]
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"I02.var13 {arm} transfer at h{transfer[3]:g}; endpoint h{horizon:g}"
    )
    return doc


if __name__ == "__main__":
    for arm in ARMS:
        raw = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{arm}-input.json"
        if target.exists():
            assert target.read_bytes() == raw, f"frozen {arm} input differs"
        else:
            target.write_bytes(raw)
        print(arm, sha(target), len(raw))
