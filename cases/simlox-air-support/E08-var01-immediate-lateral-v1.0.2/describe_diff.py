"""Freeze exact E07 to E08 source changes and the Y/N controlled contrast."""
import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    found = {t["name"]: t for t in doc["model"]["tables"]}
    if len(found) != len(doc["model"]["tables"]):
        raise ValueError("duplicate tables")
    return found


def delta(left: dict, right: dict) -> dict:
    return {
        "added": {name: right[name] for name in sorted(right.keys() - left.keys())},
        "removed": {name: left[name] for name in sorted(left.keys() - right.keys())},
        "changed": {name: {"before": left[name], "after": right[name]}
                    for name in sorted(left.keys() & right.keys()) if left[name] != right[name]},
        "unchanged_table_count": len(left.keys() & right.keys()) - sum(left[name] != right[name] for name in left.keys() & right.keys()),
    }


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("parent changed")
    parent = tables(PARENT)
    on = tables(HERE / "on-input.json")
    off = tables(HERE / "off-input.json")
    on_diff = delta(parent, on)
    off_diff = delta(parent, off)
    contrast = delta(off, on)
    expected_changed = {"ProblemDescription", "Control", "Station", "StationStructure", "ItemStationStructure", "StockAllocation", "ResultCollection", "Item"}
    assert set(on_diff["changed"]) == expected_changed
    assert set(off_diff["changed"]) == expected_changed
    assert set(on_diff["added"]) == set(off_diff["added"]) == {"LateralSupport", "StationLateralSupport"}
    assert not on_diff["removed"] and not off_diff["removed"]
    assert set(contrast["changed"]) == {"ProblemDescription", "Control"}
    assert not contrast["added"] and not contrast["removed"]
    assert [row[0] for row in on["ResultCollection"]["instances"][0]["rows"]] == ["MISSION", "SYSTEM", "ITEM"]
    assert on["ResultCollection"] == off["ResultCollection"]
    item_names = [col["name"] for col in on["Item"]["columns"]]
    assert on["Item"]["instances"][0]["rows"][0][item_names.index("TRACK")] == "Y"
    assert on["Item"] == off["Item"]
    off_control = contrast["changed"]["Control"]["before"]
    on_control = contrast["changed"]["Control"]["after"]
    assert off_control["columns"] == on_control["columns"]
    names = [col["name"] for col in on_control["columns"]]
    off_row = off_control["instances"][0]["rows"][0]
    on_row = on_control["instances"][0]["rows"][0]
    assert [(names[i], old, new) for i, (old, new) in enumerate(zip(off_row, on_row)) if old != new] == [("ENLAT", "N", "Y")]
    assert contrast["changed"]["ProblemDescription"]["before"]["columns"] == contrast["changed"]["ProblemDescription"]["after"]["columns"]
    result = {"schema": "simlox-e08-var01-v102-exact-diff/v1", "parent_sha256": PARENT_SHA,
              "on_sha256": sha(HERE / "on-input.json"), "off_sha256": sha(HERE / "off-input.json"),
              "on_from_parent": on_diff, "off_from_parent": off_diff, "on_from_off": contrast}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen exact diff changed")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"sha256": sha(output), "on_changed": sorted(on_diff["changed"]), "off_changed": sorted(off_diff["changed"])}))


if __name__ == "__main__":
    main()
