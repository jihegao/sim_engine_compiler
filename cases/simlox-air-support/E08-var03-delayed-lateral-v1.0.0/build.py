"""Build DLAYL Y/N on an E08 lateral peer with a scheduled future spare."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E08-var01-immediate-lateral-v1.0.2" / "on-input.json"
PARENT_SHA = "630d7600e7ff77ddb057f05af0852b4f41ed6335718570f9fcf5eddd9f51c474"
DONOR = HERE.parent / "I02-var04-between-delay-v1.0.0" / "native-input.json"
DONOR_SHA = "607b5d5bc9d3c850b533b4bc50e202e6719c23182b47038fdf056222bfce2f39"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(enabled):
    assert sha(PARENT) == PARENT_SHA and sha(DONOR) == DONOR_SHA
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    donor_tables = {t["name"]: t for t in json.loads(DONOR.read_text(encoding="utf-8"))["model"]["tables"]}
    assert "ItemTransfer" not in tables
    transfer = copy.deepcopy(donor_tables["ItemTransfer"])
    assert [c["name"] for c in transfer["columns"]] == ["STFID", "STTID", "IID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    transfer["instances"][0]["rows"] = [["DEPOT-01", "BASE-02", "TEACH-LRU-01", 9.0, 1, 2.0, None]]
    doc["model"]["tables"].append(transfer)
    stock = tables["StockAllocation"]
    names = [c["name"] for c in stock["columns"]]
    stid, size = names.index("STID"), names.index("STSIZ")
    peer = [r for r in stock["instances"][0]["rows"] if r[stid] == "BASE-02"]
    assert len(peer) == 1 and peer[0][size] == 1
    peer[0][size] = 0
    lateral = tables["LateralSupport"]
    names = [c["name"] for c in lateral["columns"]]
    assert lateral["instances"][0]["rows"][0][names.index("LSRUL")] == "IMMEDIATE"
    lateral["instances"][0]["rows"][0][names.index("DLAYL")] = "Y" if enabled else "N"
    description = tables["ProblemDescription"]
    names = [c["name"] for c in description["columns"]]
    description["instances"][0]["rows"][0][names.index("PDESC")] = (
        f"E08 delayed lateral {'enabled' if enabled else 'disabled'}; peer spare in scheduled transfer at h10"
    )
    return doc


if __name__ == "__main__":
    for enabled, name in ((False, "off-input.json"), (True, "on-input.json")):
        raw = (json.dumps(build(enabled), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / name
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} differs"
        else:
            path.write_bytes(raw)
        print(name, sha(path), len(raw))
