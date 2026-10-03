"""Author replay for E11.var05 item route under autonomous policy."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e11-var05-item-route-v100-ssh-20261003-01"
CLOSURE_SHA = "89e51a620d96fea8f4d52005a82e9b5e201d79372193ab9b3ed92076f5fcac57"
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
    template = ROOT / contract["template"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    run = HERE / "runs" / RUN_ID
    ck("frozen contract/diff", contract["case_id"] == "E11" and contract["variant_id"] == "E11.var05" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("accepted item-route template", sha(template / "native-input.json") == contract["template"]["input_sha256"] == diff["template_sha256"])
    ck("child source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"])
    ck("table addition delta", diff["changed_tables"] == ["ProblemDescription"] and diff["added_tables"] == ["ItemStationStructure"] and diff["unchanged_parent_tables"] == 31 and diff["description_after"] == "E11.var05 AUTOM item-specific SLOW route 5h from/7h to counterexample")
    added = dict(zip(diff["added_columns"], diff["added_row"]))
    ck("one special route", added["IID"] == "TEACH-LRU-01" and added["STID"] == "BASE-01" and added["MSTID"] == "DEPOT-01" and added["OPOL"] == "SLOW" and added["TFRMS"] == 5 and added["TTOMS"] == 7 and added["PFRMS"] is None and added["PTOMS"] is None)
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("closure seal", sha(run / "closure.json") == CLOSURE_SHA)
    ck("native identity", inv["case_id"] == "E11" and inv["case_version"] == "1.0.0-candidate" and inv["run_id"] == closure["run_id"] == RUN_ID)
    ck("guarded SSH GUI queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    ck("local source pins", all(pins[key] == sha(HERE / name) for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
    ck("parent and template pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["template"] == contract["template"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("native source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        ck(f"raw {name}", (run / name).stat().st_size == meta["bytes"] > 4 and sha(run / name) == meta["sha256"])
    before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    ck("23-table roundtrip", sha(run / "input.json") == contract["native_input_sha256"] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 23 and "ItemStationStructure" in before and all(after.get(name) == table for name, table in before.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("zero-error valid output", "Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in conversion and "Starting simulation..." in conversion and "Saving results ..." in conversion and all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
    ck("ignored-route warnings", Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1, "2076": 1, "2077": 1, "445": 1}) and "TFRMS ignored for autonomous mission station: BASE-01" in conversion and "TTOMS ignored for autonomous mission station: BASE-01" in conversion and "Data is ignored for autonomous mission station: BASE-01" in conversion)
    events = (run / "model.log").read_bytes()
    ck("event log byte parity", events == (parent_run / "model.log").read_bytes() and sha(run / "model.log") == "ac9be222a308d3e78a7656bb82c3a19470c620d1e825e1d9871d32f22b2063a2")
    event_text = events.decode("utf-8-sig", errors="replace")
    ck("h10 fault demand", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in event_text and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in event_text)
    ck("h11 bidirectional zero-time transport", event_text.count("Time: 11  scheduled transport task 0 starts with 1 items/systems, transport time: 0") == 1 and event_text.count("Time: 11  scheduled transport task 1 starts with 1 items/systems, transport time: 0") == 1 and event_text.count("Time: 11  scheduled transport task 0 arrives with 1 items/systems") == 1 and event_text.count("Time: 11  scheduled transport task 1 arrives with 1 items/systems") == 1)
    ck("backorder ready restock", "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1" in event_text and "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in event_text and "Time: 12 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in event_text)
    ck("mission and resource outcomes", event_text.count("mission aborted:") == 1 and event_text.count("mission success:") == 2 and "allocated to maintenance task" not in event_text)
    child_report, parent_report = report(run / "report-raw.json"), report(parent_run / "report-raw.json")
    ck("report tables", set(child_report) == set(parent_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("only description differs", child_report["ProblemDescription"] != parent_report["ProblemDescription"] and all(child_report[name] == parent_report[name] for name in ("ResultSummary", "SystemResults", "StockTotalResults")))
    summary = rows(child_report["ResultSummary"])[0]
    ck("mission summary", abs(summary["MSUF"] - 2 / 3) < 1e-5 and summary["MTMF"] == 1)
    system, stock = rows(child_report["SystemResults"]), rows(child_report["StockTotalResults"])
    ck("72 aligned half-hour bins", len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
    ck("one fault repair demand", sum(r["NFAIL"] or 0 for r in system) == sum(r["NREPT"] or 0 for r in system) == sum(r["NDF"] or 0 for r in stock) == 1)
    ck("one-hour backorder", sum(r["NBO"] or 0 for r in stock) / 2 == 1 and stock[-1]["NBO"] == 0 and stock[-1]["PNB"] == 1)
    ck("terminal readiness", system[-1]["NSYRY"] == 1 and system[-1]["NSYA"] == 1 and abs(sum(r["NSYA"] or 0 for r in system) / 2 - 34.6666667) < 1e-4)
    result = {"schema": "simlox-e11-var05-item-route-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
