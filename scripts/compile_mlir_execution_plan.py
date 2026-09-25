#!/usr/bin/env python3
"""Compile canonical aircraft-support inputs through the bounded MLIR pilot."""

from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from types import SimpleNamespace
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR, CORE_VERSION, BUSINESS_VERSION, digest
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.compiler.layout import compile_core, layout_core


EXPECTED_MLIR_VERSION = "23.1.1"
READS = (
    "personnel_capacity",
    "equipment_capacity",
    "local_inventory",
    "job_reservations",
    "route_source_inventory",
    "active_shipment",
)
EFFECTS = (
    "reserve_capacity",
    "consume_inventory",
    "request_remote_spares",
    "emit_dispatch_trace",
)


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _string_array(values: tuple[str, ...] | list[str]) -> str:
    return "[" + ", ".join(_quote(value) for value in values) + "]"


def _float(value: float) -> str:
    text = format(value, ".17g")
    if "." not in text and "e" not in text.lower():
        text += ".0"
    return text


def emit_sim_module(core: CoreIR) -> str:
    """Project validated symbolic Core through its layout; no Plan is constructed."""
    layout = layout_core(core)
    projected = dict(layout)
    for table in ('activities', 'components', 'supply_routes'):
        projected[table] = [SimpleNamespace(**row) for row in layout[table]]
    for activity in projected['activities']:
        activity.steps = [SimpleNamespace(**step) for step in activity.steps]
    plan = SimpleNamespace(**projected, fingerprint=digest(layout))
    attrs = [
        'sim.schema = "aircraft-support-core/v1"',
        f"sim.semantic_profile = {_quote(plan.semantic_profile)}",
        f"sim.phases = {_string_array(plan.phases)}",
        f"sim.work_policy = {_quote(plan.work_policy)}",
        f"sim.rng_profile = {_quote(plan.rng_profile)}",
        f"sim.base_plan_fingerprint = {_quote(plan.fingerprint)}",
    ]
    lines = ["module attributes {" + ", ".join(attrs) + "} {"]
    for activity in plan.activities:
        has_static_spares = any(step.spares for step in activity.steps)
        activity_attrs = [
            f"activity_index = {activity.index} : i64",
            f"resource_node_index = {activity.resource_node_index} : i64",
            f"step_count = {len(activity.steps)} : i64",
            f"activity_id = {_quote(activity.activity_id)}",
            f"has_static_spares = {'true' if has_static_spares else 'false'}",
            f"replacement_ratio = {_float(activity.replacement_ratio)} : f64",
            f"maintenance_methods = {_string_array(list(activity.maintenance_methods))}",
        ]
        lines.append(
            '  "sim.activity"() {' + ", ".join(activity_attrs) + "} : () -> ()"
        )
    for activity in plan.activities:
        for step in activity.steps:
            spares = "[" + ", ".join(
                "{product_id = "
                + _quote(product_id)
                + f", quantity = {quantity} : i64}}"
                for product_id, quantity in step.spares
            ) + "]"
            step_attrs = [
                f"activity_index = {activity.index} : i64",
                f"step_index = {step.index} : i64",
                f"resource_node_index = {activity.resource_node_index} : i64",
                f"personnel = {step.personnel} : i64",
                f"equipment = {step.equipment} : i64",
                f"activity_id = {_quote(activity.activity_id)}",
                f"step_code = {_quote(step.code)}",
                f"source_path = {_quote(step.source_path)}",
                f"spares = {spares}",
                f"reads = {_string_array(list(READS))}",
                f"effects = {_string_array(list(EFFECTS))}",
            ]
            lines.append(
                '  "sim.work_step"() {' + ", ".join(step_attrs) + "} : () -> ()"
            )
    for component in plan.components:
        component_attrs = [
            f"repair_activity_index = {component.repair_activity_index} : i64",
            f"product_type = {_quote(component.product_type)}",
            f"product_id = {_quote(component.product_id)}",
        ]
        lines.append(
            '  "sim.component"() {'
            + ", ".join(component_attrs)
            + "} : () -> ()"
        )
    for route in plan.supply_routes:
        route_attrs = [
            f"source_node_index = {route.source_node_index} : i64",
            f"destination_node_index = {route.destination_node_index} : i64",
            f"product_id = {_quote(route.product_id)}",
        ]
        lines.append(
            '  "sim.supply_route"() {'
            + ", ".join(route_attrs)
            + "} : () -> ()"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _mlir_tool(explicit: Path | None) -> Path:
    if explicit:
        return explicit
    prefix = os.environ.get("MLIR_PREFIX")
    candidates = [Path(prefix) / "bin/mlir-opt"] if prefix else []
    candidates.extend(
        [Path("/opt/homebrew/opt/llvm/bin/mlir-opt"), Path(shutil.which("mlir-opt") or "")]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("mlir-opt not found; set --mlir-opt or MLIR_PREFIX")


def run_mlir_pass(
    plan: object,
    plugin_dir: Path,
    mlir_opt: Path | None,
    *,
    build_index: bool,
    mlir_output: Path | None,
) -> tuple[dict[str, object] | None, float, str]:
    tool = _mlir_tool(mlir_opt)
    version_result = subprocess.run(
        [str(tool), "--version"], check=True, capture_output=True, text=True
    )
    version_text = version_result.stdout + version_result.stderr
    if EXPECTED_MLIR_VERSION not in version_text:
        raise RuntimeError(
            f"MLIR must be pinned to {EXPECTED_MLIR_VERSION}; got {version_text.strip()}"
        )
    dialect = plugin_dir / "SimDialect.so"
    pass_plugin = plugin_dir / "SimResourceDispatchPass.so"
    if not dialect.is_file() or not pass_plugin.is_file():
        raise RuntimeError(
            f"MLIR plugins missing under {plugin_dir}; build tools/mlir_dispatch first"
        )

    with tempfile.TemporaryDirectory(prefix="sim-mlir-pilot-") as temporary:
        temporary_path = Path(temporary)
        input_path = temporary_path / "core.mlir"
        output_path = temporary_path / "resource-index.json"
        input_path.write_text(emit_sim_module(plan), encoding="utf-8")
        pass_options = ["build-index=1"] if build_index else ["build-index=0"]
        if build_index:
            pass_options.append(f"json-output={output_path}")
        pipeline = "builtin.module(sim-build-resource-dependency-index{" + " ".join(pass_options) + "})"
        command = [
            str(tool),
            f"--load-dialect-plugin={dialect.resolve()}",
            f"--load-pass-plugin={pass_plugin.resolve()}",
            str(input_path),
            "--pass-pipeline=" + pipeline,
            "-o",
            str(mlir_output.resolve()) if mlir_output else os.devnull,
        ]
        if mlir_output:
            mlir_output.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        completed = subprocess.run(command, capture_output=True, text=True)
        elapsed = time.perf_counter() - started
        if completed.returncode:
            raise RuntimeError(
                "MLIR compilation failed:\n"
                + completed.stdout
                + completed.stderr
                + "\nCommand: "
                + " ".join(command)
            )
        if mlir_output:
            rendered = mlir_output.read_text(encoding="utf-8")
            mlir_output.write_text(rendered.rstrip("\n") + "\n", encoding="utf-8")
        if not build_index:
            return None, elapsed, EXPECTED_MLIR_VERSION
        index = json.loads(output_path.read_text(encoding="utf-8"))
        return index, elapsed, EXPECTED_MLIR_VERSION


def _with_checksum(index: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(index)
    checksum_body = json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    result["checksum"] = hashlib.sha256(checksum_body).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--semantic-profile",
        choices=("legacy-minute-v1", "event-time-v2"),
        default="legacy-minute-v1",
    )
    parser.add_argument("--plugin-dir", type=Path)
    parser.add_argument("--mlir-opt", type=Path)
    parser.add_argument(
        "--mlir-output",
        type=Path,
        help="write the verified (and, when enabled, indexed) sim module",
    )
    parser.add_argument(
        "--disable-business-pass",
        action="store_true",
        help="parse and verify the sim Core IR while omitting the resource index",
    )
    args = parser.parse_args()
    plugin_dir = args.plugin_dir or Path(__file__).resolve().parents[1] / "tools/mlir_dispatch/build"
    if not (plugin_dir / "SimDialect.so").is_file():
        fallback = plugin_dir.parent / "build-make"
        if (fallback / "SimDialect.so").is_file():
            plugin_dir = fallback

    started = time.perf_counter()
    value = json.loads(args.input.read_text(encoding="utf-8"))
    if value.get('version') == CORE_VERSION:
        core = CoreIR.from_dict(value)
    else:
        business = BusinessIR.from_dict(value) if value.get('version') == BUSINESS_VERSION else import_business_ir(value, semantic_profile=args.semantic_profile)
        core = lower_business(business)
    compile_seconds = time.perf_counter() - started
    index, mlir_seconds, mlir_version = run_mlir_pass(
        core,
        plugin_dir,
        args.mlir_opt,
        build_index=not args.disable_business_pass,
        mlir_output=args.mlir_output,
    )
    plan = compile_core(core, resource_dispatch_index=_with_checksum(index) if index is not None else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "plan_fingerprint": plan.fingerprint,
                "core_fingerprint": core.fingerprint,
                "business_fingerprint": core.payload["source"]["business_fingerprint"],
                "source_inputs_sha256": plan.source_inputs_sha256,
                "mlir_version": mlir_version,
                "business_pass_enabled": index is not None,
                "candidate_rule_count": (
                    index["candidate_rule_count"] if index is not None else 0
                ),
                "resource_dispatch_index_checksum": (
                    plan.resource_dispatch_index.get("checksum")
                    if plan.resource_dispatch_index is not None
                    else None
                ),
                "mlir_output_sha256": (
                    hashlib.sha256(args.mlir_output.read_bytes()).hexdigest()
                    if args.mlir_output is not None
                    else None
                ),
                "python_compile_seconds": compile_seconds,
                "mlir_seconds": mlir_seconds,
                "aircraft": len(plan.aircraft),
                "missions": len(plan.missions),
                "activities": len(plan.activities),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
