"""Build an isolated SIMLOX J35 candidate from AMD128's current Project boundary.

The old F35 native export supplies only the SIMLOX 2017 table schema. Business
values come from the pinned AMD128 ProjectJsonExporter -> SimulationAdapter
output and from its independently compiled Execution Plan. The resulting model
is a structural candidate, not a cross-runtime semantic oracle.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path


EXPECTED_SHA256 = {
    "template": "aec7d1049aced4c2842081c106ad19b7cd3248c2dd168e5bf278bd3920f610f9",
    "project": "aa285af2abcea77d8244f16599284259d4a3ac57288ee0b5afc8a626566744d7",
    "canonical": "30c20086cbf400dd35e132f71498c1d05c256d74a1384355b703ccc713601559",
    "plan": "44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb",
}
PROJECT_ID = "project-j35-8aircraft-43day-availability-20260909"
PERSONNEL_RIDS = {"军械": "P_ARM", "机械": "P_MECH", "特设": "P_SPEC", "航电": "P_AVION"}
EQUIPMENT_RIDS = {"JYC": "E_JYC", "GDC": "E_GDC", "KTC": "E_KTC", "DYC": "E_DYC", "QYC": "E_QYC", "CDC": "E_CDC"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(model: dict, name: str) -> dict:
    matches = [entry for entry in model["model"]["tables"] if entry["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one SIMLOX table {name}, got {len(matches)}")
    return matches[0]


def rows(entry: dict) -> list[dict]:
    columns = [column["name"] for column in entry["columns"]]
    if len(entry["instances"]) != 1:
        raise ValueError(f"unexpected instances in {entry['name']}")
    return [dict(zip(columns, row, strict=True)) for row in entry["instances"][0]["rows"]]


def set_rows(entry: dict, records: list[dict]) -> None:
    columns = [column["name"] for column in entry["columns"]]
    entry["instances"][0]["rows"] = [[record.get(column) for column in columns] for record in records]


def rename_template(value: object) -> object:
    if isinstance(value, str):
        return value.replace("F35", "J35").replace("f35", "j35")
    if isinstance(value, list):
        return [rename_template(item) for item in value]
    if isinstance(value, dict):
        return {key: rename_template(item) for key, item in value.items()}
    return value


def task_id(activity: dict) -> str | None:
    aid = activity["activity_id"]
    if aid == "j35-service-0103":
        return "MISSION_PREP"
    if aid == "preventive-j35-6":
        return "PM_25H"
    if aid == "preventive-j35-50h-24h":
        return "PM_50H"
    if aid == "corrective-j35-generic-lru-replacement":
        return "CM_GENERIC"
    if activity["kind"] == "repair":
        return f"CM_{aid}".upper()
    return None


def build(template: dict, project: dict, canonical: dict, plan: dict) -> tuple[dict, dict]:
    if not (project["project_id"] == canonical["project_identity"]["project_id"] == PROJECT_ID):
        raise ValueError("J35 source project identity changed")
    if plan["source_inputs_sha256"] != "d9aa54e27d152bab775e3653a1025e42457ea9900e454849ec0d65c6c9cc65c5":
        raise ValueError("J35 Plan is not compiled from the pinned canonical input")
    if plan["work_policy"] != "stable-topological-serial":
        raise ValueError("unexpected J35 work policy")
    if len(canonical["aircraft"]["assets"]) != 8 or len(plan["missions"]) != 104:
        raise ValueError("J35 fleet or mission count changed")
    model = rename_template(copy.deepcopy(template))
    model["model"]["database_version"] = template["model"]["database_version"]

    # The SIMLOX table layout is reused, but every business identity and rate
    # is checked against the current J35 canonical input below.
    components = {component["id"].upper(): component for component in canonical["equipment_tree"]["components"]}
    if len(components) != 424 or canonical["equipment_tree"]["root_component_id"].upper() != "J35-AIRCRAFT-ROOT":
        raise ValueError("unexpected J35 component structure")
    root_id = "J35-AIRCRAFT-ROOT"
    children: dict[str, list[str]] = defaultdict(list)
    for cid, component in components.items():
        if component.get("parent_id"):
            children[str(component["parent_id"]).upper()].append(cid)
    totals: dict[str, float] = {}
    visiting: set[str] = set()

    def cumulative_rate(cid: str) -> float:
        if cid in totals:
            return totals[cid]
        if cid in visiting:
            raise ValueError("cycle in J35 component tree")
        visiting.add(cid)
        value = float(components[cid].get("failure_rate") or 0)
        value += sum(int(components[child].get("quantity") or 1) * cumulative_rate(child) for child in children[cid])
        visiting.remove(cid)
        totals[cid] = value
        return value

    cumulative_rate(root_id)
    item_rows = rows(table(model, "Item"))
    if len(item_rows) != 423 or {r["IID"] for r in item_rows} != set(components) - {root_id}:
        raise ValueError("SIMLOX item IDs do not match J35 components")
    for row in item_rows:
        component = components[row["IID"]]
        row["DESCR"] = component["name"]
        row["FRT"] = cumulative_rate(row["IID"]) * 1_000_000
        row["OPID"] = "OPHOURS"
        row["NOTE"] = (
            f"canonical product_id={component['product_id']}; "
            f"own_failure_rate={component.get('failure_rate') or 0}; per-million OPHOURS"
        )
    set_rows(table(model, "Item"), item_rows)
    system = rows(table(model, "System"))
    if len(system) != 1 or system[0]["SID"] != "J35":
        raise ValueError("unexpected system template")
    system[0].update(DESCR="J35 aircraft", FRT=cumulative_rate(root_id) * 1_000_000, OPID="OPHOURS")
    system[0]["NOTE"] = "canonical root subtree rate; per-million OPHOURS"
    set_rows(table(model, "System"), system)

    structure = rows(table(model, "ItemStructure"))
    if len(structure) != 423:
        raise ValueError("unexpected item structure count")
    for row in structure:
        component = components[row["IID"]]
        expected_mother = str(component["parent_id"]).upper()
        row["MID"] = "J35" if expected_mother == root_id else expected_mother
        row["QTYPM"] = int(component["quantity"])
    set_rows(table(model, "ItemStructure"), structure)

    deployment = rows(table(model, "SystemDeployment"))
    deployment[0]["QTYPS"] = canonical["aircraft"]["fleet_count"]
    deployment[0]["NOTE"] = "8 aircraft; tail identities and initial life states are not represented"
    set_rows(table(model, "SystemDeployment"), deployment)
    units = rows(table(model, "Unit"))
    if len(units) != 1 or units[0]["UNID"] != "J35_UNIT":
        raise ValueError("unexpected SIMLOX unit template")
    units[0]["DESCR"] = "Eight canonical J35 assets; individual tail IDs not represented"
    set_rows(table(model, "Unit"), units)
    mission = rows(table(model, "MissionType"))
    basic = canonical["mission_profile"]["basic_missions"][0]
    if len(mission) != 1 or len({spec["duration_minutes"] for spec in plan["missions"]}) != 1:
        raise ValueError("J35 missions cannot use one SIMLOX mission type")
    if basic["cancelMinutes"] != 20 or {spec["cancel_minutes"] for spec in plan["missions"]} != {20}:
        raise ValueError("J35 mission deferment window changed")
    phase_ratios = [phase["phaseRatio"] for phase in basic["missionPhases"]]
    if len(phase_ratios) != 3 or abs(sum(phase_ratios) - 1) > 1e-9:
        raise ValueError("unexpected J35 mission phase ratios")
    mission[0].update(
        MTID=basic["id"], DESCR=basic["name"], NOS=basic["equipmentQuantity"],
        MNOS=basic["minRequiredSorties"], DURN=plan["missions"][0]["duration_minutes"] / 60,
        MSUCPT=basic["successPoint"], TFOUT=phase_ratios[0], TFRET=phase_ratios[2],
        NOPER=basic["advanceNoticeMinutes"] / 60,
        NOTE="Plan mission duration=324min; page basic=234min; phase fractions 0.3/0.4/0.3",
    )
    set_rows(table(model, "MissionType"), mission)
    schedule = rows(table(model, "OperationProfile"))
    starts = [spec["planned_start"] / 60 for spec in plan["missions"]]
    if len(schedule) != len(starts) or sorted(row["STIM"] for row in schedule) != sorted(starts):
        raise ValueError("J35 schedule differs from template")
    for row in schedule:
        row["SPRID"] = basic["id"]
        row["DTIM"] = basic["cancelMinutes"] / 60
    set_rows(table(model, "OperationProfile"), schedule)
    control = rows(table(model, "Control"))
    control[0].update(APID="J35", NREPS=1, RSEED="1", SIMPE=1032, RCEND=1032)
    set_rows(table(model, "Control"), control)
    set_rows(table(model, "ProblemDescription"), [{"PDESC": (
        "AMD128 main J35 43-day Project; ProjectJsonExporter/SimulationAdapter; "
        "structural SIMLOX candidate, not semantic parity"
    )}])

    activity_by_id = {activity["activity_id"]: activity for activity in plan["activities"]}
    canonical_activities = {activity["id"]: activity for activity in canonical["support_activities"]["activities"]}
    jobs = {job["activityCode"]: job for job in project["supportActivityJobs"]}
    inactive_activity_ids = {
        "j35-service-0103-relaunch", "j35-service-0103-postflight", "logistics-34",
    }
    inactive_activities = {activity["activity_id"] for activity in plan["activities"] if not task_id(activity)}
    if inactive_activities != inactive_activity_ids or any(activity_by_id[aid]["steps"] for aid in inactive_activities):
        raise ValueError("new or nonempty J35 activity has no SIMLOX task mapping")
    tasks = rows(table(model, "Tasks"))
    task_for_activity = {aid: task_id(activity) for aid, activity in activity_by_id.items() if task_id(activity)}
    if {r["TID"] for r in tasks} != set(task_for_activity.values()):
        raise ValueError("J35 SIMLOX task IDs differ from Plan activity mapping")
    aid_for_task = {tid: aid for aid, tid in task_for_activity.items()}
    for row in tasks:
        aid = aid_for_task[row["TID"]]
        row["DESCR"] = activity_by_id[aid]["name"]
        row["NOTE"] = f"canonical activity={aid}; Plan serial steps; replacement split is approximate"
    set_rows(table(model, "Tasks"), tasks)
    prep_steps = activity_by_id["j35-service-0103"]["steps"]
    if len(prep_steps) != 14 or sum(step["duration_minutes"] for step in prep_steps) != 142:
        raise ValueError("unexpected J35 preparation steps")
    prep = rows(table(model, "MissionPreparation"))
    prep[0].update(MTID=basic["id"], SID="J35", STID="BASE", DURN=142 / 60)
    prep[0]["NOTE"] = "14 Plan serial subtasks total 142min; page plan duration 148min; canonical aggregate 120min"
    set_rows(table(model, "MissionPreparation"), prep)

    type_rows = rows(table(model, "SubTaskType"))
    if len(type_rows) != 14:
        raise ValueError("unexpected preflight type count")
    for index, row in enumerate(type_rows):
        step = prep_steps[index]
        raw = jobs[step["code"]]
        row.update(SUTID=f"J35P{index + 1:02d}", DESCR=raw["workName"], NOTE=f"canonical code={step['code']}")
    set_rows(table(model, "SubTaskType"), type_rows)

    # Match the Plan-selected repair task for each component. SIMLOX requires
    # REMOVE/REPLACE subtasks, so a one-step Plan repair remains a 50/50 split.
    plan_components = {component["component_id"].upper(): component for component in plan["components"]}
    repair_rows = rows(table(model, "ItemRepair"))
    replacement_rows = rows(table(model, "ItemReplacement"))
    if len(repair_rows) != 423 or len(replacement_rows) != 423:
        raise ValueError("unexpected item repair/replacement count")
    for row in repair_rows:
        component = plan_components[row["IID"]]
        aid = plan["activities"][component["repair_activity_index"]]["activity_id"]
        row.update(DIRPT=0, DIRPTID=None)
        row["NOTE"] = f"instant refurbishment placeholder; canonical activity={aid}"
    set_rows(table(model, "ItemRepair"), repair_rows)
    replacement_by_item = {row["IID"]: row for row in replacement_rows}
    for link in structure:
        row = replacement_by_item[link["IID"]]
        component = plan_components[link["IID"]]
        activity = plan["activities"][component["repair_activity_index"]]
        row.update(MID=link["MID"], STID="BASE", SURPT=activity["steps"][0]["duration_minutes"] / 60,
                   SURPTID=task_for_activity[activity["activity_id"]])
        row["NOTE"] = f"canonical activity={activity['activity_id']}; REMOVE/REPLACE 50/50 approximation"
    set_rows(table(model, "ItemReplacement"), replacement_rows)
    system_repair = rows(table(model, "SystemRepair"))
    system_repair[0].update(SID="J35", STID="BASE", SURPT=3, SURPTID="CM_GENERIC")
    set_rows(table(model, "SystemRepair"), system_repair)
    for name in ("MaterielPM", "PMLocation"):
        entries = rows(table(model, name))
        for row in entries:
            row["MID" if name == "MaterielPM" else "ID"] = "J35"
        set_rows(table(model, name), entries)

    breakdown = []
    requirements = []
    step_mapping = []
    page_resources = [r for r in project["supportResources"] if r["type"] in {"personnel", "equipment"}]
    if len(page_resources) != 10:
        raise ValueError("expected 4 professional and 6 device types in J35 Project")
    resource_rows = rows(table(model, "Resource"))
    allocations = rows(table(model, "ResourceAllocation"))
    if {r["RID"] for r in resource_rows} != {"PERSONNEL", "DEVICE"}:
        raise ValueError("unexpected pooled SIMLOX resources")
    typed_lookup: dict[tuple[str, str], str] = {}
    for source in page_resources:
        if source["organizationNodeId"] != "support-org-1783479792728":
            raise ValueError("typed resource has unexpected source station")
        rid = (PERSONNEL_RIDS[source["model"]] if source["type"] == "personnel"
               else EQUIPMENT_RIDS[source["model"]])
        label = source["model"] if source["type"] == "personnel" else source["name"]
        key = (source["type"], label)
        if key in typed_lookup:
            raise ValueError(f"duplicate typed source resource {key}")
        typed_lookup[key] = rid
        resource_rows.append({"RID": rid, "DESCR": label, "TYPE": "SPECIAL",
                              "NOTE": f"Project supportResource={source['id']}"})
        allocations.append({"POINT": "J35", "RID": rid, "STID": "BASE",
                            "RQTY": int(source["quantity"]), "NOTE": "source category capacity"})
    set_rows(table(model, "Resource"), resource_rows)
    set_rows(table(model, "ResourceAllocation"), allocations)
    omitted_page_requirements = []
    for activity in plan["activities"]:
        aid = activity["activity_id"]
        tid = task_for_activity.get(aid)
        if not tid:
            continue
        for step in activity["steps"]:
            raw = jobs[step["code"]]
            if tid == "MISSION_PREP":
                seq = step["index"] + 1
                parts = [(seq, f"J35P{seq:02d}", step["duration_minutes"])]
            elif activity["kind"] == "repair":
                parts = [(1, "<REMOVE>", step["duration_minutes"] / 2),
                         (2, "<REPLACE>", step["duration_minutes"] / 2)]
            else:
                parts = [(step["index"] + 1, "<INSPECT>", step["duration_minutes"])]
            declared = {"personnel": [], "equipment": []}
            for kind, field, name_field in (("personnel", "personnel", "professional"),
                                            ("equipment", "equipment", "name")):
                for source in raw.get(field) or []:
                    label = str(source.get(name_field) or source.get("model") or "").strip()
                    quantity = int(source.get("quantity", 1))
                    if not label or quantity <= 0:
                        raise ValueError(f"invalid J35 resource demand {aid}/{step['code']}")
                    declared[kind].append({"label": label, "quantity": quantity})
            effective_typed = {kind: [entry for entry in declared[kind]
                                      if (kind, entry["label"]) in typed_lookup]
                               for kind in ("personnel", "equipment")}
            note = " | ".join(f"{kind}=" + (
                ",".join(f"{entry['label']}x{entry['quantity']}" for entry in effective_typed[kind]) or "none")
                for kind in ("personnel", "equipment"))
            for seq, sutid, minutes in parts:
                breakdown.append({"TID": tid, "SEQ": seq, "SUTID": sutid, "DURN": minutes / 60,
                                  "NOTE": f"canonical code={step['code']} | {note}"
                                  + (" | replacement duration split 50/50" if activity["kind"] == "repair" else "")})
                for rid, quantity in (("PERSONNEL", step["personnel"]), ("DEVICE", step["equipment"])):
                    requirements.append({"TID": tid, "SEQ": seq, "RID": rid, "QTY": quantity,
                                         "RPROB": 1, "NOTE": "Plan pooled demand; typed source overlay is additional"})
                for kind in ("personnel", "equipment"):
                    for entry in declared[kind]:
                        key = (kind, entry["label"])
                        rid = typed_lookup.get(key)
                        if rid is None:
                            omitted = {"activity_id": aid, "code": step["code"],
                                       "kind": kind, **entry,
                                       "reason": "No matching source supportResource; excluded from SIMLOX constraints"}
                            if omitted["code"] != "J35-USE-003" or omitted["kind"] != "equipment" or omitted["label"] != "充氧车":
                                raise ValueError(f"unmapped J35 resource demand: {omitted}")
                            omitted_page_requirements.append(omitted)
                            continue
                        requirements.append({"TID": tid, "SEQ": seq, "RID": rid,
                                             "QTY": entry["quantity"], "RPROB": 1,
                                             "NOTE": f"Project declared {kind}={entry['label']}"})
                step_mapping.append({"activity_id": aid, "task_id": tid, "seq": seq,
                                     "subtask_type": sutid, "code": step["code"],
                                     "duration_minutes": minutes, "page_declared": declared,
                                     "simlox_typed": effective_typed,
                                     "plan_pooled": {"personnel": step["personnel"], "equipment": step["equipment"]},
                                     "predecessors": step["predecessors"]})
    if len(breakdown) != 30 or len(omitted_page_requirements) != 1:
        raise ValueError("J35 jobs or omitted oxygen truck requirement changed")
    set_rows(table(model, "TaskBreakDown"), breakdown)
    set_rows(table(model, "SubTaskResource"), requirements)

    nodes = {node["id"]: node for node in canonical["support_network"]["nodes"]}
    source_to_station = {"support-org-1783479792728": "BASE", "support-org-dadui": "DEPOT"}
    product_items: dict[str, list[str]] = defaultdict(list)
    for cid, component in components.items():
        if cid != root_id:
            product_items[component["product_id"]].append(cid)
    stock_rows = []
    stock_mapping = []
    for node_id, station in source_to_station.items():
        node = nodes[node_id]
        if len(node["inventory"]) != 403:
            raise ValueError("unexpected J35 source inventory coverage")
        for product_id, quantity in sorted(node["inventory"].items()):
            matches = product_items[product_id]
            if len(matches) != 1:
                raise ValueError(f"cannot uniquely map stock product {product_id}")
            item_id = matches[0]
            stock_rows.append({"POINT": "J35", "IID": item_id, "STID": station,
                               "STSIZ": int(quantity), "NOTE": f"canonical product_id={product_id}"})
            stock_mapping.append({"source_node_id": node_id, "station_id": station,
                                  "product_id": product_id, "item_id": item_id, "quantity": int(quantity)})
    set_rows(table(model, "StockAllocation"), stock_rows)
    route = canonical["support_network"]["organization_graph"]["transport_policies"]
    if len(route) != 1 or route[0]["transport_time_hours"] != 2 or route[0]["capacity"] != 1:
        raise ValueError("unexpected J35 vertical transport policy")
    set_rows(table(model, "StationStructure"), [{"STID": "BASE", "MSTID": "DEPOT",
        "TFRMS": 2, "TTOMS": 2, "DFRAC": 1, "OPOL": "FAST",
        "NOTE": "source depot-to-base 2h; reverse 2h assumed for SIMLOX; source batch cap 1 not represented"}])

    component_mapping = [{"source_component_id": component["id"],
        "product_id": component["product_id"], "simlox_id": "J35" if cid == root_id else cid,
        "parent_simlox_id": None if cid == root_id else ("J35" if str(component["parent_id"]).upper() == root_id
                                                           else str(component["parent_id"]).upper()),
        "quantity": component["quantity"], "own_failure_rate_per_hour": component.get("failure_rate") or 0,
        "simlox_frT_per_million_hours": cumulative_rate(cid) * 1_000_000}
        for cid, component in components.items()]
    mapping = {
        "project_id": PROJECT_ID,
        "source": {
            "host": "AMD128", "repository": "/home/g/Models/spare_mvp",
            "repository_revision": "0e709bdcc2d692d9cfed49b9037c76ef71aefe33",
            "project_payload_raw_sha256": "bce310581ae8b2fdf1fcd28f76065a673e63746f9b39be5152393d5c67287a7e",
            "project_export_sha256": EXPECTED_SHA256["project"],
            "canonical_export_sha256": EXPECTED_SHA256["canonical"],
            "canonical_input_fingerprint": plan["source_inputs_sha256"],
            "execution_plan_sha256": EXPECTED_SHA256["plan"],
            "simlox_template_sha256": EXPECTED_SHA256["template"],
            "project_version": project["project_version"],
            "project_schema_version": project["schema_version"],
            "canonical_schema_version": canonical["schema_version"],
            "plan_version": plan["plan_version"],
            "rng_profile": plan["rng_profile"],
            "semantic_profile": plan["semantic_profile"],
        },
        "policy": "AMD128 J35 Project -> canonical -> Plan; SIMLOX structural candidate with typed resource overlay",
        "counts": {"aircraft": 8, "missions": len(plan["missions"]), "components": len(components),
            "products": len(project["products"]), "support_activities": len(canonical_activities),
            "catalog_jobs": len(project["supportActivityJobs"]), "active_steps": len(step_mapping),
            "resource_types": len(resource_rows), "resource_allocations": len(allocations),
            "subtask_resources": len(requirements), "stock_rows": len(stock_rows),
            "positive_stock_rows": sum(row["STSIZ"] > 0 for row in stock_rows)},
        "resource_types": [{"source_id": row["id"], "kind": row["type"], "model": row["model"],
                            "name": row["name"], "simlox_rid": (PERSONNEL_RIDS[row["model"]] if row["type"] == "personnel"
                                                               else EQUIPMENT_RIDS[row["model"]]),
                            "capacity": row["quantity"]} for row in page_resources],
        "omitted_page_requirements": omitted_page_requirements,
        "inactive_catalog_jobs": [
            {"code": job["activityCode"], "name": job["workName"]}
            for job in project["supportActivityJobs"]
            if job["activityCode"] not in {step["code"] for step in step_mapping}
        ],
        "inactive_activities": [
            {"activity_id": aid, "reason": "Plan has zero executable steps"}
            for aid in sorted(inactive_activities)
        ],
        "components": component_mapping,
        "stock": stock_mapping,
        "steps": step_mapping,
        "semantic_gaps": [
            "SIMLOX seed 0 rejected; candidate uses seed 1 with different RNG stream",
            "20-minute SIMLOX mission deferment is mapped, but daily-v1 relaunch/postflight/dispatch/cancellation rules are not yet shown equivalent; same preflight runs before each SIMLOX mission",
            "page-declared oxygen truck on J35-USE-003 is excluded because it has no source supportResource; Plan pooled DEVICE demand remains",
            "typed requirements are additional to Plan's pooled 1+1 demands; no semantic parity claim",
            "PM 7-calendar-day OR 25-flight-hour trigger and per-tail initial lives not represented",
            "repair REMOVE/REPLACE 50/50 and instant refurbishment are approximations",
            "SIMLOX transport reverse time is assumed and batch cap 1 is not represented",
            "output definitions and random request tape have no accepted mapping",
        ],
    }
    return model, mapping


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    args = parser.parse_args()
    for key in EXPECTED_SHA256:
        actual = sha256(getattr(args, key))
        if actual != EXPECTED_SHA256[key]:
            raise ValueError(f"{key} SHA-256 mismatch: {actual}")
    model, mapping = build(load(args.template), load(args.project), load(args.canonical), load(args.plan))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.mapping.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mapping["inputs"] = {key: EXPECTED_SHA256[key] for key in EXPECTED_SHA256}
    mapping["inputs"]["output_json_sha256"] = sha256(args.output)
    args.mapping.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": mapping["counts"], "output_json_sha256": sha256(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
