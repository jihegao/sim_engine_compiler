#!/usr/bin/env python3
"""Freeze, admit, measure and summarize the Issue #6 CPU batch baseline.

The formal ``measure`` command is intentionally separate from preparation.  It
is destructive only inside one newly frozen run directory, has a single
monotonic deadline, and cannot resume or retry a partial window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import signal
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/spare_mvp/f35-43day-5352a0d"
DEFAULT_INPUT = FIXTURE / "simulation-inputs.json"
DEFAULT_REFERENCE_PLAN = FIXTURE / "execution-plan.json"
DEFAULT_STAGE_BINARY = ROOT / "rust/runtime/target/release/stage-c-benchmark"
DEFAULT_RUNTIME_BINARY = ROOT / "rust/runtime/target/release/sim-engine-runtime"
DEFAULT_PYTHON = ROOT / ".venv/bin/python"
WORKER = Path(__file__).with_name("binding_worker.py")
BASE_COMMIT = "595cb5eee9987324b19a8c3566f201f937e05f15"
EXPECTED_HOST = "g-1503-amd128"
EXPECTED_INPUT_FILE_SHA256 = "a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d"
EXPECTED_SOURCE_DIGEST = "6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6"
EXPECTED_PROJECT_DIGEST = "220f41d8a4e71e1a4c6a91143c100368c0cdd1440cbdcbace57a28ae56582fa5"
EXPECTED_UPSTREAM_COMMIT = "5352a0d7757cbac012c75d516d1a7ac4ff15aa2a"
EXPECTED_PROFILE = "event-time-v2"
EXPECTED_WORK_POLICY = "stable-topological-serial"
EXPECTED_RNG_PROFILE = "legacy-sequential-v1"
EXPECTED_DURATION = 61920
EXPECTED_REFERENCE_PLAN_SHA256 = "548f77dfc61b9c545f5ac17eefcd5443f265a1530818696f9cafed7c3dd97298"
EXPECTED_REFERENCE_PLAN_FINGERPRINT = "f3a055330fe3c03bb9d47c745e12fdaeae11ac29ff355c1751534163fc7da256"
PINNED_TOOLCHAIN = "1.90.0"
CPUSET = "0-7"
CELL_TIME_BUDGET_SECONDS = 60.0
POSTFLIGHT_BUDGET_SECONDS = 10.0
WORKERS = [1, 2, 4, 8]
ROTATIONS = [[1, 2, 4, 8], [8, 4, 2, 1], [2, 4, 8, 1]]
OBSERVATIONS = ["summary", "full"]
BACKENDS = ["rust", "pyo3"]
SEEDS_N64 = [0, 1, 7, 7] * 16
SOURCE_SCOPE = ("src", "rust", "pyproject.toml")


class CellProcessInterrupted(RuntimeError):
    """Raised after the harness has killed and reaped its active child group."""

    def __init__(self, execution: dict[str, Any]):
        super().__init__("measurement interrupted by coordinator signal")
        self.execution = execution


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any, *, pretty: bool = True) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    else:
        text = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    return text.encode("utf-8")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_write(path, json_bytes(value))


def checked_output(command: Sequence[str], *, cwd: Path = ROOT) -> str:
    return subprocess.run(
        list(map(str, command)),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def command_fact(
    command: Sequence[str], *, timeout_seconds: float = 15.0
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(map(str, command)),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "command": list(map(str, command)),
            "exit_status": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": list(map(str, command)), "error": repr(error)}


def read_optional(path: str) -> dict[str, Any]:
    target = Path(path)
    try:
        data = target.read_bytes()
        return {"path": path, "value": data.decode("utf-8", "replace"), "sha256": sha256_bytes(data)}
    except OSError as error:
        return {"path": path, "unavailable": repr(error)}


def machine_snapshot(*, deadline_monotonic: float | None = None) -> dict[str, Any]:
    commands = [
        ["hostname"],
        ["uname", "-a"],
        ["lscpu"],
        ["lscpu", "-e=cpu,node,socket,core,online,maxmhz,minmhz"],
        ["numactl", "--hardware"],
        ["taskset", "-pc", str(os.getpid())],
        ["ps", "-eo", "pid,ppid,psr,pcpu,pmem,comm,args", "--sort=-pcpu"],
    ]
    files = [
        "/proc/meminfo",
        "/proc/loadavg",
        "/proc/self/status",
        "/sys/fs/cgroup/cpuset.cpus.effective",
        "/sys/fs/cgroup/cpuset.cpus",
        "/sys/fs/cgroup/cpu.max",
        "/sys/fs/cgroup/memory.max",
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
        "/sys/devices/system/cpu/cpufreq/boost",
        "/sys/devices/system/cpu/amd_pstate/cpb_boost",
    ]
    command_results = []
    for command in commands:
        timeout = 15.0
        if deadline_monotonic is not None:
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0:
                command_results.append(
                    {"command": command, "error": "postflight_deadline_exhausted"}
                )
                continue
            timeout = min(1.0, remaining)
        command_results.append(command_fact(command, timeout_seconds=timeout))
    return {
        "captured_at_unix_ns": time.time_ns(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "commands": command_results,
        "files": [read_optional(path) for path in files],
    }


def validate_placement() -> dict[str, Any]:
    if not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("sched_getaffinity is required for the formal Linux host")
    allowed = sorted(os.sched_getaffinity(0))
    selected = list(range(8))
    if not set(selected).issubset(allowed):
        raise RuntimeError(f"CPU set {CPUSET} is not allowed by process affinity")
    raw = checked_output(["lscpu", "-p=CPU,CORE,SOCKET,NODE"])
    rows: dict[int, tuple[int, int, int]] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        cpu, core, socket, node = (int(item) for item in line.split(","))
        rows[cpu] = (core, socket, node)
    if any(cpu not in rows for cpu in selected):
        raise RuntimeError("lscpu omitted one of CPUs 0-7")
    physical = {(rows[cpu][1], rows[cpu][0]) for cpu in selected}
    nodes = {rows[cpu][2] for cpu in selected}
    if len(physical) != 8 or len(nodes) != 1:
        raise RuntimeError("CPUs 0-7 are not eight distinct physical cores in one NUMA node")
    sibling_sets = {
        str(cpu): sorted(
            candidate
            for candidate, identity in rows.items()
            if identity[:2] == rows[cpu][:2]
        )
        for cpu in selected
    }
    expected_siblings = {str(cpu): [cpu, cpu + 64] for cpu in selected}
    if sibling_sets != expected_siblings:
        raise RuntimeError(
            f"unexpected SMT sibling topology: {sibling_sets}; expected {expected_siblings}"
        )
    return {
        "selected_logical_cpus": selected,
        "allowed_logical_cpus": allowed,
        "physical_core_identities": [list(value) for value in sorted(physical)],
        "numa_nodes": sorted(nodes),
        "smt_siblings": sibling_sets,
    }


def plan_identity(path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from sim_engine_compiler.ir.plan import ExecutionPlan

    raw = json.loads(path.read_text(encoding="utf-8"))
    plan = ExecutionPlan.from_dict(raw)
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "fingerprint": plan.fingerprint,
        "semantic_profile": plan.semantic_profile,
        "work_policy": plan.work_policy,
        "rng_profile": plan.rng_profile,
        "source_inputs_sha256": plan.source_inputs_sha256,
        "duration_minutes": plan.duration_minutes,
        "phases": list(plan.phases),
        "resource_dispatch_index_present": plan.resource_dispatch_index is not None,
    }


def validate_timed_plan(identity: dict[str, Any]) -> None:
    expected = {
        "semantic_profile": EXPECTED_PROFILE,
        "work_policy": EXPECTED_WORK_POLICY,
        "rng_profile": EXPECTED_RNG_PROFILE,
        "source_inputs_sha256": EXPECTED_SOURCE_DIGEST,
        "duration_minutes": EXPECTED_DURATION,
        "resource_dispatch_index_present": False,
    }
    mismatches = {
        key: {"expected": value, "actual": identity.get(key)}
        for key, value in expected.items()
        if identity.get(key) != value
    }
    reference = plan_identity(DEFAULT_REFERENCE_PLAN)
    if identity.get("phases") != reference["phases"]:
        mismatches["phases"] = {
            "expected": reference["phases"],
            "actual": identity.get("phases"),
        }
    if mismatches:
        raise RuntimeError(f"timed Plan identity mismatch: {mismatches}")


def measurement_list() -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    ordinal = 0
    for repeat, workers_order in enumerate(ROTATIONS):
        for workers in workers_order:
            for observation in OBSERVATIONS:
                for backend in BACKENDS:
                    cells.append(
                        {
                            "ordinal": ordinal,
                            "kind": "primary",
                            "repeat": repeat,
                            "sample_count": 64,
                            "worker_threads": workers,
                            "observation_level": observation,
                            "backend": backend,
                            "warmups": 1,
                            "measured_calls": 1,
                        }
                    )
                    ordinal += 1
    for sample_count, workers in ((1, 1), (8, 8)):
        for observation in OBSERVATIONS:
            for backend in BACKENDS:
                cells.append(
                    {
                        "ordinal": ordinal,
                        "kind": "startup_probe",
                        "repeat": None,
                        "sample_count": sample_count,
                        "worker_threads": workers,
                        "observation_level": observation,
                        "backend": backend,
                        "warmups": 1,
                        "measured_calls": 1,
                    }
                )
                ordinal += 1
    if len(cells) != 56:
        raise AssertionError(f"internal schedule error: {len(cells)} cells")
    return cells


def _git_source_identity() -> dict[str, Any]:
    status = checked_output(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *SOURCE_SCOPE,
        ]
    )
    if status:
        raise RuntimeError(f"runtime/compiler source scope is dirty: {status}")
    diff = subprocess.run(
        ["git", "diff", "--quiet", BASE_COMMIT, "--", *SOURCE_SCOPE],
        cwd=ROOT,
        check=False,
    )
    if diff.returncode != 0:
        raise RuntimeError("runtime/compiler source scope differs from frozen base commit")
    names = checked_output(
        ["git", "ls-tree", "-r", "--name-only", BASE_COMMIT, "--", *SOURCE_SCOPE]
    ).splitlines()
    hashes = {}
    for name in names:
        path = ROOT / name
        if not path.is_file():
            raise RuntimeError(f"base source file missing from worktree: {name}")
        hashes[name] = sha256_file(path)
    digest = sha256_bytes(json_bytes(hashes, pretty=False))
    return {
        "base_commit": BASE_COMMIT,
        "current_commit": checked_output(["git", "rev-parse", "HEAD"]),
        "scope": list(SOURCE_SCOPE),
        "tracked_file_count": len(hashes),
        "tracked_files_sha256": hashes,
        "aggregate_sha256": digest,
        "untracked_or_modified_entries": [],
    }


def validate_lineage(
    path: Path, *, plan: dict[str, Any], input_path: Path
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid compiler lineage JSON: {error}") from error
    if value.get("version") != "compiler-lineage/v2":
        raise RuntimeError("formal baseline requires compiler-lineage/v2")
    expected = {
        "canonical_sha256": EXPECTED_SOURCE_DIGEST,
        "plan_fingerprint": plan["fingerprint"],
    }
    mismatches = {
        key: {"expected": expected_value, "actual": value.get(key)}
        for key, expected_value in expected.items()
        if value.get(key) != expected_value
    }
    if mismatches:
        raise RuntimeError(f"compiler lineage identity mismatch: {mismatches}")
    if sha256_file(input_path) != EXPECTED_INPUT_FILE_SHA256:
        raise RuntimeError("lineage input file no longer matches frozen canonical input")
    return {
        "version": value["version"],
        "canonical_sha256": value["canonical_sha256"],
        "plan_fingerprint": value["plan_fingerprint"],
        "business_fingerprint": value.get("business_fingerprint"),
        "core_fingerprint": value.get("core_fingerprint"),
    }


def validate_compiler_command(
    raw: str, *, input_path: Path, plan_path: Path, lineage_path: Path
) -> list[str]:
    command = shlex.split(raw)
    required = {
        str(input_path.resolve()),
        str(plan_path.resolve()),
        "--semantic-profile",
        EXPECTED_PROFILE,
        "--artifacts-dir",
        str(lineage_path.resolve().parent),
    }
    if not required.issubset(command):
        raise RuntimeError(
            "compiler command must bind the absolute frozen input/output paths and event-time-v2"
        )
    entrypoints = []
    for token in command:
        candidate = Path(token)
        if candidate.name == "compile_ir.py":
            entrypoints.append(
                candidate.resolve()
                if candidate.is_absolute()
                else (ROOT / candidate).resolve()
            )
    if entrypoints != [(ROOT / "scripts/compile_ir.py").resolve()]:
        raise RuntimeError("compiler command must use the exact supported scripts/compile_ir.py")
    if any("dependency-dispatch" in token for token in command):
        raise RuntimeError("compiler command must not enable candidate dispatch")
    return command


def python_environment_identity(python: Path) -> dict[str, Any]:
    metadata = command_fact(
        [
            str(python),
            "-c",
            (
                "import json,platform,sys,sysconfig;"
                "print(json.dumps({'executable':sys.executable,'version':sys.version,"
                "'implementation':platform.python_implementation(),"
                "'prefix':sys.prefix,'base_prefix':sys.base_prefix,"
                "'exec_prefix':sys.exec_prefix,"
                "'soabi':sysconfig.get_config_var('SOABI')},sort_keys=True))"
            ),
        ]
    )
    packages = command_fact(
        [
            str(python),
            "-c",
            (
                "import importlib.metadata as m,json;"
                "rows=[{'name':d.metadata.get('Name'),'version':d.version,"
                "'direct_url':d.read_text('direct_url.json')} for d in m.distributions()];"
                "print(json.dumps(sorted(rows,key=lambda r:((r['name'] or '').lower(),"
                "r['version'] or '',r['direct_url'] or '')),sort_keys=True))"
            ),
        ]
    )
    if metadata.get("exit_status") != 0 or packages.get("exit_status") != 0:
        raise RuntimeError("unable to freeze Python environment identity")
    return {
        "metadata": json.loads(metadata["stdout"]),
        "installed_distributions": json.loads(packages["stdout"]),
    }


def _extension_for_python(python: Path) -> Path:
    code = (
        "import pathlib,sim_engine_compiler._runtime as m;"
        "print(pathlib.Path(m.__file__).resolve())"
    )
    value = checked_output([str(python), "-c", code])
    return Path(value)


def _require_file(path: Path, label: str) -> Path:
    path = path.resolve()
    if not path.is_file():
        raise RuntimeError(f"{label} does not exist: {path}")
    return path


def _require_python_path(path: Path) -> Path:
    # Keep the venv launcher path: resolving its symlink would discard venv
    # prefix discovery and silently select the global interpreter environment.
    path = path.expanduser().absolute()
    if not path.is_file():
        raise RuntimeError(f"binding Python does not exist: {path}")
    return path


def freeze(args: argparse.Namespace) -> Path:
    if platform.node() != EXPECTED_HOST:
        raise RuntimeError(f"formal subject host must be {EXPECTED_HOST!r}")
    plan = _require_file(args.plan, "timed Plan")
    input_path = _require_file(args.input, "canonical input")
    reference_plan = _require_file(args.reference_plan, "reference Plan")
    stage_binary = _require_file(args.stage_binary, "stage-c-benchmark")
    runtime_binary = _require_file(args.runtime_binary, "sim-engine-runtime")
    python = _require_python_path(args.python)
    lineage = _require_file(args.lineage, "canonical-to-Plan lineage")
    if sha256_file(input_path) != EXPECTED_INPUT_FILE_SHA256:
        raise RuntimeError("canonical input file digest mismatch")
    fixture_manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    if fixture_manifest.get("inputs_sha256") != EXPECTED_SOURCE_DIGEST:
        raise RuntimeError("fixture semantic input digest mismatch")
    if fixture_manifest.get("project_sha256") != EXPECTED_PROJECT_DIGEST:
        raise RuntimeError("fixture project digest mismatch")
    if fixture_manifest.get("spare_mvp_commit") != EXPECTED_UPSTREAM_COMMIT:
        raise RuntimeError("fixture upstream source commit mismatch")
    timed_plan = plan_identity(plan)
    validate_timed_plan(timed_plan)
    reference_identity = plan_identity(reference_plan)
    if (
        reference_identity["semantic_profile"] != "legacy-minute-v1"
        or reference_identity["sha256"] != EXPECTED_REFERENCE_PLAN_SHA256
        or reference_identity["fingerprint"] != EXPECTED_REFERENCE_PLAN_FINGERPRINT
    ):
        raise RuntimeError("reference Plan is not the exact checked-in F35 legacy Plan")
    lineage_identity = validate_lineage(
        lineage, plan=timed_plan, input_path=input_path
    )
    compiler_argv = validate_compiler_command(
        args.compiler_command,
        input_path=input_path,
        plan_path=plan,
        lineage_path=lineage,
    )
    placement = validate_placement()
    source = _git_source_identity()
    extension = _extension_for_python(python)
    extension = _require_file(extension, "PyO3 extension")
    python_environment = python_environment_identity(python)
    compiler_entrypoint = _require_file(
        ROOT / "scripts/compile_ir.py", "compiler entrypoint"
    )
    rustc = command_fact(["rustc", "+1.90.0", "-Vv"])
    cargo = command_fact(["cargo", "+1.90.0", "-V"])
    if rustc.get("exit_status") != 0 or "1.90.0" not in rustc.get("stdout", ""):
        raise RuntimeError("pinned Rust 1.90.0 toolchain is unavailable")
    if cargo.get("exit_status") != 0:
        raise RuntimeError("pinned Cargo is unavailable")

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = args.output_root.resolve() / f"run-{timestamp}-{os.getpid()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    seeds_path = run_dir / "seeds-n64.json"
    schedule_path = run_dir / "measurement-list.json"
    atomic_json(seeds_path, SEEDS_N64)
    atomic_json(schedule_path, measurement_list())
    snapshot = machine_snapshot()
    snapshot_path = run_dir / "machine-freeze.json"
    atomic_json(snapshot_path, snapshot)
    manifest = {
        "schema_version": "cpu-batch-freeze/v1",
        "status": "frozen_not_admitted_not_measured",
        "created_at_unix_ns": time.time_ns(),
        "protocol": {
            "path": str((Path(__file__).with_name("PROTOCOL.md")).resolve()),
            "sha256": sha256_file(Path(__file__).with_name("PROTOCOL.md")),
        },
        "repository": source,
        "host": EXPECTED_HOST,
        "cpuset": CPUSET,
        "deadline_seconds": 1200,
        "placement": placement,
        "canonical_input": {
            "path": str(input_path),
            "file_sha256": sha256_file(input_path),
            "semantic_sha256": EXPECTED_SOURCE_DIGEST,
            "project_sha256": EXPECTED_PROJECT_DIGEST,
            "upstream_commit": EXPECTED_UPSTREAM_COMMIT,
        },
        "reference_plan": reference_identity,
        "timed_plan": timed_plan,
        "compiler": {
            "command": args.compiler_command,
            "argv": compiler_argv,
            "lineage_path": str(lineage),
            "lineage_sha256": sha256_file(lineage),
            "lineage_bytes": lineage.stat().st_size,
            "lineage_identity": lineage_identity,
        },
        "artifacts": {
            "stage_c_benchmark": {"path": str(stage_binary), "sha256": sha256_file(stage_binary)},
            "runtime": {"path": str(runtime_binary), "sha256": sha256_file(runtime_binary)},
            "python": {"path": str(python), "sha256": sha256_file(python)},
            "pyo3_extension": {"path": str(extension), "sha256": sha256_file(extension)},
            "driver": {"path": str(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__))},
            "binding_worker": {"path": str(WORKER.resolve()), "sha256": sha256_file(WORKER)},
            "compiler_entrypoint": {"path": str(compiler_entrypoint), "sha256": sha256_file(compiler_entrypoint)},
            "cargo_lock": {
                "path": str((ROOT / "rust/runtime/Cargo.lock").resolve()),
                "sha256": sha256_file(ROOT / "rust/runtime/Cargo.lock"),
            },
        },
        "toolchain": {
            "required": PINNED_TOOLCHAIN,
            "rustc": rustc,
            "cargo": cargo,
            "python": command_fact([str(python), "--version"]),
            "python_environment": python_environment,
            "install_provenance": args.install_provenance,
        },
        "schedule": {
            "seeds_path": seeds_path.name,
            "seeds_sha256": sha256_file(seeds_path),
            "measurement_list_path": schedule_path.name,
            "measurement_list_sha256": sha256_file(schedule_path),
            "cell_count": 56,
            "workers": WORKERS,
            "rotations": ROTATIONS,
            "observations": OBSERVATIONS,
            "backends": BACKENDS,
        },
        "admission_policy": {
            "window_deadline_seconds": 1200,
            "cell_time_budget_seconds": CELL_TIME_BUDGET_SECONDS,
            "postflight_budget_seconds": POSTFLIGHT_BUDGET_SECONDS,
            "meaning": (
                "fixed pre-registered per-process cap, not a guarantee of unknown runtime; "
                "a cell starts only when this full budget remains and any timeout permanently closes the window"
            ),
        },
        "machine_snapshot": {
            "path": snapshot_path.name,
            "sha256": sha256_file(snapshot_path),
        },
        "timing_boundaries": {
            "rust_primary": "stage-c report phases.batch_execution_ns",
            "pyo3_primary": "binding worker call_ns; bundled public run_batch boundary",
            "rss": "GNU /usr/bin/time -v whole fresh process high-water RSS",
            "cold_wall": "driver monotonic subprocess wall including startup, warmup, measurement and evidence write",
        },
    }
    manifest_path = run_dir / "manifest.json"
    atomic_json(manifest_path, manifest)
    atomic_write(run_dir / "manifest.sha256", (sha256_file(manifest_path) + "\n").encode())
    for path in (seeds_path, schedule_path, snapshot_path, manifest_path, run_dir / "manifest.sha256"):
        path.chmod(0o444)
    print(run_dir)
    return run_dir


def load_frozen(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    expected = (run_dir / "manifest.sha256").read_text(encoding="ascii").strip()
    if sha256_file(manifest_path) != expected:
        raise RuntimeError("manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "cpu-batch-freeze/v1":
        raise RuntimeError("unsupported freeze manifest schema")
    protocol = manifest.get("protocol", {})
    protocol_path = Path(protocol.get("path", ""))
    if (
        not protocol_path.is_file()
        or protocol_path.resolve() != Path(__file__).with_name("PROTOCOL.md").resolve()
        or sha256_file(protocol_path) != protocol.get("sha256")
    ):
        raise RuntimeError("frozen protocol identity drift")
    if manifest.get("host") != EXPECTED_HOST or manifest.get("cpuset") != CPUSET:
        raise RuntimeError("frozen host or CPU placement contract drift")
    if manifest.get("deadline_seconds") != 1200:
        raise RuntimeError("frozen window deadline drift")
    schedule = manifest["schedule"]
    for name_key, hash_key in (
        ("seeds_path", "seeds_sha256"),
        ("measurement_list_path", "measurement_list_sha256"),
    ):
        path = run_dir / schedule[name_key]
        if sha256_file(path) != schedule[hash_key]:
            raise RuntimeError(f"frozen schedule artifact drift: {path.name}")
    seeds = json.loads((run_dir / schedule["seeds_path"]).read_text(encoding="utf-8"))
    cells = json.loads(
        (run_dir / schedule["measurement_list_path"]).read_text(encoding="utf-8")
    )
    if seeds != SEEDS_N64:
        raise RuntimeError("frozen seed list does not match the protocol")
    if cells != measurement_list():
        raise RuntimeError("frozen measurement list does not match the protocol")
    canonical = manifest["canonical_input"]
    if sha256_file(Path(canonical["path"])) != canonical["file_sha256"]:
        raise RuntimeError("canonical input byte drift")
    if (
        canonical.get("file_sha256") != EXPECTED_INPUT_FILE_SHA256
        or canonical.get("semantic_sha256") != EXPECTED_SOURCE_DIGEST
        or canonical.get("project_sha256") != EXPECTED_PROJECT_DIGEST
        or canonical.get("upstream_commit") != EXPECTED_UPSTREAM_COMMIT
    ):
        raise RuntimeError("canonical input manifest identity drift")
    compiler = manifest["compiler"]
    if sha256_file(Path(compiler["lineage_path"])) != compiler["lineage_sha256"]:
        raise RuntimeError("canonical-to-Plan lineage drift")
    timed_identity = plan_identity(Path(manifest["timed_plan"]["path"]))
    if timed_identity != manifest["timed_plan"]:
        raise RuntimeError("timed Plan identity drift")
    validate_timed_plan(timed_identity)
    reference_identity = plan_identity(Path(manifest["reference_plan"]["path"]))
    if reference_identity != manifest["reference_plan"]:
        raise RuntimeError("reference Plan identity drift")
    if (
        reference_identity["sha256"] != EXPECTED_REFERENCE_PLAN_SHA256
        or reference_identity["fingerprint"] != EXPECTED_REFERENCE_PLAN_FINGERPRINT
        or reference_identity["semantic_profile"] != "legacy-minute-v1"
    ):
        raise RuntimeError("reference Plan is not the exact checked-in F35 legacy Plan")
    lineage_identity = validate_lineage(
        Path(compiler["lineage_path"]),
        plan=timed_identity,
        input_path=Path(canonical["path"]),
    )
    if lineage_identity != compiler.get("lineage_identity"):
        raise RuntimeError("compiler lineage semantic identity drift")
    compiler_argv = validate_compiler_command(
        compiler["command"],
        input_path=Path(canonical["path"]),
        plan_path=Path(timed_identity["path"]),
        lineage_path=Path(compiler["lineage_path"]),
    )
    if compiler_argv != compiler.get("argv"):
        raise RuntimeError("compiler command identity drift")
    admission = manifest.get("admission_policy", {})
    budget = admission.get("cell_time_budget_seconds")
    if (
        budget != CELL_TIME_BUDGET_SECONDS
        or admission.get("window_deadline_seconds") != 1200
        or admission.get("postflight_budget_seconds") != POSTFLIGHT_BUDGET_SECONDS
    ):
        raise RuntimeError("per-cell time-budget admission policy drift")
    for artifact in manifest["artifacts"].values():
        if sha256_file(Path(artifact["path"])) != artifact["sha256"]:
            raise RuntimeError(f"frozen artifact drift: {artifact['path']}")
    current_python_environment = python_environment_identity(
        Path(manifest["artifacts"]["python"]["path"])
    )
    if current_python_environment != manifest["toolchain"]["python_environment"]:
        raise RuntimeError("Python environment identity drift")
    current_source = _git_source_identity()
    if current_source["aggregate_sha256"] != manifest["repository"]["aggregate_sha256"]:
        raise RuntimeError("runtime/compiler source drift")
    return manifest


def validate_execution_artifacts(manifest: dict[str, Any]) -> None:
    if sha256_file(Path(manifest["timed_plan"]["path"])) != manifest["timed_plan"]["sha256"]:
        raise RuntimeError("timed Plan bytes drifted during the formal window")
    for name, artifact in manifest["artifacts"].items():
        if sha256_file(Path(artifact["path"])) != artifact["sha256"]:
            raise RuntimeError(f"execution artifact drifted during the formal window: {name}")


def _run_capture(
    command: list[str],
    cwd: Path,
    timeout: float | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    started_ns = time.monotonic_ns()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        finished_ns = time.monotonic_ns()
        return {
            "command": command,
            "started_monotonic_ns": started_ns,
            "finished_monotonic_ns": finished_ns,
            "wall_ns": finished_ns - started_ns,
            "exit_status": process.returncode,
            "stdout": stdout.decode("utf-8", "replace"),
            "stderr": stderr.decode("utf-8", "replace"),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as error:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        finished_ns = time.monotonic_ns()
        return {
            "command": command,
            "started_monotonic_ns": started_ns,
            "finished_monotonic_ns": finished_ns,
            "wall_ns": finished_ns - started_ns,
            "exit_status": None,
            "stdout": (stdout or error.stdout or b"").decode("utf-8", "replace"),
            "stderr": (stderr or error.stderr or b"").decode("utf-8", "replace"),
            "timed_out": True,
            "process_group_killed": True,
        }
    except KeyboardInterrupt as error:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        finished_ns = time.monotonic_ns()
        raise CellProcessInterrupted(
            {
                "command": command,
                "started_monotonic_ns": started_ns,
                "finished_monotonic_ns": finished_ns,
                "wall_ns": finished_ns - started_ns,
                "exit_status": None,
                "stdout": stdout.decode("utf-8", "replace"),
                "stderr": stderr.decode("utf-8", "replace"),
                "timed_out": False,
                "interrupted": True,
                "process_group_killed": True,
            }
        ) from error


def _normalized_plan_identity(result: dict[str, Any]) -> dict[str, Any]:
    value = dict(result)
    value.pop("plan_fingerprint", None)
    return value


def _without_trace(result: dict[str, Any]) -> dict[str, Any]:
    value = dict(result)
    value.pop("trace", None)
    return value


def _first_divergence(expected: Any, actual: Any, *, accepted_reference: bool = False) -> Any:
    sys.path.insert(0, str(ROOT / "src"))
    from sim_engine_compiler.reference.conformance import first_divergence

    if accepted_reference:
        return first_divergence(
            expected, actual, float_rel_tol=2e-15, float_abs_tol=1e-12
        )
    return first_divergence(expected, actual)


def _jsonable_divergence(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else value


def _run_runtime_gate(
    runtime: Path,
    plan: Path,
    output: Path,
    seeds: list[int],
    workers: int,
    observation: str,
) -> dict[str, Any]:
    command = [
        str(runtime),
        str(plan),
        str(output),
        "--seeds",
        ",".join(map(str, seeds)),
        "--worker-threads",
        str(workers),
        "--observation-level",
        observation,
    ]
    result = _run_capture(command, ROOT)
    atomic_json(output.with_name(f"{output.stem}-command.json"), result)
    if result["exit_status"] != 0 or not output.is_file():
        raise RuntimeError(f"runtime semantic gate failed: {result}")
    result["output"] = {
        "path": output.name,
        "sha256": sha256_file(output),
        "bytes": output.stat().st_size,
    }
    return result


def _semantic_gate_impl(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.resolve()
    manifest = load_frozen(run_dir)
    gate_dir = run_dir / "semantic-gate"
    gate_dir.mkdir(exist_ok=False)
    runtime = Path(manifest["artifacts"]["runtime"]["path"])
    event_plan = Path(manifest["timed_plan"]["path"])
    legacy_plan = Path(manifest["reference_plan"]["path"])
    commands: list[dict[str, Any]] = []
    rust_paths: dict[str, Path] = {}

    specifications = [
        ("legacy-full-required", legacy_plan, [0, 1, 7], 1, "full"),
        ("event-full-required", event_plan, [0, 1, 7], 1, "full"),
        ("event-summary-required", event_plan, [0, 1, 7], 1, "summary"),
    ]
    for observation in OBSERVATIONS:
        for workers in (1, 8):
            specifications.append(
                (f"event-{observation}-duplicate-w{workers}", event_plan, [7, 0, 7, 1], workers, observation)
            )
    for name, plan, seeds, workers, observation in specifications:
        output = gate_dir / f"rust-{name}.json"
        commands.append(_run_runtime_gate(runtime, plan, output, seeds, workers, observation))
        rust_paths[name] = output

    binding_report = gate_dir / "pyo3-gate.json"
    binding_command = [
        str(Path(manifest["artifacts"]["python"]["path"])),
        str(WORKER),
        "semantic-gate",
        "--plan",
        str(event_plan),
        "--reference-plan",
        str(legacy_plan),
        "--report",
        str(binding_report),
    ]
    binding_execution = _run_capture(binding_command, ROOT)
    commands.append(binding_execution)
    atomic_json(gate_dir / "pyo3-command.json", binding_execution)
    if binding_execution["exit_status"] != 0 or not binding_report.is_file():
        raise RuntimeError(f"PyO3 semantic gate failed: {binding_execution}")
    pyo3_gate = json.loads(binding_report.read_text(encoding="utf-8"))
    pyo3_raw = json.loads(binding_report.with_name("pyo3-gate-raw.json").read_text(encoding="utf-8"))

    rust = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in rust_paths.items()}
    checks: list[dict[str, Any]] = []

    def compare(
        name: str, expected: Any, actual: Any, *, accepted_reference: bool = False
    ) -> None:
        exact = _first_divergence(expected, actual)
        accepted = (
            _first_divergence(expected, actual, accepted_reference=True)
            if accepted_reference and exact is not None
            else exact
        )
        checks.append(
            {
                "name": name,
                "passed": accepted is None,
                "first_exact_divergence": _jsonable_divergence(exact),
                "first_accepted_divergence": _jsonable_divergence(accepted),
                "comparison_policy": (
                    "tests/differential/test_rust_runtime.py: accepted F35 cross-backend float policy"
                    if accepted_reference
                    else "exact after only the named normalization"
                ),
            }
        )

    compare("pyo3_internal_gate", True, pyo3_gate.get("passed"))
    compare(
        "rust_legacy_vs_python_reference",
        pyo3_raw["reference_results"],
        [row["result"] for row in rust["legacy-full-required"]["samples"]],
        accepted_reference=True,
    )
    for backend, legacy, event in (
        ("rust", rust["legacy-full-required"], rust["event-full-required"]),
        ("pyo3", pyo3_raw["legacy_full"], pyo3_raw["event_full"]),
    ):
        compare(
            f"{backend}_legacy_vs_event_except_plan_fingerprint",
            [_normalized_plan_identity(row["result"]) for row in legacy["samples"]],
            [_normalized_plan_identity(row["result"]) for row in event["samples"]],
        )
    for backend, full, summary in (
        ("rust", rust["event-full-required"], rust["event-summary-required"]),
        ("pyo3", pyo3_raw["event_full"], pyo3_raw["event_summary"]),
    ):
        compare(f"{backend}_summary_trace_empty", [[], [], []], [row["result"].get("trace") for row in summary["samples"]])
        compare(
            f"{backend}_full_summary_non_trace",
            [_without_trace(row["result"]) for row in full["samples"]],
            [_without_trace(row["result"]) for row in summary["samples"]],
        )
    for observation in OBSERVATIONS:
        rust_one = rust[f"event-{observation}-duplicate-w1"]
        rust_eight = rust[f"event-{observation}-duplicate-w8"]
        compare(f"rust_{observation}_duplicate_worker_invariant", rust_one["samples"], rust_eight["samples"])
        compare(f"rust_{observation}_duplicate_seed_equal", rust_one["samples"][0]["result"], rust_one["samples"][2]["result"])
        pyo3_one = pyo3_raw["duplicate_runs"][f"{observation}-w1"]
        pyo3_eight = pyo3_raw["duplicate_runs"][f"{observation}-w8"]
        compare(f"pyo3_{observation}_duplicate_worker_invariant", pyo3_one["samples"], pyo3_eight["samples"])
        compare(f"pyo3_{observation}_duplicate_seed_equal", pyo3_one["samples"][0]["result"], pyo3_one["samples"][2]["result"])
        compare(f"rust_pyo3_{observation}_duplicate_w1", rust_one["samples"], pyo3_one["samples"])
    compare(
        "rust_duplicate_full_summary_non_trace",
        [_without_trace(row["result"]) for row in rust["event-full-duplicate-w1"]["samples"]],
        [_without_trace(row["result"]) for row in rust["event-summary-duplicate-w1"]["samples"]],
    )
    compare("rust_pyo3_event_full", rust["event-full-required"]["samples"], pyo3_raw["event_full"]["samples"])
    compare("rust_pyo3_event_summary", rust["event-summary-required"]["samples"], pyo3_raw["event_summary"]["samples"])

    passed = all(check["passed"] for check in checks)
    report = {
        "schema_version": "cpu-batch-semantic-gate/v1",
        "passed": passed,
        "manifest_sha256": sha256_file(run_dir / "manifest.json"),
        "commands": commands,
        "checks": checks,
        "candidate_dispatch": {
            "rust_commands_include_flag": any("--dependency-dispatch" in command["command"] for command in commands),
            "pyo3": "unavailable through public run_batch",
        },
        "raw_result_files": {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in gate_dir.glob("*.json")
        },
    }
    if report["candidate_dispatch"]["rust_commands_include_flag"]:
        report["passed"] = False
    atomic_json(gate_dir / "report.json", report)
    atomic_write(
        gate_dir / "report.sha256",
        (sha256_file(gate_dir / "report.json") + "\n").encode("ascii"),
    )
    if not report["passed"]:
        raise RuntimeError("semantic admission gate failed")
    print(gate_dir / "report.json")
    return report


def semantic_gate(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.resolve()
    try:
        return _semantic_gate_impl(args)
    except Exception as error:
        gate_dir = run_dir / "semantic-gate"
        if gate_dir.is_dir() and not (gate_dir / "report.json").is_file():
            raw_files = {
                path.name: {
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
                for path in gate_dir.glob("*.json")
            }
            failure_report = {
                "schema_version": "cpu-batch-semantic-gate/v1",
                "passed": False,
                "manifest_sha256": (
                    sha256_file(run_dir / "manifest.json")
                    if (run_dir / "manifest.json").is_file()
                    else None
                ),
                "commands": [
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in sorted(gate_dir.glob("*-command.json"))
                ],
                "checks": [
                    {
                        "name": "semantic_gate_execution",
                        "passed": False,
                        "first_exact_divergence": None,
                        "failure": {
                            "type": type(error).__name__,
                            "message": str(error),
                        },
                    }
                ],
                "candidate_dispatch": {
                    "rust_commands_include_flag": False,
                    "pyo3": "unavailable through public run_batch",
                },
                "raw_result_files": raw_files,
            }
            atomic_json(gate_dir / "report.json", failure_report)
            atomic_write(
                gate_dir / "report.sha256",
                (sha256_file(gate_dir / "report.json") + "\n").encode("ascii"),
            )
        raise


def validate_gate_evidence(
    run_dir: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    gate_dir = run_dir / "semantic-gate"
    report_path = gate_dir / "report.json"
    seal_path = gate_dir / "report.sha256"
    if not report_path.is_file() or not seal_path.is_file():
        raise RuntimeError("sealed semantic gate evidence is required")
    if sha256_file(report_path) != seal_path.read_text(encoding="ascii").strip():
        raise RuntimeError("semantic gate report seal mismatch")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema_version") != "cpu-batch-semantic-gate/v1":
        raise RuntimeError("unsupported semantic gate schema")
    if report.get("manifest_sha256") != sha256_file(run_dir / "manifest.json"):
        raise RuntimeError("semantic gate is bound to a different frozen manifest")
    dispatch = report.get("candidate_dispatch", {})
    if (
        dispatch.get("rust_commands_include_flag") is not False
        or dispatch.get("pyo3") != "unavailable through public run_batch"
    ):
        raise RuntimeError("semantic gate did not prove candidate dispatch disabled")
    if not report.get("passed") or not report.get("checks") or not all(
        check.get("passed") is True for check in report["checks"]
    ):
        raise RuntimeError("semantic gate checks are not all passed")
    expected_files = report.get("raw_result_files")
    if not isinstance(expected_files, dict) or not expected_files:
        raise RuntimeError("semantic gate raw result manifest is missing")
    actual_files = {
        path.name
        for path in gate_dir.glob("*.json")
        if path.name != report_path.name
    }
    if actual_files != set(expected_files):
        raise RuntimeError("semantic gate raw result file set drift")
    for name, identity in expected_files.items():
        path = gate_dir / name
        if (
            sha256_file(path) != identity.get("sha256")
            or path.stat().st_size != identity.get("bytes")
        ):
            raise RuntimeError(f"semantic gate raw result drift: {name}")
    if manifest["timed_plan"]["sha256"] != sha256_file(
        Path(manifest["timed_plan"]["path"])
    ):
        raise RuntimeError("semantic gate timed Plan binding drift")
    return report


def parse_gnu_time(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {"maximum_resident_set_kbytes": None, "elapsed_wall": None}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Maximum resident set size (kbytes):"):
            values["maximum_resident_set_kbytes"] = int(stripped.rsplit(":", 1)[1].strip())
        elif stripped.startswith("Elapsed (wall clock) time"):
            values["elapsed_wall"] = stripped.split(": ", 1)[-1]
    return values


def _cell_command(
    manifest: dict[str, Any], cell: dict[str, Any], seeds: list[int], report_path: Path
) -> list[str]:
    plan = manifest["timed_plan"]["path"]
    if cell["backend"] == "rust":
        inner = [
            manifest["artifacts"]["stage_c_benchmark"]["path"],
            plan,
            str(report_path),
            "--seeds",
            ",".join(map(str, seeds)),
            "--worker-threads",
            str(cell["worker_threads"]),
            "--warmups",
            "1",
            "--repeats",
            "1",
            "--observation-level",
            cell["observation_level"],
        ]
    else:
        inner = [
            manifest["artifacts"]["python"]["path"],
            str(WORKER),
            "cell",
            "--plan",
            plan,
            "--seeds",
            ",".join(map(str, seeds)),
            "--worker-threads",
            str(cell["worker_threads"]),
            "--observation-level",
            cell["observation_level"],
            "--report",
            str(report_path),
        ]
    return ["taskset", "-c", CPUSET, "/usr/bin/time", "-v", *inner]


def _verify_cell_report(
    cell: dict[str, Any],
    seeds: list[int],
    report: dict[str, Any],
    frozen_plan: dict[str, Any],
) -> dict[str, Any]:
    effective_workers = min(cell["worker_threads"], len(seeds))
    if cell["backend"] == "rust":
        expected_top = {
            "schema_version": "stage-c-segmented-benchmark/v1",
            "plan_path": frozen_plan["path"],
            "plan_bytes": frozen_plan["bytes"],
            "plan_fingerprint": frozen_plan["fingerprint"],
            "semantic_profile": frozen_plan["semantic_profile"],
            "work_policy": frozen_plan["work_policy"],
            "rng_profile": frozen_plan["rng_profile"],
            "seeds": seeds,
            "worker_threads": effective_workers,
            "warmups": 1,
            "repeats": 1,
            "until": None,
            "observation_level": cell["observation_level"],
            "dependency_dispatch": False,
        }
        drift = {
            key: {"expected": value, "actual": report.get(key)}
            for key, value in expected_top.items()
            if report.get(key) != value
        }
        if drift:
            raise AssertionError(f"Rust cell report identity drift: {drift}")
        if report.get("dependency_dispatch") is not False:
            raise AssertionError("Rust cell enabled candidate dispatch")
        if report.get("warmups") != 1 or report.get("repeats") != 1:
            raise AssertionError("Rust cell warmup/repeat count drift")
        if report.get("semantic_profile") != EXPECTED_PROFILE:
            raise AssertionError("Rust cell profile drift")
        if len(report.get("records", [])) != 1 or report["records"][0].get("repeat") != 0:
            raise AssertionError("Rust cell must contain exactly repeat zero")
        record = report["records"][0]
        indexes = record["sample_indexes"]
        actual_seeds = record["seeds"]
        digest = record["samples_sha256"]
        warm_ns = record["phases"]["batch_execution_ns"]
        warmup = {
            "completed": True,
            "proof_available": False,
            "reason": "stage-c-benchmark retains no warmup result digest; a failed warmup prevents the measured record",
        }
    else:
        expected_plan = {
            "path": frozen_plan["path"],
            "sha256": frozen_plan["sha256"],
            "bytes": frozen_plan["bytes"],
            "semantic_profile": frozen_plan["semantic_profile"],
            "work_policy": frozen_plan["work_policy"],
            "rng_profile": frozen_plan["rng_profile"],
            "duration_minutes": frozen_plan["duration_minutes"],
            "source_inputs_sha256": frozen_plan["source_inputs_sha256"],
            "resource_dispatch_index_present": False,
        }
        expected_envelope = {
            "plan_fingerprint": frozen_plan["fingerprint"],
            "sample_count": len(seeds),
            "worker_threads": effective_workers,
            "until": None,
        }
        if report.get("schema_version") != "cpu-batch-binding-cell/v1":
            raise AssertionError("unsupported PyO3 cell report schema")
        if report.get("plan") != expected_plan:
            raise AssertionError("PyO3 cell Plan identity drift")
        if report.get("result_envelope") != expected_envelope:
            raise AssertionError("PyO3 measured result envelope drift")
        if report.get("warmup_envelope") != expected_envelope:
            raise AssertionError("PyO3 warmup result envelope drift")
        if (
            report.get("worker_threads") != cell["worker_threads"]
            or report.get("effective_worker_threads") != effective_workers
            or report.get("sample_count") != len(seeds)
            or report.get("observation_level") != cell["observation_level"]
        ):
            raise AssertionError("PyO3 requested cell identity drift")
        if report.get("warmups") != 1 or report.get("measured_calls") != 1:
            raise AssertionError("PyO3 cell warmup/call count drift")
        indexes = report["proof"]["sample_indexes"]
        actual_seeds = report["proof"]["seeds"]
        digest = report["proof"]["samples_sha256"]
        warm_ns = report["call_ns"]
        if not report.get("warmup_completed") or not report.get("warmup_matches_measured"):
            raise AssertionError("PyO3 warmup proof failed")
        warmup = {
            "completed": True,
            "proof_available": True,
            "proof": report["warmup_proof"],
            "matches_measured": True,
        }
    if indexes != list(range(len(seeds))) or actual_seeds != seeds:
        raise AssertionError("cell sample identity/order drift")
    return {"samples_sha256": digest, "warm_batch_ns": warm_ns, "warmup": warmup}


def measure(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.resolve()
    manifest = load_frozen(run_dir)
    validate_gate_evidence(run_dir, manifest)
    current_placement = validate_placement()
    if current_placement != manifest["placement"]:
        raise RuntimeError("CPU placement changed after freeze")
    frozen_deadline = float(manifest["admission_policy"]["window_deadline_seconds"])
    if args.deadline_seconds != frozen_deadline:
        raise RuntimeError("measurement deadline differs from the frozen admission policy")
    cell_time_budget = float(
        manifest["admission_policy"]["cell_time_budget_seconds"]
    )
    measure_dir = run_dir / "measurement"
    measure_dir.mkdir(exist_ok=False)
    cells = json.loads((run_dir / manifest["schedule"]["measurement_list_path"]).read_text(encoding="utf-8"))
    seeds_n64 = json.loads((run_dir / manifest["schedule"]["seeds_path"]).read_text(encoding="utf-8"))
    state: dict[str, Any] = {
        "schema_version": "cpu-batch-measurement-state/v1",
        "status": "initializing",
        "started_monotonic_ns": 0,
        "deadline_seconds": args.deadline_seconds,
        "deadline_monotonic_ns": 0,
        "cell_time_budget_seconds": cell_time_budget,
        "postflight_budget_seconds": POSTFLIGHT_BUDGET_SECONDS,
        "cells_total": len(cells),
        "cells_completed": 0,
        "stop_reason": None,
    }
    content_digests: dict[tuple[str, str, int], str] = {}
    received_signal: list[int | None] = [None]
    previous_handlers = {
        signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
    }

    def interrupt_handler(signum: int, _frame: Any) -> None:
        received_signal[0] = signum
        raise KeyboardInterrupt(f"received signal {signum}")

    for signum in previous_handlers:
        signal.signal(signum, interrupt_handler)
    started = 0.0
    deadline = float("inf")
    try:
        started = time.monotonic()
        deadline = started + args.deadline_seconds
        state.update(
            {
                "status": "running",
                "started_monotonic_ns": time.monotonic_ns(),
                "deadline_monotonic_ns": int(deadline * 1e9),
            }
        )
        atomic_json(measure_dir / "state.json", state)
        state["machine_before"] = machine_snapshot(
            deadline_monotonic=deadline - POSTFLIGHT_BUDGET_SECONDS
        )
        atomic_json(measure_dir / "state.json", state)
        for cell in cells:
            remaining = deadline - time.monotonic()
            if remaining < cell_time_budget + POSTFLIGHT_BUDGET_SECONDS:
                state["status"] = "incomplete"
                state["stop_reason"] = (
                    "remaining_window_below_frozen_cell_plus_postflight_budget"
                )
                break
            ordinal = cell["ordinal"]
            cell_dir = measure_dir / f"cell-{ordinal:02d}"
            cell_dir.mkdir(exist_ok=False)
            seeds = seeds_n64[: cell["sample_count"]]
            raw_report = cell_dir / "raw-report.json"
            command = _cell_command(manifest, cell, seeds, raw_report)
            try:
                validate_execution_artifacts(manifest)
            except Exception as error:  # noqa: BLE001 - identity drift closes the window
                for stream in ("stdout.txt", "stderr.txt"):
                    atomic_write(cell_dir / stream, b"")
                record = {
                    "schema_version": "cpu-batch-cell-record/v1",
                    "cell": cell,
                    "command": command,
                    "status": "failed",
                    "failure": {
                        "type": type(error).__name__,
                        "message": str(error),
                    },
                    "captured_output": {
                        stream: {
                            "path": f"{stream}.txt",
                            "sha256": sha256_file(cell_dir / f"{stream}.txt"),
                            "bytes": 0,
                        }
                        for stream in ("stdout", "stderr")
                    },
                }
                atomic_json(cell_dir / "record.json", record)
                state["status"] = "incomplete"
                state["stop_reason"] = f"execution_identity_drift:{ordinal}"
                break
            environment = dict(os.environ)
            environment["RUSTUP_TOOLCHAIN"] = PINNED_TOOLCHAIN
            environment["LC_ALL"] = "C"
            interrupted = False
            try:
                execution = _run_capture(
                    command,
                    ROOT,
                    timeout=min(remaining, cell_time_budget),
                    environment=environment,
                )
            except CellProcessInterrupted as error:
                execution = error.execution
                interrupted = True
            atomic_write(cell_dir / "stdout.txt", execution["stdout"].encode("utf-8"))
            atomic_write(cell_dir / "stderr.txt", execution["stderr"].encode("utf-8"))
            record: dict[str, Any] = {
                "schema_version": "cpu-batch-cell-record/v1",
                "cell": cell,
                "command": command,
                "environment": {
                    "RUSTUP_TOOLCHAIN": PINNED_TOOLCHAIN,
                    "LC_ALL": "C",
                    "taskset": CPUSET,
                },
                "execution": execution,
                "gnu_time": parse_gnu_time(execution["stderr"]),
                "captured_output": {
                    "stdout": {
                        "path": "stdout.txt",
                        "sha256": sha256_file(cell_dir / "stdout.txt"),
                        "bytes": (cell_dir / "stdout.txt").stat().st_size,
                    },
                    "stderr": {
                        "path": "stderr.txt",
                        "sha256": sha256_file(cell_dir / "stderr.txt"),
                        "bytes": (cell_dir / "stderr.txt").stat().st_size,
                    },
                },
            }
            if interrupted:
                record["status"] = "failed"
                record["failure"] = {
                    "type": "coordinator_interrupt",
                    "signal": received_signal[0],
                    "message": "owned child process group killed and reaped",
                }
                atomic_json(cell_dir / "record.json", record)
                state["status"] = "incomplete"
                state["stop_reason"] = f"coordinator_interrupt:{received_signal[0]}"
                break
            if execution["timed_out"] or execution["exit_status"] != 0 or not raw_report.is_file():
                record["status"] = "timeout" if execution["timed_out"] else "failed"
                atomic_json(cell_dir / "record.json", record)
                state["status"] = "incomplete"
                state["stop_reason"] = f"cell_{record['status']}:{ordinal}"
                break
            try:
                raw = json.loads(raw_report.read_text(encoding="utf-8"))
                validate_execution_artifacts(manifest)
                proof = _verify_cell_report(cell, seeds, raw, manifest["timed_plan"])
                key = (
                    cell["backend"],
                    cell["observation_level"],
                    cell["sample_count"],
                )
                previous = content_digests.setdefault(
                    key, proof["samples_sha256"]
                )
                if previous != proof["samples_sha256"]:
                    raise AssertionError(
                        "sample content changed across worker/repeat envelope"
                    )
            except Exception as error:  # noqa: BLE001 - malformed cell evidence must fail closed
                record["status"] = "failed"
                record["failure"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
                if raw_report.is_file():
                    record["raw_report"] = {
                        "path": raw_report.name,
                        "sha256": sha256_file(raw_report),
                        "bytes": raw_report.stat().st_size,
                    }
                atomic_json(cell_dir / "record.json", record)
                state["status"] = "incomplete"
                state["stop_reason"] = f"cell_evidence_invalid:{ordinal}"
                break
            record.update(
                {
                    "status": "completed",
                    "proof": proof,
                    "raw_report": {
                        "path": raw_report.name,
                        "sha256": sha256_file(raw_report),
                        "bytes": raw_report.stat().st_size,
                    },
                }
            )
            atomic_json(cell_dir / "record.json", record)
            state["cells_completed"] += 1
            atomic_json(measure_dir / "state.json", state)
        else:
            state["status"] = "completed"
            state["stop_reason"] = "all_preregistered_cells_completed"
    except Exception as error:
        state["status"] = "incomplete"
        state["stop_reason"] = f"fail_closed:{type(error).__name__}:{error}"
        raise
    except KeyboardInterrupt:
        state["status"] = "incomplete"
        state["stop_reason"] = f"coordinator_interrupt:{received_signal[0]}"
    finally:
        recorded_ordinals = {
            json.loads(path.read_text(encoding="utf-8"))["cell"]["ordinal"]
            for path in measure_dir.glob("cell-*/record.json")
        }
        state["incomplete_ordinals"] = [
            cell["ordinal"]
            for cell in cells
            if cell["ordinal"] not in recorded_ordinals
        ]
        try:
            state["machine_after"] = machine_snapshot(
                deadline_monotonic=deadline - 1.0
            )
        except KeyboardInterrupt:
            state["status"] = "incomplete"
            state["stop_reason"] = f"coordinator_interrupt:{received_signal[0]}"
            state["machine_after"] = {
                "incomplete": True,
                "reason": "coordinator interrupt during postflight monitoring",
            }
        state["finished_monotonic_ns"] = time.monotonic_ns()
        state["elapsed_ns"] = (
            state["finished_monotonic_ns"] - state["started_monotonic_ns"]
        )
        if (
            state["deadline_monotonic_ns"]
            and state["finished_monotonic_ns"] > state["deadline_monotonic_ns"]
        ):
            state["status"] = "incomplete"
            state["stop_reason"] = "window_deadline_exceeded_during_postflight"
        try:
            atomic_json(measure_dir / "state.json", state)
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
    print(measure_dir / "state.json")
    return state


def _distribution(values: Iterable[float]) -> dict[str, float] | None:
    materialized = list(values)
    if not materialized:
        return None
    median = statistics.median(materialized)
    return {
        "median": median,
        "minimum": min(materialized),
        "maximum": max(materialized),
        "median_absolute_deviation": statistics.median(abs(value - median) for value in materialized),
    }


def validate_measurement_records(
    run_dir: Path, manifest: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    measure_dir = run_dir / "measurement"
    state = json.loads((measure_dir / "state.json").read_text(encoding="utf-8"))
    schedule = json.loads(
        (run_dir / manifest["schedule"]["measurement_list_path"]).read_text(
            encoding="utf-8"
        )
    )
    seeds_n64 = json.loads(
        (run_dir / manifest["schedule"]["seeds_path"]).read_text(encoding="utf-8")
    )
    expected_by_ordinal = {cell["ordinal"]: cell for cell in schedule}
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    content_digests: dict[tuple[str, str, int], str] = {}
    for directory in sorted(measure_dir.glob("cell-*")):
        if not directory.is_dir() or not re.fullmatch(r"cell-\d{2}", directory.name):
            raise RuntimeError(f"unexpected measurement entry: {directory.name}")
        record_path = directory / "record.json"
        if not record_path.is_file():
            raise RuntimeError(f"measurement cell has no record: {directory.name}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        cell = record.get("cell", {})
        ordinal = cell.get("ordinal")
        if (
            not isinstance(ordinal, int)
            or ordinal in seen
            or directory.name != f"cell-{ordinal:02d}"
            or expected_by_ordinal.get(ordinal) != cell
        ):
            raise RuntimeError(f"measurement cell identity drift: {directory.name}")
        seen.add(ordinal)
        if record.get("status") not in {"completed", "failed", "timeout"}:
            raise RuntimeError(f"invalid measurement cell status: {directory.name}")
        captured = record.get("captured_output", {})
        for stream in ("stdout", "stderr"):
            identity = captured.get(stream, {})
            path = directory / identity.get("path", "")
            if (
                not path.is_file()
                or path.parent != directory
                or sha256_file(path) != identity.get("sha256")
                or path.stat().st_size != identity.get("bytes")
            ):
                raise RuntimeError(
                    f"measurement {stream} evidence drift: {directory.name}"
                )
        if record["status"] == "completed":
            raw_identity = record.get("raw_report", {})
            raw_path = directory / raw_identity.get("path", "")
            if (
                not raw_path.is_file()
                or raw_path.parent != directory
                or sha256_file(raw_path) != raw_identity.get("sha256")
                or raw_path.stat().st_size != raw_identity.get("bytes")
            ):
                raise RuntimeError(f"measurement raw report drift: {directory.name}")
            seeds = seeds_n64[: cell["sample_count"]]
            expected_command = _cell_command(manifest, cell, seeds, raw_path)
            if record.get("command") != expected_command:
                raise RuntimeError(f"measurement command drift: {directory.name}")
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            proof = _verify_cell_report(cell, seeds, raw, manifest["timed_plan"])
            if proof != record.get("proof"):
                raise RuntimeError(f"measurement proof drift: {directory.name}")
            key = (
                cell["backend"],
                cell["observation_level"],
                cell["sample_count"],
            )
            previous = content_digests.setdefault(key, proof["samples_sha256"])
            if previous != proof["samples_sha256"]:
                raise RuntimeError(
                    f"measurement content changed across envelopes: {directory.name}"
                )
        records.append(record)
    completed = sum(record["status"] == "completed" for record in records)
    if state.get("cells_completed") != completed:
        raise RuntimeError("measurement state completed count drift")
    if state.get("status") == "completed" and (
        seen != set(expected_by_ordinal)
        or any(record["status"] != "completed" for record in records)
    ):
        raise RuntimeError("completed measurement state lacks the exact 56-cell evidence set")
    return state, records


def summarize(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.resolve()
    manifest = load_frozen(run_dir)
    measure_dir = run_dir / "measurement"
    state, records = validate_measurement_records(run_dir, manifest)
    completed = [record for record in records if record.get("status") == "completed"]
    failed = [record for record in records if record.get("status") != "completed"]
    primary = [record for record in completed if record["cell"]["kind"] == "primary"]
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in primary:
        cell = record["cell"]
        grouped[(cell["backend"], cell["observation_level"], cell["worker_threads"])].append(record)
    rows: list[dict[str, Any]] = []
    for (backend, observation, workers), values in sorted(grouped.items()):
        warm = [record["proof"]["warm_batch_ns"] for record in values]
        throughputs = [64 * 1e9 / value for value in warm]
        stage_values: dict[str, list[float]] = defaultdict(list)
        for record in values:
            ordinal = record["cell"]["ordinal"]
            raw_path = measure_dir / f"cell-{ordinal:02d}" / record["raw_report"]["path"]
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            stages = (
                raw["records"][0]["phases"]
                if backend == "rust"
                else raw["stages"]
            )
            for name, value in stages.items():
                if value is not None:
                    stage_values[name].append(value)
        speedups: list[float] = []
        efficiencies: list[float] = []
        for record in values:
            repeat = record["cell"]["repeat"]
            baseline = next(
                (
                    item
                    for item in primary
                    if item["cell"]["backend"] == backend
                    and item["cell"]["observation_level"] == observation
                    and item["cell"]["worker_threads"] == 1
                    and item["cell"]["repeat"] == repeat
                ),
                None,
            )
            if baseline is not None:
                speedup = baseline["proof"]["warm_batch_ns"] / record["proof"]["warm_batch_ns"]
                speedups.append(speedup)
                efficiencies.append(speedup / workers)
        rows.append(
            {
                "backend": backend,
                "observation_level": observation,
                "worker_threads": workers,
                "repeat_count": len(values),
                "warm_batch_ns": _distribution(warm),
                "samples_per_second": _distribution(throughputs),
                "paired_speedup_vs_same_repeat_worker_1": _distribution(speedups) if speedups else None,
                "paired_efficiency": _distribution(efficiencies) if efficiencies else None,
                "stage_ns": {
                    name: _distribution(samples)
                    for name, samples in sorted(stage_values.items())
                },
                "cold_process_wall_ns": _distribution(
                    record["execution"]["wall_ns"]
                    for record in values
                    if "execution" in record
                ),
                "rss_kbytes": _distribution(
                    record["gnu_time"]["maximum_resident_set_kbytes"]
                    for record in values
                    if record["gnu_time"]["maximum_resident_set_kbytes"] is not None
                ),
            }
        )
    summary = {
        "schema_version": "cpu-batch-summary/v1",
        "measurement_status": state["status"],
        "complete_issue6_baseline": state["status"] == "completed" and len(completed) == 56,
        "cells_completed": len(completed),
        "completed_ordinals": [record["cell"]["ordinal"] for record in completed],
        "cells_failed": len(failed),
        "failed_ordinals": [record["cell"]["ordinal"] for record in failed],
        "cells_missing": 56 - len(completed) - len(failed),
        "cells_total": 56,
        "primary": rows,
        "startup_probes": [record for record in completed if record["cell"]["kind"] == "startup_probe"],
        "limitations": [
            "startup probes are excluded from scaling claims",
            "Rust and PyO3 timing boundaries differ; no cross-backend speedup is computed",
            "PyO3 internal stages are bundled and no stage is inferred by subtraction",
            "whole-process RSS is a high-water mark, not incremental batch allocation",
            "PyO3 whole-process RSS includes imports, warmup and measured result trees, proof construction, wrapper encoding and evidence writing",
            "Rust and PyO3 RSS values have different resident work and must not form an incremental-memory ratio",
        ],
        "manifest_sha256": sha256_file(run_dir / "manifest.json"),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(run_dir / "summary.json")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--output-root", type=Path, required=True)
    freeze_parser.add_argument("--plan", type=Path, required=True, help="precompiled unindexed event-time-v2 Plan")
    freeze_parser.add_argument("--lineage", type=Path, required=True)
    freeze_parser.add_argument("--compiler-command", required=True)
    freeze_parser.add_argument("--install-provenance", required=True)
    freeze_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    freeze_parser.add_argument("--reference-plan", type=Path, default=DEFAULT_REFERENCE_PLAN)
    freeze_parser.add_argument("--stage-binary", type=Path, default=DEFAULT_STAGE_BINARY)
    freeze_parser.add_argument("--runtime-binary", type=Path, default=DEFAULT_RUNTIME_BINARY)
    freeze_parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    gate_parser = subparsers.add_parser("semantic-gate")
    gate_parser.add_argument("--run-dir", type=Path, required=True)
    measure_parser = subparsers.add_parser("measure")
    measure_parser.add_argument("--run-dir", type=Path, required=True)
    measure_parser.add_argument("--deadline-seconds", type=float, default=1200.0)
    summary_parser = subparsers.add_parser("summarize")
    summary_parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args)
    elif args.command == "semantic-gate":
        semantic_gate(args)
    elif args.command == "measure":
        if args.deadline_seconds <= 0 or args.deadline_seconds > 1200:
            parser.error("deadline-seconds must be in (0, 1200]")
        measure(args)
    else:
        summarize(args)


if __name__ == "__main__":
    main()
