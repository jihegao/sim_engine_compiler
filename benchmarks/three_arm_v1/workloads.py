"""Bounded, synthetic workloads for the same-kernel three-arm experiment.

These cases are derived from the hand-calculable B1 canonical fixture.  They
exercise dispatch structure; they are deliberately not labelled as J35 or as
an upstream performance case.  The helpers return fresh values so a benchmark
driver cannot accidentally carry mutations between arms or scale points.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.layers import BusinessIR


ROOT = Path(__file__).resolve().parents[2]
B1_SOURCE = ROOT / "tests" / "fixtures" / "synthetic" / "b1-daily-operations.json"
DEFAULT_SIZES = (4, 16, 64)
STRUCTURAL_FAMILIES = ("low-contention", "sparse-affected", "dense-affected")


def canonical_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class WorkloadSpec:
    """One bounded canonical structural case with explicit evidence limits."""

    case_id: str
    family: str
    size: int
    canonical_inputs: dict[str, Any]
    canonical_sha256: str
    provenance: dict[str, Any]
    expected_business_events: tuple[str, ...]

    def fresh_inputs(self) -> dict[str, Any]:
        return deepcopy(self.canonical_inputs)


@dataclass(frozen=True)
class IRVariantSpec:
    """A persisted Business IR revision made without runtime source changes."""

    case_id: str
    dimension: str
    business_ir: dict[str, Any]
    edited_business_paths: tuple[str, ...]
    origin_canonical_sha256: str

    def restore(self) -> BusinessIR:
        return BusinessIR.from_dict(deepcopy(self.business_ir))


def _duration_for(size: int) -> int:
    # Freeze one horizon so the scale curve changes entity/waiting-set size,
    # not simulated time.  N64 dense cleanup fits inside this bounded window.
    del size
    return 222


def _base_inputs(size: int) -> dict[str, Any]:
    if type(size) is not int or size < 2:
        raise ValueError("structural workload size must be an integer >= 2")

    value = json.loads(B1_SOURCE.read_text())
    duration = _duration_for(size)
    asset = deepcopy(value["aircraft"]["assets"][0])
    value["aircraft"]["assets"] = [
        {**deepcopy(asset), "tail_number": f"SYN-{index:04d}"}
        for index in range(size)
    ]
    value["aircraft"]["fleet_count"] = size
    value["aircraft"]["initial_ready"] = size

    basic = value["mission_profile"]["basic_missions"][0]
    basic.update(
        equipmentQuantity=size,
        minRequiredSorties=1,
        advanceNoticeMinutes=10,
        cancelMinutes=5,
        taskDurationMinutes=10,
    )
    task = value["mission_profile"]["composite_tasks"][0]["taskItems"][0]
    task.update(
        id="bounded-sortie",
        firstWaveTime="00:20",
        dailyRepeatCount=1,
        equipmentQuantity=size,
    )
    task.pop("intervalHours", None)
    value["mission_profile"]["composite_tasks"][0]["taskItems"] = [task]
    value["mission_profile"]["duration_minutes"] = duration

    for activity in value["support_activities"]["activities"]:
        for step in activity.get("jobs") or []:
            step["durationMinutes"] = 2
    value["time"].update(
        duration_minutes=duration,
        requested_steps=duration,
        sample_every_minutes=max(1, duration // 2),
    )
    value["stop_policy"]["conditions"] = [
        {"type": "duration", "duration_minutes": duration}
    ]
    value["project_identity"].update(
        project_id=f"synthetic-three-arm-{size}",
        project_version="three-arm-v1",
        source_import_id="derived-from-hand-calculable-b1",
    )
    return value


def _configure_sparse_groups(inputs: dict[str, Any], size: int) -> None:
    """Partition demand so each release affects a small dependency bucket."""

    target_group_size = 2 if size < 8 else 4
    group_sizes = []
    remaining = size
    while remaining:
        count = min(target_group_size, remaining)
        group_sizes.append(count)
        remaining -= count

    assets = inputs["aircraft"]["assets"]
    offset = 0
    models = []
    basics = []
    tasks = []
    nodes = []
    activities = []
    basic_template = inputs["mission_profile"]["basic_missions"][0]
    task_template = inputs["mission_profile"]["composite_tasks"][0]["taskItems"][0]
    activity_templates = inputs["support_activities"]["activities"]
    for group, count in enumerate(group_sizes):
        model = f"SYN-TYPE-{group:03d}"
        plan_group = f"sparse-group-{group:03d}"
        node_id = f"sparse-node-{group:03d}"
        models.append(model)
        for asset in assets[offset : offset + count]:
            asset["aircraft_type"] = model
            asset["model"] = model
        offset += count

        basic = deepcopy(basic_template)
        basic.update(
            id=f"basic-{group:03d}",
            missionId=f"basic-{group:03d}",
            name=f"Sparse group {group}",
            equipmentQuantity=count,
            minRequiredSorties=1,
            advanceNoticeMinutes=30,
            cancelMinutes=30,
            equipmentType=model,
        )
        basics.append(basic)
        task = deepcopy(task_template)
        task.update(
            id=f"sortie-{group:03d}",
            basicMissionId=basic["id"],
            basicTaskName=basic["name"],
            firstWaveTime="00:45",
            equipmentQuantity=count,
            equipmentType=model,
            operations_plan_group_id=plan_group,
        )
        tasks.append(task)
        nodes.append(
            {
                "id": node_id,
                "name": f"Sparse node {group}",
                "personnel_capacity": max(1, count - 1),
                "equipment_capacity": max(1, count - 1),
                "inventory": {},
            }
        )
        for template in activity_templates:
            activity = deepcopy(template)
            activity.update(
                id=f"{template['id']}-g{group:03d}",
                plan_group_id=plan_group,
                aircraft_model=model,
                resource_id=node_id,
            )
            # Distinct completion minutes ensure a resource change wakes one
            # small dependency bucket while other buckets remain blocked.
            for step in activity.get("jobs") or []:
                step["durationMinutes"] = 2 + group
            activities.append(activity)

    inputs["aircraft"]["models"] = models
    inputs["mission_profile"]["basic_missions"] = basics
    inputs["mission_profile"]["composite_tasks"][0]["taskItems"] = tasks
    inputs["support_network"]["nodes"] = nodes
    inputs["support_activities"]["activities"] = activities


def build_structural_workload(family: str, size: int) -> WorkloadSpec:
    """Create a low, sparse, or dense resource-impact scale point."""

    if family not in STRUCTURAL_FAMILIES:
        raise ValueError(f"unknown structural family {family!r}")
    inputs = _base_inputs(size)
    if family == "sparse-affected":
        _configure_sparse_groups(inputs, size)
        capacity = None
    elif family == "low-contention":
        capacity = size
    else:
        capacity = 1
    if capacity is not None:
        node = inputs["support_network"]["nodes"][0]
        node["personnel_capacity"] = capacity
        node["equipment_capacity"] = capacity
    case_id = f"synthetic-{family}-n{size}"
    inputs["project_identity"]["project_id"] = case_id
    input_sha256 = canonical_sha256(inputs)
    return WorkloadSpec(
        case_id=case_id,
        family=family,
        size=size,
        canonical_inputs=inputs,
        canonical_sha256=input_sha256,
        provenance={
            "classification": "synthetic-structural-workload",
            "source_fixture": str(B1_SOURCE.relative_to(ROOT)),
            "source_fixture_sha256": hashlib.sha256(B1_SOURCE.read_bytes()).hexdigest(),
            "canonical_sha256": input_sha256,
            "upstream_case": None,
            "j35_claim": False,
            "purpose": "bounded dispatch waiting-set structure only",
            "sparse_group_target_size": (
                (2 if size < 8 else 4) if family == "sparse-affected" else None
            ),
        },
        expected_business_events=(
            *(("personnel_delay",) if family != "low-contention" else ()),
            *(("mission_launched", "mission_returned") if family != "dense-affected" else ()),
            "simulation_stopped",
        ),
    )


def structural_workloads(
    sizes: Iterable[int] = DEFAULT_SIZES,
) -> tuple[WorkloadSpec, ...]:
    """Return the frozen 3 x N bounded structural matrix in stable order."""

    normalized = tuple(sizes)
    if not normalized or len(set(normalized)) != len(normalized):
        raise ValueError("sizes must be a non-empty sequence of unique values")
    return tuple(
        build_structural_workload(family, size)
        for family in STRUCTURAL_FAMILIES
        for size in normalized
    )


def _collection(payload: dict[str, Any], section: str, name: str) -> list[dict[str, Any]]:
    return payload["sections"][section]["collections"][name]


def _sealed_variant(
    *,
    name: str,
    dimension: str,
    payload: dict[str, Any],
    paths: tuple[str, ...],
    origin_sha256: str,
) -> IRVariantSpec:
    business = BusinessIR.create(payload)
    return IRVariantSpec(
        case_id=name,
        dimension=dimension,
        business_ir=business.to_dict(),
        edited_business_paths=paths,
        origin_canonical_sha256=origin_sha256,
    )


def ir_reuse_variants(
    size: int = 8, *, semantic_profile: str = "event-time-v2"
) -> tuple[IRVariantSpec, ...]:
    """Edit model frequency, capacity, and process composition in Business IR.

    All variants originate from one canonical import.  Each is independently
    checksummed and reloadable before lowering to Core and layout to a Plan.
    No runtime or dispatch implementation choice is encoded in these revisions.
    """

    base = build_structural_workload("sparse-affected", size)
    imported = import_business_ir(
        base.fresh_inputs(), semantic_profile=semantic_profile
    )

    frequency = deepcopy(imported.payload)
    frequency_task = _collection(
        frequency, "mission_profile", "composite_tasks"
    )[0]["definition"]["taskItems"][0]
    frequency_task["dailyRepeatCount"] = 3
    frequency_task["intervalHours"] = 0.25

    resources = deepcopy(imported.payload)
    resource_node = _collection(resources, "support_network", "nodes")[0][
        "definition"
    ]
    resource_node["personnel_capacity"] = max(1, size // 2)
    resource_node["equipment_capacity"] = max(1, size // 2)

    process = deepcopy(imported.payload)
    preflight = _collection(
        process, "support_activities", "activities"
    )[0]["definition"]
    preflight["jobs"].append(
        {
            "activityCode": "PRE-VERIFY",
            "durationMinutes": 1,
            "personnel": [{"professional": "inspector", "quantity": 1}],
            "equipment": [{"model": "tester", "quantity": 1}],
            "spare": [],
            "predecessors": ["PRE-1"],
        }
    )

    prefix = f"synthetic-ir-reuse-n{size}"
    origin = base.canonical_sha256
    return (
        _sealed_variant(
            name=f"{prefix}-mission-frequency",
            dimension="mission-frequency",
            payload=frequency,
            paths=(
                "sections.mission_profile.collections.composite_tasks[0].definition."
                "taskItems[0].dailyRepeatCount",
                "sections.mission_profile.collections.composite_tasks[0].definition."
                "taskItems[0].intervalHours",
            ),
            origin_sha256=origin,
        ),
        _sealed_variant(
            name=f"{prefix}-resource-counts",
            dimension="resource-counts",
            payload=resources,
            paths=(
                "sections.support_network.collections.nodes[0].definition.personnel_capacity",
                "sections.support_network.collections.nodes[0].definition.equipment_capacity",
            ),
            origin_sha256=origin,
        ),
        _sealed_variant(
            name=f"{prefix}-process-composition",
            dimension="process-composition",
            payload=process,
            paths=(
                "sections.support_activities.collections.activities[0].definition.jobs[1]",
            ),
            origin_sha256=origin,
        ),
    )


def persist_ir_reuse_artifacts(
    output: Path, *, size: int = 8,
    semantic_profiles: tuple[str, ...] = ("legacy-minute-v1", "event-time-v2"),
) -> dict[str, Any]:
    """Persist reloadable Business/Core/Plan revisions and a hash manifest."""

    from sim_engine_compiler.compiler.layout import compile_core
    from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
    from sim_engine_compiler.reference import SimpyReferenceRuntime

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)

    def write(path: Path, value: dict[str, Any]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return hashlib.sha256(path.read_bytes()).hexdigest()

    origin = build_structural_workload("sparse-affected", size)
    origin_path = output / "origin-canonical.json"
    origin_file_sha256 = write(origin_path, origin.fresh_inputs())
    manifest: dict[str, Any] = {
        "schema_version": "three-arm-ir-reuse-artifacts/v1",
        "classification": "synthetic-model-ir-reuse",
        "j35_claim": False,
        "origin": {
            "path": origin_path.name,
            "file_sha256": origin_file_sha256,
            "canonical_sha256": origin.canonical_sha256,
            "provenance": origin.provenance,
        },
        "variants": [],
    }
    for semantic_profile in semantic_profiles:
        for variant in ir_reuse_variants(
            size=size, semantic_profile=semantic_profile
        ):
            business = variant.restore()
            core = lower_business(business)
            plan = compile_core(core)
            directory = output / semantic_profile / variant.dimension
            records = {}
            for stage, value in (
                ("business", business.to_dict()),
                ("core", core.to_dict()),
                ("plan", plan.to_dict()),
            ):
                path = directory / f"{stage}.json"
                records[stage] = {
                    "path": str(path.relative_to(output)),
                    "sha256": write(path, value),
                }
            reference_status = "unsupported-event-time-python-reference"
            if semantic_profile == "legacy-minute-v1":
                reference_path = directory / "reference-result.json"
                records["reference_result"] = {
                    "path": str(reference_path.relative_to(output)),
                    "sha256": write(
                        reference_path, SimpyReferenceRuntime(plan, seed=0).run()
                    ),
                    "seed": 0,
                }
                reference_status = "generated"
            manifest["variants"].append(
                {
                    "case_id": variant.case_id,
                    "dimension": variant.dimension,
                    "semantic_profile": semantic_profile,
                    "origin_canonical_sha256": variant.origin_canonical_sha256,
                    "edited_business_paths": list(variant.edited_business_paths),
                    "business_fingerprint": business.fingerprint,
                    "core_fingerprint": core.fingerprint,
                    "plan_fingerprint": plan.fingerprint,
                    "reference_status": reference_status,
                    "artifacts": records,
                }
            )
    write(output / "manifest.json", manifest)
    return manifest
