#!/usr/bin/env python3
"""Deterministic generated-model differential checks and invalid-input probes."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import subprocess

import generic
import reference


def semantic(result):
    return {key: value for key, value in result.items() if key != "diagnostics"}


def generated_model(index):
    rng = random.Random(27092026 + index)
    domain = "aircraft" if index % 2 == 0 else "production"
    assets = [{"id": f"asset-{n}"} for n in range(rng.randrange(5))]
    resources = [{"id": f"capacity-{n}", "kind": "capacity", "initial": rng.randint(1, 3)}
                 for n in range(rng.randrange(1, 4))]
    resources.append({"id": "stock", "kind": "stock", "initial": rng.randrange(4)})
    processes = []
    for n in range(rng.randint(1, 8)):
        lower = rng.randrange(4)
        eligible = rng.sample([item["id"] for item in assets], rng.randint(0, len(assets)))
        process = {
            "id": f"work-{n}", "release": None if rng.random() < .1 else rng.randrange(11),
            "duration": [lower, lower + rng.randrange(4)], "eligible": eligible,
            "needs": {item["id"]: 1 for item in resources if rng.random() < .25},
            "after": [item["id"] for item in processes if rng.random() < .13],
        }
        if rng.random() < .25:
            process["repeat_delay"] = rng.randint(1, 5)
        processes.append(process)
    maintenance = []
    for asset in assets:
        if rng.random() < .7:
            outage = {"id": "outage-" + asset["id"], "asset": asset["id"],
                      "at": rng.randrange(10), "duration": [0, rng.randrange(1, 4)], "needs": {}}
            if rng.random() < .5:
                outage["repeat_every"] = rng.randrange(5, 13)
            maintenance.append(outage)
    arrivals = [{"id": f"arrival-{n}", "time": rng.randrange(25), "resource": "stock", "quantity": rng.randrange(1, 5)}
                for n in range(rng.randrange(4))]
    model = {"schema": "business/v1", "profile": "ir-native-event-v1", "domain": domain,
             "model_id": f"generated-{index}", "revision": "1", "time_unit": "tick",
             "horizon": rng.randrange(1, 41), "resources": resources, "arrivals": arrivals}
    model["fleet" if domain == "aircraft" else "machines"] = assets
    model["missions" if domain == "aircraft" else "jobs"] = processes
    model["maintenance" if domain == "aircraft" else "outages"] = maintenance
    return model


def check_invariants(plan, result):
    data = plan.to_dict()
    processes = data["processes"]
    lookup = {p["id"]: p for p in processes}
    for i, owner in enumerate(result["owners"]):
        assert owner == -1 or (result["status"][owner] == 2 and result["selected"][owner] == i)
    for i, resource in enumerate(data["resources"]):
        assert result["resources"][i] >= 0
        if resource["kind"] == "capacity":
            occupied = sum(dict(process["needs"]).get(i, 0) for j, process in enumerate(processes) if result["status"][j] == 2)
            assert result["resources"][i] + occupied == resource["initial"]
        else:
            incoming = sum(event["value"] for event in data["events"] if event["op"] == "add_stock" and event["target"] == i and event["time"] <= data["horizon"])
            consumed = sum(dict(lookup[row[2]]["needs"]).get(i, 0) for row in result["trace"] if row[1] == "start")
            assert result["resources"][i] == resource["initial"] + incoming - consumed
    for i, process in enumerate(processes):
        assert result["completed"][i] == sum(row[1] == "complete" and row[2] == process["id"] for row in result["trace"])


def invalid_probes():
    base = {"schema": "business/v1", "profile": "ir-native-event-v1", "domain": "production",
            "model_id": "invalid-probe", "revision": "1", "time_unit": "tick", "horizon": 10,
            "machines": [{"id": "A"}], "resources": [{"id": "R", "kind": "capacity", "initial": 1}],
            "jobs": [{"id": "work", "release": 0, "duration": [1, 2], "eligible": ["A"], "needs": {"R": 1}, "after": []}]}
    variations = []
    def probe(name, mutate):
        raw = deepcopy(base)
        mutate(raw)
        variations.append((name, raw))
    probe("unknown_business_operation", lambda r: r["jobs"][0].update(operation="invented"))
    probe("invalid_units", lambda r: r.update(time_unit="minute"))
    probe("unsupported_profile", lambda r: r.update(profile="legacy-minute-v1"))
    probe("unknown_candidate", lambda r: r["jobs"][0].update(eligible=["missing"]))
    probe("unknown_resource", lambda r: r["jobs"][0].update(needs={"missing": 1}))
    probe("unknown_predecessor", lambda r: r["jobs"][0].update(after=["missing"]))
    probe("cyclic_predecessor", lambda r: r["jobs"][0].update(after=["work"]))
    probe("negative_duration", lambda r: r["jobs"][0].update(duration=[-1, 2]))
    probe("duration_unit_string", lambda r: r["jobs"][0].update(duration=["2h", "2h"]))
    probe("boolean_time", lambda r: r.update(horizon=True))
    probe("impossible_capacity", lambda r: r["jobs"][0].update(needs={"R": 2}))
    probe("unknown_rule", lambda r: r.update(rules={"selection": "llm_magic"}))
    probe("zero_repeat_delay", lambda r: r["jobs"][0].update(repeat_delay=0))
    probe("duplicate_asset", lambda r: r["machines"].append({"id": "A"}))
    probe("integer_exceeds_backend_int64", lambda r: r.update(horizon=2**63))
    results = []
    for name, raw in variations:
        try:
            generic.build_plan(raw)
        except (ValueError, TypeError, KeyError) as error:
            results.append({"case": name, "rejected": True, "error_type": type(error).__name__, "message": str(error)})
        else:
            results.append({"case": name, "rejected": False})
    return results


def core_adversarial(binary=None):
    """An aborted process restarts before its stale completion becomes due."""
    raw = {"schema": "business/v1", "profile": "ir-native-event-v1", "domain": "production",
           "model_id": "core-generation-restart", "revision": "1", "time_unit": "tick", "horizon": 11,
           "machines": [{"id": "A"}], "resources": [{"id": "R", "kind": "capacity", "initial": 1}],
           "jobs": [{"id": "work", "release": 0, "duration": [10, 10], "eligible": ["A"], "needs": {"R": 1}}]}
    core = generic.lower_core(generic.compile_business(raw))
    core["events"] = [
        {"id": "abort", "time": 2, "op": "set_state", "target": "A", "value": 1, "trigger": None, "repeat_every": None},
        {"id": "reactivate", "time": 3, "op": "set_state", "target": "A", "value": 0, "trigger": "work", "repeat_every": None},
    ]
    core["source_map"].update({"event:abort": "/core-test/events/0", "event:reactivate": "/core-test/events/1"})
    variants = []
    for horizon, status, finished, owner, available in [(11, 2, -1, 0, 0), (14, 3, 13, -1, 1)]:
        value = deepcopy(core)
        value["horizon"] = horizon
        plan = generic.compile_plan(value)
        expected = reference.run_plan(plan)
        actual = generic.run_plan(plan)
        assert semantic(actual) == semantic(expected)
        assert actual["status"] == [status] and actual["generation"] == [1]
        assert actual["started"] == [3] and actual["finished"] == [finished]
        assert actual["owners"] == [owner] and actual["resources"] == [available]
        assert not any(row[:3] == [10, "complete", "work"] for row in actual["trace"])
        if binary:
            output = subprocess.run([str(binary.resolve())], input=json.dumps({"plan": plan.to_dict(), "seeds": [0], "trace": True}), text=True, capture_output=True, check=True)
            rust = json.loads(output.stdout)["results"][0]
            assert semantic(rust) == semantic(expected)
        variants.append({"horizon": horizon, "passed": True, "status": actual["status"], "generation": actual["generation"], "trace": actual["trace"]})

    mutations = {
        "unknown_core_operation": lambda c: c["events"][0].update(op="invented_operation"),
        "invalid_core_unit": lambda c: c.update(time_unit="seconds"),
        "invalid_core_target": lambda c: c["events"][0].update(target="missing"),
        "invalid_core_trigger": lambda c: c["events"][0].update(trigger="missing"),
        "cyclic_core_processes": lambda c: c["processes"][0].update(after=["work"]),
        "zero_core_recurrence": lambda c: c["events"][0].update(repeat_every=0),
        "stock_operation_on_capacity": lambda c: c["events"][0].update(op="add_stock", target="R", value=1),
    }
    probes = []
    for name, mutate in mutations.items():
        value = deepcopy(core)
        mutate(value)
        try:
            generic.compile_plan(value)
        except (ValueError, TypeError, KeyError) as error:
            probes.append({"case": name, "rejected": True, "message": str(error)})
        else:
            probes.append({"case": name, "rejected": False})
    backend_probes = []
    if binary:
        mutations = {
            "unknown_plan_operation": lambda p: p["events"][0].update(op="invented_operation"),
            "invalid_plan_unit": lambda p: p.update(time_unit="seconds"),
            "unsupported_backend_profile": lambda p: p.update(profile="legacy-minute-v1"),
            "invalid_dense_target": lambda p: p["events"][0].update(target=999),
            "invalid_dense_candidate": lambda p: p["processes"][0].update(candidates=[999]),
            "cyclic_dense_process": lambda p: (p["processes"][0].update(after=[0]), p.update(successors=[[0]])),
            "integer_exceeds_int64": lambda p: p.update(horizon=2**63),
            "unknown_plan_field": lambda p: p.update(arbitrary_code="execute()"),
        }
        for name, mutate in mutations.items():
            value = generic.compile_plan(core).to_dict()
            mutate(value)
            del value["fingerprint"]
            value["fingerprint"] = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            output = subprocess.run([str(binary.resolve())], input=json.dumps({"plan": value, "seeds": [0]}), text=True, capture_output=True)
            backend_probes.append({"case": name, "rejected": output.returncode != 0,
                                   "exit_code": output.returncode, "message": output.stderr.strip()})
    numeric = []
    edge = deepcopy(raw)
    edge["model_id"] = "int64-horizon-boundary"
    edge["horizon"] = 2**63 - 1
    edge["jobs"][0]["release"] = 2**63 - 2
    boundary_plan = generic.build_plan(edge)
    expected = reference.run_plan(boundary_plan)
    actual = generic.run_plan(boundary_plan)
    assert semantic(actual) == semantic(expected)
    assert actual["status"] == [2] and actual["finished"] == [-1]
    if binary:
        output = subprocess.run([str(binary.resolve())], input=json.dumps({"plan": boundary_plan.to_dict(), "seeds": [0]}), text=True, capture_output=True, check=True)
        assert semantic(json.loads(output.stdout)["results"][0]) == semantic(expected)
    numeric.append({"case": "completion_beyond_int64_horizon", "passed": True})

    stock = deepcopy(raw)
    stock["model_id"] = "stock-overflow"
    stock["jobs"] = []
    stock["resources"] = [{"id": "stock", "kind": "stock", "initial": 2**63 - 1}]
    stock["arrivals"] = [{"id": "arrival", "time": 0, "resource": "stock", "quantity": 1}]
    overflow_plan = generic.build_plan(stock)
    for name, execute in [("reference", reference.run_plan), ("indexed", generic.run_plan)]:
        try:
            execute(overflow_plan)
        except RuntimeError as error:
            numeric.append({"case": "stock_overflow", "backend": name, "rejected": True, "message": str(error)})
        else:
            raise AssertionError(f"{name} accepted stock overflow")
    if binary:
        output = subprocess.run([str(binary.resolve())], input=json.dumps({"plan": overflow_plan.to_dict(), "seeds": [0]}), text=True, capture_output=True)
        assert output.returncode != 0
        numeric.append({"case": "stock_overflow", "backend": "rust", "rejected": True, "message": output.stderr.strip()})
    return {"scope": "Direct Core IR operations, not Business IR editing capability.", "generation_reuse": variants,
            "core_probes": probes, "backend_probes": backend_probes, "numeric_boundaries": numeric}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=int, default=100)
    parser.add_argument("--rust", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("adversarial_results.json"))
    args = parser.parse_args()
    records = []
    failures = []
    for index in range(args.models):
        raw = generated_model(index)
        try:
            plan = generic.build_plan(raw)
            inputs_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            expected_batch = []
            seeds = [0, 17, 0xFFFFFFFF]
            for seed in seeds:
                expected = reference.run_plan(plan, seed=seed, trace=True)
                actual = generic.run_plan(plan, seed=seed, trace=True)
                assert semantic(actual) == semantic(expected), "optimized Python differs from independent reference"
                check_invariants(plan, actual)
                no_trace = generic.run_plan(plan, seed=seed, trace=False)
                assert {k: v for k, v in semantic(no_trace).items() if k != "trace"} == {k: v for k, v in semantic(actual).items() if k != "trace"}, "observation changes state"
                assert no_trace["trace"] == []
                expected_batch.append(expected)
            if args.rust:
                request = {"plan": plan.to_dict(), "seeds": seeds, "trace": True, "threads": 2}
                process = subprocess.run([str(args.rust.resolve())], input=json.dumps(request), text=True, capture_output=True, check=True)
                rust = json.loads(process.stdout)
                # Rust batch envelope is normalized after the final API lands.
                values = rust["results"] if isinstance(rust, dict) and "results" in rust else rust
                if isinstance(values, dict) and "samples" in values:
                    values = values["samples"]
                for actual, expected in zip(values, expected_batch, strict=True):
                    value = actual.get("result", actual) if isinstance(actual, dict) else actual
                    assert semantic(value) == semantic(expected), "Rust differs from independent reference"
            records.append({"model": raw["model_id"], "domain": raw["domain"], "input_sha256": inputs_hash,
                            "plan_fingerprint": plan.to_dict()["fingerprint"], "seeds": seeds, "passed": True})
        except Exception as error:
            failures.append({"model": raw["model_id"], "error_type": type(error).__name__, "message": str(error), "business": raw})
    probes = invalid_probes()
    core_checks = core_adversarial(args.rust)
    results = {"schema": "ir-validation-adversarial/v1", "model_count": args.models, "model_passes": len(records),
               "differential_samples": len(records) * 3, "rust_included": args.rust is not None,
               "invalid_probes": probes, "core_checks": core_checks, "failures": failures, "models": records,
               "scope": "Synthetic ir-native-event-v1 generated-model tests; no legacy semantic or Monte Carlo distribution equivalence claim."}
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"models": args.models, "passed": len(records), "failures": len(failures), "rejections": sum(p["rejected"] for p in probes), "probes": len(probes), "output": str(args.output)}))
    if failures or not all(item["rejected"] for item in probes + core_checks["core_probes"] + core_checks["backend_probes"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
