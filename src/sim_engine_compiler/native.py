"""Python boundary for the independent Rust plan runtime.

The native call receives a whole serialized plan and returns a whole result or
batch. No event-level callbacks cross the Python/Rust boundary.
"""

from __future__ import annotations

import json
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Sequence

from sim_engine_compiler.ir.plan import ExecutionPlan


PlanInput = ExecutionPlan | Mapping[str, Any] | str | bytes | PathLike[str]


def _native_module():
    try:
        from sim_engine_compiler import _runtime
    except ImportError as error:  # pragma: no cover - depends on install mode
        raise RuntimeError(
            "the Rust binding is not installed; run `.venv/bin/python -m pip install -e .`"
        ) from error
    return _runtime


def native_available() -> bool:
    try:
        _native_module()
    except RuntimeError:
        return False
    return True


def _plan_json(plan: PlanInput) -> str:
    if isinstance(plan, ExecutionPlan):
        value: Any = plan.to_dict()
    elif isinstance(plan, Mapping):
        value = dict(plan)
    elif isinstance(plan, bytes):
        return plan.decode("utf-8")
    elif isinstance(plan, PathLike):
        return Path(plan).read_text()
    elif isinstance(plan, str):
        stripped = plan.lstrip()
        if stripped.startswith("{"):
            return plan
        return Path(plan).read_text()
    else:  # pragma: no cover - defensive public boundary
        raise TypeError(f"unsupported plan input {type(plan)!r}")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_plan(
    plan: PlanInput,
    *,
    seed: int = 0,
    until: int | None = None,
) -> dict[str, Any]:
    """Run one sample in Rust and return the decoded result contract."""

    encoded = _native_module().run_plan_json(_plan_json(plan), seed, until)
    return json.loads(encoded)


def run_batch(
    plan: PlanInput,
    seeds: Sequence[int],
    *,
    worker_threads: int | None = None,
    until: int | None = None,
) -> dict[str, Any]:
    """Run independent samples in Rust with input-order-stable results."""

    encoded = _native_module().run_batch_json(
        _plan_json(plan), list(seeds), worker_threads, until
    )
    return json.loads(encoded)
