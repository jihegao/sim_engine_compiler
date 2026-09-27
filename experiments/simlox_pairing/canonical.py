"""Minimal self-authored canonical inputs for the SIMLOX A01/A02 pairing.

These inputs exercise the existing ``spare_mvp`` canonical import boundary.
They are not translations of Project JSON and do not consume the native
expected-observation files when producing engine results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim_engine_compiler.compiler.layout import compile_core, lineage
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime

HANDOFF_COMMIT = "519b2094c3be355399bc101cdcfe30d456cbb47b"
UPSTREAM_ADAPTER_REVISION = "5352a0d7757cbac012c75d516d1a7ac4ff15aa2a"
UPSTREAM_INPUT_SCHEMA_SHA256 = (
    "bd8d6acca8e4fb678bf0b536d257fae41811f44e3c841b13cabdc32c2fe3f694"
)
NATIVE_INPUT_SHA256 = {
    "A01": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
    "A02": "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8",
}
_STARTS = {"A01": (8,), "A02": (8, 20, 32)}


@dataclass(frozen=True)
class CaseArtifacts:
    """The independently produced artifacts for one pairing case."""

    case_id: str
    canonical: dict[str, Any]
    business: BusinessIR
    core: CoreIR
    plan: ExecutionPlan
    lineage: dict[str, Any]
    result: dict[str, Any]
    source_mapping: dict[str, Any]


def _case_id(value: str) -> str:
    case_id = str(value).upper()
    if case_id not in _STARTS:
        raise ValueError(
            f"unsupported SIMLOX pairing case {value!r}; expected A01 or A02"
        )
    return case_id


def build_canonical(case_id: str) -> dict[str, Any]:
    """Build an explicit canonical input without consulting native results."""

    case_id = _case_id(case_id)
    task_items = [
        {
            "id": f"{case_id.lower()}-mission-{index + 1:02d}",
            "basicMissionId": "teach-basic-mission",
            "basicTaskName": "TEACH-UNIT",
            "firstWaveTime": f"{hour:02d}:00",
            "dailyRepeatCount": 1,
            "equipmentType": "TEACH-AIR",
            "operations_plan_group_id": "teach-daily",
        }
        for index, hour in enumerate(_STARTS[case_id])
    ]
    return {
        "schema_version": "aircraft-support-v1-input-v1",
        "operations_support_policy": "daily-v1",
        "project_identity": {
            "project_id": f"simlox-{case_id.lower()}-pairing-teaching-input",
            "project_version": "1",
            "scenario_id": case_id,
            "source_import_id": "self-authored-pairing-input",
        },
        "mission_profile": {
            "profile_id": f"simlox-{case_id.lower()}-pairing",
            "name": f"SIMLOX {case_id} bounded pairing",
            "duration_minutes": 2160,
            "basic_missions": [
                {
                    "id": "teach-basic-mission",
                    "missionId": "teach-basic-mission",
                    "name": "TEACH-UNIT",
                    "advanceNoticeMinutes": 60,
                    "cancelMinutes": 20,
                    "equipmentQuantity": 1,
                    "equipmentType": "TEACH-AIR",
                    "minRequiredSorties": 1,
                    "successPoint": 1.0,
                    "taskDurationMinutes": 120,
                }
            ],
            "composite_tasks": [
                {
                    "id": f"{case_id.lower()}-teaching-missions",
                    "name": f"{case_id} teaching missions",
                    "priority": 1,
                    "taskItems": task_items,
                }
            ],
            "mission_calendar": [
                {
                    "day_index": 1,
                    "composite_task_id": f"{case_id.lower()}-teaching-missions",
                }
            ],
            "periodic_source": {
                "level": "week",
                "label": "周剖面",
                "configured_slots": len(task_items),
            },
            "mission_phases": [],
            "airports": [],
        },
        "aircraft": {
            "fleet_count": 1,
            "initial_ready": 1,
            "models": ["TEACH-AIR"],
            "assets": [
                {
                    "tail_number": "TEACH-AIR-01",
                    "aircraft_type": "TEACH-AIR",
                    "model": "TEACH-AIR",
                    "initial_state": "available",
                    "source_initial_state": "available",
                    "initial_life_state": {
                        "calendar_days": 0,
                        "flight_hours": 0.0,
                        "takeoff_landing_cycles": 0,
                    },
                    "source_initial_life_state": {
                        "calendar_days": 0,
                        "flight_hours": 0.0,
                        "takeoff_landing_cycles": 0,
                    },
                    "preventive_thresholds": {
                        "calendar_days": 0,
                        "flight_hours": 0.0,
                        "takeoff_landing_cycles": 0,
                    },
                    "preventive_threshold_sources": {
                        "calendar_days": [],
                        "flight_hours": [],
                        "takeoff_landing_cycles": [],
                    },
                    "preventive_cycles": [],
                    "initial_due_dimensions": [],
                    "initial_preventive_due": False,
                }
            ],
        },
        "equipment_tree": {
            "root_component_id": "teach-air",
            "components": [
                {
                    "id": "teach-air",
                    "name": "TEACH-AIR",
                    "parent_id": "",
                    "aircraft_model": "TEACH-AIR",
                    "quantity": 1,
                    "failure_rate": 0.0,
                }
            ],
        },
        "support_network": {
            "nodes": [
                {
                    "id": "teach-flight-line",
                    "name": "Teaching flight line",
                    "organization_node_id": "teach-flight-line",
                    "personnel_capacity": 1,
                    "equipment_capacity": 1,
                    "inventory": {},
                    "transport_policies": [],
                }
            ],
            "organization_graph": {
                "runtime_mode": "legacy",
                "nodes": [],
                "parent_edges": [],
                "lateral_edges": [],
                "resource_ownership": [],
                "transport_policies": [],
            },
        },
        "support_activities": {
            "activities": [
                {
                    "id": "teach-daily-preflight",
                    "name": "Notice binding bookkeeping",
                    "activity_type": "operations",
                    "operations_phase": "preflight",
                    "plan_group_id": "teach-daily",
                    "aircraft_model": "TEACH-AIR",
                    "resource_id": "teach-flight-line",
                    "equipment_id": "teach-air",
                    "priority": 1,
                    "jobs": [],
                },
                {
                    "id": "teach-daily-relaunch",
                    "name": "Notice relaunch binding bookkeeping",
                    "activity_type": "operations",
                    "operations_phase": "relaunch",
                    "plan_group_id": "teach-daily",
                    "aircraft_model": "TEACH-AIR",
                    "resource_id": "teach-flight-line",
                    "equipment_id": "teach-air",
                    "priority": 1,
                    "jobs": [],
                },
                {
                    "id": "teach-daily-postflight",
                    "name": "Terminal postflight",
                    "activity_type": "operations",
                    "operations_phase": "postflight",
                    "plan_group_id": "teach-daily",
                    "aircraft_model": "TEACH-AIR",
                    "resource_id": "teach-flight-line",
                    "equipment_id": "teach-air",
                    "priority": 1,
                    "jobs": [],
                },
            ]
        },
        "time": {
            "duration_minutes": 2160,
            "tick_minutes": 1,
            "sample_every_minutes": 30,
            "max_state_frames_single": 2160,
            "requested_steps": 2160,
        },
        "monte_carlo": {
            "sample_count": 1,
            "sweep": {
                "failureRates": [],
                "spareMultipliers": [],
                "supportCapacities": [],
            },
        },
        "seed": 0,
        "stop_policy": {
            "schema_version": "stop-policy-v0",
            "mode": "or",
            "conditions": [{"type": "duration", "duration_minutes": 2160}],
            "defaulted": False,
        },
    }


def compile_case(case_id: str) -> CaseArtifacts:
    """Compile all three IR layers and execute the independent Python Plan."""

    case_id = _case_id(case_id)
    canonical = build_canonical(case_id)
    business = import_business_ir(canonical)
    core = lower_business(business)
    plan = compile_core(core)
    result = SimpyReferenceRuntime(plan, seed=0).run()
    mission_mapping = [
        {
            "native_mission_instance": f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>",
            "canonical_task_item_id": f"{case_id.lower()}-mission-{index + 1:02d}",
            "engine_mission_id": mission.mission_id,
            "source_path": mission.source_path,
        }
        for index, mission in enumerate(plan.missions)
    ]
    source_mapping = {
        "source_contract": {
            "upstream_revision": UPSTREAM_ADAPTER_REVISION,
            "canonical_schema": "contracts/aircraft_support_v1_input.schema.json",
            "canonical_schema_sha256": UPSTREAM_INPUT_SCHEMA_SHA256,
            "native_handoff_commit": HANDOFF_COMMIT,
            "native_input_sha256": NATIVE_INPUT_SHA256[case_id],
            "input_classification": "self-authored canonical teaching input",
        },
        "aircraft": {
            "native_instance": "<TEACH-AIR-01,0>",
            "canonical_tail_number": "TEACH-AIR-01",
            "engine_aircraft_index": 0,
            "source_path": "aircraft.assets[0]",
        },
        "missions": mission_mapping,
        "notice_binding": {
            "canonical_field": "mission_profile.basic_missions[0].advanceNoticeMinutes",
            "engine_fields": [
                "missions[*].preparation_start",
                "aircraft.state=mission_ready",
                "aircraft.prepared_mission_indexes",
            ],
            "semantic_scope": (
                "zero-work daily-v1 mission binding; not modeled preparation work; "
                "not inventory spare reservation"
            ),
        },
        "event_mapping": [
            {
                "native_concept": "notification",
                "engine_observation": "preflight_created",
                "time_field": "missions[*].preparation_start",
                "not_independent_event": True,
            },
            {
                "native_concept": "allocation",
                "engine_observation": "aircraft.current_mission_id",
                "time_field": "missions[*].preparation_start",
            },
            {
                "native_concept": "ready_for_assigned_mission",
                "engine_observation": "aircraft.state=mission_ready",
                "time_field": "missions[*].preparation_start",
            },
            {
                "native_concept": "start",
                "engine_observation": "mission_launched",
                "time_field": "missions[*].planned_start",
            },
            {
                "native_concept": "completion",
                "engine_observation": "mission_returned",
                "time_field": "missions[*].planned_start + duration_minutes",
            },
        ],
        "native_only_boundaries": [
            "inner task interval 8.5h-9.5h",
            "zero-time native preparation log records",
        ],
    }
    return CaseArtifacts(
        case_id=case_id,
        canonical=canonical,
        business=business,
        core=core,
        plan=plan,
        lineage=lineage(business, core, plan),
        result=result,
        source_mapping=source_mapping,
    )
