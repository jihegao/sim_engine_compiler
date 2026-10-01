"""Independent read-only replay of sealed E06.var01 local/upstream runs.

Standard library only. Author build, checker, and validator are never imported.
The frozen sources and raw runs are read, not modified.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
PARENT = ROOT / "E05-local-repair-reissue-v1.0.0" / "native-input.json"
SUPPORT = ROOT / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
RUNS = {name: CASE / "runs" / f"e06-{name}-v100-ssh-20261002-01" for name in ("local", "upstream")}
FILES = {
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
checks = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native=False):
    content = path.read_text(encoding="utf-8-sig")
    if native: content = re.sub(r",(?=\s*[}\]])", "", content)
    return json.loads(content)


def check(name, passed, detail=None):
    checks.append({"name": name, "pass": bool(passed), **({"detail": detail} if detail is not None else {})})


def tables(doc, root="model"):
    return {table["name"]: table for table in doc[root]["tables"]}


def col(table, name):
    return [c["name"] for c in table["columns"]].index(name)


def rows(table):
    return [(inst["instance_name"], row) for inst in table["instances"] for row in inst["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for _, row in rows(table)]


def near(x, y, tolerance=2e-5):
    return math.isclose(x, y, abs_tol=tolerance, rel_tol=0)


def generate(parent, support, arm):
    doc = copy.deepcopy(parent)
    t, s = tables(doc), tables(support)
    desc = t["ProblemDescription"]
    desc["instances"][0]["rows"][0][col(desc, "PDESC")] = f"E06 cumulative direct-repair boundary {arm}"
    for name in ("Station", "StationStructure"):
        t[name]["instances"][0]["rows"].append(copy.deepcopy(s[name]["instances"][0]["rows"][-1]))
    repair = t["ItemRepair"]
    original = copy.deepcopy(repair["instances"][0]["rows"][0])
    repair["instances"][0]["rows"][0][col(repair, "DIRPF")] = 1.0 if arm == "local" else 0.0
    original[col(repair, "STID")] = "DEPOT-01"
    original[col(repair, "DIRPF")] = 1.0
    repair["instances"][0]["rows"].append(original)
    stock = t["StockAllocation"]
    depot = copy.deepcopy(stock["instances"][0]["rows"][0])
    depot[col(stock, "STID")] = "DEPOT-01"
    depot[col(stock, "STSIZ")] = 0
    stock["instances"][0]["rows"].append(depot)
    return doc


def times(log, phrase):
    return [float(x) for x in re.findall(r"Time: ([0-9.]+)\s+" + phrase, log)]


def main():
    contract = read(CASE / "contract.json")
    parent, support = read(PARENT), read(SUPPORT)
    check("E05 parent SHA", sha(PARENT) == contract["parent"]["input_sha256"])
    check("E04 support SHA", sha(SUPPORT) == contract["support_prerequisite"]["input_sha256"])
    check("manual SHA", sha(FILES["manual"]) == contract["source"]["manual_pdf_sha256"])
    source_sha = {key: sha(path) for key, path in FILES.items()}
    parent_tables = tables(parent)
    inputs = {}
    outcomes = {}
    raw_count = 0
    gui = None
    for arm, run in RUNS.items():
        source = CASE / f"{arm}-input.json"
        rebuilt = generate(parent, support, arm)
        frozen_bytes = (json.dumps(rebuilt, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        check(f"{arm} exact parent/support-derived bytes", source.read_bytes() == frozen_bytes)
        check(f"{arm} frozen source hash", sha(source) == contract["native_input_sha256"][arm])
        check(f"{arm} copied native input", source.read_bytes() == (run / "input.json").read_bytes())
        inputs[arm] = tables(read(source))
        changed = {name for name in inputs[arm] if inputs[arm][name] != parent_tables.get(name)}
        check(f"{arm} exact five-table parent delta", changed == {"ProblemDescription", "Station", "StationStructure", "ItemRepair", "StockAllocation"} and set(inputs[arm]) == set(parent_tables), sorted(changed))
        item_repairs = records(inputs[arm]["ItemRepair"])
        check(f"{arm} base/depot DIRPF boundary", len(item_repairs) == 2 and [(r["STID"], r["DIRPF"], r["DIRPT"]) for r in item_repairs] == [("BASE-01", 1.0 if arm == "local" else 0.0, 1.0), ("DEPOT-01", 1.0, 1.0)])
        allocations = records(inputs[arm]["StockAllocation"])
        check(f"{arm} one base spare and zero depot stock", [(r["STID"], r["STSIZ"]) for r in allocations] == [("BASE-01", 1), ("DEPOT-01", 0)])
        link = records(inputs[arm]["StationStructure"])
        check(f"{arm} two-hour two-way support link", len(link) == 1 and link[0]["STID"] == "BASE-01" and link[0]["MSTID"] == "DEPOT-01" and link[0]["TFRMS"] == link[0]["TTOMS"] == 2)

        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        check(f"{arm} invocation SHA/identity", closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["run_id"] == closure["run_id"] == run.name and invocation["variant"] == arm)
        check(f"{arm} session-0 SSH/sshd", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"])
        check(f"{arm} host queue mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        identity = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
        if gui is None: gui = identity
        check(f"{arm} GUI PID/start continuity", identity == gui and identity[:2] == (13340, 1) and all(s["gui_preserved"] for s in steps))
        check(f"{arm} five successful CLI/check steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" for s in steps))
        check(f"{arm} unchanged sealed source", closure["source_hashes_before"] == closure["source_hashes_after"] and closure["error"] is None)
        for key, expected in closure["source_hashes_before"].items():
            actual = sha(source) if key == "input" else sha(Path(invocation["planned_check"]["executable"])) if key == "python" else source_sha[key]
            check(f"{arm} source seal {key}", actual == expected)
        raw_count += len(closure["raw"])
        check(f"{arm} twelve raw file seals", len(closure["raw"]) == 12)
        for name, seal in closure["raw"].items():
            path = run / name
            check(f"{arm} raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        check(f"{arm} raw seal complete", set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
        exported = tables(read(run / "roundtrip-raw.json", native=True))
        populated = [name for name, table in inputs[arm].items() if rows(table)]
        check(f"{arm} 21 row-containing source tables", len(populated) == 21)
        for name in populated:
            before, after = inputs[arm][name], exported.get(name)
            check(f"{arm} exact {name} roundtrip", after is not None and [c["name"] for c in before["columns"]] == [c["name"] for c in after["columns"]] and rows(before) == rows(after))
        native_log = (run / "run.log").read_text(encoding="utf-8-sig")
        summary = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", native_log)
        check(f"{arm} converter summary", summary is not None)
        diagnostics = tuple(map(int, summary.groups())) if summary else None
        check(f"{arm} zero-error classified conversion", diagnostics == (0, 1, 0) and "(warning #108)" in native_log)
        check(f"{arm} nonempty SXO/log/report", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        failures = times(log, r"<TEACH-AIR-01,0> critical random failure added")
        expected_failures = [9.25527, 21.9597, 33.3079] if arm == "local" else [9.25527]
        check(f"{arm} all observed critical failures", failures == expected_failures, failures)
        aborted = times(log, r"<BASIC-MISSION,[^>]+> mission aborted:")
        success = times(log, r"<BASIC-MISSION,[^>]+> mission success:")
        check(f"{arm} mission outcome times", aborted == expected_failures and success == ([] if arm == "local" else [22.0, 34.0]))
        first_demand = "Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,1>"
        first_spare = "Take replacement item <TEACH-LRU-01,0,0> from stock"
        check(f"{arm} first failed LRU #1 and spare #0", f"Time: 9.75527 <TEACH-LRU-01,0,BASE-01,0> {first_demand}" in log and f"Time: 9.75527 <TEACH-LRU-01,0,BASE-01,0> {first_spare}" in log)
        check(f"{arm} first REMOVE then REPLACE", "Time: 9.75527  remove subitem" in log and "Time: 9.92193  fit subitem" in log and "Time: 10.2553  fit subitem" in log)
        repairs = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,(BASE-01|DEPOT-01),0> Start repair of item <TEACH-LRU-01,0,(\d+)>", log)
        restocks = re.findall(r"Time: ([0-9.]+) <TEACH-LRU-01,0,(BASE-01|DEPOT-01),0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", log)
        if arm == "local":
            check("local three base repair starts", repairs == [("9.92193", "BASE-01", "1"), ("22.1667", "BASE-01", "2"), ("33.9746", "BASE-01", "3")], repairs)
            check("local three base repaired identities restock", restocks == [("10.9219", "BASE-01", "1"), ("23.1667", "BASE-01", "2"), ("34.9746", "BASE-01", "3")], restocks)
            check("local repaired #1/#2 reissued", "Time: 22 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock" in log and "Time: 33.8079 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,2> from stock" in log)
            check("local no physical transport", not re.search(r"transport task \d+ starts with 1 items/systems", log))
        else:
            check("upstream first repair at depot", repairs == [("11.9219", "DEPOT-01", "1")], repairs)
            check("upstream base item #1 restock", restocks == [("14.9219", "BASE-01", "1")], restocks)
            chain = (("9.92193", "transport task 0 starts with 1 items/systems, transport time: 2"), ("11.9219", "transport task 0 arrives with 1 items/systems"), ("12.9219", "transport task 2 starts with 1 items/systems, transport time: 2"), ("14.9219", "transport task 2 arrives with 1 items/systems"))
            check("upstream exact two-hour outward/return timing", all(f"Time: {time}  {event}" in log for time, event in chain))
            check("upstream same #1 physical transport requests", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log and "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log)
            check("upstream depot backorder added and cleared", "Time: 9.92193 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added" in log and "Time: 12.9219 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3" in log)

        report = tables(read(run / "report-raw.json", native=True), "report")
        system, stock, result = (records(report[name]) for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
        check(f"{arm} aligned 72 half-hour bins", len(system) == len(stock) == 72 and all(s["STINT"] == t["STINT"] == i / 2 and s["ETINT"] == t["ETINT"] == (i + 1) / 2 for i, (s, t) in enumerate(zip(system, stock))))
        check(f"{arm} 36-hour one-replication report", len(result) == 1 and result[0]["NREP"] == 1 and result[0]["RTIUP"] == 36)
        check(f"{arm} report failure/repair counts", sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == len(expected_failures))
        check(f"{arm} terminal ready and base stock", near(system[-1]["NSYRY"], 1) and near(stock[-1]["PNB"], 1))
        check(f"{arm} reported NBO zero", all((r["NBO"] or 0) == 0 for r in stock))
        outcomes[arm] = {"run_id": run.name, "input_sha256": sha(source), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "converter_errors_warnings_notes": diagnostics, "critical_failures": failures, "mission_aborts": aborted, "mission_successes": success, "item_repair_starts_time_station_instance": repairs, "base_restock_time_station_instance": restocks, "terminal_ready": system[-1]["NSYRY"], "terminal_stock_PNB": stock[-1]["PNB"]}
    check("only PDESC and base DIRPF differ between arms", {name for name in inputs["local"] if inputs["local"][name] != inputs["upstream"].get(name)} == {"ProblemDescription", "ItemRepair"})
    check("24 raw SHA seals", raw_count == 24)
    failed = [item for item in checks if not item["pass"]]
    report = {"schema": "independent-e06-var01-readonly/v1", "reviewer": "a17_static_reviewer", "verdict": "GO bounded fixed-seed DIRPF station-routing CLI evidence" if not failed else "NO-GO", "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "raw_seals": raw_count, "outcomes": outcomes, "limitations": ["The two arms diverge in later stochastic failures (local three, upstream one); only the shared first failure is a matched routing contrast.", "Native StockTotalResults.NBO remains zero even though the upstream event log records a depot backorder from 9.92193 to 12.9219; event-level and aggregate report scopes differ.", "Boundary DIRPF 1/0 at one seed does not establish intermediate accumulated-fraction behavior, GUI behavior, or cross-engine equivalence."]}
    OUT.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "failures": failed, "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))


if __name__ == "__main__": main()
