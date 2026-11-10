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


def _failure_distribution(value: Any, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise CompilationError(
            "expected failure distribution object",
            code="invalid_failure_distribution",
            source_path=path,
        )
    if not value:
        return

    raw_type = value.get("distributionType")
    if raw_type is None:
        raw_type = value.get("distribution_type")
    if raw_type is not None and not isinstance(raw_type, str):
        raise CompilationError(
            "failure distribution type must be a string",
            code="unsupported_failure_distribution",
            source_path=path,
        )
    distribution_type = raw_type.strip().lower() if isinstance(raw_type, str) else ""
    if "mtbf" in value:
        if distribution_type not in {"exponential", "指数分布"}:
            raise CompilationError(
                "MTBF is currently supported only for the exponential distribution",
                code="unsupported_failure_distribution",
                source_path=path,
            )
        mtbf = value["mtbf"]
        try:
            numeric_mtbf = float(mtbf) if type(mtbf) in (int, float) else math.nan
        except OverflowError:
            numeric_mtbf = math.inf
        if not math.isfinite(numeric_mtbf) or numeric_mtbf <= 0:
            raise CompilationError(
                "MTBF must be a positive finite number",
                code="invalid_mtbf",
                source_path=f"{path}.mtbf",
            )
        if "timeUnit" not in value:
            raise CompilationError(
                "MTBF timeUnit is required",
                code="missing_failure_time_unit",
                source_path=f"{path}.timeUnit",
            )
        if value["timeUnit"] != "hour":
            raise CompilationError(
                "aircraft-support MTBF timeUnit must be 'hour'",
                code="unsupported_failure_time_unit",
                source_path=f"{path}.timeUnit",
            )
        if "timeBasis" not in value:
            raise CompilationError(
                "aircraft-support MTBF timeBasis is required",
                code="missing_failure_time_basis",
                source_path=f"{path}.timeBasis",
            )
        if value["timeBasis"] != "flight_hour":
            raise CompilationError(
                "aircraft-support MTBF timeBasis must be 'flight_hour'",
                code="unsupported_failure_time_basis",
                source_path=f"{path}.timeBasis",
            )
        if not math.isfinite(1.0 / numeric_mtbf):
            raise CompilationError(
                "MTBF is outside the supported numeric range",
                code="invalid_mtbf",
                source_path=f"{path}.mtbf",
            )
        return

    if distribution_type and not any(
        kind in distribution_type
        for kind in ("exponential", "指数", "weibull", "威布尔", "normal", "正态",
                     "uniform", "均匀", "fixed", "固定")
    ):
        raise CompilationError(
            f"unsupported failure distribution {raw_type!r}",
            code="unsupported_failure_distribution",
            source_path=path,
        )


def validate_canonical_work(inputs: dict[str, Any]) -> None:
    equipment_tree = inputs.get("equipment_tree")
    components = equipment_tree.get("components", []) if isinstance(equipment_tree, dict) else []
    for index, component in enumerate(components):
        if isinstance(component, dict):
            redundancy = component.get("k_out_of_n")
            if redundancy is not None:
                path = f"equipment_tree.components[{index}].k_out_of_n"
                if not isinstance(redundancy, dict) or type(redundancy.get("enabled")) is not bool:
                    raise CompilationError(
                        "k_out_of_n must be an object with a boolean enabled field",
                        code="invalid_k_out_of_n",
                        source_path=path,
                    )
                if redundancy["enabled"]:
                    raise CompilationError(
                        "aircraft-support k_out_of_n is not supported",
                        code="unsupported_k_out_of_n",
                        source_path=path,
                    )
            _failure_distribution(
                component.get("failure_distribution"),
                f"equipment_tree.components[{index}].failure_distribution",
            )
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
