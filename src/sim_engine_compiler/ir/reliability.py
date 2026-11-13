"""Versioned R1 reliability schema for component groups and instances.

This module is an additive schema contract.  It does not change the legacy
``aircraft-support-plan/v1alpha2`` plan or either runtime.  A Plan produced by
this module is consumed by the existing runtimes only after a later runtime
adapter is implemented.

The contract encodes these invariants:

* ``quantity`` expands one component group into independent instance templates.
* Different component groups are always in series.
* ``k_out_of_n`` is only valid inside one component group's instances.
* No implicit redundancy is derived from ``quantity``.
* New plans never use ``failure_threshold``.
* Static instance templates live in the Plan; mutable state lives in RunState.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence

from sim_engine_compiler.diagnostics import CompilationError


RELIABILITY_POLICY = "instance-redundancy/v1"
RELIABILITY_BUSINESS_VERSION = "aircraft-reliability-business/v1"
RELIABILITY_CORE_VERSION = "aircraft-reliability-core/v1"
RELIABILITY_PLAN_VERSION = "aircraft-support-plan/v1alpha2"

SERIES = "series"
K_OUT_OF_N = "k_out_of_n"
_REDUNDANCY_KINDS = frozenset((SERIES, K_OUT_OF_N))
_TIME_PROFILES = frozenset(("legacy-minute-v1", "event-time-v2"))


def _reject(message: str, code: str, path: str) -> None:
    raise CompilationError(message, code=code, source_path=path)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {key: _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    return value


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _rate(value: Any, path: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        _reject("failure rate must be finite and nonnegative", "invalid_failure_rate", path)
    return float(value)


def _optional_nonnegative_int(value: Any, path: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        _reject(
            "repair duration must be a nonnegative integer or null",
            "invalid_repair_duration",
            path,
        )
    return value


def _reject_failure_threshold(value: Any, path: str = "$") -> None:
    """Reject ``failure_threshold`` anywhere in a new reliability document."""
    if isinstance(value, Mapping):
        if "failure_threshold" in value:
            _reject(
                "failure_threshold is not allowed in the new reliability schema",
                "failure_threshold_in_new_plan",
                f"{path}.failure_threshold",
            )
        for key, child in value.items():
            _reject_failure_threshold(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_failure_threshold(child, f"{path}[{index}]")


@dataclass(frozen=True)
class ReliabilityBusinessGroup:
    """Business-level component group before Core/Plan layout."""

    group_id: str
    component_type_id: str
    name: str
    quantity: int
    parent_group_id: str | None
    parent_instance_id: str | None
    aircraft_indexes: tuple[int, ...]
    redundancy_kind: str
    redundancy_k: int
    redundancy_n: int
    repair_activity_index: int
    repair_duration_minutes: int | None
    source_path: str


@dataclass(frozen=True)
class ReliabilityBusinessInstance:
    """Business-level instance template, scoped to one component group."""

    instance_id: str
    group_id: str
    failure_rate_per_hour: float
    repair_activity_index: int
    repair_duration_minutes: int | None
    source_path: str


@dataclass(frozen=True)
class ReliabilityBusinessModel:
    aircraft_ids: tuple[str, ...]
    groups: tuple[ReliabilityBusinessGroup, ...]
    instances: tuple[ReliabilityBusinessInstance, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RELIABILITY_BUSINESS_VERSION,
            "payload": _jsonable(self),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())


@dataclass(frozen=True)
class ReliabilityCoreGroup:
    group_id: str
    component_type_id: str
    name: str
    quantity: int
    parent_group_id: str | None
    aircraft_ids: tuple[str, ...]
    redundancy_kind: str
    redundancy_k: int
    redundancy_n: int
    repair_activity_index: int
    repair_duration_minutes: int | None
    source_path: str


@dataclass(frozen=True)
class ReliabilityCoreInstance:
    instance_template_id: str
    group_id: str
    parent_instance_id: str | None
    failure_rate_per_hour: float
    repair_activity_index: int
    repair_duration_minutes: int | None
    source_path: str


@dataclass(frozen=True)
class ReliabilityCoreIR:
    business_fingerprint: str
    groups: tuple[ReliabilityCoreGroup, ...]
    instances: tuple[ReliabilityCoreInstance, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": RELIABILITY_CORE_VERSION,
            "payload": {
                "business_fingerprint": self.business_fingerprint,
                "tables": _jsonable(
                    {
                        "component_groups": self.groups,
                        "component_instances": self.instances,
                    }
                ),
            },
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())


@dataclass(frozen=True)
class ReliabilityComponentGroupSpec:
    index: int
    group_id: str
    component_type_id: str
    name: str
    parent_group_index: int
    aircraft_indexes: tuple[int, ...]
    quantity: int
    redundancy_kind: str
    redundancy_k: int
    redundancy_n: int
    repair_activity_index: int
    repair_duration_minutes: int
    source_path: str


@dataclass(frozen=True)
class ReliabilityComponentInstanceSpec:
    index: int
    instance_template_id: str
    group_index: int
    parent_instance_index: int
    failure_rate_per_hour: float
    repair_activity_index: int
    repair_duration_minutes: int
    source_path: str


@dataclass(frozen=True)
class ReliabilityComponentInstanceState:
    runtime_instance_id: str
    aircraft_index: int
    aircraft_id: str
    instance_template_id: str
    group_index: int
    parent_instance_index: int | None
    remaining_exposure: float = 0.0
    failed: bool = False
    failed_at: int | None = None
    repairing: bool = False
    repair_remaining: int = 0
    exposure_paused: bool = False

    @property
    def healthy(self) -> bool:
        return not self.failed and not self.repairing


@dataclass(frozen=True)
class ReliabilityExecutionPlan:
    plan_version: str
    domain: str
    semantic_profile: str
    work_policy: str
    rng_profile: str
    reliability_policy: str
    source_inputs_sha256: str
    duration_minutes: int
    aircraft_ids: tuple[str, ...]
    component_groups: tuple[ReliabilityComponentGroupSpec, ...]
    component_instances: tuple[ReliabilityComponentInstanceSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(self)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ReliabilityExecutionPlan":
        _reject_failure_threshold(value)
        if value.get("plan_version") != RELIABILITY_PLAN_VERSION:
            _reject(
                "unsupported reliability plan version",
                "unsupported_plan_version",
                "plan_version",
            )
        groups = tuple(
            ReliabilityComponentGroupSpec(
                **{
                    **item,
                    "aircraft_indexes": tuple(item.get("aircraft_indexes", ())),
                    "repair_duration_minutes": item.get("repair_duration_minutes"),
                }
            )
            for item in value.get("component_groups", ())
        )
        instances = tuple(
            ReliabilityComponentInstanceSpec(
                **{
                    **item,
                    "parent_instance_index": int(item.get("parent_instance_index", -1)),
                    "repair_duration_minutes": item.get("repair_duration_minutes"),
                }
            )
            for item in value.get("component_instances", ())
        )
        plan = cls(
            plan_version=value["plan_version"],
            domain=value.get("domain", ""),
            semantic_profile=value.get("semantic_profile", ""),
            work_policy=value.get("work_policy", ""),
            rng_profile=value.get("rng_profile", ""),
            reliability_policy=value.get("reliability_policy", ""),
            source_inputs_sha256=value.get("source_inputs_sha256", ""),
            duration_minutes=value.get("duration_minutes", 0),
            aircraft_ids=tuple(value.get("aircraft_ids", ())),
            component_groups=groups,
            component_instances=instances,
        )
        plan.validate()
        return plan

    def validate(self) -> None:
        if self.plan_version != RELIABILITY_PLAN_VERSION:
            _reject(
                "unsupported reliability plan version",
                "unsupported_plan_version",
                "plan_version",
            )
        if self.reliability_policy != RELIABILITY_POLICY:
            _reject(
                "unsupported reliability policy",
                "unsupported_reliability_policy",
                "reliability_policy",
            )
        if self.domain != "aircraft-support":
            _reject("unsupported domain", "unsupported_domain", "domain")
        if self.semantic_profile not in _TIME_PROFILES:
            _reject(
                "unsupported semantic profile",
                "unsupported_semantic_profile",
                "semantic_profile",
            )
        if self.work_policy != "stable-topological-serial":
            _reject("unsupported work policy", "unsupported_work_policy", "work_policy")
        if self.rng_profile != "legacy-sequential-v1":
            _reject("unsupported RNG profile", "unsupported_rng_profile", "rng_profile")
        if (
            type(self.source_inputs_sha256) is not str
            or len(self.source_inputs_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.source_inputs_sha256)
        ):
            _reject(
                "source_inputs_sha256 must be a SHA-256 hex digest",
                "invalid_source_fingerprint",
                "source_inputs_sha256",
            )
        if type(self.duration_minutes) is not int or self.duration_minutes < 0:
            _reject("duration must be nonnegative", "invalid_duration", "duration_minutes")
        if not self.aircraft_ids or any(
            type(item) is not str or not item for item in self.aircraft_ids
        ) or len(set(self.aircraft_ids)) != len(self.aircraft_ids):
            _reject("aircraft_ids must be unique nonempty strings", "invalid_aircraft_ids", "aircraft_ids")

        group_ids: dict[str, ReliabilityComponentGroupSpec] = {}
        for position, group in enumerate(self.component_groups):
            path = f"component_groups[{position}]"
            if group.index != position:
                _reject("group index must equal its position", "invalid_group_index", path)
            if type(group.group_id) is not str or not group.group_id or group.group_id in group_ids:
                _reject("duplicate or missing group_id", "duplicate_component_group_id", path)
            group_ids[group.group_id] = group
            if type(group.component_type_id) is not str or not group.component_type_id:
                _reject("component_type_id is required", "component_type_missing", path)
            if type(group.name) is not str:
                _reject("name must be a string", "invalid_group_name", path)
            if type(group.quantity) is not int or group.quantity < 1:
                _reject("quantity must be a positive integer", "invalid_quantity", path)
            if group.redundancy_kind not in _REDUNDANCY_KINDS:
                _reject(
                    "redundancy_kind must be series or k_out_of_n",
                    "invalid_redundancy_kind",
                    path,
                )
            if type(group.redundancy_n) is not int or group.redundancy_n != group.quantity:
                _reject(
                    "redundancy_n must equal quantity",
                    "redundancy_n_mismatch",
                    path,
                )
            if group.redundancy_kind == SERIES:
                if group.redundancy_k not in (None, 0):
                    _reject(
                        "series groups must not define redundancy_k",
                        "redundancy_k_on_series",
                        path,
                    )
            else:
                if type(group.redundancy_k) is not int or not 1 <= group.redundancy_k <= group.redundancy_n:
                    _reject(
                        "k must be between 1 and n",
                        "invalid_redundancy_k",
                        path,
                    )
            if type(group.parent_group_index) is not int:
                _reject("parent_group_index must be an integer", "invalid_parent_group", path)
            if group.parent_group_index != -1:
                if not 0 <= group.parent_group_index < len(self.component_groups):
                    _reject("unknown parent group", "unknown_parent_group", path)
            indexes = group.aircraft_indexes
            if (
                type(indexes) is not tuple
                or len(set(indexes)) != len(indexes)
                or any(type(item) is not int or not 0 <= item < len(self.aircraft_ids) for item in indexes)
            ):
                _reject("invalid aircraft_indexes", "invalid_aircraft_indexes", path)
            if type(group.repair_activity_index) is not int or group.repair_activity_index < -1:
                _reject("invalid repair activity index", "invalid_repair_activity", path)
            _optional_nonnegative_int(group.repair_duration_minutes, path)
            if type(group.source_path) is not str or not group.source_path:
                _reject("source_path is required", "missing_source_path", path)

        instance_ids: dict[str, ReliabilityComponentInstanceSpec] = {}
        for position, instance in enumerate(self.component_instances):
            path = f"component_instances[{position}]"
            if instance.index != position:
                _reject("instance index must equal its position", "invalid_instance_index", path)
            if (
                type(instance.instance_template_id) is not str
                or not instance.instance_template_id
                or instance.instance_template_id in instance_ids
            ):
                _reject(
                    "duplicate or missing instance_template_id",
                    "duplicate_instance_id",
                    path,
                )
            instance_ids[instance.instance_template_id] = instance
            if type(instance.group_index) is not int or not 0 <= instance.group_index < len(self.component_groups):
                _reject("unknown instance group", "unknown_instance_group", path)
            _rate(instance.failure_rate_per_hour, f"{path}.failure_rate_per_hour")
            if (
                type(instance.repair_activity_index) is not int
                or instance.repair_activity_index < -1
            ):
                _reject("invalid repair activity index", "invalid_repair_activity", path)
            _optional_nonnegative_int(instance.repair_duration_minutes, path)
            if type(instance.source_path) is not str or not instance.source_path:
                _reject("source_path is required", "missing_source_path", path)
            if type(instance.parent_instance_index) is not int:
                _reject("parent_instance_index must be an integer", "invalid_parent_instance", path)

        for position, group in enumerate(self.component_groups):
            path = f"component_groups[{position}]"
            members = [
                instance for instance in self.component_instances
                if instance.group_index == position
            ]
            if len(members) != group.quantity:
                _reject(
                    "quantity must equal the number of instance templates",
                    "quantity_instance_mismatch",
                    path,
                )
            parents = {instance.parent_instance_index for instance in members}
            if len(parents) != 1:
                _reject(
                    "all instances in a group must share one parent instance",
                    "mixed_parent_instance_unsupported",
                    path,
                )
            parent_instance_index = next(iter(parents))
            if group.parent_group_index == -1:
                if parent_instance_index != -1:
                    _reject(
                        "root groups must not define a parent instance",
                        "parent_instance_mismatch",
                        path,
                    )
            else:
                if parent_instance_index < 0 or parent_instance_index >= len(self.component_instances):
                    _reject(
                        "parent instance is required for a non-root group",
                        "ambiguous_parent_instance",
                        path,
                    )
                parent_instance = self.component_instances[parent_instance_index]
                if parent_instance.group_index != group.parent_group_index:
                    _reject(
                        "parent instance does not belong to parent group",
                        "parent_instance_group_mismatch",
                        path,
                    )

        # Parent group cycles.
        for start in range(len(self.component_groups)):
            seen: set[int] = set()
            current = start
            while current != -1:
                if current in seen:
                    _reject(
                        "cyclic component parent groups are unsupported",
                        "cyclic_component_parent",
                        f"component_groups[{start}]",
                    )
                seen.add(current)
                current = self.component_groups[current].parent_group_index


def _validate_component_tables(
    groups: Sequence[ReliabilityComponentGroupSpec],
    instances: Sequence[ReliabilityComponentInstanceSpec],
    *,
    aircraft_count: int,
) -> None:
    if aircraft_count < 0:
        _reject("invalid aircraft count", "invalid_aircraft_ids", "aircraft")
    plan = ReliabilityExecutionPlan(
        plan_version=RELIABILITY_PLAN_VERSION,
        domain="aircraft-support",
        semantic_profile="legacy-minute-v1",
        work_policy="stable-topological-serial",
        rng_profile="legacy-sequential-v1",
        reliability_policy=RELIABILITY_POLICY,
        source_inputs_sha256="0" * 64,
        duration_minutes=1,
        aircraft_ids=tuple(f"aircraft-{index}" for index in range(aircraft_count)),
        component_groups=tuple(groups),
        component_instances=tuple(instances),
    )
    plan.validate()


def lower_reliability_core(
    model: ReliabilityBusinessModel,
    *,
    business_fingerprint: str = "",
) -> ReliabilityCoreIR:
    group_by_id = {group.group_id: group for group in model.groups}
    if len(group_by_id) != len(model.groups):
        _reject("duplicate business group id", "duplicate_component_group_id", "groups")
    for instance in model.instances:
        if instance.group_id not in group_by_id:
            _reject("unknown business group", "unknown_instance_group", instance.source_path)
    groups = tuple(
        ReliabilityCoreGroup(
            group_id=group.group_id,
            component_type_id=group.component_type_id,
            name=group.name,
            quantity=group.quantity,
            parent_group_id=group.parent_group_id,
            aircraft_ids=tuple(
                model.aircraft_ids[index]
                for index in group.aircraft_indexes
                if 0 <= index < len(model.aircraft_ids)
            ),
            redundancy_kind=group.redundancy_kind,
            redundancy_k=group.redundancy_k,
            redundancy_n=group.redundancy_n,
            repair_activity_index=group.repair_activity_index,
            repair_duration_minutes=group.repair_duration_minutes,
            source_path=group.source_path,
        )
        for group in model.groups
    )
    instances = tuple(
        ReliabilityCoreInstance(
            instance_template_id=instance.instance_id,
            group_id=instance.group_id,
            parent_instance_id=group_by_id[instance.group_id].parent_instance_id,
            failure_rate_per_hour=instance.failure_rate_per_hour,
            repair_activity_index=instance.repair_activity_index,
            repair_duration_minutes=instance.repair_duration_minutes,
            source_path=instance.source_path,
        )
        for instance in model.instances
    )
    core = ReliabilityCoreIR(
        business_fingerprint=business_fingerprint or model.fingerprint,
        groups=groups,
        instances=instances,
    )
    _validate_core(core)
    return core


def _validate_core(core: ReliabilityCoreIR) -> None:
    group_ids = {group.group_id for group in core.groups}
    if len(group_ids) != len(core.groups):
        _reject("duplicate Core group symbol", "duplicate_component_group_id", "groups")
    for group in core.groups:
        if group.parent_group_id is not None and group.parent_group_id not in group_ids:
            _reject("unknown Core parent group", "unknown_parent_group", group.source_path)
        if group.redundancy_kind not in _REDUNDANCY_KINDS:
            _reject("invalid Core redundancy kind", "invalid_redundancy_kind", group.source_path)
        if group.redundancy_n != group.quantity:
            _reject("Core redundancy_n mismatch", "redundancy_n_mismatch", group.source_path)
        if group.redundancy_kind == SERIES and group.redundancy_k not in (None, 0):
            _reject("series group has k", "redundancy_k_on_series", group.source_path)
        if group.redundancy_kind == K_OUT_OF_N and (
            type(group.redundancy_k) is not int
            or not 1 <= group.redundancy_k <= group.redundancy_n
        ):
            _reject("invalid Core redundancy k", "invalid_redundancy_k", group.source_path)
    instance_ids = {instance.instance_template_id for instance in core.instances}
    if len(instance_ids) != len(core.instances):
        _reject("duplicate Core instance symbol", "duplicate_instance_id", "instances")
    for instance in core.instances:
        if instance.group_id not in group_ids:
            _reject("unknown Core instance group", "unknown_instance_group", instance.source_path)
        if instance.parent_instance_id is not None and instance.parent_instance_id not in instance_ids:
            _reject(
                "unknown Core parent instance",
                "unknown_parent_instance",
                instance.source_path,
            )
        _rate(instance.failure_rate_per_hour, instance.source_path)


def layout_reliability_plan(
    core: ReliabilityCoreIR,
    *,
    semantic_profile: str = "legacy-minute-v1",
    work_policy: str = "stable-topological-serial",
    rng_profile: str = "legacy-sequential-v1",
    source_inputs_sha256: str = "",
    duration_minutes: int = 0,
    aircraft_ids: tuple[str, ...] = (),
) -> ReliabilityExecutionPlan:
    if not aircraft_ids:
        aircraft_ids = tuple(
            sorted({aircraft for group in core.groups for aircraft in group.aircraft_ids})
        )
    group_indexes = {group.group_id: index for index, group in enumerate(core.groups)}
    instance_indexes = {
        instance.instance_template_id: index for index, instance in enumerate(core.instances)
    }
    groups = tuple(
        ReliabilityComponentGroupSpec(
            index=index,
            group_id=group.group_id,
            component_type_id=group.component_type_id,
            name=group.name,
            parent_group_index=group_indexes.get(group.parent_group_id, -1),
            aircraft_indexes=tuple(
                aircraft_ids.index(aircraft)
                for aircraft in group.aircraft_ids
                if aircraft in aircraft_ids
            ),
            quantity=group.quantity,
            redundancy_kind=group.redundancy_kind,
            redundancy_k=group.redundancy_k,
            redundancy_n=group.redundancy_n,
            repair_activity_index=group.repair_activity_index,
            repair_duration_minutes=group.repair_duration_minutes,
            source_path=group.source_path,
        )
        for index, group in enumerate(core.groups)
    )
    instances = tuple(
        ReliabilityComponentInstanceSpec(
            index=index,
            instance_template_id=instance.instance_template_id,
            group_index=group_indexes[instance.group_id],
            parent_instance_index=instance_indexes.get(instance.parent_instance_id, -1),
            failure_rate_per_hour=instance.failure_rate_per_hour,
            repair_activity_index=instance.repair_activity_index,
            repair_duration_minutes=instance.repair_duration_minutes,
            source_path=instance.source_path,
        )
        for index, instance in enumerate(core.instances)
    )
    plan = ReliabilityExecutionPlan(
        plan_version=RELIABILITY_PLAN_VERSION,
        domain="aircraft-support",
        semantic_profile=semantic_profile,
        work_policy=work_policy,
        rng_profile=rng_profile,
        reliability_policy=RELIABILITY_POLICY,
        source_inputs_sha256=source_inputs_sha256,
        duration_minutes=duration_minutes,
        aircraft_ids=tuple(aircraft_ids),
        component_groups=groups,
        component_instances=instances,
    )
    plan.validate()
    return plan


def runtime_instance_id(aircraft_id: str, instance_template_id: str) -> str:
    return f"{aircraft_id}/{instance_template_id}"


def runtime_instance_ids(
    plan: ReliabilityExecutionPlan,
    aircraft_id: str,
    aircraft_index: int,
) -> tuple[str, ...]:
    result = []
    for group in plan.component_groups:
        if aircraft_index not in group.aircraft_indexes:
            continue
        for instance in plan.component_instances:
            if instance.group_index == group.index:
                result.append(runtime_instance_id(aircraft_id, instance.instance_template_id))
    return tuple(result)


def repair_duration_minutes_for(
    plan: ReliabilityExecutionPlan,
    group_index: int,
    instance_index: int,
) -> int | None:
    group = plan.component_groups[group_index]
    instance = plan.component_instances[instance_index]
    if instance.repair_duration_minutes is not None:
        return instance.repair_duration_minutes
    return group.repair_duration_minutes


def repair_activity_index_for(
    plan: ReliabilityExecutionPlan,
    group_index: int,
    instance_index: int,
) -> int:
    group = plan.component_groups[group_index]
    instance = plan.component_instances[instance_index]
    if instance.repair_activity_index >= 0:
        return instance.repair_activity_index
    return group.repair_activity_index


def _children_by_parent_instance(
    plan: ReliabilityExecutionPlan,
) -> dict[int, tuple[int, ...]]:
    result: dict[int, list[int]] = {}
    for group in plan.component_groups:
        if group.parent_group_index < 0:
            continue
        members = [
            instance for instance in plan.component_instances
            if instance.group_index == group.index
        ]
        if not members:
            continue
        parent = members[0].parent_instance_index
        result.setdefault(parent, []).append(group.index)
    return {key: tuple(value) for key, value in result.items()}


def _group_instance_indexes(
    plan: ReliabilityExecutionPlan, group_index: int
) -> tuple[int, ...]:
    return tuple(
        instance.index
        for instance in plan.component_instances
        if instance.group_index == group_index
    )


def _state_lookup(
    plan: ReliabilityExecutionPlan,
    states: Sequence[ReliabilityComponentInstanceState],
    aircraft_index: int,
) -> dict[int, ReliabilityComponentInstanceState]:
    result: dict[int, ReliabilityComponentInstanceState] = {}
    by_template = {
        state.instance_template_id: state
        for state in states
        if state.aircraft_index == aircraft_index
    }
    for instance in plan.component_instances:
        state = by_template.get(instance.instance_template_id)
        if state is not None:
            result[instance.index] = state
    return result


def instance_healthy(
    plan: ReliabilityExecutionPlan,
    states: Sequence[ReliabilityComponentInstanceState],
    aircraft_index: int,
    instance_index: int,
    *,
    children: Mapping[int, tuple[int, ...]] | None = None,
    memo: dict[tuple[str, int], bool] | None = None,
) -> bool:
    children = children or _children_by_parent_instance(plan)
    memo = memo if memo is not None else {}
    key = ("instance", instance_index)
    if key in memo:
        return memo[key]
    state = _state_lookup(plan, states, aircraft_index).get(instance_index)
    result = state is not None and state.healthy
    if result:
        for child_group in children.get(instance_index, ()):
            if not group_healthy(
                plan, states, aircraft_index, child_group, children=children, memo=memo
            ):
                result = False
                break
    memo[key] = result
    return result


def group_healthy(
    plan: ReliabilityExecutionPlan,
    states: Sequence[ReliabilityComponentInstanceState],
    aircraft_index: int,
    group_index: int,
    *,
    children: Mapping[int, tuple[int, ...]] | None = None,
    memo: dict[tuple[str, int], bool] | None = None,
) -> bool:
    children = children or _children_by_parent_instance(plan)
    memo = memo if memo is not None else {}
    key = ("group", group_index)
    if key in memo:
        return memo[key]
    group = plan.component_groups[group_index]
    members = _group_instance_indexes(plan, group_index)
    if group.redundancy_kind == SERIES:
        result = all(
            instance_healthy(
                plan, states, aircraft_index, instance_index,
                children=children, memo=memo,
            )
            for instance_index in members
        )
    else:
        healthy_count = sum(
            1
            for instance_index in members
            if instance_healthy(
                plan, states, aircraft_index, instance_index,
                children=children, memo=memo,
            )
        )
        result = healthy_count >= int(group.redundancy_k or 0)
    memo[key] = result
    return result


def aircraft_healthy(
    plan: ReliabilityExecutionPlan,
    states: Sequence[ReliabilityComponentInstanceState],
    aircraft_index: int,
) -> bool:
    children = _children_by_parent_instance(plan)
    memo: dict[tuple[str, int], bool] = {}
    roots = [
        group for group in plan.component_groups
        if group.parent_group_index == -1 and aircraft_index in group.aircraft_indexes
    ]
    return all(
        group_healthy(
            plan, states, aircraft_index, group.index,
            children=children, memo=memo,
        )
        for group in roots
    )


def complete_repair(
    plan: ReliabilityExecutionPlan,
    states: Sequence[ReliabilityComponentInstanceState],
    runtime_instance_id_value: str,
) -> tuple[ReliabilityComponentInstanceState, ...]:
    """Clear only the target runtime instance and leave every other state alone."""
    found = False
    result: list[ReliabilityComponentInstanceState] = []
    for state in states:
        if state.runtime_instance_id == runtime_instance_id_value:
            found = True
            result.append(
                replace(
                    state,
                    failed=False,
                    failed_at=None,
                    repairing=False,
                    repair_remaining=0,
                    exposure_paused=False,
                )
            )
        else:
            result.append(state)
    if not found:
        _reject(
            "unknown runtime instance",
            "repair_target_unknown",
            runtime_instance_id_value,
        )
    return tuple(result)
