"""Generate the planned B01--C03 SIMLOX native teaching candidates.

The input is a small, validated case description.  This module writes only
the documented native tables; it is not a Project JSON interpreter, an engine
compiler, or a simulation runtime.  Generated files remain native-unverified
until they have been imported, run, and inspected in the pinned 4700-3 SIMLOX
environment.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LIB = ROOT.parent
PARAMETERS = ROOT / "parameters"
NATIVE = ROOT / "native"
PARENT_DIFFS = ROOT / "parent-diffs"
CASES = ("B01", "B02", "B03", "C01", "C02", "C03")
PARAMETER_SCHEMA = "simlox-preparation-resource-parameters/v1"
STATUS = "planned_native_acceptance"
FAILED_B02_SHA256 = "60c80a4af566de353e31cd8298143d024872b38e699472a4d015cadfa882cb24"
FAILED_RESOURCE_SHA256 = {
    ("C01", "capacity-2"): "93301cecea35423752561c915c362693b7abecc01404a692cca5b28c9621b996",
    ("C01", "capacity-1"): "f6a7356f615fbf4df7142f6759d01324ec13a52a6950af755da05ebd324127bc",
    ("C01", "capacity-0"): "7814bff1988f587ff0746883ffa3834756834d731ba6dbd3a037cd1382b6598a",
    ("C01", "wrong-specialty"): "e78c83ec92f9ad2a5fdbe7bd40200b16bdfdfba1c2bfb3ccd58239a83897ec5c",
    ("C02", "both-available"): "903a44f052c24232e3090a11b6ffeb8706f1f1a509ca60ca1dd2d2308f62363c",
    ("C02", "equipment-zero"): "468c0b960a73ca081c0d9e701a3b270399a1c0682c1d55aeb1fd959b116f51d9",
    ("C03", "staffing-2"): "75db451d3fb6822335fccb2ae66ab730084f86e82ee8d6b15b293bef4077977b",
    ("C03", "staffing-1"): "530dabd7b901bce65d23dfb384552515c55ca5b8b8f01d8f0b23d111dee4a92c",
    ("C03", "staffing-0"): "3209c13a933641b779d2c4949b451c334b74a3f14a09a14d6e1385a1eb733b20",
}

_spec = importlib.util.spec_from_file_location(
    "simlox_a_native_writer", LIB / "tools" / "generate_native.py"
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load the pinned native table writer")
writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(writer)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def integer(value: object, path: str, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, f"{path}: expected integer >= {minimum}")
    return value


def identifier(value: object, path: str) -> str:
    require(type(value) is str and bool(value.strip()), f"{path}: expected nonempty identifier")
    return value


def parameter_path(case_id: str) -> Path:
    return PARAMETERS / f"{case_id}.json"


def active_parameter_path(case_id: str) -> Path:
    if case_id == "B02":
        return PARAMETERS / "B02-v1.0.1.json"
    return parameter_path(case_id)


def candidate_revision(parameters: dict) -> str:
    return parameters.get("candidate_revision", "1.0.0")


def artifact_name(parameters: dict, variant_id: str) -> str:
    base = f"{parameters['case_id']}--{variant_id}"
    revision = candidate_revision(parameters)
    return f"{base}.json" if revision == "1.0.0" else f"{base}--v{revision}.json"


def validate_parameters(p: dict) -> None:
    expected = {
        "schema", "case_id", "version", "parent_case", "status", "source_method_id",
        "units", "site_id", "unit_id", "aircraft_type_id", "aircraft_quantity",
        "mission_types", "waves", "preparation_profiles", "resources", "variants",
        "horizon_minutes", "result_interval_minutes", "repetitions", "native_seed_text",
    }
    require(set(p) in (expected, expected | {"candidate_revision"}),
            f"{p.get('case_id', '?')}: unknown or missing parameter field")
    case_id = p["case_id"]
    require(p["schema"] == PARAMETER_SCHEMA and case_id in CASES, "unsupported parameter schema/case")
    require(p["status"] == STATUS, f"{case_id}: status must preserve native acceptance boundary")
    if "candidate_revision" in p:
        identifier(p["candidate_revision"], f"{case_id}.candidate_revision")
    require(p["source_method_id"] == f"M-{case_id}", f"{case_id}: wrong manual method mapping")
    require(p["units"] == {
        "authored_time": "minute", "native_time": "hour", "minutes_per_hour": 60,
        "resource": "count",
    }, f"{case_id}: invalid units")
    for field in ("site_id", "unit_id", "aircraft_type_id", "version", "native_seed_text"):
        identifier(p[field], f"{case_id}.{field}")
    quantity = integer(p["aircraft_quantity"], f"{case_id}.aircraft_quantity", 1)
    integer(p["horizon_minutes"], f"{case_id}.horizon_minutes", 1)
    integer(p["result_interval_minutes"], f"{case_id}.result_interval_minutes", 1)
    integer(p["repetitions"], f"{case_id}.repetitions", 1)

    mission_ids: set[str] = set()
    for i, mission in enumerate(p["mission_types"]):
        require(set(mission) == {
            "id", "description", "aircraft_required", "minimum_aircraft",
            "flight_duration_minutes", "notice_lead_minutes",
        }, f"{case_id}.mission_types[{i}]: fields")
        mid = identifier(mission["id"], f"{case_id}.mission_types[{i}].id")
        require(mid not in mission_ids, f"{case_id}: duplicate mission type {mid}")
        mission_ids.add(mid)
        required = integer(mission["aircraft_required"], f"{case_id}.{mid}.aircraft_required", 1)
        minimum = integer(mission["minimum_aircraft"], f"{case_id}.{mid}.minimum_aircraft", 1)
        require(minimum <= required <= quantity, f"{case_id}.{mid}: invalid formation size")
        integer(mission["flight_duration_minutes"], f"{case_id}.{mid}.flight_duration", 1)
        integer(mission["notice_lead_minutes"], f"{case_id}.{mid}.notice_lead", 0)

    require(bool(p["waves"]), f"{case_id}: at least one wave is required")
    wave_keys: set[tuple[str, int]] = set()
    for i, wave in enumerate(p["waves"]):
        require(set(wave) == {"mission_type_id", "planned_start_minutes", "quantity", "delay_minutes"},
                f"{case_id}.waves[{i}]: fields")
        mid = identifier(wave["mission_type_id"], f"{case_id}.waves[{i}].mission_type_id")
        require(mid in mission_ids, f"{case_id}: unresolved wave mission {mid}")
        start = integer(wave["planned_start_minutes"], f"{case_id}.waves[{i}].start", 0)
        require((mid, start) not in wave_keys, f"{case_id}: duplicate wave key")
        wave_keys.add((mid, start))
        integer(wave["quantity"], f"{case_id}.waves[{i}].quantity", 1)
        integer(wave["delay_minutes"], f"{case_id}.waves[{i}].delay", 0)

    resource_ids: set[str] = set()
    for i, resource in enumerate(p["resources"]):
        require(set(resource) == {"id", "business_kind", "native_type", "capacity"},
                f"{case_id}.resources[{i}]: fields")
        rid = identifier(resource["id"], f"{case_id}.resources[{i}].id")
        require(rid not in resource_ids, f"{case_id}: duplicate resource {rid}")
        resource_ids.add(rid)
        require(resource["business_kind"] in ("personnel", "equipment"), f"{case_id}.{rid}: kind")
        require(resource["native_type"] == "SPECIAL", f"{case_id}.{rid}: only proven SPECIAL type allowed")
        integer(resource["capacity"], f"{case_id}.{rid}.capacity", 0)

    profile_ids: set[str] = set()
    task_ids: set[str] = set()
    step_type_ids: set[str] = set()
    for i, profile in enumerate(p["preparation_profiles"]):
        require(set(profile) == {"mission_type_id", "aggregate_duration_minutes", "task_id", "task_demands", "steps"},
                f"{case_id}.preparation_profiles[{i}]: fields")
        mid = identifier(profile["mission_type_id"], f"{case_id}.preparation_profiles[{i}].mission")
        require(mid in mission_ids and mid not in profile_ids, f"{case_id}: duplicate/unresolved preparation {mid}")
        profile_ids.add(mid)
        integer(profile["aggregate_duration_minutes"], f"{case_id}.{mid}.aggregate_duration", 0)
        task_id = profile["task_id"]
        steps = profile["steps"]
        require(type(profile["task_demands"]) is dict, f"{case_id}.{mid}: task_demands")
        for rid, demand in profile["task_demands"].items():
            require(rid in resource_ids, f"{case_id}: unresolved task resource demand {rid}")
            integer(demand, f"{case_id}.{mid}.task_demands.{rid}", 1)
        if task_id is None:
            require(not steps and not profile["task_demands"],
                    f"{case_id}.{mid}: task-less scalar preparation cannot have work definitions")
        else:
            task_id = identifier(task_id, f"{case_id}.{mid}.task_id")
            require(task_id not in task_ids, f"{case_id}.{mid}: duplicate task")
            task_ids.add(task_id)
            for seq, step in enumerate(steps, 1):
                require(set(step) == {"id", "duration_minutes", "demands"},
                        f"{case_id}.{task_id}.steps[{seq}]: fields")
                step_id = identifier(step["id"], f"{case_id}.{task_id}.steps[{seq}].id")
                require(step_id not in step_type_ids, f"{case_id}: duplicate subtask type {step_id}")
                step_type_ids.add(step_id)
                integer(step["duration_minutes"], f"{case_id}.{task_id}.{step_id}.duration", 1)
                require(type(step["demands"]) is dict, f"{case_id}.{task_id}.{step_id}: demands")
                for rid, demand in step["demands"].items():
                    require(rid in resource_ids, f"{case_id}: unresolved resource demand {rid}")
                    integer(demand, f"{case_id}.{task_id}.{step_id}.{rid}", 1)
    require(profile_ids == mission_ids, f"{case_id}: each mission type needs one preparation profile")

    variant_ids: set[str] = set()
    for i, variant in enumerate(p["variants"]):
        require(set(variant) == {"variant_id", "description", "resource_capacities"},
                f"{case_id}.variants[{i}]: fields")
        variant_id = identifier(variant["variant_id"], f"{case_id}.variants[{i}].variant_id")
        require(variant_id not in variant_ids, f"{case_id}: duplicate variant {variant_id}")
        variant_ids.add(variant_id)
        require(type(variant["resource_capacities"]) is dict, f"{case_id}.{variant_id}: capacities")
        for rid, capacity in variant["resource_capacities"].items():
            require(rid in resource_ids, f"{case_id}.{variant_id}: unresolved resource {rid}")
            integer(capacity, f"{case_id}.{variant_id}.{rid}", 0)
    require(bool(variant_ids), f"{case_id}: at least one named variant required")

    if case_id == "B01":
        require(p["preparation_profiles"][0]["aggregate_duration_minutes"] == 30,
                "B01 must retain fixed 30 minute scalar preparation")
        require(not p["preparation_profiles"][0]["steps"], "B01 must isolate scalar preparation")
    if case_id == "B02":
        profile = p["preparation_profiles"][0]
        require([s["duration_minutes"] for s in profile["steps"]] == [10, 20], "B02 steps must be 10+20")
        require(profile["aggregate_duration_minutes"] != 30,
                "B02 aggregate scalar must differ from the step sum for the native precedence probe")
        if candidate_revision(p) == "1.0.1":
            require(p["mission_types"][0]["notice_lead_minutes"] == 60,
                    "B02 v1.0.1 must avoid native error #200 with a 60 minute notice period")
    if case_id == "B03":
        require(mission_ids == {"COLD-FIRST", "HOT-SORTIE"}, "B03 requires explicit cold/hot MTIDs")
        require([w["mission_type_id"] for w in p["waves"]] == ["COLD-FIRST", "HOT-SORTIE", "HOT-SORTIE"],
                "B03 requires one cold then two hot waves")
    if case_id == "C03":
        mission = p["mission_types"][0]
        require(quantity == mission["aircraft_required"] == mission["minimum_aircraft"] == 2,
                "C03 requires one two-aircraft formation")
        require(len(p["waves"]) == 1 and p["waves"][0]["planned_start_minutes"] == 480,
                "C03 requires the 08:00 wave")
        require(mission["notice_lead_minutes"] == 30, "C03 preparation must be notified at 07:30")
        require(p["preparation_profiles"][0]["aggregate_duration_minutes"] == 30,
                "C03 requires 30 minutes per aircraft")


def apply_variant(p: dict, variant_id: str) -> dict:
    variants = {variant["variant_id"]: variant for variant in p["variants"]}
    require(variant_id in variants, f"{p['case_id']}: unknown variant {variant_id}")
    result = copy.deepcopy(p)
    overrides = variants[variant_id]["resource_capacities"]
    for resource in result["resources"]:
        if resource["id"] in overrides:
            resource["capacity"] = overrides[resource["id"]]
    result["selected_variant"] = variant_id
    return result


def build(parameters: dict, variant_id: str) -> dict:
    validate_parameters(parameters)
    p = apply_variant(parameters, variant_id)
    # This call supplies the pinned schema envelope and column-aware row writer.
    baseline = read(LIB / "A01-single-aircraft-single-mission" / "parameters.json")
    model = writer.build(baseline)
    for native_table in model["model"]["tables"]:
        native_table["instances"][0]["rows"] = []

    set_rows = lambda name, rows: writer.set_rows(model, name, rows)
    minutes = p["units"]["minutes_per_hour"]
    missions = {mission["id"]: mission for mission in p["mission_types"]}
    case_id = p["case_id"]
    site = p["site_id"]
    sid = p["aircraft_type_id"]
    unit = p["unit_id"]
    horizon = p["horizon_minutes"] / minutes
    interval = p["result_interval_minutes"] / minutes

    set_rows("ProblemDescription", [{"PDESC": f"{case_id}; planned native acceptance candidate"}])
    set_rows("ControlParameters", [{}])
    set_rows("GlobalParameters", [{}])
    allocation_point = "AIR_BASIC"
    set_rows("Control", [{
        "NREPS": p["repetitions"], "SIMPE": horizon, "RSEED": p["native_seed_text"],
        "APID": allocation_point, "RCINT": interval, "RCSTA": 0, "RCEND": horizon,
        "ENPM": "N", "ENLOG": "Y",
    }])
    set_rows("System", [{"SID": sid, "DESCR": "Preparation-resource teaching aircraft", "FRT": 0, "OPID": "OPHOURS"}])
    set_rows("Station", [{"STID": site, "DESCR": "Teaching base", "QTY": 1, "TYPE": "WS"}])
    set_rows("Unit", [{"UNID": unit, "DESCR": "Preparation-resource teaching unit", "STID": site}])
    set_rows("SystemDeployment", [{"SID": sid, "USTID": unit, "QTYPS": p["aircraft_quantity"], "UTIL": 1}])
    set_rows("MissionType", [{
        "MTID": mission["id"], "DESCR": mission["description"],
        "NOS": mission["aircraft_required"], "MNOS": mission["minimum_aircraft"],
        "DURN": mission["flight_duration_minutes"] / minutes, "MSUCPT": 1,
        "TFOUT": 0.25, "TFRET": 0.25, "PRI": 1,
        "NOPER": mission["notice_lead_minutes"] / minutes,
    } for mission in p["mission_types"]])
    set_rows("OperationProfile", [{
        "PRID": "PREP-SCHEDULE", "SPRID": wave["mission_type_id"],
        "STIM": wave["planned_start_minutes"] / minutes, "ITYPE": "SCHEDULED",
        "IQTY": wave["quantity"], "IPER": 0, "DTIM": wave["delay_minutes"] / minutes,
    } for wave in p["waves"]])
    set_rows("OperationParameter", [{}])
    set_rows("Operations", [{"USTID": unit, "PRID": "PREP-SCHEDULE"}])
    set_rows("MissionPreparation", [{
        "MTID": profile["mission_type_id"], "SID": sid, "STID": site,
        "DURN": profile["aggregate_duration_minutes"] / minutes, "TID": profile["task_id"],
    } for profile in p["preparation_profiles"]])

    profiles_with_tasks = [profile for profile in p["preparation_profiles"] if profile["task_id"] is not None]
    set_rows("Tasks", [{"TID": profile["task_id"], "DESCR": f"{profile['mission_type_id']} preparation"}
                       for profile in profiles_with_tasks])
    set_rows("SubTaskType", [{"SUTID": step["id"], "DESCR": step["id"]}
                             for profile in profiles_with_tasks for step in profile["steps"]])
    set_rows("TaskBreakDown", [{
        "TID": profile["task_id"], "SEQ": seq, "SUTID": step["id"],
        "DURN": step["duration_minutes"] / minutes,
    } for profile in profiles_with_tasks for seq, step in enumerate(profile["steps"], 1)])
    set_rows("Resource", [{
        "RID": resource["id"], "DESCR": resource["business_kind"], "TYPE": resource["native_type"],
    } for resource in p["resources"]])
    set_rows("ResourceAllocation", [{
        "POINT": allocation_point, "RID": resource["id"], "STID": site, "RQTY": resource["capacity"],
    } for resource in p["resources"]])
    set_rows("TaskResource", [{
        "TID": profile["task_id"], "RID": rid, "QTY": quantity, "RPROB": 1,
    } for profile in profiles_with_tasks for rid, quantity in profile["task_demands"].items()])
    set_rows("SubTaskResource", [{
        "TID": profile["task_id"], "SEQ": seq, "RID": rid, "QTY": quantity, "RPROB": 1,
    } for profile in profiles_with_tasks for seq, step in enumerate(profile["steps"], 1)
      for rid, quantity in step["demands"].items()])
    result_kinds = ["MISSION", "SYSTEM"] + (["RESOURCE"] if p["resources"] else [])
    set_rows("ResultCollection", [{"RTYPE": kind, "RCINT": interval, "RCSTA": 0, "RCEND": horizon}
                                  for kind in result_kinds])
    validate_native(model, p)
    return model


def validate_native(model: dict, selected_parameters: dict) -> dict[str, list[dict]]:
    schema = read(writer.SCHEMA)
    require(digest(writer.SCHEMA.read_bytes()) == writer.SCHEMA_SHA256, "native schema fingerprint changed")
    require([t["name"] for t in model["model"]["tables"]] ==
            [t["name"] for t in schema["model"]["tables"]], "native table order changed")
    rows: dict[str, list[dict]] = {}
    for native_table, baseline in zip(model["model"]["tables"], schema["model"]["tables"]):
        require(native_table["columns"] == baseline["columns"], f"{native_table['name']}: column layout changed")
        require(len(native_table["instances"]) == 1, f"{native_table['name']}: instance count")
        records: list[dict] = []
        keys: set[tuple] = set()
        for row in native_table["instances"][0]["rows"]:
            require(len(row) == len(native_table["columns"]), f"{native_table['name']}: row width")
            record = dict(zip((column["name"] for column in native_table["columns"]), row))
            for value, column in zip(row, native_table["columns"]):
                if value is None:
                    require(not column.get("key") or (native_table["name"] == "OperationParameter" and all(v is None for v in row)),
                            f"{native_table['name']}.{column['name']}: null key")
                    continue
                kind = column["datatype"]
                valid = ((kind == "string" and type(value) is str) or
                         (kind == "integer" and type(value) is int) or
                         (kind == "double" and type(value) in (int, float) and math.isfinite(value)))
                require(valid, f"{native_table['name']}.{column['name']}: invalid type")
            key = tuple(record[column["name"]] for column in native_table["columns"] if column.get("key"))
            if key:
                require(key not in keys, f"{native_table['name']}: duplicate key {key}")
                keys.add(key)
            records.append(record)
        rows[native_table["name"]] = records

    allowed = {
        "ProblemDescription", "ControlParameters", "GlobalParameters", "Control", "System",
        "Station", "Unit", "SystemDeployment", "MissionType", "OperationProfile",
        "OperationParameter", "Operations", "MissionPreparation", "Tasks", "SubTaskType",
        "TaskBreakDown", "Resource", "ResourceAllocation", "TaskResource",
        "SubTaskResource", "ResultCollection",
    }
    require(all(name in allowed or not records for name, records in rows.items()),
            "an unsupported native mechanism became active")
    ids = {name: {record[field] for record in rows[name]} for name, field in (
        ("System", "SID"), ("Station", "STID"), ("Unit", "UNID"),
        ("MissionType", "MTID"), ("Tasks", "TID"), ("Resource", "RID"),
        ("SubTaskType", "SUTID"),
    )}
    for record in rows["MissionPreparation"]:
        require(record["MTID"] in ids["MissionType"] and record["SID"] in ids["System"] and
                record["STID"] in ids["Station"], "MissionPreparation: unresolved reference")
        require(record["TID"] is None or record["TID"] in ids["Tasks"], "MissionPreparation: unresolved task")
    step_keys = {(record["TID"], record["SEQ"]) for record in rows["TaskBreakDown"]}
    for record in rows["TaskBreakDown"]:
        require(record["TID"] in ids["Tasks"] and record["SUTID"] in ids["SubTaskType"],
                "TaskBreakDown: unresolved reference")
    for record in rows["SubTaskResource"]:
        require((record["TID"], record["SEQ"]) in step_keys and record["RID"] in ids["Resource"],
                "SubTaskResource: unresolved reference")
    allocation_points = {record["APID"] for record in rows["Control"]}
    for record in rows["ResourceAllocation"]:
        require(record["POINT"] in allocation_points and record["STID"] in ids["Station"] and
                record["RID"] in ids["Resource"], "ResourceAllocation: unresolved reference")
    require(all(record["TYPE"] == "SPECIAL" for record in rows["Resource"]), "unproven resource type")
    for record in rows["TaskResource"]:
        require(record["TID"] in ids["Tasks"] and record["RID"] in ids["Resource"],
                "TaskResource: unresolved reference")
    for profile in selected_parameters["preparation_profiles"]:
        if profile["task_demands"]:
            require(all(not step["demands"] for step in profile["steps"]),
                    "task and subtask resource demands must not be silently combined")
    return rows


def keyed_tables(model: dict) -> dict[str, dict[str, dict]]:
    result: dict[str, dict[str, dict]] = {}
    for native_table in model["model"]["tables"]:
        columns = native_table["columns"]
        names = [column["name"] for column in columns]
        key_names = [column["name"] for column in columns if column.get("key")]
        records: dict[str, dict] = {}
        for index, row in enumerate(native_table["instances"][0]["rows"]):
            record = dict(zip(names, row))
            if key_names:
                key_value = {name: record[name] for name in key_names}
            else:
                key_value = {"__row_index__": index}
            key = json.dumps(key_value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            require(key not in records, f"{native_table['name']}: duplicate normalized key")
            records[key] = record
        result[native_table["name"]] = records
    return result


def model_diff(parent: dict, child: dict) -> dict:
    left = keyed_tables(parent)
    right = keyed_tables(child)
    tables = {}
    field_change_count = 0
    added_row_count = 0
    removed_row_count = 0
    for table_name in [table["name"] for table in child["model"]["tables"]]:
        before = left[table_name]
        after = right[table_name]
        added = [{"key": json.loads(key), "row": after[key]} for key in sorted(after.keys() - before.keys())]
        removed = [{"key": json.loads(key), "row": before[key]} for key in sorted(before.keys() - after.keys())]
        changed = []
        for key in sorted(before.keys() & after.keys()):
            fields = {
                field: {"parent": before[key][field], "child": after[key][field]}
                for field in before[key]
                if before[key][field] != after[key][field]
            }
            if fields:
                changed.append({"key": json.loads(key), "fields": fields})
                field_change_count += len(fields)
        if added or removed or changed:
            tables[table_name] = {"added": added, "removed": removed, "changed": changed}
            added_row_count += len(added)
            removed_row_count += len(removed)
    return {
        "table_count": len(tables), "added_row_count": added_row_count,
        "removed_row_count": removed_row_count, "field_change_count": field_change_count,
        "tables": tables,
    }


def parent_model(case_id: str) -> tuple[str, str, dict]:
    if case_id == "B01":
        path = LIB / "A01-single-aircraft-single-mission" / "native-input.json"
        return "A01", "native-input", read(path)
    selections = {
        "B02": ("B01", "fixed-30m"),
        "B03": ("B02", "serial-10m-20m"),
        "C01": ("B02", "serial-10m-20m"),
        "C02": ("C01", "capacity-2"),
        "C03": ("C02", "both-available"),
    }
    parent_case, parent_variant = selections[case_id]
    parent_parameters = read(active_parameter_path(parent_case))
    return parent_case, parent_variant, build(parent_parameters, parent_variant)


def sibling_variant_diff(parameters: dict, variant_id: str, child: dict) -> dict:
    baseline_variant = parameters["variants"][0]["variant_id"]
    baseline = build(parameters, baseline_variant)
    difference = model_diff(baseline, child)
    if parameters["case_id"] == "C03" and variant_id != baseline_variant:
        require(difference["table_count"] == 1 and difference["field_change_count"] == 1 and
                difference["added_row_count"] == difference["removed_row_count"] == 0,
                "C03 staffing variants must differ by exactly one field")
        changed = difference["tables"].get("ResourceAllocation", {}).get("changed", [])
        require(len(changed) == 1 and set(changed[0]["fields"]) == {"RQTY"} and
                changed[0]["key"].get("RID") == "P-CREW",
                "C03 staffing variant changed a field other than P-CREW RQTY")
    return {"baseline_variant_id": baseline_variant, "actual_normalized_diff": difference}


def parent_diff(parameters: dict, variant_id: str) -> dict:
    selected = apply_variant(parameters, variant_id)
    case_id = selected["case_id"]
    if case_id == "B01":
        delta = ["MissionPreparation adds a 30 minute scalar row"]
    elif case_id == "B02":
        delta = ["MissionPreparation points to PREP-SERIAL", "TaskBreakDown adds ordered 10 and 20 minute steps",
                 "aggregate DURN is 45 minutes so native precedence remains an acceptance assertion"]
    elif case_id == "B03":
        delta = ["mission identity splits into COLD-FIRST and HOT-SORTIE",
                 "three waves use explicit MTID mapping with 30/10/10 minute preparations"]
    elif case_id == "C01":
        delta = ["one SPECIAL personnel RID is demanded by the preparation step",
                 "capacity and specialty are changed only by named variants"]
    elif case_id == "C02":
        delta = ["one SPECIAL equipment RID is added to the same preparation step"]
    else:
        delta = ["MissionType NOS and MNOS become 2", "SystemDeployment quantity becomes 2",
                 "one 08:00 wave makes two aircraft compete for a shared personnel pool"]
    parent_case, parent_variant, parent = parent_model(case_id)
    child = build(parameters, variant_id)
    require(parent_case == selected["parent_case"], f"{case_id}: parent selection drift")
    return {
        "schema": "simlox-preparation-resource-parent-diff/v1", "case_id": case_id,
        "variant_id": variant_id, "parent_case": selected["parent_case"], "status": STATUS,
        "parent_variant_id": parent_variant, "declared_delta": delta,
        "actual_normalized_diff": model_diff(parent, child),
        "sibling_variant_diff": sibling_variant_diff(parameters, variant_id, child),
        "native_verified": False,
    }


def all_candidates() -> list[tuple[dict, str]]:
    candidates = []
    for case_id in CASES:
        parameters = read(active_parameter_path(case_id))
        validate_parameters(parameters)
        candidates.extend((parameters, variant["variant_id"]) for variant in parameters["variants"])
    return candidates


def validate_contract_alignment(parameters: dict) -> None:
    case_id = parameters["case_id"]
    contract = read(ROOT / "contracts" / f"{case_id}.json")
    contract_variants = [variant["variant_id"] for variant in contract["variants"]]
    parameter_variants = [variant["variant_id"] for variant in parameters["variants"]]
    require(contract_variants == parameter_variants,
            f"{case_id}: generated variants differ from contract variants")
    model = build(parameters, parameter_variants[0])
    rows = keyed_tables(model)
    expected_tables = contract.get("native_mapping", {}).get("expected_rows", {})
    for table_name, expected in expected_tables.items():
        require(table_name in rows, f"{case_id}: contract names unknown table {table_name}")
        expected_records = expected if isinstance(expected, list) else [expected]
        actual_records = list(rows[table_name].values())
        for expected_record in expected_records:
            require(any(all(actual.get(field) == value for field, value in expected_record.items())
                        for actual in actual_records),
                    f"{case_id}: native rows do not satisfy contract {table_name} {expected_record}")


def check_generated() -> dict:
    checked = []
    failed_b02 = NATIVE / "B02--serial-10m-20m.json"
    require(failed_b02.is_file() and digest(failed_b02.read_bytes()) == FAILED_B02_SHA256,
            "immutable B02 v1.0.0 failed snapshot changed")
    require_failed_resource_snapshots()
    for case_id in CASES:
        validate_contract_alignment(read(active_parameter_path(case_id)))
    for parameters, variant_id in all_candidates():
        case_id = parameters["case_id"]
        name = artifact_name(parameters, variant_id)
        native_path = NATIVE / name
        diff_path = PARENT_DIFFS / name
        expected_native = encoded(build(parameters, variant_id))
        expected_diff = encoded(parent_diff(parameters, variant_id))
        require(native_path.read_bytes() == expected_native, f"stale generated native file: {native_path}")
        require(diff_path.read_bytes() == expected_diff, f"stale generated parent diff: {diff_path}")
        checked.append({"case_id": case_id, "variant_id": variant_id,
                        "candidate_revision": candidate_revision(parameters),
                        "native_sha256": digest(expected_native), "native_verified": False})
    expected_manifest = manifest(checked)
    require((NATIVE / "manifest.json").read_bytes() == encoded(expected_manifest),
            "stale generated native manifest")
    # Frozen A01/A02 are imported as a writer/schema source only and must stay byte-for-byte untouched.
    require(digest(writer.SCHEMA.read_bytes()) == writer.SCHEMA_SHA256, "frozen schema changed")
    return {"status": "generated_static_validated_native_unverified", "candidate_count": len(checked),
            "candidates": checked}


def manifest(candidates: list[dict]) -> dict:
    entries = []
    for candidate in candidates:
        case_id = candidate["case_id"]
        variant_id = candidate["variant_id"]
        revision = candidate["candidate_revision"]
        parameters = read(active_parameter_path(case_id))
        native_name = artifact_name(parameters, variant_id)
        entries.append({
            "case_id": case_id, "variant_id": variant_id,
            "candidate_revision": revision,
            "path": f"native/{native_name}", "input_sha256": candidate["native_sha256"],
            "parameter_path": str(active_parameter_path(case_id).relative_to(ROOT)),
            "parameter_sha256": digest(active_parameter_path(case_id).read_bytes()),
            "parent_diff_path": f"parent-diffs/{native_name}",
            "native_verified": False,
        })
    return {
        "schema": "simlox-preparation-resource-native-manifest/v1", "status": STATUS,
        "native_schema_path": "../native-schema.json", "native_schema_sha256": writer.SCHEMA_SHA256,
        "generator_path": "generate.py", "generator_sha256": digest(Path(__file__).read_bytes()),
        "candidate_count": len(entries), "candidates": entries,
        "failed_candidates": [{
            "case_id": "B02", "variant_id": "serial-10m-20m", "candidate_revision": "1.0.0",
            "path": "native/B02--serial-10m-20m.json", "input_sha256": FAILED_B02_SHA256,
            "status": "native_rejected", "diagnostic": "MissionPreparation error #200",
            "reason": "DURN 45 minutes was longer than or equal to NOPER 30 minutes",
            "native_result": "calc exit 0 with a 4-byte SXO; no behavior acceptance",
        }] + [{
            "case_id": case_id, "variant_id": variant_id, "candidate_revision": "1.0.0",
            "path": f"native/{case_id}--{variant_id}.json", "input_sha256": input_sha256,
            "status": "native_rejected", "diagnostic": "MissionPreparation error #167",
            "reason": "ResourceAllocation.POINT did not match Control.APID AIR_BASIC",
            "native_result": "calc exit 0 with a 4-byte SXO; no behavior acceptance",
        } for (case_id, variant_id), input_sha256 in FAILED_RESOURCE_SHA256.items()],
        "coverage_boundaries": [
            "B03 uses explicit MTID-specific MissionPreparation and TaskBreakDown rows; MissionTurnround is not active or verified",
            "C03 expresses a two-aircraft wave with MissionType.NOS=MNOS=2 and uses SubTaskResource; MissionFormation and TaskResource are not active or verified",
        ],
    }


def write_generated() -> dict:
    NATIVE.mkdir(parents=True, exist_ok=True)
    PARENT_DIFFS.mkdir(parents=True, exist_ok=True)
    failed_b02 = NATIVE / "B02--serial-10m-20m.json"
    require(failed_b02.is_file() and digest(failed_b02.read_bytes()) == FAILED_B02_SHA256,
            "immutable B02 v1.0.0 failed snapshot changed")
    require_failed_resource_snapshots()
    for case_id in CASES:
        validate_contract_alignment(read(active_parameter_path(case_id)))
    written = []
    manifest_candidates = []
    for parameters, variant_id in all_candidates():
        case_id = parameters["case_id"]
        name = artifact_name(parameters, variant_id)
        targets = {
            NATIVE / name: encoded(build(parameters, variant_id)),
            PARENT_DIFFS / name: encoded(parent_diff(parameters, variant_id)),
        }
        for path, raw in targets.items():
            path.write_bytes(raw)
        written.append({"case_id": case_id, "variant_id": variant_id,
                        "candidate_revision": candidate_revision(parameters)})
        manifest_candidates.append({"case_id": case_id, "variant_id": variant_id,
                                    "candidate_revision": candidate_revision(parameters),
                                    "native_sha256": digest(targets[NATIVE / name])})
    (NATIVE / "manifest.json").write_bytes(encoded(manifest(manifest_candidates)))
    return {"status": "generated_native_candidates_not_executed", "written": written}


def require_failed_resource_snapshots() -> None:
    for (case_id, variant_id), expected_sha256 in FAILED_RESOURCE_SHA256.items():
        path = NATIVE / f"{case_id}--{variant_id}.json"
        require(path.is_file() and digest(path.read_bytes()) == expected_sha256,
                f"immutable {case_id} {variant_id} v1.0.0 failed snapshot changed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-all", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--variant")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.case or args.variant or args.output:
        require(not args.write_all and args.case and args.variant and args.output,
                "single output mode requires --check --case --variant --output")
        parameters = read(active_parameter_path(args.case))
        raw = encoded(build(parameters, args.variant))
        with args.output.open("xb") as stream:
            stream.write(raw)
        report = {"status": "candidate_not_native_accepted", "path": str(args.output), "sha256": digest(raw)}
    else:
        report = write_generated() if args.write_all else check_generated()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
