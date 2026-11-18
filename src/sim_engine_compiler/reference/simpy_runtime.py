"""Independent SimPy interpreter for aircraft-support execution plans.

This module intentionally imports only the plan contract and SimPy. It does not
load canonical Project data or any legacy aircraft-support implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import random
from typing import Any

import simpy

from sim_engine_compiler.ir.plan import ActivitySpec, ExecutionPlan, MissionSpec, WorkStepSpec


class UnsupportedPlanError(ValueError):
    pass


@dataclass
class AircraftRuntimeState:
    tail_number: str
    aircraft_type: str
    model: str
    state: str
    current_mission_index: int | None = None
    return_time: int | None = None
    prepared_mission_indexes: set[int] = field(default_factory=set)
    operations_day: int | None = None
    daily_takeoffs: int = 0
    operations_plan_group_id: str = ""
    last_operations_mission_index: int | None = None
    prepared_operations_day: int | None = None
    postflight_required: bool = False
    postflight_due: bool = False
    flight_hours: float = 0.0
    takeoff_count: int = 0
    landing_count: int = 0
    failure_remaining: dict[tuple[int, int], float] = field(default_factory=dict)
    instance_failure_minutes: dict[tuple[int, int], int] = field(default_factory=dict)
    failed_component_index: int | None = None
    failed_component_instance_index: int | None = None
    failed_component_minute: int | None = None
    in_flight_failure: bool = False


@dataclass
class MissionRuntimeState:
    status: str = "scheduled"
    actual_start: int | None = None
    return_time: int | None = None
    assigned_aircraft: list[int] = field(default_factory=list)
    failed_aircraft: list[int] = field(default_factory=list)
    preflight_created: bool = False
    delay_minutes: int = 0
    success_evaluated: bool = False
    success_member_count: int = 0
    success_at_minute: int | None = None
    succeeded: bool = False


@dataclass
class JobRuntimeState:
    job_id: str
    aircraft_index: int
    kind: str
    activity_index: int
    mission_index: int | None
    state: str = "waiting"
    step_index: int = 0
    remaining: int = 0
    started_time: int | None = None
    completed_time: int | None = None
    reserved_personnel: int = 0
    reserved_equipment: int = 0
    component_index: int | None = None
    component_instance_index: int | None = None
    preventive_cycle_index: int | None = None
    maintenance_method: str | None = None
    injected_spares: tuple[tuple[str, int], ...] = ()
    requested_spare_steps: set[int] = field(default_factory=set)
    consumed_spare_steps: set[int] = field(default_factory=set)
    shortage_signature: tuple[tuple[str, int, int], ...] | None = None
    spare_reservations: dict[str, int] = field(default_factory=dict)


@dataclass
class ResourceRuntimeState:
    personnel_capacity: int
    equipment_capacity: int
    personnel_in_use: int = 0
    equipment_in_use: int = 0
    inventory: dict[str, int] = field(default_factory=dict)


@dataclass
class PreventiveCycleRuntimeState:
    life_flight_hours: float
    life_landing_cycles: int
    last_preventive_minute: int


@dataclass
class ShipmentRuntimeState:
    job_id: str
    step_index: int
    product_id: str
    quantity: int
    source_node_index: int
    destination_node_index: int
    requested_minute: int
    arrival_minute: int
    route_index: int


class SimpyReferenceRuntime:
    """Execute a validated aircraft-support plan with legacy minute ordering."""

    SUPPORTED_CAPABILITIES = frozenset(
        {"b1_task_daily_support", "b2_failure_repair", "b2_preventive_maintenance"}
    )

    def __init__(self, plan: ExecutionPlan, *, seed: int = 0):
        if plan.reliability_policy is not None:
            raise UnsupportedPlanError(
                f"Python reference runtime does not support reliability policy {plan.reliability_policy!r}"
            )
        if plan.semantic_profile != "legacy-minute-v1":
            raise UnsupportedPlanError(f"unsupported time profile {plan.semantic_profile!r}")
        if plan.work_policy != "stable-topological-serial":
            raise UnsupportedPlanError(f"unsupported work policy {plan.work_policy!r}")
        if plan.rng_profile != "legacy-sequential-v1":
            raise UnsupportedPlanError(f"unsupported RNG profile {plan.rng_profile!r}")
        if plan.unsupported_features:
            raise UnsupportedPlanError(
                "plan requires unfinished conformance slices: "
                + ", ".join(plan.unsupported_features)
            )
        self.plan = plan
        self.seed = int(seed)
        self.env = simpy.Environment()
        self.minute = 0
        self.phase = "initialize"
        self.running = True
        self.stop_reason = ""
        self.trace: list[dict[str, Any]] = []
        self.sample_requests: list[dict[str, Any]] = []
        self.rng = random.Random(self.seed)
        self.aircraft = [
            AircraftRuntimeState(
                tail_number=item.tail_number,
                aircraft_type=item.aircraft_type,
                model=item.model,
                state=item.initial_state,
                flight_hours=item.initial_flight_hours,
                takeoff_count=item.initial_cycles,
                landing_count=item.initial_cycles,
            )
            for item in plan.aircraft
        ]
        self.missions = [MissionRuntimeState() for _ in plan.missions]
        self.jobs: list[JobRuntimeState] = []
        self.resources = [
            ResourceRuntimeState(
                item.personnel_capacity,
                item.equipment_capacity,
                inventory=dict(item.inventory),
            )
            for item in plan.resource_nodes
        ]
        self.preventive_cycles = [
            PreventiveCycleRuntimeState(
                life_flight_hours=item.initial_flight_hours,
                life_landing_cycles=item.initial_landing_cycles,
                last_preventive_minute=-item.initial_calendar_days * 1440,
            )
            for item in plan.preventive_cycles
        ]
        self.shipments: list[ShipmentRuntimeState] = []
        self._job_sequence = 0
        self.launched_sorties = 0
        self.completed_sorties = 0
        self.cancelled_sorties = 0
        self.delayed_sorties = 0
        self.total_departure_delay = 0
        self.lru_failures = 0
        self.in_flight_failures = 0
        self.failed_sorties = 0
        self.preventive_maintenance_events = 0
        self.spare_demand_total = 0
        self.spare_immediately_filled_total = 0
        self.spare_consumed_total = 0
        self.shortage_events = 0
        self.transport_replenishment_events = 0
        self.total_transport_delay = 0
        self._delayed_missions: set[int] = set()
        self._activity_by_group_phase = self._index_activities()
        self._children_by_component = self._index_component_children()
        self._failure_instance_slots = tuple(
            tuple(
                (component.index, instance_index)
                for component in self.plan.components
                if component.failure_rate_per_hour > 0
                and aircraft_index in component.aircraft_indexes
                for instance_index in range(component.quantity)
            )
            for aircraft_index in range(len(self.aircraft))
        )
        self._initialize_failure_timers()

    def _index_component_children(self) -> dict[int, tuple[int, ...]]:
        result: dict[int, list[int]] = {}
        for component in self.plan.components:
            result.setdefault(component.parent_index, []).append(component.index)
        return {key: tuple(value) for key, value in result.items()}

    def _sample_instance_minutes(
        self,
        component_index: int,
        aircraft_index: int,
        instance_index: int,
        reason: str,
    ) -> float:
        component = self.plan.components[component_index]
        value = (
            self.rng.expovariate(component.failure_rate_per_hour) * 60.0
            if component.failure_rate_per_hour > 0
            else math.inf
        )
        self.sample_requests.append(
            {
                "sequence": len(self.sample_requests) + 1,
                "time": self.minute,
                "phase": self.phase,
                "stream": "legacy-sequential-v1",
                "distribution": "exponential",
                "entity": self.aircraft[aircraft_index].tail_number,
                "component_id": component.component_id,
                "quantity_index": instance_index,
                "instance_index": instance_index,
                "rate_per_hour": component.failure_rate_per_hour,
                "value_minutes": value,
                "reason": reason,
                "source_path": component.source_path,
            }
        )
        return value

    def _initialize_failure_timers(self) -> None:
        # Preserve the old model's draw-before-applicability order.
        for aircraft_index, aircraft in enumerate(self.aircraft):
            for component in self.plan.components:
                if component.failure_rate_per_hour <= 0:
                    continue
                for instance_index in range(component.quantity):
                    sampled = self._sample_instance_minutes(
                        component.index, aircraft_index, instance_index, "initialize"
                    )
                    if aircraft_index in component.aircraft_indexes:
                        aircraft.failure_remaining[(component.index, instance_index)] = sampled

    def _index_activities(self) -> dict[tuple[str, str], tuple[int, ...]]:
        result: dict[tuple[str, str], list[int]] = {}
        for activity in self.plan.activities:
            if activity.phase:
                result.setdefault((activity.plan_group_id, activity.phase), []).append(activity.index)
        return {key: tuple(value) for key, value in result.items()}

    def _emit(
        self,
        kind: str,
        rule_id: str,
        entity: str,
        details: dict[str, Any] | None = None,
        source_path: str | None = None,
    ) -> None:
        details = details or {}
        if source_path is None:
            activity_id = details.get("activity_id")
            if activity_id:
                source_path = next(
                    (
                        item.source_path
                        for item in self.plan.activities
                        if item.activity_id == activity_id
                    ),
                    None,
                )
            mission_id = details.get("mission_id")
            if source_path is None and mission_id:
                source_path = next(
                    (
                        item.source_path
                        for item in self.plan.missions
                        if item.mission_id == mission_id
                    ),
                    None,
                )
            if source_path is None:
                source_path = next(
                    (
                        item.source_path
                        for item in self.plan.missions
                        if item.mission_id == entity
                    ),
                    None,
                )
        self.trace.append(
            {
                "sequence": len(self.trace) + 1,
                "time": self.minute,
                "phase": self.phase,
                "kind": kind,
                "rule_id": rule_id,
                "entity": entity,
                "source_path": source_path,
                "details": details,
            }
        )

    def _matches_type(self, aircraft_index: int, mission: MissionSpec) -> bool:
        required = _tokens(mission.required_aircraft_type)
        if not required:
            return True
        aircraft = self.aircraft[aircraft_index]
        return bool(required & (_tokens(aircraft.aircraft_type) | _tokens(aircraft.model)))

    def _activity_for(self, group_id: str, phase: str, aircraft_index: int) -> ActivitySpec:
        candidates = [
            self.plan.activities[index]
            for index in self._activity_by_group_phase.get((group_id, phase), ())
            if not _tokens(self.plan.activities[index].aircraft_model)
            or _tokens(self.plan.activities[index].aircraft_model)
            & (_tokens(self.aircraft[aircraft_index].aircraft_type) | _tokens(self.aircraft[aircraft_index].model))
        ]
        if len(candidates) != 1:
            raise UnsupportedPlanError(
                f"operations group {group_id!r} requires exactly one compatible {phase} activity"
            )
        return candidates[0]

    def _preparation_activity(self, mission_index: int, aircraft_index: int) -> ActivitySpec:
        mission = self.plan.missions[mission_index]
        aircraft = self.aircraft[aircraft_index]
        day = max(self.minute, mission.planned_start) // 1440
        phase = "relaunch" if aircraft.operations_day == day and aircraft.daily_takeoffs else "preflight"
        aircraft.prepared_operations_day = day
        return self._activity_for(mission.operations_plan_group_id, phase, aircraft_index)

    def _create_job(
        self,
        aircraft_index: int,
        activity: ActivitySpec,
        *,
        kind: str,
        mission_index: int | None,
        component_index: int | None = None,
        component_instance_index: int | None = None,
        preventive_cycle_index: int | None = None,
    ) -> None:
        self._job_sequence += 1
        job = JobRuntimeState(
            job_id=f"job-{self._job_sequence:04d}",
            aircraft_index=aircraft_index,
            kind=kind,
            activity_index=activity.index,
            mission_index=mission_index,
            component_index=component_index,
            component_instance_index=component_instance_index,
            preventive_cycle_index=preventive_cycle_index,
        )
        if kind in {"repair", "preventive"}:
            job.maintenance_method = self._maintenance_method(activity, kind)
        if (
            kind == "repair"
            and component_index is not None
            and job.maintenance_method == "replacement"
            and activity.steps
            and not any(step.spares for step in activity.steps)
        ):
            component = self.plan.components[component_index]
            if component.product_type.strip().upper() == "LRU" and component.product_id:
                job.injected_spares = ((component.product_id, 1),)
        self.jobs.append(job)
        aircraft = self.aircraft[aircraft_index]
        self._emit(
            "operations_phase_created",
            "daily-v1.create-operation",
            job.job_id,
            {
                "tail_number": aircraft.tail_number,
                "mission_id": self._mission_id(mission_index),
                "activity_id": activity.activity_id,
                "operations_phase": activity.phase,
            },
        )
        if not activity.steps:
            job.state = "completed"
            job.started_time = job.completed_time = self.minute
            self._complete_job(job)

    def _maintenance_method(self, activity: ActivitySpec, kind: str) -> str:
        methods = list(activity.maintenance_methods) or ["non_replacement"]
        ratio = activity.replacement_ratio
        if methods == ["replacement"]:
            ratio = 1.0
        elif "replacement" not in methods:
            ratio = 0.0
        occurrence = 1 + sum(
            job.kind == kind and job.maintenance_method is not None for job in self.jobs
        )
        stream_key = f"{self.seed}|maintenance-method|{kind}|{occurrence}"
        digest = hashlib.sha256(stream_key.encode()).digest()
        roll = random.Random(int.from_bytes(digest[:16], "big")).random()
        method = "replacement" if "replacement" in methods and roll < ratio else "non_replacement"
        self._emit(
            "maintenance_method_selected",
            "maintenance.select-method",
            f"job-{self._job_sequence:04d}",
            {
                "maintenance_kind": kind,
                "maintenance_method": method,
                "replacement_ratio": ratio,
                "decision_roll": roll,
                "rng_stream": digest.hex()[:16],
                "maintenance_occurrence": occurrence,
            },
            activity.source_path,
        )
        return method

    def _complete_job(self, job: JobRuntimeState) -> None:
        activity = self.plan.activities[job.activity_index]
        aircraft = self.aircraft[job.aircraft_index]
        self._emit(
            "operations_phase_completed",
            "daily-v1.complete-operation",
            job.job_id,
            {
                "tail_number": aircraft.tail_number,
                "mission_id": self._mission_id(job.mission_index),
                "activity_id": activity.activity_id,
                "operations_phase": activity.phase,
            },
        )
        if job.kind == "preflight" and job.mission_index is not None:
            aircraft.prepared_mission_indexes.add(job.mission_index)
            aircraft.current_mission_index = job.mission_index
            aircraft.state = "mission_ready"
            self._emit(
                "preflight_completed",
                "mission.preflight-complete",
                aircraft.tail_number,
                {"mission_id": self._mission_id(job.mission_index)},
            )
        elif job.kind == "postflight":
            aircraft.state = "available"
            aircraft.postflight_required = False
            aircraft.postflight_due = False
            self._emit(
                "postflight_completed",
                "daily-v1.postflight-complete",
                aircraft.tail_number,
            )
        elif job.kind == "repair":
            if (job.component_index is None) != (job.component_instance_index is None):
                raise RuntimeError(
                    f"repair job {job.job_id!r} has incomplete component instance identity"
                )
            repaired_slot = None
            if job.component_index is not None:
                repaired_slot = (job.component_index, job.component_instance_index)
                aircraft.failure_remaining[repaired_slot] = self._sample_instance_minutes(
                    job.component_index,
                    job.aircraft_index,
                    job.component_instance_index,
                    "repair_completed",
                )
            aircraft.failed_component_index = None
            aircraft.failed_component_instance_index = None
            aircraft.failed_component_minute = None
            if repaired_slot is not None:
                aircraft.instance_failure_minutes.pop(repaired_slot, None)
            aircraft.in_flight_failure = bool(aircraft.instance_failure_minutes)
            if aircraft.instance_failure_minutes:
                next_slot = min(
                    aircraft.instance_failure_minutes,
                    key=lambda slot: (
                        aircraft.instance_failure_minutes[slot],
                        slot[0],
                        slot[1],
                    ),
                )
                next_component = self.plan.components[next_slot[0]]
                if next_component.repair_activity_index < 0:
                    raise UnsupportedPlanError(
                        f"no repair activity for component {next_component.component_id!r}"
                    )
                aircraft.state = "maintenance"
                aircraft.failed_component_index = next_slot[0]
                aircraft.failed_component_instance_index = next_slot[1]
                aircraft.failed_component_minute = aircraft.instance_failure_minutes[next_slot]
                self._create_job(
                    job.aircraft_index,
                    self.plan.activities[next_component.repair_activity_index],
                    kind="repair",
                    mission_index=job.mission_index,
                    component_index=next_slot[0],
                    component_instance_index=next_slot[1],
                )
            else:
                aircraft.state = "available"
            self._emit(
                "repair_completed",
                "maintenance.repair-complete",
                aircraft.tail_number,
                {
                    "component_id": self.plan.components[job.component_index].component_id
                    if job.component_index is not None
                    else None,
                    "instance_index": repaired_slot[1] if repaired_slot is not None else None,
                },
            )
        elif job.kind == "preventive" and job.preventive_cycle_index is not None:
            cycle_spec = self.plan.preventive_cycles[job.preventive_cycle_index]
            cycle = self.preventive_cycles[job.preventive_cycle_index]
            if cycle_spec.flight_hours > 0:
                cycle.life_flight_hours = 0.0
            if cycle_spec.landing_cycles > 0:
                cycle.life_landing_cycles = 0
            cycle.last_preventive_minute = self.minute
            aircraft.state = "available"
            first_cycle = next(
                (
                    index
                    for index, item in enumerate(self.plan.preventive_cycles)
                    if item.aircraft_index == job.aircraft_index
                ),
                None,
            )
            if first_cycle == job.preventive_cycle_index:
                aircraft.flight_hours = 0.0
                aircraft.takeoff_count = 0
                aircraft.landing_count = 0
            self._emit(
                "preventive_completed",
                "maintenance.preventive-complete",
                aircraft.tail_number,
                {"activity_id": activity.activity_id},
            )

    def _mission_id(self, mission_index: int | None) -> str | None:
        return None if mission_index is None else self.plan.missions[mission_index].mission_id

    def _active_preflight_aircraft(self, mission_index: int) -> set[int]:
        return {
            job.aircraft_index
            for job in self.jobs
            if job.kind == "preflight"
            and job.mission_index == mission_index
            and job.state in {"waiting", "running"}
        }

    def _ready_for_mission(self, aircraft_index: int, mission_index: int) -> bool:
        aircraft = self.aircraft[aircraft_index]
        if mission_index not in aircraft.prepared_mission_indexes:
            return False
        if aircraft.state == "mission_ready":
            return aircraft.current_mission_index == mission_index
        return aircraft.state == "available" and aircraft.current_mission_index in {None, mission_index}

    def _commissioned_count(self, mission_index: int) -> int:
        mission = self.plan.missions[mission_index]
        return len(
            self._active_preflight_aircraft(mission_index)
            | {
                index
                for index in range(len(self.aircraft))
                if self._ready_for_mission(index, mission_index) and self._matches_type(index, mission)
            }
        )

    def _phase_mission_returns(self) -> None:
        for aircraft_index, aircraft in enumerate(self.aircraft):
            if aircraft.state != "flying" or aircraft.return_time is None or aircraft.return_time > self.minute:
                continue
            self._return_aircraft(aircraft_index, early_return=False)

    def _phase_transport_arrivals(self) -> None:
        for job in self.jobs:
            if job.state != "cancelled" or not job.spare_reservations:
                continue
            activity = self.plan.activities[job.activity_index]
            destination = self.resources[activity.resource_node_index]
            returned = []
            for product_id, quantity in list(job.spare_reservations.items()):
                destination.inventory[product_id] = destination.inventory.get(product_id, 0) + quantity
                returned.append({"product_id": product_id, "quantity": quantity})
            job.spare_reservations.clear()
            self._emit(
                "organization_spare_reservation_returned",
                "inventory.return-cancelled-reservation",
                job.job_id,
                {"products": returned, "node_index": activity.resource_node_index},
            )
        arrived = [item for item in self.shipments if item.arrival_minute <= self.minute]
        self.shipments = [item for item in self.shipments if item.arrival_minute > self.minute]
        for shipment in arrived:
            destination = self.resources[shipment.destination_node_index]
            job = next((item for item in self.jobs if item.job_id == shipment.job_id), None)
            reserved = bool(
                job is not None
                and job.state == "waiting"
                and job.step_index == shipment.step_index
            )
            if reserved:
                job.spare_reservations[shipment.product_id] = (
                    job.spare_reservations.get(shipment.product_id, 0) + shipment.quantity
                )
            else:
                destination.inventory[shipment.product_id] = (
                    destination.inventory.get(shipment.product_id, 0) + shipment.quantity
                )
            route = self.plan.supply_routes[shipment.route_index]
            self.total_transport_delay += shipment.arrival_minute - shipment.requested_minute
            details = {
                "job_id": shipment.job_id,
                "step_index": shipment.step_index,
                "product_id": shipment.product_id,
                "quantity": shipment.quantity,
                "source_node_index": shipment.source_node_index,
                "destination_node_index": shipment.destination_node_index,
                "supply_mode": route.supply_mode,
                "relation_id": route.relation_id,
                "reserved_for_job": reserved,
                "requested_minute": shipment.requested_minute,
                "arrival_minute": shipment.arrival_minute,
            }
            self._emit(
                "transport_arrived",
                "inventory.transport-arrival",
                shipment.job_id,
                details,
                route.source_path,
            )
            self._emit(
                "organization_transport_arrived",
                "organization.transport-arrival",
                shipment.job_id,
                details,
                route.source_path,
            )

    def _dispatch_remote_spares(
        self,
        job: JobRuntimeState,
        activity: ActivitySpec,
        requirements: dict[str, int],
    ) -> None:
        destination_index = activity.resource_node_index
        destination = self.resources[destination_index]
        for product_id, needed in requirements.items():
            available = destination.inventory.get(product_id, 0) + job.spare_reservations.get(product_id, 0)
            shortage = max(0, needed - available)
            if shortage <= 0 or any(
                item.job_id == job.job_id
                and item.step_index == job.step_index
                and item.product_id == product_id
                for item in self.shipments
            ):
                continue
            for route in self.plan.supply_routes:
                if route.destination_node_index != destination_index:
                    continue
                if route.product_id and route.product_id != product_id:
                    continue
                source = self.resources[route.source_node_index]
                moved = min(
                    shortage,
                    route.capacity,
                    source.inventory.get(product_id, 0),
                )
                if moved <= 0:
                    continue
                source.inventory[product_id] -= moved
                shipment = ShipmentRuntimeState(
                    job_id=job.job_id,
                    step_index=job.step_index,
                    product_id=product_id,
                    quantity=moved,
                    source_node_index=route.source_node_index,
                    destination_node_index=destination_index,
                    requested_minute=self.minute,
                    arrival_minute=self.minute + max(1, route.transport_minutes),
                    route_index=route.index,
                )
                self.shipments.append(shipment)
                self.transport_replenishment_events += 1
                details = {
                    "job_id": job.job_id,
                    "step_index": job.step_index,
                    "product_id": product_id,
                    "quantity": moved,
                    "source_node_index": route.source_node_index,
                    "destination_node_index": destination_index,
                    "arrival_minute": shipment.arrival_minute,
                    "supply_mode": route.supply_mode,
                    "relation_id": route.relation_id,
                }
                self._emit(
                    "organization_supply_selected",
                    "organization.select-supplier",
                    job.job_id,
                    details,
                    route.source_path,
                )
                self._emit(
                    "organization_transport_dispatched",
                    "organization.dispatch-transport",
                    job.job_id,
                    details,
                    route.source_path,
                )
                break

    def _return_aircraft(self, aircraft_index: int, *, early_return: bool) -> None:
        aircraft = self.aircraft[aircraft_index]
        mission_index = aircraft.current_mission_index
        aircraft.postflight_required = True
        mission_start = (
            self.missions[mission_index].actual_start
            if mission_index is not None
            and self.missions[mission_index].actual_start is not None
            else self.plan.missions[mission_index].planned_start
            if mission_index is not None
            else self.minute
        )
        end_minute = self.minute if early_return else (aircraft.return_time or self.minute)
        flight_hours = max(0.0, (end_minute - mission_start) / 60.0)
        aircraft.flight_hours += flight_hours
        aircraft.landing_count += 1
        for cycle_index, cycle_spec in enumerate(self.plan.preventive_cycles):
            if cycle_spec.aircraft_index == aircraft_index:
                self.preventive_cycles[cycle_index].life_flight_hours += flight_hours
                self.preventive_cycles[cycle_index].life_landing_cycles += 1
        failed_on_return = bool(aircraft.in_flight_failure or aircraft.instance_failure_minutes)
        if failed_on_return:
            aircraft.state = "maintenance"
            if aircraft.in_flight_failure:
                self.failed_sorties += 1
            failure_slot = (
                (aircraft.failed_component_index, aircraft.failed_component_instance_index)
                if aircraft.failed_component_index is not None
                and aircraft.failed_component_instance_index is not None
                else min(
                    aircraft.instance_failure_minutes,
                    key=lambda slot: (
                        aircraft.instance_failure_minutes[slot],
                        slot[0],
                        slot[1],
                    ),
                )
            )
            component_index, instance_index = failure_slot
            component = self.plan.components[component_index]
            if component.repair_activity_index < 0:
                raise UnsupportedPlanError(
                    f"no repair activity for component {component.component_id!r}"
                )
            self._create_job(
                aircraft_index,
                self.plan.activities[component.repair_activity_index],
                kind="repair",
                mission_index=mission_index,
                component_index=component_index,
                component_instance_index=instance_index,
            )
            if mission_index is not None and aircraft.in_flight_failure:
                state = self.missions[mission_index]
                if aircraft_index not in state.failed_aircraft:
                    state.failed_aircraft.append(aircraft_index)
                if len(set(state.assigned_aircraft) - set(state.failed_aircraft)) < self.plan.missions[mission_index].min_required_aircraft:
                    state.status = "failed"
                    state.return_time = self.minute
            self._emit(
                "mission_failed_returned" if early_return else "mission_returned_with_component_failure",
                "failure.return-and-create-repair",
                aircraft.tail_number,
                {
                    "mission_id": self._mission_id(mission_index),
                    "component_id": component.component_id,
                    "instance_index": instance_index,
                },
            )
        else:
            self.completed_sorties += 1
            aircraft.state = "available"
        aircraft.current_mission_index = None
        aircraft.return_time = None
        if mission_index is not None:
            mission_state = self.missions[mission_index]
            active = any(
                item.state == "flying" and item.current_mission_index == mission_index
                for item in self.aircraft
            )
            if mission_state.status == "launched" and not active:
                mission_state.status = "completed"
        if not failed_on_return:
            self._emit(
                "mission_returned",
                "mission.normal-return",
                aircraft.tail_number,
                {"mission_id": self._mission_id(mission_index)},
            )

    def _release_resources(self, job: JobRuntimeState, step: WorkStepSpec) -> None:
        activity = self.plan.activities[job.activity_index]
        resource = self.resources[activity.resource_node_index]
        resource.personnel_in_use -= job.reserved_personnel
        resource.equipment_in_use -= job.reserved_equipment
        if resource.personnel_in_use < 0 or resource.equipment_in_use < 0:
            raise RuntimeError("resource ledger became negative")
        self._emit(
            "resources_released",
            "resource.release",
            job.job_id,
            {
                "node_index": activity.resource_node_index,
                "step_index": step.index,
                "personnel": job.reserved_personnel,
                "equipment": job.reserved_equipment,
                "personnel_in_use": resource.personnel_in_use,
                "equipment_in_use": resource.equipment_in_use,
            },
        )
        job.reserved_personnel = job.reserved_equipment = 0

    def _phase_job_progress(self) -> None:
        for job in self.jobs:
            if job.state != "running":
                continue
            job.remaining -= 1
            if job.remaining > 0:
                continue
            activity = self.plan.activities[job.activity_index]
            step = activity.steps[job.step_index]
            self._release_resources(job, step)
            self._emit(
                "operations_step_completed",
                "work.serial-step-complete",
                job.job_id,
                {"step_index": step.index, "activity_code": step.code},
            )
            job.step_index += 1
            if job.step_index >= len(activity.steps):
                job.state = "completed"
                job.completed_time = self.minute
                self._complete_job(job)
            else:
                job.state = "waiting"
                job.remaining = 0

    def _failure_reaches_root(self, aircraft_index: int) -> bool:
        failed = {component_index for component_index, _ in self.aircraft[aircraft_index].instance_failure_minutes}
        changed = True
        while changed:
            changed = False
            for component in reversed(self.plan.components):
                if component.index in failed or aircraft_index not in component.aircraft_indexes:
                    continue
                failed_children = sum(
                    child in failed
                    for child in self._children_by_component.get(component.index, ())
                )
                if failed_children and failed_children >= component.failure_threshold:
                    failed.add(component.index)
                    changed = True
        return any(
            component.index in failed
            and component.parent_index < 0
            and aircraft_index in component.aircraft_indexes
            for component in self.plan.components
        )

    def _phase_failures(self) -> None:
        if not self.plan.components:
            return
        for aircraft_index, aircraft in enumerate(self.aircraft):
            if aircraft.state != "flying" or aircraft.in_flight_failure:
                continue
            for failure_slot in self._failure_instance_slots[aircraft_index]:
                component_index, instance_index = failure_slot
                component = self.plan.components[component_index]
                if failure_slot in aircraft.instance_failure_minutes:
                    continue
                remaining = aircraft.failure_remaining.get(failure_slot)
                if remaining is None:
                    remaining = self._sample_instance_minutes(
                        component_index, aircraft_index, instance_index, "missing_timer"
                    )
                remaining -= 1.0
                aircraft.failure_remaining[failure_slot] = remaining
                if remaining > 0:
                    continue
                aircraft.instance_failure_minutes[failure_slot] = self.minute
                self.lru_failures += 1
                self._emit(
                    "component_failed",
                    "failure.flight-exposure-countdown",
                    aircraft.tail_number,
                    {"component_id": component.component_id, "instance_index": instance_index},
                    component.source_path,
                )
                if self._failure_reaches_root(aircraft_index):
                    aircraft.failed_component_index = component_index
                    aircraft.failed_component_instance_index = instance_index
                    aircraft.failed_component_minute = self.minute
                    aircraft.in_flight_failure = True
                    self.in_flight_failures += 1
                    self._emit(
                        "aircraft_failed",
                        "failure.tree-root-propagation",
                        aircraft.tail_number,
                        {"component_id": component.component_id, "instance_index": instance_index},
                        component.source_path,
                    )
                    self._return_aircraft(aircraft_index, early_return=True)
                    break

    def _phase_generate_preventive(self) -> None:
        active_aircraft = {
            job.aircraft_index
            for job in self.jobs
            if job.kind == "preventive" and job.state in {"waiting", "running"}
        }
        for aircraft_index, aircraft in enumerate(self.aircraft):
            if aircraft_index in active_aircraft:
                continue
            due_cycle_index = None
            due_dimensions: list[str] = []
            for cycle_index, spec in enumerate(self.plan.preventive_cycles):
                if spec.aircraft_index != aircraft_index:
                    continue
                cycle = self.preventive_cycles[cycle_index]
                dimensions = []
                if spec.calendar_days > 0 and self.minute >= cycle.last_preventive_minute + spec.calendar_days * 1440:
                    dimensions.append("calendar_days")
                if spec.flight_hours > 0 and cycle.life_flight_hours >= spec.flight_hours:
                    dimensions.append("flight_hours")
                if spec.landing_cycles > 0 and cycle.life_landing_cycles >= spec.landing_cycles:
                    dimensions.append("takeoff_landing_cycles")
                if dimensions:
                    due_cycle_index = cycle_index
                    due_dimensions = dimensions
                    break
            if due_cycle_index is None or aircraft.state != "available":
                continue
            spec = self.plan.preventive_cycles[due_cycle_index]
            aircraft.state = "maintenance"
            self.preventive_maintenance_events += 1
            self._create_job(
                aircraft_index,
                self.plan.activities[spec.activity_index],
                kind="preventive",
                mission_index=None,
                preventive_cycle_index=due_cycle_index,
            )
            self._emit(
                "preventive_created",
                "maintenance.preventive-due",
                aircraft.tail_number,
                {
                    "activity_id": self.plan.activities[spec.activity_index].activity_id,
                    "due_dimensions": due_dimensions,
                },
                spec.source_path,
            )

    def _phase_create_preflight(self) -> None:
        for mission_index, mission in enumerate(self.plan.missions):
            state = self.missions[mission_index]
            if state.status not in {"scheduled", "delayed"} or self.minute < mission.preparation_start:
                continue
            commissioned = self._commissioned_count(mission_index)
            if commissioned >= mission.required_aircraft:
                state.preflight_created = True
                continue
            active = self._active_preflight_aircraft(mission_index)
            available = [
                index
                for index, aircraft in enumerate(self.aircraft)
                if aircraft.state == "available"
                and not aircraft.postflight_due
                and self._matches_type(index, mission)
                and not aircraft.prepared_mission_indexes
                and index not in active
            ]
            created = 0
            for aircraft_index in available[: max(0, mission.required_aircraft - commissioned)]:
                aircraft = self.aircraft[aircraft_index]
                aircraft.state = "pre_support"
                aircraft.current_mission_index = mission_index
                self._create_job(
                    aircraft_index,
                    self._preparation_activity(mission_index, aircraft_index),
                    kind="preflight",
                    mission_index=mission_index,
                )
                created += 1
            state.preflight_created = self._commissioned_count(mission_index) >= mission.required_aircraft
            if created:
                self._emit(
                    "preflight_created",
                    "mission.commission-preflight",
                    mission.mission_id,
                    {"created": created},
                )

    def _phase_start_waiting_jobs(self) -> None:
        waiting = sorted(
            (job for job in self.jobs if job.state == "waiting"),
            key=lambda job: (
                self.plan.activities[job.activity_index].priority,
                job.started_time if job.started_time is not None else self.minute,
                job.job_id,
            ),
        )
        for job in waiting:
            activity = self.plan.activities[job.activity_index]
            if job.step_index >= len(activity.steps):
                job.state = "completed"
                self._complete_job(job)
                continue
            step = activity.steps[job.step_index]
            resource = self.resources[activity.resource_node_index]
            requirements = dict(step.spares)
            if job.step_index == len(activity.steps) - 1:
                for product_id, quantity in job.injected_spares:
                    requirements[product_id] = requirements.get(product_id, 0) + quantity
            if job.maintenance_method == "non_replacement" and job.kind in {"repair", "preventive"}:
                requirements = {}
            self._dispatch_remote_spares(job, activity, requirements)
            immediately_available = all(
                resource.inventory.get(product_id, 0)
                + job.spare_reservations.get(product_id, 0)
                >= quantity
                for product_id, quantity in requirements.items()
            )
            if requirements and job.step_index not in job.requested_spare_steps:
                job.requested_spare_steps.add(job.step_index)
                for product_id, quantity in requirements.items():
                    self.spare_demand_total += quantity
                    self.spare_immediately_filled_total += quantity if immediately_available else 0
                    self._emit(
                        "spare_request",
                        "inventory.request-once",
                        job.job_id,
                        {
                            "step_index": job.step_index,
                            "product_id": product_id,
                            "demand_quantity": quantity,
                            "immediately_filled_quantity": quantity if immediately_available else 0,
                            "node_index": activity.resource_node_index,
                        },
                    )
            shortages = tuple(
                (
                    product_id,
                    quantity,
                    resource.inventory.get(product_id, 0)
                    + job.spare_reservations.get(product_id, 0),
                )
                for product_id, quantity in requirements.items()
                if resource.inventory.get(product_id, 0)
                + job.spare_reservations.get(product_id, 0)
                < quantity
            )
            if shortages:
                if job.shortage_signature != shortages:
                    job.shortage_signature = shortages
                    for product_id, quantity, available in shortages:
                        self.shortage_events += 1
                        self._emit(
                            "spare_shortage",
                            "inventory.local-shortage",
                            job.job_id,
                            {
                                "step_index": job.step_index,
                                "product_id": product_id,
                                "required_quantity": quantity,
                                "available_quantity": available,
                                "node_index": activity.resource_node_index,
                            },
                        )
                continue
            job.shortage_signature = None
            if resource.personnel_in_use + step.personnel > resource.personnel_capacity:
                self._emit(
                    "personnel_delay",
                    "resource.personnel-capacity",
                    job.job_id,
                    {"step_index": step.index},
                )
                continue
            if resource.equipment_in_use + step.equipment > resource.equipment_capacity:
                self._emit(
                    "equipment_shortage",
                    "resource.equipment-capacity",
                    job.job_id,
                    {"step_index": step.index},
                )
                continue
            resource.personnel_in_use += step.personnel
            resource.equipment_in_use += step.equipment
            if requirements and job.step_index not in job.consumed_spare_steps:
                job.consumed_spare_steps.add(job.step_index)
                for product_id, quantity in requirements.items():
                    reserved = min(job.spare_reservations.get(product_id, 0), quantity)
                    if reserved:
                        remaining = job.spare_reservations[product_id] - reserved
                        if remaining:
                            job.spare_reservations[product_id] = remaining
                        else:
                            job.spare_reservations.pop(product_id, None)
                    shared = quantity - reserved
                    if shared:
                        resource.inventory[product_id] = resource.inventory.get(product_id, 0) - shared
                    self.spare_consumed_total += quantity
                    self._emit(
                        "spare_consumed",
                        "inventory.consume-at-job-start",
                        job.job_id,
                        {
                            "step_index": job.step_index,
                            "product_id": product_id,
                            "quantity": quantity,
                            "node_index": activity.resource_node_index,
                            "maintenance_method": job.maintenance_method,
                        },
                    )
            job.reserved_personnel = step.personnel
            job.reserved_equipment = step.equipment
            job.state = "running"
            job.started_time = self.minute if job.started_time is None else job.started_time
            job.remaining = step.duration_minutes
            if (
                job.kind == "repair"
                and job.component_index is not None
                and job.step_index == len(activity.steps) - 1
                and self.plan.components[job.component_index].repair_duration_minutes > 0
            ):
                job.remaining = self.plan.components[job.component_index].repair_duration_minutes
            self._emit(
                "resources_reserved",
                "resource.reserve-atomic",
                job.job_id,
                {
                    "node_index": activity.resource_node_index,
                    "step_index": step.index,
                    "personnel": step.personnel,
                    "equipment": step.equipment,
                    "personnel_in_use": resource.personnel_in_use,
                    "equipment_in_use": resource.equipment_in_use,
                },
            )
            self._emit(
                "operations_step_started",
                "work.stable-topological-serial",
                job.job_id,
                {"step_index": step.index, "activity_code": step.code},
            )

    def _phase_dispatch_missions(self) -> None:
        for mission_index, mission in enumerate(self.plan.missions):
            state = self.missions[mission_index]
            if state.status not in {"scheduled", "delayed"} or self.minute < mission.planned_start:
                continue
            candidates = [
                index
                for index in range(len(self.aircraft))
                if self._ready_for_mission(index, mission_index) and self._matches_type(index, mission)
            ]
            if len(candidates) >= mission.required_aircraft:
                assigned = candidates[: mission.required_aircraft]
                for aircraft_index in assigned:
                    aircraft = self.aircraft[aircraft_index]
                    aircraft.state = "flying"
                    aircraft.current_mission_index = mission_index
                    aircraft.prepared_mission_indexes.discard(mission_index)
                    aircraft.return_time = self.minute + mission.duration_minutes
                    day = self.minute // 1440
                    if aircraft.operations_day != day:
                        aircraft.operations_day = day
                        aircraft.daily_takeoffs = 0
                    aircraft.daily_takeoffs += 1
                    aircraft.takeoff_count += 1
                    aircraft.operations_plan_group_id = mission.operations_plan_group_id
                    aircraft.last_operations_mission_index = mission_index
                    aircraft.prepared_operations_day = None
                state.status = "launched"
                state.actual_start = self.minute
                state.return_time = self.minute + mission.duration_minutes
                state.assigned_aircraft = assigned
                state.delay_minutes = max(0, self.minute - mission.planned_start)
                self.launched_sorties += len(assigned)
                self.total_departure_delay += state.delay_minutes
                if state.delay_minutes and mission_index not in self._delayed_missions:
                    self.delayed_sorties += len(assigned)
                    self._delayed_missions.add(mission_index)
                self._emit(
                    "mission_launched",
                    "mission.dispatch-ready-aircraft",
                    mission.mission_id,
                    {"aircraft": [self.aircraft[index].tail_number for index in assigned]},
                )
            elif self.minute - mission.planned_start >= mission.cancel_minutes:
                state.status = "cancelled"
                self.cancelled_sorties += mission.required_aircraft
                self.total_departure_delay += mission.cancel_minutes
                self._cancel_mission_preflight(mission_index)
                self._emit(
                    "mission_cancelled",
                    "mission.cancel-insufficient-ready-aircraft",
                    mission.mission_id,
                )
            else:
                state.status = "delayed"
                if mission_index not in self._delayed_missions:
                    self.delayed_sorties += mission.required_aircraft
                    self._delayed_missions.add(mission_index)

    def _cancel_mission_preflight(self, mission_index: int) -> None:
        for job in self.jobs:
            if job.kind != "preflight" or job.mission_index != mission_index or job.state not in {"waiting", "running"}:
                continue
            if job.state == "running":
                activity = self.plan.activities[job.activity_index]
                self._release_resources(job, activity.steps[job.step_index])
            job.state = "cancelled"
            job.remaining = 0
        for aircraft in self.aircraft:
            if aircraft.current_mission_index == mission_index and aircraft.state in {"pre_support", "mission_ready"}:
                aircraft.state = "available"
                aircraft.current_mission_index = None
                aircraft.prepared_operations_day = None
            aircraft.prepared_mission_indexes.discard(mission_index)

    def _has_remaining_operations_mission(self, aircraft_index: int) -> bool:
        aircraft = self.aircraft[aircraft_index]
        for mission_index, mission in enumerate(self.plan.missions):
            state = self.missions[mission_index]
            if state.status not in {"scheduled", "delayed"}:
                continue
            if max(self.minute, mission.planned_start) // 1440 != aircraft.operations_day:
                continue
            if self.minute > mission.planned_start + mission.cancel_minutes:
                continue
            if not self._matches_type(aircraft_index, mission):
                continue
            if aircraft.current_mission_index == mission_index:
                return True
            if self._commissioned_count(mission_index) < mission.required_aircraft:
                return True
        return False

    def _phase_coordinate_postflight(self, *, cutoff: bool = False) -> None:
        day = self.minute // 1440
        for aircraft_index, aircraft in enumerate(self.aircraft):
            if aircraft.operations_day is None or not aircraft.daily_takeoffs:
                continue
            if (day > aircraft.operations_day or cutoff) and (
                aircraft.postflight_required or aircraft.state == "flying"
            ):
                aircraft.postflight_due = True
            if not aircraft.postflight_required:
                continue
            if not self._has_remaining_operations_mission(aircraft_index):
                aircraft.postflight_due = True
            if not aircraft.postflight_due or aircraft.state in {
                "flying",
                "maintenance",
                "preventive",
                "post_support",
            }:
                continue
            aircraft.state = "post_support"
            activity = self._activity_for(
                aircraft.operations_plan_group_id, "postflight", aircraft_index
            )
            self._create_job(
                aircraft_index,
                activity,
                kind="postflight",
                mission_index=aircraft.last_operations_mission_index,
            )

    def _phase_mission_success(self) -> None:
        for mission_index, mission in enumerate(self.plan.missions):
            state = self.missions[mission_index]
            start = state.actual_start if state.actual_start is not None else mission.planned_start
            success_minute = start + math.ceil(mission.duration_minutes * mission.success_point)
            if state.success_evaluated or success_minute > self.minute:
                continue
            state.success_member_count = len(
                set(state.assigned_aircraft) - set(state.failed_aircraft)
            )
            state.success_at_minute = self.minute
            state.success_evaluated = True
            state.succeeded = state.success_member_count >= mission.min_required_aircraft
            self._emit(
                "mission_success_point_succeeded" if state.succeeded else "mission_success_point_failed",
                "mission.evaluate-success-point",
                mission.mission_id,
                {"members": state.success_member_count},
            )

    def _execute_minute(self) -> None:
        handlers = {
            "transport_arrivals": self._phase_transport_arrivals,
            "mission_returns": self._phase_mission_returns,
            "job_progress_and_completions": self._phase_job_progress,
            "failures": self._phase_failures,
            "operations_postflight_before_preparation": self._phase_coordinate_postflight,
            "preventive_generation": self._phase_generate_preventive,
            "preflight_generation": self._phase_create_preflight,
            "resource_dispatch": self._phase_start_waiting_jobs,
            "mission_dispatch": self._phase_dispatch_missions,
            "operations_postflight_after_dispatch": self._phase_coordinate_postflight,
            "mission_success": self._phase_mission_success,
            "daily_readiness": lambda: None,
            "operational_availability": lambda: None,
            "downtime": lambda: None,
            "stop": self._phase_stop,
        }
        for phase in self.plan.phases:
            self.phase = phase
            handlers[phase]()

    def _phase_stop(self) -> None:
        if self.minute >= self.plan.duration_minutes:
            self._phase_coordinate_postflight(cutoff=True)
            self.stop_reason = "duration"
            self.running = False
            self._emit("simulation_stopped", "stop.duration", "simulation")
        elif self.plan.natural_completion_enabled and self._natural_completion_reached():
            self.stop_reason = "natural_complete"
            self.running = False
            self._emit("simulation_stopped", "stop.natural-complete", "simulation")

    def _natural_completion_reached(self) -> bool:
        if not self.plan.missions:
            return self.minute >= self.plan.duration_minutes
        if any(
            mission.status not in {"completed", "failed", "cancelled"}
            for mission in self.missions
        ):
            return False
        if any(job.state in {"waiting", "running"} for job in self.jobs):
            return False
        if self.shipments:
            return False
        if any(
            aircraft.state in {"flying", "mission_ready", "pre_support", "post_support"}
            or aircraft.postflight_required
            for aircraft in self.aircraft
        ):
            return False
        return self.minute >= max(mission.planned_start for mission in self.plan.missions)

    def _clock(self, until: int):
        while self.running and self.minute < until:
            yield self.env.timeout(1)
            self.minute = int(self.env.now)
            self._execute_minute()

    def run(self, until: float | None = None) -> dict[str, Any]:
        horizon = self.plan.duration_minutes if until is None else min(int(until), self.plan.duration_minutes)
        self.env.run(until=self.env.process(self._clock(horizon)))
        if horizon < self.plan.duration_minutes and self.running:
            self.stop_reason = "requested_until"
        return {
            "plan_fingerprint": self.plan.fingerprint,
            "seed": self.seed,
            "time": self.minute,
            "stop_reason": self.stop_reason,
            "sample_requests": list(self.sample_requests),
            "trace": list(self.trace),
            "metrics": self._metrics(),
            "terminal_state": self._terminal_state(),
        }

    def _metrics(self) -> dict[str, Any]:
        executable = [
            index for index, mission in enumerate(self.plan.missions) if mission.planned_start <= self.minute
        ]
        planned_sorties = sum(self.plan.missions[index].required_aircraft for index in executable)
        successful = sum(self.missions[index].succeeded for index in executable)
        return {
            "planned_sorties": planned_sorties,
            "planned_mission_waves": len(executable),
            "successful_mission_waves": successful,
            "mission_success_rate": successful / max(1, len(executable)),
            "launched_sorties": self.launched_sorties,
            "completed_sorties": self.completed_sorties,
            "cancelled_sorties": self.cancelled_sorties,
            "delayed_sorties": self.delayed_sorties,
            "postflight_count": sum(item.postflight_required for item in self.aircraft),
            "avg_departure_delay": self.total_departure_delay
            / max(1, self.launched_sorties + self.cancelled_sorties),
            "elapsed_minutes": self.minute,
            "stop_reason": self.stop_reason,
            "lru_failures": self.lru_failures,
            "in_flight_failures": self.in_flight_failures,
            "failed_sorties": self.failed_sorties,
            "preventive_maintenance_events": self.preventive_maintenance_events,
            "failed_count": sum(bool(item.instance_failure_minutes) for item in self.aircraft),
            "repairing_count": sum(
                any(
                    job.aircraft_index == index
                    and job.kind == "repair"
                    and job.state in {"waiting", "running"}
                    for job in self.jobs
                )
                for index in range(len(self.aircraft))
            ),
            "spare_stock_total": sum(
                sum(resource.inventory.values()) for resource in self.resources
            ),
            "spare_demand_total": self.spare_demand_total,
            "spare_immediately_filled_total": self.spare_immediately_filled_total,
            "spare_fill_rate": (
                1.0
                if self.spare_demand_total == 0
                else self.spare_immediately_filled_total / self.spare_demand_total
            ),
            "spare_consumed_total": self.spare_consumed_total,
            "shortage_events": self.shortage_events,
            "transport_in_transit_count": len(self.shipments),
            "transport_replenishment_events": self.transport_replenishment_events,
            "total_transport_delay_minutes": self.total_transport_delay,
            "mean_transport_delay": self.total_transport_delay
            / (60 * max(1, self.transport_replenishment_events)),
        }

    def _component_failure_view(self, aircraft: AircraftRuntimeState) -> dict[str, int]:
        # Legacy terminal-state shape: per component the earliest failed instance minute.
        result: dict[str, int] = {}
        for (component_index, _instance), minute in aircraft.instance_failure_minutes.items():
            component_id = self.plan.components[component_index].component_id
            if component_id not in result or minute < result[component_id]:
                result[component_id] = minute
        return result

    def _terminal_state(self) -> dict[str, Any]:
        return {
            "aircraft": [
                {
                    "tail_number": item.tail_number,
                    "state": item.state,
                    "current_mission_id": self._mission_id(item.current_mission_index),
                    "prepared_mission_ids": sorted(
                        self._mission_id(index) for index in item.prepared_mission_indexes
                    ),
                    "operations_day": item.operations_day,
                    "daily_takeoffs": item.daily_takeoffs,
                    "postflight_required": item.postflight_required,
                    "postflight_due": item.postflight_due,
                    "flight_hours": item.flight_hours,
                    "takeoff_count": item.takeoff_count,
                    "landing_count": item.landing_count,
                    "failed_component_id": self.plan.components[item.failed_component_index].component_id
                    if item.failed_component_index is not None
                    else None,
                    "component_failure_minutes": self._component_failure_view(item),
                    "in_flight_failure": item.in_flight_failure,
                }
                for item in self.aircraft
            ],
            "missions": [
                {
                    "mission_id": self.plan.missions[index].mission_id,
                    "status": item.status,
                    "actual_start": item.actual_start,
                    "assigned_tail_numbers": [
                        self.aircraft[aircraft_index].tail_number
                        for aircraft_index in item.assigned_aircraft
                    ],
                    "success_evaluated": item.success_evaluated,
                    "succeeded": item.succeeded,
                }
                for index, item in enumerate(self.missions)
            ],
            "jobs": [
                {
                    "job_id": item.job_id,
                    "kind": item.kind,
                    "aircraft": self.aircraft[item.aircraft_index].tail_number,
                    "mission_id": self._mission_id(item.mission_index),
                    "activity_id": self.plan.activities[item.activity_index].activity_id,
                    "state": item.state,
                    "step_index": item.step_index,
                    "started_time": item.started_time,
                    "completed_time": item.completed_time,
                    "component_id": self.plan.components[item.component_index].component_id
                    if item.component_index is not None
                    else None,
                    "maintenance_method": item.maintenance_method,
                }
                for item in self.jobs
            ],
            "resources": [
                {
                    "node_id": self.plan.resource_nodes[index].node_id,
                    "personnel_in_use": item.personnel_in_use,
                    "equipment_in_use": item.equipment_in_use,
                    "inventory": dict(sorted(item.inventory.items())),
                }
                for index, item in enumerate(self.resources)
            ],
        }


def _tokens(value: Any) -> set[str]:
    text = str(value or "").strip().casefold()
    if not text:
        return set()
    return {text, "".join(char for char in text if char.isalnum())}
