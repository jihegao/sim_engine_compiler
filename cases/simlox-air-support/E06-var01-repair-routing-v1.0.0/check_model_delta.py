"""Verify the exact authored table delta and the sole repair-fraction arm switch."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def tables(path: Path) -> dict:
    doc = json.loads(path.read_bytes())
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row, strict=True)) for row in t["instances"][0]["rows"]]


def main() -> None:
    parent = tables(ROOT / "E05-local-repair-reissue-v1.0.0/native-input.json")
    support = tables(ROOT / "E04-upstream-transport-fast-v1.0.0/native-input.json")
    local = tables(HERE / "local-input.json")
    upstream = tables(HERE / "upstream-input.json")
    assert parent.keys() == local.keys() == upstream.keys()
    common = {"ProblemDescription", "Station", "StationStructure", "ItemRepair", "StockAllocation"}
    assert {name for name in parent if parent[name] != local[name]} == common
    assert {name for name in parent if parent[name] != upstream[name]} == common
    assert {name for name in local if local[name] != upstream[name]} == {"ProblemDescription", "ItemRepair"}
    for variant, model, base_fraction in (("local", local, 1.0), ("upstream", upstream, 0.0)):
        assert rows(model["Station"]) == rows(parent["Station"]) + rows(support["Station"])[-1:]
        assert rows(model["StationStructure"]) == rows(parent["StationStructure"]) + rows(support["StationStructure"])[-1:]
        stock = rows(model["StockAllocation"])
        assert stock[0] == rows(parent["StockAllocation"])[0]
        assert len(stock) == 2 and stock[1] == dict(stock[0], STID="DEPOT-01", STSIZ=0)
        repair = rows(model["ItemRepair"])
        expected_base = dict(rows(parent["ItemRepair"])[0], DIRPF=base_fraction)
        assert repair == [expected_base, dict(rows(parent["ItemRepair"])[0], STID="DEPOT-01", DIRPF=1.0)]
        assert rows(model["ProblemDescription"]) == [{"PDESC": f"E06 cumulative direct-repair boundary {variant}"}]
    print(json.dumps({"passed": True, "changed_parent_tables": sorted(common),
                      "changed_arm_tables": ["ItemRepair", "ProblemDescription"],
                      "base_dirpf": {"local": 1, "upstream": 0}, "depot_dirpf": 1}))


if __name__ == "__main__":
    main()
