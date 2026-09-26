"""Readable deterministic executor for ``abm-tick-plan/v1``."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import operator
from typing import Any

# Ensure the profile's compiler registration exists even when this module is
# imported directly instead of through the package root.
from sim_engine_compiler.compiler import compile_model as _compile_model  # noqa: F401
from sim_engine_compiler.compiler.registry import register_runtime
from sim_engine_compiler.ir.abm import ABM_PROFILE, I64_MAX, I64_MIN, AbmTickPlan


class AbmRuntimeError(ValueError):
    pass


class AbmTickRuntime:
    def __init__(self, plan: AbmTickPlan | dict[str, Any], *, seed: int = 0):
        self.plan = plan if isinstance(plan, AbmTickPlan) else AbmTickPlan.from_dict(plan)
        if type(seed) is not int or not I64_MIN <= seed <= I64_MAX:
            raise AbmRuntimeError("seed must be a signed 64-bit integer")
        self.seed = seed
        self.payload = self.plan.payload
        initial = copy.deepcopy(self.payload["initial_state"])
        self.globals = initial["globals"]
        self.patches = {item["id"]: item for item in initial["patches"]}
        self.patch_at = {(item["x"], item["y"]): item["id"] for item in initial["patches"]}
        self.agents = {item["id"]: item for item in initial["agents"]}
        self.eligible_tick = {identity: 0 for identity in self.agents}
        self.events: list[dict[str, Any]] = []
        self.random_requests: list[dict[str, Any]] = []
        self._random_occurrences: dict[tuple[Any, ...], int] = {}
        self._birth_occurrences: dict[tuple[Any, ...], int] = {}
        self.tick = 0
        self.phase = "initial"

    def _state_copy(self) -> dict[str, Any]:
        return {
            "globals": copy.deepcopy(self.globals),
            "patches": {identity: copy.deepcopy(value) for identity, value in self.patches.items()},
            "agents": {identity: copy.deepcopy(value) for identity, value in self.agents.items()},
        }

    def _normalize_position(self, x: float, y: float) -> tuple[float, float]:
        topology = self.payload["topology"]
        width, height = topology["width"], topology["height"]
        if topology["kind"] == "torus":
            return ((x + 0.5) % width - 0.5, (y + 0.5) % height - 0.5)
        if not (-0.5 <= x < width - 0.5 and -0.5 <= y < height - 0.5):
            raise AbmRuntimeError(f"finite-grid move out of bounds: ({x}, {y})")
        return x, y

    def _patch_coordinate(self, actor: dict[str, Any]) -> tuple[int, int]:
        topology = self.payload["topology"]
        x, y = math.floor(actor["x"] + 0.5), math.floor(actor["y"] + 0.5)
        if topology["kind"] == "torus":
            return x % topology["width"], y % topology["height"]
        if (x, y) not in self.patch_at:
            raise AbmRuntimeError(f"position has no finite-grid patch: ({actor['x']}, {actor['y']})")
        return x, y

    def _patch_here(self, actor: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        if "kind" not in actor:
            return state["patches"][actor["id"]]
        coordinate = self._patch_coordinate(actor)
        return state["patches"][self.patch_at[coordinate]]

    @staticmethod
    def _field(record: dict[str, Any], field: str) -> Any:
        if field in {"id", "kind", "x", "y"} and field in record:
            return record[field]
        if field not in record["vars"]:
            raise AbmRuntimeError(f"unknown state field {field!r} on {record['id']}")
        return record["vars"][field]

    def _neighbors(self, actor: dict[str, Any], neighborhood: str) -> list[tuple[int, int]]:
        x, y = self._patch_coordinate(actor)
        offsets = (
            [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
            if neighborhood == "moore"
            else [(0, -1), (-1, 0), (1, 0), (0, 1)]
        )
        topology = self.payload["topology"]
        result: set[tuple[int, int]] = set()
        for dx, dy in offsets:
            coordinate = (x + dx, y + dy)
            if topology["kind"] == "torus":
                coordinate = (coordinate[0] % topology["width"], coordinate[1] % topology["height"])
            if coordinate in self.patch_at and coordinate != (x, y):
                result.add(coordinate)
        return sorted(result, key=lambda item: self.patch_at[item])

    def _random(self, address: str, entity_id: str, distribution: str,
                args: list[Any]) -> Any:
        key = (self.tick, self.phase, address, entity_id)
        occurrence = self._random_occurrences.get(key, 0)
        self._random_occurrences[key] = occurrence + 1
        identity = [self.seed, self.tick, self.phase, address, entity_id, occurrence]
        raw = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).digest()
        unit = int.from_bytes(raw[:8], "big") / 2**64
        if distribution == "traversal_key":
            value = unit
        elif distribution == "uniform":
            if len(args) != 2 or not all(type(item) in (int, float) and not isinstance(item, bool) for item in args):
                raise AbmRuntimeError("uniform requires two numeric arguments")
            value = args[0] + (args[1] - args[0]) * unit
        elif distribution == "integer":
            if len(args) != 2 or not all(type(item) is int for item in args) or args[1] <= args[0]:
                raise AbmRuntimeError("integer requires integer [low, high) bounds")
            value = args[0] + int(unit * (args[1] - args[0]))
        elif distribution == "bernoulli":
            if len(args) != 1 or type(args[0]) not in (int, float) or isinstance(args[0], bool) or not 0 <= args[0] <= 1:
                raise AbmRuntimeError("bernoulli requires probability in [0, 1]")
            value = unit < args[0]
        elif distribution == "choice":
            if len(args) != 1 or not isinstance(args[0], list) or not args[0]:
                raise AbmRuntimeError("choice requires one non-empty list argument")
            value = copy.deepcopy(args[0][min(int(unit * len(args[0])), len(args[0]) - 1)])
        else:
            raise AbmRuntimeError(f"unsupported random distribution {distribution!r}")
        self.random_requests.append({
            "sequence": len(self.random_requests), "tick": self.tick, "phase": self.phase,
            "address": address, "entity_id": entity_id, "distribution": distribution,
            "args": copy.deepcopy(args), "value": copy.deepcopy(value),
        })
        return value

    def _eval(self, expression: Any, actor: dict[str, Any] | None,
              state: dict[str, Any], outer: dict[str, Any] | None = None) -> Any:
        if not isinstance(expression, dict):
            return copy.deepcopy(expression)
        op = expression["op"]
        if op == "get":
            scope = expression["scope"]
            if scope == "globals":
                try:
                    return state["globals"][expression["field"]]
                except KeyError as exc:
                    raise AbmRuntimeError(f"unknown global {expression['field']!r}") from exc
            if scope == "outer":
                if outer is None:
                    raise AbmRuntimeError("outer requires an aggregate predicate context")
                return self._field(outer, expression["field"])
            if actor is None:
                if scope == "self":
                    try:
                        return state["globals"][expression["field"]]
                    except KeyError as exc:
                        raise AbmRuntimeError(f"unknown global {expression['field']!r}") from exc
                raise AbmRuntimeError(f"{scope} requires an entity context")
            target = actor if scope == "self" else self._patch_here(actor, state)
            return self._field(target, expression["field"])
        if op == "unary":
            value = self._eval(expression["value"], actor, state, outer)
            if expression["operator"] == "not":
                if type(value) is not bool:
                    raise AbmRuntimeError("not requires boolean")
                return not value
            if type(value) not in (int, float) or isinstance(value, bool):
                raise AbmRuntimeError("neg requires number")
            return -value
        if op == "binary":
            left = self._eval(expression["left"], actor, state, outer)
            right = self._eval(expression["right"], actor, state, outer)
            symbol = expression["operator"]
            if symbol in {"and", "or"}:
                if type(left) is not bool or type(right) is not bool:
                    raise AbmRuntimeError(f"{symbol} requires booleans")
                return left and right if symbol == "and" else left or right
            if symbol in {"+", "-", "*", "/", "%", "<", "<=", ">", ">="}:
                if any(type(value) not in (int, float) or isinstance(value, bool) for value in (left, right)):
                    raise AbmRuntimeError(f"{symbol} requires numbers")
            functions = {"+": operator.add, "-": operator.sub, "*": operator.mul,
                         "/": operator.truediv, "%": operator.mod, "==": operator.eq,
                         "!=": operator.ne, "<": operator.lt, "<=": operator.le,
                         ">": operator.gt, ">=": operator.ge}
            try:
                return functions[symbol](left, right)
            except ZeroDivisionError as exc:
                raise AbmRuntimeError("division or modulo by zero") from exc
        if op == "random":
            if actor is None:
                entity_id = "$global"
            else:
                entity_id = actor["id"]
            args = [self._eval(item, actor, state, outer) for item in expression["args"]]
            return self._random(expression["address"], entity_id, expression["distribution"], args)
        if op == "count":
            source = expression["source"]
            if source == "agents":
                candidates = list(state["agents"].values())
                if expression["agent_kind"] is not None:
                    candidates = [item for item in candidates if item["kind"] == expression["agent_kind"]]
            elif source == "agents_here":
                if actor is None:
                    raise AbmRuntimeError("agents_here count requires an entity context")
                coordinate = self._patch_coordinate(actor)
                candidates = [item for item in state["agents"].values()
                              if self._patch_coordinate(item) == coordinate]
                if expression["agent_kind"] is not None:
                    candidates = [item for item in candidates if item["kind"] == expression["agent_kind"]]
            elif source == "patches":
                candidates = list(state["patches"].values())
            else:
                if actor is None:
                    raise AbmRuntimeError("neighbor count requires an entity context")
                coordinates = set(self._neighbors(actor, expression["neighborhood"]))
                if expression["agent_kind"] is None:
                    candidates = [state["patches"][self.patch_at[item]] for item in coordinates]
                else:
                    candidates = [item for item in state["agents"].values()
                                  if (expression["agent_kind"] == "*" or item["kind"] == expression["agent_kind"])
                                  and self._patch_coordinate(item) in coordinates]
            where = expression["where"]
            if where is None:
                return len(candidates)
            count = 0
            for candidate in candidates:
                result = self._eval(where, candidate, state, actor)
                if type(result) is not bool:
                    raise AbmRuntimeError("count predicate must be boolean")
                count += int(result)
            return count
        raise AbmRuntimeError(f"unknown expression {op!r}")

    def _event(self, kind: str, entity: str, details: dict[str, Any]) -> None:
        self.events.append({"sequence": len(self.events), "tick": self.tick, "phase": self.phase,
                            "kind": kind, "entity": entity, "details": copy.deepcopy(details)})

    def _write(self, target: str, actor: dict[str, Any], field: str, value: Any,
               kind: str, state: dict[str, Any]) -> None:
        if target == "globals":
            before = self.globals.get(field)
            after = value if kind == "set" else self._add(before, value)
            self.globals[field] = copy.deepcopy(after)
            identity = "$global"
        else:
            record = actor if target == "self" else self._patch_here(actor, self._state_copy())
            live = self.patches.get(record["id"]) or self.agents.get(record["id"])
            if live is None:
                return
            before = live["vars"].get(field)
            after = value if kind == "set" else self._add(before, value)
            live["vars"][field] = copy.deepcopy(after)
            identity = live["id"]
        self._event(kind, identity, {"target": target, "field": field,
                                     "before": copy.deepcopy(before), "after": copy.deepcopy(after)})

    @staticmethod
    def _add(before: Any, delta: Any) -> Any:
        if any(type(value) not in (int, float) or isinstance(value, bool) for value in (before, delta)):
            raise AbmRuntimeError("increment requires existing numeric field and numeric value")
        return before + delta

    def _apply_action(self, action: tuple[Any, ...]) -> bool:
        kind = action[0]
        if kind in {"set", "increment"}:
            _, target, actor_id, field, value, actor_snapshot = action
            actor = self.agents.get(actor_id) or self.patches.get(actor_id) or actor_snapshot
            self._write(target, actor, field, value, kind, self._state_copy())
        elif kind == "move":
            _, actor_id, x, y, heading = action
            actor = self.agents.get(actor_id)
            if actor is None:
                return False
            before = [actor["x"], actor["y"]]
            actor["x"], actor["y"] = self._normalize_position(x, y)
            if heading is not None:
                actor["vars"]["heading"] = heading
            self._event("moved", actor_id, {"from": before, "to": [actor["x"], actor["y"]]})
        elif kind == "birth":
            _, child, parent_id = action
            if child["id"] in self.agents:
                raise AbmRuntimeError(f"duplicate birth identity {child['id']}")
            self.agents[child["id"]] = child
            self.eligible_tick[child["id"]] = self.tick + 1
            self._event("born", child["id"], {"parent": parent_id, "kind": child["kind"],
                                               "x": child["x"], "y": child["y"]})
        elif kind == "death":
            _, actor_id, killer = action
            if self.agents.pop(actor_id, None) is None:
                return False
            self.eligible_tick.pop(actor_id, None)
            self._event("died", actor_id, {} if killer is None else {"by": killer})
        return kind == "death" and action[2] is None

    def _operation_action(self, operation: dict[str, Any], actor: dict[str, Any],
                          state: dict[str, Any]) -> list[tuple[Any, ...]]:
        guard = True if operation["guard"] is None else self._eval(operation["guard"], actor, state)
        if type(guard) is not bool:
            raise AbmRuntimeError("operation guard must be boolean")
        if not guard:
            return []
        op = operation["op"]
        if op in {"set", "increment"}:
            value = self._eval(operation["value"], actor, state)
            return [(op, operation["target"], actor["id"], operation["field"], value, actor)]
        if op == "death":
            if actor["id"] in self.patches:
                raise AbmRuntimeError("patches cannot die")
            if operation["mode"] == "self":
                return [("death", actor["id"], None)]
            coordinate = self._patch_coordinate(actor)
            candidates = sorted(
                (item for item in state["agents"].values()
                 if item["id"] != actor["id"]
                 and self._patch_coordinate(item) == coordinate
                 and (operation["agent_kind"] is None or item["kind"] == operation["agent_kind"])),
                key=lambda item: item["id"],
            )
            if not candidates:
                return []
            selected = self._random(operation["address"], actor["id"], "integer", [0, len(candidates)])
            return [("death", candidates[selected]["id"], actor["id"])]
        if op == "birth":
            raw_count = self._eval(operation["count"], actor, state)
            if type(raw_count) is not int or raw_count < 0:
                raise AbmRuntimeError("birth count must be a nonnegative integer")
            result = []
            for _ in range(raw_count):
                key = (self.tick, self.phase, actor["id"], operation["address"])
                ordinal = self._birth_occurrences.get(key, 0)
                self._birth_occurrences[key] = ordinal + 1
                identity = f"{actor['id']}::{operation['address']}::{self.tick}::{ordinal}"
                variables = {field: self._eval(expr, actor, state) for field, expr in operation["vars"].items()}
                x, y = actor["x"], actor["y"]
                movement = operation["child_move"]
                if movement is not None:
                    heading_max = self._eval(movement["heading"], actor, state)
                    distance = self._eval(movement["distance"], actor, state)
                    if (type(heading_max) not in (int, float) or isinstance(heading_max, bool)
                            or heading_max <= 0 or type(distance) not in (int, float)
                            or isinstance(distance, bool)):
                        raise AbmRuntimeError("child movement requires positive heading range and numeric distance")
                    heading = self._random(movement["address"], actor["id"], "uniform", [0, heading_max])
                    variables["heading"] = heading
                    radians = math.radians(heading)
                    x, y = self._normalize_position(x + distance * math.sin(radians),
                                                    y + distance * math.cos(radians))
                result.append(("birth", {"id": identity, "kind": operation["kind"],
                                          "x": x, "y": y, "vars": variables}, actor["id"]))
            return result
        mode = operation["mode"]
        if actor["id"] in self.patches:
            raise AbmRuntimeError("patches cannot move")
        if mode in {"position", "offset"}:
            x = self._eval(operation["x"], actor, state)
            y = self._eval(operation["y"], actor, state)
            if any(type(value) not in (int, float) or isinstance(value, bool) for value in (x, y)):
                raise AbmRuntimeError("movement coordinates must be numeric")
            if mode == "offset":
                x, y = actor["x"] + x, actor["y"] + y
            x, y = self._normalize_position(x, y)
            return [("move", actor["id"], x, y, None)]
        if mode == "heading_step":
            step = operation["heading_step"]
            heading = self._field(actor, "heading")
            right_max = self._eval(step["right_max"], actor, state)
            left_max = self._eval(step["left_max"], actor, state)
            distance = self._eval(step["distance"], actor, state)
            if (type(heading) not in (int, float) or isinstance(heading, bool)
                    or type(right_max) is not int or right_max <= 0
                    or type(left_max) is not int or left_max <= 0
                    or type(distance) not in (int, float) or isinstance(distance, bool)):
                raise AbmRuntimeError("heading_step requires heading, positive integer turn bounds, and numeric distance")
            right = self._random(step["right_address"], actor["id"], "integer", [0, right_max])
            left = self._random(step["left_address"], actor["id"], "integer", [0, left_max])
            heading = (heading + right - left) % 360
            radians = math.radians(heading)
            x, y = self._normalize_position(actor["x"] + distance * math.sin(radians),
                                            actor["y"] + distance * math.cos(radians))
            return [("move", actor["id"], x, y, heading)]
        if mode == "random_global_empty":
            occupied = {self._patch_coordinate(item) for item in state["agents"].values()
                        }
            coordinates = sorted((coordinate for coordinate in self.patch_at if coordinate not in occupied),
                                 key=lambda item: (item[1], item[0], self.patch_at[item]))
        else:
            coordinates = self._neighbors(actor, operation["neighborhood"])
        if mode == "random_empty":
            occupied = {self._patch_coordinate(item) for item in state["agents"].values()
                        if item["id"] != actor["id"]}
            coordinates = [item for item in coordinates if item not in occupied]
        if not coordinates:
            return []
        choice = self._random(operation["address"], actor["id"], "integer", [0, len(coordinates)])
        x, y = coordinates[choice]
        return [("move", actor["id"], x, y, None)]

    def _run_phase(self, phase: dict[str, Any]) -> None:
        self.phase = phase["id"]
        snapshot = self._state_copy()
        table = snapshot[phase["target"]]
        actors = [item for item in table.values()
                  if phase["target"] == "patches" or
                  (self.eligible_tick.get(item["id"], self.tick + 1) <= self.tick and
                   (phase["agent_kind"] is None or item["kind"] == phase["agent_kind"]))]
        actors.sort(key=lambda item: item["id"])
        if phase["traversal"] == "random":
            actors.sort(key=lambda item: (self._random(phase["random_address"], item["id"],
                                                        "traversal_key", []), item["id"]))
        pending: list[tuple[Any, ...]] = []
        for initial_actor in actors:
            if initial_actor["id"] not in self.agents and initial_actor["id"] not in self.patches:
                continue
            dead = False
            for operation in phase["operations"]:
                if dead:
                    break
                view = snapshot if phase["read_view"] == "phase_start" else self._state_copy()
                actor = view[phase["target"]].get(initial_actor["id"])
                if actor is None:
                    break
                actions = self._operation_action(operation, actor, view)
                if phase["commit_mode"] == "buffered":
                    pending.extend(actions)
                    dead = any(action[0] == "death" and action[1] == actor["id"]
                               and action[2] is None for action in actions)
                else:
                    for action in actions:
                        dead = self._apply_action(action) or dead
        if phase["commit_mode"] == "buffered":
            for action in pending:
                self._apply_action(action)

    def _stop_condition(self) -> str | None:
        state = self._state_copy()
        for condition in self.payload["stop_conditions"]:
            value = self._eval(condition["when"], None, state)
            if type(value) is not bool:
                raise AbmRuntimeError("stop condition must be boolean")
            if value:
                return condition["id"]
        return None

    def _metrics(self) -> dict[str, Any]:
        state = self._state_copy()
        result = {}
        for metric in self.payload["metrics"]:
            if metric["reducer"] == "expression":
                result[metric["id"]] = self._eval(metric["expression"], None, state)
                continue
            if metric["source"] == "globals":
                candidates = [{"id": "$global", "vars": state["globals"]}]
            else:
                candidates = list(state[metric["source"]].values())
            if metric["where"] is not None:
                selected = []
                for candidate in candidates:
                    keep = self._eval(metric["where"], candidate, state)
                    if type(keep) is not bool:
                        raise AbmRuntimeError("metric predicate must be boolean")
                    if keep:
                        selected.append(candidate)
                candidates = selected
            reducer = metric["reducer"]
            if reducer == "count":
                value = len(candidates)
            else:
                values = [candidate["vars"].get(metric["field"]) for candidate in candidates]
                if reducer == "value":
                    value = values[0] if values else None
                elif not values:
                    value = 0 if reducer == "sum" else None
                elif reducer == "sum":
                    value = sum(values)
                elif reducer == "mean":
                    value = sum(values) / len(values)
                elif reducer == "min":
                    value = min(values)
                else:
                    value = max(values)
            result[metric["id"]] = value
        return result

    def run(self) -> dict[str, Any]:
        stopped = self._stop_condition()
        completed = 0
        if stopped is not None:
            self.phase = "stop"
            self._event("stopped", stopped, {})
            reason = f"condition:{stopped}"
        else:
            reason = "max_ticks"
            for tick in range(self.payload["max_ticks"]):
                self.tick = tick
                for phase in self.payload["phases"]:
                    self._run_phase(phase)
                completed += 1
                stopped = self._stop_condition()
                if stopped is not None:
                    self.phase = "stop"
                    self._event("stopped", stopped, {})
                    reason = f"condition:{stopped}"
                    break
        state = {
            "globals": copy.deepcopy(self.globals),
            "patches": [copy.deepcopy(self.patches[key]) for key in sorted(self.patches)],
            "agents": [copy.deepcopy(self.agents[key]) for key in sorted(self.agents)],
        }
        return {"profile": ABM_PROFILE, "seed": self.seed, "ticks": completed,
                "stop_reason": reason, "state": state, "events": copy.deepcopy(self.events),
                "random_requests": copy.deepcopy(self.random_requests), "metrics": self._metrics()}


def run_abm_plan(plan: AbmTickPlan | dict[str, Any], *, seed: int = 0) -> dict[str, Any]:
    return AbmTickRuntime(plan, seed=seed).run()


def run_abm_batch(plan: AbmTickPlan | dict[str, Any], requests: list[dict[str, int]],
                  *, workers: int = 1) -> list[dict[str, Any]]:
    """Run isolated samples and return stable ``sample_index`` order.

    The Python reference stays deliberately serial; ``workers`` is validated so
    callers can exercise the same request contract as parallel backends without
    making scheduling observable.
    """
    if type(workers) is not int or workers <= 0:
        raise AbmRuntimeError("workers must be a positive integer")
    if not isinstance(requests, list):
        raise AbmRuntimeError("batch requests must be a list")
    normalized = []
    seen = set()
    for index, request in enumerate(requests):
        if not isinstance(request, dict) or set(request) != {"sample_index", "seed"}:
            raise AbmRuntimeError(f"invalid batch request at index {index}")
        sample_index, seed = request["sample_index"], request["seed"]
        if (type(sample_index) is not int or not 0 <= sample_index <= I64_MAX
                or sample_index in seen or type(seed) is not int or not I64_MIN <= seed <= I64_MAX):
            raise AbmRuntimeError(f"invalid or duplicate sample identity at index {index}")
        seen.add(sample_index)
        normalized.append((sample_index, seed))
    sealed = plan if isinstance(plan, AbmTickPlan) else AbmTickPlan.from_dict(plan)
    results = [{"sample_index": sample_index, "result": AbmTickRuntime(sealed, seed=seed).run()}
               for sample_index, seed in normalized]
    return sorted(results, key=lambda item: item["sample_index"])


register_runtime(ABM_PROFILE, AbmTickRuntime)
