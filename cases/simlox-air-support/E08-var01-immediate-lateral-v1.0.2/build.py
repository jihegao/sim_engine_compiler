"""Build a bounded E08 immediate-lateral on/off pair from accepted E07."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E07-item-specific-transport-v1.0.1" / "native-input.json"
PARENT_SHA = "d42832b9e17b9a0c968a8bba7bcb1419eba06313097604fc0041baab5d132bc0"


def table(doc, name):
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(name)
    return matches[0]


def set_field(t, row, name, value):
    row[next(i for i, col in enumerate(t["columns"]) if col["name"] == name)] = value


def new_table(name, fields, key_count, row):
    return {
        "columns": [dict(datatype=datatype, key=True, name=field) if i < key_count
                    else dict(datatype=datatype, name=field)
                    for i, (field, datatype) in enumerate(fields)],
        "instances": [{"instance_name": "", "rows": [row]}],
        "name": name,
    }


def build(enabled):
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted E07 parent changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    set_field(table(doc, "ProblemDescription"), table(doc, "ProblemDescription")["instances"][0]["rows"][0], "PDESC",
              f"E08 immediate lateral support {'enabled' if enabled else 'disabled'}; stocked peer versus ordinary upstream stock")
    control = table(doc, "Control")
    set_field(control, control["instances"][0]["rows"][0], "ENLAT", "Y" if enabled else "N")
    item = table(doc, "Item")
    set_field(item, item["instances"][0]["rows"][0], "TRACK", "Y")
    station = table(doc, "Station")
    base = station["instances"][0]["rows"][0]
    set_field(station, base, "LGID", "LAT-01")
    peer = copy.deepcopy(base)
    set_field(station, peer, "STID", "BASE-02")
    set_field(station, peer, "DESCR", "Stocked peer for immediate lateral support")
    station["instances"][0]["rows"].append(peer)
    structure = table(doc, "StationStructure")
    peer_structure = copy.deepcopy(structure["instances"][0]["rows"][0])
    set_field(structure, peer_structure, "STID", "BASE-02")
    structure["instances"][0]["rows"].append(peer_structure)
    item_structure = table(doc, "ItemStationStructure")
    peer_item_structure = copy.deepcopy(item_structure["instances"][0]["rows"][0])
    set_field(item_structure, peer_item_structure, "STID", "BASE-02")
    item_structure["instances"][0]["rows"].append(peer_item_structure)
    stock = table(doc, "StockAllocation")
    peer_stock = copy.deepcopy(stock["instances"][0]["rows"][0])
    set_field(stock, peer_stock, "STID", "BASE-02")
    set_field(stock, peer_stock, "STSIZ", 1)
    stock["instances"][0]["rows"].append(peer_stock)
    collection = table(doc, "ResultCollection")
    item_collection = copy.deepcopy(collection["instances"][0]["rows"][0])
    set_field(collection, item_collection, "RTYPE", "ITEM")
    collection["instances"][0]["rows"].append(item_collection)
    doc["model"]["tables"].append(new_table("LateralSupport", [
        ("LGID", "string"), ("TLAT", "double"), ("DLAYL", "string"),
        ("LSRUL", "string"), ("NOTE", "string")], 1,
        ["LAT-01", 0.5, "N", "IMMEDIATE", None]))
    doc["model"]["tables"].append(new_table("StationLateralSupport", [
        ("LGID", "string"), ("STID", "string"), ("LSTID", "string"),
        ("TFRLS", "double"), ("TTOLS", "double"), ("NOTE", "string")], 3,
        ["LAT-01", "BASE-01", "BASE-02", 0.5, 0.5, None]))
    return doc


if __name__ == "__main__":
    for enabled, name in ((True, "on-input.json"), (False, "off-input.json")):
        raw = (json.dumps(build(enabled), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / name
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError(f"frozen {name} differs")
        else:
            path.write_bytes(raw)
        print(name, hashlib.sha256(raw).hexdigest(), len(raw))
