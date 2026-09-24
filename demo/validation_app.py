#!/usr/bin/env python3
"""Local, read-only comparison UI over the existing compiler and runtime CLIs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CASES = {
    "B1": ROOT / "tests/fixtures/synthetic/b1-daily-operations.json",
    "B3": ROOT / "tests/fixtures/synthetic/b3-upstream-transport.json",
    "F35": ROOT / "tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json",
}
PROFILES = {"minute": "legacy-minute-v1", "O5": "event-time-v2"}
RUNTIME = ROOT / "rust/runtime/target/release/sim-engine-runtime"
COMPILER = ROOT / "rust/compiler/target/release/sim-engine-compiler-aot"
PAGE = Path(__file__).with_name("index.html")


def _command(command: list[str], *, timeout: int = 240) -> tuple[dict[str, Any], int]:
    started = time.perf_counter_ns()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=timeout
    )
    wall_ns = time.perf_counter_ns() - started
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip()[-4000:])
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    metadata = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else {}
    return metadata, wall_ns


def _input(request: dict[str, Any]) -> tuple[str, list[int], int, str, bool, bool]:
    case = request.get("case")
    profile = request.get("profile")
    if case not in CASES or profile not in PROFILES:
        raise ValueError("Select a supported case and time profile")
    seed = int(request.get("seed", 0))
    samples = int(request.get("samples", 1))
    threads = int(request.get("threads", 1))
    indexed = request.get("mlir_index") is True
    cached = request.get("plan_cache") is True
    if seed < 0 or seed + samples - 1 > 2**64 - 1:
        raise ValueError("Seed range must fit u64")
    if not 1 <= samples <= 8 or not 1 <= threads <= 8:
        raise ValueError("Samples and threads must each be between 1 and 8")
    if indexed and cached:
        raise ValueError("The MLIR index and AOT binary cache are not a supported combined path")
    return case, list(range(seed, seed + samples)), threads, profile, indexed, cached


def _compile(
    case: str, profile: str, indexed: bool, cache_dir: Path | None, output: Path
) -> dict[str, Any]:
    source = CASES[case]
    semantic_profile = PROFILES[profile]
    if indexed:
        plugin_dir = os.environ.get("SIM_ENGINE_MLIR_PLUGIN_DIR")
        mlir_opt = os.environ.get("SIM_ENGINE_MLIR_OPT")
        if not plugin_dir or not mlir_opt:
            raise RuntimeError(
                "MLIR index requires SIM_ENGINE_MLIR_PLUGIN_DIR and SIM_ENGINE_MLIR_OPT"
            )
        command = [
            sys.executable, str(ROOT / "scripts/compile_mlir_execution_plan.py"),
            str(source), str(output), "--semantic-profile", semantic_profile,
            "--plugin-dir", plugin_dir, "--mlir-opt", mlir_opt,
        ]
        metadata, wall_ns = _command(command)
        plan_json = output
    else:
        if not COMPILER.is_file():
            raise RuntimeError("Build rust/compiler in release mode before starting the demo")
        plan_json = output.with_suffix(".json")
        command = [
            str(COMPILER), str(source), str(output), "--semantic-profile",
            semantic_profile, "--json-output", str(plan_json),
        ]
        if cache_dir is not None:
            command.extend(("--cache-dir", str(cache_dir)))
        metadata, wall_ns = _command(command)
    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    return {
        "path": output,
        "metadata": metadata,
        "plan": plan,
        "compile_wall_ns": wall_ns,
        "cache_hit": bool(metadata.get("cache_hit", False)),
    }


def _run(compiled: dict[str, Any], seeds: list[int], threads: int, output: Path) -> dict[str, Any]:
    if not RUNTIME.is_file():
        raise RuntimeError("Build rust/runtime in release mode before starting the demo")
    command = [
        str(RUNTIME), str(compiled["path"]), str(output),
        "--seeds", ",".join(map(str, seeds)), "--worker-threads", str(threads),
        "--observation-level", "full",
    ]
    _, batch_wall_ns = _command(command)
    batch = json.loads(output.read_text(encoding="utf-8"))
    sample_output = output.with_name(output.stem + "-probe.json")
    profile_output = output.with_name(output.stem + "-profile.json")
    _command([
        str(RUNTIME), str(compiled["path"]), str(sample_output),
        "--seed", str(seeds[0]), "--observation-level", "full",
        "--profile-output", str(profile_output),
    ])
    probe = json.loads(sample_output.read_text(encoding="utf-8"))
    profile = json.loads(profile_output.read_text(encoding="utf-8"))
    if _business(probe) != _business(batch["samples"][0]["result"]):
        raise RuntimeError("Profile probe changed the first sample result")
    return {"batch": batch, "batch_wall_ns": batch_wall_ns, "probe": profile}


def _business(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "plan_fingerprint"}


def _fixed_contract(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in plan.items()
        if key not in ("semantic_profile", "resource_dispatch_index")
    }


def _compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    from sim_engine_compiler.reference.conformance import first_divergence

    if len(left["batch"]["samples"]) != len(right["batch"]["samples"]):
        raise RuntimeError("Batch sample counts differ")
    for before, after in zip(left["batch"]["samples"], right["batch"]["samples"], strict=True):
        if before["seed"] != after["seed"] or before["sample_index"] != after["sample_index"]:
            raise RuntimeError("Batch seed or sample order differs")
        difference = first_divergence(_business(before["result"]), _business(after["result"]))
        if difference:
            return {
                "equal": False,
                "sample_index": before["sample_index"], "seed": before["seed"],
                "path": difference.path,
                "expected": str(difference.expected)[:800],
                "actual": str(difference.actual)[:800],
                "rule_id": difference.business_rule_id,
                "source_path": difference.source_path,
            }
    return {"equal": True}


def _arm(name: str, compiled: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    plan = compiled["plan"]
    profile = run["probe"]
    return {
        "name": name,
        "semantic_profile": plan["semantic_profile"],
        "plan_fingerprint": compiled["metadata"]["plan_fingerprint"],
        "cache_hit": compiled["cache_hit"],
        "index_enabled": plan.get("resource_dispatch_index") is not None,
        "index_checksum": (plan.get("resource_dispatch_index") or {}).get("checksum"),
        "compile_wall_ns": compiled["compile_wall_ns"],
        "plan_load_ns": profile["plan_load_ns"],
        "initialization_ns": profile["initialization_ns"],
        "execution_ns": profile["execution_ns"],
        "batch_wall_ns": run["batch_wall_ns"],
        "end_to_end_batch_wall_ns": compiled["compile_wall_ns"] + run["batch_wall_ns"],
        "candidate_visits": profile["profile"]["resource_dispatch_candidate_visits"],
        "guard_evaluations": profile["profile"]["resource_dispatch_guard_evaluations"],
        "dispatch_cache_hits": profile["profile"]["resource_dispatch_cache_hits"],
        "worker_threads": run["batch"]["worker_threads"],
        "sample_count": run["batch"]["sample_count"],
    }


def compare(request: dict[str, Any]) -> dict[str, Any]:
    case, seeds, threads, profile, indexed, cached = _input(request)
    if not RUNTIME.is_file() or not COMPILER.is_file():
        raise RuntimeError(
            "Build release CLIs first: cargo build --release --locked --manifest-path "
            "rust/runtime/Cargo.toml and rust/compiler/Cargo.toml"
        )
    with tempfile.TemporaryDirectory(prefix="sim-engine-validation-") as temporary:
        directory = Path(temporary)
        baseline_plan = _compile(case, "minute", False, None, directory / "baseline.seplan")
        selected_plan = _compile(
            case, profile, indexed, None,
            directory / ("selected-plan.json" if indexed else "selected.seplan"),
        )
        if _fixed_contract(baseline_plan["plan"]) != _fixed_contract(selected_plan["plan"]):
            raise RuntimeError("Compiled plans differ outside the selected time profile and index")
        baseline_run = _run(baseline_plan, seeds, threads, directory / "baseline-result.json")
        selected_run = _run(selected_plan, seeds, threads, directory / "selected-result.json")
        arms = [_arm("分钟基线", baseline_plan, baseline_run), _arm("算法／索引", selected_plan, selected_run)]
        correctness = {"algorithm": _compare(baseline_run, selected_run)}
        if cached:
            cache_dir = directory / "cache"
            cold = _compile(case, profile, False, cache_dir, directory / "cold.seplan")
            warm = _compile(case, profile, False, cache_dir, directory / "warm.seplan")
            if cold["cache_hit"] or not warm["cache_hit"]:
                raise RuntimeError("Expected a cold cache miss followed by a warm cache hit")
            if cold["plan"] != selected_plan["plan"] or warm["plan"] != selected_plan["plan"]:
                raise RuntimeError("Cache changed the compiled execution plan")
            cold_run = _run(cold, seeds, threads, directory / "cold-result.json")
            warm_run = _run(warm, seeds, threads, directory / "warm-result.json")
            arms.extend((
                _arm("缓存首次生成", cold, cold_run),
                _arm("缓存命中", warm, warm_run),
            ))
            correctness["cache_cold"] = _compare(selected_run, cold_run)
            correctness["cache"] = _compare(selected_run, warm_run)
        source_hashes = {arm["plan"]["source_inputs_sha256"] for arm in (baseline_plan, selected_plan)}
        if len(source_hashes) != 1:
            raise RuntimeError("Compiled arms have different canonical input fingerprints")
        version = subprocess.check_output(
            [str(RUNTIME), "--version"], cwd=ROOT, text=True
        ).strip()
        build = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        clean = not subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip()
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "case": case, "seeds": seeds, "requested_threads": threads,
            "algorithm_changed": profile != "minute" or indexed,
            "source_inputs_sha256": source_hashes.pop(),
            "input_file_sha256": hashlib.sha256(CASES[case].read_bytes()).hexdigest(),
            "contract": {
                "plan_version": baseline_plan["plan"]["plan_version"],
                "rng_profile": baseline_plan["plan"]["rng_profile"],
                "work_policy": baseline_plan["plan"]["work_policy"],
                "observation_level": "full",
            },
            "engine": {
                "runtime_version": version,
                "compiler_version": baseline_plan["metadata"].get("compiler_version"),
                "git_checkout_commit": build,
                "git_worktree_clean": clean,
                "runtime_binary_sha256": hashlib.sha256(RUNTIME.read_bytes()).hexdigest(),
                "compiler_binary_sha256": hashlib.sha256(COMPILER.read_bytes()).hexdigest(),
            },
            "arms": arms, "correctness": correctness,
            "timing_note": "单次交互运行仅供诊断，不是正式性能基准。编译与批量端到端为进程墙钟；加载、初始化、执行和机制计数来自首个 seed 的单样本 profile。批量墙钟包含进程启动、加载、初始化、执行和结果写入。",
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        body = PAGE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/compare":
            self.send_error(404)
            return
        try:
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                raise ValueError("Expected application/json")
            origin = self.headers.get("Origin")
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if origin is not None and origin != expected_origin:
                raise ValueError("Only same-origin local requests are accepted")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16384:
                raise ValueError("Request body must be at most 16 KiB")
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict):
                raise ValueError("Expected a JSON object")
            response = compare(request)
            status = 200
        except (TypeError, ValueError, RuntimeError, subprocess.TimeoutExpired, OSError) as error:
            response = {"error": str(error)}
            status = 400
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Validation UI: http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
