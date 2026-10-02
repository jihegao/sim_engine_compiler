"""Freeze parent geometry changes and the matched DLAYL Y/N contrast."""
import hashlib
import json
from pathlib import Path
from build import HERE, PARENT, PARENT_SHA, DONOR, DONOR_SHA


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(out) == len(doc["model"]["tables"])
    return out


def changed(a, b):
    return sorted(n for n in a.keys() & b.keys() if a[n] != b[n])


def main():
    assert sha(PARENT) == PARENT_SHA and sha(DONOR) == DONOR_SHA
    base, off, on = [tables(p) for p in (PARENT, HERE / "off-input.json", HERE / "on-input.json")]
    assert set(off) == set(on) == set(base) | {"ItemTransfer"}
    assert changed(base, off) == ["ProblemDescription", "StockAllocation"]
    assert changed(base, on) == ["LateralSupport", "ProblemDescription", "StockAllocation"]
    assert changed(off, on) == ["LateralSupport", "ProblemDescription"]
    stock_names = [c["name"] for c in base["StockAllocation"]["columns"]]
    peer_idx = next(i for i, r in enumerate(base["StockAllocation"]["instances"][0]["rows"])
                    if r[stock_names.index("STID")] == "BASE-02")
    old_peer = base["StockAllocation"]["instances"][0]["rows"][peer_idx]
    new_peer = off["StockAllocation"]["instances"][0]["rows"][peer_idx]
    assert [(stock_names[i], a, b) for i, (a, b) in enumerate(zip(old_peer, new_peer)) if a != b] == [("STSIZ", 1, 0)]
    assert off["StockAllocation"] == on["StockAllocation"]
    donor = tables(DONOR)["ItemTransfer"]
    assert off["ItemTransfer"]["columns"] == donor["columns"] == on["ItemTransfer"]["columns"]
    transfer = off["ItemTransfer"]["instances"][0]["rows"]
    assert transfer == on["ItemTransfer"]["instances"][0]["rows"] == [
        ["DEPOT-01", "BASE-02", "TEACH-LRU-01", 9.0, 1, 2.0, None]]
    names = [c["name"] for c in off["LateralSupport"]["columns"]]
    old, new = [t["LateralSupport"]["instances"][0]["rows"][0] for t in (off, on)]
    assert [(names[i], a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b] == [("DLAYL", "N", "Y")]
    assert len(base) == 34 and len(off) == len(on) == 35
    result = {"schema": "simlox-e08-var03-delayed-lateral-exact-diff/v1",
              "parent_sha256": PARENT_SHA, "transfer_schema_donor_sha256": DONOR_SHA,
              "off_sha256": sha(HERE / "off-input.json"), "on_sha256": sha(HERE / "on-input.json"),
              "off_from_parent": {"added_tables": ["ItemTransfer"], "changed_tables": changed(base, off),
                                  "unchanged_table_count": 32, "peer_stock_size": [1, 0], "scheduled_transfer": transfer},
              "on_from_off": {"changed_tables": changed(off, on), "unchanged_table_count": 33,
                              "dlayl": ["N", "Y"], "description_only_other_delta": True}}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    out = HERE / "exact-diff.json"
    if out.exists():
        assert out.read_bytes() == encoded, "frozen exact diff differs"
    else:
        out.write_bytes(encoded)
    print(json.dumps({"exact_diff_sha256": sha(out), "off_sha256": result["off_sha256"], "on_sha256": result["on_sha256"]}))


if __name__ == "__main__":
    main()
