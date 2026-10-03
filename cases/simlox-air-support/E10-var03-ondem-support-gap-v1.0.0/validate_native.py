"""Author replay of bounded E10.var03 ONDEM support-gap evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e10-var03-gap-v100-ssh-20261003-01"
CLOSURE_SHA = "a179aa56096ce3d813505a8ee98c261cd6f57d5a2a4e2331bea2fdbefb9595ac"
RAW_NAMES = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def report(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["report"]["tables"]}


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, result: bool) -> None:
        nonlocal checks
        checks += 1
        if not result:
            failures.append(label)

    contract, diff = (read(HERE / name) for name in ("contract.json", "exact-diff.json"))
    parent = ROOT / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    comparator = ROOT / contract["accepted_comparator"]["package"]
    comparator_run = comparator / "runs" / contract["accepted_comparator"]["run_id"]
    run = HERE / "runs" / RUN_ID
    ck("frozen contract/diff", contract["case_id"] == "E10" and contract["variant_id"] == "E10.var03" and contract["case_version"] == "1.0.0-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted ONDEM parent", sha(parent / "native-input-ondem.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("accepted FIXED comparator", sha(comparator / "native-input-fixed.json") == contract["accepted_comparator"]["input_sha256"] and sha(comparator_run / "closure.json") == contract["accepted_comparator"]["native_closure_sha256"])
    ck("child source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"])
    ck("closure seal", sha(run / "closure.json") == CLOSURE_SHA)
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("native run identity", inv["case_id"] == "E10" and inv["variant_id"] == "E10.var03" and inv["case_version"] == "1.0.0-candidate" and inv["run_id"] == closure["run_id"] == RUN_ID)
    ck("guarded SSH GUI queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    ck("local source pins", all(pins[key] == sha(HERE / name) for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
    ck("parent/comparator pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"] and pins["comparator"] == contract["accepted_comparator"]["input_sha256"] and pins["comparator_closure"] == contract["accepted_comparator"]["native_closure_sha256"])
    ck("native source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        ck(f"raw {name}", (run / name).stat().st_size == meta["bytes"] > 4 and sha(run / name) == meta["sha256"])
    before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    ck("source copy and 22-table roundtrip", sha(run / "input.json") == contract["native_input_sha256"] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 22 and all(after.get(name) == table for name, table in before.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion warning meaning", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}) and "(warning #108) Enabling simulation log may generate extensive data in log file" in conversion)
    ck("nonempty native output", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
    child_report, fixed_report, ondem_report = (report(path) for path in (run / "report-raw.json", comparator_run / "report-raw.json", parent_run / "report-raw.json"))
    ck("report table set", set(child_report) == set(fixed_report) == set(ondem_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"{name} exact h11 FIXED comparator equality", child_report[name] == fixed_report[name])
    ck("report differs from immediate ONDEM", child_report["SystemResults"] != ondem_report["SystemResults"] and child_report["StockTotalResults"] != ondem_report["StockTotalResults"] and child_report["ResultSummary"] == ondem_report["ResultSummary"])
    system, stock = rows(child_report["SystemResults"]), rows(child_report["StockTotalResults"])
    ondem_system, ondem_stock = rows(ondem_report["SystemResults"]), rows(ondem_report["StockTotalResults"])
    ck("72 aligned half-hour bins", len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
    ck("one fault repair demand", sum(r["NFAIL"] or 0 for r in system) == sum(r["NREPT"] or 0 for r in system) == sum(r["NDF"] or 0 for r in stock) == 1)
    ck("gap adds one backorder hour", abs(sum(r["NBO"] or 0 for r in stock) / 2 - 3) < 1e-6 and abs(sum(r["NBO"] or 0 for r in ondem_stock) / 2 - 2) < 1e-6)
    ck("gap delays readiness one hour", abs((sum(r["NSYA"] or 0 for r in ondem_system) - sum(r["NSYA"] or 0 for r in system)) / 2 - 1) < 1e-6)
    ck("terminal readiness/backorder and missions", system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0 and abs(rows(child_report["ResultSummary"])[0]["MSUF"] - 2 / 3) < 1e-5)
    log = (run / "model.log").read_bytes()
    ck("complete event log equals h11 FIXED comparator", log == (comparator_run / "model.log").read_bytes())
    events = log.decode("utf-8-sig", errors="replace")
    ck("support reopening scheduled", "Time: 0  scheduled transport task 0 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11" in events)
    ck("fault and demand inside gap", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in events and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in events and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in events)
    ck("demand retained on h11 schedule", "Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 0" in events and "Time: 10  transport task 1 starts with" not in events)
    ck("downward ID0 h11-h13", "Time: 11  scheduled transport task 0 starts with 1 items/systems, transport time: 2" in events and "Time: 13 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in events and "Time: 13 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 3" in events)
    ck("upward ID1 repair/restock", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached" in events and "Time: 12.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" in events and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in events)
    ck("two physical transports closed", events.count("starts with 1 items/systems, transport time: 2") == events.count("arrives with 1 items/systems") == 2)
    ck("aircraft and later missions", "Time: 13.3333 <TEACH-AIR-01,BASE-01,0> System ready" in events and "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in events and "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:" in events)
    ck("one physical item cycle", events.count("critical random failure added") == 1 and events.count("Item demand arrives from pos <TEACH-AIR-01") == 1 and events.count("Backorder added") == events.count("Backorder removed") == events.count("Take replacement item") == events.count("Put back replacement item") == 1)
    ck("no resource demand", "requests resources: no resources needed" in events and "allocated to maintenance task" not in events)
    result = {"schema": "simlox-e10-var03-ondem-support-gap-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
