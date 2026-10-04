"""Independent, read-only replay of the sealed I07.var02 v1.0.1 native pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "i07-var02-rosiz-v101-ssh-20261005-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
REVIEW = CASE / "review" / "independent-readonly-2026-10-05.json"
CHECKS = 0
FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(document: dict, root: str) -> dict:
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table: dict) -> list:
    check(len(table["instances"]) == 1, f"single instance: {table['name']}")
    return table["instances"][0]["rows"]


def report_rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def main() -> None:
    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    steps = load(RUN / "steps.json")
    outcome = load(RUN / "outcome.json")
    contract = load(CASE / "contract.json")
    check(digest(RUN / "closure.json") == "70f370b089a2bc477ebd38027be4e5bcebe94e23dc963fd8103272b9d8b660ce", "closure pin")
    check(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(closure["run_id"] == invocation["run_id"] == contract["run_id"] == RUN_ID, "run identity")
    check(closure["error"] is None and closure["publication_state"] == "not_published", "sealed successful closure")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native mutex")
    names = [f"{arm}_{task}" for arm in ("control", "change") for task in ("import", "export", "calc", "report")]
    check([step["name"] for step in steps] == names, "eight ordered native steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] and step["error"] is None, f"step success/GUI: {step['name']}")
    check(outcome["error"] is None and all(outcome["arms"][arm] == "completed" for arm in ("control", "change")), "both native arms complete")

    paths = {
        "contract": CASE / "contract.json",
        "builder": CASE / "build.py",
        "parent_input": PARENT / "native-input-default.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
        "settings_builder": PARENT / "make_report_settings.py",
        "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
        "selector": PARENT / "runs" / "report-settings" / "item-position-results.sxs",
        "control": CASE / "control-input.json",
        "change": CASE / "change-input.json",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "runner": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    before, after = closure["source_hashes_before"], closure["source_hashes_after"]
    check(before == after == invocation["source_hashes_before"], "before/after/invocation source maps")
    check(set(paths) == set(before), "complete source pin set")
    for name, path in paths.items():
        check(path.is_file() and digest(path) == before[name], f"source byte seal: {name}")
    check(before["contract"] == "7fdb7ac423e8921f22acb30ba0b675cfa271cb36740b43f6f28b6034da09ec30", "frozen contract SHA")
    check(before["parent_input"] == contract["prerequisites"]["E15"]["input_sha256"], "accepted parent pin")
    check(before["control"] == contract["frozen_source"]["inputs_sha256"]["control"] and before["change"] == contract["frozen_source"]["inputs_sha256"]["change"], "contract input pins")

    raw = closure["raw"]
    check(len(raw) == 22, "22 sealed raw files")
    check(set(raw) == {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}, "complete raw manifest")
    for name, pin in raw.items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == pin["bytes"] and digest(path) == pin["sha256"], f"raw byte seal: {name}")
    for arm in ("control", "change"):
        check(digest(RUN / f"{arm}-input.json") == before[arm], f"raw copied input: {arm}")
        check((RUN / f"{arm}.sxo").stat().st_size > 4, f"usable output: {arm}")
        log = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log, f"zero-error conversion: {arm}")
        check(re.findall(r"\(warning #(\d+)\)", log) == ["108"], f"reviewed warning: {arm}")
        check(outcome["converter_summaries"][arm] == [0, 1, 0] and outcome["warning_codes"][arm] == ["108"], f"outcome diagnostic: {arm}")

    parent = tables(load(PARENT / "native-input-default.json"), "model")
    authored = {arm: tables(load(CASE / f"{arm}-input.json"), "model") for arm in ("control", "change")}
    check(len(parent) == 31 and all(len(t) == 32 for t in authored.values()), "parent/child table counts")
    for arm, model in authored.items():
        check(set(model) == set(parent) | {"ChangesStockAllocation"}, f"one added table: {arm}")
        for name in parent:
            if name != "ProblemDescription":
                check(model[name] == parent[name], f"unchanged parent table {arm}/{name}")
        check(rows(model["StockAllocation"])[1] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, None, None, None], f"initial depot stock: {arm}")
        check(rows(model["ItemReorder"])[0][:3] == ["TEACH-DU-01", "DEPOT-01", 1.0], f"one-hour reorder lead: {arm}")
        check(rows(model["ProblemDescription"]) == [["I07.var02 matched scheduled depot ROSIZ contrast"]], f"matched description: {arm}")
    check([c["name"] for c in authored["change"]["ChangesStockAllocation"]["columns"]] == ["POINT", "IID", "STID", "TIMEC", "ROSIZ", "NOTE"], "scheduled stock schema")
    check(rows(authored["control"]["ChangesStockAllocation"]) == [[None] * 6], "control placeholder")
    check(rows(authored["change"]["ChangesStockAllocation"]) == [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5, 1, None]], "h5 ROSIZ-only child")
    for name in authored["control"]:
        if name != "ChangesStockAllocation":
            check(authored["control"][name] == authored["change"][name], f"pair isolated table: {name}")

    for arm, model in authored.items():
        exported = tables(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
        check(set(exported) == set(model), f"exact exported table names: {arm}")
        check(sum(bool(rows(table)) for table in model.values()) == 22, f"22 authored row-containing tables: {arm}")
        for name, table in model.items():
            source_rows = rows(table)
            exported_rows = rows(exported[name])
            check([c["name"] for c in table["columns"]] == [c["name"] for c in exported[name]["columns"]], f"roundtrip columns {arm}/{name}")
            if source_rows:
                check(source_rows == exported_rows, f"roundtrip authored rows {arm}/{name}")
            else:
                check(all(all(value is None for value in row) for row in exported_rows), f"empty-table canonicalization {arm}/{name}")

    event = {arm: (RUN / f"{arm}.log").read_text(encoding="utf-8-sig").splitlines() for arm in ("control", "change")}
    control, change = event["control"], event["change"]
    check((RUN / "control.log").read_bytes() == (PARENT / "runs" / "e15-var07-default-v101-ssh-20261002-01" / "model.log").read_bytes(), "control repeats accepted E15 event log")
    added = [
        "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives ",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item <TEACH-DU-01,0,6> to stock ",
        "  Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,6>,",
    ]
    for line in added:
        check(change.count(line) == 1, f"one child-only native event: {line[:80]}")
    check([line for line in change if line not in added] == control, "full event ledger differs only by six reorder lines")
    check(not any("reorder task" in line or "Delivery with" in line for line in control), "control has no reorder or delivery")
    check(not any(line.startswith("Time: 5 ") for line in change), "h5 scheduled change has no event/order")
    for arm, lines in event.items():
        for fragment in (
            "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
            "Level: 4 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>",
            "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted",
            "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Item demand arrives",
            "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
            "Level: 3 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>",
            "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,5>",
            "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready",
            "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0> to stock",
            "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success",
            "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success",
        ):
            check(any(fragment in line for line in lines), f"physical/event path {arm}: {fragment[:65]}")

    reports = {arm: tables(load(RUN / f"{arm}-report-raw.json"), "report") for arm in ("control", "change")}
    check(set(reports["control"]) == set(reports["change"]) == {"ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults", "ItemResultsTotal", "StockTotalResults"}, "selected report tables")
    for name in reports["control"]:
        if name not in {"ItemResults", "ItemResultsTotal"}:
            check(reports["control"][name] == reports["change"][name], f"same non-item report: {name}")
    for arm, report in reports.items():
        for name in ("MissionResults", "SystemResults", "StockTotalResults", "ItemResults"):
            check(len(rows(report[name])) == 72, f"72 half-hour {arm}/{name} bins")
        item = report_rows(report["ItemResults"])
        for index, row in enumerate(item):
            start, end = index / 2, (index + 1) / 2
            check(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01" and row["STINT"] == start and row["ETINT"] == end, f"item bin identity/time {arm}/{index}")
            expected_stock = 4 if start < 10 or (arm == "change" and start >= 11) else 3
            check(row["STSZ"] == 4 and row["STOHA"] == expected_stock, f"item nominal/on-hand bin {arm}/{index}")
            check(row["NRO"] == (1 if arm == "change" and start == 10 else 0) and row["NBO"] == 0, f"item order/backorder bin {arm}/{index}")
            for name in ("MissionResults", "SystemResults", "StockTotalResults"):
                binrow = report_rows(report[name])[index]
                check(binrow["STINT"] == start and binrow["ETINT"] == end, f"{name} bin time {arm}/{index}")
        total = report_rows(report["ItemResultsTotal"])[0]
        expected_mean = (4 * 10 + 3 * (26 if arm == "control" else 1) + (0 if arm == "control" else 4 * 25)) / 36
        check(abs(total["STOHA"] - expected_mean) < 1e-5 and total["NRO"] == (0 if arm == "control" else 1), f"item integrated mean/order {arm}")
        summary = report_rows(report["ResultSummary"])[0]
        check(summary["NREP"] == 1 and summary["MSTF"] == 1 and abs(summary["MSUF"] - 2 / 3) < 1e-5, f"mission summary {arm}")
    for index, (a, b) in enumerate(zip(report_rows(reports["control"]["ItemResults"]), report_rows(reports["change"]["ItemResults"]))):
        for key in set(a) - {"STOHA", "NRO"}:
            check(a[key] == b[key], f"other item report cell same {index}/{key}")
    left = report_rows(reports["control"]["ItemResultsTotal"])[0]
    right = report_rows(reports["change"]["ItemResultsTotal"])[0]
    for key in set(left) - {"STOHA", "NRO"}:
        check(left[key] == right[key], f"other item total same: {key}")

    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "run_id": RUN_ID,
        "decision": "GO_BOUNDED" if not FAILURES else "NO_GO",
        "passed": not FAILURES,
        "checks_passed": CHECKS - len(FAILURES),
        "checks_total": CHECKS,
        "failures": FAILURES,
        "closure_sha256": digest(RUN / "closure.json"),
        "contract_sha256": digest(CASE / "contract.json"),
        "raw_files_sealed": len(raw),
        "source_sha256": {name: before[name] for name in ("control", "change", "parent_input", "runner")},
        "report_sha256": {arm: digest(RUN / f"{arm}-report-raw.json") for arm in ("control", "change")},
        "observed": {
            "initial_depot_stock": 4,
            "hour_5_order": "none in both event logs",
            "hour_10": "same ordinary depot issue of physical DU ID0; depot on-hand 4 to 3",
            "control_reorder": "none through hour 36; depot terminal on-hand 3",
            "change_reorder": "one order starts hour 10; one new physical DU ID6 delivered at hour 11; depot terminal on-hand 4",
            "item_results_bins": 72,
            "item_report_deltas": "STOHA differs in 50 bins from hour 11 onward; NRO differs only in [10,10.5); all other item-bin cells match",
            "other_reports": "ResultSummary, MissionResults and totals, FixedMissionResults and totals, SystemResults, StockTotalResults match exactly across arms",
        },
        "limits": [
            "One fixed seed, tracked DU at one depot, one ordinary demand, stock-based ROSIZ 2 versus scheduled 1, one-hour lead and 36-hour horizon.",
            "The native event log does not print the internal reorder-point computation; attribution to the scheduled ROSIZ row is source-bound inference from the matched pair.",
            "No time-based strategy, repeated demand/order, transfer-at-change, GUI display, population law, other engine, or full Issue #18 acceptance is established.",
            "Unrun v1.0.0 explicit-ISTOH3 draft is an excluded design diagnostic, not a native failure run.",
        ],
    }
    REVIEW.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['decision']} {result['checks_passed']}/{result['checks_total']}")


if __name__ == "__main__":
    main()
