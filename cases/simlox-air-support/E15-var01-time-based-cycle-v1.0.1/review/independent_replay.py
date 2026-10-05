"""Independent read-only replay of the E15.var01 report-only extension."""
import difflib
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DIAG = ROOT / "E15-var01-time-based-cycle-v1.0.0"
OLD = DIAG / "runs/e15-var01-timecycle-v100-ssh-20261005-01"
E15 = ROOT / "E15-var07-explicit-istoh-v1.0.1"
PARENT = E15 / "runs/e15-var07-default-v101-ssh-20261002-01"
PARENT_ITEM = E15 / "runs/e15-var07-default-item-v101-ssh-20261002-01"
RUN = HERE / "runs/e15-var01-timecycle-report-v101-ssh-20261005-01"
checks = []


def check(name, value):
    checks.append((name, bool(value)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = read(HERE / "contract.json")
old = read(OLD / "closure.json")
new = read(RUN / "closure.json")
inv = read(RUN / "invocation.json")
steps = read(RUN / "steps.json")
check("contract pin", sha(HERE / "contract.json") == new["source_hashes_before"]["contract"])
check("original excluded closure pin", sha(OLD / "closure.json") == contract["diagnostic_parent"]["closure_sha256"] == new["parent_closure_sha256"])
check("original excluded index pin", sha(DIAG / "evidence-index.json") == contract["diagnostic_parent"]["evidence_index_sha256"])
check("original exclusion retained", old["error"] == "unreviewed converter diagnostic")
check("new invocation seal", sha(RUN / "invocation.json") == new["invocation_sha256"])
check("run and parent identities", new["run_id"] == inv["run_id"] == contract["run_id"] and new["parent_run_id"] == old["run_id"])
check("session zero, SSH, queue, GUI", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("one guarded report step", len(steps) == 1 and steps[0]["name"] == "selected_report_only" and steps[0]["exit_code"] == 0 and steps[0]["status"] == "completed" and steps[0]["gui_preserved"])
args = steps[0]["arguments"].lower()
check("no recalculation or input mutation command", all(x in args for x in (" -report ", " -rpts ", " -rjexport ", " -log ", " -close")) and not any(x in args for x in (" -calc", " -jimport", " -jexport", " -save")))
check("sources identical before and after", new["source_hashes_before"] == new["source_hashes_after"] == inv["source_hashes_before"])

sources = {
    "contract": HERE / "contract.json",
    "diagnostic_index": DIAG / "evidence-index.json",
    "diagnostic_contract": DIAG / "contract.json",
    "diagnostic_closure": OLD / "closure.json",
    "diagnostic_sxo": OLD / "model.sxo",
    "diagnostic_event": OLD / "model.log",
    "diagnostic_calc": OLD / "run.log",
    "accepted_input": E15 / "native-input-default.json",
    "accepted_sxo": PARENT / "model.sxo",
    "accepted_event": PARENT / "model.log",
    "accepted_report": PARENT_ITEM / "item-report-raw.json",
    "settings_builder": E15 / "make_report_settings.py",
    "settings": E15 / "runs/report-settings/item-position-results.sxs",
    "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": HERE / "run_report_ssh.ps1",
    "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, path in sources.items():
    check("source seal " + key, path.exists() and sha(path) == new["source_hashes_before"][key])
check("11 old sealed raw files", len(old["raw"]) == 11)
for name, seal in sorted(old["raw"].items()):
    p = OLD / name
    check("old raw " + name, p.exists() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"])
check("four new sealed raw files", len(new["raw"]) == 4)
for name, seal in sorted(new["raw"].items()):
    p = RUN / name
    check("new raw " + name, p.exists() and p.stat().st_size == seal["bytes"] and sha(p) == seal["sha256"])

parent_source = read(E15 / "native-input-default.json")
child_source = read(DIAG / "native-input.json")
pt = parent_source["model"]["tables"]
ct = child_source["model"]["tables"]
check("31 source tables", len(pt) == len(ct) == 31)
for a, b in zip(pt, ct):
    if b["name"] == "ItemReorder":
        x = a["instances"][0]["rows"]
        y = b["instances"][0]["rows"]
        expected = json.loads(json.dumps(a))
        expected["instances"][0]["rows"][0][5] = 16.0
        check("sole ROINT 0→16 source change", len(x) == len(y) == 1 and x[0][5] is None and b == expected)
    else:
        check("unchanged source " + b["name"], a == b)

calc = (OLD / "run.log").read_text(encoding="utf-8-sig")
events = (OLD / "model.log").read_text(encoding="utf-8-sig")
parent_events = (PARENT / "model.log").read_text(encoding="utf-8-sig")
check("exact warning and valid original output", re.search(r"Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0", calc) and re.findall(r"\(warning #(\d+)\)", calc) == ["108", "376"] and "Form: StockAllocation\nrec 2: (warning #376) ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01" in calc.replace("\r\n", "\n") and (OLD / "model.sxo").stat().st_size > 4)
check("opening depot and base physical IDs", "Level: 4 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>" in events and "Level: 1 Items:<TEACH-DU-01,0,4>" in events)
check("h10 depot issue and base replenishment", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in events and "Level: 3 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>" in events and "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in events)
check("failed ID5 and local replacement ID4", "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,4> from stock" in events and "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,5>" in events)
check("h16/17 time-based reorder", "Time: 16 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in events and "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives" in events and "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>" in events and "Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,6>" in events)
check("parent has no reorder", "reorder task" not in parent_events)
opcodes = difflib.SequenceMatcher(None, parent_events.splitlines(), events.splitlines(), autojunk=False).get_opcodes()
added = [line for tag, _, _, i, j in opcodes if tag == "insert" for line in events.splitlines()[i:j]]
check("exact six added event lines", all(tag in ("equal", "insert") for tag, *_ in opcodes) and len(added) == 6 and any("reorder task 0 started" in x for x in added) and any("Delivery with 1 item(s) arrives" in x for x in added))
check("same three mission outcomes and terminal readiness", events.count("mission starting, duration: 2") == 3 and events.count("mission aborted:") == 1 and events.count("mission success:") == 2 and "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in events)

doc = read(RUN / "selected-report-raw.json")["report"]
parent_doc = read(PARENT_ITEM / "item-report-raw.json")["report"]
tables = {t["name"]: t for t in doc["tables"]}
parent_tables = {t["name"]: t for t in parent_doc["tables"]}
names = ["ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults", "ItemResultsTotal", "StockTotalResults"]
check("strict ten selected tables", list(tables) == list(parent_tables) == names)


def rows(t, name):
    return t[name]["instances"][0]["rows"]


for name in names:
    check("report schema " + name, tables[name]["columns"] == parent_tables[name]["columns"] and len(tables[name]["instances"]) == 1)
for name in ("ProblemDescription", "ResultSummary", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"):
    check("parent table equality " + name, rows(tables, name) == rows(parent_tables, name))
for name in ("MissionResults", "SystemResults", "StockTotalResults"):
    x, y = rows(tables, name), rows(parent_tables, name)
    check(name + " 72 bins", len(x) == len(y) == 72)
    for i in range(72):
        check(name + " equality bin " + str(i), x[i] == y[i])

item = tables["ItemResults"]
cols = {c["name"]: i for i, c in enumerate(item["columns"])}
item_rows = rows(tables, "ItemResults")
parent_rows = rows(parent_tables, "ItemResults")
check("depot selector and 72 bins", len(item_rows) == len(parent_rows) == 72 and all(r[cols["IID"]:cols["STID"]+1] == ["TEACH-DU-01", "DEPOT-01"] for r in item_rows))
item_diffs = []
for i, (r, old_r) in enumerate(zip(item_rows, parent_rows)):
    check("item interval " + str(i), r[cols["STINT"]] == i / 2 and r[cols["ETINT"]] == (i + 1) / 2)
    for field, wanted in (("STSZ", 4), ("STOHA", 4 if i < 20 or i >= 34 else 3), ("NRO", 1 if i == 32 else 0), ("NBO", 0)):
        check("item bin " + str(i) + " " + field, r[cols[field]] == wanted)
    delta = [(item["columns"][j]["name"], old_r[j], r[j]) for j in range(len(r)) if old_r[j] != r[j]]
    if delta:
        item_diffs.append({"bin": i, "cells": delta})
    expected = [("NRO", 0, 1)] if i == 32 else ([("STOHA", 3, 4)] if i >= 34 else [])
    check("item parent delta " + str(i), delta == expected)
check("39 changed ItemResults cells", len(item_diffs) == 39)
total = tables["ItemResultsTotal"]
tc = {c["name"]: i for i, c in enumerate(total["columns"])}
a = rows(tables, "ItemResultsTotal")[0]
b = rows(parent_tables, "ItemResultsTotal")[0]
total_diffs = [(total["columns"][j]["name"], b[j], a[j]) for j in range(len(a)) if a[j] != b[j]]
check("two item total changes", [x[0] for x in total_diffs] == ["STOHA", "NRO"] and a[tc["NRO"]] == 1 and abs(a[tc["STOHA"]] - (4 * 10 + 3 * 7 + 4 * 19) / 36) < 1e-5)
check("new report outcome", read(RUN / "outcome.json") == {"status": "completed", "error": None, "exit_code": 0} and new["error"] is None)

failed = [n for n, ok in checks if not ok]
verdict = {
    "decision": "GO_BOUNDED_TIME_CYCLE_REPORT" if not failed else "NO_GO_INDEPENDENT_REPLAY",
    "passed": not failed,
    "checks_passed": len(checks) - len(failed),
    "checks_total": len(checks),
    "failures": failed,
    "v100_frozen_warning_gate": "NO_GO_UNCHANGED",
    "old_closure_sha256": sha(OLD / "closure.json"),
    "new_closure_sha256": sha(RUN / "closure.json"),
    "report_sha256": sha(RUN / "selected-report-raw.json"),
    "changed_report_cells": {"ItemResults": item_diffs, "ItemResultsTotal": total_diffs, "other_eight_tables": 0},
    "limits": "One installed CLI, fixed seed, initial ROINT16, one h10 demand and h16 cycle; no strategy-change, multiple-cycle, general-policy, GUI or cross-engine claim.",
}
(HERE / "review/independent-verdict.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k: verdict[k] for k in ("decision", "checks_passed", "checks_total", "failures")}, ensure_ascii=False))
