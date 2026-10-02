"""Independent, read-only replay of the sealed I02.var01 IN evidence.

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
NATIVE = CASE / "runs/i02-var01-in-v102-ssh-20261002-01"
SELECTED = CASE / "runs/i02-var01-item-results-v102-ssh-20261002-01"
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
check("exact new table set", set(child_tables) - set(parent_tables) == {"ItemTransfer"})
check("no table removed", not (set(parent_tables) - set(child_tables)))
check("exact changed-table set", {k for k in parent_tables if parent_tables[k] != child_tables[k]} == {"Item", "ProblemDescription", "ResultCollection"})
check("declared added table exact", diff["added_tables"] == {"ItemTransfer": child_tables["ItemTransfer"]})
check("declared no removed tables", diff["removed_tables"] == {})
for name in set(parent_tables) & set(child_tables):
    if name in diff["changed_tables"]:
        check(f"diff before {name}", diff["changed_tables"][name]["before"] == parent_tables[name])
        check(f"diff after {name}", diff["changed_tables"][name]["after"] == child_tables[name])
check("only one IN transfer", rows(child_tables["ItemTransfer"])[0] == {"STFID": "<OUTSIDE>", "STTID": "DEPOT-01", "IID": "TEACH-LRU-01", "TFTIME": 4.0, "TFQTY": 1, "TFDT": 0.0, "NOTE": None} and len(rows(child_tables["ItemTransfer"])) == 1)
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
selected_inv, selected_closure = js(SELECTED / "invocation.json"), js(SELECTED / "closure.json")
source_paths = {
    "input": CASE / "native-input.json", "parent": parent_path,
    "contract": CASE / "contract.json", "manual": installed["manual"],
    "dictionary": installed["dictionary"], "builder": CASE / "build.py",
    "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"],
}
for run_dir, invocation, closure in ((NATIVE, native_inv, native_closure), (SELECTED, selected_inv, selected_closure)):
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
check("report source closure binding", selected_inv["source_closure_sha256"] == digest(NATIVE / "closure.json") and selected_inv["source_run_id"] == NATIVE.name)
selected_paths = {
    "sxo": NATIVE / "model.sxo",
    "settings": CASE / "runs/report-settings/item-position-results.sxs",
    "exe": installed["simlox_exe"],
    "runner": CASE / "probe_item_report_results_ssh.ps1",
}
for key, path in selected_paths.items():
    check(f"report source {key} hash", selected_closure["source_hashes_before"][key] == digest(path))
check("report export success", selected_closure["exit_code"] == 0 and selected_closure["error"] is None)
check("report command uses frozen settings and SXO", "-report -rpts" in selected_inv["arguments"] and "-rjexport" in selected_inv["arguments"] and str(selected_paths["settings"]) in selected_inv["arguments"] and str(selected_paths["sxo"]) in selected_inv["arguments"])
check("report settings pin", digest(selected_paths["settings"]) == "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9")

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
selected_report = report_tables(SELECTED / "item-report-raw.json")
check("actual item table names", "ItemResults" in selected_report and "ItemResultsTotal" in selected_report and "ItemPositionResults" not in selected_report)
for name in native_report.keys() & selected_report.keys():
    check(f"report-only shared rows {name}", rows(native_report[name]) == rows(selected_report[name]))
item = rows(selected_report["ItemResults"])
stock = rows(selected_report["StockTotalResults"])
system = rows(selected_report["SystemResults"])
check("72 item, stock, system bins", len(item) == len(stock) == len(system) == 72)
for i, row in enumerate(item):
    start = i / 2
    check(f"item bin {i} identity and grid", row["IID"] == "TEACH-LRU-01" and row["STID"] == "DEPOT-01" and row["STINT"] == start and row["ETINT"] == start + .5)
    check(f"item bin {i} nominal stock", row["STSZ"] == (1 if start < 4 else 2))
    expected_onhand = 1 if start < 4 else 2 if start < 10 else 1 if start < 13 else 1.6666666269302368 if start == 13 else 2
    check(f"item bin {i} on hand", abs(row["STOHA"] - expected_onhand) < 1e-6)
    check(f"item bin {i} no depot backorder", row["NBO"] == 0)
    check(f"stock bin {i} grid", stock[i]["STINT"] == start and stock[i]["ETINT"] == start + .5)
    check(f"stock bin {i} base backorder", stock[i]["NBO"] == (1 if 10 <= start < 12 else 0))
    check(f"system bin {i} grid", system[i]["STINT"] == start and system[i]["ETINT"] == start + .5)
check("item total position identity", rows(selected_report["ItemResultsTotal"])[0]["IID"] == "TEACH-LRU-01" and rows(selected_report["ItemResultsTotal"])[0]["STID"] == "DEPOT-01")
check("item total nominal integral", abs(rows(selected_report["ItemResultsTotal"])[0]["STSZ"] - sum(r["STSZ"] for r in item)/72) < 1e-6)
check("item total on-hand integral", abs(rows(selected_report["ItemResultsTotal"])[0]["STOHA"] - sum(r["STOHA"] for r in item)/72) < 1e-6)
check("one depot demand marker", item[20]["NDF"] == 1 and sum(r["NDF"] for r in item) == 1)
check("stock waiting integral two hours", sum(r["NBO"] * .5 for r in stock) == 2)
summary = rows(selected_report["ResultSummary"])[0]
check("one replication and two successful thirds", summary["NREP"] == 1 and abs(summary["MSUF"] - 2/3) < 1e-6)
check("terminal depot nominal/on-hand", item[-1]["STSZ"] == item[-1]["STOHA"] == 2)

log = (NATIVE / "model.log").read_text(encoding="cp1252")
events = [
    "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated",
    "Time: 4  item transfer task 0 (IN)  created: aiming for <TEACH-LRU-01,0,DEPOT-01,0>",
    "Time: 4  item transfer task 0 (IN)  starts with 1 items, transfer time: 0",
    "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
    "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
    "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 12  transport task 0 arrives with 1 items/systems",
    "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,2> to stock",
]
positions = [log.find(text) for text in events]
for text, position in zip(events, positions):
    check(f"event {text[:55]}", position >= 0)
check("physical event order", positions == sorted(positions) and len(set(positions)) == len(positions))
check("exactly one IN task creation and arrival", len(re.findall(r"item transfer task \d+ \(IN\)  created", log)) == 1 and len(re.findall(r"item transfer task \d+ \(IN\)  arrives", log)) == 1)
check("nominal h4 stock has two distinct physical spares", "Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>," in log)
check("terminal physical depot spares", "Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>," in log)

result = {
    "schema": "independent-i02-var01-in-review/v1",
    "case": "I02-var01-in-transfer-v1.0.2",
    "passed": not failures,
    "verdict": "GO: bounded observed IN transfer and depot item-position stock response" if not failures else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "native_run": NATIVE.name, "report_only_run": SELECTED.name,
    "source_sha256": digest(CASE / "native-input.json"),
    "native_closure_sha256": digest(NATIVE / "closure.json"),
    "native_report_sha256": digest(NATIVE / "report-raw.json"),
    "selected_report_sha256": digest(SELECTED / "item-report-raw.json"),
    "report_only_closure_sha256": digest(SELECTED / "closure.json"),
    "observations": {
        "report_table_name": "ItemResults",
        "report_position": "TEACH-LRU-01 at DEPOT-01 (depot stock position, not the aircraft's mounted position)",
        "nominal_STSZ": "1 before h4; 2 from h4 through h36",
        "on_hand_STOHA": "1 before h4; 2 h4-h10; 1 h10-h13; fractional 1.6666666 in h13-h13.5 bin; 2 thereafter",
        "physical_transfer": "one IN unit created, started, arrived and stocked at h4; distinct item ID 1",
        "later_demand": "depot issues pre-existing item ID 0 at h10; base backorder h10-h12; failed item ID 2 repaired and returned to depot at h13.1667",
    },
    "limits": [
        "The pre-run contract used the conditional label ItemPositionResults. The native table is ItemResults with IID/STID position fields; a literal ItemPositionResults table is absent.",
        "The reported STSZ is nominal depot stock size, STOHA is on-hand depot stock. Neither is the mounted aircraft item count. ItemResultsTotal values are horizon averages, not terminal stock.",
        "One scheduled zero-delay IN transfer, one LRU/depot, one fixed seed and this installed CLI only. No OUT, BETWEEN, delay, split, priority, reorder, GUI-visual or cross-engine conclusion.",
    ],
}
OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": checks, "failures": failures, "output": str(OUTPUT)}, indent=2))
sys.exit(0 if result["passed"] else 1)
