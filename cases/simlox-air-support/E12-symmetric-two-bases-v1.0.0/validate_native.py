"""Author replay of frozen E12 native source, events, ledgers and report."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "e12-symmetric-two-bases-v100-ssh-20261003-01"
PARENT_RUN_ID = "e07-item-route-v101-20261001-01"
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

    contract, diff = (read(HERE / name) for name in ("contract.json", "exact-diff.json"))
    parent = HERE.parent / contract["accepted_parent"]["package"]
    run = HERE / "runs" / RUN_ID
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("frozen source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"] == sha(run / "input.json"))
    ck("frozen diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and diff["changed_tables"] == ["ProblemDescription", "Station", "StockAllocation"] and diff["unchanged_parent_tables"] == 29)
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent / "runs" / PARENT_RUN_ID / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("builder replay", __import__("build").build() == (HERE / "native-input.json").read_bytes())
    ck("diff replay", __import__("describe_diff").describe() == diff)
    ck("native identity", inv["case_id"] == "E12" and inv["case_version"] == "1.0.0-candidate" and closure["run_id"] == inv["run_id"] == RUN_ID)
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
    ck("two units and aircraft", all(f"<TEACH-AIR-01,{i}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,{i}>>" in log for i in (0, 1)) and log.count("Time: 0 <TEACH-AIR-01,") == 4)
    for i, item in ((0, 1), (1, 2)):
        ck(f"opening base stock {i}", f"Time: 0 <TEACH-LRU-01,0,BASE-01,{i}> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,{i}> Level: 1 Items:<TEACH-LRU-01,0,{item}>," in log)
    ck("opening depot stock", "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>," in log)
    ck("six assigned missions", len(re.findall(r"mission allocates system:", log)) == 6 and all(log.count(f"mission allocates system: <TEACH-AIR-01,{i}>") == 3 for i in (0, 1)))
    ck("five success, one abort", log.count("mission success:") == 5 and log.count("mission aborted:") == 1 and "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log)
    ck("base zero local debit", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock" in log and "Time: 10  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,1>" in log)
    ck("base one untouched", "<TEACH-LRU-01,0,BASE-01,1> Take replacement item" not in log and "<TEACH-LRU-01,0,BASE-01,1> Backorder" not in log and "<TEACH-LRU-01,0,BASE-01,1> Stock initiated" in log)
    ck("no stockout", "Backorder added" not in log and "Backorder removed" not in log)
    ck("depot stock replenishes base zero", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log and "Time: 10  transport task 0 starts with 1 items/systems, transport time: 1" in log and "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock" in log)
    ck("failed item flows up and repairs", "Time: 10.1667  transport task 2 starts with 1 items/systems, transport time: 3" in log and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,3>" in log and "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock" in log)
    ck("base zero readiness", "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log and "Time: 10 <TEACH-AIR-01,BASE-01,1> System ready <TEACH-AIR-01,1>" in log)
    tables = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
    ck("report table set", set(tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = rows(tables["ResultSummary"])[0]
    ck("summary horizon and success", summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36 and abs(summary["MSUF"] - 5 / 6) < 1e-6)
    system, stock = (rows(tables[name]) for name in ("SystemResults", "StockTotalResults"))
    ck("72 contiguous half-hour system bins", len(system) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 and r["NSYA"] <= 2 for i, r in enumerate(system)))
    ck("72 contiguous half-hour stock bins", len(stock) == 72 and all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 and r["NBO"] == 0 and r["PNB"] == 1 for i, r in enumerate(stock)))
    ck("first failure report bin", system[19]["NFAIL"] == 1 and system[20]["NSYRP"] == 1 and system[20]["SYDT"] == 0.5 and system[21]["NREPT"] == 1)
    ck("terminal systems", system[-1]["NSYRY"] == 2 and system[-1]["NSYA"] == 2 and system[-1]["NFAIL"] == 0)
    ck("terminal stock", stock[-1]["NBO"] == 0 and "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item" in log)
    result = {"schema": "simlox-e12-symmetric-bases-v100-author-validation/v1", "passed": not failures,
              "checks_total": checks, "checks_passed": checks - len(failures), "failures": failures,
              "run_id": RUN_ID, "closure_sha256": sha(run / "closure.json"),
              "event_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
