"""Nine source-semantics hand cases from the Schelling source gate.

The value tapes in this module are authored data.  They deliberately do not use
either runtime's RNG, which makes the fixtures suitable for Python/Rust and
NetLogo-oracle differential checks.
"""
from __future__ import annotations

import copy
import math
from typing import Any

SOURCE_SCHEMA = "abm-source-semantics/v1"
TAPE_SCHEMA = "abm-random-tape/v1"


def get(scope: str, field: str) -> dict[str, Any]:
    return {"op": "get", "scope": scope, "field": field}


def binary(operator: str, left: Any, right: Any) -> dict[str, Any]:
    return {"op": "binary", "operator": operator, "left": left, "right": right}


def unary(operator: str, value: Any) -> dict[str, Any]:
    return {"op": "unary", "operator": operator, "value": value}


def count(
    source: str,
    *,
    where: Any = None,
    agent_kind: str | None = None,
    neighborhood: str | None = None,
) -> dict[str, Any]:
    return {
        "op": "count",
        "source": source,
        "agent_kind": agent_kind,
        "neighborhood": neighborhood,
        "where": where,
    }


def patch(x: int, y: int) -> dict[str, Any]:
    return {"id": f"patch:{x}:{y}", "x": x, "y": y, "vars": {}}


def person(
    identity: str,
    group: str,
    x: float,
    y: float,
    *,
    heading: float = 0.0,
    happy: bool = False,
    **variables: Any,
) -> dict[str, Any]:
    values = {"group": group, "heading": heading, "happy": happy, **variables}
    return {"id": identity, "kind": "person", "x": x, "y": y, "vars": values}


def random_expr(distribution: str, address: str, args: list[Any]) -> dict[str, Any]:
    return {"op": "random", "distribution": distribution, "address": address, "args": args}


def tape_entry(
    *,
    tick: int,
    phase: str,
    address: str,
    entity_id: str,
    occurrence: int,
    distribution: str,
    args: list[Any],
    value: Any,
) -> dict[str, Any]:
    return {
        "tick": tick,
        "phase": phase,
        "address": address,
        "entity_id": entity_id,
        "occurrence": occurrence,
        "distribution": distribution,
        "args": args,
        "value": value,
    }


def tape(*requests: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": TAPE_SCHEMA, "requests": list(requests)}


def traversal(actor: str, value: float, *, phase: str = "move-unhappy", tick: int = 0) -> dict[str, Any]:
    return tape_entry(
        tick=tick,
        phase=phase,
        address="schelling.move-order",
        entity_id=actor,
        occurrence=0,
        distribution="traversal_key",
        args=[],
        value=value,
    )


def movement_draws(
    actor: str,
    attempts: list[tuple[float, float]],
    *,
    phase: str = "move-unhappy",
    tick: int = 0,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for occurrence, (turn, distance) in enumerate(attempts):
        result.extend(
            [
                tape_entry(
                    tick=tick,
                    phase=phase,
                    address="schelling.turn",
                    entity_id=actor,
                    occurrence=occurrence,
                    distribution="uniform",
                    args=[0, 360],
                    value=turn,
                ),
                tape_entry(
                    tick=tick,
                    phase=phase,
                    address="schelling.distance",
                    entity_id=actor,
                    occurrence=occurrence,
                    distribution="uniform",
                    args=[0, 10],
                    value=distance,
                ),
            ]
        )
    return result


def local_move(*, attempt_budget: int = 8) -> dict[str, Any]:
    return {
        "op": "move",
        "guard": None,
        "mode": "local_rejection",
        "x": None,
        "y": None,
        "neighborhood": None,
        "address": None,
        "heading_step": None,
        "local_rejection": {
            "turn_address": "schelling.turn",
            "distance_address": "schelling.distance",
            "turn_bounds": [0, 360],
            "distance_bounds": [0, 10],
            "attempt_budget": attempt_budget,
        },
    }


def unhappy_selector() -> dict[str, Any]:
    return unary("not", get("self", "happy"))


def move_phase(*, traversal_mode: str = "random", where: Any | None = None) -> dict[str, Any]:
    phase = {
        "id": "move-unhappy",
        "target": "agents",
        "agent_kind": "person",
        "read_view": "current",
        "commit_mode": "immediate",
        "traversal": traversal_mode,
        "random_address": "schelling.move-order" if traversal_mode == "random" else None,
        "operations": [local_move()],
    }
    if where is not None:
        phase["where"] = where
    return phase


def source_model(
    identity: str,
    agents: list[dict[str, Any]],
    *,
    phases: list[dict[str, Any]] | None = None,
    initialization: list[dict[str, Any]] | None = None,
    stop_conditions: list[dict[str, Any]] | None = None,
    metrics: list[dict[str, Any]] | None = None,
    max_ticks: int = 1,
    width: int = 5,
    height: int = 5,
) -> dict[str, Any]:
    return {
        "model_id": identity,
        "profile": "abm-tick-v1",
        "topology": {"kind": "torus", "width": width, "height": height},
        "initial_state": {
            "globals": {},
            "patches": [patch(x, y) for x in range(width) for y in range(height)],
            "agents": agents,
        },
        "phases": phases if phases is not None else [move_phase(where=unhappy_selector())],
        "stop_conditions": stop_conditions if stop_conditions is not None else [],
        "metrics": metrics if metrics is not None else [],
        "max_ticks": max_ticks,
        "source_semantics": {
            "schema_version": SOURCE_SCHEMA,
            "initialization": initialization if initialization is not None else [],
            "stop_timing": "before_tick",
        },
    }


def all_happy_stop() -> list[dict[str, Any]]:
    return [
        {
            "id": "all-happy",
            "when": binary(
                "==",
                count("agents", where=binary("==", get("self", "happy"), False)),
                0,
            ),
        }
    ]


def reassess_phase(threshold: float = 0.5) -> dict[str, Any]:
    total = count("neighbors", agent_kind="*", neighborhood="moore")
    similar = count(
        "neighbors",
        agent_kind="*",
        neighborhood="moore",
        where=binary("==", get("self", "group"), get("outer", "group")),
    )
    return {
        "id": "reassess",
        "target": "agents",
        "agent_kind": "person",
        "read_view": "phase_start",
        "commit_mode": "buffered",
        "traversal": "stable",
        "random_address": None,
        "operations": [
            {
                "op": "set",
                "guard": None,
                "target": "self",
                "field": "happy",
                "value": binary(">=", similar, binary("*", threshold, total)),
            }
        ],
    }


def _metric_initialization() -> list[dict[str, Any]]:
    return [
        {
            "id": "aggregate-source-neighbor-counts",
            "target": "agents",
            "agent_kind": "person",
            "read_view": "current",
            "commit_mode": "immediate",
            "traversal": "stable",
            "random_address": None,
            "operations": [
                {
                    "op": "increment",
                    "guard": None,
                    "target": "globals",
                    "field": "source_similar_sum",
                    "value": get("self", "similar_nearby"),
                },
                {
                    "op": "increment",
                    "guard": None,
                    "target": "globals",
                    "field": "source_total_sum",
                    "value": get("self", "total_nearby"),
                },
            ],
        }
    ]


def _source_similarity_metric() -> dict[str, Any]:
    return {
        "id": "source_percent_similar",
        "reducer": "expression",
        "source": "globals",
        "field": None,
        "where": None,
        "expression": binary(
            "*",
            100.0,
            binary(
                "/",
                get("globals", "source_similar_sum"),
                get("globals", "source_total_sum"),
            ),
        ),
    }


def _neighbor_counts(grid: list[list[str | None]]) -> list[dict[str, Any]]:
    height, width = len(grid), len(grid[0])
    residents: list[tuple[int, int, str]] = [
        (x, y, value)
        for y, row in enumerate(grid)
        for x, value in enumerate(row)
        if value is not None
    ]
    occupied = {(x, y): group for x, y, group in residents}
    result = []
    for ordinal, (x, y, group) in enumerate(residents):
        neighbors = [
            occupied[(nx, ny)]
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if dx or dy
            for nx, ny in [((x + dx) % width, (y + dy) % height)]
            if (nx, ny) in occupied
        ]
        similar = sum(item == group for item in neighbors)
        result.append(
            person(
                f"resident-{ordinal:02d}",
                group,
                x,
                y,
                happy=similar >= 0.3 * len(neighbors),
                similar_nearby=similar,
                total_nearby=len(neighbors),
            )
        )
    return result


def _case_pre_step_stop() -> dict[str, Any]:
    model = source_model(
        "schelling-source/pre-step-stop",
        [person("A", "blue", 0, 0, happy=True), person("B", "orange", 3, 3, happy=True)],
        stop_conditions=all_happy_stop(),
    )
    return {
        "case_id": "pre-step-stop",
        "obligation": 1,
        "model": model,
        "random_tape": tape(),
        "projection_expectations": {"ticks": 0, "stop_reason": "condition:all-happy", "movers": [], "attempts": []},
    }


def _case_frozen_membership() -> dict[str, Any]:
    agents = [
        person("A", "blue", 0, 2, happy=False),
        person("B", "blue", 2, 2, happy=False),
        person("C", "orange", 2, 1, happy=True),
        person("D", "orange", 1, 0, happy=True),
        person("E", "blue", 1, 3, happy=True),
        person("O", "orange", 2, 3, happy=True),
    ]
    model = source_model(
        "schelling-source/frozen-membership",
        agents,
        phases=[move_phase(where=unhappy_selector()), reassess_phase()],
    )
    requests = [traversal("A", 0.1), traversal("B", 0.2)]
    requests += movement_draws("A", [(90.0, 1.0)])
    requests += movement_draws("B", [(0.0, 0.1)])
    return {
        "case_id": "frozen-membership",
        "obligation": 2,
        "model": model,
        "random_tape": tape(*requests),
        "projection_expectations": {
            "ticks": 1,
            "stop_reason": "max_ticks",
            "movers": ["A", "B"],
            "traversal_members": ["A", "B"],
            "positions": {"A": [1.0, 2.0], "B": [2.0, 2.0], "C": [2.0, 1.0]},
            "happy": {"B": True, "C": False},
        },
    }


def _case_rejected_attempt() -> dict[str, Any]:
    model = source_model(
        "schelling-source/rejected-attempt-carries-state",
        [person("M", "blue", 0, 0), person("X", "orange", 1, 0, happy=True)],
        phases=[move_phase(traversal_mode="stable", where=unhappy_selector())],
    )
    return {
        "case_id": "rejected-attempt-carries-state",
        "obligation": 3,
        "model": model,
        "random_tape": tape(*movement_draws("M", [(90.0, 1.0), (180.0, 1.0)])),
        "projection_expectations": {
            "ticks": 1,
            "movers": ["M"],
            "positions": {"M": [0.0, 0.0]},
            "headings": {"M": 270.0},
            "attempts": [
                {"entity": "M", "ordinal": 0, "patch": [1, 0], "accepted": False},
                {"entity": "M", "ordinal": 1, "patch": [0, 0], "accepted": True},
            ],
        },
    }


def _case_own_patch() -> dict[str, Any]:
    model = source_model(
        "schelling-source/own-patch-acceptance",
        [person("M", "blue", 0, 0)],
        phases=[move_phase(traversal_mode="stable", where=unhappy_selector())],
    )
    return {
        "case_id": "own-patch-acceptance",
        "obligation": 4,
        "model": model,
        "random_tape": tape(*movement_draws("M", [(0.0, 0.1)])),
        "projection_expectations": {
            "ticks": 1,
            "movers": ["M"],
            "positions": {"M": [0.0, 0.0]},
            "attempts": [{"entity": "M", "ordinal": 0, "patch": [0, 0], "accepted": True}],
        },
    }


def _case_immediate_visibility() -> dict[str, Any]:
    model = source_model(
        "schelling-source/immediate-occupancy-visibility",
        [person("A", "blue", 0, 0), person("B", "orange", 2, 0, heading=270)],
        phases=[move_phase(where=unhappy_selector())],
    )
    requests = [traversal("A", 0.1), traversal("B", 0.2)]
    requests += movement_draws("A", [(90.0, 1.0)])
    requests += movement_draws("B", [(0.0, 1.0), (0.0, 1.0)])
    return {
        "case_id": "immediate-occupancy-visibility",
        "obligation": 5,
        "model": model,
        "random_tape": tape(*requests),
        "projection_expectations": {
            "ticks": 1,
            "movers": ["A", "B"],
            "positions": {"A": [1.0, 0.0], "B": [0.0, 0.0]},
            "attempts": [
                {"entity": "A", "ordinal": 0, "patch": [1, 0], "accepted": True},
                {"entity": "B", "ordinal": 0, "patch": [1, 0], "accepted": False},
                {"entity": "B", "ordinal": 1, "patch": [0, 0], "accepted": True},
            ],
        },
    }


def _case_wrap_center() -> dict[str, Any]:
    model = source_model(
        "schelling-source/wrap-then-center",
        [person("M", "blue", 4, 4)],
        phases=[move_phase(traversal_mode="stable", where=unhappy_selector())],
    )
    return {
        "case_id": "wrap-then-center",
        "obligation": 6,
        "model": model,
        "random_tape": tape(*movement_draws("M", [(45.0, math.sqrt(2.0))])),
        "projection_expectations": {
            "ticks": 1,
            "movers": ["M"],
            "positions": {"M": [0.0, 0.0]},
            "headings": {"M": 45.0},
            "attempts": [{"entity": "M", "ordinal": 0, "patch": [0, 0], "accepted": True}],
        },
    }


def _case_weighted_metric() -> dict[str, Any]:
    grid = [
        ["A", "A", None, "A", "A"],
        ["A", "B", "A", None, "B"],
        [None, "A", "A", "B", "A"],
        ["A", None, "B", "A", "B"],
        ["B", "A", "B", None, "A"],
    ]
    agents = _neighbor_counts(grid)
    model = source_model(
        "schelling-source/weighted-metric-witness",
        agents,
        phases=[
            {
                "id": "noop",
                "target": "patches",
                "agent_kind": None,
                "read_view": "phase_start",
                "commit_mode": "buffered",
                "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "set", "guard": False, "target": "self", "field": "unused", "value": 0}],
            }
        ],
        initialization=_metric_initialization(),
        metrics=[_source_similarity_metric()],
    )
    model["initial_state"]["globals"] = {"source_similar_sum": 0, "source_total_sum": 0}
    assert sum(item["vars"]["similar_nearby"] for item in agents) == 60
    assert sum(item["vars"]["total_nearby"] for item in agents) == 126
    return {
        "case_id": "weighted-metric-witness",
        "obligation": 7,
        "model": model,
        "random_tape": tape(),
        "projection_expectations": {
            "ticks": 1,
            "metrics": {"source_percent_similar": 100.0 * 60 / 126},
            "source_edge_sums": [60, 126],
            "adaptation_mean_witness": 47.125,
        },
    }


def _case_zero_denominator() -> dict[str, Any]:
    model = source_model(
        "schelling-source/zero-denominator",
        [person("isolate", "blue", 0, 0, happy=True, similar_nearby=0, total_nearby=0)],
        phases=[move_phase(where=unhappy_selector())],
        initialization=_metric_initialization(),
        stop_conditions=all_happy_stop(),
        metrics=[_source_similarity_metric()],
    )
    model["initial_state"]["globals"] = {"source_similar_sum": 0, "source_total_sum": 0}
    return {
        "case_id": "zero-denominator",
        "obligation": 8,
        "model": model,
        "random_tape": tape(),
        "expected_error": {"code": "metric_zero_denominator", "contains": "division by zero"},
    }


def _case_stop_vs_horizon() -> dict[str, Any]:
    model = source_model(
        "schelling-source/stop-versus-horizon",
        [person("M", "blue", 0, 0, happy=False)],
        phases=[move_phase(traversal_mode="stable", where=unhappy_selector()), reassess_phase()],
        stop_conditions=all_happy_stop(),
        max_ticks=1,
    )
    return {
        "case_id": "stop-versus-horizon",
        "obligation": 9,
        "model": model,
        "random_tape": tape(*movement_draws("M", [(0.0, 0.1)])),
        "projection_expectations": {
            "ticks": 1,
            "stop_reason": "max_ticks",
            "positions": {"M": [0.0, 0.0]},
            "happy": {"M": True},
            "on_next_go": {"max_ticks": 2, "ticks": 1, "stop_reason": "condition:all-happy"},
        },
    }


def cases() -> list[dict[str, Any]]:
    """Return independent mutable copies for verifier and test consumers."""
    return copy.deepcopy(
        [
            _case_pre_step_stop(),
            _case_frozen_membership(),
            _case_rejected_attempt(),
            _case_own_patch(),
            _case_immediate_visibility(),
            _case_wrap_center(),
            _case_weighted_metric(),
            _case_zero_denominator(),
            _case_stop_vs_horizon(),
        ]
    )


def setup_lifecycle_case() -> dict[str, Any]:
    """Two-patch setup fixture proving conditional sprout and later-init eligibility."""
    model = source_model(
        "schelling-source/setup-lifecycle",
        [],
        width=2,
        height=1,
        phases=[
            {
                "id": "noop",
                "target": "patches",
                "agent_kind": None,
                "read_view": "phase_start",
                "commit_mode": "buffered",
                "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "set", "guard": False, "target": "self", "field": "unused", "value": 0}],
            }
        ],
        initialization=[
            {
                "id": "source-setup",
                "target": "patches",
                "agent_kind": None,
                "read_view": "current",
                "commit_mode": "immediate",
                "traversal": "random",
                "random_address": "setup.patch-order",
                "operations": [
                    {
                        "op": "sprout",
                        "guard": random_expr("bernoulli", "setup.occupied", [0.5]),
                        "kind": "person",
                        "count": 1,
                        "vars": {
                            "group": random_expr("choice", "setup.group", [["blue", "orange"]]),
                            "heading": random_expr("uniform", "setup.heading", [0, 360]),
                            "happy": False,
                            "ready": False,
                        },
                        "address": "setup.sprout",
                    }
                ],
            },
            {
                "id": "post-setup-derived",
                "target": "agents",
                "agent_kind": "person",
                "read_view": "current",
                "commit_mode": "immediate",
                "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "set", "guard": None, "target": "self", "field": "ready", "value": True}],
            },
        ],
    )
    requests = [
        tape_entry(
            tick=-1, phase="source-setup", address="setup.patch-order",
            entity_id="patch:0:0", occurrence=0, distribution="traversal_key", args=[], value=0.1,
        ),
        tape_entry(
            tick=-1, phase="source-setup", address="setup.patch-order",
            entity_id="patch:1:0", occurrence=0, distribution="traversal_key", args=[], value=0.2,
        ),
        tape_entry(
            tick=-1, phase="source-setup", address="setup.occupied",
            entity_id="patch:0:0", occurrence=0, distribution="bernoulli", args=[0.5], value=True,
        ),
        tape_entry(
            tick=-1, phase="source-setup", address="setup.group", entity_id="patch:0:0",
            occurrence=0, distribution="choice", args=[["blue", "orange"]], value="orange",
        ),
        tape_entry(
            tick=-1, phase="source-setup", address="setup.heading", entity_id="patch:0:0",
            occurrence=0, distribution="uniform", args=[0, 360], value=123.5,
        ),
        tape_entry(
            tick=-1, phase="source-setup", address="setup.occupied",
            entity_id="patch:1:0", occurrence=0, distribution="bernoulli", args=[0.5], value=False,
        ),
    ]
    return {"model": model, "random_tape": tape(*requests)}
