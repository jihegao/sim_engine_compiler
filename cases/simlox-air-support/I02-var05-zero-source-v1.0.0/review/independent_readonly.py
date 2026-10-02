"""Independent read-only replay for matched I02.var05 zero-source transfer pair.

Only standard-library parsing of frozen source and native artifacts.  No case
builder, checker, validator, or SIMLOX process is invoked.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-02.json"
RUNS = {arm: CASE / f"runs/i02-var05-zero-{arm}-v100-ssh-20261002-01" for arm in ("control", "child")}
REPORTS = {
    (arm, pos): CASE / f"runs/i02-var05-zero-{'control' if arm == 'control' else 'zero'}-{pos}-v100-ssh-20261002-01"
    for arm in ("control", "child") for pos in ("depot", "base")
}
checks = 0
failures: list[str] = []


def ck(label: str, okay: bool) -> None:
    global checks
    checks += 1
    if not okay:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False):
    s = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", s) if native else s)


def table_map(document, report: bool = False):
    return {t["name"]: t for t in document["report" if report else "model"]["tables"]}


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for inst in table["instances"] for r in inst["rows"]]


contract, diff = load(CASE / "contract.json"), load(CASE / "exact-diff.json")
parent_path = ROOT / "I02-var03-between-transfer-v1.0.0/native-input.json"
inputs = {"parent": parent_path, "control": CASE / "control-input.json", "child": CASE / "native-input.json"}
sources = {arm: load(path) for arm, path in inputs.items()}
maps = {arm: table_map(document) for arm, document in sources.items()}
for arm, key in (("parent", "source_sha256"), ("control", "control_sha256"), ("child", "source_sha256")):
    expected = contract["accepted_parent"][key] if arm == "parent" else contract[key]
    ck(f"{arm} frozen source hash", sha(inputs[arm]) == expected)
ck("exact-diff frozen hash", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
for label, before, after in (("accepted_parent_to_control", "parent", "control"), ("matched_control_to_child", "control", "child")):
    segment = diff[label]
    ck(f"{label} bound source hashes", segment["before_sha256"] == sha(inputs[before]) and segment["after_sha256"] == sha(inputs[after]))
    changed = {name for name in maps[before] if maps[before][name] != maps[after][name]}
    expected = {"ItemTransfer", "ProblemDescription"} if before == "parent" else {"StockAllocation", "ProblemDescription"}
    ck(f"{label} exact changed tables", changed == expected and set(maps[before]) == set(maps[after]) and len(maps[before]) == 32)
    ck(f"{label} diff table keys", set(segment["changed_tables"]) == expected and segment["unchanged_table_count"] == 30)
    for name in sorted(expected):
        ck(f"{label} {name} before", segment["changed_tables"][name]["before"] == maps[before][name])
        ck(f"{label} {name} after", segment["changed_tables"][name]["after"] == maps[after][name])
ck("parent-to-control h2 transfer", rows(maps["control"]["ItemTransfer"])[1] == {"STFID": "DEPOT-01", "STTID": "BASE-01", "IID": "TEACH-LRU-01", "TFTIME": 2, "TFQTY": 1, "TFDT": 0, "NOTE": None})
ck("matched child transfer unchanged", maps["control"]["ItemTransfer"] == maps["child"]["ItemTransfer"])
ck("only depot initial stock changes one to zero", [(r["STID"], r["STSIZ"]) for r in rows(maps["control"]["StockAllocation"])] == [("BASE-01", 0), ("DEPOT-01", 1)] and [(r["STID"], r["STSIZ"]) for r in rows(maps["child"]["StockAllocation"])] == [("BASE-01", 0), ("DEPOT-01", 0)])

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
for key, path in installed.items():
    field = {"manual": "manual_pdf", "dictionary": "table_dictionary", "simlox_exe": "simlox_exe"}[key]
    ck(f"installed {key} fingerprint", sha(path) == contract["installed_source_sha256"][field])

native_closures = {}
for arm, directory in RUNS.items():
    invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    native_closures[arm] = closure
    ck(f"{arm} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{arm} source stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    ck(f"{arm} session0 SSH", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
    ck(f"{arm} queue/GUI", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck(f"{arm} source input and parent pins", invocation["input_sha256"] == sha(inputs[arm]) and invocation["parent_sha256"] == sha(parent_path))
    source_paths = {
        "input": inputs[arm], "parent": parent_path, "contract": CASE / "contract.json",
        "manual": installed["manual"], "dictionary": installed["dictionary"],
        "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
        "diff_checker": CASE / "describe_diff.py",
        "checker": CASE / ("check_roundtrip_control.py" if arm == "control" else "check_roundtrip_zero.py"),
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "runner_script": CASE / ("run_control_native_ssh.ps1" if arm == "control" else "run_zero_native_ssh.ps1"),
        "simlox_exe": installed["simlox_exe"],
    }
    for key, path in source_paths.items():
        ck(f"{arm} source {key} seal", closure["source_hashes_before"][key] == sha(path))
    for filename, seal in closure["raw"].items():
        raw = directory / filename
        ck(f"{arm}/{filename} bytes", raw.stat().st_size == seal["bytes"])
        ck(f"{arm}/{filename} SHA", sha(raw) == seal["sha256"])
    ck(f"{arm} copied input", sha(directory / "input.json") == sha(inputs[arm]))
    steps = load(directory / "steps.json")
    ck(f"{arm} five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"{arm} {step['name']} step", step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)
    log = (directory / "run.log").read_text(encoding="cp1252")
    ck(f"{arm} zero converter errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log and "warning #108" in log and "(error #" not in log)
    ck(f"{arm} valid SXO", (directory / "model.sxo").stat().st_size > 4)
    exported = table_map(load(directory / "roundtrip-raw.json", True))
    populated = {name for name, table in maps[arm].items() if rows(table)}
    ck(f"{arm} 22 populated source tables", len(populated) == 22)
    for name in sorted(populated):
        ck(f"{arm} exact source roundtrip {name}", exported.get(name) == maps[arm][name])

reports = {}
for (arm, pos), directory in REPORTS.items():
    invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    parent_run = RUNS[arm]
    ck(f"{arm}/{pos} invocation SHA", closure["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{arm}/{pos} source stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    ck(f"{arm}/{pos} bound parent SXO", invocation["source_run_id"] == parent_run.name and invocation["source_closure_sha256"] == sha(parent_run / "closure.json"))
    ck(f"{arm}/{pos} session0 SSH, queue, GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    report_paths = {
        "sxo": parent_run / "model.sxo", "exe": installed["simlox_exe"],
        "settings": CASE / ("runs/report-settings/item-position-results.sxs" if pos == "depot" else "runs/report-settings/base-item-position-results.sxs"),
        "runner": CASE / f"probe_{'control' if arm == 'control' else 'zero'}_{pos}_report_ssh.ps1",
    }
    for key, path in report_paths.items():
        ck(f"{arm}/{pos} {key} source pin", closure["source_hashes_before"][key] == sha(path))
    ck(f"{arm}/{pos} guarded report command", str(report_paths["sxo"]) in invocation["arguments"] and str(report_paths["settings"]) in invocation["arguments"] and "-report -rpts" in invocation["arguments"] and "-rjexport" in invocation["arguments"] and closure["exit_code"] == 0 and closure["error"] is None)
    for filename, seal in closure["raw"].items():
        raw = directory / filename
        ck(f"{arm}/{pos}/{filename} bytes", raw.stat().st_size == seal["bytes"])
        ck(f"{arm}/{pos}/{filename} SHA", sha(raw) == seal["sha256"])
    reports[arm, pos] = table_map(load(directory / "item-report-raw.json", True), True)
    original = table_map(load(parent_run / "report-raw.json", True), True)
    for name in original.keys() & reports[arm, pos].keys():
        ck(f"{arm}/{pos} shared report rows {name}", rows(original[name]) == rows(reports[arm, pos][name]))

for arm in ("control", "child"):
    depot = rows(reports[arm, "depot"]["ItemResults"])
    base = rows(reports[arm, "base"]["ItemResults"])
    sysrows = rows(reports[arm, "depot"]["SystemResults"])
    stock = rows(reports[arm, "depot"]["StockTotalResults"])
    ck(f"{arm} four 72-bin ledgers", len(depot) == len(base) == len(sysrows) == len(stock) == 72)
    for i in range(72):
        h = i / 2
        for pos, r in (("depot", depot[i]), ("base", base[i])):
            ck(f"{arm}/{pos} bin {i} identity/grid", r["IID"] == "TEACH-LRU-01" and r["STID"] == ("DEPOT-01" if pos == "depot" else "BASE-01") and r["STINT"] == h and r["ETINT"] == h + .5)
        ck(f"{arm} system/stock bin {i} grid", sysrows[i]["STINT"] == stock[i]["STINT"] == h and sysrows[i]["ETINT"] == stock[i]["ETINT"] == h + .5)
        expected_depot_nominal = (1 if h < 2 else 0 if h < 4 else 1) if arm == "control" else 0
        ck(f"{arm} depot bin {i} nominal", depot[i]["STSZ"] == expected_depot_nominal)
        expected_depot_onhand = (1 if h < 2 else 0 if h < 4 else 1 if h < 10 else 0 if h < 13 else .6666666865348816 if h == 13 else 1) if arm == "control" else 0
        ck(f"{arm} depot bin {i} on-hand", abs(depot[i]["STOHA"] - expected_depot_onhand) < 1e-6)
        expected_depot_nbo = 0 if arm == "control" or h < 10 or h >= 13.5 else .3333333432674408 if h == 13 else 1
        ck(f"{arm} depot bin {i} ordinary NBO", abs(depot[i]["NBO"] - expected_depot_nbo) < 1e-6)
        ck(f"{arm} base bin {i} nominal", base[i]["STSZ"] == (0 if h < 2 else 1))
        expected_base_onhand = (0 if h < 2 else 1 if h < 10 else 0 if h < 12 else 1) if arm == "control" else 0 if h < 4 else 1 if h < 10 else 0 if h < 15 else .6666666865348816 if h == 15 else 1
        ck(f"{arm} base bin {i} on-hand", abs(base[i]["STOHA"] - expected_base_onhand) < 1e-6)
        ck(f"{arm} base/aggregate bin {i} no reported NBO", base[i]["NBO"] == 0 and stock[i]["NBO"] == 0)
    for pos, item in (("depot", depot), ("base", base)):
        total = rows(reports[arm, pos]["ItemResultsTotal"])[0]
        ck(f"{arm}/{pos} total identity", total["IID"] == "TEACH-LRU-01" and total["STID"] == ("DEPOT-01" if pos == "depot" else "BASE-01"))
        ck(f"{arm}/{pos} nominal mean", abs(total["STSZ"] - sum(r["STSZ"] for r in item)/72) < 1e-6)
        ck(f"{arm}/{pos} on-hand mean", abs(total["STOHA"] - sum(r["STOHA"] for r in item)/72) < 1e-6)
    ck(f"{arm} summary two of three success", abs(rows(reports[arm, "depot"]["ResultSummary"])[0]["MSUF"] - 2/3) < 1e-6)
ck("paired outcome reports equal", all(rows(reports["control", "depot"][name]) == rows(reports["child", "depot"][name]) for name in ("ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal")))
for i in range(72):
    ck(f"paired system bin {i} equal", rows(reports["control", "depot"]["SystemResults"])[i] == rows(reports["child", "depot"]["SystemResults"])[i])
    ck(f"paired aggregate stock bin {i} equal", rows(reports["control", "depot"]["StockTotalResults"])[i] == rows(reports["child", "depot"]["StockTotalResults"])[i])

control_log = (RUNS["control"] / "model.log").read_text(encoding="cp1252")
child_log = (RUNS["child"] / "model.log").read_text(encoding="cp1252")
control_events = [
    "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 2  item transfer task 0 (BETWEEN)  starts with 1 items, transfer time: 0",
    "Time: 2 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
    "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
]
child_events = [
    "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder added",
    "Time: 2  item transfer task 0 (BETWEEN)  starts with 0 items, transfer time: 0",
    "Time: 2  item transfer task 0 (BETWEEN)  arrives with 0 items",
    "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
    "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder removed",
    "Time: 4  item transfer task 2 (BETWEEN)  starts with 1 items, transfer time: 0",
    "Time: 4 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
    "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added",
    "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3.16667",
    "Time: 15.1667 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
]
for arm, log, wanted in (("control", control_log, control_events), ("child", child_log, child_events)):
    for phrase in wanted:
        ck(f"{arm} event {phrase[:65]}", phrase in log)
    ck(f"{arm} event chronology", [log.find(p) for p in wanted] == sorted(log.find(p) for p in wanted))
ck("child no physical h2 replacement", "Time: 2 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives" not in child_log)
ck("child one transfer backorder add/remove", len(re.findall(r"Item transfer backorder added", child_log)) == 1 and len(re.findall(r"Item transfer backorder removed", child_log)) == 1)
ck("control no transfer backorder", "Item transfer backorder added" not in control_log)
ck("child transfer completion and ordinary demand distinct", child_log.find("Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder removed") < child_log.find("Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added") < child_log.find("Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed"))
ck("control terminal physical stock identities", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,2>," in control_log and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>," in control_log)
ck("child terminal physical stock identity", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>," in child_log)

result = {
    "schema": "independent-i02-var05-zero-source-review/v1", "case": CASE.name,
    "passed": not failures,
    "verdict": "GO: bounded zero-source BETWEEN transfer backorder and later fulfillment" if not failures else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "source_sha256": {arm: sha(path) for arm, path in inputs.items()},
    "native_closure_sha256": {arm: sha(directory / "closure.json") for arm, directory in RUNS.items()},
    "report_closure_sha256": {f"{arm}_{pos}": sha(directory / "closure.json") for (arm, pos), directory in REPORTS.items()},
    "report_sha256": {f"{arm}_{pos}": sha(directory / "item-report-raw.json") for (arm, pos), directory in REPORTS.items()},
    "observations": {
        "control": "Initial depot item ID0 transfers physically at h2; h4 IN supplies new depot item ID1; no transfer backorder.",
        "zero_source": "Initial depot empty. h2 transfer task starts and arrives with zero physical items and opens transfer backorder1. h4 IN creates ID0, removes that backorder and a second BETWEEN task places ID0 at base.",
        "nominal_caveat": "Child base STSZ=1 from h2, while base STOHA=0 until h4 physical arrival. Nominal target reflects request before performance.",
        "later_demand": "Child h10 uses local ID0. Depot ordinary backorder1 runs h10–13.1667, clears on repaired ID1, and base receives ID1 h15.1667. Both arms have same mission, SystemResults and StockTotalResults rows.",
        "terminal": "Control depot1/base1; child depot0/base1, one aircraft ready. Child transfer and ordinary backorders clear by horizon.",
    },
    "limits": [
        "Native selected table is ItemResults for IID/STID stock positions, not a mounted-item ledger.",
        "Child base nominal STSZ rises at h2 before any physical arrival. Do not equate nominal stock with performed transfer; this narrows a literal manual nominal-on-performance reading.",
        "Aggregate StockTotalResults NBO remains zero although position-scoped ItemResults shows the child depot ordinary backorder h10–13.1667.",
        "One h2 zero-source BETWEEN before scheduled h4 IN against matched initial-one control, one seed/CLI. No general priority, multi-unit split, alternate timing, nonzero delay, procurement, GUI-visual or cross-engine inference.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": checks, "failures": failures}, indent=2))
sys.exit(0 if result["passed"] else 1)
