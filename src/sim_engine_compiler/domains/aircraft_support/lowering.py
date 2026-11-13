"""Aircraft compatibility rules: Business IR to symbolic Core IR.

Typed lowering records below are temporary compiler data; no ExecutionPlan is
constructed in this module. The generic layout pass owns dense Plan addresses.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.domains.aircraft_support.validation import validate_canonical_work
from sim_engine_compiler.ir.reliability import RELIABILITY_POLICY
from sim_engine_compiler.ir.plan import (
    LEGACY_MINUTE_PHASES,
    ActivitySpec,
    AircraftSpec,
    ComponentSpec,
    MissionSpec,
    PreventiveCycleSpec,
    ResourceNodeSpec,
    SupplyRouteSpec,
    WorkStepSpec,
)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_int(value: Any, default: int) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _time_to_minute(value: Any, default: int) -> int:
    if not isinstance(value, str) or ":" not in value:
        return default
    parts = value.split(":")
    try:
        return max(0, int(parts[0]) * 60 + int(parts[1]))
    except (ValueError, IndexError):
        return default


def _resource_quantity(items: Any, explicit: Any, default: int) -> int:
    if isinstance(explicit, (int, float)) and explicit > 0:
        return max(1, int(explicit))
    if isinstance(items, list):
        total = 0
        for item in items:
            if isinstance(item, dict):
                total += _non_negative_int(item.get("quantity", 1), 1)
        if total > 0:
            return total
    return default


def _spare_requirements(value: Any) -> tuple[tuple[str, int], ...]:
    result: dict[str, int] = {}
    rows = value if isinstance(value, list) else [value]
    for row in rows:
        product_id = ""
        quantity: Any = 1
        if isinstance(row, dict):
            product_id = str(
                row.get("product_id")
                or row.get("productId")
                or row.get("spare_type")
                or row.get("id")
                or ""
            ).strip()
            quantity = row.get("quantity", 1)
        elif isinstance(row, str):
            parts = [item.strip() for item in row.split(",")]
            product_id = parts[0] if parts else ""
            quantity = parts[1] if len(parts) > 1 else 1
        if product_id:
            result[product_id] = result.get(product_id, 0) + _positive_int(quantity, 1)
    return tuple(sorted(result.items()))


def _activity_kind(item: dict[str, Any]) -> str:
    phase = str(item.get("operations_phase") or "")
    if phase:
        return phase
    text = f"{item.get('id', '')} {item.get('name', '')} {item.get('activity_type', '')}".lower()
    if "corrective" in text or "repair" in text or "修复性维修" in text or "故障修复" in text:
        return "repair"
    if "preventive" in text or "预防" in text or "定检" in text:
        return "preventive"
    if "postflight" in text or "飞行后" in text or "航后" in text:
        return "postflight"
    if "preflight" in text or "飞行前" in text or "直接准备" in text or "使用保障" in text:
        return "preflight"
    return "other"


def _aircraft_tokens(value: Any) -> set[str]:
    text = str(value or "").strip().casefold()
    if not text:
        return set()
    compact = "".join(char for char in text if char.isalnum())
    return {text, compact} - {""}


def _topological_steps(activity: dict[str, Any], source_path: str) -> tuple[WorkStepSpec, ...]:
    raw_steps = [item for item in activity.get("jobs") or [] if isinstance(item, dict)]
    codes = [str(item.get("activityCode") or f"step-{index + 1}") for index, item in enumerate(raw_steps)]
    if len(codes) != len(set(codes)):
        raise CompilationError(f"duplicate activityCode in {activity.get('id')!r}")
    source_index = {code: index for index, code in enumerate(codes)}
    predecessors_by_source: list[tuple[int, ...]] = []
    for item in raw_steps:
        unknown = [str(code) for code in item.get("predecessors") or [] if str(code) not in source_index]
        if unknown:
            raise CompilationError(
                f"unknown predecessor in {activity.get('id')!r}: {unknown}"
            )
        predecessors_by_source.append(
            tuple(source_index[str(code)] for code in item.get("predecessors") or [])
        )
    ordered_source_indexes: list[int] = []
    completed: set[int] = set()
    remaining = list(range(len(raw_steps)))
    while remaining:
        progressed = False
        # This scan order is part of legacy-minute-v1. A predecessor completed
        # earlier in the same scan makes its successor immediately eligible.
        for index in list(remaining):
            if all(parent in completed for parent in predecessors_by_source[index]):
                completed.add(index)
                ordered_source_indexes.append(index)
                remaining.remove(index)
                progressed = True
        if not progressed:
            raise CompilationError(f"cycle in activity {activity.get('id')!r}")
    dense_index = {source: dense for dense, source in enumerate(ordered_source_indexes)}
    result = []
    for dense, source in enumerate(ordered_source_indexes):
        item = raw_steps[source]
        result.append(
            WorkStepSpec(
                index=dense,
                code=codes[source],
                duration_minutes=_positive_int(
                    item.get("durationMinutes", item.get("duration_minutes")),
                    _positive_int(activity.get("duration_minutes"), 30),
                ),
                personnel=_resource_quantity(
                    item.get("personnel"),
                    item.get(
                        "requiredPersonnel",
                        item.get("required_personnel", activity.get("required_personnel")),
                    ),
                    1,
                ),
                equipment=_resource_quantity(
                    item.get("equipment"),
                    item.get(
                        "requiredDevices",
                        item.get("required_devices", activity.get("required_devices")),
                    ),
                    1,
                ),
                spares=_spare_requirements(item.get("spare")),
                predecessors=tuple(dense_index[parent] for parent in predecessors_by_source[source]),
                source_path=f"{source_path}.jobs[{source}]",
            )
        )
    return tuple(result)


def _compile_aircraft(inputs: dict[str, Any]) -> tuple[AircraftSpec, ...]:
    config = inputs.get("aircraft") if isinstance(inputs.get("aircraft"), dict) else {}
    assets = [item for item in config.get("assets") or [] if isinstance(item, dict)]
    fleet_count = max(1, _positive_int(config.get("fleet_count"), 0), len(assets))
    initial_ready = min(fleet_count, _non_negative_int(config.get("initial_ready"), fleet_count))
    models = list(config.get("models") or ["Aircraft"])
    result = []
    for index in range(fleet_count):
        item = assets[index] if index < len(assets) else {}
        initial_life = item.get("initial_life_state") if isinstance(item.get("initial_life_state"), dict) else {}
        aircraft_type = str(
            item.get("aircraft_type")
            or item.get("aircraftType")
            or item.get("model")
            or models[index % len(models)]
        )
        state = str(item.get("initial_state") or item.get("initialState") or "")
        if state not in {"available", "maintenance", "flying"}:
            state = "available" if index < initial_ready else "maintenance"
        result.append(
            AircraftSpec(
                index=index,
                tail_number=str(
                    item.get("tail_number") or item.get("tailNumber") or f"AC-{index + 1:03d}"
                ),
                aircraft_type=aircraft_type,
                model=str(item.get("model") or aircraft_type),
                initial_state=state,
                airport=str(item.get("airport") or ""),
                airport_id=str(item.get("airport_id") or item.get("airportId") or ""),
                initial_calendar_days=_non_negative_int(initial_life.get("calendar_days"), 0),
                initial_flight_hours=max(0.0, float(initial_life.get("flight_hours") or 0.0)),
                initial_cycles=_non_negative_int(initial_life.get("takeoff_landing_cycles"), 0),
            )
        )
    if len({item.tail_number for item in result}) != len(result):
        raise CompilationError("aircraft tail numbers must be unique")
    return tuple(result)


def _compile_nodes(inputs: dict[str, Any]) -> tuple[ResourceNodeSpec, ...]:
    network = inputs.get("support_network") if isinstance(inputs.get("support_network"), dict) else {}
    raw_nodes = [item for item in network.get("nodes") or [] if isinstance(item, dict)]
    if not raw_nodes:
        raw_nodes = [{"id": "default", "personnel_capacity": 1, "equipment_capacity": 1}]
    result = tuple(
        ResourceNodeSpec(
            index=index,
            node_id=str(item.get("id") or f"node-{index + 1}"),
            personnel_capacity=_non_negative_int(item.get("personnel_capacity"), 0),
            equipment_capacity=_non_negative_int(item.get("equipment_capacity"), 0),
            inventory=tuple(
                sorted(
                    (str(key), _non_negative_int(value, 0))
                    for key, value in (item.get("inventory") or {}).items()
                )
            ),
            organization_node_id=str(
                item.get("organization_node_id")
                or item.get("organizationNodeId")
                or item.get("id")
                or ""
            ),
            source_path=f"support_network.nodes[{index}]",
        )
        for index, item in enumerate(raw_nodes)
    )
    if len({item.node_id for item in result}) != len(result):
        raise CompilationError("support node ids must be unique")
    return result


def _compile_activities(
    inputs: dict[str, Any], nodes: tuple[ResourceNodeSpec, ...], component_indexes: dict[str, int]
) -> tuple[ActivitySpec, ...]:
    raw = inputs.get("support_activities")
    raw = raw if isinstance(raw, dict) else {}
    raw_activities = [item for item in raw.get("activities") or [] if isinstance(item, dict)]
    node_index = {node.node_id: node.index for node in nodes}
    default_node = next((node.index for node in nodes if node.personnel_capacity or node.equipment_capacity), 0)
    result = []
    for index, item in enumerate(raw_activities):
        activity_id = str(item.get("id") or f"activity-{index + 1}")
        resource_id = str(item.get("resource_id") or "")
        if resource_id and resource_id not in node_index:
            raise CompilationError(f"unknown resource node {resource_id!r} for {activity_id!r}")
        result.append(
            ActivitySpec(
                index=index,
                activity_id=activity_id,
                name=str(item.get("name") or activity_id),
                phase=str(item.get("operations_phase") or ""),
                plan_group_id=str(item.get("plan_group_id") or ""),
                aircraft_model=str(item.get("aircraft_model") or ""),
                resource_node_index=node_index.get(resource_id, default_node),
                priority=_positive_int(item.get("priority"), 1),
                kind=_activity_kind(item),
                equipment_component_index=component_indexes.get(str(item.get("equipment_id") or ""), -1),
                maintenance_methods=tuple(
                    dict.fromkeys(
                        str(value)
                        for value in item.get("maintenance_methods") or []
                        if str(value) in {"non_replacement", "replacement"}
                    )
                ),
                replacement_ratio=min(1.0, max(0.0, float(item.get("replacement_ratio") or 0.0))),
                steps=_topological_steps(item, f"support_activities.activities[{index}]"),
                source_path=f"support_activities.activities[{index}]",
            )
        )
    if len({item.activity_id for item in result}) != len(result):
        raise CompilationError("support activity ids must be unique")
    return tuple(result)


def _basic_missions(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(profile.get("basic_missions") or []):
        if not isinstance(item, dict):
            continue
        mission_id = str(item.get("id") or item.get("missionId") or item.get("taskNo") or f"basic-{index + 1}")
        for alias in (mission_id, item.get("name"), item.get("basicTaskName"), item.get("missionId"), item.get("taskNo")):
            if str(alias or "").strip():
                result.setdefault(str(alias), item)
    return result


def _compile_missions(inputs: dict[str, Any], duration_minutes: int) -> tuple[MissionSpec, ...]:
    profile = inputs.get("mission_profile") if isinstance(inputs.get("mission_profile"), dict) else {}
    airports = [item for item in profile.get("airports") or [] if isinstance(item, dict)]
    phases = [item for item in profile.get("mission_phases") or [] if isinstance(item, dict)]
    distance_km = max(
        (max(0.0, float(item.get("distanceToMissionKm") or 0.0)) for item in airports),
        default=0.0,
    )
    phase_minutes = sum(
        round(max(0.0, float(item.get("limitHours") or 0.0)) * 10) for item in phases
    )
    duration_adjustment = max(
        0, int(round((distance_km / 900.0) * 60)) + int(phase_minutes)
    )
    basics = _basic_missions(profile)
    default_basic = next(iter(basics.values()), {})
    calendar = profile.get("mission_calendar")
    has_calendar = isinstance(calendar, list)
    active_days: dict[str, list[int]] = {}
    for item in calendar or []:
        if not isinstance(item, dict):
            continue
        composite_id = str(item.get("composite_task_id") or "")
        day = _positive_int(item.get("day_index"), 0)
        if composite_id and day:
            active_days.setdefault(composite_id, []).append(day - 1)
    result: list[MissionSpec] = []
    for composite_index, composite in enumerate(profile.get("composite_tasks") or []):
        if not isinstance(composite, dict):
            continue
        composite_id = str(composite.get("id") or "")
        if has_calendar and composite_id not in active_days:
            continue
        for item_index, item in enumerate(composite.get("taskItems") or []):
            if not isinstance(item, dict):
                continue
            basic = default_basic
            for alias in (item.get("basicMissionId"), item.get("basicTaskName")):
                if str(alias or "") in basics:
                    basic = basics[str(alias)]
                    break
            base_id = str(item.get("id") or f"{composite_id}__item-{item_index + 1}")
            first_start = _time_to_minute(
                item.get("firstWaveTime"), _positive_int(basic.get("startHour"), 1) * 60
            )
            notice = _non_negative_int(
                item.get("advanceNoticeMinutes", basic.get("advanceNoticeMinutes")), 0
            )
            mission_duration = _positive_int(
                item.get("taskDurationMinutes", basic.get("taskDurationMinutes")), 120
            ) + duration_adjustment
            repeat_count = _positive_int(item.get("dailyRepeatCount"), 1)
            interval_value = item.get("intervalHours")
            interval = max(1, round(float(24 if interval_value is None else interval_value) * 60))
            days = sorted(set(active_days.get(composite_id, [0])))
            for day in days:
                for repeat in range(repeat_count):
                    planned = day * 1440 + first_start + repeat * interval
                    if planned >= min(duration_minutes, _positive_int(profile.get("duration_minutes"), duration_minutes)):
                        continue
                    result.append(
                        MissionSpec(
                            index=-1,
                            mission_id=f"{base_id}-d{planned // 1440 + 1}-w{repeat + 1}",
                            name=str(item.get("basicTaskName") or composite.get("name") or basic.get("name") or base_id),
                            planned_start=planned,
                            preparation_start=max(0, planned - notice),
                            duration_minutes=mission_duration,
                            required_aircraft=_positive_int(item.get("equipmentQuantity", basic.get("equipmentQuantity")), 1),
                            min_required_aircraft=_positive_int(basic.get("minRequiredSorties", basic.get("equipmentQuantity")), 1),
                            priority=_positive_int(composite.get("priority"), 1),
                            cancel_minutes=_non_negative_int(basic.get("cancelMinutes"), 20),
                            success_point=min(1.0, max(0.0, float(basic.get("successPoint", 1.0)))),
                            required_aircraft_type=str(item.get("equipmentType") or basic.get("equipmentType") or ""),
                            operations_plan_group_id=str(item.get("operations_plan_group_id") or basic.get("operations_plan_group_id") or ""),
                            source_path=f"mission_profile.composite_tasks[{composite_index}].taskItems[{item_index}]",
                        )
                    )
    if not result and not has_calendar:
        basic = default_basic
        planned = _positive_int(basic.get("startHour"), 1) * 60
        notice = _non_negative_int(basic.get("advanceNoticeMinutes"), 0)
        result.append(
            MissionSpec(
                index=0,
                mission_id=str(basic.get("missionId") or basic.get("id") or "mission-1"),
                name=str(basic.get("name") or "mission"),
                planned_start=planned,
                preparation_start=max(0, planned - notice),
                duration_minutes=_positive_int(basic.get("taskDurationMinutes"), 120),
                required_aircraft=_positive_int(basic.get("equipmentQuantity"), 1),
                min_required_aircraft=_positive_int(basic.get("minRequiredSorties", basic.get("equipmentQuantity")), 1),
                priority=1,
                cancel_minutes=_non_negative_int(basic.get("cancelMinutes"), 20),
                success_point=min(1.0, max(0.0, float(basic.get("successPoint", 1.0)))),
                required_aircraft_type=str(basic.get("equipmentType") or ""),
                operations_plan_group_id=str(basic.get("operations_plan_group_id") or ""),
                source_path="mission_profile.basic_missions[0]",
            )
        )
    result.sort(key=lambda item: (item.planned_start, item.priority))
    return tuple(
        MissionSpec(**{**item.__dict__, "index": index}) for index, item in enumerate(result)
    )


def _failure_distribution_rate(distribution: dict[str, Any]) -> float | None:
    if "mtbf" in distribution:
        return 1.0 / float(distribution["mtbf"])
    parameters = distribution.get("parameters") or distribution.get("params")
    multiplier = max(0.0, float(distribution.get("_rate_multiplier") or 1.0))
    if isinstance(parameters, (int, float)):
        return max(0.0, float(parameters)) * multiplier
    distribution_type = str(
        distribution.get("distributionType") or distribution.get("distribution_type") or ""
    ).lower()
    values: dict[str, float] = {}
    if isinstance(parameters, str):
        for part in parameters.replace("，", ",").replace("；", ",").replace(";", ",").split(","):
            if "=" not in part:
                continue
            key, raw = [item.strip().lower() for item in part.split("=", 1)]
            try:
                values[key] = max(0.0, float(raw))
            except ValueError:
                values[key] = 0.0
        for key in ("lambda", "λ", "rate", "failure_rate"):
            if key in values:
                return values[key] * multiplier
        if "weibull" in distribution_type or "威布尔" in distribution_type:
            beta = values.get("beta") or values.get("shape") or 1.0
            eta = values.get("eta") or values.get("scale") or values.get("mean")
            if eta and eta > 0:
                return (1.0 / (eta * math.gamma(1.0 + 1.0 / max(beta, 0.001)))) * multiplier
        if "normal" in distribution_type or "正态" in distribution_type:
            mean = values.get("mean") or values.get("mu")
            if mean and mean > 0:
                return (1.0 / mean) * multiplier
    if "exponential" in distribution_type or "指数" in distribution_type:
        rate = max(0.0, float(distribution.get("lambda") or distribution.get("rate") or 0.0))
        return rate * multiplier if rate > 0 else None
    if "normal" in distribution_type or "正态" in distribution_type:
        mean = max(0.0, float(distribution.get("mean") or distribution.get("mu") or 0.0))
        return (1.0 / mean) * multiplier if mean > 0 else None
    if "uniform" in distribution_type or "均匀" in distribution_type:
        minimum = float(distribution.get("min") if distribution.get("min") is not None else -1)
        maximum = float(distribution.get("max") if distribution.get("max") is not None else -1)
        if minimum >= 0 and maximum >= minimum and minimum + maximum > 0:
            return (2.0 / (minimum + maximum)) * multiplier
    if "fixed" in distribution_type or "固定" in distribution_type:
        value = float(distribution.get("value") or distribution.get("mean") or 0.0)
        return (1.0 / value) * multiplier if value > 0 else None
    return None


def _component_applies(component_model: Any, aircraft: AircraftSpec) -> bool:
    component_tokens = _aircraft_tokens(component_model)
    return not component_tokens or bool(
        component_tokens & (_aircraft_tokens(aircraft.aircraft_type) | _aircraft_tokens(aircraft.model))
    )


def _compile_components(
    inputs: dict[str, Any],
    aircraft: tuple[AircraftSpec, ...],
    activities: tuple[ActivitySpec, ...],
) -> tuple[ComponentSpec, ...]:
    raw = [
        item
        for item in inputs.get("equipment_tree", {}).get("components", [])
        if isinstance(item, dict) and item.get("id") not in (None, "")
    ]
    indexes = {str(item.get("id")): index for index, item in enumerate(raw)}
    generic_repairs = [item for item in activities if item.kind == "repair" and item.equipment_component_index < 0]
    result: list[ComponentSpec] = []
    for index, item in enumerate(raw):
        component_id = str(item.get("id"))
        quantity = max(1, int(item.get("quantity") or 1))
        rate = _failure_distribution_rate(item.get("failure_distribution") or {}) or 0.0
        applicable = tuple(
            aircraft_item.index
            for aircraft_item in aircraft
            if _component_applies(item.get("aircraft_model"), aircraft_item)
        )
        exact_repairs = [
            activity.index
            for activity in activities
            if activity.kind == "repair" and activity.equipment_component_index == index
        ]
        compatible_generic = [
            activity.index
            for activity in generic_repairs
            if not _aircraft_tokens(activity.aircraft_model)
            or any(
                _aircraft_tokens(activity.aircraft_model)
                & (_aircraft_tokens(aircraft[i].aircraft_type) | _aircraft_tokens(aircraft[i].model))
                for i in applicable
            )
        ]
        repair_activity = (exact_repairs or compatible_generic or [-1])[0]
        special = item.get("special_repair_profile") if isinstance(item.get("special_repair_profile"), dict) else {}
        result.append(
            ComponentSpec(
                index=index,
                component_id=component_id,
                name=str(item.get("name") or component_id),
                parent_index=indexes.get(str(item.get("parent_id") or ""), -1),
                aircraft_indexes=applicable,
                product_id=str(item.get("product_id") or item.get("spare_type") or ""),
                product_type=str(item.get("product_type") or ""),
                quantity=quantity,
                failure_rate_per_hour=max(0.0, rate),
                failure_threshold=1,
                repair_activity_index=repair_activity,
                repair_duration_minutes=_positive_int(special.get("repairTimeMinutes"), 0),
                source_path=f"equipment_tree.components[{index}]",
            )
        )
    return tuple(result)


def _compile_preventive_cycles(
    inputs: dict[str, Any], activities: tuple[ActivitySpec, ...]
) -> tuple[PreventiveCycleSpec, ...]:
    activity_indexes = {item.activity_id: item.index for item in activities}
    result: list[PreventiveCycleSpec] = []
    for aircraft_index, asset in enumerate(inputs.get("aircraft", {}).get("assets", [])):
        if not isinstance(asset, dict):
            continue
        fallback = asset.get("initial_life_state") if isinstance(asset.get("initial_life_state"), dict) else {}
        for cycle_index, cycle in enumerate(asset.get("preventive_cycles") or []):
            if not isinstance(cycle, dict):
                continue
            activity_id = str(cycle.get("activity_id") or cycle.get("activityId") or "")
            if activity_id not in activity_indexes:
                raise CompilationError(f"unknown preventive activity {activity_id!r}")
            thresholds = cycle.get("thresholds") if isinstance(cycle.get("thresholds"), dict) else {}
            life = cycle.get("initial_life_state") if isinstance(cycle.get("initial_life_state"), dict) else fallback
            result.append(
                PreventiveCycleSpec(
                    index=len(result),
                    aircraft_index=aircraft_index,
                    activity_index=activity_indexes[activity_id],
                    calendar_days=_non_negative_int(thresholds.get("calendar_days"), 0),
                    flight_hours=max(0.0, float(thresholds.get("flight_hours") or 0.0)),
                    landing_cycles=_non_negative_int(thresholds.get("takeoff_landing_cycles"), 0),
                    initial_calendar_days=_non_negative_int(life.get("calendar_days"), 0),
                    initial_flight_hours=max(0.0, float(life.get("flight_hours") or 0.0)),
                    initial_landing_cycles=_non_negative_int(life.get("takeoff_landing_cycles"), 0),
                    source_path=f"aircraft.assets[{aircraft_index}].preventive_cycles[{cycle_index}]",
                )
            )
    return tuple(result)


def _compile_supply_routes(
    inputs: dict[str, Any], nodes: tuple[ResourceNodeSpec, ...]
) -> tuple[SupplyRouteSpec, ...]:
    node_indexes: dict[str, int] = {}
    for node in nodes:
        node_indexes[node.node_id] = node.index
        if node.organization_node_id:
            node_indexes.setdefault(node.organization_node_id, node.index)
    graph = inputs.get("support_network", {}).get("organization_graph")
    graph = graph if isinstance(graph, dict) else {}
    lateral: dict[tuple[str, str], str] = {}
    for index, edge in enumerate(graph.get("lateral_edges") or []):
        if not isinstance(edge, dict) or not edge.get("enabled", True):
            continue
        source = str(edge.get("from_node_id") or edge.get("from") or "")
        destination = str(edge.get("to_node_id") or edge.get("to") or "")
        if source and destination:
            lateral[(source, destination)] = str(edge.get("id") or f"lateral-{index + 1}")
    routes: list[SupplyRouteSpec] = []
    canonical_policies = graph.get("transport_policies") or []
    policy_groups: list[tuple[int, list[Any], str]] = []
    if canonical_policies:
        policy_groups.append((-1, canonical_policies, "support_network.organization_graph.transport_policies"))
    else:
        for node_index, raw_node in enumerate(inputs.get("support_network", {}).get("nodes", [])):
            if isinstance(raw_node, dict):
                policy_groups.append(
                    (
                        node_index,
                        raw_node.get("transport_policies") or [],
                        f"support_network.nodes[{node_index}].transport_policies",
                    )
                )
    for node_index, policies, source_prefix in policy_groups:
        for policy_index, policy in enumerate(policies):
            if not isinstance(policy, dict):
                continue
            source_id = str(
                policy.get("from_organization_node_id")
                or policy.get("fromOrganizationNodeId")
                or policy.get("from")
                or policy.get("from_node_id")
                or ""
            )
            destination_id = str(
                policy.get("to_organization_node_id")
                or policy.get("toOrganizationNodeId")
                or policy.get("to")
                or policy.get("to_node_id")
                or (
                    inputs.get("support_network", {}).get("nodes", [])[node_index].get("id")
                    if node_index >= 0
                    else ""
                )
            )
            if source_id not in node_indexes or destination_id not in node_indexes:
                continue
            relation_id = lateral.get((source_id, destination_id), "")
            if policy.get("transport_minutes") not in (None, ""):
                transport_minutes = _non_negative_int(policy.get("transport_minutes"), 0)
            elif policy.get("transportMinutes") not in (None, ""):
                transport_minutes = _non_negative_int(policy.get("transportMinutes"), 0)
            else:
                transport_minutes = max(
                    0, round(float(policy.get("transportTimeHours") or policy.get("transport_time_hours") or 0.0) * 60)
                )
            routes.append(
                SupplyRouteSpec(
                    index=len(routes),
                    route_id=str(policy.get("id") or f"route-{node_index + 1}-{policy_index + 1}"),
                    source_node_index=node_indexes[source_id],
                    destination_node_index=node_indexes[destination_id],
                    product_id=str(policy.get("product_id") or policy.get("spare_type") or ""),
                    capacity=_positive_int(policy.get("capacity"), 1),
                    transport_minutes=transport_minutes,
                    supply_mode="lateral" if relation_id else "vertical",
                    relation_id=relation_id,
                    source_path=f"{source_prefix}[{policy_index}]",
                )
            )
    return tuple(routes)


def _core_provenance(business, aircraft):
    """Capture origins before layout and keep cycle identity separate from position."""
    from sim_engine_compiler.ir.layers import reject
    assets = business.payload['sections'].get('aircraft', {}).get('collections', {}).get('assets', [])
    origins = {'aircraft': {}, 'preventive_cycles': {}}
    for index, spec in enumerate(aircraft):
        entity = assets[index] if index < len(assets) else None
        path = entity['source_path'] if entity else 'aircraft.fleet_count'
        origins['aircraft'][spec.tail_number] = {'source_path': path}
        cycles = (entity['definition'].get('preventive_cycles') or []) if entity else []
        for cycle_index, cycle in enumerate(cycles):
            if not isinstance(cycle, dict):
                continue
            cycle_path = f'aircraft.assets[{index}].preventive_cycles[{cycle_index}]'
            explicit = [cycle[key] for key in ('id', 'cycle_id') if key in cycle]
            if explicit:
                if any(not isinstance(v, str) or not v for v in explicit) or len(set(explicit)) != 1:
                    reject(cycle_path, 'cycle id/cycle_id must be a consistent nonempty string')
                key = ['id', explicit[0]]
            else:
                equipment = cycle.get('equipment_id')
                if not isinstance(equipment, str) or not equipment:
                    reject(cycle_path, 'cycle requires id/cycle_id or stable equipment_id')
                key = ['equipment', equipment]
            origins['preventive_cycles'][cycle_path] = {
                'source_path': f'{path}.preventive_cycles[{cycle_index}]', 'cycle_key': key}
    return origins


def lower_business(business):
    from sim_engine_compiler.ir.layers import core_from_records
    inputs = business.canonical_view()
    semantic_profile = business.payload["semantic_profile"]
    if inputs.get("schema_version") != "aircraft-support-v1-input-v1":
        raise CompilationError("unsupported canonical input schema")
    if inputs.get("operations_support_policy") != "daily-v1":
        raise CompilationError("B1 requires operations_support_policy=daily-v1")
    time = inputs.get("time") if isinstance(inputs.get("time"), dict) else {}
    if semantic_profile not in {"legacy-minute-v1", "event-time-v2"}:
        raise CompilationError(f"unsupported time profile {semantic_profile!r}")
    if _positive_int(time.get("tick_minutes"), 1) != 1:
        raise CompilationError(f"{semantic_profile} requires tick_minutes=1")
    validate_canonical_work(inputs)
    duration = _positive_int(time.get("duration_minutes"), 1440)
    stop_policy = (
        inputs.get("stop_policy")
        if isinstance(inputs.get("stop_policy"), dict)
        else {}
    )
    stop_conditions = (
        stop_policy.get("conditions")
        if isinstance(stop_policy.get("conditions"), list)
        else []
    )
    natural_completion_enabled = bool(stop_policy.get("defaulted")) or not any(
        isinstance(condition, dict)
        and str(condition.get("type") or "") in {"duration", "specified_time"}
        for condition in stop_conditions
    )
    from sim_engine_compiler.domains.aircraft_support.reliability import (
        build_reliability_plan_records,
        is_reliability_input,
    )

    aircraft = _compile_aircraft(inputs)
    nodes = _compile_nodes(inputs)
    raw_component_indexes = {
        str(item.get("id")): index
        for index, item in enumerate(inputs.get("equipment_tree", {}).get("components", []))
        if isinstance(item, dict) and item.get("id") not in (None, "")
    }
    activities = _compile_activities(inputs, nodes, raw_component_indexes)
    missions = _compile_missions(inputs, duration)
    fused_reliability = is_reliability_input(inputs)
    if fused_reliability:
        groups, instances = build_reliability_plan_records(
            inputs,
            aircraft_ids=tuple(item.tail_number for item in aircraft),
        )
        components = ()
        activities = tuple(
            replace(item, equipment_component_index=-1) for item in activities
        )
    else:
        groups, instances = (), ()
        components = _compile_components(inputs, aircraft, activities)
    preventive_cycles = _compile_preventive_cycles(inputs, activities)
    supply_routes = _compile_supply_routes(inputs, nodes)

    features: list[str] = []
    records = {
        "aircraft": aircraft,
        "missions": missions,
        "activities": activities,
        "resource_nodes": nodes,
        "components": components,
        "preventive_cycles": preventive_cycles,
        "supply_routes": supply_routes,
    }
    if fused_reliability:
        records.update(
            {
                "component_groups": groups,
                "component_instances": instances,
                "reliability_policy": RELIABILITY_POLICY,
            }
        )

    return core_from_records(
        business=business,
        provenance=_core_provenance(business, aircraft),
        domain="aircraft-support",
        semantic_profile=semantic_profile,
        work_policy="stable-topological-serial",
        rng_profile="legacy-sequential-v1",
        duration_minutes=duration,
        natural_completion_enabled=natural_completion_enabled,
        phases=LEGACY_MINUTE_PHASES,
        unsupported_features=tuple(sorted(features)),
        **records,
    )
