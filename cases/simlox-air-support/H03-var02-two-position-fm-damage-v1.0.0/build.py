"""Freeze a second damage failure mode on accepted H03 POS-A source."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H03-var01-position-fm-damage-v1.0.0/mode-input.json"
PARENT_SHA = "5297d5224b3a2086c26c663aa92cd51be7c349a24f7957428f47c21fcdc4ee7c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    assert rows(parent, "FailureMode") == [[
        "FM-POS-A", "Position A direct repair", "POS-A", 1e-9,
        "OPHOURS", 1.0, None, None, None]]
    assert rows(parent, "DamageFailureMode") == [[
        "BATTLE-HIT", "TEACH-AIR-01", "FM-POS-A", 1.0, None]]
    assert rows(parent, "CMLocation") == [[
        "FM-POS-A", "TEACH-AIR-01", "BASE-01", 0.5,
        None, None, 1.0, None, None, None]]
    child = copy.deepcopy(parent)
    rows(child, "FailureMode").append([
        "FM-POS-B", "Second position A direct repair", "POS-A", 1e-9,
        "OPHOURS", 1.0, None, None, None])
    rows(child, "CMLocation").append([
        "FM-POS-B", "TEACH-AIR-01", "BASE-01", 1.0,
        None, None, 1.0, None, None, None])
    rows(child, "DamageFailureMode").append([
        "BATTLE-HIT", "TEACH-AIR-01", "FM-POS-B", 1.0, None])
    rows(child, "ProblemDescription")[0][0] = (
        "H03.var02 two certain damage failure modes on material POS-A")
    for name, doc in (("control-input.json", parent), ("two-mode-input.json", child)):
        path = HERE / name
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} differs")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(path))


if __name__ == "__main__":
    main()
