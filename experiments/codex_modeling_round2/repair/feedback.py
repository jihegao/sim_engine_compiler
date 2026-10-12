#!/usr/bin/env python3
"""Controller-mediated feedback. Never give participants the internal directory.

N: receipt only, no compilation/execution. D: compiler diagnostics only, no run.
T: compilation/execution diagnostics plus a
bounded trace summary and fixed public behavior probes. No scoring is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from experiments.codex_modeling_pilot import runner as pilot


def equal(actual, expected):
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 1e-10
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(equal(actual[k], v) for k, v in expected.items())
    return type(actual) is type(expected) and actual == expected


def selected(trace, kind, where):
    return [e for e in trace if e.get("kind") == kind and all(equal(e.get(k), v) for k, v in where.items())]


def check_probe(trace, spec):
    """Only the small preregistered public probes, never full task acceptance."""
    kind = spec["type"]
    if kind == "projection":
        events = selected(trace, spec["kind"], spec.get("where", {}))
        actual = [[e.get(field) for field in spec["fields"]] for e in events]
        expected = spec["expected"]
        passed = equal(actual, expected)
    elif kind == "resource_peak":
        usage, peak = 0, 0
        for event in trace:
            if event.get("resource") != spec["resource"]:
                continue
            if event.get("kind") == "resource_acquired":
                usage += event["quantity"]
                peak = max(peak, usage)
            elif event.get("kind") == "resource_released":
                usage -= event["quantity"]
        actual, expected = {"peak": peak}, {"peak_at_most": spec["maximum"]}
        passed = peak <= spec["maximum"]
    elif kind == "none_after":
        events = selected(trace, spec["kind"], spec.get("where", {}))
        actual = [{"hour": e.get("hour"), "kind": e.get("kind")} for e in events if e.get("hour", -1) > spec["after_hour"] + 1e-10]
        expected, passed = [], not actual
    elif kind == "ordered_events":
        found = [selected(trace, item["kind"], item.get("where", {})) for item in spec["events"]]
        actual = [[e.get("hour") for e in events] for events in found]
        passed = all(len(events) == 1 for events in found)
        if passed:
            indices = [trace.index(events[0]) for events in found]
            passed = all(a < b for a, b in zip(indices, indices[1:]))
        expected = {"each_occurs_once": True, "order": [item["label"] for item in spec["events"]]}
    else:
        raise ValueError(f"unknown public probe type: {kind}")
    return {"id": spec["id"], "description": spec["description"], "passed": bool(passed),
            "expected": expected, "actual": actual,
            "discrepancy": None if passed else {"expected": expected, "observed": actual}}


def trace_summary(result):
    trace = result.get("trace", [])
    keys = {"kind", "hour", "aircraft", "mission", "process", "step", "resource", "quantity",
            "owner", "cancelled", "outcome", "flight_hours", "driver", "pm", "reason"}
    events = [{k: v for k, v in event.items() if k in keys} for event in trace
              if event.get("kind") not in {"report", "observation", "snapshot"}]
    return {"trace_event_count": len(trace), "event_counts": dict(sorted(Counter(e.get("kind", "unknown") for e in trace).items())),
            "events": events[:200], "truncated": len(events) > 200}


def feedback_from_report(report, mode):
    if mode not in {"N", "D", "T"}:
        raise ValueError("mode must be N, D, or T")
    response = {"schema": "codex-modeling-repair-feedback/v1", "task_id": report.get("task_id"),
                "mode": mode, "received": True}
    if mode == "N":
        return response
    response["diagnostics"] = {key: report.get(key) for key in ("candidate_valid", "compiled", "error")}
    if mode == "D":
        return response
    response["diagnostics"]["executed"] = report.get("executed")
    result = report.get("result")
    if not isinstance(result, dict):
        response.update(trace_summary=None, public_probes=[], probe_note="未取得完整运行轨迹，公开行为探针未执行。")
        return response
    published = pilot.read_json(HERE / "public/probes.json")["tasks"]
    response["trace_summary"] = trace_summary(result)
    response["public_probes"] = [check_probe(result["trace"], probe) for probe in published.get(report.get("task_id"), [])]
    response["probe_note"] = "这些预注册公开探针仅覆盖部分业务行为；全部通过不代表最终完整评分通过。"
    return response


def compile_only(candidate, out):
    """Persist all three layers without instantiating or invoking a runtime."""
    out.mkdir(parents=True, exist_ok=True)
    report = {"task_id": candidate.get("task_id") if isinstance(candidate, dict) else None,
              "candidate_valid": False, "compiled": False, "error": None}
    stage = "candidate_validation"
    try:
        pilot.write_json(out / "candidate.json", candidate)
        pilot.validate_candidate(candidate)
        report["candidate_valid"] = True
        if candidate["status"] == "model":
            canonical = {"schema_version": "aircraft-bounded-input/v1", "semantic_profile": "aircraft-bounded-events/v1", "model": candidate["model"]}
            pilot.write_json(out / "canonical-input.json", canonical)
            stage = "business_import_and_roundtrip"
            business = pilot.roundtrip(pilot.import_bounded_business(canonical), out / "business.json", pilot.BUSINESS)
            stage = "core_lowering_and_roundtrip"
            core = pilot.roundtrip(pilot.lower_bounded(business), out / "core.json", pilot.CORE)
            stage = "plan_compile_and_roundtrip"
            pilot.roundtrip(pilot.compile_bounded(core, operations=pilot.operation_contracts()), out / "plan.json", pilot.PLAN)
            report["compiled"] = True
    except Exception as exc:
        report["error"] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
    pilot.write_json(out / "compile.json", report)
    return report


def run_feedback(candidate_path, out_dir, mode):
    if mode not in {"N", "D", "T"}:
        raise ValueError("mode must be N, D, or T")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError(f"output directory must be empty: {out}")
    internal = out / "internal"
    internal.mkdir()
    shutil.copyfile(candidate_path, internal / "submitted.json")
    try:
        candidate = pilot.read_json(candidate_path)
    except (ValueError, OSError) as exc:
        report = {"task_id": None, "candidate_valid": False, "compiled": False, "executed": False,
                  "result": None, "error": {"stage": "json_parse", "type": type(exc).__name__, "message": str(exc)}}
        if mode != "N":
            pilot.write_json(internal / "parse-error.json", report)
    else:
        if mode == "N":
            report = {"task_id": candidate.get("task_id") if isinstance(candidate, dict) else None}
        elif mode == "D":
            report = compile_only(candidate, internal / "compilation")
        else:
            report = pilot.run_candidate(candidate, internal / "execution", score=False)
    response = feedback_from_report(report, mode)
    pilot.write_json(out / "feedback.json", response)
    return response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=["N", "D", "T"])
    args = parser.parse_args(argv)
    response = run_feedback(args.candidate, args.out, args.mode)
    print(json.dumps(response, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
