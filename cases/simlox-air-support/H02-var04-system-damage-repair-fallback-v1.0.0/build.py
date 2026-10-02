"""Build damage-specific direct repair and ordinary fallback pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var01-system-damage-direct-repair-v1.0.0/system-input.json"
PARENT_SHA = "67eb54c6148cd17c43e050eaf3d310bf7f66b96452526614ca1af416c16d9bcb"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    item = table(doc, name)
    assert len(item["instances"]) == 1
    return item["instances"][0]["rows"]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = json.loads(PARENT.read_bytes())
    explicit = copy.deepcopy(parent)
    assert rows(explicit, "SystemRepair") == []
    assert [c["name"] for c in table(explicit, "SystemRepair")["columns"]] == [
        "SID", "STID", "DIRPT", "SURPT", "DIRPF", "SURPF", "DIRPM", "SURPM",
        "DIRPC", "SURPC", "DIRPTID", "SURPTID", "DIRPD", "SURPD", "NOTE"]
    assert rows(explicit, "DamageRepair") == [[
        "BATTLE-LOSS", "TEACH-AIR-01", "BASE-01", 1.0, 0.0, 1.0, 1.0,
        None, None, None, None, None]]
    rows(explicit, "SystemRepair").append([
        "TEACH-AIR-01", "BASE-01", 2.0, 0.0, 1.0, 1.0,
        None, None, None, None, None, None, None, None, None])
    rows(explicit, "ProblemDescription")[0][0] = (
        "H02.var04 one-hour damage-specific versus two-hour ordinary system repair")
    fallback = copy.deepcopy(explicit)
    rows(fallback, "DamageRepair").clear()
    rows(fallback, "ProblemDescription")[0][0] = (
        "H02.var04 damage-specific repair omitted; two-hour ordinary fallback")
    for arm, doc in (("explicit", explicit), ("fallback", fallback)):
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{arm}-input.json"
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        if not path.exists():
            path.write_bytes(raw)
        print(arm, sha(path))


if __name__ == "__main__":
    main()
