"""Contracts for the deliberately small ``abm-tick-v1`` execution profile.

The three artifacts are separate, reloadable, checksum-protected envelopes.  The
plan contains only JSON values so that an independent runtime can validate it
without importing model authoring code.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import math
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError


ABM_BUSINESS_VERSION = "abm-business-ir/v1"
ABM_CORE_VERSION = "abm-core-ir/v1"
ABM_PLAN_VERSION = "abm-tick-plan/v1"
ABM_PROFILE = "abm-tick-v1"

TOPOLOGIES = frozenset({"finite", "torus"})
TARGETS = frozenset({"patches", "agents"})
READ_VIEWS = frozenset({"phase_start", "current"})
COMMIT_MODES = frozenset({"buffered", "immediate"})
TRAVERSALS = frozenset({"stable", "random"})
OPERATION_NAMES = frozenset({"set", "increment", "move", "birth", "death"})
EXPRESSION_NAMES = frozenset({"get", "binary", "unary", "count", "random"})
NEIGHBORHOODS = frozenset({"moore", "von_neumann"})
I64_MIN = -(2**63)
I64_MAX = 2**63 - 1
MAX_GRID_CELLS = 1_000_000


def canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CompilationError("artifact must contain finite JSON values", code="invalid_abm_ir") from exc
    return hashlib.sha256(encoded).hexdigest()


def _reject(path: str, message: str, code: str = "invalid_abm_ir") -> None:
    raise CompilationError(message, code=code, source_path=path)


def _object(value: Any, fields: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _reject(path, f"expected fields {sorted(fields)}")
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _reject(path, "expected non-empty stable business ID")
    return value


def _number(value: Any, path: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        _reject(path, "expected finite number")
    if type(value) is int and not I64_MIN <= value <= I64_MAX:
        _reject(path, "integer is outside signed 64-bit range")


def _json_value(value: Any, path: str) -> None:
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int:
        if not I64_MIN <= value <= I64_MAX:
            _reject(path, "integer is outside signed 64-bit range")
        return
    if type(value) is float:
        if not math.isfinite(value):
            _reject(path, "expected finite JSON number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for key, item in value.items():
            _json_value(item, f"{path}.{key}")
        return
    _reject(path, "expected JSON value")


def validate_expression(value: Any, path: str) -> None:
    if value is None or type(value) in (str, bool, int, float) or isinstance(value, list):
        _json_value(value, path)
        return
    if not isinstance(value, dict) or value.get("op") not in EXPRESSION_NAMES:
        _reject(path, "unknown expression", "unsupported_operation")
    op = value["op"]
    if op == "get":
        _object(value, {"op", "scope", "field"}, path)
        if value["scope"] not in {"self", "outer", "patch_here", "globals"}:
            _reject(f"{path}.scope", "unknown state scope")
        _identifier(value["field"], f"{path}.field")
    elif op == "binary":
        _object(value, {"op", "operator", "left", "right"}, path)
        if value["operator"] not in {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "and", "or"}:
            _reject(f"{path}.operator", "unknown binary operator", "unsupported_operation")
        validate_expression(value["left"], f"{path}.left")
        validate_expression(value["right"], f"{path}.right")
    elif op == "unary":
        _object(value, {"op", "operator", "value"}, path)
        if value["operator"] not in {"not", "neg"}:
            _reject(f"{path}.operator", "unknown unary operator", "unsupported_operation")
        validate_expression(value["value"], f"{path}.value")
    elif op == "count":
        _object(value, {"op", "source", "agent_kind", "neighborhood", "where"}, path)
        if value["source"] not in {"agents", "agents_here", "patches", "neighbors"}:
            _reject(f"{path}.source", "unknown count source")
        if value["agent_kind"] is not None:
            _identifier(value["agent_kind"], f"{path}.agent_kind")
        if value["source"] == "neighbors":
            if value["neighborhood"] not in NEIGHBORHOODS:
                _reject(f"{path}.neighborhood", "unsupported neighborhood")
        elif value["neighborhood"] is not None:
            _reject(f"{path}.neighborhood", "neighborhood only applies to neighbors")
        if value["where"] is not None:
            validate_expression(value["where"], f"{path}.where")
    else:
        _object(value, {"op", "distribution", "address", "args"}, path)
        if value["distribution"] not in {"uniform", "integer", "bernoulli", "choice"}:
            _reject(f"{path}.distribution", "unsupported random distribution", "unsupported_random")
        _identifier(value["address"], f"{path}.address")
        if not isinstance(value["args"], list) or not value["args"]:
            _reject(f"{path}.args", "random distribution arguments required")
        expected_args = {"uniform": 2, "integer": 2, "bernoulli": 1, "choice": 1}
        if len(value["args"]) != expected_args[value["distribution"]]:
            _reject(f"{path}.args", f"{value['distribution']} has invalid argument count")
        for index, argument in enumerate(value["args"]):
            validate_expression(argument, f"{path}.args[{index}]")
        if value["distribution"] == "uniform" and all(
            type(argument) in (int, float) and not isinstance(argument, bool)
            for argument in value["args"]
        ) and value["args"][1] <= value["args"][0]:
            _reject(f"{path}.args", "uniform requires increasing bounds", "unsupported_random")
        if value["distribution"] == "integer" and all(type(argument) is int for argument in value["args"]):
            low, high = value["args"]
            if high <= low or high - low > I64_MAX:
                _reject(f"{path}.args", "integer requires representable increasing bounds", "unsupported_random")


def validate_operation(value: Any, path: str) -> None:
    if not isinstance(value, dict) or value.get("op") not in OPERATION_NAMES:
        _reject(path, "unknown ABM operation", "unsupported_operation")
    op = value["op"]
    common = {"op", "guard"}
    if op in {"set", "increment"}:
        _object(value, common | {"target", "field", "value"}, path)
        if value["target"] not in {"self", "patch_here", "globals"}:
            _reject(f"{path}.target", "unknown write target")
        _identifier(value["field"], f"{path}.field")
        validate_expression(value["value"], f"{path}.value")
    elif op == "move":
        _object(value, common | {"mode", "x", "y", "neighborhood", "address", "heading_step"}, path)
        if value["mode"] not in {"position", "offset", "random_neighbor", "random_empty", "random_global_empty", "heading_step"}:
            _reject(f"{path}.mode", "unsupported movement mode", "unsupported_operation")
        if value["mode"] in {"position", "offset"}:
            if (value["x"] is None or value["y"] is None or value["neighborhood"] is not None
                    or value["address"] is not None or value["heading_step"] is not None):
                _reject(path, "position/offset movement requires x and y only")
            validate_expression(value["x"], f"{path}.x")
            validate_expression(value["y"], f"{path}.y")
        elif value["mode"] in {"random_neighbor", "random_empty"}:
            if (value["x"] is not None or value["y"] is not None
                    or value["neighborhood"] not in NEIGHBORHOODS or value["heading_step"] is not None):
                _reject(path, "random movement requires a supported neighborhood")
            _identifier(value["address"], f"{path}.address")
        elif value["mode"] == "random_global_empty":
            if any(value[key] is not None for key in ("x", "y", "neighborhood", "heading_step")):
                _reject(path, "global empty movement only accepts a random address")
            _identifier(value["address"], f"{path}.address")
        else:
            if any(value[key] is not None for key in ("x", "y", "neighborhood", "address")):
                _reject(path, "heading movement only accepts heading_step")
            step = _object(value["heading_step"], {"right_max", "left_max", "distance", "right_address", "left_address"}, f"{path}.heading_step")
            for field in ("right_max", "left_max", "distance"):
                validate_expression(step[field], f"{path}.heading_step.{field}")
            _identifier(step["right_address"], f"{path}.heading_step.right_address")
            _identifier(step["left_address"], f"{path}.heading_step.left_address")
    elif op == "birth":
        _object(value, common | {"kind", "count", "vars", "address", "child_move"}, path)
        _identifier(value["kind"], f"{path}.kind")
        validate_expression(value["count"], f"{path}.count")
        _identifier(value["address"], f"{path}.address")
        if not isinstance(value["vars"], dict):
            _reject(f"{path}.vars", "expected variable expression map")
        for field, expression in value["vars"].items():
            _identifier(field, f"{path}.vars")
            validate_expression(expression, f"{path}.vars.{field}")
        if value["child_move"] is not None:
            movement = _object(value["child_move"], {"mode", "heading", "address", "distance"}, f"{path}.child_move")
            validate_expression(movement["distance"], f"{path}.child_move.distance")
            if movement["mode"] == "random_uniform":
                if movement["heading"] is None:
                    _reject(f"{path}.child_move.heading", "random_uniform requires heading range")
                validate_expression(movement["heading"], f"{path}.child_move.heading")
                _identifier(movement["address"], f"{path}.child_move.address")
            elif movement["mode"] == "inherit_heading":
                if movement["heading"] is not None or movement["address"] is not None:
                    _reject(path, "inherit_heading requires null heading and address")
            else:
                _reject(f"{path}.child_move.mode", "unsupported child movement mode", "unsupported_operation")
    else:
        _object(value, common | {"mode", "agent_kind", "address"}, path)
        if value["mode"] not in {"self", "random_agent_here"}:
            _reject(f"{path}.mode", "unsupported death mode", "unsupported_operation")
        if value["mode"] == "self":
            if value["agent_kind"] is not None or value["address"] is not None:
                _reject(path, "self death has no target filter or random address")
        else:
            if value["agent_kind"] is not None:
                _identifier(value["agent_kind"], f"{path}.agent_kind")
            _identifier(value["address"], f"{path}.address")
    if value["guard"] is not None:
        validate_expression(value["guard"], f"{path}.guard")


def validate_payload(payload: Any, *, layer: str) -> None:
    fields = {"model_id", "profile", "topology", "initial_state", "phases", "stop_conditions", "metrics", "max_ticks"}
    _object(payload, fields, layer)
    _identifier(payload["model_id"], f"{layer}.model_id")
    if payload["profile"] != ABM_PROFILE:
        _reject(f"{layer}.profile", "unsupported ABM profile", "unsupported_profile")
    topology = _object(payload["topology"], {"kind", "width", "height"}, f"{layer}.topology")
    if topology["kind"] not in TOPOLOGIES:
        _reject(f"{layer}.topology.kind", "unsupported topology", "unsupported_topology")
    if (type(topology["width"]) is not int or type(topology["height"]) is not int
            or not 0 < topology["width"] <= I64_MAX or not 0 < topology["height"] <= I64_MAX):
        _reject(f"{layer}.topology", "positive integer dimensions required")
    if topology["width"] > I64_MAX // topology["height"]:
        _reject(f"{layer}.topology", "grid area exceeds signed 64-bit range")
    grid_area = topology["width"] * topology["height"]
    if grid_area > MAX_GRID_CELLS:
        _reject(f"{layer}.topology", f"grid exceeds executable limit of {MAX_GRID_CELLS} patches")
    if type(payload["max_ticks"]) is not int or not 0 < payload["max_ticks"] <= I64_MAX:
        _reject(f"{layer}.max_ticks", "positive integer tick limit required")

    state = _object(payload["initial_state"], {"globals", "patches", "agents"}, f"{layer}.initial_state")
    if not isinstance(state["globals"], dict) or not isinstance(state["patches"], list) or not isinstance(state["agents"], list):
        _reject(f"{layer}.initial_state", "invalid state tables")
    _json_value(state["globals"], f"{layer}.initial_state.globals")
    patch_ids: set[str] = set()
    coordinates: set[tuple[int, int]] = set()
    for index, patch in enumerate(state["patches"]):
        path = f"{layer}.initial_state.patches[{index}]"
        _object(patch, {"id", "x", "y", "vars"}, path)
        identity = _identifier(patch["id"], f"{path}.id")
        if (identity in patch_ids or type(patch["x"]) is not int or type(patch["y"]) is not int
                or not I64_MIN <= patch["x"] <= I64_MAX or not I64_MIN <= patch["y"] <= I64_MAX):
            _reject(path, "duplicate patch ID or non-integer coordinate")
        if not 0 <= patch["x"] < topology["width"] or not 0 <= patch["y"] < topology["height"] or (patch["x"], patch["y"]) in coordinates:
            _reject(path, "duplicate or out-of-bounds patch coordinate")
        if not isinstance(patch["vars"], dict):
            _reject(f"{path}.vars", "expected patch variable map")
        _json_value(patch["vars"], f"{path}.vars")
        patch_ids.add(identity)
        coordinates.add((patch["x"], patch["y"]))
    if len(coordinates) != grid_area:
        _reject(f"{layer}.initial_state.patches", "one patch per grid coordinate required")

    agent_ids: set[str] = set()
    for index, agent in enumerate(state["agents"]):
        path = f"{layer}.initial_state.agents[{index}]"
        _object(agent, {"id", "kind", "x", "y", "vars"}, path)
        identity = _identifier(agent["id"], f"{path}.id")
        if identity in agent_ids:
            _reject(path, "duplicate stable agent business ID")
        _identifier(agent["kind"], f"{path}.kind")
        _number(agent["x"], f"{path}.x")
        _number(agent["y"], f"{path}.y")
        if not (
            -0.5 <= agent["x"] < topology["width"] - 0.5
            and -0.5 <= agent["y"] < topology["height"] - 0.5
        ):
            _reject(path, "agent position is outside topology bounds")
        if not isinstance(agent["vars"], dict):
            _reject(f"{path}.vars", "expected agent variable map")
        _json_value(agent["vars"], f"{path}.vars")
        agent_ids.add(identity)

    if not isinstance(payload["phases"], list) or not isinstance(payload["stop_conditions"], list) or not isinstance(payload["metrics"], list):
        _reject(layer, "phases, stop_conditions, and metrics must be lists")
    phase_ids: set[str] = set()
    for index, phase in enumerate(payload["phases"]):
        path = f"{layer}.phases[{index}]"
        _object(phase, {"id", "target", "agent_kind", "read_view", "commit_mode", "traversal", "random_address", "operations"}, path)
        identity = _identifier(phase["id"], f"{path}.id")
        if identity in phase_ids:
            _reject(path, "duplicate phase ID")
        if phase["target"] not in TARGETS or phase["read_view"] not in READ_VIEWS or phase["commit_mode"] not in COMMIT_MODES or phase["traversal"] not in TRAVERSALS:
            _reject(path, "unsupported target, read view, commit mode, or traversal")
        if phase["target"] == "patches" and phase["agent_kind"] is not None:
            _reject(f"{path}.agent_kind", "patch phase cannot filter agent kind")
        if phase["agent_kind"] is not None:
            _identifier(phase["agent_kind"], f"{path}.agent_kind")
        if phase["traversal"] == "random":
            _identifier(phase["random_address"], f"{path}.random_address")
        elif phase["random_address"] is not None:
            _reject(f"{path}.random_address", "stable traversal has no random address")
        if not isinstance(phase["operations"], list) or not phase["operations"]:
            _reject(f"{path}.operations", "phase operations required")
        for op_index, operation in enumerate(phase["operations"]):
            validate_operation(operation, f"{path}.operations[{op_index}]")
            if phase["target"] == "patches" and operation["op"] in {"move", "death"}:
                _reject(f"{path}.operations[{op_index}]", "patch phases cannot move or die")
        phase_ids.add(identity)

    stop_ids: set[str] = set()
    for index, condition in enumerate(payload["stop_conditions"]):
        path = f"{layer}.stop_conditions[{index}]"
        _object(condition, {"id", "when"}, path)
        identity = _identifier(condition["id"], f"{path}.id")
        if identity in stop_ids:
            _reject(path, "duplicate stop condition ID")
        validate_expression(condition["when"], f"{path}.when")
        stop_ids.add(identity)

    metric_ids: set[str] = set()
    for index, metric in enumerate(payload["metrics"]):
        path = f"{layer}.metrics[{index}]"
        _object(metric, {"id", "reducer", "source", "field", "where", "expression"}, path)
        identity = _identifier(metric["id"], f"{path}.id")
        if identity in metric_ids or metric["reducer"] not in {"count", "sum", "mean", "min", "max", "value", "expression"} or metric["source"] not in {"agents", "patches", "globals"}:
            _reject(path, "invalid or duplicate metric")
        if metric["reducer"] not in {"count", "expression"} and not isinstance(metric["field"], str):
            _reject(f"{path}.field", "non-count metric requires field")
        if metric["reducer"] == "value" and metric["source"] != "globals":
            _reject(path, "value reducer is only defined for globals")
        if metric["reducer"] == "expression":
            if metric["field"] is not None or metric["where"] is not None:
                _reject(path, "expression metric does not accept field or where")
            validate_expression(metric["expression"], f"{path}.expression")
        elif metric["expression"] is not None:
            _reject(f"{path}.expression", "expression only applies to expression reducer")
        if metric["where"] is not None:
            validate_expression(metric["where"], f"{path}.where")
        metric_ids.add(identity)


@dataclass(frozen=True)
class _Envelope:
    payload: dict[str, Any]

    VERSION = ""
    LAYER = "artifact"

    @classmethod
    def create(cls, payload: dict[str, Any]):
        copied = copy.deepcopy(payload)
        validate_payload(copied, layer=cls.LAYER)
        return cls(copied)

    @property
    def fingerprint(self) -> str:
        return canonical_digest({"version": self.VERSION, "payload": self.payload})

    def to_dict(self) -> dict[str, Any]:
        validate_payload(self.payload, layer=self.LAYER)
        return {"version": self.VERSION, "fingerprint": self.fingerprint, "payload": copy.deepcopy(self.payload)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        _object(value, {"version", "fingerprint", "payload"}, cls.LAYER)
        if value["version"] != cls.VERSION:
            _reject(f"{cls.LAYER}.version", f"unsupported {cls.LAYER} version")
        result = cls.create(value["payload"])
        if value["fingerprint"] != result.fingerprint:
            _reject(f"{cls.LAYER}.fingerprint", f"{cls.LAYER} checksum mismatch")
        return result


@dataclass(frozen=True)
class AbmBusinessIR(_Envelope):
    VERSION = ABM_BUSINESS_VERSION
    LAYER = "abm_business"


@dataclass(frozen=True)
class AbmCoreIR(_Envelope):
    VERSION = ABM_CORE_VERSION
    LAYER = "abm_core"


@dataclass(frozen=True)
class AbmTickPlan(_Envelope):
    VERSION = ABM_PLAN_VERSION
    LAYER = "abm_plan"
