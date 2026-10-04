"""Independent, read-only F04.var01 native evidence replay (standard library only)."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CASES = HERE.parent
PARENT = CASES / "F03-var01-two-base-crew-v1.0.0"
RUNS = [
    HERE / "runs" / f"f04-var01-repeat-{arm}-v101-ssh-20261004-01"
    for arm in ("a", "b")
]
RESULT = HERE / "review" / "independent-verdict.json"
failures: list[str] = []
checks = 0


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def read_json(path: Path, native: bool = False):
    s = path.read_text(encoding="utf-8-sig")
    if native:
        # Native exporter emits trailing commas; this substitution scans the file once.
        s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def tables(obj: dict, root: str) -> dict:
    return {t["name"]: t for t in obj[root]["tables"]}


def columns(table: dict) -> list[str]:
    return [c["name"] for c in table["columns"]]


def rows(table: dict) -> list[list]:
    return [r for inst in table["instances"] for r in inst["rows"]]


def report_rows(report: dict, name: str) -> list[dict]:
    t = tables(report, "report")[name]
    c = columns(t)
    return [dict(zip(c, r)) for r in rows(t)]


def equal(a: float, b: float, tol: float = 2e-4) -> bool:
    return abs(a - b) <= tol


def integrate(intervals: list[tuple[float, float, int]], start: float, end: float) -> float:
    return sum(n * max(0.0, min(b, end) - max(a, start)) / (end - start)
               for a, b, n in intervals)


contract = read_json(HERE / "contract.json")
diff = read_json(HERE / "exact-diff.json")
source = read_json(HERE / "native-input.json")
parent = read_json(PARENT / "staffed-input.json")
check(sha(HERE / "native-input.json") == contract["input_sha256"], "frozen input SHA")
check(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen diff SHA")
check(sha(PARENT / "staffed-input.json") == contract["accepted_parent"]["input_sha256"], "accepted parent SHA")
check(sha(PARENT / "runs" / "f03-v101-staffed-ssh-20261004-01" / "closure.json") == contract["accepted_parent"]["closure_sha256"], "accepted parent closure SHA")
check(sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["accepted_parent"]["signoff_sha256"], "accepted parent signoff SHA")

prerequisites = {
    "J04.var01": "J04-var01-fixed-replications-v1.0.0",
    "J05.var05": "J05-horizon-v1.0.0",
    "J06.var02": "J06-system-replication-v1.0.1",
    "J07.var01": "J07-formation-denial-v1.0.0",
    "J08.var01": "J08-item-stock-resource-ledger-v1.0.0",
}
for key, directory in prerequisites.items():
    stem = "2026-10-04" if key in ("J06.var02", "J08.var01") else "2026-10-01"
    signoff = CASES / directory / f"cli-scope-signoff-{stem}.md"
    check(signoff.exists() and sha(signoff) == contract["accepted_reporting_prerequisites_sha256"][key], f"{key} prerequisite SHA")

pt, st = tables(parent, "model"), tables(source, "model")
check(pt.keys() == st.keys(), "parent and child table set")
actual = []
for name in pt:
    p, s = pt[name], st[name]
    check(columns(p) == columns(s), f"{name} column shape")
    pr, sr = rows(p), rows(s)
    check(len(pr) == len(sr), f"{name} row count")
    for rownum, (a, b) in enumerate(zip(pr, sr), 1):
        for field, va, vb in zip(columns(p), a, b):
            if va != vb:
                actual.append((name, rownum, field, va, vb))
declared = [(c["table"], c["row"], c["column"], c["from"], c["to"]) for c in diff["changes"]]
check(len(actual) == 14, "exact fourteen-cell parent delta")
check(sorted(actual, key=str) == sorted(declared, key=str), "declared diff equals independently recomputed diff")
check(rows(st["Control"])[0][columns(st["Control"]).index("SIMPE")] == 1032, "43-day horizon")
for idx in (0, 3):
    row = rows(st["OperationProfile"])[idx]
    fields = columns(st["OperationProfile"])
    check(row[fields.index("IQTY")] == 21 and row[fields.index("IPER")] == 1008,
          f"profile row {idx + 1} has 48-hour native period")

source_files = {
    "native_input": HERE / "native-input.json",
    "contract": HERE / "contract.json",
    "exact_diff": HERE / "exact-diff.json",
    "accepted_parent": PARENT / "staffed-input.json",
    "accepted_parent_closure": PARENT / "runs" / "f03-v101-staffed-ssh-20261004-01" / "closure.json",
    "accepted_parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
    "build.py": HERE / "build.py",
    "describe_diff.py": HERE / "describe_diff.py",
    "check_roundtrip.py": HERE / "check_roundtrip.py",
    "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
}
for key, directory in prerequisites.items():
    stem = "2026-10-04" if key in ("J06.var02", "J08.var01") else "2026-10-01"
    source_files[key.split(".")[0] + "_signoff"] = CASES / directory / f"cli-scope-signoff-{stem}.md"

observations = []
for run in RUNS:
    label = run.name
    closure = read_json(run / "closure.json")
    invocation = read_json(run / "invocation.json")
    steps = read_json(run / "steps.json")
    check(closure["run_id"] == label == invocation["run_id"], f"{label} identity")
    check(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{label} invocation seal")
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], f"{label} source stability")
    for key, path in source_files.items():
        check(closure["source_hashes_before"].get(key) == sha(path), f"{label} source seal {key}")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], f"{label} SSH0 provenance")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{label} GUI preserved")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{label} queue mutex")
    check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{label} five steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0, f"{label} {step['name']} complete")
        if "gui_preserved" in step:
            check(step["gui_preserved"] is True, f"{label} {step['name']} GUI")
    check(len(closure["raw"]) == 12, f"{label} twelve raw artifacts")
    for filename, seal in sorted(closure["raw"].items()):
        file = run / filename
        check(file.exists() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"], f"{label} raw seal {filename}")
    check(sha(run / "input.json") == contract["input_sha256"], f"{label} exact input")
    exported = tables(read_json(run / "roundtrip-raw.json"), "model")
    n_business = 0
    for name, authored in st.items():
        original = rows(authored)
        if not original:
            continue
        n_business += 1
        native = exported.get(name)
        check(native is not None, f"{label} exported {name}")
        if native is None:
            continue
        src_cols, dst_cols = columns(authored), columns(native)
        check(set(src_cols).issubset(dst_cols), f"{label} {name} exported columns")
        projected = [[row[dst_cols.index(c)] for c in src_cols] for row in rows(native)]
        check(projected == original, f"{label} {name} authored row roundtrip")
    check(n_business == 30, f"{label} thirty row-containing tables")
    runlog = (run / "run.log").read_text(errors="replace")
    check(re.search(r"Errors:\s*0,\s*Warnings:\s*3,\s*Notes:\s*0", runlog) is not None, f"{label} converter totals")
    check([int(n) for n in re.findall(r"\(warning #(\d+)\)", runlog)] == [108, 2053, 2053], f"{label} converter warning codes")
    check((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 1000, f"{label} valid native outputs")

    log = (run / "model.log").read_text(errors="replace")
    ordered = re.findall(r"^Time:\s*([\d.]+) <([^>]+)> mission ordered: ([A-Z0-9-]+)$", log, re.M)
    starts = re.findall(r"^Time:\s*([\d.]+) <([^>]+)> mission starting, duration: ([\d.]+) : (.*)$", log, re.M)
    successes = re.findall(r"^Time:\s*([\d.]+) <([^>]+)> mission success:", log, re.M)
    completions = re.findall(r"^Time:\s*([\d.]+) <([^>]+)> mission completed: (.*)$", log, re.M)
    check(len(ordered) == len(starts) == len(successes) == len(completions) == 63, f"{label} 63 complete successful missions")
    check(not re.search(r"mission cancel|mission abort|fault occurs|failure occurs|item failure|backorder|Stock demanded|stock demanded", log, re.I), f"{label} no fault/cancel/backorder/demand")
    by_type = {typ: [] for typ in ("BASE2-MISSION", "RISK-MISSION", "BASIC-MISSION")}
    for t, unit, typ in ordered:
        check(typ in by_type, f"{label} known mission type")
        if typ in by_type:
            by_type[typ].append(float(t))
    for typ, offset in (("BASE2-MISSION", 7), ("RISK-MISSION", 20.5), ("BASIC-MISSION", 23.75)):
        check(len(by_type[typ]) == 21, f"{label} 21 {typ} orders")
        for k, t in enumerate(by_type[typ]):
            check(equal(t, offset + 48 * k, 1e-3), f"{label} {typ} order cycle {k}")
    starts_by_id = {ident: (float(t), float(duration), tail) for t, ident, duration, tail in starts}
    success_by_id = {ident: float(t) for t, ident in successes}
    completion_by_id = {ident: (float(t), tail) for t, ident, tail in completions}
    check(set(starts_by_id) == set(success_by_id) == set(completion_by_id), f"{label} mission identity closure")
    flight_intervals = []
    for ident, (begin, duration, aircraft) in starts_by_id.items():
        end, completed_aircraft = completion_by_id[ident]
        n = aircraft.count("<TEACH-AIR-01,")
        check(n == (1 if ident.startswith("BASE2-MISSION") else 2), f"{label} mission formation {ident}")
        check(equal(duration, 2) and equal(success_by_id[ident], end, 1e-3) and equal(end - begin, 2, 1e-3), f"{label} duration/success {ident}")
        check(aircraft == completed_aircraft, f"{label} aircraft identity closure {ident}")
        flight_intervals.append((begin, end, n))
    check(sum((b - a) * n for a, b, n in flight_intervals) == 210, f"{label} 210 aircraft flight hours")

    pm_starts = re.findall(r"^Time:\s*([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,(\d+)> started$", log, re.M)
    pm_ends = re.findall(r"^Time:\s*([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,(\d+)> completed$", log, re.M)
    pm_start = {task: (float(t), int(aircraft)) for t, task, aircraft in pm_starts}
    pm_end = {task: (float(t), int(aircraft)) for t, task, aircraft in pm_ends}
    check(len(pm_start) == 324 and len(pm_end) == 323, f"{label} PM task cardinality")
    check(set(pm_end).issubset(pm_start) and len(set(pm_start) - set(pm_end)) == 1, f"{label} one PM active at cutoff")
    for task, (end, aid) in pm_end.items():
        begin, original = pm_start[task]
        check(aid == original and end >= begin, f"{label} PM task {task} identity/lifecycle")
    open_task = (set(pm_start) - set(pm_end)).pop()
    check(equal(pm_start[open_task][0], 1031, 2e-3), f"{label} cutoff PM starts at 1031")
    # Task creation can precede a resource wait. Actual PM occupancy begins at
    # the separate "System to PM" event, after the maintainer is booked.
    pm_phase_start = re.findall(r"^Time:\s*([\d.]+) <TEACH-AIR-01,BASE-0[12],0> System to PM <TEACH-AIR-01,(\d+)>$", log, re.M)
    pm_phase_end = re.findall(r"^Time:\s*([\d.]+) <TEACH-AIR-01,BASE-0[12],0> Maintained system arrives <TEACH-AIR-01,(\d+)>$", log, re.M)
    check(len(pm_phase_start) == 324 and len(pm_phase_end) == 323, f"{label} PM physical phase cardinality")
    pm_active: dict[int, float] = {}
    pm_intervals = []
    pm_events = sorted([(float(t), 1, int(a)) for t, a in pm_phase_start] +
                       [(float(t), 0, int(a)) for t, a in pm_phase_end])
    for t, opening, aid in pm_events:
        if opening:
            check(aid not in pm_active, f"{label} PM phase unique aircraft {aid}@{t}")
            pm_active[aid] = t
        else:
            check(aid in pm_active, f"{label} PM phase closes aircraft {aid}@{t}")
            if aid in pm_active:
                pm_intervals.append((pm_active.pop(aid), t, 1))
    for aid, begin in pm_active.items():
        pm_intervals.append((begin, 1032, 1))
    check(len(pm_active) == 1, f"{label} one physical PM phase at horizon")
    grant_re = re.compile(r"^Time:\s*([\d.]+)  <(P-(?:CREW|MAINT) at <BASE-0[12],0>)> (allocated to|deallocated from)\s+maintenance task: 1", re.M)
    active: dict[str, float] = {}
    grants = []
    for t, key, action in grant_re.findall(log):
        at = float(t)
        if action == "allocated to":
            check(key not in active, f"{label} no duplicate resource grant {key}@{at}")
            active[key] = at
        else:
            check(key in active, f"{label} resource release has grant {key}@{at}")
            if key in active:
                grants.append((active.pop(key), at, 1))
    for key, begin in active.items():
        grants.append((begin, 1032, 1))
    check(len(active) == 1 and next(iter(active)).startswith("P-MAINT"), f"{label} only cutoff PM worker remains booked")
    check(equal(sum(b - a for a, b, _ in grants), 376.5, 3e-2), f"{label} 324 PM + 52.5 prep worker hours")

    report = read_json(run / "report-raw.json", native=True)
    summary = report_rows(report, "ResultSummary")[0]
    system = report_rows(report, "SystemResults")
    stock = report_rows(report, "StockTotalResults")
    resource = report_rows(report, "ResourceResults")
    resource_total = report_rows(report, "ResourceResultsTotal")[0]
    check(summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 1032, f"{label} summary horizon")
    for metric in ("MTMF", "MSTF", "MSUF", "STMF"):
        check(equal(summary[metric], 1), f"{label} all-success {metric}")
    check(len(system) == len(stock) == len(resource) == 2064, f"{label} 2064 aligned rows each")
    for i, (sy, so, rr) in enumerate(zip(system, stock, resource)):
        a, b = i / 2, (i + 1) / 2
        for name, row in (("System", sy), ("Stock", so), ("Resource", rr)):
            check(equal(row["STINT"], a, 1e-6) and equal(row["ETINT"], b, 1e-6), f"{label} {name} bin {i} clock")
        check(equal(sy["NSYA"] + sy["NSYUA"], 8, 2e-3), f"{label} bin {i} aircraft conserved")
        check(equal(sy["NSYRY"] + sy["NSYMA"], sy["NSYA"], 2e-3), f"{label} bin {i} available split")
        check(equal(sy["NSYPM"], sy["NSYUA"], 2e-3), f"{label} bin {i} PM/unavailable")
        check(equal(sy["NSYMO"], integrate(flight_intervals, a, b), 2e-3), f"{label} bin {i} mission occupancy")
        check(equal(sy["STACC"], sy["NSYMO"], 2e-3), f"{label} bin {i} flight hours")
        check(equal(sy["NSYPM"], integrate(pm_intervals, a, b), 6e-3), f"{label} bin {i} PM occupancy")
        check(rr["NR"] == rr["NRA"] == 4 and rr["NRW"] >= -1e-4, f"{label} bin {i} resource quantity/wait")
        check(equal(rr["NRUM"], integrate(grants, a, b), 6e-3), f"{label} bin {i} worker booking")
        check(so["NBO"] == 0 and so["NDF"] == so["NDD"] == so["NDR"] == so["NDP"] == so["NLD"] == so["NWT"] == 0, f"{label} bin {i} no stock demand")
        check(sy["NFAIL"] == sy["NDAM"] == 0, f"{label} bin {i} no failure/damage")
    check(equal(sum(r["NSYMO"] for r in system) * .5, 210, 2e-2), f"{label} report flight integral")
    check(equal(sum(r["NSYPM"] for r in system) * .5, 324, 2e-2), f"{label} report PM integral")
    check(equal(sum(r["NRUM"] for r in resource) * .5, 376.5, 2e-2), f"{label} resource use integral")
    check(equal(sum(r["NRW"] for r in resource) * .5, resource_total["NRW"] * 1032, 2e-2), f"{label} resource wait total")
    check(sum(r["NPMS"] for r in system) == 324 and sum(r["NPMT"] for r in system) == 323, f"{label} PM markers versus tasks")
    last = system[-1]
    check(equal(last["NSYRY"], 7) and equal(last["NSYPM"], 1) and equal(resource[-1]["NRUM"], 1), f"{label} last-bin active PM")
    check("Time: 1032  Start of day no 43" in log and "Tasks waiting for resources at: <BASE-02,0> 0" in log[-3000:], f"{label} terminal boundary")
    observations.append({
        "run_id": label,
        "closure_sha256": sha(run / "closure.json"),
        "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "missions_started_succeeded": len(starts),
        "pm_started_completed_open": [len(pm_start), len(pm_end), len(active)],
        "flight_aircraft_hours": 210,
        "pm_aircraft_hours": sum(r["NSYPM"] for r in system) * .5,
        "resource_booked_hours": sum(r["NRUM"] for r in resource) * .5,
        "resource_queued_hours": sum(r["NRW"] for r in resource) * .5,
        "terminal_last_bin_ready_pm": [last["NSYRY"], last["NSYPM"]],
    })

check(observations[0]["model_log_sha256"] == observations[1]["model_log_sha256"], "byte-identical repeat event logs")
check(observations[0]["report_sha256"] == observations[1]["report_sha256"], "byte-identical repeat native reports")
v100 = CASES / "F04-var01-deterministic-43day-v1.0.0"
check(v100.exists() and (v100 / "native-input.json").exists(), "excluded v1.0.0 source retained")
old = tables(read_json(v100 / "native-input.json"), "model")["OperationProfile"]
check([rows(old)[i][columns(old).index("IPER")] for i in (0, 3)] == [48, 48], "excluded v1.0.0 compressed period")

verdict = {
    "schema": "f04-var01-independent-readonly/v1",
    "passed": not failures,
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "source_sha256": sha(HERE / "native-input.json"),
    "runs": observations,
    "excluded_diagnostic": "v1.0.0 used IQTY21/IPER48, producing 48/21-hour spacing; no acceptance claim from its two runs",
    "limits": [
        "One fixed seed and NREPS1; repeatability does not establish stochastic precision or cross-engine parity.",
        "Seven ready plus one PM aircraft in the final [1031.5,1032) report bin; no post-horizon completion is observed.",
        "No failures, item demands, physical transport or repair occur; their long-horizon support behavior is untested.",
        "Aggregate resource NRW is checked against time-series total, not interpreted as booked time or a worker identity ledger.",
        "GUI visual behavior and per-replication reports are outside this CLI result.",
    ],
}
RESULT.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{verdict['verdict']} {verdict['checks_passed']}/{verdict['checks_total']}")
for failure in failures[:30]:
    print("FAIL", failure)
