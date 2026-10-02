"""Freeze a paired explicit/inherited installed-item prelife model."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import argparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "D14-var01-monitored-item-pm-v1.0.1" / "native-input-monitored.json"
PARENT_SHA = "29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903"
PRELIFE_DONOR = ROOT / "G11-var03-random-system-prelife-v1.0.0" / "native-input-equidist-control.json"
PRELIFE_DONOR_SHA = "9ee61443dc0cd0d774d5c1bc6f77343e87fe25ff9bda3772f2b8f37f520c2748"
ARMS = ("explicit-control", "inherited")


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"table schema mismatch: {name}")
    return matches[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def put(row: list, tbl: dict, **fields) -> None:
    names = [c["name"] for c in tbl["columns"]]
    for name, value in fields.items():
        row[names.index(name)] = value


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D14.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    donor_raw = PRELIFE_DONOR.read_bytes()
    if hashlib.sha256(donor_raw).hexdigest() != PRELIFE_DONOR_SHA:
        raise ValueError("accepted G11 prelife schema donor changed")
    g11 = json.loads(donor_raw)

    rows(doc, "ProblemDescription")[0][0] = "G11.var04 item prelife via position; " + arm
    ctl = table(doc, "Control")
    put(rows(doc, "Control")[0], ctl, SIMPE=96.0, RCEND=96.0)
    profile = table(doc, "OperationProfile")
    if [r[2] for r in rows(doc, "OperationProfile")] != [8.0, 20.0, 32.0]:
        raise ValueError("accepted mission schedule differs")
    for row in rows(doc, "OperationProfile"):
        put(row, profile, IQTY=0)
    for row in rows(doc, "ResultCollection"):
        names = [c["name"] for c in table(doc, "ResultCollection")["columns"]]
        if "RCEND" in names:
            row[names.index("RCEND")] = 96.0
    put(rows(doc, "SystemDeployment")[0], table(doc, "SystemDeployment"), PLID="PL-SYS")
    pm = table(doc, "MaterielPM")
    pmrow = rows(doc, "MaterielPM")[0]
    if pmrow[0] != "LRU-OP2" or pmrow[[c["name"] for c in pm["columns"]].index("MONIT")] != "Y":
        raise ValueError("accepted monitored item PM differs")
    put(pmrow, pm, PMID="LRU-CAL100", DESCR="Monitored item calendar service", PMINT=100.0, OPID="CALHOURS")
    system_pm = [None] * len(pm["columns"])
    put(system_pm, pm, PMID="SYS-CAL1000", DESCR="System calendar service outside horizon", MID="TEACH-AIR-01", PMINT=1000.0, OPID="CALHOURS", ATIM=0.0, DTIM=0.0)
    rows(doc, "MaterielPM").append(system_pm)
    replacement = table(doc, "PMReplacement")
    put(rows(doc, "PMReplacement")[0], replacement, PMID="LRU-CAL100", OPID=None)
    for name in ("PMLocation", "PMTask"):
        matches = [t for t in doc["model"]["tables"] if t["name"] == name]
        if matches:
            tbl = matches[0]
            cols = [c["name"] for c in tbl["columns"]]
            for row in tbl["instances"][0]["rows"]:
                if "PMID" in cols and row[cols.index("PMID")] == "LRU-OP2":
                    row[cols.index("PMID")] = "LRU-CAL100"
    location = table(doc, "PMLocation")
    system_location = [None] * len(location["columns"])
    put(system_location, location, PMID="SYS-CAL1000", ID="TEACH-AIR-01", STID="BASE-01", PMT=0.5)
    rows(doc, "PMLocation").append(system_location)
    # Any additional parent reference to the PM identifier must be changed explicitly.
    for tbl in doc["model"]["tables"]:
        if tbl["name"] in {"MaterielPM", "PMReplacement", "PMLocation", "PMTask"}:
            continue
        if any("LRU-OP2" in row for row in tbl["instances"][0]["rows"]):
            raise ValueError(f"unhandled PM reference in {tbl['name']}")

    prelife = copy.deepcopy(table(g11, "Prelife"))
    prelife["instances"][0]["rows"] = [
        ["PL-SYS", "System initial calendar age", "TEACH-AIR-01", None],
        ["PL-POS", "Position inherits system", "POS-A", None],
        ["PL-LRU", "Installed monitored item age", "TEACH-LRU-01", None],
    ]
    pdata = copy.deepcopy(table(g11, "PrelifeData"))
    pdata["instances"][0]["rows"] = [
        ["PL-SYS", "SYS-60", 1, 60.0, None, "CALHOURS", "FIXED", None],
        ["PL-POS", "POS-INH", 1, 0.0, None, "CALHOURS", "INHERIT", None],
        ["PL-LRU", "LRU-20", 1, 20.0, None, "CALHOURS",
         "FIXED" if arm == "explicit-control" else "INHERIT", None],
    ]
    structure = {
        "columns": [
            {"datatype": "string", "key": True, "name": "PLID"},
            {"datatype": "string", "key": True, "name": "MPLID"},
            {"datatype": "string", "key": True, "name": "MPLIND"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [
            ["PL-POS", "PL-SYS", "SYS-60", None],
            ["PL-LRU", "PL-POS", "POS-INH", None],
        ]}],
        "name": "PrelifeStructure",
    }
    doc["model"]["tables"].extend([prelife, pdata, structure])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    shas = {}
    for arm in ARMS:
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var04", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
