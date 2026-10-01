"""Source-bound author replay of the predeclared E06 three-level seed panel."""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

MANIFEST_SHA = "1ff2c01493fe6634d71124c91a5803a67cda1b907120d217cc8803a2a36d38cf"
PARENT_SHA = "7febb8c32afaa24fbf3bad94ba240e53236d8967c6fe6df51b4cfb7686828b0d"
SUPPORT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}
ITEM = r"<TEACH-LRU-01,0,(\d+)>"
FIRST_ARRIVAL = re.compile(r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives "
                           + ITEM + r" from position <TEACH-AIR-01,BASE-01,0> direct repair failure  complexity: ([0-9.]+)")
REPAIR_START = re.compile(r"^Time: ([0-9.]+) <TEACH-LRU-01,0,(BASE-01|DEPOT-01|WORKSHOP-01),0> Start repair of item " + ITEM + r"$")
REPAIR_FINISH = re.compile(r"^Time: ([0-9.]+) <TEACH-LRU-01,0,(BASE-01|DEPOT-01|WORKSHOP-01),0> Finished repair of item " + ITEM + r"$")
RESTOCK = re.compile(r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item " + ITEM + r" to stock ")
TRANSPORT = re.compile(r"^Time: ([0-9.]+)  transport request <<TEACH-LRU-01,0,(\d+)>,<TEACH-LRU-01,0,(BASE-01|DEPOT-01|WORKSHOP-01),0>,<TEACH-LRU-01,0,(BASE-01|DEPOT-01|WORKSHOP-01),0>> attached to  transport task (\d+)$")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(a: float, b: float, tolerance: float = 0.00011) -> bool:
    return abs(a - b) <= tolerance


def route(complexity: float) -> tuple[str, list[tuple[str, str]]]:
    if complexity < 0.2:
        return "BASE-01", []
    if complexity < 0.7:
        return "DEPOT-01", [("BASE-01", "DEPOT-01"), ("DEPOT-01", "BASE-01")]
    return "WORKSHOP-01", [("BASE-01", "DEPOT-01"), ("DEPOT-01", "WORKSHOP-01"),
                           ("WORKSHOP-01", "DEPOT-01"), ("DEPOT-01", "BASE-01")]


def validate(max_seed: int = 48) -> dict:
    errors: list[str] = []
    nchecks = 0
    first_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    total_failures = total_repairs = total_seals = 0
    run_records = []

    def ck(label: str, ok: bool) -> None:
        nonlocal nchecks
        nchecks += 1
        if not ok:
            errors.append(label)

    contract, manifest = load(HERE / "contract.json"), load(HERE / "seed-manifest.json")
    ck("manifest fingerprint", sha(HERE / "seed-manifest.json") == MANIFEST_SHA)
    ck("manifest panel", set(map(int, manifest["seeds"])) == set(range(1, 49))
       and manifest["parent_sha256"] == PARENT_SHA and manifest["support_sha256"] == SUPPORT_SHA)
    ck("contract panel", contract["native_panel"]["seed_manifest_sha256"] == MANIFEST_SHA
       and contract["native_panel"]["seed_range_inclusive"] == [1, 48]
       and contract["native_panel"]["horizon_hours"] == 60)
    ck("parent", sha(HERE.parent / "E06-var01-repair-routing-v1.0.0/upstream-input.json") == PARENT_SHA)
    ck("support", sha(HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json") == SUPPORT_SHA)
    ck("seed-1 sample", sha(HERE / "seed-01-input.json") == manifest["seeds"]["1"])
    for seed in range(1, max_seed + 1):
        prefix = f"seed {seed:02d}: "
        run_id = f"e06-three-v101-seed{seed:02d}-ssh-20261002-01"
        run = HERE / "runs" / run_id
        invocation, closure, steps = load(run / "invocation.json"), load(run / "closure.json"), load(run / "steps.json")
        input_sha = manifest["seeds"][str(seed)]
        ck(prefix + "invocation", invocation.get("case_id") == "E06" and invocation.get("variant_id") == "E06.var01"
           and invocation.get("seed") == seed and invocation.get("run_id") == run_id
           and invocation.get("input_sha256") == input_sha and invocation.get("manifest_sha256") == MANIFEST_SHA
           and invocation.get("parent_sha256") == PARENT_SHA and invocation.get("support_sha256") == SUPPORT_SHA)
        ck(prefix + "run input", sha(run / "input.json") == input_sha)
        for field, filename in (("contract_sha256", "contract.json"), ("builder_sha256", "build.py"),
                                ("checker_sha256", "check_roundtrip.py"), ("runner_script_sha256", "run_native_ssh.ps1")):
            ck(prefix + "bound " + filename, invocation.get(field) == sha(HERE / filename))
        ck(prefix + "executable/SSH/GUI/queue", invocation.get("simlox_exe_sha256") == EXE_SHA
           and invocation.get("session_id") == 0 and invocation.get("ssh_connection_present")
           and "sshd.exe" in invocation.get("ssh_ancestor_names", [])
           and invocation.get("gui", {}).get("pid") == 13340
           and invocation.get("gui", {}).get("session_id") == 1
           and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue")
        ck(prefix + "closure", closure.get("error") is None
           and closure.get("invocation_sha256") == sha(run / "invocation.json")
           and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
        ck(prefix + "raw set", set(closure.get("raw", {})) == RAW)
        total_seals += len(closure.get("raw", {}))
        for name, item in closure.get("raw", {}).items():
            path = run / name
            ck(prefix + "sealed " + name, path.is_file() and path.stat().st_size == item.get("bytes")
               and sha(path) == item.get("sha256"))
        ck(prefix + "step order", [step.get("name") for step in steps]
           == ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            ck(prefix + "step " + step.get("name", "?"), step.get("status") == "completed"
               and step.get("exit_code") == 0 and step.get("gui_preserved") is True)
        roundtrip = load(run / "roundtrip-validation.json")
        ck(prefix + "roundtrip", roundtrip.get("passed") is True and not roundtrip.get("differences")
           and len(roundtrip.get("populated_tables", [])) == 21
           and native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
        calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(prefix + "conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc
           and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1}))
        lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        times = [float(m[1]) for line in lines if (m := re.match(r"^Time: ([0-9.]+) ", line))]
        ck(prefix + "event order", bool(times) and times == sorted(times) and times[-1] <= 60)
        first = [m for line in lines if (m := FIRST_ARRIVAL.match(line))]
        starts = [m for line in lines if (m := REPAIR_START.match(line))]
        finishes = [m for line in lines if (m := REPAIR_FINISH.match(line))]
        restocks = [m for line in lines if (m := RESTOCK.match(line))]
        transports = [m for line in lines if (m := TRANSPORT.match(line))]
        failure_times = [m[1] for line in lines if (m := re.match(
            r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical random failure added", line))]
        aborted_times = [m[1] for line in lines if (m := re.match(
            r"^Time: ([0-9.]+) <BASIC-MISSION,[^>]+> mission aborted:", line))]
        failures = len(failure_times)
        system_starts = sum(re.search(r"^Time: [0-9.]+  system SURP task \d+ .* started$", line) is not None for line in lines)
        system_repairs = sum(re.search(r"^Time: [0-9.]+  system SURP task \d+ .* completed$", line) is not None for line in lines)
        ck(prefix + "mission abort at each failure", Counter(failure_times) == Counter(aborted_times))
        ck(prefix + "physical cycle counts", failures == system_starts == system_repairs == len(first) == len(starts) == len(finishes) == len(restocks))
        total_failures += failures
        total_repairs += len(starts)
        if first:
            station, _ = route(float(first[0][3]))
            first_counts[station] += 1
        expected_transport_count = 0
        for arrival in first:
            arrival_time, item_id, complexity = float(arrival[1]), arrival[2], float(arrival[3])
            station, path = route(complexity)
            route_counts[station] += 1
            s = [x for x in starts if x[3] == item_id]
            f = [x for x in finishes if x[3] == item_id]
            z = [x for x in restocks if x[2] == item_id]
            ck(prefix + f"item {item_id} repair identity", len(s) == len(f) == len(z) == 1
               and s[0][2] == f[0][2] == station and near(float(f[0][1]) - float(s[0][1]), 1))
            ck(prefix + f"item {item_id} route timing", len(s) == 1 and len(z) == 1
               and near(float(s[0][1]) - arrival_time, 2 * len(path) / 2)
               and near(float(z[0][1]) - float(f[0][1]), 2 * len(path) / 2))
            actual_links = [(x[3], x[4], float(x[1]), x[5]) for x in transports if x[2] == item_id]
            expected_transport_count += len(path)
            ck(prefix + f"item {item_id} transport links", [(a, b) for a, b, _, _ in actual_links] == path)
            for source, target, start_time, task_id in actual_links:
                ck(prefix + f"item {item_id} task {task_id} two-hour transport",
                   any(line.startswith(f"Time: {start_time:g} ") and f"transport task {task_id} starts with 1 items/systems, transport time: 2" in line for line in lines)
                   and any((m := re.match(r"^Time: ([0-9.]+)  transport task " + task_id + r" arrives with 1 items/systems$", line))
                           and near(float(m[1]) - start_time, 2) for line in lines))
        ck(prefix + "no extra transport", len(transports) == expected_transport_count)
        report = json.loads(native.remove_trailing_commas((run / "report-raw.json").read_bytes()))
        summary = native.table_rows(report, "ResultSummary")
        system, stock = native.table_rows(report, "SystemResults"), native.table_rows(report, "StockTotalResults")
        ck(prefix + "report horizon", len(summary) == 1 and summary[0]["NREP"] == 1
           and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 60)
        ck(prefix + "120 aligned half-hour bins", len(system) == len(stock) == 120
           and all(near(a["STINT"], i / 2, 1e-9) and near(a["ETINT"], (i + 1) / 2, 1e-9)
                   and near(b["STINT"], i / 2, 1e-9) and near(b["ETINT"], (i + 1) / 2, 1e-9)
                   for i, (a, b) in enumerate(zip(system, stock))))
        ck(prefix + "report failure/repair", sum(row["NFAIL"] for row in system) == failures
           and sum(row["NREPT"] for row in system) == system_repairs)
        ck(prefix + "terminal ready/stock", system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0
           and (not restocks or any(line == f"  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,{restocks[-1][2]}>," for line in lines)))
        run_records.append({"seed": seed, "run_id": run_id, "input_sha256": input_sha,
                            "invocation_sha256": sha(run / "invocation.json"),
                            "closure_sha256": sha(run / "closure.json"),
                            "model_log_sha256": sha(run / "model.log"),
                            "report_sha256": sha(run / "report-raw.json"),
                            "critical_failures": failures, "direct_repairs": len(starts),
                            "first_route": route(float(first[0][3]))[0] if first else None,
                            "first_complexity": float(first[0][3]) if first else None})
    if max_seed == 48:
        ck("first-failure sample size", sum(first_counts.values()) >= 36)
        for station in ("BASE-01", "DEPOT-01", "WORKSHOP-01"):
            ck(f"first-failure {station} coverage", first_counts[station] >= 3)
    return {"schema": "simlox-e06-var01-three-level-author-panel/v1", "passed": not errors,
            "checks": nchecks, "differences": errors, "seeds_completed": max_seed,
            "first_routes": dict(first_counts), "all_direct_repair_routes": dict(route_counts),
            "critical_failures": total_failures, "direct_repairs": total_repairs,
            "raw_seals": total_seals, "runs": run_records,
            "scope": "predeclared_48_seed_panel" if max_seed == 48 else "partial_diagnostic_only",
            "publication_state": "not_published"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-seed", type=int, default=48)
    args = parser.parse_args()
    if not 1 <= args.max_seed <= 48:
        parser.error("max seed must be 1 through 48")
    result = validate(args.max_seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
