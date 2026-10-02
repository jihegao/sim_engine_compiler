"""Freeze item-damage replacement-specific versus ordinary fallback inputs."""
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


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    explicit = copy.deepcopy(parent)
    table(explicit, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "H02.var04 damage-specific half-hour replacement versus ordinary one-hour fallback")
    ordinary = table(explicit, "ItemReplacement")
    assert ordinary["instances"][0]["rows"] == []
    assert [c["name"] for c in ordinary["columns"]] == [
        "MID", "IID", "STID", "SURPT", "SURPF", "SURPM", "SURPC", "SURPTID", "SURPD", "NOTE"]
    ordinary["instances"][0]["rows"].append([
        "TEACH-AIR-01", "TEACH-LRU-01", "BASE-01", 1.0, 1.0,
        None, None, None, None, None])
    fallback = copy.deepcopy(explicit)
    table(fallback, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "H02.var04 DamageReplacement omitted; ordinary one-hour ItemReplacement fallback")
    damage = table(fallback, "DamageReplacement")
    assert len(damage["instances"][0]["rows"]) == 1
    damage["instances"][0]["rows"] = []
    for name, doc in (("explicit", explicit), ("fallback", fallback)):
        path = HERE / f"{name}-input.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} input differs")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(path))


if __name__ == "__main__":
    main()
