"""Read-only replay of the versioned E15.var10 warning/report extension."""
import difflib
import hashlib
import json
import pathlib
import re

CASE = pathlib.Path(__file__).resolve().parents[1]
BASE = CASE.parent
OLD = BASE / "E15-var10-rosiz-upper-bound-v1.0.0"
OLD_RUN = OLD / "runs/e15-var10-rosiz-over-limit-v100-ssh-20261005-01"
PARENT = BASE / "E15-var07-explicit-istoh-v1.0.1"
PARENT_RUN = PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01"
PARENT_ITEM = PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01"
RUN = CASE / "runs/e15-var10-warning-report-v101-ssh-20261005-01"
checks = []


def check(name, truth):
    checks.append((name, bool(truth)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = obj(CASE / "contract.json")
old_closure = obj(OLD_RUN / "closure.json")
closure = obj(RUN / "closure.json")
inv = obj(RUN / "invocation.json")
steps = obj(RUN / "steps.json")
check("new contract pin", sha(CASE / "contract.json") == closure["source_hashes_before"]["contract"])
check("old closure pin", sha(OLD_RUN / "closure.json") == contract["diagnostic_parent"]["closure_sha256"] == closure["parent_closure_sha256"])
check("old index pin", sha(OLD / "evidence-index.json") == contract["diagnostic_parent"]["evidence_index_sha256"])
check("old gate remains failed", old_closure["expected_negative"] is False and old_closure["error"] == "expected converter error absent")
check("new invocation seal", sha(RUN / "invocation.json") == closure["invocation_sha256"])
check("run identity", closure["run_id"] == inv["run_id"] == contract["run_id"] and closure["parent_run_id"] == old_closure["run_id"])
check("session, queue, GUI", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("one successful guarded report step", len(steps) == 1 and steps[0]["name"] == "selected_report_only" and steps[0]["exit_code"] == 0 and steps[0]["status"] == "completed" and steps[0]["gui_preserved"])
args = steps[0]["arguments"].lower()
check("report-only command", all(x in args for x in (" -report ", " -rpts ", " -rjexport ", " -log ", " -close")) and not any(x in args for x in (" -calc", " -jimport", " -jexport", " -save")))
check("source before/after identical", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
paths = {
    "contract": CASE / "contract.json",
    "diagnostic_index": OLD / "evidence-index.json",
    "diagnostic_contract": OLD / "contract.json",
    "diagnostic_closure": OLD_RUN / "closure.json",
    "diagnostic_sxo": OLD_RUN / "model.sxo",
    "diagnostic_event": OLD_RUN / "model.log",
    "diagnostic_calc": OLD_RUN / "run.log",
    "accepted_input": PARENT / "native-input-explicit-three.json",
    "accepted_sxo": PARENT_RUN / "model.sxo",
    "accepted_event": PARENT_RUN / "model.log",
    "accepted_report": PARENT_ITEM / "item-report-raw.json",
    "settings_builder": PARENT / "make_report_settings.py",
    "settings": PARENT / "runs/report-settings/item-position-results.sxs",
    "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_report_ssh.ps1",
    "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, path in paths.items():
    check("source seal " + key, path.exists() and sha(path) == closure["source_hashes_before"][key])
check("old 11 raw files", len(old_closure["raw"]) == 11)
for name, seal in sorted(old_closure["raw"].items()):
    path = OLD_RUN / name
    check("old raw seal " + name, path.exists() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
check("new four raw files", len(closure["raw"]) == 4)
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check("new raw seal " + name, path.exists() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])

calc = (OLD_RUN / "run.log").read_text(encoding="utf-8-sig")
events = (OLD_RUN / "model.log").read_text(encoding="utf-8-sig")
parent_events = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
check("exact warning 168 and zero errors", re.search(r"Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0", calc) and re.findall(r"\(warning #(\d+)\)", calc) == ["108", "168"] and "Reorder size too large (ROSIZ > STSIZ+1): TEACH-DU-01" in calc)
check("valid original output", (OLD_RUN / "model.sxo").stat().st_size == 358607 and "Starting simulation..." in calc)
check("opening physical stock IDs", "Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>" in events and "Level: 1 Items:<TEACH-DU-01,0,3>" in events)
check("h10 demand and depot issue", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Item demand arrives" in events and "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in events and "Level: 2 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>" in events)
check("base repair, discard and receipt", "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,4>" in events and "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in events and "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in events)
check("no child depot reorder/delivery", "reorder task" not in events and "Delivery with" not in events)
check("parent h10/h11 reorder contrast", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started" in parent_events and "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in parent_events)
parent_lines = parent_events.splitlines()
child_lines = events.splitlines()
ops = difflib.SequenceMatcher(None, parent_lines, child_lines, autojunk=False).get_opcodes()
removed = [line for action, i, j, _, _ in ops if action == "delete" for line in parent_lines[i:j]]
check("event differences only removed parent reorder block", all(action in ("equal", "delete") for action, *_ in ops) and len(removed) == 9 and any("reorder task 0 started" in line for line in removed) and any("Delivery with 2 item(s) arrives" in line for line in removed))
check("mission and terminal event", events.count("mission starting, duration: 2") == 3 and events.count("mission aborted:") == 1 and events.count("mission success:") == 2 and "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in events)

report = obj(RUN / "selected-report-raw.json")["report"]
parent_report = obj(PARENT_ITEM / "item-report-raw.json")["report"]
new_tables = {t["name"]: t for t in report["tables"]}
old_tables = {t["name"]: t for t in parent_report["tables"]}
expected_names = ["ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults", "ItemResultsTotal", "StockTotalResults"]
check("strict ten report tables", list(new_tables) == expected_names == list(old_tables))
for name in expected_names:
    check("report schema " + name, new_tables[name]["columns"] == old_tables[name]["columns"] and len(new_tables[name]["instances"]) == 1)

def rows(tables, name):
    return tables[name]["instances"][0]["rows"]


for name in ("ProblemDescription", "ResultSummary", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"):
    check("parent table parity " + name, rows(new_tables, name) == rows(old_tables, name))
for name in ("MissionResults", "SystemResults", "StockTotalResults"):
    a, b = rows(new_tables, name), rows(old_tables, name)
    check(name + " 72 bins", len(a) == len(b) == 72)
    for i in range(72):
        check(name + " parent parity bin " + str(i), a[i] == b[i])

item = new_tables["ItemResults"]
item_rows = rows(new_tables, "ItemResults")
parent_item_rows = rows(old_tables, "ItemResults")
col = {c["name"]: i for i, c in enumerate(item["columns"])}
check("depot item selector and 72 bins", len(item_rows) == len(parent_item_rows) == 72 and all(r[col["IID"]:col["STID"] + 1] == ["TEACH-DU-01", "DEPOT-01"] for r in item_rows))
item_changes = []
for i, (r, old) in enumerate(zip(item_rows, parent_item_rows)):
    check("item bin time " + str(i), r[col["STINT"]] == i / 2 and r[col["ETINT"]] == (i + 1) / 2)
    for field, expected in (("STSZ", 4), ("STOHA", 3 if i < 20 else 2), ("NRO", 0), ("NBO", 0)):
        check("item bin " + str(i) + " " + field, r[col[field]] == expected)
    diff = [(item["columns"][j]["name"], old[j], r[j]) for j in range(len(r)) if r[j] != old[j]]
    if diff:
        item_changes.append({"bin": i, "cells": diff})
    expected_diff = [("NRO", 1, 0)] if i == 20 else ([("STOHA", 4, 2)] if i >= 22 else [])
    check("item parent delta bin " + str(i), diff == expected_diff)
total = new_tables["ItemResultsTotal"]
total_col = {c["name"]: i for i, c in enumerate(total["columns"])}
child_total = rows(new_tables, "ItemResultsTotal")[0]
parent_total = rows(old_tables, "ItemResultsTotal")[0]
total_diff = [(total["columns"][j]["name"], parent_total[j], child_total[j]) for j in range(len(child_total)) if child_total[j] != parent_total[j]]
check("item total delta", [x[0] for x in total_diff] == ["STOHA", "NRO"] and child_total[total_col["NRO"]] == 0 and abs(child_total[total_col["STOHA"]] - (3 * 10 + 2 * 26) / 36) < 1e-5)
check("report-only outcome", obj(RUN / "outcome.json") == {"status": "completed", "error": None, "exit_code": 0} and closure["error"] is None)

failures = [name for name, ok in checks if not ok]
verdict = {
    "decision": "GO_BOUNDED_WARNING_AND_REPORT_DIAGNOSTIC" if not failures else "NO_GO_REVIEW_FAILURE",
    "passed": not failures,
    "checks_passed": len(checks) - len(failures),
    "checks_total": len(checks),
    "failures": failures,
    "old_converter_error_gate": "NO_GO_UNCHANGED",
    "old_closure_sha256": sha(OLD_RUN / "closure.json"),
    "new_closure_sha256": sha(RUN / "closure.json"),
    "selected_report_sha256": sha(RUN / "selected-report-raw.json"),
    "report_differences": {
        "ResultSummary": 0,
        "MissionResults": 0,
        "SystemResults": 0,
        "StockTotalResults": 0,
        "ItemResults_changed_bins": len(item_changes),
        "ItemResults_changes": item_changes,
        "ItemResultsTotal_changes": total_diff,
    },
    "scope": "One sealed invalid ROSIZ6 stock-based depot input, installed CLI and fixed seed. Warning #168, no observed reorder, and the selected report are bounded diagnostics; no supported policy or general limit claim.",
}
(CASE / "review/independent-verdict.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k: verdict[k] for k in ("decision", "checks_passed", "checks_total", "failures")}, ensure_ascii=False))
