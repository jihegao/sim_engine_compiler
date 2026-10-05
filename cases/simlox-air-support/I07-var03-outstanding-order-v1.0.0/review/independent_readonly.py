"""Independent read-only replay of the I07.var03 pending-order evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "i07-var03-outstanding-v100-ssh-20261005-01"
RUN = CASE / "runs" / RUN_ID
I07 = ROOT / "I07-var01-reorder-lead-time-v1.0.0"
I07_RUN = I07 / "runs" / "i07-var01-reorder-leadt-v100-ssh-20261005-01"
E15 = ROOT / "E15-var07-explicit-istoh-v1.0.1"
E15_RUN = E15 / "runs" / "e15-var07-explicit-three-v101-ssh-20261002-01"
OUTPUT = CASE / "review" / "independent-readonly-2026-10-05.json"
COUNT = 0
FAILURES: list[str] = []


def verify(ok: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not ok:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def index(document: dict, root: str) -> dict:
    return {table["name"]: table for table in document[root]["tables"]}


def entries(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def as_dicts(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for row in entries(table)]


def main() -> None:
    contract = read(CASE / "contract.json")
    closure = read(RUN / "closure.json")
    invocation = read(RUN / "invocation.json")
    steps = read(RUN / "steps.json")
    outcome = read(RUN / "outcome.json")
    verify(sha(RUN / "closure.json") == "ba3e97cd3dedd79796107e44e46fc9ae5e0b9b90ed4c4df0bdadcc6c2c53dec3", "frozen closure SHA")
    verify(sha(CASE / "contract.json") == "e511d3ce02d03b594517a0eaeec4d9906a7d06be907e6eba4f9c4ef3ea5dd8c3", "frozen contract SHA")
    verify(closure["run_id"] == invocation["run_id"] == contract["run_id"] == RUN_ID, "run identity")
    verify(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation raw seal")
    verify(closure["error"] is None and outcome["error"] is None and outcome["arms"] == {"late": "completed"}, "native run complete")
    verify(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH provenance")
    verify(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    verify(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native mutex")
    verify([step["name"] for step in steps] == ["late_import", "late_export", "late_calc", "late_report"], "four native steps")
    for step in steps:
        verify(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] and step["error"] is None, f"step completed and GUI preserved: {step['name']}")

    source_paths = {
        "contract": CASE / "contract.json",
        "builder": CASE / "build.py",
        "roundtrip_checker": CASE / "check_roundtrip.py",
        "parent_input": I07 / "change-input.json",
        "parent_signoff": I07 / "cli-scope-signoff-2026-10-05.md",
        "e15_input": E15 / "native-input-explicit-three.json",
        "e15_signoff": E15 / "cli-scope-signoff-2026-10-02.md",
        "settings_builder": E15 / "make_report_settings.py",
        "default_settings": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
        "selector": E15 / "runs" / "report-settings" / "item-position-results.sxs",
        "parent_index": I07 / "evidence-index.json",
        "parent_closure": I07_RUN / "closure.json",
        "late": CASE / "late-input.json",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "runner": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    before = closure["source_hashes_before"]
    verify(before == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after/invocation seals")
    verify(set(before) == set(source_paths), "all expected sources pinned")
    for name, path in source_paths.items():
        verify(path.is_file() and sha(path) == before[name], f"source byte seal: {name}")
    for name, expected in (
        ("builder", contract["source"]["builder_sha256"]),
        ("roundtrip_checker", contract["source"]["roundtrip_checker_sha256"]),
        ("late", contract["source"]["input_sha256"]),
        ("parent_input", contract["parents"]["I07_var01"]["input_sha256"]),
        ("parent_signoff", contract["parents"]["I07_var01"]["signoff_sha256"]),
        ("parent_index", contract["parents"]["I07_var01"]["evidence_index_sha256"]),
        ("parent_closure", contract["parents"]["I07_var01"]["run_closure_sha256"]),
        ("e15_input", contract["parents"]["E15"]["input_sha256"]),
    ):
        verify(before[name] == expected, f"contract source pin: {name}")
    raw = closure["raw"]
    verify(len(raw) == 13, "13 sealed native raw files")
    verify(set(raw) == {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}, "raw manifest covers all files")
    for name, pinned in raw.items():
        path = RUN / name
        verify(path.is_file() and path.stat().st_size == pinned["bytes"] and sha(path) == pinned["sha256"], f"raw file seal: {name}")
    verify(sha(RUN / "late-input.json") == before["late"], "native copied input equals frozen input")
    verify((RUN / "late.sxo").stat().st_size > 4, "usable SXO")
    conversion = (RUN / "late-run.log").read_text(encoding="utf-8-sig")
    verify("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion, "converter has zero errors and notes")
    verify(re.findall(r"\(warning #(\d+)\)", conversion) == ["108"], "only warning #108")
    verify(outcome["converter_summaries"] == {"late": [0, 1, 0]} and outcome["warning_codes"] == {"late": ["108"]}, "outcome diagnostics independently matched")

    parent = index(read(I07 / "change-input.json"), "model")
    authored = index(read(CASE / "late-input.json"), "model")
    exported = index(read(RUN / "late-roundtrip-raw.json"), "model")
    verify(len(parent) == len(authored) == len(exported) == 32, "32 table names")
    verify(set(parent) == set(authored) == set(exported), "no table added or lost")
    verify([name for name in parent if parent[name] != authored[name]] == ["ProblemDescription", "ChangesItemReorder"], "two-table source delta")
    verify(entries(parent["ChangesItemReorder"]) == [["TEACH-DU-01", "DEPOT-01", 5, 3, None, None, None, None]], "accepted h5 comparator row")
    verify(entries(authored["ChangesItemReorder"]) == [["TEACH-DU-01", "DEPOT-01", 10.5, 3, None, None, None, None]], "late h10.5 change row")
    verify(entries(authored["ItemReorder"])[0][:3] == ["TEACH-DU-01", "DEPOT-01", 1], "initial one-hour lead")
    verify(entries(authored["StockAllocation"])[1][3:7] == [4, 2, None, 3], "nominal4/ROSIZ2/ISTOH3")
    verify(sum(bool(entries(table)) for table in authored.values()) == 22, "22 authored row-containing tables")
    for name, table in authored.items():
        verify([c["name"] for c in table["columns"]] == [c["name"] for c in exported[name]["columns"]], f"export columns: {name}")
        source_rows = entries(table)
        output_rows = entries(exported[name])
        if source_rows:
            verify(source_rows == output_rows, f"exact authored row roundtrip: {name}")
        else:
            verify(all(all(cell is None for cell in row) for row in output_rows), f"empty table only gains null placeholder: {name}")
    independent_roundtrip = read(RUN / "late-roundtrip-check.json")
    verify(independent_roundtrip["passed"] and independent_roundtrip["authored_populated_tables"] == 22, "runner roundtrip record matches independent replay")

    late_log = (RUN / "late.log").read_bytes()
    control_log = (I07_RUN / "control.log").read_bytes()
    early_log = (I07_RUN / "change.log").read_bytes()
    e15_log = (E15_RUN / "model.log").read_bytes()
    verify(late_log == control_log == e15_log, "late event ledger byte-identical to accepted initial-lead controls")
    verify(late_log != early_log, "late and early-change event ledgers differ")
    late_lines = late_log.decode("utf-8-sig").splitlines()
    early_lines = early_log.decode("utf-8-sig").splitlines()
    for fragment in (
        "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
        "Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>",
        "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted",
        "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Item demand arrives",
        "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock",
        "Level: 2 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>",
        "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,5>",
        "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>",
        "Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,5>,<TEACH-DU-01,0,6>",
        "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0> to stock",
        "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success",
        "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success",
    ):
        verify(any(fragment in line for line in late_lines), f"native event/physical ID: {fragment[:72]}")
    verify(not any(line.startswith("Time: 10.5 ") and ("reorder" in line or "Stock at" in line or "Delivery" in line) for line in late_lines), "no h10.5 order or stock movement")
    verify(sum("reorder task" in line and "started" in line for line in late_lines) == 1 and sum("Delivery with" in line for line in late_lines) == 1, "one pre-existing order and delivery only")
    verify(any("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 3" in line for line in early_lines), "accepted h5 early change sets three-hour new order")
    verify(any("Time: 13 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in line for line in early_lines), "accepted early order arrives h13")

    report = index(read(RUN / "late-report-raw.json"), "report")
    original = index(read(I07_RUN / "control-report-raw.json"), "report")
    early = index(read(I07_RUN / "change-report-raw.json"), "report")
    verify(set(report) == set(original) == set(early), "selected report table set")
    for name in report:
        if name != "ProblemDescription":
            verify(report[name] == original[name], f"late equals accepted one-hour control report: {name}")
        if name not in {"ProblemDescription", "ItemResults", "ItemResultsTotal"}:
            verify(report[name] == early[name], f"non-item report equals accepted three-hour comparator: {name}")
    for name in ("MissionResults", "SystemResults", "StockTotalResults", "ItemResults"):
        verify(len(entries(report[name])) == 72, f"72 selected half-hour bins: {name}")
    items = as_dicts(report["ItemResults"])
    early_items = as_dicts(early["ItemResults"])
    for k, (late_row, early_row) in enumerate(zip(items, early_items)):
        start, end = k / 2, (k + 1) / 2
        verify(late_row["IID"] == "TEACH-DU-01" and late_row["STID"] == "DEPOT-01" and late_row["STINT"] == start and late_row["ETINT"] == end, f"item station/time bin {k}")
        verify(late_row["STSZ"] == 4 and late_row["STOHA"] == (3 if start < 10 else 2 if start < 11 else 4), f"late nominal/on-hand bin {k}")
        verify(early_row["STOHA"] == (3 if start < 10 else 2 if start < 13 else 4), f"early on-hand comparator bin {k}")
        verify(late_row["NRO"] == (1 if start == 10 else 0) and late_row["NBO"] == 0, f"order/backorder bin {k}")
        for field in set(late_row) - {"STOHA"}:
            verify(late_row[field] == early_row[field], f"all other item-bin cells match early {k}/{field}")
        for name in ("MissionResults", "SystemResults", "StockTotalResults"):
            cell = as_dicts(report[name])[k]
            verify(cell["STINT"] == start and cell["ETINT"] == end, f"{name} time bin {k}")
    late_total = as_dicts(report["ItemResultsTotal"])[0]
    early_total = as_dicts(early["ItemResultsTotal"])[0]
    verify(abs(late_total["STOHA"] - (3 * 10 + 2 * 1 + 4 * 25) / 36) < 1e-5 and late_total["NRO"] == 1, "late integrated item stock/order")
    verify(abs(early_total["STOHA"] - (3 * 10 + 2 * 3 + 4 * 23) / 36) < 1e-5 and early_total["NRO"] == 1, "early integrated item stock/order")
    for field in set(late_total) - {"STOHA"}:
        verify(late_total[field] == early_total[field], f"other item total same: {field}")
    summary = as_dicts(report["ResultSummary"])[0]
    verify(summary["NREP"] == 1 and summary["MSTF"] == 1 and abs(summary["MSUF"] - 2 / 3) < 1e-5, "one aborted and two successful mission summary")

    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "run_id": RUN_ID,
        "decision": "GO_BOUNDED" if not FAILURES else "NO_GO",
        "passed": not FAILURES,
        "checks_passed": COUNT - len(FAILURES),
        "checks_total": COUNT,
        "failures": FAILURES,
        "contract_sha256": sha(CASE / "contract.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "raw_files_sealed": len(raw),
        "input_sha256": sha(CASE / "late-input.json"),
        "report_sha256": sha(RUN / "late-report-raw.json"),
        "observed": {
            "source_contrast": "Accepted I07.var01 changed input differs only by description and ChangesItemReorder.TIMEC 5 to 10.5.",
            "new_run": "The two-unit depot order starts h10 with one-hour lead, completes h11, and delivers physical DU IDs 5 and 6. No reorder or stock movement is logged at h10.5.",
            "controls": "New event log equals accepted I07.var01 no-change and E15 explicit-three logs byte-for-byte; accepted I07.var01 h5-change order arrives h13.",
            "item_ledger": "Depot STSZ4 all 72 bins; STOHA3 until h10, 2 from h10 to h11, then 4; NRO1 only [10,10.5); NBO0 throughout.",
            "report_comparison": "Every non-description report table equals the accepted one-hour control. Against early-change comparator, only ItemResults.STOHA bins [11,13) and integrated ItemResultsTotal.STOHA differ.",
        },
        "limits": [
            "One fixed seed, one already-started stock-based reorder, one scheduled LEADT change, and a 36-hour horizon.",
            "The log does not separately confirm application of the h10.5 change; unchanged pending-order timing is the observed fact, supported by the source-isolated pair and accepted early-change control.",
            "No post-change new order, multiple outstanding orders, time-based interval, tie-time boundary, GUI behavior, other engine, or general update rule is proven.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['decision']} {result['checks_passed']}/{result['checks_total']}")


if __name__ == "__main__":
    main()
