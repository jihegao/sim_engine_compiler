"""Author replay of the item-group by station-group depot ItemRepair intersection."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "e12-var04-item-station-group-v100-ssh-20261003-01"
RAW_NAMES = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
             "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
             "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract, diff = (read(HERE / n) for n in ("contract.json", "exact-diff.json"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    run = HERE / "runs" / RUN_ID
    inv, closure, steps = (read(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("frozen source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"] == sha(run / "input.json"))
    ck("frozen diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and diff["changed_tables"] == ["Item", "ItemRepair", "ProblemDescription", "Station"] and diff["unchanged_parent_tables"] == 28 and len(diff["changed_cells"]) == 5)
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("builder replay", __import__("build").build() == (HERE / "native-input.json").read_bytes())
    ck("diff replay", __import__("describe_diff").describe() == diff)
    ck("native identity", inv["case_id"] == "E12" and inv["variant_id"] == "E12.var04" and inv["case_version"] == "1.0.0-candidate" and closure["run_id"] == inv["run_id"] == RUN_ID)
    ck("guarded queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"),
                      ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
        ck(f"source pin {key}", pins[key] == sha(HERE / name))
    ck("parent pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw artifact set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        path = run / name
        ck(f"raw {name}", path.stat().st_size == meta["bytes"] > 4 and sha(path) == meta["sha256"])
    source, roundtrip = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    ck("22 table exact roundtrip", read(run / "roundtrip-validation.json")["passed"] is True and len(source) == 22 and all(roundtrip.get(name) == table for name, table in source.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero-error valid output", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and "Starting simulation..." in conversion and "Saving results ..." in conversion and all((run / n).stat().st_size > 1000 for n in ("model.sxo", "model.log", "report-raw.json")))
    ck("warning identity", Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for i, unit, base, spare, failtime, returntime, readytime in ((0, "TEACH-UNIT", "BASE-01", 1, "9.8829", "10.7579", "11.2579"), (1, "TEACH-UNIT-2", "BASE-02", 2, "11.1325", "11.5", "12.5")):
        ck(f"distinct unit {base}", f"Time: 0 <TEACH-AIR-01,{i}> nbr ready increased at unit: <{unit} at <{base},0>>" in log)
        ck(f"opening spare {base}", f"Time: 0 <TEACH-LRU-01,0,{base},0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,{base},0> Level: 1 Items:<TEACH-LRU-01,0,{spare}>," in log)
        ck(f"failure {base}", f"Time: {failtime} <TEACH-AIR-01,{i}> critical random failure added" in log)
        ck(f"local system repair {base}", f"Time: {returntime} <TEACH-AIR-01,{base},0> System arrives <TEACH-AIR-01,{i}>" in log and f"Time: {readytime} <TEACH-AIR-01,{base},0> System ready <TEACH-AIR-01,{i}>" in log)
        ck(f"local spare debit {base}", f"Time: {returntime} <TEACH-LRU-01,0,{base},0> Take replacement item <TEACH-LRU-01,0,{spare}> from stock" in log)
    ck("opening depot", "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>," in log)
    ck("six mission opportunities", log.count("mission ordered: BASIC-MISSION") == 6 and log.count("mission allocates system:") == 6)
    ck("four aborts two success", log.count("mission aborted:") == 4 and log.count("mission success:") == 2)
    ck("depot replenishment", "Time: 11.7579 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock" in log and "Time: 15.9246 <TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,3> to stock" in log)
    ck("depot backorder resolved", "Time: 11.5 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added" in log and "Time: 14.9246 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed" in log)
    ck("two failed items repair", "Time: 13.9246 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,3>" in log and "Time: 14.8333 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,4>" in log and "Time: 15.8333 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,4> to stock" in log)
    ck("BASE-01 group duration", "Time: 10.7579  system SURP task 0 on <TEACH-AIR-01,0> started" in log and "Time: 11.2579  system SURP task 0 on <TEACH-AIR-01,0> completed" in log and "Time: 10.7579  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours" in log)
    ck("BASE-02 individual duration", "Time: 11.5  system SURP task 1 on <TEACH-AIR-01,1> started" in log and "Time: 12.5  system SURP task 1 on <TEACH-AIR-01,1> completed" in log and "Time: 11.5  remove subitem subtask 2 seqno 1 within system SURP task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.333333 hours" in log and "Time: 11.8333  fit subitem subtask 3 seqno 2 within system SURP task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.666667 hours" in log)
    ck("no duplicate first-wave repair", len(re.findall(r"Time: (?:10\.7579|11\.5)  system SURP task \d on <TEACH-AIR-01,[01]> started", log)) == 2 and "Time: 12  system SURP task 1 on <TEACH-AIR-01,1> completed" not in log)
    current = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
    prior = {t["name"]: t for t in parse_native(parent_run / "report-raw.json")["report"]["tables"]}
    ck("report tables", set(current) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("event log byte parity", (run / "model.log").read_bytes() == (parent_run / "model.log").read_bytes())
    ck("only description differs", current["ProblemDescription"] != prior["ProblemDescription"] and all(current[name] == prior[name] for name in ("ResultSummary", "SystemResults", "StockTotalResults")))
    ck("physical depot repairs", all(f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>" in log and f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>" in log for item in (3, 4, 5)))
    summary = rows(current["ResultSummary"])[0]
    ck("36h and two sixths", summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36 and abs(summary["MSUF"] - 2 / 6) < 1e-6)
    system, stock = (rows(current[name]) for name in ("SystemResults", "StockTotalResults"))
    ck("72 system bins", len(system) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(system)))
    ck("72 stock bins", len(stock) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(stock)))
    ck("terminal sampled state and backorder", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and stock[-1]["NBO"] == 0 and "Time: 36 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
    result = {"schema": "simlox-e12-var04-item-station-group-v100-author-validation/v1", "passed": not failures,
              "checks_total": checks, "checks_passed": checks - len(failures), "failures": failures,
              "run_id": RUN_ID, "closure_sha256": sha(run / "closure.json"), "event_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
