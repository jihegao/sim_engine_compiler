"""Independent Python reference for the restricted two-server queue plan.

Random calls use CPython ``Random`` with the same transformation as the Rust
runtime: exponential values are ``-log(1 - u) / rate``. Call order is part of
the profile contract:

1. one interarrival draw schedules the first customer;
2. on an arrival, draw its class, enqueue it, seize idle servers (drawing each
   service time), then draw the next interarrival;
3. on a completion at or before the horizon, free that server and seize again.

Equal timestamps run completions before arrivals, and the lower server index
first. Customers who have not started service by the horizon are excluded from
mean wait. Mean wait is the sequential IEEE-754 sum of those waits divided by
their count. The profile errors when its fixed arrival or step limit is hit.
"""

from __future__ import annotations

import math
import random
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.identity.common import content_digest

from .model import MAX_ADMITTED_ARRIVALS, MAX_LOOP_STEPS, validate_plan


def _expovariate(rng: random.Random, rate: float) -> float:
    return -math.log(1.0 - rng.random()) / rate


def execute(
    plan: dict[str, Any],
    *,
    seed: int,
    sample_index: int = 0,
    observation: str = "full",
    until: int | None = None,
) -> dict[str, Any]:
    document = validate_plan(plan)
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise CompilationError("seed must be an unsigned 64-bit integer", code="invalid_seed", source_path="seed")
    if observation not in {"full", "summary"}:
        raise CompilationError("observation must be full or summary", code="invalid_ir", source_path="observation")
    horizon = document["horizon_minutes"]
    if until is not None:
        if type(until) is not int or until < 0 or until > horizon:
            raise CompilationError("until is outside the plan horizon", code="invalid_horizon", source_path="until")
        horizon = until
    rng = random.Random(seed)
    requests: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    ordinal = 1
    classes = list(document["classes"])
    ordered_classes = sorted(classes, key=lambda item: item["id"])
    weights = [[item["id"], item["weight"]] for item in ordered_classes]
    total_weight = sum(item["weight"] for item in ordered_classes)

    def customer_id(number: int) -> str:
        return f"customer-{number:04d}"

    def draw_exp(stream_id: str, rate: float, time: float, purpose: str) -> float:
        value = _expovariate(rng, rate)
        requests.append({
            "sequence": len(requests) + 1,
            "stream_id": stream_id,
            "distribution": "exponential",
            "rate_per_minute": rate,
            "value_minutes": value,
            "time_minutes": float(time),
            "purpose": purpose,
        })
        return value

    def draw_class(stream_id: str, time: float) -> dict[str, Any]:
        uniform = rng.random()
        point = uniform * float(total_weight)
        cumulative = 0
        chosen = ordered_classes[-1]
        for item in ordered_classes:
            cumulative += item["weight"]
            if point < float(cumulative):
                chosen = item
                break
        requests.append({
            "sequence": len(requests) + 1,
            "stream_id": stream_id,
            "distribution": "weighted_class",
            "u": uniform,
            "value": chosen["id"],
            "weights": weights,
            "time_minutes": float(time),
            "purpose": "class",
        })
        return chosen

    def emit(kind: str, rule_id: str, entity: str, source_path: str, time: float, phase: str, details: dict[str, Any]) -> None:
        trace.append({
            "sequence": len(trace) + 1,
            "time": float(time),
            "phase": phase,
            "kind": kind,
            "rule_id": rule_id,
            "entity": entity,
            "source_path": source_path,
            "details": details,
        })

    servers = [
        {
            "id": item["id"],
            "index": item["index"],
            "rate": item["service_rate_per_minute"],
            "source_path": item["source_path"],
            "customer": None,
            "busy_until": None,
        }
        for item in document["servers"]
    ]
    waiting: list[dict[str, Any]] = []
    waits: list[float] = []
    completed: list[str] = []
    arrivals = 0
    starts = 0
    completions = 0

    def idle() -> list[dict[str, Any]]:
        return [server for server in servers if server["customer"] is None]

    def fill(now: float) -> None:
        nonlocal starts
        while waiting and idle():
            waiting.sort(key=lambda customer: (-customer["priority"], customer["arrival"], customer["id"]))
            customer = waiting.pop(0)
            server = idle()[0]
            service = draw_exp(f"service:{customer['id']}", server["rate"], now, "service")
            customer["start"] = now
            customer["server_id"] = server["id"]
            customer["service"] = service
            server["customer"] = customer
            server["busy_until"] = now + service
            wait = now - customer["arrival"]
            waits.append(wait)
            starts += 1
            emit(
                "service_started",
                "queue.nonpreemptive_priority_seize/v1",
                customer["id"],
                server["source_path"],
                now,
                "service",
                {
                    "server_id": server["id"],
                    "class_id": customer["class_id"],
                    "priority": customer["priority"],
                    "wait_minutes": wait,
                    "service_minutes": service,
                },
            )

    if ordinal > MAX_ADMITTED_ARRIVALS:
        raise CompilationError("admitted arrival limit exceeded", code="resource_limit", source_path="arrivals")
    first_id = customer_id(ordinal)
    ordinal += 1
    next_arrival = draw_exp(
        f"interarrival:{first_id}", document["arrival_rate_per_minute"], 0.0, "interarrival"
    )
    next_id = first_id
    steps = 0
    while True:
        steps += 1
        if steps > MAX_LOOP_STEPS:
            raise CompilationError("queue step limit exceeded", code="resource_limit", source_path="horizon")
        candidates = []
        if next_arrival is not None and next_arrival < float(horizon):
            candidates.append((next_arrival, 1, -1, "arrival"))
        for server in servers:
            if server["customer"] is not None and server["busy_until"] <= float(horizon):
                candidates.append((server["busy_until"], 0, server["index"], "completion"))
        if not candidates:
            break
        when, _rank, index, kind = min(candidates)
        if kind == "arrival":
            if arrivals >= MAX_ADMITTED_ARRIVALS:
                raise CompilationError("admitted arrival limit exceeded", code="resource_limit", source_path="arrivals")
            chosen = draw_class(f"class:{next_id}", when)
            customer = {
                "id": next_id,
                "class_id": chosen["id"],
                "priority": chosen["priority"],
                "arrival": when,
            }
            waiting.append(customer)
            arrivals += 1
            emit(
                "customer_arrived",
                "queue.poisson_arrival/v1",
                next_id,
                "arrivals",
                when,
                "arrival",
                {"class_id": chosen["id"], "priority": chosen["priority"], "arrival_time": when},
            )
            fill(when)
            if ordinal > MAX_ADMITTED_ARRIVALS:
                raise CompilationError("admitted arrival limit exceeded", code="resource_limit", source_path="arrivals")
            upcoming = customer_id(ordinal)
            ordinal += 1
            next_arrival = when + draw_exp(
                f"interarrival:{upcoming}", document["arrival_rate_per_minute"], when, "interarrival"
            )
            next_id = upcoming
        else:
            server = servers[index]
            customer = server["customer"]
            emit(
                "service_completed",
                "queue.exponential_service/v1",
                customer["id"],
                server["source_path"],
                when,
                "service",
                {
                    "server_id": server["id"],
                    "class_id": customer["class_id"],
                    "service_minutes": customer["service"],
                },
            )
            completions += 1
            completed.append(customer["id"])
            server["customer"] = None
            server["busy_until"] = None
            fill(when)

    emit(
        "simulation_stopped",
        "stop.horizon",
        "simulation",
        "horizon",
        float(horizon),
        "stop",
        {"reason": "horizon"},
    )
    # Sequential IEEE addition, the same reduction the Rust runtime uses.
    # CPython's built-in sum is a different compensated reduction.
    total = 0.0
    for value in waits:
        total += value
    mean = None if not waits else total / len(waits)
    return {
        "plan_fingerprint": content_digest(document),
        "business_fingerprint": document["business_fingerprint"],
        "core_fingerprint": document["core_fingerprint"],
        "profile": document["profile"],
        "semantic_profile": document["semantic_profile"],
        "seed": seed,
        "sample_index": sample_index,
        "time": horizon,
        "stop_reason": "horizon",
        "sample_requests": requests,
        "trace": [] if observation == "summary" else trace,
        "metrics": {
            "mean_wait": mean,
            "wait_count": len(waits),
            "arrival_count": arrivals,
            "service_start_count": starts,
            "service_completion_count": completions,
        },
        "terminal_state": {
            "waiting": [
                {
                    "id": customer["id"],
                    "class_id": customer["class_id"],
                    "priority": customer["priority"],
                    "arrival_time": customer["arrival"],
                }
                for customer in waiting
            ],
            "servers": [
                {
                    "id": server["id"],
                    "index": server["index"],
                    "state": "idle" if server["customer"] is None else "busy",
                    "customer_id": None if server["customer"] is None else server["customer"]["id"],
                    "remaining_minutes": 0.0 if server["customer"] is None else server["busy_until"] - float(horizon),
                }
                for server in servers
            ],
            "completed_customer_ids": completed,
        },
    }
