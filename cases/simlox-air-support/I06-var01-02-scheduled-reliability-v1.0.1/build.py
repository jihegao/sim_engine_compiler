"""Build paired scheduled reliability-factor panels from accepted D02 inputs."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parent
PARENTS = {
    "item": (ROOT / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json",
             "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"),
    "fm": (ROOT / "D02-var02-failure-mode-calendar-v1.0.0" / "native-input.json",
           "23b550dbc4e0aea4d6d328fe4805a4eb50af81f3af54ccd6353e45bce933271b"),
}
SEEDS = (1, 2, 3)
ARMS = ("control", "factor4")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1, name
    return matches[0]


def cell(doc: dict, name: str, field: str, value=None, set_value=False):
    target = table(doc, name)
    names = [c["name"] for c in target["columns"]]
    rows = target["instances"][0]["rows"]
    assert len(rows) == 1 and field in names
    if set_value:
        rows[0][names.index(field)] = value
    return rows[0][names.index(field)]


def change_table(kind: str, factor: float) -> dict:
    if kind == "item":
        name, key, target, column = "ChangesItemReliability", "IID", "TEACH-LRU-01", "FRTCF"
    else:
        name, key, target, column = "ChangesFailureModeReliability", "FMID", "FM-POS-A", "FRQCF"
    return {
        "columns": [
            {"datatype": "string", "name": key},
            {"datatype": "double", "name": "TIMEC"},
            {"datatype": "double", "name": column},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [
            [target, 9.0, factor, None],
            [target, 24.0, 1.0, None],
        ]}],
        "name": name,
    }


def build(kind: str, seed: int, arm: str) -> dict:
    assert kind in PARENTS and seed in SEEDS and arm in ARMS
    path, expected = PARENTS[kind]
    raw = path.read_bytes()
    assert sha(raw) == expected
    doc = copy.deepcopy(json.loads(raw.decode("utf-8-sig")))
    assert cell(doc, "Control", "RSEED") == "1"
    cell(doc, "Control", "RSEED", str(seed), True)
    cell(doc, "ProblemDescription", "PDESC", f"I06 {kind} seed {seed} {arm} reliability factor at h9", True)
    if kind == "item":
        assert cell(doc, "Item", "IID") == "TEACH-LRU-01"
        assert cell(doc, "Item", "FRT") == 300000
        assert cell(doc, "Item", "OPID") == "OPHOURS"
        profile = table(doc, "OperationProfile")
        names = [column["name"] for column in profile["columns"]]
        events = profile["instances"][0]["rows"]
        assert [row[names.index("STIM")] for row in events] == [8.0, 20.0, 52.0]
        events[2][names.index("STIM")] = 23.0
    else:
        assert cell(doc, "FailureMode", "FMID") == "FM-POS-A"
        assert cell(doc, "FailureMode", "FRQ") == 300000
        assert cell(doc, "FailureMode", "OPID") == "CALHOURS"
    doc["model"]["tables"].append(change_table(kind, 1.0 if arm == "control" else 4.0))
    return doc


def main() -> None:
    write = "--write" in sys.argv[1:]
    hashes = {}
    for kind in PARENTS:
        for seed in SEEDS:
            for arm in ARMS:
                name = f"{kind}-seed{seed}-{arm}"
                payload = (json.dumps(build(kind, seed, arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                target = CASE / f"{name}-input.json"
                if write:
                    target.write_bytes(payload)
                else:
                    assert target.read_bytes() == payload, f"frozen input changed: {name}"
                hashes[name] = sha(payload)
    print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
