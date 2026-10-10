"""Deterministic design-review views of validated persisted aircraft IR.

The projection is intentionally offline and descriptive.  It does not lower a
Business artifact, reconstruct an earlier source model, or enumerate runtime
paths.  Plan locations are added by the bundle exporter only when lineage has
been independently verified.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from sim_engine_compiler.identity.common import content_digest, diagnostic, json_value
from sim_engine_compiler.ir.layers import (
    BUSINESS_VERSION,
    CORE_VERSION,
    REFERENCES,
    BusinessIR,
    CoreIR,
)

VIEW_SCHEMA = "aircraft-design-review-views/v1"
_VIEW_NAMES = (
    "entities", "relations", "processes", "states", "rules", "resources", "parameters",
)


def _empty() -> dict[str, Any]:
    return {
        "views": {name: [] for name in _VIEW_NAMES},
        "diagnostics": [],
        "coverage": {
            "schema_version": VIEW_SCHEMA,
            "level": "none",
            "operation_coverage": [],
            "limitations": [],
        },
    }


def _provenance(artifact_path: str, source_path: str | None) -> dict[str, Any]:
    return {
        "artifact_field_path": artifact_path,
        "source_path": source_path,
        # Persistence proves neither user authorship nor a default/normalizing
        # transform.  Those origins require evidence outside these artifacts.
        "value_origin": "unknown",
    }


def _qualified(layer: str, kind: str, element_id: str) -> dict[str, str]:
    return {"layer": layer, "kind": kind, "element_id": element_id}


def _stable_id(category: str, *parts: Any) -> str:
    return f"{category}/{content_digest([category, *parts])[:24]}"


def _logical_token(value: Any) -> str:
    if isinstance(value, Mapping):
        for name in (
            "business_id", "id", "activityCode", "code", "tail_number", "missionId",
            "node_id", "component_id", "route_id",
        ):
            if isinstance(value.get(name), str) and value[name]:
                return f"{name}={value[name]}"
    return f"content={content_digest(value)[:16]}"


def _step_identity(value: Mapping[str, Any]) -> str:
    for name in ("activityCode", "code", "id"):
        if isinstance(value.get(name), str) and value[name]:
            return value[name]
    return _logical_token(value)


def _unit(name: str, value: Any) -> tuple[str | None, str, str | None]:
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if type(value) not in (int, float):
        return None, "not-applicable", None
    units = {
        "1/hour": {"failure_rate_per_hour"},
        "minute": {
            "advance_notice_minutes", "cancel_minutes", "duration_minutes", "planned_start",
            "preparation_start", "repair_duration_minutes", "sample_every_minutes",
            "task_duration_minutes", "tick_minutes", "transport_minutes",
        },
        "hour": {
            "flight_hours", "initial_flight_hours", "interval_hours", "limit_hours",
            "start_hour",
        },
        "day": {"calendar_days", "initial_calendar_days"},
        "cycle": {
            "initial_cycles", "initial_landing_cycles", "landing_cycles",
            "takeoff_landing_cycles", "takeoff_landing_interval",
        },
        "count": {
            "configured_slots", "daily_repeat_count", "equipment", "equipment_capacity",
            "equipment_quantity",
            "failure_threshold", "fleet_count", "initial_ready", "max_state_frames_single",
            "min_required_aircraft", "min_required_sorties",
            "personnel", "personnel_capacity", "quantity", "requested_steps", "sample_count",
        },
        "dimensionless": {
            "phase_ratio", "replacement_ratio", "success_point",
        },
    }
    for unit, names in units.items():
        if name in names:
            return unit, "known", "aircraft-design-review-units/v1"
    return None, "unknown", None


def _parameters(owner: str, value: Any, artifact_path: str,
                source_path: str | None, logical_path: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for name in sorted(value):
            logical = f"{logical_path}.{name}" if logical_path else name
            result.extend(_parameters(
                owner, value[name], f"{artifact_path}.{name}", source_path, logical,
            ))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(_parameters(
                owner, item, f"{artifact_path}[{index}]", source_path,
                f"{logical_path}[{_logical_token(item)}]",
            ))
    elif value is None or type(value) in (str, bool, int, float):
        name = logical_path.rsplit(".", 1)[-1]
        unit, unit_status, unit_source = _unit(name, value)
        result.append({
            "view_id": _stable_id("parameter", owner, logical_path),
            "owner_view_id": owner,
            "name": name,
            "logical_path": logical_path,
            "value": value,
            "unit": unit,
            "unit_status": unit_status,
            "unit_source": unit_source,
            "provenance": _provenance(artifact_path, source_path),
        })
    return result


def _finish(result: dict[str, Any]) -> dict[str, Any]:
    for view_name, values in result["views"].items():
        counts = Counter(item["view_id"] for item in values)
        duplicates = sorted(view_id for view_id, count in counts.items() if count > 1)
        for view_id in duplicates:
            result["diagnostics"].append(diagnostic(
                "review_duplicate_view_identity",
                "stable review identity is not unique; ambiguous nodes were omitted",
                stage="review-projection", path=f"views.{view_name}",
                element_id=view_id,
            ))
        if duplicates:
            values[:] = [item for item in values if counts[item["view_id"]] == 1]
        values.sort(key=lambda item: item["view_id"])
    result["diagnostics"].sort(
        key=lambda item: (item["severity"], item["code"], item.get("path") or "")
    )
    return result


def _identity_maps(report: Mapping[str, Any]) -> tuple[dict[tuple[str, str], dict[str, Any]],
                                                       dict[str, dict[str, Any]]]:
    by_kind: dict[tuple[str, str], dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for element in report.get("elements", []):
        element_id, kind = element.get("element_id"), element.get("kind")
        if isinstance(element_id, str) and isinstance(kind, str):
            by_kind[(kind, element_id)] = element
            by_id[element_id] = element
    return by_kind, by_id


def _business_views(raw: dict[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    result = _empty()
    business = BusinessIR.from_dict(raw)
    by_kind, _ = _identity_maps(report)
    symbols: dict[str, list[str]] = {}
    owners: dict[tuple[str, str], str] = {}
    invalid_process_owners: set[str] = set()

    for section in sorted(business.payload["sections"]):
        section_value = business.payload["sections"][section]
        section_owner = f"business/section/{section}"
        result["views"]["parameters"].extend(_parameters(
            section_owner, section_value["properties"],
            f"payload.sections.{section}.properties", None,
        ))
        for collection in sorted(section_value["collections"]):
            kind = f"{section}.{collection}"
            for index, entity in enumerate(section_value["collections"][collection]):
                element_id = entity["business_id"]
                path = f"payload.sections.{section}.collections.{collection}[{index}]"
                if (kind, element_id) not in by_kind:
                    result["diagnostics"].append(diagnostic(
                        "review_identity_element_missing",
                        "identity report has no matching Business element",
                        stage="review-projection", path=path, element_id=element_id,
                    ))
                    continue
                owner = f"business/{kind}/{element_id}"
                owners[(kind, element_id)] = owner
                definition = entity["definition"]
                source_path = entity["source_path"]
                result["views"]["entities"].append({
                    "view_id": owner,
                    "qualified_identity": _qualified("business", kind, element_id),
                    "entity_kind": kind,
                    "label": definition.get("name") or definition.get("tail_number") or element_id,
                    "definition": copy.deepcopy(definition),
                    "provenance": _provenance(f"{path}.definition", source_path),
                })
                result["views"]["parameters"].extend(_parameters(
                    owner, definition, f"{path}.definition", source_path,
                ))
                for symbol in (element_id, definition.get("id"), definition.get("tail_number")):
                    if isinstance(symbol, str) and symbol:
                        symbols.setdefault(symbol, []).append(owner)

                if kind == "aircraft.assets" and isinstance(definition.get("initial_state"), str):
                    result["views"]["states"].append({
                        "view_id": _stable_id("state", owner, "initial_state"),
                        "owner_view_id": owner,
                        "state_kind": "initial-aircraft-state",
                        "value": definition["initial_state"],
                        "provenance": _provenance(
                            f"{path}.definition.initial_state", source_path,
                        ),
                    })
                if kind == "mission_profile.mission_phases":
                    result["views"]["states"].append({
                        "view_id": _stable_id("state", owner, "phase_state"),
                        "owner_view_id": owner,
                        "state_kind": "mission-phase-state",
                        "value": definition.get("state"),
                        "provenance": _provenance(f"{path}.definition.state", source_path),
                    })
                    result["views"]["rules"].append({
                        "view_id": _stable_id("rule", owner, "transition"),
                        "owner_view_id": owner,
                        "rule_kind": "mission-phase-transition",
                        "condition": definition.get("transitionCondition"),
                        "effect": {"state": definition.get("state")},
                        "provenance": _provenance(f"{path}.definition", source_path),
                    })
                if kind in {"support_activities.activities", "mission_profile.composite_tasks"}:
                    steps_name = "jobs" if "jobs" in definition else "taskItems"
                    steps = []
                    step_counts = Counter(
                        _step_identity(step) for step in definition.get(steps_name, [])
                    )
                    duplicate_steps = sorted(
                        step_id for step_id, count in step_counts.items() if count > 1
                    )
                    if duplicate_steps:
                        invalid_process_owners.add(owner)
                        for step_id in duplicate_steps:
                            result["diagnostics"].append(diagnostic(
                                "review_process_step_identity_ambiguous",
                                "process contains duplicate stable step identities; process was omitted",
                                stage="review-projection",
                                path=f"{path}.definition.{steps_name}",
                                element_id=step_id,
                            ))
                        continue
                    for step_index, step in enumerate(definition.get(steps_name, [])):
                        step_id = _step_identity(step)
                        step_path = f"{path}.definition.{steps_name}[{step_index}]"
                        predecessors = copy.deepcopy(step.get("predecessors", []))
                        steps.append({
                            "step_id": step_id,
                            "definition": copy.deepcopy(step),
                            "predecessors": predecessors,
                            "artifact_field_path": step_path,
                        })
                        for predecessor in predecessors:
                            count = step_counts[predecessor]
                            resolution = (
                                "persisted-process-local" if count == 1
                                else "ambiguous" if count > 1 else "unresolved"
                            )
                            result["views"]["relations"].append({
                                "view_id": _stable_id(
                                    "relation", owner, step_id, "predecessor", predecessor,
                                ),
                                "relation_kind": "predecessor",
                                "source": {"owner_view_id": owner, "step_id": step_id},
                                "target": {"owner_view_id": owner, "step_id": predecessor},
                                "resolution": resolution,
                                "provenance": _provenance(step_path, source_path),
                            })
                            if count != 1:
                                result["diagnostics"].append(diagnostic(
                                    "review_process_predecessor_ambiguous" if count else
                                    "review_process_predecessor_unresolved",
                                    "process predecessor does not identify exactly one local step",
                                    stage="review-projection", path=f"{step_path}.predecessors",
                                    element_id=predecessor, severity="warning",
                                ))
                    result["views"]["processes"].append({
                        "view_id": _stable_id("process", owner),
                        "owner_view_id": owner,
                        "process_kind": kind,
                        "steps": steps,
                        "provenance": _provenance(f"{path}.definition", source_path),
                    })
                if kind == "support_network.nodes":
                    result["views"]["resources"].append({
                        "view_id": _stable_id("resource", owner),
                        "owner_view_id": owner,
                        "resource_kind": "capacity-and-inventory-node",
                        "capacities": {
                            "personnel": definition.get("personnel_capacity"),
                            "equipment": definition.get("equipment_capacity"),
                        },
                        "inventory": copy.deepcopy(definition.get("inventory", {})),
                        "provenance": _provenance(f"{path}.definition", source_path),
                    })
                if kind == "support_activities.activities":
                    if owner in invalid_process_owners:
                        continue
                    for step_index, step in enumerate(definition.get("jobs", [])):
                        result["views"]["resources"].append({
                            "view_id": _stable_id("resource", owner, _step_identity(step)),
                            "owner_view_id": owner,
                            "resource_kind": "work-step-requirement",
                            "step_id": _step_identity(step),
                            "requirements": {
                                "personnel": copy.deepcopy(step.get("personnel", [])),
                                "equipment": copy.deepcopy(step.get("equipment", [])),
                                "spares": copy.deepcopy(step.get("spare", [])),
                            },
                            "provenance": _provenance(
                                f"{path}.definition.jobs[{step_index}]", source_path,
                            ),
                        })

    reference_fields = {
        "basicMissionId", "composite_task_id", "parent_id", "resource_id",
        "equipment_id", "activity_id", "supportActivityId", "repairActivityId",
        "source_node_id", "destination_node_id",
    }

    def add_relations(owner: str, value: Any, path: str, logical_path: str,
                      source_path: str) -> None:
        if isinstance(value, Mapping):
            for name in sorted(value):
                child = value[name]
                child_path = f"{path}.{name}"
                child_logical = f"{logical_path}.{name}" if logical_path else name
                if name in reference_fields and isinstance(child, str) and child:
                    matches = sorted(set(symbols.get(child, [])))
                    result["views"]["relations"].append({
                        "view_id": _stable_id("relation", owner, child_logical, child),
                        "relation_kind": name,
                        "source": {"owner_view_id": owner},
                        "target": {
                            "symbol": child,
                            "owner_view_id": matches[0] if len(matches) == 1 else None,
                        },
                        "resolution": "unique-business-symbol" if len(matches) == 1 else "unresolved",
                        "provenance": _provenance(child_path, source_path),
                    })
                add_relations(owner, child, child_path, child_logical, source_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                add_relations(
                    owner, child, f"{path}[{index}]",
                    f"{logical_path}[{_logical_token(child)}]", source_path,
                )

    for section, section_value in business.payload["sections"].items():
        for collection, entities in section_value["collections"].items():
            kind = f"{section}.{collection}"
            for index, entity in enumerate(entities):
                owner = owners.get((kind, entity["business_id"]))
                if owner:
                    add_relations(
                        owner, entity["definition"],
                        f"payload.sections.{section}.collections.{collection}[{index}].definition",
                        "definition",
                        entity["source_path"],
                    )

    stop = business.payload["sections"].get("stop_policy", {}).get("properties", {})
    for index, condition in enumerate(stop.get("conditions", [])):
        result["views"]["rules"].append({
            "view_id": _stable_id("rule", "business/section/stop_policy", _logical_token(condition)),
            "owner_view_id": "business/section/stop_policy",
            "rule_kind": "stop-condition",
            "condition": copy.deepcopy(condition),
            "effect": {"termination": True},
            "evaluation": {"mode": stop.get("mode"), "defaulted": stop.get("defaulted")},
            "provenance": _provenance(
                f"payload.sections.stop_policy.properties.conditions[{index}]", None,
            ),
        })
    result["coverage"].update({
        "level": "partial",
        "limitations": [
            "semantic relations are a curated aircraft subset",
            "parameter values are complete scalars but semantic rule interpretation is partial",
            "no Business-to-Core or Core-to-Plan association is claimed",
            "field presence does not establish explicit user authorship",
        ],
    })
    return _finish(result)


def _core_views(raw: dict[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    result = _empty()
    core = CoreIR.from_dict(raw)
    _, by_id = _identity_maps(report)
    known_ids = {name: {row["id"] for row in rows} for name, rows in core.payload["tables"].items()}

    for table in sorted(core.payload["tables"]):
        for row_index, row in enumerate(core.payload["tables"][table]):
            qualified_id = f"{table}/{row['id']}"
            path = f"payload.tables.{table}[{row_index}]"
            if qualified_id not in by_id:
                result["diagnostics"].append(diagnostic(
                    "review_identity_element_missing", "identity report has no matching Core element",
                    stage="review-projection", path=path, element_id=qualified_id,
                ))
                continue
            owner = f"core/{qualified_id}"
            source_path = row["source_path"]
            result["views"]["entities"].append({
                "view_id": owner,
                "qualified_identity": _qualified("core", table, qualified_id),
                "entity_kind": table,
                "label": row["attributes"].get("name") or row["id"],
                "attributes": copy.deepcopy(row["attributes"]),
                "provenance": _provenance(path, source_path),
            })
            result["views"]["parameters"].extend(_parameters(
                owner, row["attributes"], f"{path}.attributes", source_path,
            ))
            if table == "aircraft":
                result["views"]["states"].append({
                    "view_id": _stable_id("state", owner, "initial_state"),
                    "owner_view_id": owner,
                    "state_kind": "initial-aircraft-state",
                    "value": row["attributes"]["initial_state"],
                    "provenance": _provenance(f"{path}.attributes.initial_state", source_path),
                })
            if table == "resource_nodes":
                result["views"]["resources"].append({
                    "view_id": _stable_id("resource", owner),
                    "owner_view_id": owner,
                    "resource_kind": "capacity-and-inventory-node",
                    "capacities": {
                        "personnel": row["attributes"]["personnel_capacity"],
                        "equipment": row["attributes"]["equipment_capacity"],
                    },
                    "inventory": copy.deepcopy(row["attributes"]["inventory"]),
                    "provenance": _provenance(f"{path}.attributes", source_path),
                })
            for field, (target_table, _optional) in sorted(REFERENCES.get(table, {}).items()):
                targets = row["references"][field]
                targets = targets if field == "aircraft_indexes" else [targets]
                for target in targets:
                    if target is None:
                        continue
                    target_id = f"{target_table}/{target}"
                    result["views"]["relations"].append({
                        "view_id": _stable_id("relation", owner, field, target_id),
                        "relation_kind": field,
                        "source": {"owner_view_id": owner},
                        "target": {"owner_view_id": f"core/{target_id}", "qualified_id": target_id},
                        "resolution": (
                            "validated-core-symbol" if target in known_ids[target_table] else "unresolved"
                        ),
                        "provenance": _provenance(f"{path}.references.{field}", source_path),
                    })
            if table == "activities":
                steps = []
                for step_index, step in enumerate(row["steps"]):
                    step_id = f"activities/{row['id']}/steps/{step['id']}"
                    step_owner = f"core/{step_id}"
                    step_path = f"{path}.steps[{step_index}]"
                    steps.append({
                        "step_id": step_id,
                        "qualified_identity": _qualified("core", "activity_step", step_id),
                        "attributes": copy.deepcopy(step["attributes"]),
                        "predecessors": copy.deepcopy(step["predecessors"]),
                        "dependencies": copy.deepcopy(step["dependencies"]),
                        "artifact_field_path": step_path,
                    })
                    result["views"]["parameters"].extend(_parameters(
                        step_owner, step["attributes"], f"{step_path}.attributes", source_path,
                    ))
                    result["views"]["resources"].append({
                        "view_id": _stable_id("resource", step_owner),
                        "owner_view_id": step_owner,
                        "resource_kind": "work-step-requirement",
                        "requirements": {
                            "personnel": step["attributes"]["personnel"],
                            "equipment": step["attributes"]["equipment"],
                            "spares": copy.deepcopy(step["attributes"]["spares"]),
                        },
                        "dependencies": copy.deepcopy(step["dependencies"]),
                        "provenance": _provenance(step_path, source_path),
                    })
                    for predecessor in step["predecessors"]:
                        target = f"activities/{row['id']}/steps/{predecessor}"
                        result["views"]["relations"].append({
                            "view_id": _stable_id("relation", step_id, "predecessor", target),
                            "relation_kind": "predecessor",
                            "source": {"owner_view_id": step_owner},
                            "target": {"owner_view_id": f"core/{target}"},
                            "resolution": "validated-core-symbol",
                            "provenance": _provenance(f"{step_path}.predecessors", source_path),
                        })
                result["views"]["processes"].append({
                    "view_id": _stable_id("process", owner),
                    "owner_view_id": owner,
                    "process_kind": "support-activity",
                    "steps": steps,
                    "provenance": _provenance(path, source_path),
                })

    result["views"]["parameters"].extend(_parameters(
        "core/contract", core.payload["contract"], "payload.contract", None,
    ))
    contract = core.payload["contract"]
    result["views"]["rules"].append({
        "view_id": "core/contract/execution",
        "qualified_identity": _qualified("core", "execution_contract", "execution"),
        "owner_view_id": "core/contract",
        "rule_kind": "execution-contract",
        "condition": {
            "semantic_profile": contract["semantic_profile"],
            "work_policy": contract["work_policy"],
            "rng_profile": contract["rng_profile"],
            "phases": copy.deepcopy(contract["phases"]),
        },
        "effect": {
            "duration_minutes": contract["duration_minutes"],
            "natural_completion_enabled": contract["natural_completion_enabled"],
        },
        "provenance": _provenance("payload.contract", None),
    })
    operation_coverage = []
    for index, operation in enumerate(core.payload["operations"]):
        operation_id = operation["operation"]
        result["views"]["rules"].append({
            "view_id": f"core/operation/{operation_id}",
            "qualified_identity": _qualified("core", "compiler_operation", operation_id),
            "owner_view_id": "core/contract",
            "rule_kind": "compatibility-phase-operation",
            "operation": operation_id,
            "phase": operation["phase"],
            "condition": {
                "time": operation["time"],
                "reads": copy.deepcopy(operation["reads"]),
                "random": operation["random"],
            },
            "effect": {"writes": copy.deepcopy(operation["writes"])},
            "backends": copy.deepcopy(operation["backends"]),
            "precision": operation["effect_precision"],
            "coverage": "partial",
            "provenance": _provenance(f"payload.operations[{index}]", None),
        })
        operation_coverage.append({
            "operation": operation_id,
            "status": "partial",
            "precision": operation["effect_precision"],
            "limitation": "compatibility phase operation is coarser than a domain-rule mapping",
        })
    result["diagnostics"].append(diagnostic(
        "coarse_operation_mapping",
        "Core operations remain named compatibility phases and are not expanded into runtime paths",
        stage="review-projection", path="payload.operations", severity="warning",
    ))
    result["coverage"].update({
        "level": "partial",
        "operation_coverage": operation_coverage,
        "limitations": [
            "Core compatibility operations are coarser than domain rules",
            "no original Business model is inferred from Core",
            "no Core-to-Plan association is claimed",
            "field presence does not establish explicit user authorship",
        ],
    })
    return _finish(result)


def project_views(raw: Mapping[str, Any], artifact_report: Mapping[str, Any]) -> dict[str, Any]:
    """Project seven stable review views from a validated Business or Core artifact."""
    result = _empty()
    try:
        artifact = json_value(raw)
        report = json_value(artifact_report)
    except (RecursionError, TypeError, ValueError) as exc:
        result["diagnostics"].append(diagnostic(
            "review_input_not_json", str(exc), stage="review-projection", path="$",
        ))
        return result
    if not isinstance(artifact, dict) or not isinstance(report, dict):
        result["diagnostics"].append(diagnostic(
            "review_input_invalid", "artifact and identity report must be JSON objects",
            stage="review-projection", path="$",
        ))
        return result
    if report.get("status") not in {"valid", "partial"}:
        result["diagnostics"].append(diagnostic(
            "review_artifact_not_validated",
            "identity report must validate the artifact before review projection",
            stage="review-projection", path="artifact_report.status",
        ))
        return result
    if report.get("identity", {}).get("content_digest") != content_digest(artifact):
        result["diagnostics"].append(diagnostic(
            "review_artifact_identity_mismatch",
            "identity report content digest does not bind the supplied artifact",
            stage="review-projection", path="artifact_report.identity.content_digest",
        ))
        return result
    try:
        if artifact.get("version") == BUSINESS_VERSION and report.get("layer") == "business":
            return _business_views(artifact, report)
        if artifact.get("version") == CORE_VERSION and report.get("layer") == "core":
            return _core_views(artifact, report)
    except (KeyError, TypeError, ValueError) as exc:
        result["diagnostics"].append(diagnostic(
            "review_artifact_reload_failed", str(exc), stage="review-projection", path="$",
        ))
        return result
    result["diagnostics"].append(diagnostic(
        "unsupported_review_artifact",
        "review views support validated aircraft Business and Core artifacts only",
        stage="review-projection", path="version",
    ))
    return result
