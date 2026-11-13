"""Serializable execution plan for the independent reference runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from .reliability import (
    RELIABILITY_POLICY,
    ReliabilityComponentGroupSpec,
    ReliabilityComponentInstanceSpec,
    _reject,
    _reject_failure_threshold,
    _validate_component_tables,
)


PLAN_VERSION = "aircraft-support-plan/v1alpha2"
LEGACY_MINUTE_PHASES = (
    "transport_arrivals",
    "mission_returns",
    "job_progress_and_completions",
    "failures",
    "operations_postflight_before_preparation",
    "preventive_generation",
    "preflight_generation",
    "resource_dispatch",
    "mission_dispatch",
    "operations_postflight_after_dispatch",
    "mission_success",
    "daily_readiness",
    "operational_availability",
    "downtime",
    "stop",
)


@dataclass(frozen=True)
class AircraftSpec:
    index: int
    tail_number: str
    aircraft_type: str
    model: str
    initial_state: str
    airport: str = ""
    airport_id: str = ""
    initial_calendar_days: int = 0
    initial_flight_hours: float = 0.0
    initial_cycles: int = 0


@dataclass(frozen=True)
class MissionSpec:
    index: int
    mission_id: str
    name: str
    planned_start: int
    preparation_start: int
    duration_minutes: int
    required_aircraft: int
    min_required_aircraft: int
    priority: int
    cancel_minutes: int
    success_point: float
    required_aircraft_type: str
    operations_plan_group_id: str
    source_path: str


@dataclass(frozen=True)
class WorkStepSpec:
    index: int
    code: str
    duration_minutes: int
    personnel: int
    equipment: int
    spares: tuple[tuple[str, int], ...]
    predecessors: tuple[int, ...]
    source_path: str


@dataclass(frozen=True)
class ActivitySpec:
    index: int
    activity_id: str
    name: str
    phase: str
    plan_group_id: str
    aircraft_model: str
    resource_node_index: int
    priority: int
    kind: str
    equipment_component_index: int
    maintenance_methods: tuple[str, ...]
    replacement_ratio: float
    steps: tuple[WorkStepSpec, ...]
    source_path: str


@dataclass(frozen=True)
class ResourceNodeSpec:
    index: int
    node_id: str
    personnel_capacity: int
    equipment_capacity: int
    inventory: tuple[tuple[str, int], ...]
    organization_node_id: str
    source_path: str


@dataclass(frozen=True)
class ComponentSpec:
    index: int
    component_id: str
    name: str
    parent_index: int
    aircraft_indexes: tuple[int, ...]
    product_id: str
    product_type: str
    quantity: int
    failure_rate_per_hour: float
    failure_threshold: int
    repair_activity_index: int
    repair_duration_minutes: int
    source_path: str


@dataclass(frozen=True)
class PreventiveCycleSpec:
    index: int
    aircraft_index: int
    activity_index: int
    calendar_days: int
    flight_hours: float
    landing_cycles: int
    initial_calendar_days: int
    initial_flight_hours: float
    initial_landing_cycles: int
    source_path: str


@dataclass(frozen=True)
class SupplyRouteSpec:
    index: int
    route_id: str
    source_node_index: int
    destination_node_index: int
    product_id: str
    capacity: int
    transport_minutes: int
    supply_mode: str
    relation_id: str
    source_path: str


@dataclass(frozen=True)
class ExecutionPlan:
    plan_version: str
    domain: str
    semantic_profile: str
    work_policy: str
    rng_profile: str
    source_inputs_sha256: str
    duration_minutes: int
    natural_completion_enabled: bool
    phases: tuple[str, ...]
    aircraft: tuple[AircraftSpec, ...]
    missions: tuple[MissionSpec, ...]
    activities: tuple[ActivitySpec, ...]
    resource_nodes: tuple[ResourceNodeSpec, ...]
    components: tuple[ComponentSpec, ...]
    preventive_cycles: tuple[PreventiveCycleSpec, ...]
    supply_routes: tuple[SupplyRouteSpec, ...]
    unsupported_features: tuple[str, ...]
    reliability_policy: str | None = None
    component_groups: tuple[ReliabilityComponentGroupSpec, ...] = ()
    component_instances: tuple[ReliabilityComponentInstanceSpec, ...] = ()
    resource_dispatch_index: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.resource_dispatch_index is None:
            value.pop("resource_dispatch_index")
        if self.reliability_policy is None:
            value.pop("reliability_policy")
        if not self.component_groups:
            value.pop("component_groups")
        if not self.component_instances:
            value.pop("component_instances")
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionPlan":
        if value.get("plan_version") != PLAN_VERSION:
            raise ValueError(f"unsupported plan version {value.get('plan_version')!r}")

        reliability_policy = value.get("reliability_policy")
        if reliability_policy is not None:
            _reject_failure_threshold(value)
        groups = tuple(
            ReliabilityComponentGroupSpec(
                **{
                    **item,
                    "aircraft_indexes": tuple(item.get("aircraft_indexes", ())),
                }
            )
            for item in value.get("component_groups", ())
        )
        instances = tuple(
            ReliabilityComponentInstanceSpec(**item)
            for item in value.get("component_instances", ())
        )
        if reliability_policy is not None:
            _validate_component_tables(
                groups,
                instances,
                aircraft_count=len(value.get("aircraft", ())),
            )
        elif groups or instances:
            _reject(
                "component_groups/component_instances require reliability_policy",
                "unsupported_reliability_policy",
                "reliability_policy",
            )

        activities = []
        for activity in value.get("activities", []):
            steps = tuple(
                WorkStepSpec(
                    **{
                        **step,
                        "predecessors": tuple(step.get("predecessors", ())),
                        "spares": tuple(tuple(item) for item in step.get("spares", ())),
                    }
                )
                for step in activity.get("steps", [])
            )
            activities.append(
                ActivitySpec(
                    **{
                        **activity,
                        "steps": steps,
                        "maintenance_methods": tuple(
                            activity.get("maintenance_methods", ())
                        ),
                    }
                )
            )
        return cls(
            plan_version=value["plan_version"],
            domain=value["domain"],
            semantic_profile=value["semantic_profile"],
            work_policy=value["work_policy"],
            rng_profile=value["rng_profile"],
            source_inputs_sha256=value["source_inputs_sha256"],
            duration_minutes=int(value["duration_minutes"]),
            natural_completion_enabled=bool(
                value.get("natural_completion_enabled", False)
            ),
            phases=tuple(value.get("phases", ())),
            aircraft=tuple(AircraftSpec(**item) for item in value.get("aircraft", [])),
            missions=tuple(MissionSpec(**item) for item in value.get("missions", [])),
            activities=tuple(activities),
            resource_nodes=tuple(
                ResourceNodeSpec(
                    **{
                        **item,
                        "inventory": tuple(
                            tuple(entry) for entry in item.get("inventory", ())
                        ),
                    }
                )
                for item in value.get("resource_nodes", [])
            ),
            components=tuple(
                ComponentSpec(
                    **{
                        **item,
                        "aircraft_indexes": tuple(item.get("aircraft_indexes", ())),
                    }
                )
                for item in value.get("components", [])
            ),
            preventive_cycles=tuple(
                PreventiveCycleSpec(**item)
                for item in value.get("preventive_cycles", [])
            ),
            supply_routes=tuple(
                SupplyRouteSpec(**item) for item in value.get("supply_routes", [])
            ),
            unsupported_features=tuple(value.get("unsupported_features", ())),
            reliability_policy=reliability_policy,
            component_groups=groups,
            component_instances=instances,
            resource_dispatch_index=value.get("resource_dispatch_index"),
        )

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            {
                key: value
                for key, value in self.to_dict().items()
                if key != "resource_dispatch_index"
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()
