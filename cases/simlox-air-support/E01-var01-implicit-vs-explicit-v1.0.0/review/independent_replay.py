"""Independent read-only replay of accepted D01 and E01 evidence for E01.var01."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
BASE = CASE.parent
CONTRACT = CASE / "contract.json"
OUT = HERE / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def data(path: Path) -> bytes:
    return path.read_bytes()


def sha(path: Path) -> str:
    return hashlib.sha256(data(path)).hexdigest()


def obj(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict, key: str) -> dict:
    return {t["name"]: t for t in doc[key]["tables"]}


def report(path: Path) -> dict:
    # Native default -jsonreport leaves trailing commas. Normalize parser copy only.
    text = path.read_text(encoding="utf-8-sig")
    return tables(json.loads(re.sub(r",(?=\s*[}\]])", "", text)), "report")


def rows(table: dict) -> list:
    return [(i["instance_name"], row) for i in table["instances"] for row in i["rows"]]


def line(log: str, time: str, fragment: str) -> bool:
    return any(x.startswith("Time: " + time + " ") and fragment in x for x in log.splitlines())


contract = obj(CONTRACT)
check(contract["variant_id"] == "E01.var01", "contract variant")
check(sha(CONTRACT) == "ff683ebaa65214a1ed90f58ec9cfcea3e1820363e72318707e8fa48f777676e0", "contract pin")
arms: dict[str, dict] = {}
for label in ("implicit_default", "explicit_breakdown"):
    pin = contract["parents"][label]
    pkg = BASE / pin["package"]
    run = pkg / "runs" / pin["run_id"]
    source = pkg / "native-input.json"
    signoff = pkg / "cli-scope-signoff-2026-09-29.md"
    closure_file = run / "closure.json"
    check(sha(source) == pin["input_sha256"], label + " input pin")
    check(sha(signoff) == pin["signoff_sha256"], label + " signoff pin")
    check(sha(closure_file) == pin["closure_sha256"], label + " closure pin")
    closure = obj(closure_file)
    check(closure["source_hashes_before"] == closure["source_hashes_after"], label + " source stable")
    check(closure["source_hashes_before"]["input"] == pin["input_sha256"], label + " closure input")
    check(closure["error"] is None, label + " closure error")
    check(len(closure["raw"]) == 12, label + " 12 raw files")
    for name, seal in sorted(closure["raw"].items()):
        raw = data(run / name)
        check(len(raw) == seal["bytes"] and hashlib.sha256(raw).hexdigest() == seal["sha256"], label + " raw " + name)
    invocation = obj(run / "invocation.json")
    check(sha(run / "invocation.json") == closure["invocation_sha256"], label + " invocation pin")
    check(invocation["run_id"] == pin["run_id"], label + " invocation identity")
    check(invocation["session_id"] == 0 and invocation["ssh_connection_present"], label + " SSH0")
    check("sshd.exe" in invocation["ssh_ancestor_names"], label + " sshd ancestry")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", label + " mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]), label + " GUI identity")
    steps = obj(run / "steps.json")
    check([x["name"] for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], label + " steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"], label + " step " + step["name"])
    rt = obj(run / "roundtrip-validation.json")
    check(rt["passed"] is True and not rt["differences"], label + " saved roundtrip verdict")
    inp = tables(obj(source), "model")
    exported = tables(obj(run / "roundtrip-raw.json"), "model")
    populated = {name for name, table in inp.items() if rows(table)}
    check(len(populated) == (18 if label == "implicit_default" else 20), label + " populated table count")
    for name in sorted(populated):
        check(name in exported and inp[name]["columns"] == exported[name]["columns"] and inp[name]["instances"] == exported[name]["instances"], label + " exact roundtrip " + name)
    calc_log = (run / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc_log, label + " converter summary")
    check(calc_log.count("(warning #108)") == 1 and "(error #" not in calc_log, label + " warning 108 only")
    check((run / "model.sxo").stat().st_size > 1000, label + " valid result")
    independent = obj(pkg / "review" / "independent-native-review-2026-09-29.json")
    check(independent["passed"] is True and not independent["differences"] and independent["run_id"] == pin["run_id"], label + " accepted independent replay")
    arms[label] = {"source": inp, "report": report(run / "report-raw.json"), "log": (run / "model.log").read_text(encoding="utf-8-sig")}

implicit = arms["implicit_default"]
explicit = arms["explicit_breakdown"]
changed = {name for name in implicit["source"] if implicit["source"][name] != explicit["source"][name]}
check(changed == set(contract["source_delta"]["allowed_changed_tables"]), "exact four-table source delta")
for name in sorted(set(implicit["source"]) - changed):
    check(implicit["source"][name] == explicit["source"][name], "fixed table " + name)
sys_i = rows(implicit["source"]["SystemRepair"])[0][1]
sys_e = rows(explicit["source"]["SystemRepair"])[0][1]
columns = [c["name"] for c in implicit["source"]["SystemRepair"]["columns"]]
check(dict(zip(columns, sys_i))["SURPT"] == dict(zip(columns, sys_e))["SURPT"] == 0.5, "common SURPT")
check(dict(zip(columns, sys_i))["SURPTID"] is None and dict(zip(columns, sys_e))["SURPTID"] == "E01-SURP", "task binding")
check(not rows(implicit["source"]["Tasks"]) and not rows(implicit["source"]["TaskBreakDown"]), "implicit has no task rows")
check(len(rows(explicit["source"]["Tasks"])) == 1, "explicit task row")
bd = explicit["source"]["TaskBreakDown"]
bdcols = [c["name"] for c in bd["columns"]]
bdrows = [dict(zip(bdcols, row)) for _, row in rows(bd)]
check([(r["TID"], r["SEQ"], r["SUTID"], r["DURN"]) for r in bdrows] == [("E01-SURP", 1, "<REMOVE>", 1 / 6), ("E01-SURP", 2, "<REPLACE>", 1 / 3)], "explicit breakdown")

for label, arm in arms.items():
    log = arm["log"]
    check(line(log, "9.8829", "critical random failure added"), label + " failure time")
    check("subitem failed: <TEACH-LRU-01,0,1>" in log, label + " failed ID1")
    check(line(log, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock"), label + " spare ID0 issue")
    check(line(log, "10", "Item demand arrives from pos"), label + " demand")
    check("backorder" not in log.lower(), label + " no backorder event")
    check(line(log, "10.5", "System ready <TEACH-AIR-01,0>"), label + " aircraft ready")
    check(line(log, "10.5", "system SURP task 0 on <TEACH-AIR-01,0> completed"), label + " system task end")
for label, middle, restock, remove_duration, fit_duration in [
    ("implicit_default", "10.25", "11.25", "0.25", "0.25"),
    ("explicit_breakdown", "10.1667", "11.1667", "0.166667", "0.333333"),
]:
    log = arms[label]["log"]
    check(line(log, "10", "remove subitem subtask") and line(log, "10", "planned to last for " + remove_duration + " hours"), label + " remove start and duration")
    check(line(log, middle, "remove subitem subtask") and line(log, middle, "fit subitem subtask"), label + " remove/fit boundary")
    check(line(log, middle, "planned to last for " + fit_duration + " hours"), label + " fit duration")
    check(line(log, "10.5", "fit subitem subtask") and line(log, "10.5", "completed"), label + " fit completion")
    check(line(log, middle, "Item requiring maintenance arrives <TEACH-LRU-01,0,1>"), label + " failed item repair arrival")
    check(line(log, restock, "Finished repair of item <TEACH-LRU-01,0,1>"), label + " repair completion")
    check(line(log, restock, "Put back replacement item <TEACH-LRU-01,0,1> to stock"), label + " physical return")

for table_name, expected in [("ResultSummary", 1), ("SystemResults", 72), ("StockTotalResults", 72)]:
    one = implicit["report"][table_name]
    two = explicit["report"][table_name]
    check(one["columns"] == two["columns"], table_name + " columns")
    check(len(rows(one)) == len(rows(two)) == expected, table_name + " row count")
    for index, (left, right) in enumerate(zip(rows(one), rows(two))):
        check(left == right, table_name + " row " + str(index))
check(implicit["report"]["ProblemDescription"] != explicit["report"]["ProblemDescription"], "report description differs")
check(set(implicit["report"]) == set(explicit["report"]) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")

verdict = {
    "schema": "simlox-e01-var01-independent-derived-replay/v1",
    "variant_id": "E01.var01",
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks": checks,
    "failures": failures,
    "observed": {
        "first_failure_hour": 9.8829,
        "failed_lru_id": 1,
        "issued_spare_id": 0,
        "implicit_remove_fit_hours": [10, 10.25, 10.5],
        "explicit_remove_fit_hours": [10, 10.1667, 10.5],
        "item_restock_hours": {"implicit": 11.25, "explicit": 11.1667},
        "system_and_stock_report_rows_equal": True,
    },
    "limit": "two accepted fixed-seed runs only; explicitness and step durations vary together, so no isolated causal claim",
}
OUT.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": verdict["verdict"], "checks": checks, "failures": failures}, ensure_ascii=False))
raise SystemExit(0 if not failures else 1)
