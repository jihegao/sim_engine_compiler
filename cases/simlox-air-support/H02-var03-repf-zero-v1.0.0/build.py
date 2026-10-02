"""Build byte-identical REPF1 control and REPF0 damaged-LRU endpoint."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
PARENT_SHA = "82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(doc: dict, name: str) -> list:
    found = [table for table in doc["model"]["tables"] if table["name"] == name]
    assert len(found) == 1
    instances = found[0]["instances"]
    assert len(instances) == 1 and len(instances[0]["rows"]) == 1
    return instances[0]["rows"][0]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    raw_control = PARENT.read_bytes()
    control = json.loads(raw_control)
    child = copy.deepcopy(control)
    assert row(control, "DamageItem") == [
        "BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1.0, 1.0, None, None]
    row(child, "DamageItem")[4] = 0.0
    row(child, "ProblemDescription")[0] = "H02.var03 primary LRU damage with REPF zero discard"
    raw_child = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for name, raw in (("repairable-input.json", raw_control),
                      ("discard-input.json", raw_child)):
        path = HERE / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} differs")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(path))


if __name__ == "__main__":
    main()
