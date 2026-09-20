#!/usr/bin/env python3
"""Run the isolated legacy oracle on an existing canonical simulation_inputs file.

This tool is deliberately outside the compiler/runtime package. Production code
must never import it or the legacy model it loads.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import MethodType
from typing import Any


PHASE_METHODS = {
    "_process_transport_arrivals": "transport_arrivals",
    "_process_mission_returns": "mission_returns",
    "_process_job_progress_and_completions": "job_progress_and_completions",
    "_evaluate_failures": "failures",
    "_generate_preventive_jobs": "preventive_generation",
    "_create_due_preflight_jobs": "preflight_generation",
    "_start_waiting_jobs": "resource_dispatch",
    "_dispatch_due_missions": "mission_dispatch",
    "_evaluate_mission_success_points": "mission_success",
    "_record_daily_readiness_sample_if_due": "daily_readiness",
    "_record_operational_availability_sample_if_due": "operational_availability",
    "_record_downtime_minutes": "downtime",
    "_stop_decision": "stop",
}


def instrument(model: Any) -> None:
    model._oracle_phase = "initialize"
    model._oracle_phase_calls = {}
    model._oracle_events = []
    original_event = model._event

    def event_wrapper(self, event, message, details=None):
        self._oracle_events.append(
            {
                "time": self.minute,
                "phase": self._oracle_phase,
                "kind": event,
                "message": message,
                "details": copy.deepcopy(details or {}),
            }
        )
        return original_event(event, message, details)

    model._event = MethodType(event_wrapper, model)
    for method_name, phase in PHASE_METHODS.items():
        original = getattr(model, method_name)

        def make_wrapper(bound, phase_name):
            def wrapper(self, *args, **kwargs):
                self._oracle_phase = phase_name
                return bound(*args, **kwargs)

            return wrapper

        setattr(model, method_name, MethodType(make_wrapper(original, phase), model))

    original_coordinate = model._coordinate_operations_postflight

    def coordinate_wrapper(self, *args, **kwargs):
        key = (self.minute, "operations_postflight")
        call = self._oracle_phase_calls.get(key, 0) + 1
        self._oracle_phase_calls[key] = call
        self._oracle_phase = (
            "operations_postflight_before_preparation"
            if call == 1
            else "operations_postflight_after_dispatch"
            if call == 2
            else "stop"
        )
        return original_coordinate(*args, **kwargs)

    model._coordinate_operations_postflight = MethodType(coordinate_wrapper, model)


def entity_for_event(item: dict[str, Any]) -> str:
    details = item.get("details") or {}
    for key in ("job_id", "mission_id", "tail_number"):
        if details.get(key):
            return str(details[key])
    message = str(item.get("message") or "")
    return message.split()[0] if message else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spare-mvp-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="write minified JSON while retaining the complete raw trace",
    )
    args = parser.parse_args()
    root = args.spare_mvp_root.resolve()
    sys.path.insert(0, str(root))
    from src.spare_mvp_abm.aircraft_support_v1.model import AircraftSupportV1Model
    from src.spare_mvp_abm.aircraft_support_v1.failure_engine import FailureEngineMixin

    input_bytes = args.input.read_bytes()
    inputs = json.loads(input_bytes)
    inputs["seed"] = args.seed
    inputs["disable_visualization_frames"] = True
    sample_requests: list[dict[str, Any]] = []
    original_sample = FailureEngineMixin._sample_lru_failure_minutes

    def sampled_failure_minutes(self, component):
        value = original_sample(self, component)
        sample_requests.append(
            {
                "sequence": len(sample_requests) + 1,
                "time": int(getattr(self, "minute", 0)),
                "phase": str(getattr(self, "_oracle_phase", "initialize")),
                "stream": "legacy-sequential-v1",
                "distribution": "exponential",
                "component_id": str(component.get("id") or "component"),
                "quantity": max(1, int(component.get("quantity") or 1)),
                "rate_per_hour": float(component.get("failure_rate") or 0.0),
                "value_minutes": value,
            }
        )
        return value

    FailureEngineMixin._sample_lru_failure_minutes = sampled_failure_minutes
    try:
        model = AircraftSupportV1Model(inputs)
    finally:
        FailureEngineMixin._sample_lru_failure_minutes = original_sample
    instrument(model)
    # Keep recording repair-completion resamples after instrumentation.
    model._sample_lru_failure_minutes = MethodType(sampled_failure_minutes, model)
    result = model.run()
    payload = {
        "oracle": "AircraftSupportV1Model",
        "oracle_fixture_version": "legacy-minute-oracle/v1",
        "spare_mvp_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "input_file_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "seed": args.seed,
        "time": model.minute,
        "sample_requests": sample_requests,
        "trace": [
            {
                **item,
                "entity": entity_for_event(item),
            }
            for item in model._oracle_events
        ],
        "metrics": result["metrics"],
        "terminal_state": {
            "aircraft": [
                {
                    "tail_number": item.tail_number,
                    "state": item.state,
                    "current_mission_id": item.current_mission_id,
                    "prepared_mission_ids": sorted(item.prepared_mission_ids),
                    "operations_day": item.operations_day,
                    "daily_takeoffs": item.daily_takeoffs,
                    "postflight_required": item.postflight_required,
                    "postflight_due": item.postflight_due,
                    "flight_hours": item.flight_hours,
                    "takeoff_count": item.takeoff_count,
                    "landing_count": item.landing_count,
                    "failed_component_id": item.failed_component_id,
                    "component_failure_minutes": dict(item.component_failure_minutes),
                    "in_flight_failure": item.in_flight_failure,
                }
                for item in model.aircraft
            ],
            "missions": [
                {
                    "mission_id": item.mission_id,
                    "status": item.status,
                    "actual_start": item.actual_start,
                    "assigned_tail_numbers": list(item.assigned_tail_numbers),
                    "success_evaluated": item.success_evaluated,
                    "succeeded": item.succeeded,
                }
                for item in model.missions
            ],
            "jobs": [
                {
                    "job_id": item.job_id,
                    "kind": item.kind,
                    "aircraft": item.tail_number,
                    "mission_id": item.mission_id,
                    "activity_id": item.activity_id,
                    "state": item.state,
                    "step_index": item.task_index,
                    "started_time": item.started_time,
                    "completed_time": item.completed_time,
                    "component_id": item.component_id,
                    "maintenance_method": item.maintenance_method,
                }
                for item in model.jobs
            ],
            "resources": [
                {
                    "node_id": node["id"],
                    "personnel_in_use": node["personnel_in_use"],
                    "equipment_in_use": node["equipment_in_use"],
                    "inventory": dict(sorted(node["inventory"].items())),
                }
                for node in model.nodes.values()
            ],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if args.compact else 2,
            separators=(",", ":") if args.compact else None,
        )
        + "\n"
    )
    print(json.dumps({"events": len(payload["trace"]), "metrics": payload["metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
