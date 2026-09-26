"""Add the pinned F35 Plan's serial work steps to an isolated SIMLOX JSON model.

This preserves the original native candidate as input evidence. The output is a
new JSON import candidate; SIMLOX must still import, export, and run it.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


PINNED_INPUT_SHA256 = {
    "base_json": "065fd59e257fe3609b5feea63149b662a9ab5ef45ad929ee1d35d878e4920dfa",
    "canonical": "a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d",
    "plan": "548f77dfc61b9c545f5ac17eefcd5443f265a1530818696f9cafed7c3dd97298",
    "dictionary": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_columns(dictionary: Path, name: str) -> list[dict]:
    types = {"Text": "string", "Integer": "integer", "Floating point": "double"}
    columns = []
    for line in dictionary.read_text(encoding="utf-8-sig").splitlines():
        fields = line.split(";")
        if len(fields) < 7 or fields[0] != name or fields[5] not in types:
            continue
        column = {"name": fields[2], "datatype": types[fields[5]]}
        if fields[4] == "Index":
            column["key"] = True
        columns.append(column)
    if not columns:
        raise ValueError(f"missing SIMLOX dictionary table {name}")
    return columns


def get_table(model: dict, name: str) -> dict:
    matches = [table for table in model["model"]["tables"] if table["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} table, got {len(matches)}")
    return matches[0]


def records(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    instances = table["instances"]
    if len(instances) != 1:
        raise ValueError(f"expected one instance in {table['name']}")
    return [dict(zip(columns, row, strict=True)) for row in instances[0]["rows"]]


def replace_records(table: dict, items: list[dict]) -> None:
    columns = [column["name"] for column in table["columns"]]
    table["instances"][0]["rows"] = [
        [item.get(column) for column in columns] for item in items
    ]


def add_table(model: dict, dictionary: Path, name: str, items: list[dict]) -> None:
    if any(table["name"] == name for table in model["model"]["tables"]):
        raise ValueError(f"table {name} already exists")
    table = {
        "name": name,
        "columns": table_columns(dictionary, name),
        "instances": [{"instance_name": "", "rows": []}],
    }
    replace_records(table, items)
    model["model"]["tables"].append(table)


def build(base: dict, canonical: dict, plan: dict, dictionary: Path) -> tuple[dict, dict]:
    if plan["plan_version"] != "aircraft-support-plan/v1alpha2":
        raise ValueError("unexpected Plan version")
    if plan["work_policy"] != "stable-topological-serial":
        raise ValueError("only the accepted serial F35 work policy is supported")
    model = copy.deepcopy(base)
    # The pinned candidate stored per-hour rates directly. SIMLOX 2017's FRT
    # is failures per million OPIDs; OPID=OPHOURS in this model.
    for name in ("Item", "System"):
        reliability_rows = records(get_table(model, name))
        for row in reliability_rows:
            if row.get("FRT") is not None:
                row["FRT"] *= 1_000_000
                row["NOTE"] = (
                    str(row.get("NOTE") or "")
                    + " | source per-hour rate multiplied by 1e6 for SIMLOX 1/MOPIDs"
                )
        replace_records(get_table(model, name), reliability_rows)
    source_activities = {
        activity["id"]: activity
        for activity in canonical["support_activities"]["activities"]
    }
    plan_activities = {
        activity["activity_id"]: activity for activity in plan["activities"]
    }
    if len(source_activities) != len(plan_activities):
        raise ValueError("source/Plan activity count mismatch")
    if set(source_activities) != set(plan_activities):
        raise ValueError("source/Plan activity IDs differ")

    task_id = {}
    for activity in plan["activities"]:
        aid = activity["activity_id"]
        if aid == "f35-service-0103":
            task_id[aid] = "MISSION_PREP"
        elif aid == "preventive-f35-6":
            task_id[aid] = "PM_25H"
        elif aid == "preventive-f35-50h-24h":
            task_id[aid] = "PM_50H"
        elif aid == "corrective-f35-generic-lru-replacement":
            task_id[aid] = "CM_GENERIC"
        elif activity["kind"] == "repair":
            task_id[aid] = f"CM_{aid}"

    existing_tasks = records(get_table(model, "Tasks"))
    existing_ids = {row["TID"] for row in existing_tasks}
    if set(task_id.values()) != existing_ids:
        raise ValueError("base SIMLOX Tasks differ from the pinned F35 task mapping")
    for row in existing_tasks:
        aid = next(aid for aid, tid in task_id.items() if tid == row["TID"])
        row["NOTE"] = f"canonical activity={aid}; accepted Plan steps"
    replace_records(get_table(model, "Tasks"), existing_tasks)

    types = {"personnel": set(), "equipment": set()}
    for aid in task_id:
        for job in source_activities[aid].get("jobs") or []:
            types["personnel"].update(
                str(value.get("professional") or "").strip()
                for value in job.get("personnel") or []
            )
            types["equipment"].update(
                str(value.get("model") or value.get("name") or "").strip()
                for value in job.get("equipment") or []
            )
    resource_rows = records(get_table(model, "Resource"))
    if {row["RID"] for row in resource_rows} != {"PERSONNEL", "DEVICE"}:
        raise ValueError("base resource pool differs from pinned F35 candidate")

    subtask_types = []
    breakdown = []
    requirements = []
    mapping_steps = []
    preflight = plan_activities["f35-service-0103"]
    for activity in plan["activities"]:
        aid = activity["activity_id"]
        if aid not in task_id:
            continue
        tid = task_id[aid]
        raw_jobs = {
            job["activityCode"]: job
            for job in source_activities[aid].get("jobs") or []
        }
        if activity["kind"] == "repair" and len(activity["steps"]) != 1:
            raise ValueError(f"repair task {tid} is not a single accepted Plan step")
        for step in activity["steps"]:
            code = step["code"]
            if code not in raw_jobs:
                raise ValueError(f"missing canonical job {aid}/{code}")
            raw = raw_jobs[code]
            if aid == preflight["activity_id"]:
                seq = step["index"] + 1
                sutid = f"F35P{seq:02d}"
                subtask_types.append(
                    {
                        "SUTID": sutid,
                        "DESCR": str(raw.get("workName") or code),
                        "NOTE": f"canonical activityCode={code}",
                    }
                )
                substeps = [(seq, sutid, step["duration_minutes"])]
            elif activity["kind"] == "repair":
                # SIMLOX replacement requires both REMOVE and REPLACE. The
                # source has only one duration, so the 50/50 split is explicit
                # approximation; their sum still equals the accepted Plan step.
                half = step["duration_minutes"] / 2
                substeps = [(1, "<REMOVE>", half), (2, "<REPLACE>", half)]
            else:
                substeps = [(step["index"] + 1, "<INSPECT>", step["duration_minutes"])]
            required = {"PERSONNEL": step["personnel"], "DEVICE": step["equipment"]}
            declared = {"personnel": [], "equipment": []}
            for kind, field in (("personnel", "personnel"), ("equipment", "equipment")):
                for value in raw.get(field) or []:
                    label = str(value.get("professional") if kind == "personnel" else value.get("model") or value.get("name") or "").strip()
                    if not label:
                        raise ValueError(f"blank declared {kind} in {aid}/{code}")
                    quantity = int(value.get("quantity", 1))
                    if quantity <= 0:
                        raise ValueError(f"nonpositive declared {kind} in {aid}/{code}")
                    declared[kind].append({"label": label, "quantity": quantity})
            declared_note = " | ".join(
                f"{kind}=" + (
                    ",".join(f"{row['label']}x{row['quantity']}" for row in declared[kind])
                    or "none"
                )
                for kind in ("personnel", "equipment")
            )
            for seq, sutid, duration_minutes in substeps:
                breakdown.append(
                    {
                        "TID": tid,
                        "SEQ": seq,
                        "SUTID": sutid,
                        "DURN": duration_minutes / 60,
                        "NOTE": f"canonical code={code} | {declared_note}"
                        + (" | replacement time split 50/50" if activity["kind"] == "repair" else ""),
                    }
                )
                for rid, quantity in required.items():
                    requirements.append(
                        {
                            "TID": tid,
                            "SEQ": seq,
                            "RID": rid,
                            "QTY": quantity,
                            "RPROB": 1,
                            "NOTE": "accepted Plan pooled resource",
                        }
                    )
                mapping_steps.append(
                    {
                        "activity_id": aid,
                        "task_id": tid,
                        "seq": seq,
                        "subtask_type": sutid,
                        "code": code,
                        "duration_minutes": duration_minutes,
                        "plan_personnel": step["personnel"],
                        "plan_equipment": step["equipment"],
                        "declared": declared,
                        "predecessors": step["predecessors"],
                    }
                )

    if len(preflight["steps"]) != 14 or sum(step["duration_minutes"] for step in preflight["steps"]) != 142:
        raise ValueError("unexpected pinned F35 preflight steps")
    prep_rows = records(get_table(model, "MissionPreparation"))
    if len(prep_rows) != 1 or prep_rows[0]["TID"] != "MISSION_PREP":
        raise ValueError("unexpected base mission preparation")
    prep_rows[0]["DURN"] = 142 / 60
    prep_rows[0]["NOTE"] = "14 accepted Plan steps, 142 nominal minutes; SIMLOX serial subtasks"
    replace_records(get_table(model, "MissionPreparation"), prep_rows)

    repair_rows = records(get_table(model, "ItemRepair"))
    components = {component["component_id"].upper(): component for component in plan["components"]}
    if len(repair_rows) != 423:
        raise ValueError("unexpected base ItemRepair count")
    replacements = []
    structure_rows = records(get_table(model, "ItemStructure"))
    if len(structure_rows) != 423:
        raise ValueError("unexpected base ItemStructure count")
    for structure in structure_rows:
        component = components[structure["IID"].upper()]
        activity = plan["activities"][component["repair_activity_index"]]
        tid = task_id[activity["activity_id"]]
        replacements.append(
            {
                "MID": structure["MID"],
                "IID": structure["IID"],
                "STID": "BASE",
                "SURPT": activity["steps"][0]["duration_minutes"] / 60,
                "SURPF": 1,
                "SURPTID": tid,
                "NOTE": f"canonical activity={activity['activity_id']}; 2-step replacement approximation",
            }
        )
    for row in repair_rows:
        component = components[row["IID"].upper()]
        activity = plan["activities"][component["repair_activity_index"]]
        row["DIRPTID"] = None
        row["DIRPT"] = 0
        row["NOTE"] = f"removed item instant refurbishment placeholder; canonical activity={activity['activity_id']}"
    replace_records(get_table(model, "ItemRepair"), repair_rows)

    add_table(
        model,
        dictionary,
        "SystemRepair",
        [
            {
                "SID": "F35",
                "STID": "BASE",
                "DIRPT": 0,
                "SURPT": 3,
                "DIRPF": 0,
                "SURPF": 1,
                "SURPTID": "CM_GENERIC",
                "NOTE": "fallback; ItemReplacement overrides per component",
            }
        ],
    )
    add_table(model, dictionary, "ItemReplacement", replacements)
    add_table(model, dictionary, "SubTaskType", subtask_types)
    add_table(model, dictionary, "TaskBreakDown", breakdown)
    add_table(model, dictionary, "SubTaskResource", requirements)
    mapping = {
        "source_project_id": canonical["project_identity"]["project_id"],
        "plan_source_inputs_sha256": plan["source_inputs_sha256"],
        "policy": "accepted Plan serial preflight/PM and pooled SPECIAL resources; replacement work split 50/50 into SIMLOX REMOVE/REPLACE; typed requirements remain notes; FRT converted to per-million OPHOURS",
        "counts": {
            "subtask_types": len(subtask_types),
            "task_breakdown": len(breakdown),
            "subtask_resources": len(requirements),
            "declared_resource_types": sum(len(labels - {""}) for labels in types.values()),
            "item_repair": len(repair_rows),
            "item_replacement": len(replacements),
            "system_repair": 1,
            "failure_rate_multiplier": 1_000_000,
        },
        "declared_resource_names": {kind: sorted(labels - {""}) for kind, labels in types.items()},
        "steps": mapping_steps,
    }
    return model, mapping


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-json", required=True, type=Path)
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--dictionary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    args = parser.parse_args()
    for name, path in (
        ("base_json", args.base_json),
        ("canonical", args.canonical),
        ("plan", args.plan),
        ("dictionary", args.dictionary),
    ):
        actual = sha256(path)
        if actual != PINNED_INPUT_SHA256[name]:
            raise ValueError(f"{name} SHA-256 changed: {actual}")
    model, mapping = build(
        read_json(args.base_json),
        read_json(args.canonical),
        read_json(args.plan),
        args.dictionary,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.mapping.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mapping["inputs"] = {
        "base_json_sha256": sha256(args.base_json),
        "canonical_file_sha256": sha256(args.canonical),
        "plan_file_sha256": sha256(args.plan),
        "dictionary_sha256": sha256(args.dictionary),
        "output_json_sha256": sha256(args.output),
    }
    args.mapping.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": mapping["counts"], "output_json_sha256": mapping["inputs"]["output_json_sha256"]}))


if __name__ == "__main__":
    main()
