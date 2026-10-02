"""Independent, read-only replay of the sealed I02.var04 delayed BETWEEN evidence.

Uses only Python's standard library and original source/native artifacts.  It
never calls SIMLOX or the case builder, checker, or author validator.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
NATIVE = CASE / "runs/i02-var04-delay2-v100-ssh-20261002-01"
DEPOT = CASE / "runs/i02-var04-depot-results-v100-ssh-20261002-01"
BASE = CASE / "runs/i02-var04-base-results-v100-ssh-20261002-01"
OUTPUT = CASE / "review/independent-readonly-2026-10-02.json"
checks = 0
failures: list[str] = []


def check(label: str, condition: bool) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def js(path: Path, native: bool = False):
    data = path.read_text(encoding="utf-8-sig")
    if native:
        data = re.sub(r",\s*([}\]])", r"\1", data)
    return json.loads(data)


def tables(model):
    return {t["name"]: t for t in model["model"]["tables"]}


def report_tables(path: Path):
    return {t["name"]: t for t in js(path, True)["report"]["tables"]}


def rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, raw)) for inst in table["instances"] for raw in inst["rows"]]


contract = js(CASE / "contract.json")
diff = js(CASE / "exact-diff.json")
parent_path = (CASE / contract["direct_parent"]["source"]).resolve()
parent = js(parent_path)
child = js(CASE / "native-input.json")
parent_tables, child_tables = tables(parent), tables(child)
check("parent file hash", digest(parent_path) == contract["direct_parent"]["sha256"])
check("child file hash", digest(CASE / "native-input.json") == contract["source_sha256"])
check("exact-diff file hash", digest(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
check("diff parent and child pins", diff["parent_sha256"] == digest(parent_path) and diff["child_sha256"] == digest(CASE / "native-input.json"))
check("no new tables", not (set(child_tables) - set(parent_tables)))
check("no table removed", not (set(parent_tables) - set(child_tables)))
check("exact changed-table set", {k for k in parent_tables if parent_tables[k] != child_tables[k]} == {"ItemTransfer", "ProblemDescription"})
check("declared no added tables", diff["added_tables"] == {})
check("declared no removed tables", diff["removed_tables"] == {})
for name in set(parent_tables) & set(child_tables):
    if name in diff["changed_tables"]:
        check(f"diff before {name}", diff["changed_tables"][name]["before"] == parent_tables[name])
        check(f"diff after {name}", diff["changed_tables"][name]["after"] == child_tables[name])
check("exact IN then BETWEEN source rows", rows(child_tables["ItemTransfer"]) == [
    {"STFID": "<OUTSIDE>", "STTID": "DEPOT-01", "IID": "TEACH-LRU-01", "TFTIME": 4.0, "TFQTY": 1, "TFDT": 0.0, "NOTE": None},
    {"STFID": "DEPOT-01", "STTID": "BASE-01", "IID": "TEACH-LRU-01", "TFTIME": 6.0, "TFQTY": 1, "TFDT": 2.0, "NOTE": None},
])
check("tracked item", rows(child_tables["Item"])[0]["TRACK"] == "Y")
check("item report collection", [(r["RTYPE"], r["RCINT"], r["RCSTA"], r["RCEND"]) for r in rows(child_tables["ResultCollection"])] == [("MISSION", .5, 0, 36), ("SYSTEM", .5, 0, 36), ("ITEM", .5, 0, 36)])
check("no reorder business rows", "ItemReorder" not in child_tables or not rows(child_tables["ItemReorder"]))

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
for key, path in installed.items():
    contract_key = {"manual": "manual_pdf", "dictionary": "table_dictionary", "simlox_exe": "simlox_exe"}[key]
    check(f"installed {key} pin", digest(path) == contract["installed_source_sha256"][contract_key])

native_inv, native_closure = js(NATIVE / "invocation.json"), js(NATIVE / "closure.json")
report_runs = {"depot": DEPOT, "base": BASE}
report_inv = {k: js(v / "invocation.json") for k, v in report_runs.items()}
report_closure = {k: js(v / "closure.json") for k, v in report_runs.items()}
source_paths = {
    "input": CASE / "native-input.json", "parent": parent_path,
    "contract": CASE / "contract.json", "manual": installed["manual"],
    "dictionary": installed["dictionary"], "builder": CASE / "build.py",
    "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"],
}
for run_dir, invocation, closure in [(NATIVE, native_inv, native_closure)] + [(d, report_inv[k], report_closure[k]) for k, d in report_runs.items()]:
    check(f"{run_dir.name} invocation seal", closure["invocation_sha256"] == digest(run_dir / "invocation.json"))
    check(f"{run_dir.name} source stable", closure["source_hashes_before"] == closure["source_hashes_after"])
    check(f"{run_dir.name} invocation source binds closure", invocation["source_hashes_before"] == closure["source_hashes_before"])
    check(f"{run_dir.name} session0 SSH", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
    check(f"{run_dir.name} mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check(f"{run_dir.name} GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    for filename, seal in closure["raw"].items():
        raw = run_dir / filename
        check(f"{run_dir.name}/{filename} bytes", raw.stat().st_size == seal["bytes"])
        check(f"{run_dir.name}/{filename} SHA", digest(raw) == seal["sha256"])
for key, path in source_paths.items():
    check(f"native source {key} hash", native_closure["source_hashes_before"][key] == digest(path))
check("native input copied exactly", digest(NATIVE / "input.json") == digest(CASE / "native-input.json"))
check("native invocation parent/input", native_inv["parent_sha256"] == digest(parent_path) and native_inv["input_sha256"] == digest(CASE / "native-input.json"))
for position in ("depot", "base"):
    invocation, closure = report_inv[position], report_closure[position]
    check(f"{position} report source closure binding", invocation["source_closure_sha256"] == digest(NATIVE / "closure.json") and invocation["source_run_id"] == NATIVE.name)
    paths = {
        "sxo": NATIVE / "model.sxo",
        "settings": CASE / ("runs/report-settings/item-position-results.sxs" if position == "depot" else "runs/report-settings/base-item-position-results.sxs"),
        "exe": installed["simlox_exe"],
        "runner": CASE / ("probe_depot_report_ssh.ps1" if position == "depot" else "probe_base_report_ssh.ps1"),
    }
    for key, path in paths.items():
        check(f"{position} report source {key} hash", closure["source_hashes_before"][key] == digest(path))
    check(f"{position} report export success", closure["exit_code"] == 0 and closure["error"] is None)
    check(f"{position} report command uses frozen settings and SXO", "-report -rpts" in invocation["arguments"] and "-rjexport" in invocation["arguments"] and str(paths["settings"]) in invocation["arguments"] and str(paths["sxo"]) in invocation["arguments"])

steps = js(NATIVE / "steps.json")
check("five ordered native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
for s in steps:
    check(f"step {s['name']} exit", s["exit_code"] == 0 and s["error"] is None)
    check(f"step {s['name']} GUI preserved", s["gui_preserved"] is True)
check("valid native SXO", (NATIVE / "model.sxo").stat().st_size > 4)
check("no conversion errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in (NATIVE / "run.log").read_text(encoding="cp1252"))
check("warning 108 only", "warning #108" in (NATIVE / "run.log").read_text(encoding="cp1252") and "(error #" not in (NATIVE / "run.log").read_text(encoding="cp1252"))

roundtrip = js(NATIVE / "roundtrip-raw.json", True)
round_tables = tables(roundtrip)
populated = {name for name, table in child_tables.items() if rows(table)}
check("22 populated source tables", len(populated) == 22)
for name in sorted(populated):
    check(f"exact roundtrip {name}", round_tables.get(name) == child_tables[name])

native_report = report_tables(NATIVE / "report-raw.json")
reports = {position: report_tables(directory / "item-report-raw.json") for position, directory in report_runs.items()}
for position, selected_report in reports.items():
    check(f"{position} actual item table names", "ItemResults" in selected_report and "ItemResultsTotal" in selected_report and "ItemPositionResults" not in selected_report)
    for name in native_report.keys() & selected_report.keys():
        check(f"{position} report-only shared rows {name}", rows(native_report[name]) == rows(selected_report[name]))
depot_item = rows(reports["depot"]["ItemResults"])
base_item = rows(reports["base"]["ItemResults"])
stock = rows(reports["depot"]["StockTotalResults"])
system = rows(reports["depot"]["SystemResults"])
check("72 depot/base item, stock, system bins", len(depot_item) == len(base_item) == len(stock) == len(system) == 72)
for i, row in enumerate(depot_item):
    start = i / 2
    check(f"item bin {i} identity and grid", row["IID"] == "TEACH-LRU-01" and row["STID"] == "DEPOT-01" and row["STINT"] == start and row["ETINT"] == start + .5)
    check(f"item bin {i} nominal stock", row["STSZ"] == (1 if start < 4 else 2 if start < 6 else 1))
    expected_onhand = 1 if start < 4 else 2 if start < 6 else 1 if start < 10 else 0 if start < 13 else .6666666865348816 if start == 13 else 1
    check(f"item bin {i} on hand", abs(row["STOHA"] - expected_onhand) < 1e-6)
    check(f"item bin {i} no depot backorder", row["NBO"] == 0)
    check(f"stock bin {i} grid", stock[i]["STINT"] == start and stock[i]["ETINT"] == start + .5)
    check(f"stock bin {i} no external backorder", stock[i]["NBO"] == 0)
    check(f"system bin {i} grid", system[i]["STINT"] == start and system[i]["ETINT"] == start + .5)
    base = base_item[i]
    check(f"base bin {i} identity and grid", base["IID"] == "TEACH-LRU-01" and base["STID"] == "BASE-01" and base["STINT"] == start and base["ETINT"] == start + .5)
    check(f"base bin {i} nominal", base["STSZ"] == (0 if start < 8 else 1))
    check(f"base bin {i} on hand", base["STOHA"] == (0 if start < 8 else 1 if start < 10 else 0 if start < 12 else 1))
    check(f"base bin {i} no backorder", base["NBO"] == 0)
    check(f"two-station bin {i} nominal plus in-transit conservation", row["STSZ"] + base["STSZ"] + (1 if 6 <= start < 8 else 0) == (1 if start < 4 else 2))
for position, item_rows in (("depot", depot_item), ("base", base_item)):
    total = rows(reports[position]["ItemResultsTotal"])[0]
    check(f"{position} total position identity", total["IID"] == "TEACH-LRU-01" and total["STID"] == ("DEPOT-01" if position == "depot" else "BASE-01"))
    check(f"{position} total nominal integral", abs(total["STSZ"] - sum(r["STSZ"] for r in item_rows)/72) < 1e-6)
    check(f"{position} total on-hand integral", abs(total["STOHA"] - sum(r["STOHA"] for r in item_rows)/72) < 1e-6)
check("depot and base demand markers", depot_item[20]["NDF"] == base_item[20]["NDF"] == 1 and sum(r["NDF"] for r in depot_item) == sum(r["NDF"] for r in base_item) == 1)
check("aggregate stock zero external backorder", sum(r["NBO"] for r in stock) == 0)
parent_depot_dir = ROOT / "I02-var03-between-transfer-v1.0.0/runs/i02-var03-depot-results-v100-ssh-20261002-01"
parent_base_dir = ROOT / "I02-var03-between-transfer-v1.0.0/runs/i02-var03-base-results-v100-ssh-20261002-01"
parent_depot_closure = js(parent_depot_dir / "closure.json")
parent_base_closure = js(parent_base_dir / "closure.json")
check("accepted zero-delay depot report raw seal", digest(parent_depot_dir / "item-report-raw.json") == parent_depot_closure["raw"]["item-report-raw.json"]["sha256"])
check("accepted zero-delay base report raw seal", digest(parent_base_dir / "item-report-raw.json") == parent_base_closure["raw"]["item-report-raw.json"]["sha256"])
parent_depot_report = report_tables(parent_depot_dir / "item-report-raw.json")
parent_base_report = report_tables(parent_base_dir / "item-report-raw.json")
for name in ("ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"):
    check(f"zero-delay-equivalent outcome rows {name}", rows(reports["depot"][name]) == rows(parent_depot_report[name]))
parent_system = rows(parent_depot_report["SystemResults"])
parent_stock = rows(parent_depot_report["StockTotalResults"])
for i in range(72):
    check(f"system bin {i} unchanged from zero-delay", system[i] == parent_system[i])
    check(f"stock bin {i} unchanged from zero-delay", stock[i] == parent_stock[i])
for i in (21, 22, 23):
    check(f"local spare permits ready bin {i}", system[i]["NSYRY"] == 1 and system[i]["NSYWI"] == 0)
for i in (20, 21, 22, 23):
    check(f"no external backorder in bin {i}", stock[i]["NBO"] == 0 and stock[i]["PNB"] == 1)
for i, (current, prior) in enumerate(zip(depot_item, rows(parent_depot_report["ItemResults"]))):
    check(f"depot bin {i} unchanged from zero-delay", current == prior)
for i, (current, prior) in enumerate(zip(base_item, rows(parent_base_report["ItemResults"]))):
    expected_shift = 1 if 12 <= i < 16 else 0
    check(f"base bin {i} nominal delayed by two hours", current["STSZ"] == prior["STSZ"] - expected_shift)
    check(f"base bin {i} on-hand delayed by two hours", current["STOHA"] == prior["STOHA"] - expected_shift)
    check(f"base bin {i} other metrics unchanged", {k: v for k, v in current.items() if k not in ("STSZ", "STOHA")} == {k: v for k, v in prior.items() if k not in ("STSZ", "STOHA")})
summary = rows(reports["depot"]["ResultSummary"])[0]
check("one replication and two successful thirds", summary["NREP"] == 1 and abs(summary["MSUF"] - 2/3) < 1e-6)
check("terminal depot nominal/on-hand", depot_item[-1]["STSZ"] == depot_item[-1]["STOHA"] == 1)
check("terminal base nominal/on-hand", base_item[-1]["STSZ"] == base_item[-1]["STOHA"] == 1)

log = (NATIVE / "model.log").read_text(encoding="cp1252")
events = [
    "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated",
    "Time: 4  item transfer task 0 (IN)  created: aiming for <TEACH-LRU-01,0,DEPOT-01,0>",
    "Time: 4  item transfer task 0 (IN)  starts with 1 items, transfer time: 0",
    "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
    "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
    "Time: 6  item transfer task 1 (BETWEEN)  created: starting from <TEACH-LRU-01,0,DEPOT-01,0> aiming for <TEACH-LRU-01,0,BASE-01,0>",
    "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer demand arrives from pos <TEACH-LRU-01,0,BASE-01,0>",
    "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 6  item transfer task 1 (BETWEEN)  starts with 1 items, transfer time: 2",
    "Time: 8  item transfer task 1 (BETWEEN)  arrives with 1 items",
    "Time: 8 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
    "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
    "Time: 12  transport task 0 arrives with 1 items/systems",
    "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock",
    "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,2> to stock",
]
positions = [log.find(text) for text in events]
for text, position in zip(events, positions):
    check(f"event {text[:55]}", position >= 0)
check("physical event order", positions == sorted(positions) and len(set(positions)) == len(positions))
check("exactly one IN task creation and arrival", len(re.findall(r"item transfer task \d+ \(IN\)  created", log)) == 1 and len(re.findall(r"item transfer task \d+ \(IN\)  arrives", log)) == 1)
check("exactly one BETWEEN task creation and arrival", len(re.findall(r"item transfer task \d+ \(BETWEEN\)  created", log)) == 1 and len(re.findall(r"item transfer task \d+ \(BETWEEN\)  arrives", log)) == 1)
check("nominal h4 stock has two distinct physical spares", "Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>," in log)
check("post-BETWEEN depot stock contains only item 1", "Level: 1 Items:<TEACH-LRU-01,0,1>," in log)
check("post-BETWEEN base stock contains item 0", "Time: 8 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>," in log)
check("post-demand stock empty", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:" in log)
check("terminal physical depot spare", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,2>," in log)
check("terminal physical base spare", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>," in log)

result = {
    "schema": "independent-i02-var04-between-delay-review/v1",
    "case": "I02-var04-between-delay-v1.0.0",
    "passed": not failures,
    "verdict": "GO: bounded observed two-hour BETWEEN delay against zero-delay control" if not failures else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "native_run": NATIVE.name, "report_only_runs": {k: v.name for k, v in report_runs.items()},
    "source_sha256": digest(CASE / "native-input.json"),
    "native_closure_sha256": digest(NATIVE / "closure.json"),
    "native_report_sha256": digest(NATIVE / "report-raw.json"),
    "selected_report_sha256": {k: digest(v / "item-report-raw.json") for k, v in report_runs.items()},
    "report_only_closure_sha256": {k: digest(v / "closure.json") for k, v in report_runs.items()},
    "observations": {
        "report_table_name": "ItemResults",
        "report_positions": "TEACH-LRU-01 at DEPOT-01 and BASE-01 stock positions, distinct from aircraft mounted item",
        "nominal_STSZ": "depot 1→2 h4→1 h6; base 0→1 h8; station sum falls by one during h6–8 transit",
        "on_hand_STOHA": "depot 1→2 h4→1 h6→0 h10→1 after repair h13.1667; base 0→1 h8→0 h10→1 h12",
        "physical_transfer": "IN item ID1 stocked at depot h4; BETWEEN item ID0 leaves depot h6 and reaches base h8",
        "later_demand": "base uses local item ID0 h10 and is ready h10.5; depot item ID1 goes to base replenishment h10–12; failed item ID2 repaired and stocked at depot h13.1667",
    },
    "limits": [
        "The native table is ItemResults with IID/STID stock-position fields; a literal ItemPositionResults table is absent.",
        "STSZ is nominal station stock size and STOHA is on-hand. Neither is the mounted aircraft item count. ItemResultsTotal values are horizon averages, not terminal stock.",
        "TFDT2 versus TFDT0 for one available-stock BETWEEN after IN, one LRU, two stations, one seed and this CLI only. No standalone BETWEEN, other delay values, IN/OUT delay, shortage split, priority, reorder, GUI-visual or cross-engine conclusion.",
    ],
}
OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": checks, "failures": failures, "output": str(OUTPUT)}, indent=2))
sys.exit(0 if result["passed"] else 1)
