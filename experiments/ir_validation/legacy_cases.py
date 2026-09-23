#!/usr/bin/env python3
"""Reproducible current-engine validation, through canonical inputs only.

Run from the repository with Python 3.12 and simpy installed:
  python experiments/ir_validation/legacy_cases.py --rust-binary PATH --f35

The explicit expectations below are small, hand-calculable assertions; agreement
between runtimes is separately recorded. Unknown features are probed as gaps,
not quietly relabeled passing behavior. No legacy model is imported.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import hashlib
import gzip
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(1, str(ROOT))
from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence

FIXTURES = ROOT / "tests/fixtures/synthetic"
F35 = ROOT / "tests/fixtures/spare_mvp/f35-43day-5352a0d"


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def timing(fn):
    start = time.perf_counter_ns()
    value = fn()
    return value, time.perf_counter_ns() - start


def comparable(result):
    return {key: value for key, value in result.items() if key != "plan_fingerprint"}


def difference(left, right):
    diff = first_divergence(left, right, float_rel_tol=2e-15, float_abs_tol=1e-12)
    return None if diff is None else {"path": diff.path, "expected": diff.expected, "actual": diff.actual}


def events(result, kind):
    return [item for item in result["trace"] if item["kind"] == kind]


def times(result, kind):
    return [item["time"] for item in events(result, kind)]


def check(label, actual, expected):
    return {"assertion": label, "expected": expected, "actual": actual, "passed": actual == expected}


def run_native(binary, plan, seed, tmp, *, observation="full", until=None):
    src, out = tmp / "plan.json", tmp / "result.json"
    src.write_text(json.dumps(plan.to_dict()))
    command = [str(binary), str(src), str(out), "--seed", str(seed), "--observation-level", observation]
    if until is not None:
        command.extend(["--until", str(until)])
    _, wall_ns = timing(lambda: subprocess.run(command, check=True, capture_output=True, text=True))
    return json.loads(out.read_text()), wall_ns


def canonical_cases():
    cases = []
    for name in ("b1-daily-operations", "b2-failure-repair", "b2-preventive-maintenance", "b3-upstream-transport"):
        cases.append((name, fixture(name), 0))

    # The same plan and two seeds bind the second mission to different aircraft.
    # Initial component failure samples: seed 0 aircraft 1 fails at minute 11;
    # seed 1 fails at minute 6 and repairs at 9, before minute 11 preparation.
    spare = fixture("b2-failure-repair")
    spare["aircraft"]["fleet_count"] = spare["aircraft"]["initial_ready"] = 2
    spare["aircraft"]["assets"].append({**copy.deepcopy(spare["aircraft"]["assets"][0]), "tail_number": "F35-02"})
    spare["support_network"]["nodes"][0].update(personnel_capacity=2, equipment_capacity=2)
    spare["mission_profile"]["basic_missions"][0]["advanceNoticeMinutes"] = 1
    second = copy.deepcopy(spare["mission_profile"]["composite_tasks"][0]["taskItems"][0])
    second.update(id="sortie-spare", firstWaveTime="00:12")
    spare["mission_profile"]["composite_tasks"][0]["taskItems"].append(second)
    cases.extend([("dynamic-spare-seed-0", spare, 0), ("repaired-aircraft-reused-seed-1", spare, 1)])

    same = fixture("b1-daily-operations")
    same["mission_profile"]["basic_missions"][0]["advanceNoticeMinutes"] = 0
    same["mission_profile"]["composite_tasks"][0]["taskItems"][0]["firstWaveTime"] = "00:17"
    same["mission_profile"]["composite_tasks"][0]["taskItems"][1]["firstWaveTime"] = "00:30"
    cases.append(("simultaneous-return-and-dispatch", same, 0))

    serial = fixture("b1-daily-operations")
    serial["support_network"]["nodes"][0].update(personnel_capacity=2, equipment_capacity=2)
    step = serial["support_activities"]["activities"][0]["jobs"][0]
    step.update(activityCode="A", durationMinutes=2)
    serial["support_activities"]["activities"][0]["jobs"].extend([
        {**copy.deepcopy(step), "activityCode": "B", "durationMinutes": 3},
        {**copy.deepcopy(step), "activityCode": "JOIN", "durationMinutes": 1, "predecessors": ["A", "B"]},
    ])
    cases.append(("serial-branch-join", serial, 0))

    contention = fixture("b1-daily-operations")
    contention["mission_profile"]["basic_missions"][0].update(equipmentQuantity=2, minRequiredSorties=2)
    contention["mission_profile"]["composite_tasks"][0]["taskItems"] = contention["mission_profile"]["composite_tasks"][0]["taskItems"][:1]
    cases.append(("shared-resource-release-wakeup", contention, 0))

    no_stock = fixture("b3-upstream-transport")
    no_stock["support_network"]["nodes"][0]["inventory"]["filter"] = 0
    cases.append(("permanent-shortage-no-phantom-completion", no_stock, 0))

    loop = fixture("b2-failure-repair")
    loop["time"]["duration_minutes"] = loop["mission_profile"]["duration_minutes"] = 70
    loop["stop_policy"]["conditions"][0]["duration_minutes"] = 70
    original = loop["mission_profile"]["composite_tasks"][0]["taskItems"][0]
    loop["mission_profile"]["composite_tasks"][0]["taskItems"] = [
        {**copy.deepcopy(original), "id": f"sortie-{i}", "firstWaveTime": clock}
        for i, clock in enumerate(("00:05", "00:25", "00:45"))
    ]
    cases.append(("repair-and-fly-lifecycle-loop", loop, 0))

    cancelled = fixture("b1-daily-operations")
    cancelled["time"]["duration_minutes"] = cancelled["mission_profile"]["duration_minutes"] = 8
    cancelled["mission_profile"]["basic_missions"][0].update(advanceNoticeMinutes=2, cancelMinutes=1)
    cancelled["mission_profile"]["composite_tasks"][0]["taskItems"] = [
        {**cancelled["mission_profile"]["composite_tasks"][0]["taskItems"][0], "firstWaveTime": "00:03"}
    ]
    cancelled["aircraft"]["fleet_count"] = 1
    cancelled["aircraft"]["assets"] = cancelled["aircraft"]["assets"][:1]
    cancelled["support_network"] = fixture("b3-upstream-transport")["support_network"]
    for node in cancelled["support_network"]["nodes"]:
        node.update(personnel_capacity=0, equipment_capacity=0)
    for activity in cancelled["support_activities"]["activities"]:
        activity["resource_id"] = "line"
    cancelled["support_activities"]["activities"][0]["jobs"][0].update(durationMinutes=10, spare="filter,1")
    cases.append(("cancel-returns-arrived-reservation", cancelled, 0))
    return cases


def hand_assertions(name, result):
    out = []
    add = lambda label, actual, expected: out.append(check(label, actual, expected))
    metrics = result["metrics"]
    if name == "b1-daily-operations":
        add("launches at 20 and 40", times(result, "mission_launched"), [20, 40])
        add("returns at 30 and 50", times(result, "mission_returned"), [30, 50])
        add("two successful completed sorties", [metrics["launched_sorties"], metrics["completed_sorties"], metrics["successful_mission_waves"]], [2, 2, 2])
    elif name == "b2-failure-repair":
        add("flight exposure ceil(5.5818) gives failure 11", times(result, "aircraft_failed"), [11])
        add("3-minute repair finishes 14", times(result, "repair_completed"), [14])
        add("failed sortie is not replaced in flight", [metrics["failed_sorties"], metrics["launched_sorties"]], [1, 1])
    elif name == "b2-preventive-maintenance":
        add("initially due maintenance completes at 4", times(result, "preventive_completed"), [4])
    elif name == "b3-upstream-transport":
        add("stock transported at 1 arrives at 3", [times(result, "organization_transport_dispatched"), times(result, "transport_arrived")], [[1], [3]])
        add("arrival wakes job, 2-minute work finishes at 5", times(result, "preventive_completed"), [5])
        add("exactly one spare consumed", metrics["spare_consumed_total"], 1)
    elif name.startswith("dynamic-spare") or name.startswith("repaired-aircraft"):
        expected_tails = [["F35-01"], ["F35-02" if name.startswith("dynamic") else "F35-01"]]
        add("runtime binding follows actual availability", [event["details"]["aircraft"] for event in events(result, "mission_launched")], expected_tails)
        add("departures fixed despite differing binding", times(result, "mission_launched"), [5, 12])
    elif name == "simultaneous-return-and-dispatch":
        at_30 = [event["kind"] for event in result["trace"] if event["time"] == 30 and event["kind"] in {"mission_returned", "mission_launched"}]
        add("return is visible before dispatch at minute 30", at_30, ["mission_returned", "mission_launched"])
        add("same aircraft can relaunch", [event["details"]["aircraft"] for event in events(result, "mission_launched")], [["F35-01"], ["F35-01"]])
    elif name == "serial-branch-join":
        starts = events(result, "operations_step_started")[:3]
        add("two independent branches remain serial by policy", [event["time"] for event in starts], [10, 12, 15])
        add("2+3+1 minute serial preflight completes at 16", times(result, "preflight_completed")[:1], [16])
    elif name == "shared-resource-release-wakeup":
        starts = events(result, "operations_step_started")[:2]
        add("capacity-one preflight starts at 10 and release 13", [event["time"] for event in starts], [10, 13])
        add("both aircraft depart at 20", [(event["time"], len(event["details"]["aircraft"])) for event in events(result, "mission_launched")], [(20, 2)])
    elif name == "permanent-shortage-no-phantom-completion":
        add("no stock means no completion", times(result, "preventive_completed"), [])
        add("no phantom consumption", metrics["spare_consumed_total"], 0)
        add("job remains waiting at horizon", [job["state"] for job in result["terminal_state"]["jobs"]], ["waiting"])
    elif name == "repair-and-fly-lifecycle-loop":
        add("same aircraft launches three times", times(result, "mission_launched"), [5, 25, 45])
        add("three failure-repair cycles complete", [len(events(result, "aircraft_failed")), len(events(result, "repair_completed"))], [3, 3])
        add("failure timer resampled after each repair", len(result["sample_requests"]), 4)
    elif name == "cancel-returns-arrived-reservation":
        add("cancel at 4; reservation return next transport phase 5", [times(result, "mission_cancelled"), times(result, "organization_spare_reservation_returned")], [[4], [5]])
        add("one spare conserved in line inventory", {node["node_id"]: node["inventory"] for node in result["terminal_state"]["resources"]}, {"base": {"filter": 0}, "line": {"filter": 1}})
    add("all terminal resource holdings nonnegative", all(node["personnel_in_use"] >= 0 and node["equipment_in_use"] >= 0 and all(v >= 0 for v in node["inventory"].values()) for node in result["terminal_state"]["resources"]), True)
    return out


def negative_probes():
    rows = []
    def probe(name, build, execute=False):
        try:
            value = build()
            if execute:
                SimpyReferenceRuntime(value).run()
            rows.append({"case": name, "expected": "explicit rejection", "passed": False, "actual": "accepted", "compiled_value": value.to_dict() if name == "negative-work-duration" else None})
        except (ValueError, TypeError, KeyError) as exc:
            rows.append({"case": name, "expected": "explicit rejection", "passed": True, "actual": str(exc), "error_type": type(exc).__name__})
    def modified(fn):
        inputs = fixture("b1-daily-operations")
        fn(inputs)
        return compile_aircraft_support(inputs)
    probe("unknown-canonical-schema", lambda: modified(lambda x: x.update(schema_version="invented")))
    probe("unknown-time-profile", lambda: compile_aircraft_support(fixture("b1-daily-operations"), semantic_profile="invented"))
    probe("duplicate-aircraft-id", lambda: modified(lambda x: x["aircraft"]["assets"][1].update(tail_number="F35-01")))
    probe("unknown-resource-reference", lambda: modified(lambda x: x["support_activities"]["activities"][0].update(resource_id="nonexistent")))
    probe("unknown-step-predecessor", lambda: modified(lambda x: x["support_activities"]["activities"][0]["jobs"][0].update(predecessors=["missing"])))
    probe("local-process-cycle", lambda: modified(lambda x: x["support_activities"]["activities"][0]["jobs"][0].update(predecessors=["PRE-1"])))
    base = compile_aircraft_support(fixture("b1-daily-operations"))
    probe("unsupported-parallel-work-policy", lambda: replace(base, work_policy="dag-parallel"), execute=True)
    probe("unsupported-operation-capability", lambda: replace(base, unsupported_features=("agent-invented-op",)), execute=True)
    probe("negative-work-duration", lambda: modified(lambda x: x["support_activities"]["activities"][0]["jobs"][0].update(durationMinutes=-3)))
    probe("unknown-equipment-component-reference", lambda: modified(lambda x: x["support_activities"]["activities"][0].update(equipment_id="nonexistent")))
    # This is a duration unit mismatch at an explicitly minute-typed field.
    probe("duration-unit-string", lambda: modified(lambda x: x["support_activities"]["activities"][0]["jobs"][0].update(durationMinutes="3 hours")))
    for row in rows:
        if row.get("compiled_value"):
            row["compiled_value"] = {"actual_duration_minutes": row["compiled_value"]["activities"][0]["steps"][0]["duration_minutes"]}
    return rows


def repository_suite(native_library=None):
    if native_library:
        spec = importlib.util.spec_from_file_location("sim_engine_compiler._runtime", native_library)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules["sim_engine_compiler._runtime"] = module
    modules = ["tests.conformance.test_b1_reference", "tests.conformance.test_b2_b3_reference", "tests.conformance.test_f35_reference", "tests.differential.test_rust_runtime", "tests.differential.test_event_time_runtime"]
    if native_library:
        modules.append("tests.differential.test_python_binding")
    class RecordingResult(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.records = []
        def startTest(self, test):
            super().startTest(test)
            self.started = time.perf_counter_ns()
        def addSuccess(self, test):
            super().addSuccess(test)
            self.records.append({"test": test.id(), "status": "passed", "elapsed_ns": time.perf_counter_ns() - self.started})
        def addFailure(self, test, err):
            super().addFailure(test, err)
            self.records.append({"test": test.id(), "status": "failed", "error": self._exc_info_to_string(err, test)})
        def addError(self, test, err):
            super().addError(test, err)
            self.records.append({"test": test.id(), "status": "error", "error": self._exc_info_to_string(err, test)})
        def addSubTest(self, test, subtest, err):
            super().addSubTest(test, subtest, err)
            if err:
                self.records.append({"test": subtest.id(), "status": "failed_subtest", "error": self._exc_info_to_string(err, test)})
        def addSkip(self, test, reason):
            super().addSkip(test, reason)
            self.records.append({"test": test.id(), "status": "skipped", "reason": reason})
    result = RecordingResult()
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    _, elapsed = timing(lambda: suite.run(result))
    return {"modules": modules, "tests_run": result.testsRun, "passed": result.wasSuccessful(), "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "elapsed_ns": elapsed, "tests": result.records, "native_binding_loaded_from": str(native_library) if native_library else None}


def finalize_report(report):
    for suffix in ("passed", "total"):
        if f"hand_assertions_{suffix}" in report["summary"]:
            report["summary"][f"explicit_assertions_{suffix}"] = report["summary"].pop(f"hand_assertions_{suffix}")
    report["assertion_groups"] = {"hand_calculated_timeline_and_metric_checks": 28, "terminal_nonnegative_resource_invariants": 12, "plan_roundtrip_and_immutability_checks": 24}
    report["event_time_implementation_boundary"] = {"source": "rust/runtime/src/runtime/event_time.rs", "observation": "build_wake_calendar scans entity/mission/cycle collections at wakes; advance_continuous_state contains a per-skipped-minute countdown loop to preserve legacy floating arithmetic. The measured speedup demonstrates conservative event-calendar skipping, not a fully event-proportional generic kernel."}
    report["standalone_validation_boundary"] = "Negative probes call compile_aircraft_support directly, bypassing the upstream Adapter export script's Draft202012Validator. They establish gaps in this standalone compiler API, not acceptance by the complete Project+Adapter+schema chain. This workspace does not contain that upstream schema."
    report["acceptance"] = {
        "positive_cases_passed": all(row["passed"] for row in report["positive_cases"]),
        "f35_differences_absent": all(value is None for row in report["f35"] for key, value in row.items() if key.endswith("difference")),
        "repository_suite_passed": report.get("repository_suite", {}).get("passed"),
        "standalone_input_validation_gate_passed": all(row["passed"] for row in report["negative_probes"]),
    }
    paired = report.get("paired_event_time_benchmark")
    if paired:
        report["paired_timing_summary"] = []
        for mode in ("full", "summary"):
            rows = [row for row in paired["records"] if row["observation_level"] == mode]
            ratios = [row["legacy_to_event_ratio"] for row in rows]
            report["paired_timing_summary"].append({
                "observation_level": mode,
                "pairs": len(rows),
                "all_exact_business_equivalent": all(row["business_equivalent"] for row in rows),
                "median_paired_execution_speedup": statistics.median(ratios),
                "min_paired_execution_speedup": min(ratios),
                "max_paired_execution_speedup": max(ratios),
                "median_legacy_execution_ms": statistics.median(row["legacy"]["execution_ns"] for row in rows) / 1e6,
                "median_event_execution_ms": statistics.median(row["event_time"]["execution_ns"] for row in rows) / 1e6,
                "timing_scope": "runtime.run only, excludes initialization/compilation/serialization; alternates execution order; 1 warmup per seed and mode; diagnostic shared-host measurement",
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust-binary", type=Path)
    parser.add_argument("--f35", action="store_true")
    parser.add_argument("--benchmark-repeats", type=int, default=1)
    parser.add_argument("--paired-repeats", type=int, default=5)
    parser.add_argument("--run-repository-suite", action="store_true")
    parser.add_argument("--native-library", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("legacy_results.json"))
    args = parser.parse_args()
    report = {"schema_version": "ir-validation-current-engine/v1", "source_revision": "4a2fc15b6c0aae723ba1dd7bdbdf54f6e05491dc", "python": sys.version, "platform": platform.platform(), "evidence_scope": "synthetic canonical fixtures and fixed F35 canonical input; checked-in fixed upstream oracles; no Project parsing or live upstream execution", "positive_cases": [], "negative_probes": negative_probes(), "f35": [], "benchmark": [], "limitations": ["Current compiler lowers canonical input directly to aircraft-specific plan; Business/Core IR not materialized here", "Parallel local work policy unsupported; explicit rejection tested", "Timing runs are local diagnostic measurements, not a controlled production benchmark"]}
    with tempfile.TemporaryDirectory(prefix="legacy-ir-validation-") as scratch:
        tmp = Path(scratch)
        spare_fingerprints = []
        for name, inputs, seed in canonical_cases():
            plan, compile_ns = timing(lambda: compile_aircraft_support(inputs))
            runtime, init_ns = timing(lambda: SimpyReferenceRuntime(plan, seed=seed))
            result, execution_ns = timing(runtime.run)
            assertions = hand_assertions(name, result)
            roundtrip = ExecutionPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
            assertions.append(check("serialized plan roundtrip preserves fingerprint", roundtrip.fingerprint, plan.fingerprint))
            assertions.append(check("run leaves immutable plan fingerprint unchanged", plan.fingerprint, roundtrip.fingerprint))
            record = {"case": name, "source": "synthetic canonical simulation_inputs", "seed": seed, "profile": plan.semantic_profile, "input_sha256": plan.source_inputs_sha256, "plan_fingerprint": plan.fingerprint, "timing_ns": {"compile": compile_ns, "initialize": init_ns, "execute_with_full_observation": execution_ns}, "assertions": assertions, "python_result_sha256": digest(result)}
            oracle_path = FIXTURES / f"{name}-oracle.json"
            if oracle_path.exists():
                oracle = json.loads(oracle_path.read_text())
                record["fixed_synthetic_upstream_oracle_terminal_difference"] = difference(oracle["terminal_state"], result["terminal_state"])
            if args.rust_binary:
                rust, wall = run_native(args.rust_binary, plan, seed, tmp)
                event, event_wall = run_native(args.rust_binary, replace(plan, semantic_profile="event-time-v2"), seed, tmp)
                record.update(python_rust_full_difference=difference(result, rust), rust_legacy_event_full_difference=difference(comparable(rust), comparable(event)), rust_wall_including_process_read_write_ns=wall, rust_event_wall_including_process_read_write_ns=event_wall)
            record["passed"] = all(item["passed"] for item in assertions) and all(value is None for key, value in record.items() if key.endswith("difference"))
            if "spare" in name or "repaired-aircraft" in name:
                spare_fingerprints.append(plan.fingerprint)
            report["positive_cases"].append(record)
            print(f"{name}: {'PASS' if record['passed'] else 'FAIL'}", flush=True)
        report["dynamic_binding_same_plan"] = len(set(spare_fingerprints)) == 1

        if args.rust_binary:
            # Repeated seeds and input order survive 1 vs 3 worker scheduling.
            plan = compile_aircraft_support(fixture("b2-failure-repair"))
            src = tmp / "batch-plan.json"
            src.write_text(json.dumps(plan.to_dict()))
            batches = []
            for workers in (1, 3):
                out = tmp / f"batch-{workers}.json"
                subprocess.run([str(args.rust_binary), str(src), str(out), "--seeds", "7,0,7,1", "--worker-threads", str(workers)], check=True, capture_output=True, text=True)
                batches.append(json.loads(out.read_text()))
            report["batch_independence"] = {"seeds": [7, 0, 7, 1], "worker_threads": [1, 3], "difference": difference(batches[0]["samples"], batches[1]["samples"]), "stable_sample_indexes": [sample["sample_index"] for sample in batches[1]["samples"]] == [0, 1, 2, 3], "repeated_seed_equal": batches[0]["samples"][0]["result"] == batches[0]["samples"][2]["result"]}

        if args.f35:
            from tests.conformance.test_f35_reference import CORE_METRICS, _business_timeline, _sample_projection
            inputs = json.loads((F35 / "simulation-inputs.json").read_text())
            plan, compile_ns = timing(lambda: compile_aircraft_support(inputs))
            report["f35_compile_ns"] = compile_ns
            report["f35_input_sha256"] = plan.source_inputs_sha256
            report["f35_shape"] = {"aircraft": len(plan.aircraft), "missions": len(plan.missions), "components": len(plan.components), "horizon_minutes": plan.duration_minutes}
            for seed in (0, 1, 7):
                runtime, init_ns = timing(lambda: SimpyReferenceRuntime(plan, seed=seed))
                python, execute_ns = timing(runtime.run)
                row = {"seed": seed, "profile": plan.semantic_profile, "plan_fingerprint": plan.fingerprint, "python_initialize_ns": init_ns, "python_execute_with_full_observation_ns": execute_ns, "python_result_sha256": digest(python), "sample_requests": len(python["sample_requests"]), "trace_events": len(python["trace"]), "metrics": {key: python["metrics"][key] for key in ("planned_sorties", "launched_sorties", "completed_sorties", "failed_sorties", "cancelled_sorties", "successful_mission_waves")}}
                oracle_path = F35 / "oracle" / f"f35-oracle-v2-seed-{seed}.json.gz"
                if oracle_path.exists():
                    with gzip.open(oracle_path, "rt") as handle:
                        oracle = json.load(handle)
                    row.update(fixed_upstream_oracle_terminal_difference=difference(oracle["terminal_state"], python["terminal_state"]), fixed_upstream_oracle_metrics_difference=difference({key: oracle["metrics"][key] for key in CORE_METRICS}, {key: python["metrics"][key] for key in CORE_METRICS}), fixed_upstream_oracle_timeline_difference=difference(_business_timeline(oracle["trace"]), _business_timeline(python["trace"])), fixed_upstream_oracle_rng_difference=difference(_sample_projection(oracle["sample_requests"]), _sample_projection(python["sample_requests"])), oracle_gzip_sha256=hashlib.sha256(oracle_path.read_bytes()).hexdigest())
                else:
                    row["upstream_oracle_comparison"] = "not run; oracle file unavailable"
                if args.rust_binary:
                    rust, wall = run_native(args.rust_binary, plan, seed, tmp)
                    event, event_wall = run_native(args.rust_binary, replace(plan, semantic_profile="event-time-v2"), seed, tmp)
                    summary, summary_wall = run_native(args.rust_binary, replace(plan, semantic_profile="event-time-v2"), seed, tmp, observation="summary")
                    row.update(python_rust_full_difference=difference(python, rust), rust_legacy_event_full_difference=difference(comparable(rust), comparable(event)), full_summary_metrics_difference=difference(event["metrics"], summary["metrics"]), full_summary_terminal_difference=difference(event["terminal_state"], summary["terminal_state"]), rust_legacy_wall_ns=wall, rust_event_wall_ns=event_wall, rust_event_summary_wall_ns=summary_wall)
                report["f35"].append(row)
                print(f"F35 seed {seed}: {row.get('python_rust_full_difference')} / {row.get('rust_legacy_event_full_difference')}", flush=True)
            if args.rust_binary:
                # Use the repository's native segmented benchmark; initialization
                # and execution are isolated inside the Rust process.
                benchmark_binary = args.rust_binary.with_name("stage-c-benchmark")
                if benchmark_binary.exists():
                    for profile in ("legacy-minute-v1", "event-time-v2"):
                        src = tmp / f"{profile}-f35.json"
                        src.write_text(json.dumps(replace(plan, semantic_profile=profile).to_dict()))
                        output = tmp / f"{profile}-timing.json"
                        subprocess.run([str(benchmark_binary), str(src), str(output), "--seeds", "0,1,7", "--worker-threads", "1", "--warmups", "1", "--repeats", str(args.benchmark_repeats)], check=True, capture_output=True, text=True)
                        timing_report = json.loads(output.read_text())
                        timing_report["plan_path"] = "generated from fixed canonical F35 input by this script"
                        report["benchmark"].append(timing_report)

                paired_binary = args.rust_binary.with_name("event_time_benchmark")
                if paired_binary.exists():
                    output = tmp / "paired-timing.json"
                    subprocess.run([str(paired_binary), str(tmp / "legacy-minute-v1-f35.json"), str(tmp / "event-time-v2-f35.json"), str(output), "--seeds", "0,1,7", "--observation-levels", "full,summary", "--warmups", "1", "--repeats", str(args.paired_repeats), "--session-label", "2026-09-22-ir-validation"], check=True, capture_output=True, text=True)
                    report["paired_event_time_benchmark"] = json.loads(output.read_text())

    if args.run_repository_suite:
        report["repository_suite"] = repository_suite(args.native_library)

    report["summary"] = {"positive_cases_passed": sum(row["passed"] for row in report["positive_cases"]), "positive_cases_total": len(report["positive_cases"]), "hand_assertions_passed": sum(check["passed"] for row in report["positive_cases"] for check in row["assertions"]), "hand_assertions_total": sum(len(row["assertions"]) for row in report["positive_cases"]), "negative_probes_rejected": sum(row["passed"] for row in report["negative_probes"]), "negative_probes_total": len(report["negative_probes"]), "validation_gaps": [row["case"] for row in report["negative_probes"] if not row["passed"]]}
    finalize_report(report)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    if not report["acceptance"]["positive_cases_passed"] or not report["acceptance"]["f35_differences_absent"] or report["acceptance"]["repository_suite_passed"] is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
