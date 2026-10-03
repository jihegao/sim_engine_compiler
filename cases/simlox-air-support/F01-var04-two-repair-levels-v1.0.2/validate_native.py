"""Read-only author replay of the F01.var04 local/depot nested repair run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/f01-var04-levels-v102-ssh-20261004-01"
EARLIER = ROOT / "F01-var04-two-repair-levels-v1.0.1/runs/f01-var04-levels-v101-ssh-20261004-01"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def report_rows(report: dict, name: str) -> list[dict]:
    t = next(t for t in report["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row)) for i in t["instances"] for row in i["rows"]]


def scan(log: str, pattern: str) -> list[tuple]:
    return [(float(m.group(1)), *m.groups()[1:]) for m in re.finditer(pattern, log, re.M)]


def main() -> None:
    failures: list[str] = []
    checks = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    parent = contract["accepted_behavior_parent"]
    donor = contract["accepted_level_allocation_reference"]
    ck((contract["case_id"], contract["variant_id"], contract["version"]) ==
       ("F01", "F01.var04", "1.0.2-candidate"), "contract identity")
    ck(sha(HERE / "native-input.json") == contract["native_input_sha256"], "frozen input")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen diff")
    diff = load(HERE / "exact-diff.json")
    ck(diff["input_sha256"] == contract["native_input_sha256"] and
       diff["parent_sha256"] == parent["input_sha256"] and
       [x["table"] for x in diff["changed_tables"]] ==
       ["ProblemDescription", "Control", "Station", "StationStructure", "ItemRepair", "Tasks",
        "StockAllocation", "ResultCollection", "TaskCategory", "TaskLevel", "MaintenanceAllocation"], "exact source delta")
    for label, pin in (("parent", parent), ("donor", donor)):
        base = ROOT / pin["package"]
        ck(sha(base / pin["input"]) == pin["input_sha256"], f"{label} input")
        ck(sha(base / "runs" / pin["run_id"] / "closure.json") == pin["closure_sha256"], f"{label} native closure")
        ck(sha(base / "evidence-index.json") == pin["evidence_index_sha256"], f"{label} evidence index")
    for key in ("prior_excluded_diagnostic", "second_excluded_diagnostic"):
        pin = contract[key]
        ck(sha(ROOT / pin["package"] / "runs" / pin["run_id"] / "closure.json") == pin["closure_sha256"], f"{key} closure")

    invocation, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN.name and invocation["variant_id"] == "F01.var04", "run identity")
    ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
    ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "host queue and GUI")
    ck(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"), "successful closure")
    ck(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "stable source through native run")
    sources = {"input": HERE / "native-input.json", "parent": ROOT / parent["package"] / parent["input"],
               "parent_closure": ROOT / parent["package"] / "runs" / parent["run_id"] / "closure.json",
               "parent_evidence_index": ROOT / parent["package"] / "evidence-index.json",
               "level_allocation_reference": ROOT / donor["package"] / donor["input"],
               "level_allocation_reference_closure": ROOT / donor["package"] / "runs" / donor["run_id"] / "closure.json",
               "level_allocation_reference_evidence_index": ROOT / donor["package"] / "evidence-index.json",
               "excluded_diagnostic_closure": ROOT / contract["prior_excluded_diagnostic"]["package"] / "runs" / contract["prior_excluded_diagnostic"]["run_id"] / "closure.json",
               "second_excluded_diagnostic_closure": EARLIER / "closure.json",
               "exact_diff": HERE / "exact-diff.json", "contract": HERE / "contract.json",
               "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
               "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}
    for key, p in sources.items():
        ck(closure["source_hashes_before"][key] == sha(p), f"source seal {key}")
    ck(set(closure["raw"]) == RAW, "twelve raw files")
    for name, meta in closure["raw"].items():
        p = RUN / name
        ck(p.is_file() and p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"], f"raw seal {name}")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five guarded steps")
    ck((RUN / "model.sxi").stat().st_size > 1000 and (RUN / "model.sxo").stat().st_size > 1000, "nonempty SXI/SXO")
    source = parse_native(HERE / "native-input.json")
    authored = populated(source)
    exported = populated(parse_native(RUN / "roundtrip-raw.json"))
    rt = load(RUN / "roundtrip-validation.json")
    ck(rt["passed"] and not rt["differences"] and len(authored) == 25, "25-table roundtrip")
    for name, value in authored.items():
        ck(exported.get(name) == value, f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 2" in runlog and
       runlog.count("(warning #108)") == 1 and runlog.count("(notice #2034)") == 2 and
       all(f"Item type ignored for task category-associated item: {item}" in runlog
           for item in ("TEACH-LRU-01", "TEACH-SRU-01")), "converter message set")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    older = (EARLIER / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(older.splitlines()[2:] == log.splitlines()[2:len(older.splitlines())], "first 36h event prefix unchanged")
    faults = scan(log, r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added")
    lru_demands = scan(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>")
    lru_issues = scan(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    lru_returns = scan(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
    sru_demands = scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,(\d+)>")
    sru_issues = scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Take replacement item <TEACH-SRU-01,0,(\d+)> from stock")
    sru_returns = scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,(\d+)> to stock")
    ck(all(len(x) == 3 for x in (faults, lru_demands, lru_issues, lru_returns, sru_demands, sru_issues, sru_returns)), "three complete physical cycles")
    if all(len(x) == 3 for x in (lru_demands, lru_issues, lru_returns, sru_demands, sru_issues, sru_returns)):
        for i in range(3):
            ck(lru_demands[i][1] == lru_returns[i][1] and lru_demands[i][0] <= lru_issues[i][0] < lru_returns[i][0], f"LRU physical identity cycle {i}")
            ck(sru_demands[i][1] == sru_returns[i][1] and sru_demands[i][0] <= sru_issues[i][0] < sru_returns[i][0] < 42, f"SRU physical identity cycle {i}")
        for i in (1, 2):
            ck(lru_issues[i][1] == lru_returns[i-1][1] and lru_returns[i-1][0] < lru_issues[i][0], f"repaired LRU reissue {i}")
            ck(sru_issues[i][1] == sru_returns[i-1][1] and sru_returns[i-1][0] < sru_issues[i][0], f"repaired SRU reissue {i}")
    for item, site, count, duration in (("LRU", "BASE-01", 3, .75), ("SRU", "DEPOT-01", 3, 1.0)):
        typ = "SURP" if item == "LRU" else "DIRP"
        starts = scan(log, rf"^Time: ([\d.]+) <TEACH-{item}-01,0,{site},0> Start repair of item <TEACH-{item}-01,0,(\d+)>")
        ends = scan(log, rf"^Time: ([\d.]+) <TEACH-{item}-01,0,{site},0> Finished repair of item <TEACH-{item}-01,0,(\d+)>")
        task_starts = scan(log, rf"^Time: ([\d.]+)  item {typ} task \d+ on <TEACH-{item}-01,0,(\d+)> started")
        task_ends = scan(log, rf"^Time: ([\d.]+)  item {typ} task \d+ on <TEACH-{item}-01,0,(\d+)> completed")
        ck(all(len(x) == count for x in (starts, ends, task_starts, task_ends)), f"{item} site/task counts")
        for i in range(min(map(len, (starts, ends, task_starts, task_ends)))):
            ck(starts[i][1] == ends[i][1] == task_starts[i][1] == task_ends[i][1] and
               abs(ends[i][0] - starts[i][0] - duration) < 1e-4, f"{item} {duration}h repair {i}")
    ck(not scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Start repair of item") and
       not scan(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item"), "repair site separation")
    outbound = scan(log, r"^Time: ([\d.]+)  transport request <<TEACH-SRU-01,0,(\d+)>,<TEACH-SRU-01,0,BASE-01,0>,<TEACH-SRU-01,0,DEPOT-01,0>> started")
    inbound = scan(log, r"^Time: ([\d.]+)  transport request <<TEACH-SRU-01,0,(\d+)>,<TEACH-SRU-01,0,DEPOT-01,0>,<TEACH-SRU-01,0,BASE-01,0>> started")
    depot_arrivals = scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-SRU-01,0,(\d+)>")
    ck(all(len(x) == 3 for x in (outbound, inbound, depot_arrivals)) and
       len(scan(log, r"^Time: ([\d.]+)  transport task \d+ arrives with 1 items/systems")) == 6, "three complete round trips")
    if all(len(x) == 3 for x in (outbound, inbound, depot_arrivals, sru_returns)):
        for i in range(3):
            ck(outbound[i][1] == inbound[i][1] == depot_arrivals[i][1] == sru_returns[i][1] and
               abs(depot_arrivals[i][0] - outbound[i][0] - 2) < 1e-3 and
               abs(sru_returns[i][0] - inbound[i][0] - 2) < 1e-3, f"SRU transport identities/time {i}")
    ck(len(scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,DEPOT-01,0> Backorder added")) == 3 and
       len(scan(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,DEPOT-01,0> Backorder removed")) == 3, "three resolved internal backorders")
    ck("requests resources: no resources needed" in log and "resource shortage" not in log.lower(), "resource ledger no shortage")
    ck(len(scan(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:")) == 3 and
       len(scan(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:")) == 0, "three aborted missions")
    for item in ("LRU", "SRU"):
        levels = re.findall(rf"^  Stock at: <TEACH-{item}-01,0,BASE-01,0> Level: (\d+) Items:(.*)$", log, re.M)
        ck(bool(levels) and levels[0][0] == levels[-1][0] == "1" and len(re.findall(r"<TEACH-" + item + r"-01,0,\d+>", levels[-1][1])) == 1,
           f"{item} base stock restored")
    depot_levels = re.findall(r"^  Stock at: <TEACH-SRU-01,0,DEPOT-01,0> Level: (\d+) Items:(.*)$", log, re.M)
    ck(bool(depot_levels) and all(level == "0" for level, _ in depot_levels), "depot SRU stock zero")

    report = parse_native(RUN / "report-raw.json")
    old_report = parse_native(EARLIER / "report-raw.json")
    names = {t["name"] for t in report["report"]["tables"]}
    ck(names == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary, system, stock = (report_rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    old_system, old_stock = (report_rows(old_report, n) for n in ("SystemResults", "StockTotalResults"))
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 0, "one repetition, zero success")
    ck(len(system) == len(stock) == 84 and len(old_system) == len(old_stock) == 72, "84 report bins")
    for i, (sy, st) in enumerate(zip(system, stock)):
        ck(sy["STINT"] == st["STINT"] == i / 2 and sy["ETINT"] == st["ETINT"] == (i + 1) / 2, f"grid bin {i}")
        if i < 72:
            ck(sy == old_system[i] and st == old_stock[i], f"unchanged original bin {i}")
        else:
            sy0 = dict(old_system[-1], STINT=i / 2, ETINT=(i + 1) / 2)
            st0 = dict(old_stock[-1], STINT=i / 2, ETINT=(i + 1) / 2)
            ck(sy == sy0 and st == st0, f"quiescent extension bin {i}")
    ck(sum(row["NFAIL"] for row in system) == sum(row["NREPT"] for row in system) == len(faults) == 3, "three failures and system repairs")
    ck(sum(row["NDF"] for row in stock) == len(lru_demands) == 3 and
       sum(row["NWT"] for row in stock) == len(lru_demands) == 3, "stock demand/wait report")
    ck(system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and stock[-1]["NBO"] == 0 and
       all(row["NBO"] == 0 for row in stock), "terminal ready and no aggregate stock backorder")
    result = {"schema": "simlox-f01-var04-v102-author-replay/v1", "case_id": "F01.var04",
              "passed": not failures, "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "run_id": RUN.name, "closure_sha256": sha(RUN / "closure.json"),
              "physical_cycles": len(lru_demands), "depot_sru_repairs": len(depot_arrivals),
              "outbound_sru_transports": len(outbound), "inbound_sru_transports": len(inbound),
              "system_report_bins": len(system), "stock_report_bins": len(stock)}
    (HERE / "author-validation-2026-10-04.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("passed", "checks_passed", "checks_total", "failures")}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
