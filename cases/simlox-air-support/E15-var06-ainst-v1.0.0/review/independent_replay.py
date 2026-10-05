"""Independent standard-library replay of additional initial stock evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
RUN = CASE / "runs" / "e15-var06-ainst-two-v100-ssh-20261005-01"
PARENT_RUN = PARENT / "runs" / "e15-var07-default-v101-ssh-20261002-01"
PARENT_REPORT_RUN = PARENT / "runs" / "e15-var07-default-item-v101-ssh-20261002-01"
PARENT_LOG = PARENT_RUN / "model.log"
PARENT_REPORT = PARENT_REPORT_RUN / "item-report-raw.json"
OUT = CASE / "review" / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(value: bool, label: str) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path, branch: str) -> dict:
    return {table["name"]: table for table in read(path)[branch]["tables"]}


def cols(table: dict) -> list[str]:
    return [col["name"] for col in table["columns"]]


def rows(table: dict) -> list:
    return table["instances"][0]["rows"]


contract = read(CASE / "contract.json")
closure = read(RUN / "closure.json")
invocation = read(RUN / "invocation.json")
steps = read(RUN / "steps.json")
outcome = read(RUN / "outcome.json")
check(contract["run_id"] == closure["run_id"] == invocation["run_id"] == RUN.name, "run identity")
check(contract["case_id"] == "E15" and contract["variant_id"] == "E15.var06" and contract["version"] == "1.0.0-candidate", "frozen contract identity")
check(closure["error"] is None and outcome["error"] is None, "clean closure/outcome")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(len(closure["raw"]) == 13, "thirteen raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), f"raw exists {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw size {name}")
        check(sha(path) == seal["sha256"], f"raw SHA {name}")
source_paths = {
    "contract": CASE / "contract.json",
    "input": CASE / "native-input.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-default.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "parent_index": PARENT / "evidence-index.json",
    "parent_event": PARENT_LOG,
    "parent_report": PARENT_REPORT,
    "selector": PARENT / "runs" / "report-settings" / "item-position-results.sxs",
    "selector_builder": PARENT / "make_report_settings.py",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after/invocation")
for name, path in sorted(source_paths.items()):
    check(sha(path) == closure["source_hashes_before"][name], f"source SHA {name}")
for name, key in (("input", "input_sha256"), ("builder", "builder_sha256"), ("roundtrip_checker", "roundtrip_checker_sha256"), ("selector", "selector_sha256"), ("selector_builder", "selector_builder_sha256"), ("manual", "manual_pdf_sha256"), ("exe", "simlox_exe_sha256")):
    check(contract["source"][key] == closure["source_hashes_before"][name], f"contract source pin {name}")
for name, key in (("parent_input", "input_sha256"), ("parent_signoff", "signoff_sha256"), ("parent_index", "evidence_index_sha256"), ("parent_event", "event_log_sha256"), ("parent_report", "selected_report_sha256")):
    check(contract["accepted_parent"][key] == closure["source_hashes_before"][name], f"contract parent pin {name}")
for source_run, expected_count in ((PARENT_RUN, 12), (PARENT_REPORT_RUN, 2)):
    parent_closure = read(source_run / "closure.json")
    check(len(parent_closure["raw"]) == expected_count, f"parent raw count {source_run.name}")
    for name, seal in sorted(parent_closure["raw"].items()):
        path = source_run / name
        check(path.is_file(), f"parent raw exists {source_run.name}/{name}")
        if path.is_file():
            check(path.stat().st_size == seal["bytes"], f"parent raw size {source_run.name}/{name}")
            check(sha(path) == seal["sha256"], f"parent raw SHA {source_run.name}/{name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0/sshd")
check(invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}, "protected GUI")
check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
check(len(steps) == 4, "four native steps")
for name in ("import", "export", "calc", "report"):
    selected = [step for step in steps if step["name"] == name]
    check(len(selected) == 1 and selected[0]["status"] == "completed" and selected[0]["exit_code"] == 0 and selected[0]["gui_preserved"], f"guarded step {name}")
check(outcome["roundtrip"] == "exact" and outcome["converter_summary"] == [0, 1, 0] and outcome["warning_codes"] == ["108"] and outcome["result"] == "native_run_completed", "native outcome")
calc_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"Input conversion completed\. Errors: 0, Warnings: 1, Notes: 0", calc_log) is not None, "converter summary raw")
check(re.findall(r"\(warning #(\d+)\)", calc_log) == ["108"] and not re.search(r"\(error #\d+\)", calc_log), "converter diagnostics raw")
check((RUN / "model.sxo").stat().st_size > 1000, "valid native result")

parent = tables(PARENT / "native-input-default.json", "model")
child = tables(RUN / "input.json", "model")
exported = tables(RUN / "roundtrip-raw.json", "model")
check(sha(RUN / "input.json") == sha(CASE / "native-input.json"), "copied input")
check(len(parent) == len(child) == 31 and set(parent) == set(child), "same 31 tables")
for name in sorted(parent):
    if name != "StockAllocation":
        check(child[name] == parent[name], f"unchanged parent table {name}")
stock_names = cols(child["StockAllocation"])
parent_stock = rows(parent["StockAllocation"])
child_stock = rows(child["StockAllocation"])
check(stock_names == cols(parent["StockAllocation"]), "stock column schema")
check(len(parent_stock) == len(child_stock) == 2, "two stock rows")
check(parent_stock[0] == child_stock[0], "unchanged BASE stock row")
check(sum(a != b for pr, cr in zip(parent_stock, child_stock) for a, b in zip(pr, cr)) == 1, "sole source cell")
check(dict(zip(stock_names, parent_stock[1]))["AINST"] is None and dict(zip(stock_names, child_stock[1]))["AINST"] == 2, "depot AINST null-to2")
check(dict(zip(stock_names, child_stock[1]))["ISTOH"] is None, "depot ISTOH omitted")
check(dict(zip(stock_names, child_stock[1]))["STSIZ"] == 4 and dict(zip(stock_names, child_stock[1]))["ROSIZ"] == 2, "nominal and batch unchanged")
authored = [name for name, table in child.items() if rows(table)]
check(len(authored) == 21, "21 row-containing authored tables")
for name in authored:
    check(name in exported, f"roundtrip present {name}")
    if name in exported:
        check(child[name]["columns"] == exported[name]["columns"], f"roundtrip typed columns {name}")
        check(rows(child[name]) == rows(exported[name]), f"roundtrip rows {name}")

event = (RUN / "model.log").read_text(encoding="utf-8-sig")
for needle in (
    "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
    "Level: 6 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,4>,<TEACH-DU-01,0,5>",
    "Level: 1 Items:<TEACH-DU-01,0,6>",
    "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added",
    "subitem failed: <TEACH-DU-01,0,7>",
    "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,6> from stock",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
    "Level: 5 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,4>,<TEACH-DU-01,0,5>",
    "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,7>",
    "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0> to stock",
    "Time: 10  transport task 0 starts with 1 items/systems, transport time: 2",
    "Time: 12  transport task 0 arrives with 1 items/systems",
):
    check(needle in event, f"physical event {needle[:58]}")
check(not re.search(r"reorder task \d+ (?:started|completed)|Delivery with \d+ item\(s\)", event), "no reorder/delivery")
check(event.count("critical random failure added") == 1, "one physical failure")
check(event.count("Take replacement item ") == 2, "two stock issues")
check(event.count("Replacement item arrives ") == 1 and event.count("Put back replacement item ") == 1, "one base replenishment")
check(event.count("transport task 0 starts with 1 items/systems") == 1 and event.count("transport task 0 arrives with 1 items/systems") == 1, "one physical shipment")
check(event.count("mission starting, duration: 2") == 3 and event.count("mission success:") == 2 and event.count("mission aborted:") == 1, "mission outcomes")
snapshots = list(re.finditer(r"Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:([^\n]*)", event))
check([(m.group(1), int(m.group(2)), re.findall(r"<TEACH-DU-01,0,(\d+)>", m.group(3))) for m in snapshots] == [
    ("DEPOT-01", 6, ["0", "1", "2", "3", "4", "5"]),
    ("BASE-01", 1, ["6"]),
    ("BASE-01", 0, []),
    ("DEPOT-01", 5, ["1", "2", "3", "4", "5"]),
    ("BASE-01", 1, ["0"]),
], "complete physical stock snapshots")
for match in snapshots:
    ids = re.findall(r"<TEACH-DU-01,0,(\d+)>", match.group(3))
    check(len(ids) == int(match.group(2)) and len(ids) == len(set(ids)), f"physical snapshot {match.group(1)} {match.start()}")

report = tables(RUN / "selected-report-raw.json", "report")
parent_report = tables(PARENT_REPORT, "report")
check(set(report) == set(parent_report) and len(report) == 10, "ten selected tables")
for name in sorted(report):
    check(cols(report[name]) == cols(parent_report[name]), f"report columns {name}")
    check(len(rows(report[name])) == len(rows(parent_report[name])), f"report length {name}")
    if name not in ("ItemResults", "ItemResultsTotal"):
        check(rows(report[name]) == rows(parent_report[name]), f"unchanged parent report {name}")
for name in ("ItemResults", "SystemResults", "StockTotalResults", "MissionResults"):
    check(len(rows(report[name])) == 72, f"72 {name} bins")
item = report["ItemResults"]
names = cols(item)
for i, data in enumerate(rows(item)):
    row = dict(zip(names, data))
    start = i / 2
    check(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01", f"selected item bin {i}")
    check(row["STINT"] == start and row["ETINT"] == start + 0.5, f"interval bin {i}")
    check(row["STSZ"] == 4 and row["NBO"] == 0, f"nominal/backorder bin {i}")
    check(row["STOHA"] == (6 if start < 10 else 5), f"on-hand bin {i}")
    check(row["NRO"] == 0, f"no reorder marker bin {i}")
    parent_row = dict(zip(names, rows(parent_report["ItemResults"])[i]))
    for field in names:
        if field != "STOHA" and field != "NRO":
            check(row[field] == parent_row[field], f"other item field {i}/{field}")
total = dict(zip(cols(report["ItemResultsTotal"]), rows(report["ItemResultsTotal"])[0]))
check(abs(total["STOHA"] - (6 * 10 + 5 * 26) / 36) < 1e-5, "time-weighted item on-hand")
check(total["NRO"] == 0, "total reorder zero")
parent_total = dict(zip(cols(parent_report["ItemResultsTotal"]), rows(parent_report["ItemResultsTotal"])[0]))
for name in total:
    if name not in ("STOHA", "NRO"):
        check(total[name] == parent_total[name], f"other item total {name}")
check(rows(item)[-1][names.index("STOHA")] == 5, "terminal depot stock five")

verdict = {
    "schema": "simlox-independent-readonly-review/v1",
    "case": "E15.var06 v1.0.0",
    "run_id": RUN.name,
    "verdict": "PASS_BOUNDED_AINST2" if not failures else "EXCLUDE_NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "closure_sha256": sha(RUN / "closure.json"),
    "event_log_sha256": sha(RUN / "model.log"),
    "report_sha256": sha(RUN / "selected-report-raw.json"),
    "scope": "One seed and one depot: AINST2 with omitted ISTOH yields opening on-hand6 against nominal STSIZ4; one h10 issue leaves on-hand5 and no reorder through h36. No explicit ISTOH precedence or later-demand inference.",
}
OUT.write_text(json.dumps(verdict, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(f"{verdict['verdict']} {verdict['checks_passed']}/{checks}")
if failures:
    print("\n".join(failures[:30]))
    raise SystemExit(1)
