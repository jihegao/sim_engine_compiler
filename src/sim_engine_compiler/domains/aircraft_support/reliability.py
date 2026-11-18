"""Canonical-input adapter for fused v1alpha2 reliability records.

The production entry is ``compile_aircraft_support``; this module supplies
component-group/instance records to the existing Lowering and Plan path.  It
does not implement a second compiler and does not change Runtime failure
scheduling.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.domains.aircraft_support.lowering import (
    _failure_distribution_rate,
)
from sim_engine_compiler.domains.aircraft_support.validation import _failure_distribution
from sim_engine_compiler.ir.reliability import (
    K_OUT_OF_N,
    SERIES,
    ReliabilityBusinessGroup,
    ReliabilityBusinessInstance,
    ReliabilityBusinessModel,
    ReliabilityComponentGroupSpec,
    ReliabilityComponentInstanceSpec,
)


def _reject(message: str, code: str, path: str) -> None:
    raise CompilationError(message, code=code, source_path=path)


def _tokens(value: Any) -> set[str]:
    text = str(value or "").strip().casefold()
    if not text:
        return set()
    compact = "".join(character for character in text if character.isalnum())
    return {text, compact} - {""}


def _positive_int(value: Any, path: str, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if type(value) is not int or value < 1:
        _reject("expected a positive integer", "invalid_quantity", path)
    return value


def _nonnegative_int(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        _reject("expected a nonnegative integer", "invalid_repair_duration", path)
    return value


def _rate(value: Any, path: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        _reject("failure rate must be finite and nonnegative", "invalid_failure_rate", path)
    return float(value)


def _failure_rate(item: Mapping[str, Any], path: str) -> float | None:
    explicit = item.get("failure_rate_per_hour")
    if explicit is None:
        explicit = item.get("failure_rate")
    distribution = item.get("failure_distribution")
    distribution_path = f"{path}.failure_distribution"
    _failure_distribution(distribution, distribution_path)
    distribution_present = isinstance(distribution, dict) and bool(distribution)
    if explicit is not None and distribution_present:
        _reject(
            "failure_rate_per_hour and failure_distribution are mutually exclusive",
            "ambiguous_failure_parameter",
            path,
        )
    if explicit is not None:
        return _rate(explicit, f"{path}.failure_rate_per_hour")
    if distribution_present:
        converted = _failure_distribution_rate(distribution)
        if converted is None:
            _reject(
                "unsupported failure distribution",
                "unsupported_failure_distribution",
                distribution_path,
            )
        return _rate(converted, distribution_path)
    return None


def _repair_activity(profile: Any, path: str) -> int:
    if not isinstance(profile, dict):
        return -1
    value = profile.get("repair_activity_index")
    if value is None:
        value = profile.get("repairActivityIndex")
    if value is None:
        return -1
    if type(value) is not int or value < -1:
        _reject("invalid repair activity index", "invalid_repair_activity", path)
    return value


def _repair_duration(profile: Any, path: str) -> int | None:
    if not isinstance(profile, dict):
        return None
    value = profile.get("repair_duration_minutes")
    if value is None:
        value = profile.get("repairTimeMinutes")
    if value is None:
        return None
    return _nonnegative_int(value, path)


def _repair_profile(item: Mapping[str, Any]) -> Any:
    if "repair_profile" in item:
        return item.get("repair_profile")
    return item.get("special_repair_profile")


def _parse_redundancy(
    item: Mapping[str, Any], path: str, instance_count: int
) -> tuple[str, int | None, int]:
    redundancy = item.get("redundancy")
    legacy = item.get("k_out_of_n")
    if redundancy is not None and legacy is not None:
        _reject(
            "redundancy and k_out_of_n are mutually exclusive",
            "ambiguous_redundancy",
            path,
        )
    if redundancy is not None:
        if not isinstance(redundancy, dict):
            _reject("redundancy must be an object", "invalid_redundancy", path)
        kind = redundancy.get("kind")
        if kind not in (SERIES, K_OUT_OF_N):
            _reject("invalid redundancy kind", "invalid_redundancy_kind", path)
        if kind == SERIES:
            if redundancy.get("k") is not None:
                _reject("series must not define k", "redundancy_k_on_series", path)
            n = redundancy.get("n", instance_count)
            if type(n) is not int or n != instance_count:
                _reject("redundancy_n must equal quantity", "redundancy_n_mismatch", path)
            return SERIES, None, instance_count
        k = redundancy.get("k")
        n = redundancy.get("n")
        if type(n) is not int or n != instance_count:
            _reject("redundancy_n must equal quantity", "redundancy_n_mismatch", path)
        if type(k) is not int or not 1 <= k <= n:
            _reject("k must be between 1 and n", "invalid_redundancy_k", path)
        return K_OUT_OF_N, k, n
    if legacy is not None:
        if not isinstance(legacy, dict) or type(legacy.get("enabled")) is not bool:
            _reject(
                "k_out_of_n must be an object with a boolean enabled field",
                "invalid_k_out_of_n",
                path,
            )
        if not legacy["enabled"]:
            return SERIES, None, instance_count
        k = legacy.get("k")
        n = legacy.get("n")
        if type(n) is not int or n != instance_count:
            _reject("k_out_of_n n must equal quantity", "redundancy_n_mismatch", path)
        if type(k) is not int or not 1 <= k <= n:
            _reject("k must be between 1 and n", "invalid_redundancy_k", path)
        return K_OUT_OF_N, k, n
    return SERIES, None, instance_count


def _aircraft_metadata(
    inputs: Mapping[str, Any], aircraft_ids: tuple[str, ...]
) -> tuple[tuple[str, str, str], ...]:
    config = inputs.get("aircraft")
    assets = config.get("assets") if isinstance(config, dict) else None
    assets = assets if isinstance(assets, list) else []
    result: list[tuple[str, str, str]] = []
    for index, aircraft_id in enumerate(aircraft_ids):
        asset = assets[index] if index < len(assets) and isinstance(assets[index], dict) else {}
        result.append(
            (
                aircraft_id,
                str(asset.get("aircraft_type") or ""),
                str(asset.get("model") or ""),
            )
        )
    return tuple(result)


def _applies(
    component_model: Any,
    aircraft_ids: tuple[str, ...],
    metadata: tuple[tuple[str, str, str], ...],
) -> tuple[int, ...]:
    component_tokens = _tokens(component_model)
    if not component_tokens:
        return tuple(range(len(aircraft_ids)))
    result = []
    for index, (aircraft_id, aircraft_type, model) in enumerate(metadata):
        tokens = _tokens(aircraft_id) | _tokens(aircraft_type) | _tokens(model)
        if component_tokens & tokens:
            result.append(index)
    return tuple(result)


def _aircraft_ids(inputs: Mapping[str, Any], explicit: Sequence[str] | None) -> tuple[str, ...]:
    if explicit is not None:
        result = tuple(str(item) for item in explicit)
    else:
        config = inputs.get("aircraft")
        assets = config.get("assets") if isinstance(config, dict) else None
        assets = assets if isinstance(assets, list) else []
        result = tuple(
            str(asset.get("tail_number") or f"aircraft-{index + 1}")
            for index, asset in enumerate(assets)
            if isinstance(asset, dict)
        )
        if not result:
            fleet_count = config.get("fleet_count") if isinstance(config, dict) else None
            count = int(fleet_count) if type(fleet_count) is int and fleet_count > 0 else 1
            result = tuple(f"aircraft-{index + 1}" for index in range(count))
    if not result or any(not item for item in result) or len(set(result)) != len(result):
        _reject("aircraft ids must be unique and nonempty", "invalid_aircraft_ids", "aircraft")
    return result


def _default_name(item: Mapping[str, Any], group_id: str) -> str:
    return str(item.get("name") or group_id)


def build_reliability_business(
    inputs: Mapping[str, Any],
    *,
    aircraft_ids: Sequence[str] | None = None,
) -> ReliabilityBusinessModel:
    """Build the new Business reliability schema from canonical components.

    The caller must explicitly opt into this path; the legacy compiler and
    runtimes are intentionally untouched.
    """
    equipment_tree = inputs.get("equipment_tree")
    components = equipment_tree.get("components") if isinstance(equipment_tree, dict) else None
    if not isinstance(components, list):
        _reject("equipment_tree.components must be a list", "invalid_components", "equipment_tree.components")

    aircraft_ids_value = _aircraft_ids(inputs, aircraft_ids)
    metadata = _aircraft_metadata(inputs, aircraft_ids_value)
    raw_groups: list[dict[str, Any]] = []
    seen_group_ids: set[str] = set()
    seen_instance_ids: set[str] = set()

    for index, item in enumerate(components):
        path = f"equipment_tree.components[{index}]"
        if not isinstance(item, dict):
            _reject("component must be an object", "invalid_component", path)
        if "failure_threshold" in item:
            _reject(
                "failure_threshold is not allowed in the reliability schema",
                "failure_threshold_in_new_plan",
                f"{path}.failure_threshold",
            )
        group_id = item.get("id")
        if type(group_id) is not str or not group_id:
            _reject("component id is required", "invalid_component_id", f"{path}.id")
        if group_id in seen_group_ids:
            _reject("duplicate component id", "duplicate_component_group_id", f"{path}.id")
        seen_group_ids.add(group_id)
        component_type_id = item.get("component_type_id")
        if type(component_type_id) is not str or not component_type_id:
            _reject(
                "component_type_id is required for the reliability schema",
                "component_type_missing",
                f"{path}.component_type_id",
            )
        group_rate = _failure_rate(item, path)
        group_profile = _repair_profile(item)
        group_repair_activity = _repair_activity(group_profile, f"{path}.repair_profile")
        group_repair_duration = _repair_duration(group_profile, f"{path}.repair_profile")
        parent_id = item.get("parent_id")
        if parent_id in (None, ""):
            parent_id = None
        elif type(parent_id) is not str:
            _reject("parent_id must be a string", "invalid_parent_group", f"{path}.parent_id")
        parent_instance_id = item.get("parent_instance_id")
        if parent_instance_id in (None, ""):
            parent_instance_id = None
        elif type(parent_instance_id) is not str:
            _reject(
                "parent_instance_id must be a string",
                "invalid_parent_instance",
                f"{path}.parent_instance_id",
            )

        explicit_instances = item.get("instances")
        parsed_instances: list[dict[str, Any]] = []
        if explicit_instances is not None:
            if not isinstance(explicit_instances, list) or not explicit_instances:
                _reject(
                    "instances must be a nonempty list",
                    "invalid_instances",
                    f"{path}.instances",
                )
            quantity_value = item.get("quantity")
            if quantity_value is not None and (
                type(quantity_value) is not int or quantity_value != len(explicit_instances)
            ):
                _reject(
                    "quantity must equal the explicit instance count",
                    "quantity_instance_mismatch",
                    f"{path}.quantity",
                )
            quantity = len(explicit_instances)
            for instance_index, instance in enumerate(explicit_instances):
                instance_path = f"{path}.instances[{instance_index}]"
                if not isinstance(instance, dict):
                    _reject("instance must be an object", "invalid_instance", instance_path)
                instance_id = instance.get("instance_id")
                if type(instance_id) is not str or not instance_id:
                    _reject(
                        "instance_id is required",
                        "invalid_instance_id",
                        f"{instance_path}.instance_id",
                    )
                if instance_id in seen_instance_ids:
                    _reject(
                        "duplicate instance_id",
                        "duplicate_instance_id",
                        f"{instance_path}.instance_id",
                    )
                seen_instance_ids.add(instance_id)
                instance_rate = _failure_rate(instance, instance_path)
                if instance_rate is None:
                    instance_rate = group_rate if group_rate is not None else 0.0
                instance_profile = instance.get("repair_profile")
                instance_repair_activity = (
                    _repair_activity(instance_profile, f"{instance_path}.repair_profile")
                    if instance_profile is not None
                    else group_repair_activity
                )
                instance_repair_duration = (
                    _repair_duration(instance_profile, f"{instance_path}.repair_profile")
                    if instance_profile is not None
                    else group_repair_duration
                )
                parsed_instances.append(
                    {
                        "instance_id": instance_id,
                        "failure_rate_per_hour": instance_rate,
                        "repair_activity_index": instance_repair_activity,
                        "repair_duration_minutes": instance_repair_duration,
                        "source_path": instance_path,
                    }
                )
        else:
            quantity = _positive_int(item.get("quantity", 1), f"{path}.quantity", 1)
            if group_rate is None:
                group_rate = 0.0
            for instance_index in range(quantity):
                instance_id = f"{group_id}-{instance_index}"
                if instance_id in seen_instance_ids:
                    _reject(
                        "generated instance_id collides with another instance",
                        "duplicate_instance_id",
                        path,
                    )
                seen_instance_ids.add(instance_id)
                parsed_instances.append(
                    {
                        "instance_id": instance_id,
                        "failure_rate_per_hour": group_rate,
                        "repair_activity_index": group_repair_activity,
                        "repair_duration_minutes": group_repair_duration,
                        "source_path": f"{path}.instances[{instance_index}]",
                    }
                )

        redundancy_kind, redundancy_k, redundancy_n = _parse_redundancy(
            item, f"{path}.redundancy", quantity
        )
        raw_groups.append(
            {
                "group_id": group_id,
                "component_type_id": component_type_id,
                "name": _default_name(item, group_id),
                "quantity": quantity,
                "parent_id": parent_id,
                "parent_instance_id": parent_instance_id,
                "instances": parsed_instances,
                "redundancy_kind": redundancy_kind,
                "redundancy_k": redundancy_k,
                "redundancy_n": redundancy_n,
                "repair_activity_index": group_repair_activity,
                "repair_duration_minutes": group_repair_duration,
                "aircraft_indexes": _applies(
                    item.get("aircraft_model"), aircraft_ids_value, metadata
                ),
                "source_path": path,
            }
        )

    raw_by_id = {group["group_id"]: group for group in raw_groups}
    for group in raw_groups:
        parent_id = group["parent_id"]
        if parent_id is None:
            if group["parent_instance_id"] is not None:
                _reject(
                    "parent_instance_id requires parent_id",
                    "parent_instance_mismatch",
                    group["source_path"],
                )
            continue
        parent = raw_by_id.get(parent_id)
        if parent is None:
            _reject("unknown parent group", "unknown_parent_group", group["source_path"])
        parent_instances = [instance["instance_id"] for instance in parent["instances"]]
        parent_instance_id = group["parent_instance_id"]
        if len(parent_instances) > 1:
            if parent_instance_id is None:
                _reject(
                    "parent_instance_id is required when the parent has multiple instances",
                    "ambiguous_parent_instance",
                    group["source_path"],
                )
        elif parent_instance_id is None:
            parent_instance_id = parent_instances[0]
        if parent_instance_id not in parent_instances:
            _reject(
                "parent_instance_id does not belong to the parent group",
                "parent_instance_group_mismatch",
                group["source_path"],
            )
        group["parent_instance_id"] = parent_instance_id

    # Detect parent-group cycles.
    for group in raw_groups:
        seen: set[str] = set()
        current: str | None = group["group_id"]
        while current is not None:
            if current in seen:
                _reject(
                    "cyclic component parent groups are unsupported",
                    "cyclic_component_parent",
                    group["source_path"],
                )
            seen.add(current)
            current = raw_by_id[current]["parent_id"]

    groups = tuple(
        ReliabilityBusinessGroup(
            group_id=group["group_id"],
            component_type_id=group["component_type_id"],
            name=group["name"],
            quantity=group["quantity"],
            parent_group_id=group["parent_id"],
            parent_instance_id=group["parent_instance_id"],
            aircraft_indexes=group["aircraft_indexes"],
            redundancy_kind=group["redundancy_kind"],
            redundancy_k=group["redundancy_k"],
            redundancy_n=group["redundancy_n"],
            repair_activity_index=group["repair_activity_index"],
            repair_duration_minutes=group["repair_duration_minutes"],
            source_path=group["source_path"],
        )
        for group in raw_groups
    )
    instances = tuple(
        ReliabilityBusinessInstance(
            instance_id=instance["instance_id"],
            group_id=group["group_id"],
            failure_rate_per_hour=instance["failure_rate_per_hour"],
            repair_activity_index=instance["repair_activity_index"],
            repair_duration_minutes=instance["repair_duration_minutes"],
            source_path=instance["source_path"],
        )
        for group in raw_groups
        for instance in group["instances"]
    )
    return ReliabilityBusinessModel(
        aircraft_ids=aircraft_ids_value,
        groups=groups,
        instances=instances,
    )


def is_reliability_input(inputs: Mapping[str, Any]) -> bool:
    equipment_tree = inputs.get("equipment_tree")
    components = equipment_tree.get("components") if isinstance(equipment_tree, dict) else None
    if not isinstance(components, list):
        return False
    for component in components:
        if not isinstance(component, dict):
            continue
        if any(
            key in component
            for key in ("component_type_id", "instances", "redundancy", "parent_instance_id")
        ):
            return True
        legacy = component.get("k_out_of_n")
        if isinstance(legacy, dict) and legacy.get("enabled") is True:
            return True
    return False


def build_reliability_plan_records(
    inputs: Mapping[str, Any],
    *,
    aircraft_ids: Sequence[str] | None = None,
) -> tuple[
    tuple[ReliabilityComponentGroupSpec, ...],
    tuple[ReliabilityComponentInstanceSpec, ...],
]:
    """Build fused v1alpha2 Plan/Core reliability records.

    The records use integer Core references, ready for the existing
    ``core_from_records`` and ``layout_core`` path.
    """
    model = build_reliability_business(inputs, aircraft_ids=aircraft_ids)
    group_indexes = {
        group.group_id: index for index, group in enumerate(model.groups)
    }
    instance_indexes = {
        instance.instance_id: index for index, instance in enumerate(model.instances)
    }
    groups = tuple(
        ReliabilityComponentGroupSpec(
            index=index,
            group_id=group.group_id,
            component_type_id=group.component_type_id,
            name=group.name,
            parent_group_index=(
                group_indexes[group.parent_group_id]
                if group.parent_group_id is not None
                else -1
            ),
            aircraft_indexes=group.aircraft_indexes,
            quantity=group.quantity,
            redundancy_kind=group.redundancy_kind,
            redundancy_k=group.redundancy_k or 0,
            redundancy_n=group.redundancy_n,
            repair_activity_index=group.repair_activity_index,
            repair_duration_minutes=group.repair_duration_minutes or 0,
            source_path=group.source_path,
        )
        for index, group in enumerate(model.groups)
    )
    parent_instance_by_group = {
        group.group_id: (
            instance_indexes[group.parent_instance_id]
            if group.parent_instance_id is not None
            else -1
        )
        for group in model.groups
    }
    instances = tuple(
        ReliabilityComponentInstanceSpec(
            index=index,
            instance_template_id=instance.instance_id,
            group_index=group_indexes[instance.group_id],
            parent_instance_index=parent_instance_by_group[instance.group_id],
            failure_rate_per_hour=instance.failure_rate_per_hour,
            repair_activity_index=instance.repair_activity_index,
            repair_duration_minutes=instance.repair_duration_minutes or 0,
            source_path=instance.source_path,
        )
        for index, instance in enumerate(model.instances)
    )
    return groups, instances
