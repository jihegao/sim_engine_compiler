#!/usr/bin/env python3
"""Execute submitted models using the existing bounded three-layer pipeline.

``validate`` has no dependency on tasks, expected models, or private scoring.
``evaluate`` adds the independent evaluator *after* execution. Every invocation
uses an empty output directory, preserving previous submissions and receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sim_engine_compiler.ir.bounded import BUSINESS, CORE, PLAN, Document, digest
from sim_engine_compiler.integrations.spare_mvp.bounded import import_bounded_business
from sim_engine_compiler.domains.aircraft_support.bounded import lower_bounded, operation_contracts
from sim_engine_compiler.compiler.bounded_layout import compile_bounded
from sim_engine_compiler.domains.aircraft_support.bounded_runtime import BoundedAircraftRuntime


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def no_constant(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=no_duplicates, parse_constant=no_constant)


def validate_candidate(candidate):
    if type(candidate) is not dict or set(candidate) != {
        "task_id", "status", "model", "questions", "reason"
    }:
        raise ValueError("candidate requires exactly task_id, status, model, questions, reason")
    if type(candidate["task_id"]) is not str or not candidate["task_id"]:
        raise ValueError("task_id must be a nonempty string")
    if candidate["status"] not in ("model", "clarify", "unsupported"):
        raise ValueError("status must be model, clarify, or unsupported")
    if type(candidate["reason"]) is not str:
        raise ValueError("reason must be a string")
    if type(candidate["questions"]) is not list:
        raise ValueError("questions must be a list")
    for question in candidate["questions"]:
        if (type(question) is not dict or set(question) != {"field", "question"}
                or any(type(question[k]) is not str or not question[k]
                       for k in ("field", "question"))):
            raise ValueError("each question requires nonempty string field and question")
    if candidate["status"] == "model":
        if type(candidate["model"]) is not dict or candidate["questions"]:
            raise ValueError("model status requires a complete model and empty questions")
    else:
        if candidate["model"] is not None or not candidate["reason"]:
            raise ValueError("non-model status requires null model and a nonempty reason")
        if candidate["status"] == "clarify" and not candidate["questions"]:
            raise ValueError("clarify status requires at least one question")
        if candidate["status"] == "unsupported" and candidate["questions"]:
            raise ValueError("unsupported status requires empty questions")


def roundtrip(document, path, version):
    write_json(path, document.to_dict())
    reloaded = Document.from_dict(read_json(path), version)
    if document.fingerprint != reloaded.fingerprint:
        raise ValueError("persist/reload fingerprint mismatch")
    return reloaded


def git_revision():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_candidate(candidate, out_dir, *, score=False):
    started = time.perf_counter()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {out_dir}")
    report = {
        "schema": "codex-modeling-pilot-run/v1",
        "task_id": candidate.get("task_id") if isinstance(candidate, dict) else None,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "evaluate" if score else "validate",
        "provider": "openai", "surface": "codex-session", "model_id": None,
        "model_id_note": "Exact model identifier unavailable; not inferred from product name.",
        "generation_seconds": None, "generation_tokens": None,
        "generation_cost": None,
        "python": platform.python_version(), "platform": platform.platform(),
        "git_revision": git_revision(),
        "candidate_valid": False, "compiled": False, "executed": False,
        "error": None, "result": None, "evaluation": None,
        "timings_seconds": {}, "fingerprints": {},
    }
    timings = report["timings_seconds"]
    stage = "candidate_validation"
    stage_started = time.perf_counter()
    try:
        write_json(out_dir / "candidate.json", candidate)
        validate_candidate(candidate)
        report["candidate_valid"] = True
        report["fingerprints"]["candidate"] = digest(candidate)
        timings[stage] = time.perf_counter() - stage_started
        if candidate["status"] == "model":
            canonical = {"schema_version": "aircraft-bounded-input/v1",
                         "semantic_profile": "aircraft-bounded-events/v1",
                         "model": candidate["model"]}
            write_json(out_dir / "canonical-input.json", canonical)
            compile_started = time.perf_counter()
            stage, stage_started = "business_import_and_roundtrip", time.perf_counter()
            business = roundtrip(import_bounded_business(canonical), out_dir / "business.json", BUSINESS)
            timings[stage] = time.perf_counter() - stage_started
            stage, stage_started = "core_lowering_and_roundtrip", time.perf_counter()
            core = roundtrip(lower_bounded(business), out_dir / "core.json", CORE)
            timings[stage] = time.perf_counter() - stage_started
            stage, stage_started = "plan_compile_and_roundtrip", time.perf_counter()
            plan = roundtrip(compile_bounded(core, operations=operation_contracts()),
                             out_dir / "plan.json", PLAN)
            timings[stage] = time.perf_counter() - stage_started
            timings["compile_with_persistence"] = time.perf_counter() - compile_started
            report["compiled"] = True
            report["fingerprints"].update(canonical=digest(canonical), business=business.fingerprint,
                                           core=core.fingerprint, plan=plan.fingerprint)
            write_json(out_dir / "source-maps.json", {
                "business": business.payload["source_map"],
                "core": {name: [{"id": r["id"], "source_path": r["source_path"]}
                                for r in rows] for name, rows in core.payload["tables"].items()},
                "plan": plan.payload["source_map"],
            })
            stage, stage_started = "runtime_initialization", time.perf_counter()
            runtime = BoundedAircraftRuntime(plan)
            timings[stage] = time.perf_counter() - stage_started
            stage, stage_started = "execution", time.perf_counter()
            result = runtime.run()
            timings[stage] = time.perf_counter() - stage_started
            report["result"] = result
            report["executed"] = True
            report["fingerprints"]["result"] = digest(result)
            write_json(out_dir / "result.json", result)
            write_json(out_dir / "trace.json", result["trace"])
    except Exception as exc:
        timings[stage] = time.perf_counter() - stage_started
        report["error"] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}

    # This is the sole oracle boundary. validate never imports this module.
    if score:
        score_started = time.perf_counter()
        try:
            evaluator = importlib.import_module("experiments.codex_modeling_pilot.evaluator")
            report["evaluation"] = evaluator.evaluate(candidate, report["result"])
            write_json(out_dir / "evaluation.json", report["evaluation"])
        except Exception as exc:
            report["evaluation_error"] = {"type": type(exc).__name__, "message": str(exc)}
        timings["independent_scoring"] = time.perf_counter() - score_started

    timings["total_runner"] = time.perf_counter() - started
    # Public feedback contains only structural/execution diagnostics, never a score.
    public = {key: report[key] for key in (
        "task_id", "candidate_valid", "compiled", "executed", "error", "timings_seconds"
    )}
    public["timings_seconds"] = {k: v for k, v in timings.items() if k != "independent_scoring"}
    write_json(out_dir / "public-diagnostics.json", public)
    write_json(out_dir / "run.json", {k: v for k, v in report.items() if k != "result"})
    write_json(out_dir / "artifact-hashes.json", {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out_dir.iterdir()) if p.is_file()
    })
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "evaluate"):
        command = sub.add_parser(name)
        command.add_argument("--candidate", required=True, type=Path)
        command.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    # Enable namespace-package import only for explicit independent scoring.
    if args.command == "evaluate":
        sys.path.insert(0, str(ROOT))
    try:
        report = run_candidate(read_json(args.candidate), args.out,
                               score=args.command == "evaluate")
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"task_id": report["task_id"], "out": str(args.out),
                      "candidate_valid": report["candidate_valid"],
                      "compiled": report["compiled"], "executed": report["executed"],
                      "error": report["error"],
                      **({"evaluation": report["evaluation"],
                          "evaluation_error": report.get("evaluation_error")}
                         if args.command == "evaluate" else {})}, ensure_ascii=False))
    return int(report["error"] is not None or "evaluation_error" in report
               or (args.command == "evaluate" and
                   not (report["evaluation"] or {}).get("accepted", False)))


if __name__ == "__main__":
    raise SystemExit(main())
