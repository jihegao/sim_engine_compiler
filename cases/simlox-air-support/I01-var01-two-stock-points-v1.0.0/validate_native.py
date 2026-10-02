"""Replay sealed stock-only APID POINT selection and backorder evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
PARENT_RUN = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/runs/e01-v100-ssh-20260929-01"
RUNS = {arm: HERE / "runs" / f"i01-var01-{arm}-v100-ssh-20261002-01"
        for arm in ("stocked", "empty")}
INSTALL = {"manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(actual: object, target: float, tolerance: float = 1e-3) -> bool:
    return isinstance(actual, (float, int)) and math.isclose(
        float(actual), target, rel_tol=0, abs_tol=tolerance)


def rows(report: dict, name: str) -> list[dict]:
    table, = [t for t in report["report"]["tables"] if t["name"] == name]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(t) for t in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}
    def ck(name: str, value: bool) -> None:
        assert name not in checks
        checks[name] = bool(value)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_sources", sha(HERE / "contract.json") ==
       "b697f25a2e88efbdb501ea4df7bb3ebb585e84403c9b1d3e36218b565b08386f" and
       sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       all(sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, path in sources.items()))
    first, second = diff["parent_to_stocked"], diff["stocked_to_empty"]
    stock_rows = first["changed_tables"]["StockAllocation"]["after"]["instances"][0]["rows"]
    before_apid = second["changed_tables"]["Control"]["before"]["instances"][0]["rows"][0][3]
    after_apid = second["changed_tables"]["Control"]["after"]["instances"][0]["rows"][0][3]
    ck("exact_delta", not first["added_tables"] and not first["removed_tables"] and
       set(first["changed_tables"]) == {"StockAllocation", "ProblemDescription"} and
       stock_rows[0][:4] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1] and
       stock_rows[1][:4] == ["AIR_EMPTY", "TEACH-LRU-01", "BASE-01", 0] and
       not second["added_tables"] and not second["removed_tables"] and
       set(second["changed_tables"]) == {"Control", "ProblemDescription"} and
       before_apid == "AIR_BASIC" and after_apid == "AIR_EMPTY")
    ck("installed_sources", sha(INSTALL["manual"]) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(INSTALL["dictionary"]) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(INSTALL["simlox_exe"]) == contract["installed_source_sha256"]["simlox_exe"])
    authored = {arm: populated(parse_native(path)) for arm, path in sources.items()}
    ck("authored_tables", all(len(tables) == 20 for tables in authored.values()))
    evidence = {}
    for arm, run in RUNS.items():
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        hashes = closure["source_hashes_before"]
        ck(f"{arm}.closure", invocation["variant"] == arm and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["error"] is None and hashes == closure["source_hashes_after"] and
           hashes["input"] == sha(run / "input.json") == sha(sources[arm]) and
           hashes["parent"] == sha(PARENT) and
           hashes["contract"] == sha(HERE / "contract.json") and
           hashes["builder"] == sha(HERE / "build.py") and
           hashes["exact_diff"] == sha(HERE / "exact-diff.json") and
           hashes["diff_checker"] == sha(HERE / "describe_diff.py") and
           hashes["checker"] == sha(HERE / "check_roundtrip.py") and
           hashes["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
           all(hashes[key] == sha(path) for key, path in INSTALL.items()))
        ck(f"{arm}.guard", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
           [step["name"] for step in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(step["status"] == ("calc_observed" if step["name"] == "calc" else "completed") and
               step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
           for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == 20 and
           all(exported.get(name) == values for name, values in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 1" in converter and
           "warning #108" in converter and "warning #242" not in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        failures = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        cancellations = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission cancelled:")
        success = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission success:")
        surp_start = times(log, r"Time: ([\d.]+)  system SURP task 0 on <TEACH-AIR-01,0> started")
        surp_end = times(log, r"Time: ([\d.]+)  system SURP task 0 on <TEACH-AIR-01,0> completed")
        item_repair_end = times(log, r"Time: ([\d.]+)  item DIRP task 1 on <TEACH-LRU-01,0,\d+> completed")
        stock_take = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item")
        backorder_add = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder added")
        backorder_remove = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder removed")
        replacement_arrival = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives")
        ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
        ck(f"{arm}.common_events", starts == [8, 20, 32] and
           len(failures) == len(aborts) == len(surp_start) == len(surp_end) ==
           len(item_repair_end) == 1 and near(failures[0], 9.8829) and
           near(aborts[0], failures[0]) and near(surp_start[0], 10) and
           success == [22, 34] and not cancellations and
           "subject to attrition" not in log and "Damage BATTLE" not in log and
           "warning #242" not in converter and
           len(ready) == 5 and near(ready[0], surp_end[0]) and
           near(ready[-1], 34))
        if arm == "stocked":
            ck("stocked.local_spare", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1" in log and
               len(stock_take) == 1 and near(stock_take[0], 10) and
               not backorder_add and not backorder_remove and
               near(surp_end[0], 10.5) and near(item_repair_end[0], 11.1667) and
               len(replacement_arrival) == 1 and near(replacement_arrival[0], item_repair_end[0]) and
               "Put back replacement item" in log)
            ck("stocked.parent_event_log", sha(run / "model.log") == sha(PARENT_RUN / "model.log"))
        else:
            ck("empty.backorder_and_reused_repair", "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0" in log and
               not stock_take and len(backorder_add) == len(backorder_remove) ==
               len(replacement_arrival) == 1 and near(backorder_add[0], 10) and
               near(backorder_remove[0], 11.1667) and
               near(replacement_arrival[0], item_repair_end[0]) and
               near(surp_end[0], 11.5) and
               "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in log)
        summary, system, stock = (rows(parse_native(run / "report-raw.json"), name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near(sum(row[k] or 0 for k in ("NSYA", "NSYUA", "NSYLA")), 1) and
           near(sum(row[k] or 0 for k in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1)
           for row in system))
        exposure = .5 * sum(row["NSYRP"] or 0 for row in system)
        ck(f"{arm}.report_events", sum(row["NDAM"] or 0 for row in system) == 0 and
           sum(row["NREPT"] or 0 for row in system) == 1 and
           sum(row["NFAIL"] or 0 for row in system) == 1 and
           near(exposure, .5) and all(near(row["NSYLA"], 0) for row in system) and
           sum(row["NDF"] or 0 for row in stock) == 1 and
           sum(row["NWT"] or 0 for row in stock) == 1 and
           all(near(row["NDD"], 0) for row in stock))
        backorder_hours = .5 * sum(row["NBO"] or 0 for row in stock)
        if arm == "stocked":
            ck("stocked.stock_ledger", near(backorder_hours, 0) and
               all(near(row["NBO"], 0) and near(row["PNB"], 1) for row in stock))
            parent_report = parse_native(PARENT_RUN / "report-raw.json")
            ck("stocked.parent_report_ledgers", all(rows(parent_report, name) == current for name, current in
               (("ResultSummary", summary), ("SystemResults", system), ("StockTotalResults", stock))))
        else:
            ck("empty.stock_ledger", near(backorder_hours, 1.16667) and
               near(stock[20]["NBO"], 1) and near(stock[21]["NBO"], 1) and
               near(stock[22]["NBO"], 1 / 3) and
               near(stock[20]["WT"], 1.16667) and
               near(stock[20]["PNB"], 0) and near(stock[22]["PNB"], 2 / 3) and
               near(stock[-1]["NBO"], 0))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1) and
           near(system[-1]["NSYLA"], 0) and
           near(system[-1]["NSYUA"], 0) and near(stock[-1]["NBO"], 0) and
           near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 2 / 3))
        evidence[arm] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "failure_times": failures, "mission_abort_times": aborts,
                         "system_replacement_start": surp_start, "system_replacement_end": surp_end,
                         "item_repair_end": item_repair_end, "stock_take": stock_take,
                         "backorder_added": backorder_add, "backorder_removed": backorder_remove,
                         "backorder_hours": backorder_hours,
                         "system_repair_hours": exposure, "terminal_ready": system[-1]["NSYRY"],
                         "summary": summary[0]}
    result = {"schema": "simlox-i01-var01-two-stock-points-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "stock_only_APID_AIR_BASIC_vs_AIR_EMPTY_local_spare",
              "publication_state": "not_published"}
    output = HERE / "author-validation.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen author validation differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "sha256": sha(output)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
