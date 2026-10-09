"""Strict authored and native export oracle for one scheduled turnround row."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from model_common import HERE, REPO, RUN_ID, NATIVE_DIR, RECOVERED_DIR, INPUT_PIN, EXPORT_PIN, compare_tables, count_model, exact, seal, strict_json, typed_equal
from source_gate import verify as verify_source

PARENT = REPO / "cases/simlox-air-support/B04-cross-midnight-turnround-v1.0.1"
PARENT_INPUT = PARENT / "turnround-input.json"
PARENT_EXPORT = PARENT / "runs/b04-v101-turnround-20260930-01/roundtrip-raw.json"
PARENT_INPUT_PIN = {"bytes":42867,"sha256":"9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"}
PARENT_EXPORT_PIN = {"bytes":58901,"sha256":"f16c59e16c7fadbf52a94fced3a15d389abeac647301601a434fb16dca8f2677"}
NEW_COLUMNS = [
    {"name":"MTID","datatype":"string","key":True},
    {"name":"SID","datatype":"string","key":True},
    {"name":"STID","datatype":"string","key":True},
    {"name":"TIMEC","datatype":"double","key":True},
    {"name":"DURN","datatype":"double"},
    {"name":"DURND","datatype":"string"},
    {"name":"NOTE","datatype":"string"},
]
NEW_ROW = ["BASIC-MISSION","TEACH-AIR-01","BASE-01",25.0,1.5,None,None]
NEW_TABLE = {"name":"ChangesMissionTurnround","columns":NEW_COLUMNS,
             "instances":[{"instance_name":"","rows":[NEW_ROW]}]}

def predicted(parent: object, arm: str) -> dict:
    assert arm in ("authored","exported")
    assert count_model(parent,"model")==({"tables":32,"rows":22,"cells":204} if arm=="authored"
                                         else {"tables":32,"rows":36,"cells":367})
    child = copy.deepcopy(parent)
    assert type(child) is dict and set(child)=={"model"}
    tables = child["model"]["tables"]
    assert type(tables) is list and len(tables)==32
    assert tables[-1]["name"]=="MissionTurnround"
    assert all(table["name"]!="ChangesMissionTurnround" for table in tables)
    addition=copy.deepcopy(NEW_TABLE)
    if arm=="exported":
        addition["instances"][0]["rows"][0][3]=25
    tables.append(addition)
    assert len(tables)==33 and tables[32]["name"]=="ChangesMissionTurnround"
    return child

def source_oracles() -> dict[str,object]:
    parent_input=strict_json(exact(PARENT_INPUT,PARENT_INPUT_PIN))
    parent_export=strict_json(exact(PARENT_EXPORT,PARENT_EXPORT_PIN))
    authored=predicted(parent_input,"authored")
    exported=predicted(parent_export,"exported")
    expected_input=strict_json(exact(HERE/"native-input.json",INPUT_PIN))
    expected_export=strict_json(exact(HERE/"preserved-design/expected-export.json",EXPORT_PIN))
    assert count_model(authored,"model")==count_model(expected_input,"model")=={"tables":33,"rows":23,"cells":211}
    assert count_model(exported,"model")==count_model(expected_export,"model")=={"tables":33,"rows":37,"cells":374}
    assert typed_equal(authored["model"]["database_version"],expected_input["model"]["database_version"])
    assert typed_equal(exported["model"]["database_version"],expected_export["model"]["database_version"])
    assert compare_tables(authored["model"]["tables"],expected_input["model"]["tables"])==211
    assert compare_tables(exported["model"]["tables"],expected_export["model"]["tables"])==374
    assert typed_equal(authored,expected_input), "authored representation differs"
    assert typed_equal(exported,expected_export), "export integral-double representation differs"
    assert [t["name"] for t in authored["model"]["tables"]]==[t["name"] for t in exported["model"]["tables"]]
    return {"authored":authored,"exported":exported}

def validate(run: Path, source: bool=True) -> dict[str,object]:
    assert run in (NATIVE_DIR,RECOVERED_DIR) and run.is_dir(), str(run)
    if source: verify_source()
    expected=source_oracles()
    actual_input=strict_json((run/"input.json").read_bytes())
    actual_export=strict_json((run/"roundtrip-raw.json").read_bytes())
    assert seal(run/"input.json")==INPUT_PIN
    assert count_model(actual_input,"model")=={"tables":33,"rows":23,"cells":211}
    assert count_model(actual_export,"model")=={"tables":33,"rows":37,"cells":374}
    assert typed_equal(expected["authored"]["model"]["database_version"],actual_input["model"]["database_version"])
    assert typed_equal(expected["exported"]["model"]["database_version"],actual_export["model"]["database_version"])
    assert compare_tables(expected["authored"]["model"]["tables"],actual_input["model"]["tables"])==211
    assert compare_tables(expected["exported"]["model"]["tables"],actual_export["model"]["tables"])==374
    assert typed_equal(expected["authored"],actual_input), "authored typed model differs"
    assert typed_equal(expected["exported"],actual_export), "export typed model differs"
    return {"schema":"i05-var07-roundtrip-check/v101","passed":True,"run_id":RUN_ID,
            "native_run_directory":str(NATIVE_DIR),"input_sha256":INPUT_PIN["sha256"],
            "export_sha256":seal(run/"roundtrip-raw.json")["sha256"],
            "authored_tables":33,"authored_rows":23,"authored_cells":211,
            "exported_tables":33,"exported_rows":37,"exported_cells":374,
            "native_calls":0,"issues":[]}

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-dir",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(validate(args.run_dir),sort_keys=True))

if __name__=="__main__": main()
