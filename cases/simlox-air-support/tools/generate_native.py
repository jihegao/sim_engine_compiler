"""Generate the A01/A02 SIMLOX teaching inputs from a row-free native schema.

This is a native SIMLOX table writer, not an interpreter for spare_mvp Project
JSON and not an Execution Plan compiler.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "native-schema.json"
SCHEMA_SHA256 = "162679fd6e06e64c83f004417122379e773f47b1ea089c7e0c1a06f2f560c65e"
DIRS = {
    "A01": ROOT / "A01-single-aircraft-single-mission",
    "A02": ROOT / "A02-single-aircraft-repeated-missions",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["model"]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} table")
    return matches[0]


def set_rows(model: dict, name: str, mappings: list[dict]) -> None:
    target = table(model, name)
    if len(target["instances"]) != 1:
        raise ValueError(f"{name} must have exactly one schema instance")
    names = [column["name"] for column in target["columns"]]
    for row in mappings:
        unknown = set(row) - set(names)
        if unknown:
            raise ValueError(f"unknown {name} columns: {sorted(unknown)}")
    target["instances"][0]["rows"] = [[row.get(column) for column in names] for row in mappings]


def validate_parameters(parameters: dict) -> None:
    case = parameters.get("case_id")
    if case not in DIRS:
        raise ValueError("only A01/A02 are implemented")
    expected = json.loads((DIRS[case] / "parameters.json").read_text(encoding="utf-8"))
    if set(parameters) != set(expected):
        raise ValueError("parameter keys differ from frozen v1 contract")
    for key, value in expected.items():
        candidate = parameters[key]
        if type(candidate) is not type(value):
            raise ValueError(f"{key} has wrong type for frozen v1 contract")
        if isinstance(value, float) and (not math.isfinite(candidate) or candidate != value):
            raise ValueError(f"{key} differs from frozen v1 contract")
        if isinstance(value, list):
            if len(candidate) != len(value) or any(type(a) is not type(b) or
                (isinstance(a, float) and not math.isfinite(a)) or a != b
                for a, b in zip(candidate, value)):
                raise ValueError(f"{key} differs from frozen v1 contract")
        elif candidate != value:
            raise ValueError(f"{key} differs from frozen v1 contract")


def build(parameters: dict) -> dict:
    if sha256(SCHEMA) != SCHEMA_SHA256:
        raise ValueError("native table schema fingerprint changed")
    validate_parameters(parameters)
    case = parameters["case_id"]
    starts = parameters["planned_start_hours"]
    if starts != ([8.0] if case == "A01" else [8.0, 20.0, 32.0]):
        raise ValueError("this version's scheduled waves are frozen")
    if any(later < earlier + parameters["mission_duration_hours"] for earlier, later in zip(starts, starts[1:])):
        raise ValueError("mission instances overlap")
    model = copy.deepcopy(json.loads(SCHEMA.read_text(encoding="utf-8")))
    sid, stid, unid = (parameters[key] for key in ("stable_aircraft_sid", "base_stid", "unit_unid"))
    mtid, prid = (parameters[key] for key in ("mission_mtid", "operation_prid"))
    horizon = parameters["horizon_hours"]
    set_rows(model, "ProblemDescription", [{"PDESC": "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"}])
    set_rows(model, "ControlParameters", [{}])
    set_rows(model, "GlobalParameters", [{}])
    set_rows(model, "Control", [{"NREPS": parameters["repetitions"], "SIMPE": horizon,
                                 "RSEED": parameters["native_seed_text"], "APID": "AIR_BASIC",
                                 "RCINT": parameters["result_interval_hours"], "RCSTA": 0,
                                 "RCEND": horizon, "ENPM": "N", "ENLOG": "Y"}])
    set_rows(model, "System", [{"SID": sid, "DESCR": "Generic teaching aircraft",
                                "FRT": 0, "OPID": "OPHOURS"}])
    set_rows(model, "Station", [{"STID": stid, "DESCR": "Teaching base", "QTY": 1, "TYPE": "WS"}])
    set_rows(model, "SystemDeployment", [{"SID": sid, "USTID": unid, "QTYPS": 1, "UTIL": 1}])
    set_rows(model, "Unit", [{"UNID": unid, "DESCR": "One-aircraft teaching unit", "STID": stid}])
    set_rows(model, "MissionType", [{"MTID": mtid, "DESCR": "Two-hour generic mission", "NOS": 1,
                                     "MNOS": 1, "DURN": parameters["mission_duration_hours"],
                                     "MSUCPT": 1, "TFOUT": 0.25, "TFRET": 0.25,
                                     "PRI": 1, "NOPER": parameters["notice_lead_hours"]}])
    set_rows(model, "OperationProfile", [{"PRID": prid, "SPRID": mtid, "STIM": start,
                                           "ITYPE": "SCHEDULED", "IQTY": 1, "IPER": 0,
                                           "DTIM": parameters["delay_window_hours"]} for start in starts])
    set_rows(model, "OperationParameter", [{}])
    set_rows(model, "Operations", [{"USTID": unid, "PRID": prid}])
    set_rows(model, "MissionPreparation", [])
    set_rows(model, "ResultCollection", [{"RTYPE": kind, "RCINT": parameters["result_interval_hours"],
                                           "RCSTA": 0, "RCEND": horizon} for kind in ("MISSION", "SYSTEM")])
    # All other row-free schema tables stay empty: no item, failure repair,
    # preventive maintenance, resource, stock, task or transport transaction.
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(DIRS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--omit-native-preparation-row", action="store_true",
                        help="explicit spelling of the default row-free configuration; retained for diagnostic replay")
    parser.add_argument("--with-native-preparation-row", action="store_true",
                        help="diagnostic only: add the obsolete zero-duration row that increments NPSTA")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    params = json.loads((DIRS[args.case] / "parameters.json").read_text(encoding="utf-8"))
    model = build(params)
    if args.with_native_preparation_row and args.omit_native_preparation_row:
        raise ValueError("preparation-row flags conflict")
    if args.with_native_preparation_row:
        set_rows(model, "MissionPreparation", [{"MTID": params["mission_mtid"], "SID": params["stable_aircraft_sid"],
                                                "STID": params["base_stid"], "DURN": 0, "TID": None}])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"case_id": args.case, "path": str(args.output), "sha256": sha256(args.output)}))


if __name__ == "__main__":
    main()
