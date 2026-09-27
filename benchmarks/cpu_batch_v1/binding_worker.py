#!/usr/bin/env python3
"""Fresh-process worker for the public PyO3 ``run_batch`` boundary.

This module deliberately imports only the public package API.  It never reaches
through the binding to a private prepared-plan handle and never exposes a
dependency-dispatch switch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _json_bytes(value: Any, *, sort_keys: bool = False) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _jsonable_divergence(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else value


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _validate_batch(
    result: dict[str, Any],
    seeds: Sequence[int],
    *,
    worker_threads: int | None = None,
) -> None:
    samples = result.get("samples")
    if not isinstance(samples, list):
        raise TypeError("run_batch result has no samples list")
    indexes = [sample.get("sample_index") for sample in samples]
    actual_seeds = [sample.get("seed") for sample in samples]
    if indexes != list(range(len(seeds))):
        raise AssertionError(f"sample_index order changed: {indexes!r}")
    if actual_seeds != list(seeds):
        raise AssertionError(f"seed order changed: {actual_seeds!r}")
    if result.get("sample_count") != len(seeds):
        raise AssertionError("run_batch sample_count changed")
    if result.get("until") is not None:
        raise AssertionError("run_batch unexpectedly applied an until horizon")
    if worker_threads is not None and result.get("worker_threads") != min(
        worker_threads, len(seeds)
    ):
        raise AssertionError("run_batch effective worker count changed")
    fingerprint = result.get("plan_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise AssertionError("run_batch omitted Plan fingerprint")
    if any(sample["result"].get("plan_fingerprint") != fingerprint for sample in samples):
        raise AssertionError("sample Plan fingerprint differs from batch envelope")


def _batch_proof(result: dict[str, Any], seeds: Sequence[int]) -> dict[str, Any]:
    _validate_batch(result, seeds)
    samples = result["samples"]
    ordered = _json_bytes(samples)
    canonical = _json_bytes(samples, sort_keys=True)
    return {
        "sample_indexes": [sample["sample_index"] for sample in samples],
        "seeds": [sample["seed"] for sample in samples],
        # Ordered and canonical digests are proof within this Python boundary.
        # They are never used as cross-language tree-equivalence evidence.
        "samples_sha256": _sha256(ordered),
        "samples_canonical_sha256": _sha256(canonical),
        "samples_json_bytes": len(ordered),
        "per_sample_result_sha256": [
            _sha256(_json_bytes(sample["result"], sort_keys=True)) for sample in samples
        ],
    }


def run_cell(
    plan_path: Path,
    seeds: list[int],
    worker_threads: int,
    observation_level: str,
    report_path: Path,
) -> dict[str, Any]:
    import sim_engine_compiler

    if not sim_engine_compiler.native_available():
        raise RuntimeError("native binding unavailable")

    started = time.perf_counter_ns()
    plan_bytes = plan_path.read_bytes()
    plan_read_ns = time.perf_counter_ns() - started
    plan_payload = json.loads(plan_bytes)

    warmup = sim_engine_compiler.run_batch(
        plan_bytes,
        seeds,
        worker_threads=worker_threads,
        observation_level=observation_level,
    )
    _validate_batch(warmup, seeds, worker_threads=worker_threads)
    warmup_proof = _batch_proof(warmup, seeds)
    started = time.perf_counter_ns()
    result = sim_engine_compiler.run_batch(
        plan_bytes,
        seeds,
        worker_threads=worker_threads,
        observation_level=observation_level,
    )
    call_ns = time.perf_counter_ns() - started
    _validate_batch(result, seeds, worker_threads=worker_threads)
    proof = _batch_proof(result, seeds)
    if warmup["samples"] != result["samples"]:
        raise AssertionError("warmup and measured sample trees differ")

    started = time.perf_counter_ns()
    encoded = _json_bytes(result["samples"])
    wrapper_encode_ns = time.perf_counter_ns() - started
    with tempfile.NamedTemporaryFile(
        prefix="cpu-batch-binding-", suffix=".json", delete=False
    ) as handle:
        scratch = Path(handle.name)
        started = time.perf_counter_ns()
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        wrapper_write_ns = time.perf_counter_ns() - started
    scratch.unlink()

    report = {
        "schema_version": "cpu-batch-binding-cell/v1",
        "backend": "pyo3-public-run-batch",
        "observation_level": observation_level,
        "worker_threads": worker_threads,
        "effective_worker_threads": min(worker_threads, len(seeds)),
        "sample_count": len(seeds),
        "warmups": 1,
        "warmup_completed": True,
        "warmup_proof": warmup_proof,
        "warmup_matches_measured": True,
        "measured_calls": 1,
        "plan_read_ns": plan_read_ns,
        "plan": {
            "path": str(plan_path.resolve()),
            "sha256": _sha256(plan_bytes),
            "bytes": len(plan_bytes),
            "semantic_profile": plan_payload["semantic_profile"],
            "work_policy": plan_payload["work_policy"],
            "rng_profile": plan_payload["rng_profile"],
            "duration_minutes": plan_payload["duration_minutes"],
            "source_inputs_sha256": plan_payload["source_inputs_sha256"],
            "resource_dispatch_index_present": "resource_dispatch_index" in plan_payload,
        },
        "result_envelope": {
            key: result[key]
            for key in ("plan_fingerprint", "sample_count", "worker_threads", "until")
        },
        "warmup_envelope": {
            key: warmup[key]
            for key in ("plan_fingerprint", "sample_count", "worker_threads", "until")
        },
        "call_ns": call_ns,
        "wrapper_encode_ns": wrapper_encode_ns,
        "wrapper_write_ns": wrapper_write_ns,
        "stages": {
            "canonical_compilation_ns": None,
            "plan_read_ns": plan_read_ns,
            "parse_validate_prepare_pool_initialize_execute_serialize_transfer_decode_ns": call_ns,
            "batch_only_initialization_ns": None,
            "batch_only_execution_ns": None,
            "wrapper_encode_ns": wrapper_encode_ns,
            "wrapper_write_ns": wrapper_write_ns,
            "independent_in_process_end_to_end_ns": None,
        },
        "boundary": (
            "call_ns is one public run_batch(plan_bytes, seeds) call after one "
            "identical untimed warmup; Plan read, process/import startup and wrapper "
            "evidence encoding/writing are outside call_ns"
        ),
        "proof": proof,
    }
    _atomic_json(report_path, report)
    return report


def _without_plan_identity(result: dict[str, Any]) -> dict[str, Any]:
    value = dict(result)
    value.pop("plan_fingerprint", None)
    return value


def _without_trace(result: dict[str, Any]) -> dict[str, Any]:
    value = dict(result)
    value.pop("trace", None)
    return value


def run_semantic_gate(
    plan_path: Path, reference_plan_path: Path, report_path: Path
) -> dict[str, Any]:
    import sim_engine_compiler
    from sim_engine_compiler.ir.plan import ExecutionPlan
    from sim_engine_compiler.reference import SimpyReferenceRuntime
    from sim_engine_compiler.reference.conformance import first_divergence

    if not sim_engine_compiler.native_available():
        raise RuntimeError("native binding unavailable")
    plan_bytes = plan_path.read_bytes()
    reference_plan_bytes = reference_plan_path.read_bytes()
    reference_plan = ExecutionPlan.from_dict(
        json.loads(reference_plan_path.read_text(encoding="utf-8"))
    )
    required_seeds = [0, 1, 7]
    legacy_full = sim_engine_compiler.run_batch(
        reference_plan_bytes,
        required_seeds,
        worker_threads=1,
        observation_level="full",
    )
    event_full = sim_engine_compiler.run_batch(
        plan_bytes, required_seeds, worker_threads=1, observation_level="full"
    )
    event_summary = sim_engine_compiler.run_batch(
        plan_bytes, required_seeds, worker_threads=1, observation_level="summary"
    )
    _validate_batch(legacy_full, required_seeds)
    _validate_batch(event_full, required_seeds)
    _validate_batch(event_summary, required_seeds)

    reference_exact_divergences: list[Any] = []
    reference_accepted_divergences: list[Any] = []
    profile_divergences: list[Any] = []
    observation_divergences: list[Any] = []
    reference_results: list[dict[str, Any]] = []
    for index, seed in enumerate(required_seeds):
        reference = SimpyReferenceRuntime(reference_plan, seed=seed).run()
        reference_results.append(reference)
        reference_exact_divergences.append(
            _jsonable_divergence(
                first_divergence(
                    reference, legacy_full["samples"][index]["result"]
                )
            )
        )
        reference_accepted_divergences.append(
            _jsonable_divergence(first_divergence(
                reference,
                legacy_full["samples"][index]["result"],
                float_rel_tol=2e-15,
                float_abs_tol=1e-12,
            ))
        )
        legacy_normalized = _without_plan_identity(
            legacy_full["samples"][index]["result"]
        )
        event_normalized = _without_plan_identity(
            event_full["samples"][index]["result"]
        )
        profile_divergences.append(
            None
            if legacy_normalized == event_normalized
            else _jsonable_divergence(
                first_divergence(legacy_normalized, event_normalized)
            )
        )
        if event_summary["samples"][index]["result"].get("trace") != []:
            observation_divergences.append("$.trace: summary trace is not empty")
        else:
            full_non_trace = _without_trace(event_full["samples"][index]["result"])
            summary_non_trace = _without_trace(
                event_summary["samples"][index]["result"]
            )
            observation_divergences.append(
                None
                if full_non_trace == summary_non_trace
                else _jsonable_divergence(
                    first_divergence(full_non_trace, summary_non_trace)
                )
            )

    duplicate_seeds = [7, 0, 7, 1]
    duplicate_runs: dict[str, dict[str, Any]] = {}
    duplicate_results: dict[tuple[str, int], dict[str, Any]] = {}
    for observation in ("full", "summary"):
        for workers in (1, 8):
            value = sim_engine_compiler.run_batch(
                plan_bytes,
                duplicate_seeds,
                worker_threads=workers,
                observation_level=observation,
            )
            _validate_batch(value, duplicate_seeds)
            duplicate_results[(observation, workers)] = value
            duplicate_runs[f"{observation}-w{workers}"] = _batch_proof(
                value, duplicate_seeds
            )

    duplicate_checks = {
        "full_worker_invariant": duplicate_results[("full", 1)]["samples"]
        == duplicate_results[("full", 8)]["samples"],
        "summary_worker_invariant": duplicate_results[("summary", 1)]["samples"]
        == duplicate_results[("summary", 8)]["samples"],
        "duplicate_seed_7_equal_not_aliased": (
            duplicate_results[("full", 1)]["samples"][0]["result"]
            == duplicate_results[("full", 1)]["samples"][2]["result"]
            and duplicate_results[("full", 1)]["samples"][0] is not duplicate_results[("full", 1)]["samples"][2]
        ),
        "duplicate_summary_seed_7_equal_not_aliased": (
            duplicate_results[("summary", 1)]["samples"][0]["result"]
            == duplicate_results[("summary", 1)]["samples"][2]["result"]
            and duplicate_results[("summary", 1)]["samples"][0]
            is not duplicate_results[("summary", 1)]["samples"][2]
        ),
        "duplicate_full_summary_equivalent": all(
            _without_trace(full_sample["result"])
            == _without_trace(summary_sample["result"])
            and summary_sample["result"].get("trace") == []
            for full_sample, summary_sample in zip(
                duplicate_results[("full", 1)]["samples"],
                duplicate_results[("summary", 1)]["samples"],
                strict=True,
            )
        ),
    }
    passed = (
        all(item is None for item in reference_accepted_divergences)
        and all(item is None for item in profile_divergences)
        and all(item is None for item in observation_divergences)
        and all(duplicate_checks.values())
    )
    report = {
        "schema_version": "cpu-batch-binding-semantic-gate/v1",
        "passed": passed,
        "required_seeds": required_seeds,
        "reference_comparison_policy": {
            "source": "tests/differential/test_rust_runtime.py F35 accepted cross-backend policy",
            "exact_checked_first": True,
            "float_rel_tol": 2e-15,
            "float_abs_tol": 1e-12,
        },
        "reference_exact_divergences": reference_exact_divergences,
        "reference_accepted_divergences": reference_accepted_divergences,
        "profile_transition_divergences": profile_divergences,
        "observation_divergences": observation_divergences,
        "legacy_full": _batch_proof(legacy_full, required_seeds),
        "event_full": _batch_proof(event_full, required_seeds),
        "event_summary": _batch_proof(event_summary, required_seeds),
        "duplicate_seeds": duplicate_seeds,
        "duplicate_runs": duplicate_runs,
        "duplicate_checks": duplicate_checks,
        "candidate_dispatch": "unavailable through public run_batch",
    }
    raw_path = report_path.with_name(f"{report_path.stem}-raw.json")
    raw = {
        "reference_results": reference_results,
        "legacy_full": legacy_full,
        "event_full": event_full,
        "event_summary": event_summary,
        "duplicate_runs": {
            f"{observation}-w{workers}": value
            for (observation, workers), value in duplicate_results.items()
        },
    }
    _atomic_json(raw_path, raw)
    report["raw_results"] = {
        "path": raw_path.name,
        "sha256": _sha256(raw_path.read_bytes()),
        "bytes": raw_path.stat().st_size,
    }
    _atomic_json(report_path, report)
    if not passed:
        raise AssertionError("PyO3/reference semantic gate failed")
    return report


def _parse_seeds(value: str) -> list[int]:
    seeds = [int(item) for item in value.split(",") if item.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    cell = subparsers.add_parser("cell")
    cell.add_argument("--plan", type=Path, required=True)
    cell.add_argument("--seeds", type=_parse_seeds, required=True)
    cell.add_argument("--worker-threads", type=int, required=True)
    cell.add_argument("--observation-level", choices=("full", "summary"), required=True)
    cell.add_argument("--report", type=Path, required=True)
    gate = subparsers.add_parser("semantic-gate")
    gate.add_argument("--plan", type=Path, required=True)
    gate.add_argument("--reference-plan", type=Path, required=True)
    gate.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "cell":
        if args.worker_threads < 1:
            parser.error("worker-threads must be positive")
        run_cell(
            args.plan,
            args.seeds,
            args.worker_threads,
            args.observation_level,
            args.report,
        )
    else:
        run_semantic_gate(args.plan, args.reference_plan, args.report)


if __name__ == "__main__":
    main()
