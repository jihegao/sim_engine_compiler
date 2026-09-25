"""Scoped canonical work-duration and component-reference validation.

This is not a replacement for the upstream canonical schema. Missing/null and
zero durations retain legacy defaulting; positive fractions retain truncation.
Bare JSON numeric strings are an explicit compatibility normalization. Unit
strings, booleans, nonfinite values and negative durations are never defaulted.
"""

from __future__ import annotations

import json
import math
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError


def _duration(value: Any, path: str) -> None:
    if value is None:
        return
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value.strip())
        except ValueError:
            parsed = None
    try:
        number = float(parsed) if type(parsed) in (int, float) else math.nan
    except OverflowError:
        number = math.inf
    if not math.isfinite(number):
        raise CompilationError(
            "expected finite numeric minutes (unit text is not supported)",
            code="invalid_duration_type", source_path=path,
        )
    if number < 0:
        raise CompilationError("duration must be nonnegative", code="negative_duration", source_path=path)
    if number >= 2**63:
        raise CompilationError("duration exceeds supported integer minutes", code="duration_out_of_range", source_path=path)


def validate_canonical_work(inputs: dict[str, Any]) -> None:
    components = inputs.get("equipment_tree", {}).get("components", [])
    component_ids = {str(item["id"]) for item in components
                     if isinstance(item, dict) and item.get("id") not in (None, "")}
    for index, activity in enumerate(inputs.get("support_activities", {}).get("activities", [])):
        if not isinstance(activity, dict):
            continue
        path = f"support_activities.activities[{index}]"
        _duration(activity.get("duration_minutes"), f"{path}.duration_minutes")
        reference = activity.get("equipment_id")
        if reference is not None and reference != "":
            if not isinstance(reference, str) or reference not in component_ids:
                raise CompilationError(
                    f"activity {activity.get('id', '')!r} has unresolved component reference {reference!r}",
                    code="unresolved_component_reference", source_path=f"{path}.equipment_id",
                )
        for job_index, job in enumerate(activity.get("jobs") or []):
            if isinstance(job, dict):
                for field in ("durationMinutes", "duration_minutes"):
                    _duration(job.get(field), f"{path}.jobs[{job_index}].{field}")
