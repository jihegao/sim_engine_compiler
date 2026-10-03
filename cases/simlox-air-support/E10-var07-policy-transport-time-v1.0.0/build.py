"""Freeze ONDEM policy transport-time override and one exponential draw."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var01-fixed-ondem-v1.0.1/native-input-ondem.json"
PARENT_SHA = "1ad095c4d1d371c1a2b8e7bc61d629e59459eff90ff310e5c6d1945c4cf70882"
ARMS = ("det3", "exp3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def row_and_names(doc: dict, name: str) -> tuple[list, list[str]]:
    t = table(doc, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    return t["instances"][0]["rows"][0], [c["name"] for c in t["columns"]]


def build(arm: str) -> bytes:
    assert arm in ARMS and sha(PARENT) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    desc, _ = row_and_names(doc, "ProblemDescription")
    desc[0] = f"E10.var07 ONDEM TPTIM 3h versus link TFRMS 2h; TPTIMD {'<EXP>' if arm == 'exp3' else 'none'}"
    link, link_names = row_and_names(doc, "StationStructure")
    assert link[link_names.index("TFRMS")] == 2.0 and link[link_names.index("PFRMS")] == "DOWN-POLICY"
    policy, names = row_and_names(doc, "TransportPolicyProfile")
    assert policy[names.index("TPRID")] == "DOWN-POLICY"
    assert policy[names.index("STPRID")] == "ONDEM"
    assert policy[names.index("MINBS")] == 1
    assert policy[names.index("TPTIM")] == 2.0 and policy[names.index("TPTIMD")] is None
    policy[names.index("TPTIM")] = 3.0
    if arm == "exp3":
        policy[names.index("TPTIMD")] = "<EXP>"
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    for arm in ARMS:
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        if write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
        print(json.dumps({"arm": arm, "parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
