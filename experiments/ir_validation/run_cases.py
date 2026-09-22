#!/usr/bin/env python3
"""Run hand-expected, cross-engine and model-change acceptance checks.

Run from the repository root:
  python experiments/ir_validation/run_cases.py

No expected result is derived from an engine. Differential equality is an
additional check, not the source of the hand-calculated acceptance criteria.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, is_dataclass, FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cases import make_cases, rng_model, model, job, repair, resource
import generic
import reference


def serializable(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    return value


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serializable(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def digest(value):
    return sha256(json.dumps(serializable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def semantic(result, *, exclude_fingerprint=False, exclude_trace=False):
    ignored = {"diagnostics"}
    if exclude_fingerprint:
        ignored.add("fingerprint")
    if exclude_trace:
        ignored.add("trace")
    return {key: value for key, value in result.items() if key not in ignored}


def same(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, received {actual!r}")


class Suite:
    def __init__(self, output, rust):
        self.output = output
        self.rust = rust
        self.rows = []
        self.engine_runs = {"python_reference": 0, "python_indexed": 0, "rust": 0}

    def rust_run(self, plan, seeds, *, trace=True, threads=1):
        request = {"plan": serializable(plan), "seeds": list(seeds), "repeats": 1, "threads": threads, "trace": trace}
        completed = subprocess.run([str(self.rust)], input=json.dumps(request), text=True, capture_output=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"Rust exited {completed.returncode}: {completed.stderr.strip()} {completed.stdout[:600]}")
        value = json.loads(completed.stdout)
        results = value["results"]
        same(len(results), len(seeds), "Rust result count")
        self.engine_runs["rust"] += len(results)
        return results

    def all_engines(self, plan, seeds=(0,), *, trace=True, threads=1):
        by_seed = []
        rust_results = self.rust_run(plan, seeds, trace=trace, threads=threads)
        for position, seed in enumerate(seeds):
            py = generic.run_plan(plan, seed=seed, trace=trace)
            ref = reference.run_plan(plan, seed=seed, trace=trace)
            self.engine_runs["python_indexed"] += 1
            self.engine_runs["python_reference"] += 1
            same(semantic(py), semantic(ref), f"Python indexed/reference equality seed={seed}")
            same(semantic(rust_results[position]), semantic(ref), f"Rust/reference equality seed={seed}")
            by_seed.append({"python_reference": ref, "python_indexed": py, "rust": rust_results[position]})
        return by_seed

    def check(self, id, description, function):
        try:
            detail = function() or {}
            row = {"id": id, "description": description, "status": "passed", **detail}
        except Exception as error:
            row = {"id": id, "description": description, "status": "failed", "error": f"{type(error).__name__}: {error}", "stack": traceback.format_exc()}
        self.rows.append(row)
        print(f"{row['status']:6} {id}", flush=True)
        write_json(self.output / "case_results.json", self.report())

    def report(self):
        return {"profile": "ir-native-event-v1", "scope": "Synthetic new-profile acceptance; does not establish legacy spare_mvp equivalence.",
                "count": len(self.rows), "passed": sum(r["status"] == "passed" for r in self.rows),
                "failed": sum(r["status"] != "passed" for r in self.rows), "engine_runs": self.engine_runs,
                "cases": self.rows}

    def compile(self, raw, id):
        business = generic.compile_business(raw)
        core = generic.lower_core(business)
        plan = generic.compile_plan(core)
        prefix = self.output / "cases" / id
        write_json(prefix / "business.json", business)
        write_json(prefix / "core.json", core)
        write_json(prefix / "plan.json", plan)
        write_json(prefix / "source.json", raw)
        return plan, {"source_sha256": digest(raw), "business_sha256": digest(business),
                      "core_sha256": digest(core), "plan_sha256": digest(plan),
                      "plan_fingerprint": plan.to_dict()["fingerprint"]}

    def hand_case(self, case):
        plan, hashes = self.compile(case["business"], case["id"])
        write_json(self.output / "cases" / case["id"] / "expected.json", case["expected"])
        results = self.all_engines(plan)[0]
        p = plan.to_dict()
        for engine, result in results.items():
            check_expected(p, result, case["expected"])
            write_json(self.output / "cases" / case["id"] / f"{engine}.json", result)
        summary = self.all_engines(plan, trace=False)[0]
        for engine, result in summary.items():
            same(result["trace"], [], f"{engine} summary trace omitted")
            same(semantic(result, exclude_trace=True), semantic(results[engine], exclude_trace=True), f"{engine} observation isolation")
        return {**hashes, "engines": list(results), "hand_expectations": case["expected"], "summary_full_equal": True}


def check_expected(plan, result, expected):
    process_indices = {entry["id"]: i for i, entry in enumerate(plan["processes"])}
    assets = [entry["id"] for entry in plan["assets"]]
    resources = {entry["id"]: i for i, entry in enumerate(plan["resources"])}
    for name, assertions in expected["processes"].items():
        index = process_indices[name]
        for key, value in assertions.items():
            if key == "selected_id":
                chosen = result["selected"][index]
                actual = None if chosen < 0 else assets[chosen]
            else:
                actual = result[key][index]
            same(actual, value, f"{name}.{key}")
    for name, value in expected["resources"].items():
        same(result["resources"][resources[name]], value, f"resource {name}")
    for name, value in expected["assets"].items():
        same(result["assets"][assets.index(name)], value, f"asset {name}")
    for event in expected["trace_contains"]:
        if event not in result["trace"]:
            raise AssertionError(f"Missing expected event {event!r}")
    for event in expected["trace_absent"]:
        if event in result["trace"]:
            raise AssertionError(f"Unexpected forbidden event {event!r}")
    previous = -1
    for event in expected["trace_order"]:
        current = result["trace"].index(event)
        if current <= previous:
            raise AssertionError(f"Incorrect event order for {event!r}")
        previous = current
    # Conservation/ownership checks are independent of any exact expected times.
    if any(value < 0 for value in result["resources"]):
        raise AssertionError("Negative resource quantity")
    for index, resource_spec in enumerate(plan["resources"]):
        if resource_spec["kind"] == "capacity":
            held = sum(dict(spec["needs"]).get(index, 0) for j, spec in enumerate(plan["processes"]) if result["status"][j] == 2)
            same(result["resources"][index] + held, resource_spec["initial"], f"Capacity conservation for {resource_spec['id']}")
    for asset_index, owner in enumerate(result["owners"]):
        if owner >= 0:
            same(result["status"][owner], 2, "Owned asset has running owner")
            same(result["selected"][owner], asset_index, "Asset owner and selected index agree")


def metamorphic_rng(suite):
    seeds = (0, 1, 7, 2026, 4294967295)
    outcomes = {}
    for variant, blocked, unrelated in [("baseline", False, False), ("reordered_plus_irrelevant", False, True), ("retry", True, False)]:
        plan, _ = suite.compile(rng_model(blocked=blocked, unrelated=unrelated), "M01_rng_" + variant)
        index = [p["id"] for p in plan.to_dict()["processes"]].index("random-job")
        rows = suite.all_engines(plan, seeds=seeds)
        outcomes[variant] = []
        for seed, row in zip(seeds, rows):
            result = row["python_reference"]
            sampled = result["sampled"][index]
            same(result["started"][index], 3 if blocked else 0, f"RNG variant {variant} start")
            same(result["finished"][index], sampled + (3 if blocked else 0), f"RNG variant {variant} finish")
            requests = [entry for entry in result["trace"] if entry[1:3] == ["random", "random-job"]]
            same(len(requests), 1, "One sample only after acquisition, not on retry")
            outcomes[variant].append({"seed": seed, "duration": sampled})
        write_json(suite.output / "cases" / ("M01_rng_" + variant) / "results.json", rows)
    same(outcomes["baseline"], outcomes["reordered_plus_irrelevant"], "Stable IDs survive unrelated asset/process insertion")
    same(outcomes["baseline"], outcomes["retry"], "Waiting retries do not advance random streams")
    return {"seeds": list(seeds), "outcomes": outcomes, "limitation": "Toy uint32 RNG; this is a reproducibility check, not distribution validation."}


def metamorphic_patch(suite):
    raw = deepcopy(make_cases()[0]["business"])
    old_plan, old_hashes = suite.compile(raw, "M02_patch_v1")
    old_before = suite.all_engines(old_plan)[0]
    old_bytes = json.dumps(old_plan.to_dict(), sort_keys=True)
    try:
        old_plan.revision = "illegal-in-place-edit"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Execution Plan permits in-place revision mutation")
    raw["revision"] = "v2"
    raw["missions"][0]["eligible"] = ["A0"]
    new_plan, new_hashes = suite.compile(raw, "M02_patch_v2")
    new_results = suite.all_engines(new_plan)[0]
    same(new_results["python_reference"]["started"][0], 4, "Candidate relationship patch waits for A0 repair")
    same(new_results["python_reference"]["finished"][0], 6, "Candidate relationship patch completion")
    same(new_results["python_reference"]["selected"][0], 0, "Candidate relationship patch changes aircraft binding")
    same(json.dumps(old_plan.to_dict(), sort_keys=True), old_bytes, "Old plan unchanged after source edit")
    old_after = suite.all_engines(old_plan)[0]
    same(old_before, old_after, "Old revision results remain unchanged after new compilation")
    if old_hashes["plan_fingerprint"] == new_hashes["plan_fingerprint"]:
        raise AssertionError("Changing candidate relation did not change fingerprint")
    # Runtime state is private across concurrent Python samples; Rust order is
    # checked with three workers and duplicate seeds, not inferred from a mean.
    seeds = [7, 0, 7, 2026]
    serial = suite.all_engines(new_plan, seeds=seeds)
    with ThreadPoolExecutor(max_workers=3) as pool:
        concurrent = list(pool.map(lambda seed: generic.run_plan(new_plan, seed=seed), seeds))
    suite.engine_runs["python_indexed"] += len(seeds)
    parallel_rust = suite.rust_run(new_plan, seeds, threads=3)
    for index, result in enumerate(serial):
        same(semantic(concurrent[index]), semantic(result["python_indexed"]), "Concurrent Python state isolation")
        same(semantic(parallel_rust[index]), semantic(result["rust"]), "Rust thread count/order isolation")
    write_json(suite.output / "cases" / "M02_patch_v2" / "results.json", new_results)
    return {"old_plan_fingerprint": old_hashes["plan_fingerprint"], "new_plan_fingerprint": new_hashes["plan_fingerprint"],
            "old_flight": {"aircraft": "A1", "start": 1, "finish": 3}, "new_flight": {"aircraft": "A0", "start": 4, "finish": 6},
            "shared_plan_private_run_state": True, "rust_threads": [1, 3], "seeds_in_requested_order": seeds,
            "limitation": "New revision uses full deterministic recompilation; no incremental compiler or in-flight state migration is claimed."}


def metamorphic_rule_relationship(suite):
    base = deepcopy(make_cases()[8]["business"])
    old, _ = suite.compile(base, "M03_precedence_v1")
    old_result = suite.all_engines(old)[0]["python_reference"]
    base["revision"] = "v2"
    base["missions"][1]["after"] = ["cut"]
    new, _ = suite.compile(base, "M03_precedence_v2")
    new_result = suite.all_engines(new)[0]["python_reference"]
    same(old_result["finished"][2], 4, "Parallel join completion")
    same(new_result["finished"][2], 6, "Relationship patch serializes work")
    same(len(new.to_dict()["processes"]), len(old.to_dict()["processes"]), "Rule change reuses finite process table")
    return {"parallel_completion": 4, "serial_completion": 6, "edited_relation": "paint.after = ['cut']", "parameter_only_edit": False}


def metamorphic_domain(suite):
    production = deepcopy(make_cases()[12]["business"])
    aircraft = deepcopy(production)
    aircraft["domain"] = "aircraft"
    aircraft["fleet"] = aircraft.pop("machines")
    aircraft["missions"] = aircraft.pop("jobs")
    aircraft["maintenance"] = aircraft.pop("outages")
    first, _ = suite.compile(production, "M04_domain_production")
    second, _ = suite.compile(aircraft, "M04_domain_aircraft")
    first_results = suite.all_engines(first)[0]
    second_results = suite.all_engines(second)[0]
    for engine in first_results:
        same(semantic(first_results[engine], exclude_fingerprint=True), semantic(second_results[engine], exclude_fingerprint=True), f"{engine} domain mapping equivalence")
    return {"equal_except_identity_fingerprint": True, "limitation": "Two domain vocabularies currently share the same finite task/asset/resource grammar; richer domain expressiveness remains unproven."}


def validation_cases(suite):
    base = model("validation", assets=[{"id": "A"}], resources=[resource("crew")], work=[job("one", 1, eligible=["A"], needs={"crew": 1}), job("two", 1, after=["one"])])
    variants = []
    def edit(id, description, function):
        raw = deepcopy(base)
        function(raw)
        variants.append((id, description, raw))
    edit("V01_profile", "Unknown semantic profile rejects", lambda x: x.update(profile="unknown-profile"))
    edit("V02_units", "Unrecognized time units reject", lambda x: x.update(time_unit="minutes"))
    edit("V03_reference", "Missing asset reference rejects", lambda x: x["missions"][0].update(eligible=["missing"]))
    edit("V04_negative", "Negative duration rejects", lambda x: x["missions"][0].update(duration=[-1, 2]))
    edit("V05_unsupported_rule", "Unsupported dispatch policy rejects", lambda x: x.update(rules={"selection": "magic-best"}))
    edit("V06_cyclic_dependencies", "Local process DAG cycle rejects", lambda x: x["missions"][0].update(after=["two"]))
    edit("V07_missing_resource", "Missing capacity/stock reference rejects", lambda x: x["missions"][0].update(needs={"missing": 1}))
    edit("V08_duplicate_identity", "Duplicate asset identity rejects", lambda x: x["fleet"].append({"id": "A"}))
    edit("V09_impossible_capacity", "Capacity demand above total rejects", lambda x: x["missions"][0].update(needs={"crew": 2}))
    edit("V10_zero_recurrence", "Zero-delay recurrence rejects", lambda x: x["missions"][0].update(repeat_delay=0))
    edit("V11_fractional_clock", "Fractional clock rejects instead of rounding", lambda x: x.update(horizon=1.5))
    edit("V12_unknown_business_operation", "Invented business operation/key rejects", lambda x: x["missions"][0].update(operation="teleport"))
    edit("V13_boolean_clock", "Boolean clock rejects instead of integer coercion", lambda x: x.update(horizon=True))
    edit("V14_reversed_duration", "Reversed duration range rejects", lambda x: x["missions"][0].update(duration=[3, 1]))
    for id, description, raw in variants:
        def run(raw=raw, id=id):
            write_json(suite.output / "rejections" / f"{id}.json", raw)
            try:
                generic.build_plan(raw)
            except (ValueError, TypeError) as error:
                return {"diagnostic": str(error), "input_sha256": digest(raw)}
            raise AssertionError("Invalid input was accepted")
        suite.check(id, description, run)

    def unknown_core_operation():
        raw = deepcopy(base)
        raw["maintenance"] = [repair("fault", "A", 2, 1)]
        core = generic.lower_core(generic.compile_business(raw))
        core["events"][0]["op"] = "teleport"
        write_json(suite.output / "rejections" / "V15_unknown_core_operation.json", core)
        try:
            generic.compile_plan(core)
        except (ValueError, TypeError) as error:
            if "operation" not in str(error):
                raise AssertionError(f"Expected operation diagnostic, received {error}")
            return {"diagnostic": str(error), "input_sha256": digest(core)}
        raise AssertionError("Unknown Core operation was accepted")
    suite.check("V15_unknown_core_operation", "An agent-invented Core operation fails deterministic compilation", unknown_core_operation)

    def unknown_backend_operation():
        raw = deepcopy(base)
        raw["maintenance"] = [repair("fault", "A", 2, 1)]
        plan = generic.build_plan(raw).to_dict()
        plan["events"][0]["op"] = "teleport"
        del plan["fingerprint"]
        plan["fingerprint"] = digest(plan)
        write_json(suite.output / "rejections" / "V16_unknown_backend_operation.json", plan)
        completed = subprocess.run([str(suite.rust)], input=json.dumps({"plan": plan, "seeds": [0]}), text=True, capture_output=True, check=False)
        if completed.returncode == 0:
            raise AssertionError("Rust backend accepted an unsupported operation with a valid fingerprint")
        return {"diagnostic": completed.stderr.strip() or completed.stdout.strip(), "input_sha256": digest(plan), "recomputed_valid_fingerprint": True}
    suite.check("V16_unknown_backend_operation", "Rust loader rejects unsupported operation even after a valid plan hash is recomputed", unknown_backend_operation)

    def corrupted_plan():
        plan = generic.build_plan(base).to_dict()
        plan["revision"] = "tampered-without-new-fingerprint"
        completed = subprocess.run([str(suite.rust)], input=json.dumps({"plan": plan, "seeds": [0]}), text=True, capture_output=True, check=False)
        if completed.returncode == 0:
            raise AssertionError("Rust backend accepted a corrupted plan fingerprint")
        return {"diagnostic": completed.stderr.strip() or completed.stdout.strip(), "input_sha256": digest(plan)}
    suite.check("V17_corrupted_plan_fingerprint", "Mutating a serialized plan without recomputing its fingerprint fails loading", corrupted_plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results")
    parser.add_argument("--rust", "--binary", dest="rust", type=Path, default=HERE / "rust_kernel" / "target" / "release" / "ir-validation-kernel")
    args = parser.parse_args()
    if not args.rust.is_file():
        parser.error(f"Rust runtime is missing: {args.rust}; build experiments/ir_validation/rust_kernel with cargo build --release")
    suite = Suite(args.output.resolve(), args.rust.resolve())
    for case in make_cases():
        suite.check(case["id"], case["description"], lambda case=case: suite.hand_case(case))
    suite.check("M01_rng_stable_identity", "Random sample identity survives dense-index changes, unrelated work and waiting retries", lambda: metamorphic_rng(suite))
    suite.check("M02_model_version_isolation", "Candidate relationship changes create a new version while old plan/state and threaded sample results stay isolated", lambda: metamorphic_patch(suite))
    suite.check("M03_rule_relationship_edit", "Changing dependency edges changes parallel/serial behavior, beyond tuning parameters", lambda: metamorphic_rule_relationship(suite))
    suite.check("M04_second_domain_lowering", "Two domain mappings produce identical generic runtime behavior", lambda: metamorphic_domain(suite))
    validation_cases(suite)
    report = suite.report()
    source_paths = [HERE / "cases.py", HERE / "run_cases.py", HERE / "generic.py",
                    HERE / "validation.py", HERE / "reference.py", HERE / "SPEC.md",
                    HERE / "rust_kernel" / "src" / "main.rs",
                    *sorted((HERE / "domain_packages").glob("*.py"))]
    report["source_files_sha256"] = {str(path.relative_to(HERE)): sha256(path.read_bytes()).hexdigest() for path in source_paths}
    report["rust_binary_sha256"] = sha256(args.rust.read_bytes()).hexdigest()
    write_json(args.output / "case_results.json", report)
    print(json.dumps({"passed": report["passed"], "failed": report["failed"], "engine_runs": report["engine_runs"]}, ensure_ascii=False))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
