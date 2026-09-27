"""Trace-derived observations for the bounded SIMLOX A01/A02 pairing slice.

The functions in this module never use native expected schedules to construct an
engine observation.  State intervals are reconstructed from a full reference
runtime trace and the immutable Execution Plan that produced it.  Native
expectations enter only through :func:`compare_observations`.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

from sim_engine_compiler.ir.plan import LEGACY_MINUTE_PHASES, ExecutionPlan

SCHEMA = "simlox-a01-a02-engine-observations/v1"
COMPARISON_SCHEMA = "simlox-a01-a02-observation-comparison/v1"
PROFILE_FIELDS = ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")
PAIRING_TRACE_KINDS = frozenset(
    {
        "operations_phase_created",
        "operations_phase_completed",
        "preflight_completed",
        "preflight_created",
        "mission_launched",
        "mission_returned",
        "postflight_completed",
        "mission_success_point_succeeded",
        "simulation_stopped",
    }
)


class ObservationError(ValueError):
    """A fail-closed observation extraction error with a stable code and path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(f"{code} at {path}: {message}")
        self.code = code
        self.path = path
        self.message = message


def _reject(code: str, path: str, message: str) -> None:
    raise ObservationError(code, path, message)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_exact_identity_map(
    *,
    supplied: Mapping[str, str],
    expected_keys: set[str],
    path: str,
) -> dict[str, str]:
    result = dict(supplied)
    if set(result) != expected_keys:
        _reject(
            "identity_domain_mismatch",
            path,
            f"expected engine identities {sorted(expected_keys)!r}, got {sorted(result)!r}",
        )
    if any(not isinstance(value, str) or not value for value in result.values()):
        _reject("invalid_identity", path, "mapped identities must be non-empty strings")
    if len(set(result.values())) != len(result):
        _reject("identity_not_one_to_one", path, "mapped identities must be unique")
    return result


def _validate_pairing_plan(plan: ExecutionPlan, horizon_minutes: int) -> None:
    if plan.domain != "aircraft-support":
        _reject("unsupported_domain", "plan.domain", repr(plan.domain))
    profiles = {
        "semantic_profile": (plan.semantic_profile, "legacy-minute-v1"),
        "work_policy": (plan.work_policy, "stable-topological-serial"),
        "rng_profile": (plan.rng_profile, "legacy-sequential-v1"),
    }
    for field, (actual, supported) in profiles.items():
        if actual != supported:
            _reject(
                "unsupported_pairing_profile",
                f"plan.{field}",
                f"expected {supported!r}, got {actual!r}",
            )
    if plan.phases != LEGACY_MINUTE_PHASES:
        _reject(
            "unsupported_pairing_phases",
            "plan.phases",
            "the A01/A02 observation contract is bound to LEGACY_MINUTE_PHASES",
        )
    if plan.duration_minutes != horizon_minutes:
        _reject(
            "horizon_mismatch",
            "plan.duration_minutes",
            f"expected {horizon_minutes}, got {plan.duration_minutes}",
        )
    if plan.natural_completion_enabled:
        _reject(
            "unsupported_stop_policy",
            "plan.natural_completion_enabled",
            "the pairing requires an explicit full 36-hour duration run",
        )
    if len(plan.aircraft) != 1:
        _reject(
            "unsupported_fleet_size",
            "plan.aircraft",
            "A01/A02 identity and total metrics require exactly one aircraft",
        )
    if plan.aircraft[0].initial_state != "available":
        _reject(
            "unsupported_initial_state",
            "plan.aircraft[0].initial_state",
            "the pairing baseline requires available",
        )
    if any(mission.required_aircraft != 1 for mission in plan.missions):
        _reject(
            "unsupported_wave_size",
            "plan.missions",
            "A01/A02 require exactly one aircraft per wave",
        )
    pairing_phases = {"preflight", "relaunch", "postflight"}
    activities = [item for item in plan.activities if item.phase in pairing_phases]
    found_phases = {item.phase for item in activities}
    if (
        len(plan.activities) != 3
        or len(activities) != 3
        or found_phases != pairing_phases
    ):
        _reject(
            "missing_pairing_activity",
            "plan.activities",
            f"expected exactly one activity for each of {sorted(pairing_phases)!r}",
        )
    if any(item.steps for item in activities):
        _reject(
            "unsupported_support_work",
            "plan.activities",
            "preflight, relaunch, and postflight must contain zero work steps",
        )
    if plan.preventive_cycles or plan.supply_routes:
        _reject(
            "unsupported_mechanism",
            "plan",
            "preventive maintenance and supply routes are outside A01/A02",
        )
    if any(component.failure_rate_per_hour for component in plan.components):
        _reject(
            "unsupported_mechanism",
            "plan.components",
            "failure behavior is outside A01/A02",
        )


def _validated_trace(result: Mapping[str, Any], horizon_minutes: int) -> list[dict[str, Any]]:
    if result.get("time") != horizon_minutes:
        _reject(
            "incomplete_run",
            "result.time",
            f"expected full horizon {horizon_minutes}, got {result.get('time')!r}",
        )
    if result.get("stop_reason") != "duration":
        _reject(
            "unexpected_stop_reason",
            "result.stop_reason",
            f"expected 'duration', got {result.get('stop_reason')!r}",
        )
    trace = result.get("trace")
    if not isinstance(trace, list) or not trace:
        _reject("missing_full_trace", "result.trace", "full trace is required")
    validated: list[dict[str, Any]] = []
    last_sequence = 0
    last_time = -1
    for index, raw in enumerate(trace):
        path = f"result.trace[{index}]"
        if not isinstance(raw, Mapping):
            _reject("invalid_trace_event", path, "expected object")
        event = dict(raw)
        sequence = event.get("sequence")
        minute = event.get("time")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            _reject("invalid_trace_sequence", f"{path}.sequence", repr(sequence))
        if sequence != last_sequence + 1:
            _reject(
                "noncontiguous_trace",
                f"{path}.sequence",
                f"expected {last_sequence + 1}, got {sequence}",
            )
        if not isinstance(minute, int) or isinstance(minute, bool):
            _reject("invalid_trace_time", f"{path}.time", repr(minute))
        if minute < last_time or not 0 <= minute <= horizon_minutes:
            _reject(
                "invalid_trace_order",
                f"{path}.time",
                f"time {minute} follows {last_time} or exceeds the horizon",
            )
        last_sequence = sequence
        last_time = minute
        validated.append(event)
    stop = validated[-1]
    if stop.get("kind") != "simulation_stopped" or stop.get("time") != horizon_minutes:
        _reject(
            "missing_duration_stop_event",
            "result.trace[-1]",
            "the final trace event must be simulation_stopped at the horizon",
        )
    return validated


def _event_record(
    *,
    kind: str,
    time: int,
    mission: str | None,
    aircraft: str | None,
    evidence: Mapping[str, Any] | None,
    evidence_kind: str = "runtime_trace",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "time_minutes": time,
        "mission_instance": mission,
        "aircraft_instance": aircraft,
        "evidence": {
            "kind": evidence_kind,
            "sequence": None if evidence is None else evidence.get("sequence"),
            "trace_kind": None if evidence is None else evidence.get("kind"),
            "rule_id": None if evidence is None else evidence.get("rule_id"),
            "source_path": None if evidence is None else evidence.get("source_path"),
        },
    }


def extract_engine_observations(
    plan: ExecutionPlan,
    result: Mapping[str, Any],
    *,
    case_id: str,
    aircraft_identity: Mapping[str, str],
    mission_identity: Mapping[str, str],
    interval_minutes: int = 30,
    horizon_minutes: int = 2160,
) -> dict[str, Any]:
    """Extract A01/A02 profiles from an actual full engine result.

    ``mission_ready`` is deliberately represented as ``reserved``: it is ready
    for its assigned engine mission but is not the native globally-free/ready
    state.  The initial ready observation comes from the Plan's explicit
    initial state, not from a synthetic trace event.
    """

    if not isinstance(case_id, str) or not case_id:
        _reject("invalid_case_id", "case_id", repr(case_id))
    if not isinstance(interval_minutes, int) or interval_minutes <= 0:
        _reject("invalid_interval", "interval_minutes", repr(interval_minutes))
    if horizon_minutes <= 0 or horizon_minutes % interval_minutes:
        _reject(
            "invalid_horizon",
            "horizon_minutes",
            "must be positive and exactly divisible by interval_minutes",
        )
    _validate_pairing_plan(plan, horizon_minutes)
    if result.get("plan_fingerprint") != plan.fingerprint:
        _reject(
            "result_plan_mismatch",
            "result.plan_fingerprint",
            f"expected {plan.fingerprint}, got {result.get('plan_fingerprint')!r}",
        )
    aircraft_map = _require_exact_identity_map(
        supplied=aircraft_identity,
        expected_keys={item.tail_number for item in plan.aircraft},
        path="aircraft_identity",
    )
    mission_map = _require_exact_identity_map(
        supplied=mission_identity,
        expected_keys={item.mission_id for item in plan.missions},
        path="mission_identity",
    )
    trace = _validated_trace(result, horizon_minutes)

    engine_tail = plan.aircraft[0].tail_number
    native_aircraft = aircraft_map[engine_tail]
    lifecycle = {mission.mission_id: "scheduled" for mission in plan.missions}
    state = "ready"
    active_mission: str | None = None
    transitions: list[tuple[int, int, str]] = [(0, 0, state)]
    mapped_events = [
        _event_record(
            kind="ready_increased",
            time=0,
            mission=None,
            aircraft=native_aircraft,
            evidence=None,
            evidence_kind="plan_initial_state",
        )
    ]
    allocations: dict[str, dict[str, Any]] = {}
    notices: dict[str, dict[str, Any]] = {}
    launches: dict[str, dict[str, Any]] = {}
    returns: dict[str, dict[str, Any]] = {}
    successes: dict[str, dict[str, Any]] = {}

    def transition(event: Mapping[str, Any], new_state: str) -> None:
        nonlocal state
        state = new_state
        transitions.append((int(event["time"]), int(event["sequence"]), new_state))

    for event in trace:
        kind = event.get("kind")
        if kind not in PAIRING_TRACE_KINDS:
            _reject(
                "unsupported_pairing_trace_event",
                f"result.trace[{event['sequence'] - 1}].kind",
                repr(kind),
            )
        details = event.get("details")
        if not isinstance(details, Mapping):
            details = {}
        minute = int(event["time"])
        if kind == "operations_phase_created" and details.get("operations_phase") in {
            "preflight",
            "relaunch",
        }:
            mission_id = details.get("mission_id")
            tail = details.get("tail_number")
            if mission_id not in lifecycle or tail != engine_tail:
                _reject(
                    "unmapped_allocation_identity",
                    f"result.trace[{event['sequence'] - 1}]",
                    f"mission={mission_id!r}, tail={tail!r}",
                )
            if mission_id in allocations or lifecycle[mission_id] != "scheduled" or state != "ready":
                _reject(
                    "invalid_allocation_transition",
                    f"result.trace[{event['sequence'] - 1}]",
                    f"mission={mission_id!r}, lifecycle={lifecycle[mission_id]!r}, state={state!r}",
                )
            lifecycle[mission_id] = "reserved"
            active_mission = mission_id
            allocations[mission_id] = event
            transition(event, "reserved")
            native_mission = mission_map[mission_id]
            mapped_events.extend(
                (
                    _event_record(
                        kind="allocation",
                        time=minute,
                        mission=native_mission,
                        aircraft=native_aircraft,
                        evidence=event,
                    ),
                    _event_record(
                        kind="ready_decreased",
                        time=minute,
                        mission=native_mission,
                        aircraft=native_aircraft,
                        evidence=event,
                    ),
                )
            )
        elif kind == "preflight_created":
            mission_id = event.get("entity")
            if mission_id not in lifecycle or mission_id in notices:
                _reject(
                    "invalid_notice_identity",
                    f"result.trace[{event['sequence'] - 1}]",
                    repr(mission_id),
                )
            allocation = allocations.get(str(mission_id))
            if allocation is None or allocation["time"] != minute:
                _reject(
                    "notice_without_allocation",
                    f"result.trace[{event['sequence'] - 1}]",
                    "notice evidence must be paired to a same-minute allocation",
                )
            notices[str(mission_id)] = event
            mapped_events.append(
                _event_record(
                    kind="notification",
                    time=minute,
                    mission=mission_map[str(mission_id)],
                    aircraft=native_aircraft,
                    evidence=event,
                    evidence_kind="runtime_trace_time_proxy",
                )
            )
        elif kind == "mission_launched":
            mission_id = event.get("entity")
            assigned = details.get("aircraft")
            if (
                mission_id not in lifecycle
                or lifecycle[str(mission_id)] != "reserved"
                or active_mission != mission_id
                or assigned != [engine_tail]
                or mission_id in launches
            ):
                _reject(
                    "invalid_launch_transition",
                    f"result.trace[{event['sequence'] - 1}]",
                    f"mission={mission_id!r}, assigned={assigned!r}, state={state!r}",
                )
            lifecycle[str(mission_id)] = "flying"
            launches[str(mission_id)] = event
            transition(event, "flying")
            mapped_events.append(
                _event_record(
                    kind="start",
                    time=minute,
                    mission=mission_map[str(mission_id)],
                    aircraft=native_aircraft,
                    evidence=event,
                )
            )
        elif kind == "mission_success_point_succeeded":
            mission_id = event.get("entity")
            if mission_id not in lifecycle or mission_id in successes:
                _reject(
                    "invalid_success_identity",
                    f"result.trace[{event['sequence'] - 1}]",
                    repr(mission_id),
                )
            successes[str(mission_id)] = event
            mapped_events.append(
                _event_record(
                    kind="success",
                    time=minute,
                    mission=mission_map[str(mission_id)],
                    aircraft=native_aircraft,
                    evidence=event,
                )
            )
        elif kind == "mission_returned":
            mission_id = details.get("mission_id")
            tail = event.get("entity")
            if (
                mission_id not in lifecycle
                or lifecycle[str(mission_id)] != "flying"
                or active_mission != mission_id
                or tail != engine_tail
                or mission_id in returns
            ):
                _reject(
                    "invalid_return_transition",
                    f"result.trace[{event['sequence'] - 1}]",
                    f"mission={mission_id!r}, tail={tail!r}, state={state!r}",
                )
            lifecycle[str(mission_id)] = "completed"
            returns[str(mission_id)] = event
            native_mission = mission_map[str(mission_id)]
            mapped_events.extend(
                (
                    _event_record(
                        kind="completion",
                        time=minute,
                        mission=native_mission,
                        aircraft=native_aircraft,
                        evidence=event,
                    ),
                    _event_record(
                        kind="ready_increased",
                        time=minute,
                        mission=native_mission,
                        aircraft=native_aircraft,
                        evidence=event,
                    ),
                )
            )
            transition(event, "ready")
            active_mission = None
        elif kind == "mission_cancelled":
            mission_id = event.get("entity")
            if mission_id not in lifecycle or lifecycle[str(mission_id)] not in {
                "scheduled",
                "reserved",
            }:
                _reject(
                    "invalid_cancel_transition",
                    f"result.trace[{event['sequence'] - 1}]",
                    repr(mission_id),
                )
            lifecycle[str(mission_id)] = "cancelled"
            if active_mission == mission_id:
                transition(event, "ready")
                active_mission = None
    missing = {
        mission_id: {
            "allocation": mission_id in allocations,
            "notice": mission_id in notices,
            "launch": mission_id in launches,
            "return": mission_id in returns,
            "success": mission_id in successes,
        }
        for mission_id in lifecycle
        if not all(
            (
                mission_id in allocations,
                mission_id in notices,
                mission_id in launches,
                mission_id in returns,
                mission_id in successes,
            )
        )
    }
    if missing:
        _reject("incomplete_mission_evidence", "result.trace", repr(missing))

    terminal = result.get("terminal_state")
    if not isinstance(terminal, Mapping):
        _reject("missing_terminal_state", "result.terminal_state", "expected object")
    aircraft_terminal = terminal.get("aircraft")
    mission_terminal = terminal.get("missions")
    if not isinstance(aircraft_terminal, list) or not isinstance(mission_terminal, list):
        _reject("missing_terminal_state", "result.terminal_state", "aircraft and missions required")
    if len(aircraft_terminal) != 1 or aircraft_terminal[0].get("tail_number") != engine_tail:
        _reject("terminal_identity_mismatch", "result.terminal_state.aircraft", repr(aircraft_terminal))
    terminal_aircraft = aircraft_terminal[0]
    if (
        terminal_aircraft.get("state") != "available"
        or terminal_aircraft.get("current_mission_id") is not None
        or terminal_aircraft.get("prepared_mission_ids") != []
        or terminal_aircraft.get("failed_component_id") is not None
        or terminal_aircraft.get("in_flight_failure") is not False
    ):
        _reject(
            "unexpected_terminal_aircraft_state",
            "result.terminal_state.aircraft[0]",
            repr(terminal_aircraft),
        )
    if len(mission_terminal) != len(plan.missions) or not all(
        isinstance(item, Mapping) for item in mission_terminal
    ):
        _reject(
            "terminal_identity_mismatch",
            "result.terminal_state.missions",
            "expected exactly one object per Plan mission",
        )
    by_mission = {item.get("mission_id"): item for item in mission_terminal}
    if len(by_mission) != len(mission_terminal):
        _reject(
            "duplicate_terminal_mission",
            "result.terminal_state.missions",
            "mission_id values must be unique",
        )
    if set(by_mission) != set(lifecycle):
        _reject("terminal_identity_mismatch", "result.terminal_state.missions", repr(sorted(by_mission)))
    for mission_id, status in lifecycle.items():
        terminal_mission = by_mission[mission_id]
        launch = launches[mission_id]
        if (
            status != "completed"
            or terminal_mission.get("status") != status
            or terminal_mission.get("actual_start") != launch["time"]
            or terminal_mission.get("assigned_tail_numbers") != [engine_tail]
            or terminal_mission.get("success_evaluated") is not True
            or terminal_mission.get("succeeded") is not True
        ):
            _reject(
                "terminal_mission_trace_mismatch",
                f"result.terminal_state.missions[{mission_id!r}]",
                f"trace lifecycle={status!r}, terminal={terminal_mission!r}",
            )
    metrics = result.get("metrics")
    if not isinstance(metrics, Mapping):
        _reject("missing_metrics", "result.metrics", "expected object")
    metric_expectations = {
        "planned_mission_waves": len(plan.missions),
        "launched_sorties": len(launches),
        "completed_sorties": len(returns),
        "cancelled_sorties": 0,
    }
    for field, expected in metric_expectations.items():
        if metrics.get(field) != expected:
            _reject(
                "metrics_trace_mismatch",
                f"result.metrics.{field}",
                f"expected {expected}, got {metrics.get(field)!r}",
            )

    transitions.sort(key=lambda item: (item[0], item[1]))
    intervals: list[dict[str, Any]] = []
    transition_index = 0
    current_state = transitions[0][2]
    for interval_index, start in enumerate(range(0, horizon_minutes, interval_minutes)):
        end = start + interval_minutes
        while transition_index + 1 < len(transitions) and transitions[transition_index + 1][0] <= start:
            transition_index += 1
            current_state = transitions[transition_index][2]
        cursor = start
        durations = {"ready": 0, "reserved": 0, "flying": 0}
        scan_index = transition_index + 1
        while scan_index < len(transitions) and transitions[scan_index][0] < end:
            minute, _sequence, next_state = transitions[scan_index]
            durations[current_state] += minute - cursor
            cursor = minute
            current_state = next_state
            transition_index = scan_index
            scan_index += 1
        durations[current_state] += end - cursor
        scale = 1.0 / interval_minutes
        ready = durations["ready"] * scale
        reserved = durations["reserved"] * scale
        flying = durations["flying"] * scale
        intervals.append(
            {
                "index": interval_index,
                "start_minutes": start,
                "end_minutes": end,
                "FTMO": flying,
                "NSYMO": flying,
                "NSYMA": reserved + flying,
                "NSYMR": reserved,
                "NSYRY": ready,
            }
        )

    interval_hours = interval_minutes / 60.0
    integrals = {
        "FTMO_hours": sum(item["FTMO"] for item in intervals) * interval_hours,
        "NSYMO_aircraft_hours": sum(item["NSYMO"] for item in intervals) * interval_hours,
        "NSYMA_aircraft_hours": sum(item["NSYMA"] for item in intervals) * interval_hours,
        "NSYMR_aircraft_hours": sum(item["NSYMR"] for item in intervals) * interval_hours,
        "NSYRY_aircraft_hours": sum(item["NSYRY"] for item in intervals) * interval_hours,
    }
    launched_waves = len(launches)
    terminal_counts = {
        "planned_waves": len(plan.missions),
        "launched_waves": launched_waves,
        "sorties": sum(len(event["details"]["aircraft"]) for event in launches.values()),
        "completed_waves": sum(item.get("status") == "completed" for item in by_mission.values()),
        "cancelled_waves": sum(item.get("status") == "cancelled" for item in by_mission.values()),
        "unfinished_at_horizon": sum(
            item.get("status") not in {"completed", "failed", "cancelled"}
            for item in by_mission.values()
        ),
    }
    mapped_events.sort(
        key=lambda item: (
            item["time_minutes"],
            -1 if item["evidence"]["sequence"] is None else item["evidence"]["sequence"],
            item["kind"],
        )
    )
    return {
        "schema": SCHEMA,
        "case_id": case_id,
        "status": "observed",
        "bindings": {
            "plan_fingerprint": plan.fingerprint,
            "source_inputs_sha256": plan.source_inputs_sha256,
            "result_sha256": _canonical_sha256(dict(result)),
            "semantic_profile": plan.semantic_profile,
            "observation": "full",
            "horizon_minutes": horizon_minutes,
            "interval_minutes": interval_minutes,
        },
        "identity_mapping": {
            "aircraft": aircraft_map,
            "missions": mission_map,
        },
        "mapped_events": mapped_events,
        "intervals": intervals,
        "integrals": integrals,
        "terminal": terminal_counts,
        "unsupported_native_observables": [
            {
                "kind": "notification_semantics",
                "status": "time_proxy_only",
                "reason": "preflight_created supplies the commission-boundary time; the engine has no independent native notification event",
            },
            {
                "kind": "created",
                "status": "native_only_unobserved",
                "reason": "no source-faithful engine event mapping is agreed",
            },
            {
                "kind": "activated",
                "status": "native_only_unobserved",
                "reason": "no source-faithful engine event mapping is agreed",
            },
            {
                "kind": "task_start/task_completion",
                "status": "native_only_unobserved",
                "reason": "the native 8.5-9.5h inner task is not an engine mission boundary",
            },
            {
                "kind": "zero_time_preparation_log",
                "status": "native_only_unobserved",
                "reason": "NPSTA=0; zero-work Plan activities are validated, not reported as native work",
            },
        ],
        "notes": [
            "Plan initial_state=available is the time-zero ready evidence; it is not a captured runtime event.",
            "Engine mission_ready is classified as reserved/non-ready, not native globally-free ready.",
            "Notification time is a preflight_created proxy, not proof of an independent notification lifecycle event.",
            "Mapped native event order is not evidence of engine/native same-tick microstep equivalence.",
            "SIMPE horizon and native RCEND collection-window behavior are not conflated.",
            "Native MSUF is not interpreted as completed_waves.",
        ],
    }


def compare_observations(
    actual: Mapping[str, Any],
    expected_case: Mapping[str, Any],
    tolerances: Mapping[str, Any],
    *,
    expected_source_inputs_sha256: str | None = None,
    expected_plan_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Compare an extracted result to native expectations, retaining every check."""

    checks: list[dict[str, Any]] = []

    def check(
        path: str,
        left: Any,
        right: Any,
        *,
        absolute_tolerance: float | None = None,
    ) -> None:
        if absolute_tolerance is None:
            passed = left == right
        else:
            passed = (
                isinstance(left, (int, float))
                and not isinstance(left, bool)
                and isinstance(right, (int, float))
                and not isinstance(right, bool)
                and math.isclose(
                    float(left),
                    float(right),
                    rel_tol=0.0,
                    abs_tol=absolute_tolerance,
                )
            )
        checks.append(
            {
                "path": path,
                "status": "pass" if passed else "fail",
                "actual": left,
                "expected": right,
                "absolute_tolerance": absolute_tolerance,
            }
        )

    check("schema", actual.get("schema"), SCHEMA)
    check("case_id", actual.get("case_id"), expected_case.get("case_id"))
    bindings = actual.get("bindings", {})
    if expected_source_inputs_sha256 is not None:
        check(
            "bindings.source_inputs_sha256",
            bindings.get("source_inputs_sha256"),
            expected_source_inputs_sha256,
        )
    if expected_plan_fingerprint is not None:
        check(
            "bindings.plan_fingerprint",
            bindings.get("plan_fingerprint"),
            expected_plan_fingerprint,
        )

    comparable_kinds = {
        "notification",
        "allocation",
        "ready_decreased",
        "start",
        "success",
        "completion",
        "ready_increased",
    }
    actual_events = sorted(
        (
            item
            for item in actual.get("mapped_events", [])
            if item.get("kind") in comparable_kinds
        ),
        key=lambda item: (
            item.get("time_minutes"),
            item.get("kind"),
            str(item.get("mission_instance")),
            str(item.get("aircraft_instance")),
        ),
    )
    expected_events = sorted(
        (
            item
            for item in expected_case.get("events", [])
            if item.get("kind") in comparable_kinds
            and item.get("mapping") in {"mission_observable", "state_observable"}
        ),
        key=lambda item: (
            item.get("time_minutes"),
            item.get("kind"),
            str(item.get("mission_instance")),
            str(item.get("aircraft_instance")),
        ),
    )
    check("mapped_events.length", len(actual_events), len(expected_events))
    event_tolerance = float(tolerances["event_time"]["equivalent_minutes"])
    for index in range(min(len(actual_events), len(expected_events))):
        observed = actual_events[index]
        expected = expected_events[index]
        prefix = f"mapped_events[{index}]"
        check(f"{prefix}.kind", observed.get("kind"), expected.get("kind"))
        check(
            f"{prefix}.mission_instance",
            observed.get("mission_instance"),
            expected.get("mission_instance"),
        )
        check(
            f"{prefix}.aircraft_instance",
            observed.get("aircraft_instance"),
            expected.get("aircraft_instance"),
        )
        check(
            f"{prefix}.time_minutes",
            observed.get("time_minutes"),
            expected.get("time_minutes"),
            absolute_tolerance=event_tolerance,
        )

    actual_intervals = actual.get("intervals", [])
    expected_intervals = expected_case.get("intervals", [])
    check("intervals.length", len(actual_intervals), len(expected_intervals))
    for index in range(min(len(actual_intervals), len(expected_intervals))):
        observed = actual_intervals[index]
        expected = expected_intervals[index]
        prefix = f"intervals[{index}]"
        check(f"{prefix}.index", observed.get("index"), expected.get("index"))
        endpoint_tolerance = float(
            tolerances["normal_interval_endpoint"]["equivalent_minutes"]
        )
        for field in ("start_minutes", "end_minutes"):
            check(
                f"{prefix}.{field}",
                observed.get(field),
                expected.get(field),
                absolute_tolerance=endpoint_tolerance,
            )
        for field in PROFILE_FIELDS:
            check(
                f"{prefix}.{field}",
                observed.get(field),
                expected.get(field),
                absolute_tolerance=float(tolerances["profile"][field]["absolute"]),
            )

    integral_names = {
        "FTMO": "FTMO_hours",
        "NSYMO": "NSYMO_aircraft_hours",
        "NSYMA": "NSYMA_aircraft_hours",
        "NSYMR": "NSYMR_aircraft_hours",
        "NSYRY": "NSYRY_aircraft_hours",
    }
    for field, key in integral_names.items():
        check(
            f"integrals.{key}",
            actual.get("integrals", {}).get(key),
            expected_case.get("integrals", {}).get(key),
            absolute_tolerance=float(tolerances["integral"][field]["absolute"]),
        )
    for field, expected in expected_case.get("terminal", {}).items():
        check(f"terminal.{field}", actual.get("terminal", {}).get(field), expected)

    first_failure = next((item for item in checks if item["status"] == "fail"), None)
    return {
        "schema": COMPARISON_SCHEMA,
        "case_id": expected_case.get("case_id"),
        "status": "matched" if first_failure is None else "mismatched",
        "check_count": len(checks),
        "passed_count": sum(item["status"] == "pass" for item in checks),
        "failed_count": sum(item["status"] == "fail" for item in checks),
        "first_divergence": first_failure,
        "checks": checks,
    }
