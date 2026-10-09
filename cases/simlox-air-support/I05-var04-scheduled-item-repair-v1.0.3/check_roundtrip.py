"""Full authored/exported model oracle for one scheduled ChangesItemRepair row."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from model_common import HERE, REPO, RUN_ID, NATIVE_DIR, RECOVERED_DIR, INPUT_PIN, compare_tables, count_model, exact, seal, strict_json, typed_equal
from source_gate import verify as verify_source

PARENT = REPO / "cases/simlox-air-support/E05-local-repair-reissue-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_EXPORT = PARENT / "runs/e05-v100-ssh-20260929-01/roundtrip-raw.json"
PARENT_INPUT_PIN = {"bytes": 43690, "sha256": "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"}
PARENT_EXPORT_PIN = {"bytes": 57986, "sha256": "896387a14791dd6f14ceec9acf6398beca981656fc0656019e7849df2af79b21"}
NEW_COLUMNS = [
    {"name":"IID","datatype":"string","key":True},
    {"name":"STID","datatype":"string","key":True},
    {"name":"TIMEC","datatype":"double","key":True},
    {"name":"DIRPT","datatype":"double"},
    {"name":"SURPT","datatype":"double"},
    {"name":"DIRPF","datatype":"double"},
    {"name":"SURPF","datatype":"double"},
    {"name":"DIRPD","datatype":"string"},
    {"name":"SURPD","datatype":"string"},
    {"name":"NOTE","datatype":"string"},
]
NEW_ROW = ["TEACH-LRU-01", "BASE-01", 5.0, 1.5, 0.0, 1.0, 1.0, None, None, None]
NEW_TABLE = {"name":"ChangesItemRepair", "columns":NEW_COLUMNS,
             "instances":[{"instance_name":"", "rows":[NEW_ROW]}]}
EXPORT_ORDER = HERE / "preserved-design/export-serialization-v103.json"
EXPORT_ORDER_PIN = {"bytes": 1874, "sha256": "bab7315e63c301eccd7e004d9946d2b4db291279f3d65ec65a3c4cd4e3fca7b7"}

def export_serialization() -> dict[str, object]:
    doc = strict_json(exact(EXPORT_ORDER, EXPORT_ORDER_PIN))
    assert type(doc) is dict and doc["schema"] == "i05-var04-export-serialization/v103"
    assert doc["authored_insertion_index"] == 12 and doc["export_insertion_index"] == 17
    assert doc["export_predecessor"] == "Operations" and doc["export_successor"] == "Unit"
    assert doc["observation_is_not_behavior_acceptance"] is True
    assert doc["superseded_source_delta_field"] == {
        "path":"preserved-design/source-delta.json", "bytes":5997,
        "sha256":"eb0148601892353a2ebfb1cf43a1a76fc3ac746f2f4ed20d5fb4266d9990bcd8",
        "field":"export_gate", "old_export_insertion_index":12,
        "new_export_insertion_index":17,
        "scope":"export table order only; authored input index 12 and all business/log/report oracles unchanged"}
    names = doc["exact_export_table_names"]
    assert type(names) is list and len(names) == len(set(names)) == 32
    assert names[16:19] == ["Operations", "ChangesItemRepair", "Unit"]
    return doc

def predicted_child(parent: object, arm: str) -> dict:
    assert arm in ("authored", "exported")
    root = "model"
    assert count_model(parent, root) == ({"tables":31,"rows":24,"cells":274} if arm == "authored" else {"tables":31,"rows":35,"cells":369})
    child = copy.deepcopy(parent)
    tables = child[root]["tables"]
    assert tables[11]["name"] == "ItemRepair" and tables[12]["name"] != "ChangesItemRepair"
    assert all(table["name"] != "ChangesItemRepair" for table in tables)
    insertion = 12 if arm == "authored" else 17
    if arm == "exported":
        assert tables[16]["name"] == "Operations" and tables[17]["name"] == "Unit"
    tables.insert(insertion, copy.deepcopy(NEW_TABLE))
    if arm == "exported":
        assert [t["name"] for t in tables] == export_serialization()["exact_export_table_names"]
    assert count_model(child, root) == ({"tables":32,"rows":25,"cells":284} if arm == "authored" else {"tables":32,"rows":36,"cells":379})
    return child

def source_oracles() -> dict[str, object]:
    parent_input = strict_json(exact(PARENT_INPUT, PARENT_INPUT_PIN))
    child_input = strict_json(exact(HERE / "native-input.json", INPUT_PIN))
    parent_export = strict_json(exact(PARENT_EXPORT, PARENT_EXPORT_PIN))
    authored = predicted_child(parent_input, "authored")
    exported = predicted_child(parent_export, "exported")
    assert type(child_input) is dict and set(child_input) == {"model"}
    assert typed_equal(authored["model"]["database_version"], child_input["model"]["database_version"])
    assert compare_tables(authored["model"]["tables"], child_input["model"]["tables"]) == 284
    assert compare_tables(parent_export["model"]["tables"], [table for table in exported["model"]["tables"] if table["name"] != "ChangesItemRepair"]) == 369
    return {"authored": authored, "exported": exported,
            "counts": {"authored_tables":32,"authored_rows":25,"authored_cells":284,
                       "exported_tables":32,"exported_rows":36,"exported_cells":379}}

def validate(run: Path, source: bool = True) -> dict[str, object]:
    assert run in (NATIVE_DIR, RECOVERED_DIR) and run.is_dir(), str(run)
    if source:
        verify_source()
    oracles = source_oracles()
    input_actual = strict_json((run / "input.json").read_bytes())
    export_actual = strict_json((run / "roundtrip-raw.json").read_bytes())
    assert seal(run / "input.json") == INPUT_PIN
    assert count_model(input_actual, "model") == {"tables":32,"rows":25,"cells":284}
    assert count_model(export_actual, "model") == {"tables":32,"rows":36,"cells":379}
    assert typed_equal(oracles["authored"]["model"]["database_version"], input_actual["model"]["database_version"])
    assert typed_equal(oracles["exported"]["model"]["database_version"], export_actual["model"]["database_version"])
    assert compare_tables(oracles["authored"]["model"]["tables"], input_actual["model"]["tables"]) == 284
    assert compare_tables(oracles["exported"]["model"]["tables"], export_actual["model"]["tables"]) == 379
    return {"schema":"i05-var04-roundtrip-check/v103", "passed":True,
            "run_id":RUN_ID, "native_run_directory":str(NATIVE_DIR),
            "input_sha256":INPUT_PIN["sha256"], "export_sha256":seal(run / "roundtrip-raw.json")["sha256"],
            **oracles["counts"], "native_calls":0, "issues":[]}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
