"""Independent read-only replay of the E06 three-level 48-seed panel.

Uses only the standard library and never imports author builder/checker/validator.
It reads immutable sources and native runs and writes only its adjacent JSON report.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
PARENT = ROOT / "E06-var01-repair-routing-v1.0.0" / "upstream-input.json"
SUPPORT = ROOT / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
FILES = {
    "sample": CASE / "seed-01-input.json",
    "manifest": CASE / "seed-manifest.json",
    "parent": PARENT,
    "support": SUPPORT,
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
BASE, DEPOT, WORKSHOP = "BASE-01", "DEPOT-01", "WORKSHOP-01"
ITEM = r"TEACH-LRU-01,0,(\d+)"
POOL = r"TEACH-LRU-01,0,([^,>]+),0"
checks = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native=False):
    value = path.read_text(encoding="utf-8-sig")
    if native: value = re.sub(r",(?=\s*[}\]])", "", value)
    return json.loads(value)


def check(name, passed, detail=None):
    checks.append({"name": name, "pass": bool(passed), **({"detail": detail} if detail is not None else {})})


def near(x, y, tol=3e-4):
    return math.isclose(x, y, rel_tol=0, abs_tol=tol)


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def index(table, name):
    return [c["name"] for c in table["columns"]].index(name)


def rows(table):
    return [(inst["instance_name"], row) for inst in table["instances"] for row in inst["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for _, row in rows(table)]


def setfield(table, row, name, value):
    row[index(table, name)] = value


def construct(parent, seed):
    doc = copy.deepcopy(parent)
    t = tables(doc)
    setfield(t["ProblemDescription"], t["ProblemDescription"]["instances"][0]["rows"][0], "PDESC", "E06 three-level cumulative direct repair fractions 0.2/0.7/1")
    control = t["Control"]["instances"][0]["rows"][0]
    for name, value in (("RSEED", str(seed)), ("SIMPE", 60.0), ("RCEND", 60.0)):
        setfield(t["Control"], control, name, value)
    for inst in t["ResultCollection"]["instances"]:
        for row in inst["rows"]: setfield(t["ResultCollection"], row, "RCEND", 60.0)
    station = t["Station"]
    top = copy.deepcopy(station["instances"][0]["rows"][1])
    setfield(station, top, "STID", WORKSHOP)
    setfield(station, top, "DESCR", "Teaching final repair workshop")
    station["instances"][0]["rows"].append(top)
    hierarchy = t["StationStructure"]
    new_link = copy.deepcopy(hierarchy["instances"][0]["rows"][0])
    setfield(hierarchy, new_link, "STID", DEPOT)
    setfield(hierarchy, new_link, "MSTID", WORKSHOP)
    hierarchy["instances"][0]["rows"].append(new_link)
    repair = t["ItemRepair"]
    base, depot = repair["instances"][0]["rows"]
    setfield(repair, base, "DIRPF", .2)
    setfield(repair, depot, "DIRPF", .7)
    top_repair = copy.deepcopy(depot)
    setfield(repair, top_repair, "STID", WORKSHOP)
    setfield(repair, top_repair, "DIRPF", 1.0)
    repair["instances"][0]["rows"].append(top_repair)
    stock = t["StockAllocation"]
    top_stock = copy.deepcopy(stock["instances"][0]["rows"][1])
    setfield(stock, top_stock, "STID", WORKSHOP)
    stock["instances"][0]["rows"].append(top_stock)
    return doc


def classify(complexity):
    if complexity < .2: return BASE
    if complexity < .7: return DEPOT
    return WORKSHOP


def physical_trace(log):
    # Each removed item's first BASE arrival carries the one drawn complexity.
    first = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <" + ITEM + r"> from position <TEACH-AIR-01,BASE-01,0> direct repair failure\s+complexity: ([0-9.]+)", log)
    movement = re.findall(r"Time: ([0-9.]+)\s+transport request <<" + ITEM + r">,<" + POOL + r">,<" + POOL + r">> started", log)
    repair_starts = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,([^,>]+),0> Start repair of item <" + ITEM + r">", log)
    repair_ends = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,([^,>]+),0> Finished repair of item <" + ITEM + r">", log)
    restocks = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <" + ITEM + r"> to stock", log)
    arrivals = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,([^,>]+),0> (?:Item requiring maintenance arrives|Replacement item arrives) <" + ITEM + r">", log)
    ids = [item for _, item, _ in first]
    traces = []
    for initial, item, complexity_text in first:
        complexity = float(complexity_text)
        level = classify(complexity)
        outward = [] if level == BASE else [(BASE, DEPOT)] if level == DEPOT else [(BASE, DEPOT), (DEPOT, WORKSHOP)]
        inward = [(dest, src) for src, dest in reversed(outward)]
        legs = [(float(t), src, dst) for t, item_id, src, dst in movement if item_id == item]
        starts = [(float(t), station) for t, station, item_id in repair_starts if item_id == item]
        ends = [(float(t), station) for t, station, item_id in repair_ends if item_id == item]
        back = [float(t) for t, item_id in restocks if item_id == item]
        arrivals_for_item = [(float(t), station) for t, station, item_id in arrivals if item_id == item]
        traces.append({"id": int(item), "complexity": complexity, "classification": level, "base_arrival": float(initial), "expected_legs": outward + inward, "legs": legs, "repair_starts": starts, "repair_ends": ends, "base_restocks": back, "arrivals": arrivals_for_item})
    return traces, {"first": len(first), "unique_ids": len(set(ids)), "movement": len(movement), "repair_starts": len(repair_starts), "repair_ends": len(repair_ends), "restocks": len(restocks)}


def verify_item(seed, item):
    prefix = f"seed {seed:02d} item {item['id']}"
    expected_legs = item["expected_legs"]
    observed_legs = [(src, dst) for _, src, dst in item["legs"]]
    check(prefix + " exact outward/return station path", observed_legs == expected_legs, observed_legs)
    check(prefix + " unique station repair", len(item["repair_starts"]) == len(item["repair_ends"]) == 1 and item["repair_starts"][0][1] == item["repair_ends"][0][1] == item["classification"])
    if len(item["repair_starts"]) != 1 or len(item["repair_ends"]) != 1: return
    started, finished = item["repair_starts"][0][0], item["repair_ends"][0][0]
    outward_hops = len(expected_legs) // 2
    check(prefix + " two-hour outbound links", near(started, item["base_arrival"] + outward_hops * 2))
    check(prefix + " one-hour direct repair", near(finished - started, 1))
    check(prefix + " single base restock after return", len(item["base_restocks"]) == 1 and near(item["base_restocks"][0], finished + outward_hops * 2))
    expected_leg_starts = [item["base_arrival"] + i * 2 for i in range(outward_hops)] + [finished + i * 2 for i in range(outward_hops)]
    check(prefix + " physical transport starts", len(item["legs"]) == len(expected_leg_starts) and all(near(t, expected) for (t, _, _), expected in zip(item["legs"], expected_leg_starts)), [t for t, _, _ in item["legs"]])
    # Native arrival lines bind the same physical instance to each destination.
    for started_leg, _, destination in item["legs"]:
        check(prefix + f" arrival at {destination} after two hours", any(station == destination and near(time, started_leg + 2) for time, station in item["arrivals"]))


def main():
    contract, manifest = read(CASE / "contract.json"), read(CASE / "seed-manifest.json")
    parent = read(PARENT)
    check("parent SHA", sha(PARENT) == contract["direct_parent"]["input_sha256"])
    check("support SHA", sha(SUPPORT) == contract["support_prerequisite"]["input_sha256"])
    check("manual SHA", sha(FILES["manual"]) == contract["source"]["manual_pdf_sha256"])
    check("dictionary SHA", sha(FILES["dictionary"]) == contract["source"]["dictionary_sha256"])
    check("manifest SHA", sha(FILES["manifest"]) == contract["native_panel"]["seed_manifest_sha256"])
    check("sample SHA", sha(FILES["sample"]) == contract["native_panel"]["sample_seed_1_input_sha256"])
    check("48 manifest seeds", set(manifest["seeds"]) == {str(i) for i in range(1, 49)})
    current_sha = {name: sha(path) for name, path in FILES.items()}
    parent_tables = tables(parent)
    runs_dir = CASE / "runs"
    run_names = {f"e06-three-v101-seed{seed:02d}-ssh-20261002-01" for seed in range(1, 49)}
    check("exact 48 accepted run directories", {p.name for p in runs_dir.iterdir() if p.is_dir()} == run_names)
    gui = None
    raw_count = 0
    first_count = Counter()
    all_count = Counter()
    first_observed = 0
    all_items = 0
    per_seed = {}
    for seed in range(1, 49):
        tag = f"seed {seed:02d}"
        run = runs_dir / f"e06-three-v101-seed{seed:02d}-ssh-20261002-01"
        frozen = (json.dumps(construct(parent, seed), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        expected_sha = hashlib.sha256(frozen).hexdigest()
        check(tag + " exact parent-derived model bytes", (run / "input.json").read_bytes() == frozen)
        check(tag + " manifest input SHA", expected_sha == manifest["seeds"][str(seed)])
        if seed == 1: check("seed 01 sample bytes", (CASE / "seed-01-input.json").read_bytes() == frozen)
        source = tables(read(run / "input.json"))
        changed = {name for name in source if source[name] != parent_tables.get(name)}
        check(tag + " common/seed table delta", changed == {"ProblemDescription", "Control", "ResultCollection", "Station", "StationStructure", "ItemRepair", "StockAllocation"})
        repair = records(source["ItemRepair"])
        check(tag + " accumulated DIRPF", [(r["STID"], r["DIRPF"], r["DIRPT"]) for r in repair] == [(BASE, .2, 1), (DEPOT, .7, 1), (WORKSHOP, 1, 1)])
        allocation = records(source["StockAllocation"])
        check(tag + " 1/0/0 opening stock", [(r["STID"], r["STSIZ"]) for r in allocation] == [(BASE, 1), (DEPOT, 0), (WORKSHOP, 0)])
        links = records(source["StationStructure"])
        check(tag + " two 2h FAST links", [(r["STID"], r["MSTID"], r["TFRMS"], r["TTOMS"], r["OPOL"]) for r in links] == [(BASE, DEPOT, 2, 2, "FAST"), (DEPOT, WORKSHOP, 2, 2, "FAST")])
        control = records(source["Control"])[0]
        collections = records(source["ResultCollection"])
        check(tag + " 60h model and collection horizon", control["RSEED"] == str(seed) and control["SIMPE"] == control["RCEND"] == 60 and {r["RTYPE"] for r in collections} == {"MISSION", "SYSTEM"} and all(r["RCEND"] == 60 for r in collections))

        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        check(tag + " invocation SHA and identity", sha(run / "invocation.json") == closure["invocation_sha256"] and invocation["run_id"] == closure["run_id"] == run.name)
        check(tag + " session0 SSH and queue", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        identity = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
        if gui is None: gui = identity
        check(tag + " preserved GUI identity", identity == gui and identity[:2] == (13340, 1) and all(s["gui_preserved"] for s in steps))
        check(tag + " five successful steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" for s in steps))
        check(tag + " unchanged source closure", closure["source_hashes_before"] == closure["source_hashes_after"] and closure["error"] is None)
        for key, recorded in closure["source_hashes_before"].items():
            actual = expected_sha if key == "input" else sha(Path(invocation["planned_check"]["executable"])) if key == "python" else current_sha[key]
            check(tag + f" source seal {key}", recorded == actual)
        raw_count += len(closure["raw"])
        check(tag + " twelve raw seals", len(closure["raw"]) == 12)
        for name, seal in closure["raw"].items():
            path = run / name
            check(tag + " raw " + name, path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        check(tag + " sealed raw file set", set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
        exported = tables(read(run / "roundtrip-raw.json", native=True))
        populated = [name for name, table in source.items() if rows(table)]
        check(tag + " source row-table count", len(populated) == 21)
        for name in populated:
            before, after = source[name], exported.get(name)
            check(tag + " exact roundtrip " + name, after is not None and [c["name"] for c in before["columns"]] == [c["name"] for c in after["columns"]] and rows(before) == rows(after))
        native_log = (run / "run.log").read_text(encoding="utf-8-sig")
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", native_log)
        check(tag + " converter summary", conversion is not None)
        diagnostics = tuple(map(int, conversion.groups())) if conversion else None
        check(tag + " zero-error conversion", diagnostics == (0, 1, 0) and "(warning #108)" in native_log)
        check(tag + " nonempty SXO/event/report", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        items, totals = physical_trace(log)
        check(tag + " unique failed-item identities", totals["first"] == totals["unique_ids"] == totals["repair_starts"] == totals["repair_ends"] == totals["restocks"])
        failure_times = [float(x) for x in re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,0> critical random failure added", log)]
        abort_times = [float(x) for x in re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,[^>]+> mission aborted:", log)]
        success_times = [float(x) for x in re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,[^>]+> mission success:", log)]
        system_repair_completions = [float(x) for x in re.findall(r"Time: ([0-9.]+)\s+system SURP task \d+ on <TEACH-AIR-01,0> completed", log)]
        check(tag + " failure and mission abort same event time", failure_times == abort_times and len(failure_times) == len(items), [failure_times, abort_times])
        check(tag + " completed system repairs for each failure", len(system_repair_completions) == len(items))
        check(tag + " three mission outcomes", len(abort_times) + len(success_times) == 3)
        for item in items:
            verify_item(seed, item)
            all_count[item["classification"]] += 1
        if items:
            first_observed += 1
            first_count[items[0]["classification"]] += 1
        all_items += len(items)
        check(tag + " transport movement count", totals["movement"] == sum(len(item["expected_legs"]) for item in items))
        report = tables(read(run / "report-raw.json", native=True), "report")
        system, stock, summary = (records(report[name]) for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
        check(tag + " 120 aligned half-hour bins", len(system) == len(stock) == 120 and all(s["STINT"] == t["STINT"] == i / 2 and s["ETINT"] == t["ETINT"] == (i + 1) / 2 for i, (s, t) in enumerate(zip(system, stock))))
        check(tag + " report 60h one replication", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 60)
        check(tag + " report failure/repair counts", sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == len(items))
        check(tag + " terminal ready and base stock", near(system[-1]["NSYRY"], 1) and near(stock[-1]["PNB"], 1))
        per_seed[str(seed)] = {"run_id": run.name, "input_sha256": expected_sha, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "observed_items": [{"id": i["id"], "complexity": i["complexity"], "route": i["classification"], "base_arrival": i["base_arrival"], "repair_start": i["repair_starts"][0][0] if i["repair_starts"] else None, "repair_finish": i["repair_ends"][0][0] if i["repair_ends"] else None, "base_restock": i["base_restocks"][0] if i["base_restocks"] else None} for i in items]}
    check("576 raw SHA seals", raw_count == 48 * 12)
    check("first complexity observed in at least 36 seeds", first_observed >= 36, first_observed)
    for station in (BASE, DEPOT, WORKSHOP):
        check(f"first-item {station} coverage at least 3", first_count[station] >= 3, first_count[station])
    failed = [item for item in checks if not item["pass"]]
    report = {"schema": "independent-e06-three-level-readonly/v1", "reviewer": "a17_static_reviewer", "verdict": "GO bounded 48-seed cumulative DIRPF routing CLI evidence" if not failed else "NO-GO", "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "raw_seals": raw_count, "first_complexity_seed_count": first_observed, "first_routing_counts": dict(sorted(first_count.items())), "all_failed_item_count": all_items, "all_routing_counts": dict(sorted(all_count.items())), "per_seed": per_seed, "diagnostic_predecessor": "v1.0.0 rejected: inherited 36-hour ResultCollection windows; its 48 local diagnostic runs are excluded", "limitations": ["Observed classifications at DIRPF .2/.7/1 do not establish exact population proportions or random-generator independence.", "No sampled complexity exactly equals a threshold unless explicitly visible in per-seed evidence; equality semantics are not inferred.", "StockTotalResults is an aggregate reporting scope; station-level backorders and transport identities are traced from native events.", "SURPF, discard, PRU/DU, multiple bases, resource contention, GUI behavior and cross-engine parity are outside scope."]}
    OUT.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "failures": failed[:12], "first_routing_counts": report["first_routing_counts"], "all_items": all_items, "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))


if __name__ == "__main__": main()
