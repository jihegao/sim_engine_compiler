"""Build a base aircraft with two additive CBSID configurations and three missions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "E01-local-spare-explicit-replacement-v1.0.0" / "native-input.json"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
A11 = ROOT / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
A11_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"


def table(doc, name):
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def rows(doc, name):
    return table(doc, name)["instances"][0]["rows"]


def build():
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(A11.read_bytes()).hexdigest() == A11_SHA
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    a11 = json.loads(A11.read_text(encoding="utf-8"))
    rows(doc, "ProblemDescription")[0][0] = "A16 base to config A to config B to base; explicit local REMOVE/REPLACE"
    base = rows(doc, "System")[0]
    base[1] = "Base aircraft for two additive configurations"
    base[3:5] = [None, None]
    for sid, desc in (("TEACH-CONF-A", "Configuration adding A LRU"), ("TEACH-CONF-B", "Configuration adding B LRU")):
        config = copy.deepcopy(base)
        config[0:2] = [sid, desc]
        config[7] = base[0]  # CBSID. BSID must stay empty.
        rows(doc, "System").append(config)
    base_item = rows(doc, "Item")[0]
    base_item[3] = 0
    for iid, desc, sid in (("TEACH-LRU-A", "Configuration A additional LRU", "TEACH-CONF-A"), ("TEACH-LRU-B", "Configuration B additional LRU", "TEACH-CONF-B")):
        item = copy.deepcopy(base_item)
        item[0:2] = [iid, desc]
        rows(doc, "Item").append(item)
        rows(doc, "ItemStructure").append([iid, sid, 1, 1.0, None, None, None, None, None])
        repair = copy.deepcopy(rows(doc, "ItemRepair")[0]); repair[0] = iid
        rows(doc, "ItemRepair").append(repair)
        stock = copy.deepcopy(rows(doc, "StockAllocation")[0]); stock[1] = iid
        rows(doc, "StockAllocation").append(stock)
    base_mission = rows(doc, "MissionType")[0]
    base_mission[0:2] = ["BASE-MISSION", "Base aircraft mission"]
    for mtid, desc in (("CONF-A-MISSION", "Mission needs configuration A"), ("CONF-B-MISSION", "Mission needs configuration B")):
        mission = copy.deepcopy(base_mission)
        mission[0:2] = [mtid, desc]
        rows(doc, "MissionType").append(mission)
    for row, mtid in zip(rows(doc, "OperationProfile"), ("CONF-A-MISSION", "CONF-B-MISSION", "BASE-MISSION")):
        row[1] = mtid
    schema = copy.deepcopy(table(a11, "MissionSystem"))
    schema["instances"][0]["rows"] = [
        ["CONF-A-MISSION", "TEACH-CONF-A", 1, 1, 1, None, "configuration A required"],
        ["CONF-B-MISSION", "TEACH-CONF-B", 1, 1, 1, None, "configuration B required"],
        ["BASE-MISSION", base[0], 1, 1, 1, None, "base type required"],
    ]
    doc["model"]["tables"].append(schema)
    rows(doc, "Unit")[0][1] = "One reconfigurable aircraft unit"
    return doc


if __name__ == "__main__":
    target = HERE / "native-input.json"
    generated = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if target.exists():
        assert target.read_text(encoding="utf-8") == generated
    else:
        target.write_text(generated, encoding="utf-8", newline="\n")
    print(hashlib.sha256(target.read_bytes()).hexdigest())
