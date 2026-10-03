"""Freeze two equal-fraction actual depot parents from accepted E12.var05."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var05-base02-zero-opening-stock-v1.0.0/native-input.json"
PARENT_SHA = "940592a6e27a84549e57656921ca111c1fc3c16e0bf233b90259866afb81071b"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(doc: dict, name: str) -> tuple[list[str], list[list]]:
    t = table(doc, name)
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var07 two symmetric physical depots with equal DFRAC demand propagation"
    )
    sn, station = rows(doc, "Station")
    depot = [r for r in station if r[sn.index("STID")] == "DEPOT-01"]
    assert len(station) == 3 and len(depot) == 1 and depot[0][sn.index("QTY")] == 1 and depot[0][sn.index("GSTID")] == "DEPOT-GRP"
    second = depot[0].copy()
    second[sn.index("STID")] = "DEPOT-02"
    second[sn.index("DESCR")] = "Second teaching support depot"
    station.append(second)
    for name in ("StationStructure", "ItemStationStructure"):
        cols, links = rows(doc, name)
        assert len(links) == 2 and {r[cols.index("STID")] for r in links} == {"BASE-01", "BASE-02"}
        for link in links.copy():
            assert link[cols.index("MSTID")] == "DEPOT-01" and link[cols.index("DFRAC")] == 1.0
            link[cols.index("DFRAC")] = 0.5
            sibling = link.copy()
            sibling[cols.index("MSTID")] = "DEPOT-02"
            links.append(sibling)
    an, allocation = rows(doc, "StockAllocation")
    depot_stock = [r for r in allocation if r[an.index("STID")] == "DEPOT-01"]
    assert len(allocation) == 3 and len(depot_stock) == 1 and depot_stock[0][an.index("STSIZ")] == 1
    second_stock = depot_stock[0].copy()
    second_stock[an.index("STID")] = "DEPOT-02"
    allocation.append(second_stock)
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    output = HERE / "native-input.json"
    raw = build()
    if sys.argv[1:] == ["--write"]:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: build.py [--write]")
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))
