"""Independent read-only I02.var08 replay from source and sealed native evidence."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "E08-var01-immediate-lateral-v1.0.2"
NATIVE = CASE / "runs/i02-var08-lateral-out-v100-ssh-20261002-01"
REPORT_RUNS = {p: CASE / f"runs/i02-var08-{p}-report-v100-ssh-20261002-01" for p in ("base01", "base02", "depot")}
OUT = CASE / "review/independent-readonly-2026-10-02.json"
checks = 0
failures: list[str] = []


def ck(label: str, good: bool) -> None:
    global checks
    checks += 1
    if not good:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path, native: bool = False):
    s = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", s) if native else s)


def tables(data, report: bool = False):
    return {t["name"]: t for t in data["report" if report else "model"]["tables"]}


def rows(table):
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, r)) for inst in table["instances"] for r in inst["rows"]]


contract, diff = parse(CASE / "contract.json"), parse(CASE / "exact-diff.json")
parent_path = PARENT_CASE / "on-input.json"
donor_path = CASE.parent / "I02-var02-out-transfer-v1.0.0/native-input.json"
child_path = CASE / "native-input.json"
parent, child = tables(parse(parent_path)), tables(parse(child_path))
ck("accepted E08 parent source SHA", sha(parent_path) == contract["direct_parent"]["sha256"] == diff["parent_sha256"])
ck("I02 OUT schema donor SHA", sha(donor_path) == contract["transfer_schema_source"]["sha256"])
ck("child source SHA", sha(child_path) == contract["source_sha256"] == diff["child_sha256"])
ck("exact diff SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
ck("exact table delta", set(child)-set(parent) == {"ItemTransfer"} and set(parent)-set(child) == set() and {n for n in parent if parent[n] != child[n]} == {"ProblemDescription"} and diff["unchanged_table_count"] == 33)
ck("diff added table", diff["added_tables"] == {"ItemTransfer": child["ItemTransfer"]} and diff["removed_tables"] == {})
ck("diff description before/after", diff["changed_tables"]["ProblemDescription"]["before"] == parent["ProblemDescription"] and diff["changed_tables"]["ProblemDescription"]["after"] == child["ProblemDescription"])
ck("single h2 empty-base OUT", rows(child["ItemTransfer"]) == [{"STFID": "BASE-01", "STTID": "<OUTSIDE>", "IID": "TEACH-LRU-01", "TFTIME": 2, "TFQTY": 1, "TFDT": 0, "NOTE": None}])
ck("ENLAT remains enabled", rows(child["Control"])[0]["ENLAT"] == "Y" and child["Control"] == parent["Control"])
ck("peer/depot stock source unchanged", child["StockAllocation"] == parent["StockAllocation"])

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
for key, path in installed.items():
    field = {"manual": "manual_pdf", "dictionary": "table_dictionary", "simlox_exe": "simlox_exe"}[key]
    ck(f"installed {key} SHA", sha(path) == contract["installed_source_sha256"][field])

inv, closure = parse(NATIVE / "invocation.json"), parse(NATIVE / "closure.json")
ck("native invocation SHA", closure["invocation_sha256"] == sha(NATIVE / "invocation.json"))
ck("native source stable", inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
ck("session0 SSH queue GUI", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
source_paths = {
    "input": child_path, "parent": parent_path, "transfer_schema_source": donor_path,
    "contract": CASE / "contract.json", "manual": installed["manual"], "dictionary": installed["dictionary"],
    "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"],
}
for key, path in source_paths.items():
    ck(f"native source pin {key}", closure["source_hashes_before"][key] == sha(path))
ck("native input copied", sha(NATIVE / "input.json") == sha(child_path))
for filename, seal in closure["raw"].items():
    path = NATIVE / filename
    ck(f"native/{filename} bytes", path.stat().st_size == seal["bytes"])
    ck(f"native/{filename} SHA", sha(path) == seal["sha256"])
steps = parse(NATIVE / "steps.json")
ck("five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
for step in steps:
    ck(f"native step {step['name']}", step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)
runlog = (NATIVE / "run.log").read_text(encoding="cp1252")
ck("zero conversion errors", "Input conversion completed. Errors: 0" in runlog and "(error #" not in runlog)
ck("valid SXO", (NATIVE / "model.sxo").stat().st_size > 4)
exported = tables(parse(NATIVE / "roundtrip-raw.json", True))
populated = {name for name, t in child.items() if rows(t)}
ck("25 populated source tables", len(populated) == 25)
for name in sorted(populated):
    ck(f"exact roundtrip {name}", exported.get(name) == child[name])

selected = {}
default_report = tables(parse(NATIVE / "report-raw.json", True), True)
for pos, directory in REPORT_RUNS.items():
    invocation, sealed = parse(directory / "invocation.json"), parse(directory / "closure.json")
    ck(f"{pos} invocation SHA", sealed["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{pos} stable report source", invocation["source_hashes_before"] == sealed["source_hashes_before"] == sealed["source_hashes_after"])
    ck(f"{pos} parent closure", invocation["source_run_id"] == NATIVE.name and invocation["source_closure_sha256"] == sha(NATIVE / "closure.json"))
    ck(f"{pos} session0 SSH queue GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    settings = CASE / f"runs/report-settings/{'base-01' if pos == 'base01' else 'base-02' if pos == 'base02' else 'depot'}-item.sxs"
    for key, path in {"sxo": NATIVE / "model.sxo", "settings": settings, "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1"}.items():
        ck(f"{pos} {key} pin", sealed["source_hashes_before"][key] == sha(path))
    ck(f"{pos} report command and exit", str(settings) in invocation["arguments"] and str(NATIVE / "model.sxo") in invocation["arguments"] and "-report -rpts" in invocation["arguments"] and "-rjexport" in invocation["arguments"] and sealed["exit_code"] == 0 and sealed["error"] is None)
    for filename, seal in sealed["raw"].items():
        path = directory / filename
        ck(f"{pos}/{filename} bytes", path.stat().st_size == seal["bytes"])
        ck(f"{pos}/{filename} SHA", sha(path) == seal["sha256"])
    selected[pos] = tables(parse(directory / "item-report-raw.json", True), True)
    ck(f"{pos} ItemResults table selected", "ItemResults" in selected[pos] and "ItemResultsTotal" in selected[pos])
    for name in default_report.keys() & selected[pos].keys():
        ck(f"{pos} default/selected {name} same rows", rows(default_report[name]) == rows(selected[pos][name]))

item = {p: rows(selected[p]["ItemResults"]) for p in REPORT_RUNS}
system = rows(selected["base01"]["SystemResults"])
stock = rows(selected["base01"]["StockTotalResults"])
missions = rows(selected["base01"]["MissionResults"])
ck("three item, system, stock, mission 72-bin ledgers", all(len(v) == 72 for v in item.values()) and len(system) == len(stock) == len(missions) == 72)
for i in range(72):
    h = i/2
    for pos, station in (("base01", "BASE-01"), ("base02", "BASE-02"), ("depot", "DEPOT-01")):
        r = item[pos][i]
        ck(f"{pos} bin {i} identity/grid", r["IID"] == "TEACH-LRU-01" and r["STID"] == station and r["STINT"] == h and r["ETINT"] == h+.5)
    ck(f"system/stock bin {i} grid", system[i]["STINT"] == stock[i]["STINT"] == h and system[i]["ETINT"] == stock[i]["ETINT"] == h+.5)
    ck(f"mission bin {i} grid", missions[i]["STINT"] == h and missions[i]["ETINT"] == h+.5)
    ck(f"base01 bin {i} stock stays zero", item["base01"][i]["STSZ"] == item["base01"][i]["STOHA"] == 0)
    ck(f"base01 bin {i} ordinary backorder", item["base01"][i]["NBO"] == (0 if h < 10 else 1))
    ck(f"base02 bin {i} peer stock", item["base02"][i]["STSZ"] == 1 and item["base02"][i]["STOHA"] == (0 if 10 <= h < 11 else 1))
    expected_depot = 1 if h < 10 or h >= 14.5 else 0 if h < 14 else .6666666865348816
    ck(f"depot bin {i} stock", item["depot"][i]["STSZ"] == 1 and abs(item["depot"][i]["STOHA"] - expected_depot) < 1e-6)
    ck(f"stock bin {i} aggregate NBO", stock[i]["NBO"] == (0 if h < 10 else 1))
    expected_requested = 1 if 8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34 else 0
    ck(f"mission bin {i} requested/accepted", missions[i]["MTREQ"] == missions[i]["STREQ"] == expected_requested and missions[i]["MTACC"] == missions[i]["STACC"] == (1 if 8 <= h < 10 else 0))
    if h >= 10.5:
        ck(f"system bin {i} remains not-ready/waiting", system[i]["NSYRY"] == 0 and system[i]["NSYWI"] == 1)
    if h < 7:
        ck(f"system bin {i} initially ready", system[i]["NSYRY"] == 1)
for pos, item_rows in item.items():
    total = rows(selected[pos]["ItemResultsTotal"])[0]
    ck(f"{pos} total nominal/onhand integrals", abs(total["STSZ"] - sum(r["STSZ"] for r in item_rows)/72) < 1e-6 and abs(total["STOHA"] - sum(r["STOHA"] for r in item_rows)/72) < 1e-6)
ck("terminal no aircraft ready", system[-1]["NSYRY"] == 0 and system[-1]["NSYUA"] == 1)
summary = rows(selected["base01"]["ResultSummary"])[0]
ck("summary failed/cancelled outcomes", summary["MSUF"] == 0 and abs(summary["MTMF"] - 1/3) < 1e-6)

parent_report_dir = PARENT_CASE / "runs/e08-on-base01-report-v102-ssh-20261002-01"
parent_report_seal = parse(parent_report_dir / "closure.json")
ck("accepted E08 control report sealed", sha(parent_report_dir / "item-report-raw.json") == parent_report_seal["raw"]["item-report-raw.json"]["sha256"])
control = tables(parse(parent_report_dir / "item-report-raw.json", True), True)
ck("control terminal ready and mission success", rows(control["SystemResults"])[-1]["NSYRY"] == 1 and abs(rows(control["ResultSummary"])[0]["MSUF"] - 2/3) < 1e-6)
for pos in ("base02", "depot"):
    prior_dir = PARENT_CASE / f"runs/e08-on-{pos}-report-v102-ssh-20261002-01"
    prior_closure = parse(prior_dir / "closure.json")
    ck(f"control {pos} selected report sealed", sha(prior_dir / "item-report-raw.json") == prior_closure["raw"]["item-report-raw.json"]["sha256"])
    prior = tables(parse(prior_dir / "item-report-raw.json", True), True)
    for i, (a,b) in enumerate(zip(item[pos], rows(prior["ItemResults"]))):
        ck(f"{pos} bin {i} item metrics same as lateral control", a == b)

log = (NATIVE / "model.log").read_text(encoding="cp1252")
events = [
    "Time: 2  item transfer task 0 (OUT)  created: starting from <TEACH-LRU-01,0,BASE-01,0>",
    "Time: 2 <TEACH-LRU-01,0,BASE-01,0> Item transfer demand arrives from OUT-transfer",
    "Time: 2 <TEACH-LRU-01,0,BASE-01,0> Item transfer backorder added",
    "Time: 2  item transfer task 0 (OUT)  starts with 0 items, transfer time: 0",
    "Time: 2  item transfer task 0 (OUT)  arrives with 0 items",
    "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added",
    "Time: 10 <TEACH-LRU-01,0,BASE-02,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
    "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
    "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Item transfer backorder removed",
    "Time: 10.5  item transfer task 1 (OUT)  starts with 1 items, transfer time: 0",
    "Time: 10.5  item transfer task 1 (OUT)  arrives with 1 items",
    "Time: 11 <TEACH-LRU-01,0,BASE-02,0> Replacement item arrives <TEACH-LRU-01,0,0>",
]
for phrase in events:
    ck(f"physical event {phrase[:66]}", phrase in log)
ck("event chronology", [log.find(p) for p in events] == sorted(log.find(p) for p in events))
ck("no h2 peer issue or transport", "Time: 2 <TEACH-LRU-01,0,BASE-02,0> Take replacement item" not in log and "Time: 2  transport task" not in log)
ck("h10.5 arrival diverted to OUT while ordinary BO remains", "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Item transfer backorder removed" in log and "Backorders at: <TEACH-LRU-01,0,BASE-01,0> Nbr: 1" in log and "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Backorder removed" not in log)
ck("later two missions cancel", "Time: 20.3333 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled" in log and "Time: 32.3333 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission cancelled" in log)
ck("terminal peer/depot stock", "Stock at: <TEACH-LRU-01,0,BASE-02,0> Level: 1 Items:<TEACH-LRU-01,0,0>," in log and "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,2>," in log)

result = {
    "schema": "independent-i02-var08-lateral-out-review/v1", "case": CASE.name,
    "passed": not failures,
    "verdict": "GO: restricted h2 transfer demand does not initiate lateral; NO-GO: global transfer-never-uses-lateral wording" if not failures else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "source_sha256": sha(child_path), "native_closure_sha256": sha(NATIVE / "closure.json"),
    "selected_closure_sha256": {p: sha(d / "closure.json") for p,d in REPORT_RUNS.items()},
    "selected_report_sha256": {p: sha(d / "item-report-raw.json") for p,d in REPORT_RUNS.items()},
    "observations": {
        "h2": "OUT at empty BASE-01 makes transfer BO1; task starts/arrives with zero physical items; stocked BASE-02 peer remains untouched.",
        "h10_to_10_5": "Ordinary aircraft demand triggers lateral BASE-02 item ID1 to BASE-01. Its arrival clears the older transfer BO and a new OUT task sends ID1 out; ordinary aircraft BO remains1.",
        "downstream": "Aircraft never returns ready; scheduled missions 2 and3 cancel at 20.3333 and32.3333. Parent E08 ON control instead finishes ready and has two successful later missions.",
        "terminal": "BASE-01 stock0/BO1, BASE-02 stock1, DEPOT stock1, aircraft not ready at h36. Item, System, Stock and Mission reports reconcile.",
    },
    "limits": [
        "The local h2 no-lateral response is supported. A blanket claim that transfers never use lateral is contradicted as a net-source claim: later ordinary lateral supply feeds the transfer BO and OUTs the peer's item.",
        "The native log does not expose the simulator's internal consideration set at h2; claim only no observed h2 lateral issue/transport and unchanged peer stock.",
        "One IID, one h2 OUT from empty local stock, one stocked peer, IMMEDIATE/DLAYL=N, one seed/CLI. No universal priority, all transfer types, other timing, GUI-visual or cross-engine inference.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": checks, "failures": failures}, indent=2))
sys.exit(0 if result["passed"] else 1)
