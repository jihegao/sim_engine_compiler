#!/usr/bin/env python3
"""Run the F35 MLIR resource-dispatch pilot with semantic and cost evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json"
)
EXPECTED_MLIR_VERSION = "23.1.1"


def checked(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    source_root = str(ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        item for item in (source_root, environment.get("PYTHONPATH", "")) if item
    )
    result = subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(
            "command failed:\n"
            + " ".join(command)
            + "\n"
            + result.stdout
            + result.stderr
        )
    return result


def timed_command(command: list[str]) -> tuple[float, dict[str, object]]:
    started = time.perf_counter()
    result = checked(command)
    elapsed = time.perf_counter() - started
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    metadata = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else {}
    return elapsed, metadata


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markdown_summary(
    report: dict[str, object], compile_rows: dict[str, dict[str, object]], output: Path
) -> str:
    arms = [
        ("现有编译链", "existing_compile_chain", "baseline"),
        ("MLIR 验证，业务 pass 关闭", "mlir_business_pass_disabled", "mlir_off"),
        ("MLIR 资源索引 pass 开启", "mlir_business_pass_enabled", "mlir_on"),
    ]
    lines = [
        "# MLIR resource dispatch pilot: F35 real-case evidence",
        "",
        f"- Input file SHA-256: `{report['input_sha256']}`",
        f"- Canonical source input SHA-256: `{report['source_inputs_sha256']}`",
        f"- Upstream spare_mvp revision: `{report['spare_mvp_commit']}`",
        f"- Semantic plan fingerprint: `{report['semantic_plan_fingerprint']}`",
        f"- LLVM/MLIR: `{report['mlir_version']}`; Rust: `{report['rustc']}`",
        f"- Seeds/runtime repeats/compiler repeats: `{report['seeds']}` / `{report['repeats']}` / `{report['compile_repeats']}`; complete `RunResult` JSON trees were compared exactly.",
        f"- MLIR emitted `{report['candidate_rule_count']}` candidate rules.",
        "",
        "| Arm | Compile wall (s) | Candidate visits | Guard evaluations | Cache hits | Median execution (ms) | Median runtime end-to-end (ms) | Compile + load + all runtime samples (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    runtime_records = report["runtime"]["records"]
    load_fields = {
        "baseline": "baseline_plan_load_parse_validate_ns",
        "mlir_off": "mlir_disabled_plan_load_parse_validate_ns",
        "mlir_on": "mlir_enabled_plan_load_parse_validate_ns",
    }
    for label, arm_name, compile_key in arms:
        records = [item for item in runtime_records if item["arm"] == arm_name]
        visits = sum(item["resource_dispatch_candidate_visits"] for item in records)
        guards = sum(item["resource_dispatch_guard_evaluations"] for item in records)
        hits = sum(item["resource_dispatch_cache_hits"] for item in records)
        execution_ms = statistics.median(item["execution_ns"] for item in records) / 1e6
        e2e_ms = statistics.median(item["end_to_end_ns"] for item in records) / 1e6
        runtime_total_s = (
            sum(item["end_to_end_ns"] for item in records)
            + report["runtime"][load_fields[compile_key]]
        ) / 1e9
        compile_s = float(compile_rows[compile_key]["compile_wall_seconds"])
        lines.append(
            f"| {label} | {compile_s:.4f} | {visits} | {guards} | {hits} | {execution_ms:.3f} | {e2e_ms:.3f} | {compile_s + runtime_total_s:.4f} |"
        )
    lines.extend(
        [
            "",
            f"Exact full-result parity: **{report['runtime']['exact_full_result_parity']}** across all arms and seeds.",
            "",
            "The runtime still visits waiting jobs in existing priority/time/job-ID order to preserve event placement. `guard evaluations` counts full dynamic spare, route, and capacity checks; cache hits replay the original per-minute capacity delay event where required. The measurement does not claim fewer outer waiting-list visits.",
            "",
            "`Compile + load + all runtime samples` includes one compile, one plan read/parse/validation, and the measured end-to-end runtime of every seed/repeat. The one-time MLIR plugin and Rust binary builds are excluded. Detailed per-run counters and nanosecond phase profiles are in `benchmark.json`; generated plans and compiler timing metadata are adjacent files.",
            "",
        ]
    )
    if report["runtime"]["guard_reduction_percent"] <= 0:
        lines.append(
            "Decision: the semantic integration passed, but the pass did not reduce total guard evaluations on this workload; do not claim a runtime win or promote this optimization from the F35 evidence."
        )
    elif report["total_cost_reduction_percent"] <= 0:
        lines.append(
            f"Decision: the pass reduced guard evaluations by {report['runtime']['guard_reduction_percent']:.2f}%, but compile + load + measured sample cost is {abs(report['total_cost_delta_seconds']):.4f}s higher than baseline for this run count. This evidence does not show a total-cost win; the approximate break-even is {report['estimated_break_even_samples']} samples if the measured per-sample runtime saving holds."
        )
    else:
        lines.append(
            f"Decision: guard evaluations fell by {report['runtime']['guard_reduction_percent']:.2f}%, and compile + load + sample total cost fell by {report['total_cost_reduction_percent']:.2f}% for this workload. This is F35-specific evidence, not a general scaling guarantee."
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--plugin-dir", type=Path)
    parser.add_argument("--mlir-opt", type=Path)
    parser.add_argument("--seeds", default="0,1,7")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--compile-repeats", type=int, default=3)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError("the pilot requires the repository's Python 3.12+ environment")
    if args.repeats < 1:
        raise ValueError("--repeats must be positive")
    if args.compile_repeats < 1:
        raise ValueError("--compile-repeats must be positive")

    input_path = args.input.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    llvm_prefix = Path(os.environ.get("MLIR_PREFIX", "/opt/homebrew/opt/llvm")).resolve()
    mlir_opt = args.mlir_opt or llvm_prefix / "bin/mlir-opt"
    plugin_dir = args.plugin_dir or ROOT / "tools/mlir_dispatch/build-unix"

    checked(
        [
            "cmake",
            "-G",
            "Unix Makefiles",
            "-S",
            str(ROOT / "tools/mlir_dispatch"),
            "-B",
            str(plugin_dir),
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DLLVM_DIR={llvm_prefix / 'lib/cmake/llvm'}",
            f"-DMLIR_DIR={llvm_prefix / 'lib/cmake/mlir'}",
        ]
    )
    checked(["cmake", "--build", str(plugin_dir), "--parallel", "2"])

    cargo = shutil.which("cargo")
    if not cargo:
        raise RuntimeError("cargo not found")
    checked(
        [
            cargo,
            "build",
            "--locked",
            "--release",
            "--bin",
            "sim-engine-runtime",
            "--bin",
            "mlir_resource_dispatch_benchmark",
            "--manifest-path",
            str(ROOT / "rust/runtime/Cargo.toml"),
        ]
    )

    plan_paths = {
        "baseline": output / "baseline-plan.json",
        "mlir_off": output / "mlir-pass-off-plan.json",
        "mlir_on": output / "mlir-pass-on-plan.json",
    }
    compile_rows: dict[str, dict[str, object]] = {}
    def compile_command(
        key: str, destination: Path, mlir_output: Path | None = None
    ) -> list[str]:
        common = [
            sys.executable,
            str(ROOT / "scripts/compile_execution_plan.py")
            if key == "baseline"
            else str(ROOT / "scripts/compile_mlir_execution_plan.py"),
            str(input_path),
            str(destination),
        ]
        if key != "baseline":
            common.extend(("--plugin-dir", str(plugin_dir), "--mlir-opt", str(mlir_opt)))
            if mlir_output:
                common.extend(("--mlir-output", str(mlir_output)))
        if key == "mlir_off":
            common.append("--disable-business-pass")
        return common

    with tempfile.TemporaryDirectory(prefix="sim-mlir-compile-warmup-") as temp:
        warmup_dir = Path(temp)
        for key in ("baseline", "mlir_off", "mlir_on"):
            timed_command(compile_command(key, warmup_dir / f"{key}.json"))

    compile_samples: dict[str, list[float]] = {
        key: [] for key in ("baseline", "mlir_off", "mlir_on")
    }
    compile_metadata: dict[str, list[dict[str, object]]] = {
        key: [] for key in compile_samples
    }
    for repeat in range(args.compile_repeats):
        order = (
            ("baseline", "mlir_off", "mlir_on")
            if repeat % 2 == 0
            else ("mlir_on", "mlir_off", "baseline")
        )
        for key in order:
            mlir_output = (
                output / f"{key}-core.mlir" if key != "baseline" else None
            )
            command = compile_command(key, plan_paths[key], mlir_output)
            elapsed, metadata = timed_command(command)
            compile_samples[key].append(elapsed)
            compile_metadata[key].append(metadata)
    for key in compile_samples:
        fingerprints = {
            item.get("plan_fingerprint") for item in compile_metadata[key]
        }
        if len(fingerprints) != 1:
            raise RuntimeError(f"{key} compiler output changed semantic plan fingerprint")
        if key == "mlir_on":
            checksums = {
                item.get("resource_dispatch_index_checksum")
                for item in compile_metadata[key]
            }
            if len(checksums) != 1 or None in checksums:
                raise RuntimeError("MLIR resource-index pass output is not deterministic")
        if key != "baseline":
            module_hashes = {
                item.get("mlir_output_sha256") for item in compile_metadata[key]
            }
            if len(module_hashes) != 1 or None in module_hashes:
                raise RuntimeError(f"{key} sim module output is not deterministic")
        compile_rows[key] = {
            "command": compile_command(
                key,
                plan_paths[key],
                output / f"{key}-core.mlir" if key != "baseline" else None,
            ),
            "compile_wall_seconds": statistics.median(compile_samples[key]),
            "compile_wall_seconds_samples": compile_samples[key],
            "compiler_metadata_samples": compile_metadata[key],
            "plan_bytes": plan_paths[key].stat().st_size,
            "plan_sha256": sha256(plan_paths[key]),
        }
    (output / "compile-report.json").write_text(
        json.dumps(compile_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    runtime_report_path = output / "benchmark.json"
    benchmark_binary = ROOT / "rust/runtime/target/release/mlir_resource_dispatch_benchmark"
    checked(
        [
            str(benchmark_binary),
            str(plan_paths["baseline"]),
            str(plan_paths["mlir_off"]),
            str(plan_paths["mlir_on"]),
            str(runtime_report_path),
            "--seeds",
            args.seeds,
            "--repeats",
            str(args.repeats),
        ]
    )
    runtime = json.loads(runtime_report_path.read_text(encoding="utf-8"))
    records = runtime["records"]
    by_arm = {
        name: [record for record in records if record["arm"] == name]
        for name in (
            "existing_compile_chain",
            "mlir_business_pass_disabled",
            "mlir_business_pass_enabled",
        )
    }
    baseline_guards = sum(
        item["resource_dispatch_guard_evaluations"]
        for item in by_arm["existing_compile_chain"]
    )
    optimized_guards = sum(
        item["resource_dispatch_guard_evaluations"]
        for item in by_arm["mlir_business_pass_enabled"]
    )
    guard_reduction_percent = (
        (baseline_guards - optimized_guards) * 100.0 / baseline_guards
        if baseline_guards
        else 0.0
    )
    baseline_total_cost = (
        float(compile_rows["baseline"]["compile_wall_seconds"])
        + runtime["baseline_plan_load_parse_validate_ns"] / 1e9
        + sum(
            item["end_to_end_ns"]
            for item in by_arm["existing_compile_chain"]
        )
        / 1e9
    )
    optimized_total_cost = (
        float(compile_rows["mlir_on"]["compile_wall_seconds"])
        + runtime["mlir_enabled_plan_load_parse_validate_ns"] / 1e9
        + sum(
            item["end_to_end_ns"]
            for item in by_arm["mlir_business_pass_enabled"]
        )
        / 1e9
    )
    baseline_per_sample = statistics.median(
        item["end_to_end_ns"] for item in by_arm["existing_compile_chain"]
    )
    optimized_per_sample = statistics.median(
        item["end_to_end_ns"] for item in by_arm["mlir_business_pass_enabled"]
    )
    per_sample_saving = baseline_per_sample - optimized_per_sample
    baseline_one_time_ns = int(
        float(compile_rows["baseline"]["compile_wall_seconds"]) * 1e9
        + runtime["baseline_plan_load_parse_validate_ns"]
    )
    optimized_one_time_ns = int(
        float(compile_rows["mlir_on"]["compile_wall_seconds"]) * 1e9
        + runtime["mlir_enabled_plan_load_parse_validate_ns"]
    )
    compile_and_load_delta_ns = max(
        0,
        optimized_one_time_ns - baseline_one_time_ns,
    )
    estimated_break_even_samples = (
        (compile_and_load_delta_ns + per_sample_saving - 1) // per_sample_saving
        if per_sample_saving > 0
        else None
    )
    report: dict[str, object] = {
        "schema_version": "mlir-resource-dispatch-pilot-evidence/v1",
        "input_path": str(input_path.relative_to(ROOT))
        if input_path.is_relative_to(ROOT)
        else str(input_path),
        "input_sha256": sha256(input_path),
        "source_inputs_sha256": compile_rows["baseline"]["compiler_metadata_samples"][-1].get(
            "source_inputs_sha256"
        ),
        "spare_mvp_commit": json.loads(
            (input_path.parent / "manifest.json").read_text(encoding="utf-8")
        )["spare_mvp_commit"],
        "semantic_plan_fingerprint": runtime["baseline_plan_fingerprint"],
        "mlir_version": EXPECTED_MLIR_VERSION,
        "rustc": checked(["rustc", "--version"]).stdout.strip(),
        "python": sys.version.split()[0],
        "host": platform.platform(),
        "seeds": [int(item) for item in args.seeds.split(",")],
        "repeats": args.repeats,
        "compile_repeats": args.compile_repeats,
        "candidate_rule_count": runtime["mlir_candidate_rule_count"],
        "total_cost_seconds_by_arm": {
            "baseline": baseline_total_cost,
            "mlir_on": optimized_total_cost,
        },
        "total_cost_delta_seconds": optimized_total_cost - baseline_total_cost,
        "total_cost_reduction_percent": (
            (baseline_total_cost - optimized_total_cost) * 100.0 / baseline_total_cost
            if baseline_total_cost
            else 0.0
        ),
        "estimated_break_even_samples": estimated_break_even_samples,
        "compile": compile_rows,
        "runtime": {
            **runtime,
            "guard_reduction_percent": guard_reduction_percent,
        },
    }
    (output / "evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = markdown_summary(report, compile_rows, output)
    (output / "README.md").write_text(summary, encoding="utf-8")
    print(output / "README.md")


if __name__ == "__main__":
    main()
