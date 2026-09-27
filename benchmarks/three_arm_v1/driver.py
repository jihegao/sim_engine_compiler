#!/usr/bin/env python3
"""Fail-closed preparation and once-only runner for the Rust three-arm pilot.

The runner uses the existing ``stage-c-benchmark`` executable for every arm.
It changes only the plan selected for the process and the explicit
``--dependency-dispatch`` flag:

* scan: scan plan, no flag
* cache: indexed plan, no flag
* candidates: indexed plan, ``--dependency-dispatch``

No compilation, reference execution, or profiling happens in the formal
window.  Preparation consumes an already-passed semantic gate and a plan map.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ARMS = ("scan", "cache", "candidates")
ARM_ROTATIONS = (
    ARMS,
    ("cache", "candidates", "scan"),
    ("candidates", "scan", "cache"),
)
SEEDS = (0, 1, 7)
WORKER_THREADS = 1
WARMUPS = 1
REPEATS = 3
CELL_TIMEOUT_SECONDS = 30
POSTFLIGHT_RESERVE_SECONDS = 10
MINIMUM_CELL_START_SECONDS = CELL_TIMEOUT_SECONDS + POSTFLIGHT_RESERVE_SECONDS
WINDOW_DEADLINE_SECONDS = 1200
MAX_NORMALIZED_LOAD = 0.05
PLAN_MAP_SCHEMA = "three-arm-plan-map/v1"
GATE_SCHEMA = "three-arm-semantic-gate/v1"
MANIFEST_SCHEMA = "three-arm-formal-manifest/v1"
STATE_SCHEMA = "three-arm-formal-state/v1"
REPORT_SCHEMA = "stage-c-segmented-benchmark/v1"
RUST_TOOLCHAIN = "1.90.0"
HEAVY_PROCESS_NAMES = frozenset(
    {
        "cargo",
        "rustc",
        "pytest",
        "stage-c-benchmark",
        "sim-engine-runtime",
        "cmake",
        "ninja",
        "make",
        "cc1",
        "cc1plus",
        "clang",
        "clang++",
        "gcc",
        "g++",
    }
)
EXPECTED_HOST = "g-1503-amd128"
EXPECTED_CASE_IDS = (
    "j35",
    "synthetic-low-contention-n4",
    "synthetic-low-contention-n16",
    "synthetic-low-contention-n64",
    "synthetic-sparse-affected-n4",
    "synthetic-sparse-affected-n16",
    "synthetic-sparse-affected-n64",
    "synthetic-dense-affected-n4",
    "synthetic-dense-affected-n16",
    "synthetic-dense-affected-n64",
    "j35-full",
)
J35_CANONICAL_SEMANTIC_SHA256 = "faf7c801351fd1cd3817fe3f03fe2b7e95056a7c1d9733e5863b291fddc2a689"
J35_UPSTREAM_COMMIT = "0e709bdcc2d692d9cfed49b9037c76ef71aefe33"
SHA256_HEX = frozenset("0123456789abcdef")


class AdmissionError(RuntimeError):
    """The formal window may not start or continue on this host."""


class CellFailure(RuntimeError):
    """A formal cell failed after preserving its evidence."""

    def __init__(self, reason: str, execution: dict[str, Any]):
        super().__init__(reason)
        self.reason = reason
        self.execution = execution


class CoordinatorInterrupted(RuntimeError):
    """SIGINT/SIGTERM closed the once-only window."""

    def __init__(self, signum: int):
        super().__init__(f"signal:{signum}")
        self.signum = signum


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= SHA256_HEX


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_canonical_json(value) + b"\n")
    temporary.replace(path)


def _require_file(path: Path, label: str, *, executable: bool = False) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} is not a file: {resolved}")
    if executable and not os.access(resolved, os.X_OK):
        raise ValueError(f"{label} is not executable: {resolved}")
    return resolved


def _resolve_from(base: Path, raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty path string")
    path = Path(raw).expanduser()
    return _require_file(path if path.is_absolute() else base / path, label)


def _plan_identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    value = _load_object(path, "Execution Plan")
    required = (
        "plan_version",
        "source_inputs_sha256",
        "semantic_profile",
        "work_policy",
        "rng_profile",
    )
    missing = [field for field in required if not isinstance(value.get(field), str)]
    if missing:
        raise ValueError(f"plan {path} lacks string fields: {', '.join(missing)}")
    return {
        "path": str(path),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "plan_version": value["plan_version"],
        "source_inputs_sha256": value["source_inputs_sha256"],
        "semantic_profile": value["semantic_profile"],
        "work_policy": value["work_policy"],
        "rng_profile": value["rng_profile"],
    }


def _validate_plan_pair(scan_path: Path, indexed_path: Path, case_id: str) -> None:
    scan = _load_object(scan_path, "scan Execution Plan")
    indexed = _load_object(indexed_path, "indexed Execution Plan")
    if "resource_dispatch_index" in scan:
        raise ValueError(f"scan Plan unexpectedly contains a dispatch index for {case_id}")
    index = indexed.pop("resource_dispatch_index", None)
    if not isinstance(index, dict) or index.get("schema_version") != "resource-dispatch-index/v2":
        raise ValueError(f"indexed Plan lacks resource-dispatch-index/v2 for {case_id}")
    if scan != indexed:
        raise ValueError(f"scan and indexed Plans differ outside the dispatch index for {case_id}")


def _require_exact_list(value: object, expected: tuple[int, ...], label: str) -> None:
    if value != list(expected):
        raise ValueError(f"{label} must be exactly {list(expected)}")


def _validate_gate_case(
    case_id: str,
    case: dict[str, Any],
    gate_case: object,
    scan: dict[str, Any],
    indexed: dict[str, Any],
    raw_files: dict[str, str],
) -> None:
    if not isinstance(gate_case, dict):
        raise ValueError(f"semantic gate lacks case {case_id!r}")
    input_sha256 = gate_case.get("input_sha256")
    if not _is_sha256(input_sha256):
        raise ValueError(f"semantic gate input hash is invalid for {case_id}")
    input_path = _require_file(Path(gate_case.get("input_path", "")), "canonical input")
    if str(input_path) not in raw_files:
        raise ValueError(f"canonical input is absent from raw evidence for {case_id}")
    canonical_input = _load_object(input_path, "canonical input")
    if sha256_bytes(_canonical_json(canonical_input)) != input_sha256:
        raise ValueError(f"canonical input digest mismatch for {case_id}")
    if case_id in {"j35", "j35-full"} and input_sha256 != J35_CANONICAL_SEMANTIC_SHA256:
        raise ValueError(f"J35 semantic input hash mismatch for {case_id}")
    if scan["source_inputs_sha256"] != input_sha256 or indexed["source_inputs_sha256"] != input_sha256:
        raise ValueError(f"Plan source input identity mismatch for {case_id}")
    if gate_case.get("semantic_profile") != case["semantic_profile"]:
        raise ValueError(f"semantic gate profile mismatch for {case_id}")
    if gate_case.get("observation_level") != case["observation_level"]:
        raise ValueError(f"semantic gate observation mismatch for {case_id}")
    _require_exact_list(gate_case.get("seeds"), SEEDS, f"gate seeds for {case_id}")
    if gate_case.get("untils") not in (None, [None]):
        raise ValueError(f"gate untils for {case_id} must be null or [null]")
    plans = gate_case.get("plans")
    if not isinstance(plans, dict):
        raise ValueError(f"semantic gate lacks plans for {case_id}")
    if plans.get("scan_sha256") != scan["sha256"]:
        raise ValueError(f"semantic gate scan hash mismatch for {case_id}")
    if plans.get("indexed_sha256") != indexed["sha256"]:
        raise ValueError(f"semantic gate indexed hash mismatch for {case_id}")
    fingerprint = plans.get("plan_fingerprint")
    if not _is_sha256(fingerprint):
        raise ValueError(f"semantic gate lacks plan_fingerprint for {case_id}")
    comparisons = gate_case.get("comparisons")
    if not isinstance(comparisons, dict) or comparisons.get("rust_three_arm_exact") is not True:
        raise ValueError(f"three-arm exact gate did not pass for {case_id}")
    threads = comparisons.get("threads")
    if not isinstance(threads, dict):
        raise ValueError(f"thread comparison is absent for {case_id}")
    if threads.get("counts") != [1, 3] or threads.get("duplicate_seed_order_exact") is not True:
        raise ValueError(f"thread invariance gate did not pass for {case_id}")
    reference = comparisons.get("reference")
    required_reference = {
        "trace_business_projection",
        "sample_requests",
        "metrics",
        "terminal_state",
    }
    if not isinstance(reference, dict) or set(reference) != required_reference:
        raise ValueError(f"reference comparison is incomplete for {case_id}")
    for field in required_reference - {"sample_requests"}:
        if reference[field] != {"passed": True, "exact": True}:
            raise ValueError(f"reference {field} policy did not pass exactly for {case_id}")
    if reference["sample_requests"] != {
        "passed": True,
        "exact": False,
        "float_fields": ["sample_requests[*].value_minutes"],
        "rel_tol": 2e-15,
        "abs_tol": 1e-12,
    }:
        raise ValueError(f"reference sample_requests tolerance policy is invalid for {case_id}")
    profile_validation = gate_case.get("profile_validation")
    if (
        not isinstance(profile_validation, dict)
        or profile_validation.get("workload_counters_validated") is not True
        or profile_validation.get("timing_fields_used_as_semantic_evidence") is not False
    ):
        raise ValueError(f"profile counter validation is invalid for {case_id}")
    profile_outputs = profile_validation.get("outputs")
    if not isinstance(profile_outputs, list) or len(profile_outputs) != 3:
        raise ValueError(f"profile counter evidence is incomplete for {case_id}")
    if {output.get("arm") for output in profile_outputs if isinstance(output, dict)} != set(ARMS):
        raise ValueError(f"profile arms are incomplete for {case_id}")
    for output in profile_outputs:
        if (
            not isinstance(output, dict)
            or output.get("level") != case["observation_level"]
            or output.get("seed") != 0
            or output.get("workload_fields_validated") is not True
            or output.get("timing_fields_semantic") is not False
            or output.get("passed") is not True
        ):
            raise ValueError(f"profile output validation failed for {case_id}")
        profile_path = _require_file(Path(output.get("profile_path", "")), "profile evidence")
        if str(profile_path) not in raw_files:
            raise ValueError(f"profile output is absent from raw evidence for {case_id}")
    result_hashes = gate_case.get("result_sha256_by_seed")
    if not isinstance(result_hashes, dict) or set(result_hashes) != {"0", "1", "7"}:
        raise ValueError(f"result hashes are incomplete for {case_id}")
    if any(not _is_sha256(value) for value in result_hashes.values()):
        raise ValueError(f"result hashes are invalid for {case_id}")


def _schedule(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for case in cases:
        for repeat, arms in enumerate(ARM_ROTATIONS):
            for arm in arms:
                cells.append(
                    {
                        "ordinal": len(cells),
                        "case_id": case["case_id"],
                        "repeat": repeat,
                        "arm": arm,
                        "observation_level": case["observation_level"],
                        "seeds": list(SEEDS),
                        "worker_threads": WORKER_THREADS,
                        "warmups": WARMUPS,
                        "measured_repeats": 1,
                    }
                )
    return cells


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(f"run directory must be absent or empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    gate_path = _require_file(args.semantic_gate, "semantic gate")
    map_path = _require_file(args.plan_map, "plan map")
    binary = _require_file(args.stage_binary, "stage-c-benchmark", executable=True)
    gnu_time = _require_file(args.gnu_time, "GNU time", executable=True)
    taskset = _require_file(args.taskset, "taskset", executable=True)
    gate = _load_object(gate_path, "semantic gate")
    plan_map = _load_object(map_path, "plan map")
    if args.cpuset != "0-7":
        raise ValueError("formal protocol requires cpuset 0-7")
    if (
        gate.get("schema_version") != GATE_SCHEMA
        or gate.get("status") != "passed"
        or gate.get("admissible") is not True
        or gate.get("input_case_count") != 10
        or gate.get("admission_case_count") != 11
    ):
        raise ValueError("semantic gate must be three-arm-semantic-gate/v1 with status passed")
    gate_artifacts = gate.get("artifacts")
    if not isinstance(gate_artifacts, dict):
        raise ValueError("semantic gate lacks artifact identities")
    runtime_path = _require_file(
        Path(gate_artifacts.get("sim_engine_runtime_path", "")),
        "semantic sim-engine-runtime",
        executable=True,
    )
    if sha256_file(runtime_path) != gate_artifacts.get("sim_engine_runtime_sha256"):
        raise ValueError("semantic sim-engine-runtime hash mismatch")
    raw_files = gate.get("raw_files")
    if not isinstance(raw_files, dict) or not raw_files:
        raise ValueError("semantic gate raw_files inventory must be non-empty")
    frozen_raw_files: dict[str, str] = {}
    for raw_path, digest in raw_files.items():
        if not isinstance(raw_path, str) or not _is_sha256(digest):
            raise ValueError("semantic gate raw_files entries must be path/hash strings")
        resolved = _require_file(Path(raw_path), "semantic raw evidence")
        if sha256_file(resolved) != digest:
            raise ValueError(f"semantic raw evidence hash mismatch: {resolved}")
        frozen_raw_files[str(resolved)] = digest
    required_evidence_names = {
        "PROTOCOL.md",
        "source-audit.json",
        "upstream-manifest.json",
        "artifacts.json",
        "regression-receipt.json",
        "plan-map.json",
        "stage-c-benchmark",
    }
    if not required_evidence_names.issubset({Path(path).name for path in frozen_raw_files}):
        raise ValueError("semantic raw evidence inventory is incomplete")
    for name in required_evidence_names:
        matching = {
            digest for path, digest in frozen_raw_files.items() if Path(path).name == name
        }
        if len(matching) != 1:
            raise ValueError(f"conflicting semantic evidence files named {name}")
    source_audit_path = next(
        Path(path) for path in frozen_raw_files if Path(path).name == "source-audit.json"
    )
    source_audit = _load_object(source_audit_path, "J35 source audit")
    if (
        source_audit.get("schema_version") != "three-arm-source-audit/v1"
        or source_audit.get("upstream", {}).get("head") != J35_UPSTREAM_COMMIT
        or source_audit.get("canonical_identity", {}).get("canonical_semantic_digest")
        != J35_CANONICAL_SEMANTIC_SHA256
        or source_audit.get("result", {}).get("j35_source_provenance_verified") is not True
        or source_audit.get("result", {}).get("canonical_export_byte_reproducible") is not True
    ):
        raise ValueError("J35 source audit did not prove the frozen provenance")
    receipt_path = next(
        Path(path) for path in frozen_raw_files if Path(path).name == "regression-receipt.json"
    )
    receipt = _load_object(receipt_path, "regression receipt")
    receipt_checks = receipt.get("checks")
    if (
        receipt.get("status") != "passed"
        or not isinstance(receipt_checks, list)
        or not receipt_checks
        or any(not isinstance(check, dict) or check.get("passed") is not True for check in receipt_checks)
        or not isinstance(receipt.get("raw_files"), dict)
        or not receipt["raw_files"]
    ):
        raise ValueError("regression/reuse/rejection receipt is incomplete")
    artifacts_path = next(
        Path(path) for path in frozen_raw_files if Path(path).name == "artifacts.json"
    )
    semantic_artifacts = _load_object(artifacts_path, "semantic artifact manifest")
    artifact_files = semantic_artifacts.get("files")
    if (
        semantic_artifacts.get("source_commit") != gate.get("source_commit")
        or not isinstance(semantic_artifacts.get("source_tree"), str)
        or len(semantic_artifacts["source_tree"]) != 40
        or not isinstance(artifact_files, dict)
        or not isinstance(semantic_artifacts.get("rustc"), str)
        or not semantic_artifacts["rustc"].startswith(f"rustc {RUST_TOOLCHAIN} ")
        or not isinstance(semantic_artifacts.get("cargo"), str)
        or not semantic_artifacts["cargo"].startswith(f"cargo {RUST_TOOLCHAIN} ")
    ):
        raise ValueError("semantic artifact manifest is incomplete")
    upstream_path = next(
        Path(path) for path in frozen_raw_files if Path(path).name == "upstream-manifest.json"
    )
    upstream = _load_object(upstream_path, "J35 upstream manifest")
    if (
        upstream.get("spare_mvp_commit") != J35_UPSTREAM_COMMIT
        or upstream.get("canonical_file_sha256")
        != "ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793"
        or upstream.get("adapter")
        != "src.spare_mvp_contract.adapter.SimulationAdapter.compile_scenario"
    ):
        raise ValueError("J35 upstream manifest is invalid")
    checks = gate.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(check, dict) or check.get("passed") is not True for check in checks
    ):
        raise ValueError("semantic gate checks must be non-empty and all passed")
    if len(checks) != 240:
        raise ValueError("semantic gate must contain exactly 240 per-case checks")
    for case_id in EXPECTED_CASE_IDS[:-1]:
        case_checks = [check for check in checks if check.get("case") == case_id]
        if len(case_checks) != 24:
            raise ValueError(f"semantic gate must contain exactly 24 checks for {case_id}")
        reference_seeds = {
            check.get("seed")
            for check in case_checks
            if check.get("check") == "reference-legacy"
        }
        arm_seed_pairs = {
            (check.get("arm"), check.get("seed"))
            for check in case_checks
            if check.get("check") == "three-arm/profile/observation"
        }
        batch_combinations = {
            (check.get("arm"), check.get("level"), check.get("threads"))
            for check in case_checks
            if check.get("check") == "batch-order-duplicate-thread"
        }
        if reference_seeds != set(SEEDS):
            raise ValueError(f"reference seed coverage is incomplete for {case_id}")
        if arm_seed_pairs != {(arm, seed) for arm in ARMS for seed in SEEDS}:
            raise ValueError(f"three-arm seed coverage is incomplete for {case_id}")
        if batch_combinations != {
            (arm, level, threads)
            for arm in ARMS
            for level in ("full", "summary")
            for threads in (1, 3)
        }:
            raise ValueError(f"observation/thread coverage is incomplete for {case_id}")
    profile_manifest = gate.get("profile_manifest")
    if not isinstance(profile_manifest, list) or len(profile_manifest) != 60:
        raise ValueError("semantic gate must contain exactly 60 profile records")
    expected_profile_keys = {
        (case_id, arm, level, 0)
        for case_id in EXPECTED_CASE_IDS[:-1]
        for arm in ARMS
        for level in ("full", "summary")
    }
    actual_profile_keys: set[tuple[str, str, str, int]] = set()
    expected_profile_fields = {
        "case",
        "input_sha256",
        "arm",
        "level",
        "seed",
        "profile_path",
        "workload_fields_validated",
        "timing_fields_semantic",
        "passed",
    }
    for record in profile_manifest:
        if not isinstance(record, dict) or set(record) != expected_profile_fields:
            raise ValueError("profile manifest record fields differ from the frozen schema")
        key = (record["case"], record["arm"], record["level"], record["seed"])
        actual_profile_keys.add(key)
        if (
            record["input_sha256"]
            != gate.get("cases", {}).get(record["case"], {}).get("input_sha256")
            or record["workload_fields_validated"] is not True
            or record["timing_fields_semantic"] is not False
            or record["passed"] is not True
        ):
            raise ValueError("profile manifest record did not pass the frozen policy")
        profile_path = _require_file(Path(record["profile_path"]), "profile manifest output")
        if str(profile_path) not in frozen_raw_files:
            raise ValueError("profile manifest output is absent from raw evidence")
    if actual_profile_keys != expected_profile_keys:
        raise ValueError("profile manifest combinations are incomplete or duplicated")
    if plan_map.get("schema_version") != PLAN_MAP_SCHEMA:
        raise ValueError(f"plan map schema must be {PLAN_MAP_SCHEMA}")
    raw_cases = plan_map.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 11:
        raise ValueError("formal plan map must contain exactly 11 ordered case groups")
    gate_cases = gate.get("cases")
    if not isinstance(gate_cases, dict):
        raise ValueError("semantic gate cases must be an object keyed by case id")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("each plan-map case must be an object")
        case_id = raw_case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate case id: {case_id!r}")
        seen.add(case_id)
        scan_path = _resolve_from(map_path.parent, raw_case.get("scan_plan"), "scan plan")
        indexed_path = _resolve_from(map_path.parent, raw_case.get("indexed_plan"), "indexed plan")
        _validate_plan_pair(scan_path, indexed_path, case_id)
        scan = _plan_identity(scan_path)
        indexed = _plan_identity(indexed_path)
        if scan["semantic_profile"] != indexed["semantic_profile"]:
            raise ValueError(f"plan profiles differ for {case_id}")
        observation = raw_case.get("observation_level", "summary")
        if observation not in ("summary", "full"):
            raise ValueError(f"unsupported observation level for {case_id}: {observation!r}")
        semantic_profile = raw_case.get("semantic_profile", "event-time-v2")
        if semantic_profile != "event-time-v2" or scan["semantic_profile"] != semantic_profile:
            raise ValueError(f"{case_id} must use event-time-v2")
        case = {
            "case_id": case_id,
            "semantic_profile": semantic_profile,
            "observation_level": observation,
            "scan_plan": scan,
            "indexed_plan": indexed,
            "plan_fingerprint": gate_cases.get(case_id, {})
            .get("plans", {})
            .get("plan_fingerprint"),
        }
        _validate_gate_case(
            case_id, case, gate_cases.get(case_id), scan, indexed, frozen_raw_files
        )
        cases.append(case)
    if [case["observation_level"] for case in cases].count("summary") != 10:
        raise ValueError("formal matrix requires exactly ten summary case groups")
    if [case["observation_level"] for case in cases].count("full") != 1:
        raise ValueError("formal matrix requires exactly one full case group")
    if set(gate_cases) != seen:
        raise ValueError("semantic gate and plan map must contain exactly the same case ids")
    if tuple(case["case_id"] for case in cases) != EXPECTED_CASE_IDS:
        raise ValueError("formal case ids or order differ from the preregistered matrix")
    input_hashes = [gate_cases[case_id]["input_sha256"] for case_id in EXPECTED_CASE_IDS]
    if input_hashes[0] != input_hashes[-1] or len(set(input_hashes[:-1])) != 10:
        raise ValueError("formal cases do not bind ten distinct canonical inputs")
    source_commit = _git_head()
    if gate.get("source_commit") != source_commit:
        raise ValueError("semantic gate source_commit differs from current HEAD")
    if _git_tracked_status():
        raise ValueError("tracked source must be clean before formal preparation")
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "prepared_at_unix_seconds": int(time.time()),
        "source_commit": source_commit,
        "semantic_gate": {
            "path": str(gate_path),
            "file_sha256": sha256_file(gate_path),
            "canonical_sha256": sha256_bytes(_canonical_json(gate)),
            "source_commit": gate.get("source_commit"),
            "runtime": {
                "path": str(runtime_path),
                "sha256": gate_artifacts["sim_engine_runtime_sha256"],
            },
            "raw_files": frozen_raw_files,
        },
        "plan_map": {"path": str(map_path), "sha256": sha256_file(map_path)},
        "artifacts": {
            "stage_c_benchmark": {"path": str(binary), "sha256": sha256_file(binary)},
            "gnu_time": {"path": str(gnu_time), "sha256": sha256_file(gnu_time)},
            "taskset": {"path": str(taskset), "sha256": sha256_file(taskset)},
        },
        "toolchain": _rust_toolchain_identity(),
        "cases": cases,
        "schedule": _schedule(cases),
        "protocol": {
            "seeds": list(SEEDS),
            "worker_threads": WORKER_THREADS,
            "warmups_per_process": WARMUPS,
            "repeats": REPEATS,
            "arm_rotations": [list(value) for value in ARM_ROTATIONS],
            "cpuset": args.cpuset,
            "cell_timeout_seconds": CELL_TIMEOUT_SECONDS,
            "postflight_reserve_seconds": POSTFLIGHT_RESERVE_SECONDS,
            "minimum_cell_start_seconds": MINIMUM_CELL_START_SECONDS,
            "window_deadline_seconds": WINDOW_DEADLINE_SECONDS,
            "max_normalized_load": MAX_NORMALIZED_LOAD,
            "timing_scope": (
                "stage-c phase timings include plan read/parse/fingerprint, RunState "
                "initialization, prepared batch execution, serialization, write, and end-to-end"
            ),
            "rss_scope": "GNU time -v high-water RSS for one fresh pinned stage-c process",
            "profile_diagnostics": "excluded from formal measured processes",
        },
    }
    if frozen_raw_files.get(str(binary)) != manifest["artifacts"]["stage_c_benchmark"]["sha256"]:
        raise ValueError("timed stage-c-benchmark is not bound by semantic admission")
    if artifact_files.get(str(binary)) != manifest["artifacts"]["stage_c_benchmark"]["sha256"]:
        raise ValueError("timed stage-c-benchmark is absent from the build artifact manifest")
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    (run_dir / "manifest.sha256").write_text(
        sha256_file(manifest_path) + "\n", encoding="ascii"
    )
    return manifest


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _git_tracked_status() -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _rust_toolchain_identity() -> dict[str, str]:
    values: dict[str, str] = {"rustup_toolchain": RUST_TOOLCHAIN}
    for label, command in (
        ("rustc_vv", ["rustc", f"+{RUST_TOOLCHAIN}", "-Vv"]),
        ("cargo_version", ["cargo", f"+{RUST_TOOLCHAIN}", "-V"]),
    ):
        completed = subprocess.run(
            command, cwd=ROOT, check=True, capture_output=True, text=True
        )
        values[label] = completed.stdout.strip()
    if not values["rustc_vv"].startswith(f"rustc {RUST_TOOLCHAIN} "):
        raise ValueError(f"unexpected Rust compiler: {values['rustc_vv'].splitlines()[0]}")
    return values


def _load_frozen(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    digest_path = run_dir / "manifest.sha256"
    expected = digest_path.read_text(encoding="ascii").strip()
    actual = sha256_file(manifest_path)
    if expected != actual:
        raise AdmissionError("manifest hash mismatch")
    manifest = _load_object(manifest_path, "formal manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise AdmissionError("unsupported formal manifest schema")
    _validate_manifest_contract(manifest)
    return manifest


def _validate_manifest_contract(manifest: dict[str, Any]) -> None:
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 11:
        raise AdmissionError("formal manifest must contain exactly 11 case groups")
    if sum(case.get("observation_level") == "summary" for case in cases) != 10:
        raise AdmissionError("formal manifest must contain ten summary groups")
    if sum(case.get("observation_level") == "full" for case in cases) != 1:
        raise AdmissionError("formal manifest must contain one full group")
    if manifest.get("schedule") != _schedule(cases):
        raise AdmissionError("formal schedule differs from the frozen 99-cell matrix")
    protocol = manifest.get("protocol", {})
    expected = {
        "seeds": list(SEEDS),
        "worker_threads": WORKER_THREADS,
        "warmups_per_process": WARMUPS,
        "repeats": REPEATS,
        "arm_rotations": [list(value) for value in ARM_ROTATIONS],
        "cpuset": "0-7",
        "cell_timeout_seconds": CELL_TIMEOUT_SECONDS,
        "postflight_reserve_seconds": POSTFLIGHT_RESERVE_SECONDS,
        "minimum_cell_start_seconds": MINIMUM_CELL_START_SECONDS,
        "window_deadline_seconds": WINDOW_DEADLINE_SECONDS,
        "max_normalized_load": MAX_NORMALIZED_LOAD,
    }
    for field, value in expected.items():
        if protocol.get(field) != value:
            raise AdmissionError(f"formal protocol field changed: {field}")


def _validate_frozen_files(manifest: dict[str, Any]) -> None:
    if _git_head() != manifest["source_commit"] or _git_tracked_status():
        raise AdmissionError("source revision or tracked tree changed after preparation")
    artifacts = manifest["artifacts"]
    for label, identity in artifacts.items():
        path = _require_file(Path(identity["path"]), label, executable=True)
        if sha256_file(path) != identity["sha256"]:
            raise AdmissionError(f"{label} hash changed after preparation")
    gate = manifest["semantic_gate"]
    if sha256_file(Path(gate["path"])) != gate["file_sha256"]:
        raise AdmissionError("semantic gate changed after preparation")
    runtime = _require_file(Path(gate["runtime"]["path"]), "semantic runtime", executable=True)
    if sha256_file(runtime) != gate["runtime"]["sha256"]:
        raise AdmissionError("semantic runtime changed after preparation")
    for raw_path, digest in gate["raw_files"].items():
        if sha256_file(_require_file(Path(raw_path), "semantic raw evidence")) != digest:
            raise AdmissionError(f"semantic raw evidence changed: {raw_path}")
    if sha256_file(Path(manifest["plan_map"]["path"])) != manifest["plan_map"]["sha256"]:
        raise AdmissionError("plan map changed after preparation")
    for case in manifest["cases"]:
        for arm in ("scan_plan", "indexed_plan"):
            identity = case[arm]
            path = _require_file(Path(identity["path"]), arm)
            if path.stat().st_size != identity["bytes"] or sha256_file(path) != identity["sha256"]:
                raise AdmissionError(f"{case['case_id']} {arm} changed after preparation")
    if _rust_toolchain_identity() != manifest["toolchain"]:
        raise AdmissionError("Rust 1.90.0 toolchain identity changed after preparation")


def _descendant_pids(root_pid: int) -> set[int]:
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for status in Path("/proc").glob("[0-9]*/status"):
            try:
                lines = status.read_text(encoding="utf-8", errors="replace").splitlines()
                ppid = int(next(line for line in lines if line.startswith("PPid:")).split()[1])
                pid = int(status.parent.name)
            except (OSError, StopIteration, ValueError):
                continue
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return descendants


def _is_heavy_process(comm: str, tokens: list[str]) -> bool:
    executable = Path(tokens[0]).name if tokens else ""
    comm_match = any(
        comm == name or (len(comm) == 15 and name.startswith(comm))
        for name in HEAVY_PROCESS_NAMES
    )
    executable_match = executable in HEAVY_PROCESS_NAMES
    python_test = executable.startswith("python") and any(
        (token in {"pytest", "unittest"} and index > 0 and tokens[index - 1] == "-m")
        or (token.endswith(".py") and "/benchmarks/" in token)
        for index, token in enumerate(tokens)
    )
    return comm_match or executable_match or python_test


def _has_live_ancestor(pid: int, ancestor: int) -> bool:
    current = pid
    visited: set[int] = set()
    for _ in range(64):
        if current == ancestor:
            return True
        if current <= 1 or current in visited:
            return False
        visited.add(current)
        try:
            lines = Path(f"/proc/{current}/status").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            current = int(next(line for line in lines if line.startswith("PPid:")).split()[1])
        except (OSError, StopIteration, ValueError):
            return False
    return False


def heavy_processes(*, owned_pids: set[int] | None = None) -> list[dict[str, Any]]:
    owned = owned_pids or _descendant_pids(os.getpid())
    found: list[dict[str, Any]] = []
    for directory in Path("/proc").glob("[0-9]*"):
        try:
            pid = int(directory.name)
            if pid in owned:
                continue
            comm = (directory / "comm").read_text(encoding="utf-8").strip()
            raw_tokens = (directory / "cmdline").read_bytes().split(b"\0")
            tokens = [token.decode("utf-8", errors="replace") for token in raw_tokens if token]
            if not _is_heavy_process(comm, tokens):
                continue
            if _has_live_ancestor(pid, os.getpid()):
                continue
            cmdline = " ".join(tokens)
        except (OSError, ValueError):
            continue
        found.append({"pid": pid, "comm": comm, "cmdline": cmdline})
    return sorted(found, key=lambda value: value["pid"])


def _namespace_link(path: str) -> dict[str, str]:
    try:
        return {"value": os.readlink(path)}
    except OSError as error:
        return {"error_type": type(error).__name__, "error": str(error)}


def machine_snapshot(*, detailed_processes: bool = False) -> dict[str, Any]:
    load = os.getloadavg()
    cpu_count = os.cpu_count() or 1
    visible_pids = sorted(int(path.name) for path in Path("/proc").glob("[0-9]*"))
    snapshot: dict[str, Any] = {
        "monotonic_ns": time.monotonic_ns(),
        "hostname": platform.node(),
        "load_average": list(load),
        "logical_cpus": cpu_count,
        "normalized_load_1m": load[0] / cpu_count,
        "process_affinity": sorted(os.sched_getaffinity(0)),
        "pid_namespace": _namespace_link("/proc/self/ns/pid"),
        "visible_pid_count": len(visible_pids),
        "maximum_visible_pid": max(visible_pids, default=0),
        "heavy_processes": heavy_processes(),
    }
    if detailed_processes:
        completed = subprocess.run(
            ["ps", "-eo", "pid,ppid,comm,args"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        snapshot["ps_command"] = ["ps", "-eo", "pid,ppid,comm,args"]
        snapshot["ps_output"] = completed.stdout
        snapshot["ps_output_sha256"] = sha256_bytes(completed.stdout.encode("utf-8"))
        lscpu = subprocess.run(
            ["lscpu", "--json"], check=True, capture_output=True, text=True, timeout=5
        )
        snapshot["lscpu_json"] = json.loads(lscpu.stdout)
        snapshot["meminfo"] = Path("/proc/meminfo").read_text(encoding="utf-8")
        snapshot["proc_stat"] = Path("/proc/stat").read_text(encoding="utf-8")
        snapshot["namespaces"] = {
            name: {
                "self": _namespace_link(f"/proc/self/ns/{name}"),
                "pid_1": _namespace_link(f"/proc/1/ns/{name}"),
            }
            for name in ("pid", "mnt", "user", "net", "uts", "cgroup")
        }
    return snapshot


def _admit(snapshot: dict[str, Any], maximum: float) -> None:
    if snapshot["hostname"] != EXPECTED_HOST:
        raise AdmissionError(f"formal host must be {EXPECTED_HOST}")
    if snapshot["normalized_load_1m"] > maximum:
        raise AdmissionError(
            f"normalized 1m load {snapshot['normalized_load_1m']:.3f} exceeds {maximum:.3f}"
        )
    if snapshot["heavy_processes"]:
        raise AdmissionError("foreign heavy process overlaps the formal window")
    if not set(range(8)).issubset(snapshot["process_affinity"]):
        raise AdmissionError("formal cpuset 0-7 is outside the process affinity allowance")


def parse_gnu_time(stderr: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith("Maximum resident set size (kbytes):"):
            result["maximum_resident_set_kbytes"] = int(stripped.rsplit(":", 1)[1].strip())
        elif stripped.startswith("Elapsed (wall clock) time"):
            result["elapsed_wall"] = stripped.rsplit(": ", 1)[-1]
        elif stripped.startswith("Percent of CPU this job got:"):
            result["cpu_percent"] = stripped.rsplit(":", 1)[1].strip()
    if "maximum_resident_set_kbytes" not in result:
        raise ValueError("GNU time output lacks maximum resident set size")
    return result


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("owned process group did not terminate after SIGKILL") from error


def _run_capture(
    command: list[str],
    *,
    timeout: float,
    overlap_check: Callable[[], list[dict[str, Any]]],
    environment: dict[str, str],
) -> dict[str, Any]:
    started = time.monotonic()
    started_ns = time.monotonic_ns()
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stdout_file, tempfile.TemporaryFile(
        mode="w+t", encoding="utf-8"
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
            env={**os.environ, **environment},
        )
        overlap: list[dict[str, Any]] = []
        timed_out = False
        interrupted: BaseException | None = None
        try:
            while process.poll() is None:
                elapsed = time.monotonic() - started
                if elapsed > timeout:
                    timed_out = True
                    _terminate(process)
                    break
                overlap = overlap_check()
                if overlap:
                    _terminate(process)
                    break
                try:
                    process.wait(timeout=min(0.25, max(0.001, timeout - elapsed)))
                except subprocess.TimeoutExpired:
                    pass
        except BaseException as error:
            interrupted = error
            _terminate(process)
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read()
        stderr = stderr_file.read()
    execution = {
        "command": command,
        "started_monotonic_ns": started_ns,
        "finished_monotonic_ns": time.monotonic_ns(),
        "wall_ns": int((time.monotonic() - started) * 1_000_000_000),
        "exit_status": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "overlap": overlap,
    }
    if interrupted is not None:
        execution["interrupted"] = True
        raise CellFailure(
            f"coordinator_interrupt:{type(interrupted).__name__}", execution
        ) from interrupted
    if timed_out:
        raise CellFailure("cell_timeout", execution)
    if overlap:
        raise CellFailure("foreign_process_overlap", execution)
    if process.returncode != 0:
        raise CellFailure(f"cell_exit_status:{process.returncode}", execution)
    return execution


def _case_by_id(manifest: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(case for case in manifest["cases"] if case["case_id"] == case_id)


def _cell_command(
    manifest: dict[str, Any], cell: dict[str, Any], report_path: Path, time_path: Path
) -> list[str]:
    case = _case_by_id(manifest, cell["case_id"])
    plan_key = "scan_plan" if cell["arm"] == "scan" else "indexed_plan"
    command = [
        manifest["artifacts"]["taskset"]["path"],
        "-c",
        manifest["protocol"]["cpuset"],
        manifest["artifacts"]["gnu_time"]["path"],
        "-v",
        "-o",
        str(time_path),
        manifest["artifacts"]["stage_c_benchmark"]["path"],
        case[plan_key]["path"],
        str(report_path),
        "--seeds",
        ",".join(str(seed) for seed in cell["seeds"]),
        "--worker-threads",
        str(cell["worker_threads"]),
        "--warmups",
        str(cell["warmups"]),
        "--repeats",
        str(cell["measured_repeats"]),
        "--observation-level",
        cell["observation_level"],
    ]
    if cell["arm"] == "candidates":
        command.append("--dependency-dispatch")
    return command


def _verify_report(
    manifest: dict[str, Any], cell: dict[str, Any], report: dict[str, Any]
) -> str:
    case = _case_by_id(manifest, cell["case_id"])
    plan = case["scan_plan"] if cell["arm"] == "scan" else case["indexed_plan"]
    expected_dispatch = cell["arm"] == "candidates"
    expected = {
        "schema_version": REPORT_SCHEMA,
        "plan_path": plan["path"],
        "plan_bytes": plan["bytes"],
        "plan_fingerprint": case["plan_fingerprint"],
        "semantic_profile": case["semantic_profile"],
        "work_policy": plan["work_policy"],
        "rng_profile": plan["rng_profile"],
        "seeds": list(SEEDS),
        "worker_threads": WORKER_THREADS,
        "warmups": WARMUPS,
        "repeats": 1,
        "until": None,
        "observation_level": cell["observation_level"],
        "dependency_dispatch": expected_dispatch,
    }
    for field, value in expected.items():
        if report.get(field) != value:
            raise ValueError(f"stage-c report field {field} differs from frozen cell")
    rustc = report.get("rustc")
    if not isinstance(rustc, str) or not rustc.startswith(f"rustc {RUST_TOOLCHAIN} "):
        raise ValueError("stage-c report was not produced with frozen rustc 1.90.0")
    records = report.get("records")
    if not isinstance(records, list) or len(records) != 1:
        raise ValueError("stage-c report must contain exactly one measured record")
    record = records[0]
    if record.get("repeat") != 0:
        raise ValueError("stage-c record repeat must be zero")
    if record.get("sample_indexes") != [0, 1, 2] or record.get("seeds") != list(SEEDS):
        raise ValueError("stage-c result order differs from frozen seeds")
    digest = record.get("samples_sha256")
    if not _is_sha256(digest):
        raise ValueError("stage-c report lacks sample digest")
    phases = record.get("phases")
    required_phases = {
        "plan_read_ns",
        "plan_parse_validate_ns",
        "fingerprint_ns",
        "run_state_initialization_ns",
        "single_sample_execution_ns",
        "single_sample_serialization_ns",
        "batch_execution_ns",
        "batch_serialization_ns",
        "batch_write_ns",
        "end_to_end_batch_ns",
    }
    if not isinstance(phases, dict) or set(phases) != required_phases:
        raise ValueError("stage-c report lacks required phase timings")
    if any(type(phases[field]) is not int or phases[field] < 0 for field in required_phases):
        raise ValueError("stage-c report contains invalid phase timings")
    for field in ("batch_result_sha256",):
        if not _is_sha256(record.get(field)):
            raise ValueError(f"stage-c record contains invalid {field}")
    for field in ("single_result_bytes", "batch_result_bytes"):
        if type(record.get(field)) is not int or record[field] <= 0:
            raise ValueError(f"stage-c record contains invalid {field}")
    return digest


def _persist_state(path: Path, state: dict[str, Any]) -> None:
    _write_json(path, state)


def measure(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.expanduser().resolve(strict=True)
    manifest = _load_frozen(run_dir)
    state_path = run_dir / "state.json"
    try:
        descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as error:
        raise AdmissionError("formal window is once-only and state.json already exists") from error
    os.close(descriptor)
    started = time.monotonic()
    state: dict[str, Any] = {
        "schema_version": STATE_SCHEMA,
        "status": "admitting",
        "started_at_unix_seconds": int(time.time()),
        "manifest_sha256": sha256_file(run_dir / "manifest.json"),
        "cells_total": len(manifest["schedule"]),
        "cells_completed": 0,
        "records": [],
    }
    _persist_state(state_path, state)
    signals = tuple(
        signum for signum in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None))
        if signum is not None
    )
    previous_handlers = {signum: signal.getsignal(signum) for signum in signals}

    def interrupt(signum: int, _frame: object) -> None:
        raise CoordinatorInterrupted(signum)

    for signum in signals:
        signal.signal(signum, interrupt)
    try:
        if args.deadline_seconds > WINDOW_DEADLINE_SECONDS or args.deadline_seconds <= 0:
            raise AdmissionError("deadline must be in (0, 1200]")
        _validate_frozen_files(manifest)
        preflight = machine_snapshot(detailed_processes=True)
        state["preflight"] = preflight
        _admit(preflight, manifest["protocol"]["max_normalized_load"])
        state["status"] = "running"
        _persist_state(state_path, state)
        expected_by_case: dict[str, str] = {}
        for cell in manifest["schedule"]:
            remaining = args.deadline_seconds - (time.monotonic() - started)
            if remaining < MINIMUM_CELL_START_SECONDS:
                raise AdmissionError("insufficient_time_for_next_cell_and_postflight")
            ordinal = cell["ordinal"]
            cell_dir = run_dir / "measurement" / f"cell-{ordinal:03d}"
            cell_dir.mkdir(parents=True, exist_ok=False)
            report_path = cell_dir / "stage-c-report.json"
            time_path = cell_dir / "gnu-time.txt"
            command = _cell_command(manifest, cell, report_path, time_path)
            before = machine_snapshot()
            _admit(before, manifest["protocol"]["max_normalized_load"])
            remaining = args.deadline_seconds - (time.monotonic() - started)
            if remaining < MINIMUM_CELL_START_SECONDS:
                raise AdmissionError("insufficient_time_after_cell_preflight")
            timeout = min(CELL_TIMEOUT_SECONDS, remaining - POSTFLIGHT_RESERVE_SECONDS)
            try:
                execution = _run_capture(
                    command,
                    timeout=timeout,
                    overlap_check=lambda: heavy_processes(),
                    environment={"RUSTUP_TOOLCHAIN": RUST_TOOLCHAIN},
                )
                report = _load_object(report_path, "stage-c report")
                digest = _verify_report(manifest, cell, report)
                timing_text = time_path.read_text(encoding="utf-8")
                timing = parse_gnu_time(timing_text)
                prior = expected_by_case.setdefault(cell["case_id"], digest)
                if digest != prior:
                    raise ValueError("sample result digest differs across arms or repeats")
                after = machine_snapshot()
                _admit(after, manifest["protocol"]["max_normalized_load"])
                record = {
                    "cell": cell,
                    "status": "complete",
                    "execution": execution,
                    "stage_c_report_sha256": sha256_file(report_path),
                    "samples_sha256": digest,
                    "gnu_time": timing,
                    "gnu_time_sha256": sha256_file(time_path),
                    "machine_before": before,
                    "machine_after": after,
                }
                _write_json(cell_dir / "record.json", record)
            except BaseException as error:
                execution = error.execution if isinstance(error, CellFailure) else None
                failure = {
                    "cell": cell,
                    "status": "failed",
                    "failure": {"type": type(error).__name__, "message": str(error)},
                    "execution": execution,
                    "available_files": sorted(path.name for path in cell_dir.iterdir()),
                }
                _write_json(cell_dir / "record.json", failure)
                raise
            state["records"].append(str((cell_dir / "record.json").relative_to(run_dir)))
            state["cells_completed"] += 1
            _persist_state(state_path, state)
        state["postflight"] = machine_snapshot(detailed_processes=True)
        _admit(state["postflight"], manifest["protocol"]["max_normalized_load"])
        if time.monotonic() - started > args.deadline_seconds:
            raise AdmissionError("deadline_exceeded_during_postflight")
        state["status"] = "complete"
        state["finished_at_unix_seconds"] = int(time.time())
        state["elapsed_seconds"] = time.monotonic() - started
        _persist_state(state_path, state)
        if time.monotonic() - started > args.deadline_seconds:
            raise AdmissionError("deadline_exceeded_during_completion_write")
        return state
    except BaseException as error:
        state["status"] = "incomplete"
        state["stop_reason"] = f"{type(error).__name__}:{error}"
        state["finished_at_unix_seconds"] = int(time.time())
        state["elapsed_seconds"] = time.monotonic() - started
        _persist_state(state_path, state)
        raise
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def status(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir.expanduser().resolve(strict=True)
    manifest = _load_frozen(run_dir)
    state_path = run_dir / "state.json"
    return {
        "manifest_sha256": sha256_file(run_dir / "manifest.json"),
        "cells_total": len(manifest["schedule"]),
        "state": _load_object(state_path, "formal state") if state_path.exists() else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument("--semantic-gate", type=Path, required=True)
    prepare_parser.add_argument("--plan-map", type=Path, required=True)
    prepare_parser.add_argument("--stage-binary", type=Path, required=True)
    prepare_parser.add_argument("--cpuset", default="0-7")
    prepare_parser.add_argument("--gnu-time", type=Path, default=Path("/usr/bin/time"))
    prepare_parser.add_argument("--taskset", type=Path, default=Path("/usr/bin/taskset"))
    prepare_parser.set_defaults(function=prepare)
    measure_parser = subparsers.add_parser("measure")
    measure_parser.add_argument("--run-dir", type=Path, required=True)
    measure_parser.add_argument("--deadline-seconds", type=int, default=WINDOW_DEADLINE_SECONDS)
    measure_parser.set_defaults(function=measure)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--run-dir", type=Path, required=True)
    status_parser.set_defaults(function=status)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.function(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
