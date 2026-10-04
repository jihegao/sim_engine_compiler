"""Build F03 two-base stocked-peer lateral ENLAT Y/N pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F03-var03-demand-location-v1.0.0" / "risk_base1-input.json"
PARENT_SHA = "df4daeab5076e4b29b2d2a04c0a90bddd0af589af1e0dce2483c48fce5c2a06c"
DONOR = HERE.parent / "E08-var01-immediate-lateral-v1.0.2" / "on-input.json"
DONOR_SHA = "630d7600e7ff77ddb057f05af0852b4f41ed6335718570f9fcf5eddd9f51c474"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    return matches[0]


def rows(doc: dict, name: str) -> list[list]:
    t = table(doc, name)
    assert len(t["instances"]) == 1
    return t["instances"][0]["rows"]


def build() -> tuple[dict, dict]:
    raw, donor_raw = PARENT.read_bytes(), DONOR.read_bytes()
    assert sha(raw) == PARENT_SHA and sha(donor_raw) == DONOR_SHA
    parent, donor = json.loads(raw), json.loads(donor_raw)
    assert len(parent["model"]["tables"]) == 32 and not any(t["name"] == "LateralSupport" for t in parent["model"]["tables"])
    assert [r[0] for r in rows(parent, "Station")] == ["BASE-01", "DEPOT-01", "BASE-02"]
    assert rows(parent, "Control")[0][8] is None and rows(parent, "StockAllocation")[-1][:4] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-02", 0]
    assert rows(donor, "LateralSupport") == [["LAT-01", 0.5, "N", "IMMEDIATE", None]]
    on = copy.deepcopy(parent)
    rows(on, "ProblemDescription")[0][0] = "F03.var04 two-base risk fleet with stocked lateral peer ENLAT Y"
    rows(on, "Control")[0][8] = "Y"
    for row in rows(on, "Station"):
        if row[0] in ("BASE-01", "BASE-02"):
            row[8] = "LAT-01"
    rows(on, "StockAllocation")[-1][3] = 1
    on["model"]["tables"].append(copy.deepcopy(table(donor, "LateralSupport")))
    off = copy.deepcopy(on)
    rows(off, "ProblemDescription")[0][0] = "F03.var04 two-base risk fleet stocked peer but ENLAT N"
    rows(off, "Control")[0][8] = "N"
    return on, off


def main() -> None:
    out = {}
    for arm, doc in zip(("lateral_on", "lateral_off"), build()):
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{arm}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {arm} changed"
        else:
            path.write_bytes(raw)
        out[arm] = sha(raw)
    print(json.dumps({"parent": PARENT_SHA, "donor": DONOR_SHA, "inputs": out}))


if __name__ == "__main__":
    main()
