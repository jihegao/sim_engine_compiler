"""Build an isolated D05 fault, PM, and shared-worker native probe from D03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA256 = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUTPUT = HERE / "native-input.json"


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table shape")
    return found[0]


def cols(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(model: dict, name: str) -> list[list]:
    return table(model, name)["instances"][0]["rows"]


def set_one(model: dict, name: str, **values: object) -> None:
    t = table(model, name)
    if len(rows(model, name)) != 1 or set(values) - set(cols(t)):
        raise ValueError(f"unexpected {name} row/columns")
    for key, value in values.items():
        rows(model, name)[0][cols(t).index(key)] = value


def add(model: dict, name: str, **values: object) -> None:
    t = table(model, name)
    if set(values) - set(cols(t)):
        raise ValueError(f"unknown {name} fields")
    rows(model, name).append([values.get(c) for c in cols(t)])


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("published D03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    m = doc["model"]
    set_one(m, "ProblemDescription", PDESC="D05 pilot: system fault and calendar PM compete for one maintainer")
    set_one(m, "Control", SIMPE=36.0, RCEND=36.0)
    for row in rows(m, "ResultCollection"):
        row[cols(table(m, "ResultCollection")).index("RCEND")] = 36.0
    set_one(m, "SystemDeployment", QTYPS=2)
    set_one(m, "Unit", DESCR="Two-aircraft shared-maintainer teaching unit", MAXPM=2)
    set_one(m, "System", FRT=1_000_000.0)
    set_one(m, "MaterielPM", DTIM=0.5)
    if rows(m, "SystemRepair"):
        raise ValueError("published D03 has unexpected system repair")
    add(m, "SystemRepair", SID="TEACH-AIR-01", STID="BASE-01", DIRPT=5.0,
        SURPT=0.0, DIRPF=1.0, SURPF=1.0, DIRPTID="CM-DIRECT")
    add(m, "Tasks", TID="CM-DIRECT", DESCR="Five-hour direct system repair")
    add(m, "TaskBreakDown", TID="CM-DIRECT", SEQ=1, SUTID="<REPAIR>", DURN=5.0)
    add(m, "Resource", RID="P-MAINT", DESCR="One shared maintenance worker", TYPE="SPECIAL")
    add(m, "ResourceAllocation", POINT="AIR_BASIC", RID="P-MAINT", STID="BASE-01", RQTY=1)
    add(m, "SubTaskResource", TID="PM-CAL24", SEQ=1, RID="P-MAINT", QTY=1, RPROB=1.0)
    add(m, "SubTaskResource", TID="CM-DIRECT", SEQ=1, RID="P-MAINT", QTY=1, RPROB=1.0)
    mt = table(m, "MissionType")
    base = rows(m, "MissionType")[0]
    base[cols(mt).index("MFF")] = 0.0
    risk = copy.deepcopy(base)
    risk[cols(mt).index("MTID")] = "RISK-MISSION"
    risk[cols(mt).index("DESCR")] = "Three-hour failure exposure"
    risk[cols(mt).index("DURN")] = 3.0
    risk[cols(mt).index("MFF")] = 1.0
    rows(m, "MissionType").append(risk)
    profile = table(m, "OperationProfile")
    waves = rows(m, "OperationProfile")
    if [w[cols(profile).index("STIM")] for w in waves] != [8.0, 20.0, 32.0]:
        raise ValueError("published D03 mission waves differ")
    waves[1][cols(profile).index("SPRID")] = "RISK-MISSION"
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D05 pilot input differs")
    print(json.dumps({"case_id": "D05", "status": "native_probe", "parent_sha256": PARENT_SHA256,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
