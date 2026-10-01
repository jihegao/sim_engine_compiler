"""Source-bound author replay of the E07 item-specific SLOW native run."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from check_roundtrip import native_json, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e07-item-slow-v100-ssh-20261002-01"
RUN = HERE / "runs" / RUN_ID
PARENT = ROOT / "E07-item-specific-transport-v1.0.1"
PARENT_RUN = PARENT / "runs/e07-item-route-v101-20261001-01"
REPORT = HERE / "author-validation.json"
EXE = Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")
MANUAL = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")
DICTIONARY = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt")
PYTHON = Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
PARENT_LOG_SHA = "7510c95d4c96b3de565123c5fa117e3ebc8b051d56b2255617b7ed8c42adc39a"
PARENT_REPORT_SHA = "c68d371f695d4fcd0f2610e8147f0f40513715ce1fa76e43e9165297718530cf"
PARENT_CLOSURE_SHA = "c73b4316c0fc44ad31484a7a4eab73d60294d3f054f20d1691cca008d85b64cd"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, name: str) -> list[dict]:
    matches = [table for table in doc["report"]["tables"] if table["name"] == name]
    if len(matches) != 1:
        raise AssertionError(f"missing or duplicate {name}")
    table = matches[0]
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def validate() -> dict:
    passed, differences = 0, []

    def need(label: str, condition: bool) -> None:
        nonlocal passed
        passed += 1
        if not condition:
            differences.append(label)

    contract = native_json(HERE / "contract.json")
    parent_input, support_input = PARENT / "native-input.json", ROOT / "E04-upstream-transport-fast-v1.0.0/native-input.json"
    source = HERE / "native-input.json"
    need("contract identity", contract["case_id"] == "E07" and contract["variant_id"] == "E07.var01"
         and contract["version"] == "1.0.0-candidate" and contract["direct_parent"]["native_run_id"] == PARENT_RUN.name)
    need("parent/support/input fingerprints", sha(parent_input) == contract["direct_parent"]["input_sha256"]
         and sha(support_input) == contract["support_prerequisite"]["input_sha256"]
         and sha(source) == sha(RUN / "input.json") == contract["input_sha256"])
    need("manual/dictionary/executable fingerprints", sha(MANUAL) == contract["source"]["manual_pdf_sha256"]
         and sha(DICTIONARY) == contract["source"]["dictionary_sha256"] and sha(EXE) == EXE_SHA)
    parent_doc, child_doc = native_json(parent_input), native_json(source)
    parent_tables = {table["name"]: table for table in parent_doc["model"]["tables"]}
    child_tables = {table["name"]: table for table in child_doc["model"]["tables"]}
    need("exact two-table source delta", set(parent_tables) == set(child_tables)
         and {name for name in parent_tables if parent_tables[name] != child_tables[name]}
         == {"ProblemDescription", "ItemStationStructure"})
    item = child_tables["ItemStationStructure"]
    keys = [column["name"] for column in item["columns"]]
    item_row = dict(zip(keys, item["instances"][0]["rows"][0]))
    general = child_tables["StationStructure"]
    general_row = dict(zip([column["name"] for column in general["columns"]], general["instances"][0]["rows"][0]))
    need("specific SLOW and general FAST", item_row["IID"] == "TEACH-LRU-01" and item_row["STID"] == "BASE-01"
         and item_row["MSTID"] == "DEPOT-01" and item_row["OPOL"] == "SLOW"
         and item_row["TFRMS"] == 1 and item_row["TTOMS"] == 3 and item_row["DFRAC"] == 1
         and item_row["CFRMS"] is None and item_row["CTOMS"] is None
         and general_row["OPOL"] == "FAST" and general_row["TFRMS"] == general_row["TTOMS"] == 2)
    invocation, closure, steps = (native_json(RUN / filename) for filename in ("invocation.json", "closure.json", "steps.json"))
    expected = {
        "input": source, "parent": parent_input, "support": support_input,
        "table_dictionary": DICTIONARY, "manual": MANUAL,
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py", "python": PYTHON,
        "runner_script": HERE / "run_native_ssh.ps1", "simlox_exe": EXE,
    }
    need("native source seals", set(closure["source_hashes_before"]) == set(expected)
         and closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"]
         and all(closure["source_hashes_before"][name] == sha(path) for name, path in expected.items()))
    need("session/GUI/queue", invocation["run_id"] == RUN_ID and invocation["variant"] == "item-slow"
         and invocation["session_id"] == 0 and invocation["ssh_connection_present"]
         and "sshd.exe" in invocation["ssh_ancestor_names"]
         and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
         and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    need("closure and native steps", closure["error"] is None
         and closure["invocation_sha256"] == sha(RUN / "invocation.json")
         and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
         and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    need("twelve sealed raw artifacts", len(closure["raw"]) == 12
         and all((RUN / name).is_file() and (RUN / name).stat().st_size == seal["bytes"]
                 and sha(RUN / name) == seal["sha256"] for name, seal in closure["raw"].items()))
    before, after = populated(native_json(source)), populated(native_json(RUN / "roundtrip-raw.json"))
    rt = native_json(RUN / "roundtrip-validation.json")
    need("exact 22 authored-table roundtrip", len(before) == 22
         and all(after.get(name) == contents for name, contents in before.items())
         and rt["passed"] and not rt["differences"])
    native_defaults = {"ItemReorder", "ItemReplacement", "MaterielPM", "MissionPreparation", "PMLocation",
                       "Resource", "ResourceAllocation", "SubTaskResource", "SubTaskType", "TaskResource"}
    extra = set(after) - set(before)
    need("native-added tables are all-null placeholders", extra == native_defaults
         and all(len(after[name][1]) == 1 and all(value is None for value in after[name][1][0]) for name in extra))
    calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    need("zero conversion errors and sole ENLOG warning", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc
         and Counter(re.findall(r"\(warning #(\d+)\)", calc)) == Counter({"108": 1}))
    need("accepted FAST raw control", sha(PARENT_RUN / "model.log") == PARENT_LOG_SHA
         and sha(PARENT_RUN / "report-raw.json") == PARENT_REPORT_SHA
         and sha(PARENT_RUN / "closure.json") == PARENT_CLOSURE_SHA)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    fast = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    times = [float(m[1]) for line in log.splitlines() if (m := re.match(r"^Time: ([0-9.]+) ", line))]
    need("ordered native events", bool(times) and times == sorted(times) and times[-1] <= 36)
    need("shared failure and mission abort", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log
         and "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log
         and "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in fast
         and log.count("critical random failure added") == log.count("mission aborted:") == 1)
    need("base demand/backorder shared", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in log
         and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log
         and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in fast)
    need("SLOW defers depot issue", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item" not in log
         and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in fast)
    need("depot demand occurs only on faulty arrival",
         "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" not in log
         and log.count("<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives from pos") == 1)
    need("faulty instance 1 upward three hours", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  transport task 0" in log
         and "Time: 10.1667  transport task 0 starts with 1 items/systems, transport time: 3" in log
         and "Time: 13.1667  transport task 0 arrives with 1 items/systems" in log
         and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" in log)
    need("depot demand/issue on faulty arrival", "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in log
         and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log)
    need("replacement instance 0 downward one hour", "Time: 13.1667  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  transport task 2" in log
         and "Time: 13.1667  transport task 2 starts with 1 items/systems, transport time: 1" in log
         and "Time: 14.1667  transport task 2 arrives with 1 items/systems" in log
         and "Time: 14.1667 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in log)
    need("exact two attached physical shipments", log.count(" attached to  transport task ") == 2
         and log.count(" arrives with 1 items/systems") == 2)
    need("backorder duration/fit/readiness", "Time: 14.1667 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 4.16667" in log
         and "Time: 14.1667  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>" in log
         and "Time: 14.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in log
         and "Time: 14.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log
         and "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in fast)
    need("faulty instance repaired and restocked", "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>" in log
         and "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>" in log
         and "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log
         and log.count("Take replacement item <TEACH-LRU-01,0,0> from stock") == 1
         and log.count("Put back replacement item <TEACH-LRU-01,0,1> to stock") == 1)
    need("one abort/two later successes", log.count("mission aborted:") == 1 and log.count("mission success:") == 2
         and "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed" in log
         and "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission completed" in log)
    report, fast_report = native_json(RUN / "report-raw.json"), native_json(PARENT_RUN / "report-raw.json")
    system, stock, summary = rows(report, "SystemResults"), rows(report, "StockTotalResults"), rows(report, "ResultSummary")
    fast_stock = rows(fast_report, "StockTotalResults")
    need("72 aligned half-hour System/Stock bins", len(system) == len(stock) == len(fast_stock) == 72
         and all((a["STINT"], a["ETINT"], b["STINT"], b["ETINT"]) == (i / 2, (i + 1) / 2, i / 2, (i + 1) / 2)
                 for i, (a, b) in enumerate(zip(system, stock))))
    need("one native failure/repair/demand", len(summary) == 1 and summary[0]["NREP"] == 1
         and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36
         and sum(row["NFAIL"] for row in system) == sum(row["NREPT"] for row in system) == 1
         and sum(row["NDF"] for row in stock) == 1)
    need("backorder occupancy and terminal state", abs(sum(row["NBO"] for row in stock) * 0.5 - 4.1666667) < 1e-4
         and abs(sum(row["NBO"] for row in fast_stock) * 0.5 - 1.0) < 1e-6
         and system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0 and stock[-1]["PNB"] == 1)
    return {"schema": "simlox-e07-var01-item-slow-author-validation/v1", "passed": not differences,
            "checks": passed, "differences": differences, "run_id": RUN_ID,
            "input_sha256": sha(source), "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"),
            "report_sha256": sha(RUN / "report-raw.json"), "raw_seals": len(closure["raw"]),
            "fast_parent_run_id": PARENT_RUN.name, "fast_parent_model_log_sha256": PARENT_LOG_SHA,
            "observed_slow_timing_hours": {"base_demand": 10, "faulty_up_start": 10.1667,
                                           "depot_arrival_and_issue": 13.1667, "spare_base_arrival": 14.1667,
                                           "system_ready": 14.5},
            "scope": "one_fixed_seed_item_specific_slow_demand", "publication_state": "not_published"}


def main() -> None:
    result = validate()
    REPORT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "report_sha256": sha(REPORT)}))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
