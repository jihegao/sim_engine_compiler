"""Author replay for one source-bound E11 autonomous support gap."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e11-base-autom-v100-ssh-20261003-01"
CLOSURE_SHA = "2885c774b1551225c5fbcafc4c0b6669884600a0f03696ac29a3eba2ac34dd2c"
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
    run = HERE / "runs" / RUN_ID
    ck("frozen contract/diff", contract["case_id"] == "E11" and contract["case_version"] == "1.0.0-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("child source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"])
    ck("three-field exact diff", [(x["table"], x["column"]) for x in diff["changes"]] == [("ProblemDescription", "PDESC"), ("Station", "TYPE"), ("StationStructure", "PTOMS")] and diff["unchanged_parent_tables"] == 29)
    ck("closure seal", sha(run / "closure.json") == CLOSURE_SHA)
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("native identity", inv["case_id"] == "E11" and inv["case_version"] == "1.0.0-candidate" and inv["run_id"] == closure["run_id"] == RUN_ID)
    ck("guarded SSH GUI queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    ck("local source pins", all(pins[key] == sha(HERE / name) for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
    ck("parent pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("native source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        ck(f"raw {name}", (run / name).stat().st_size == meta["bytes"] > 4 and sha(run / name) == meta["sha256"])
    before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
    ck("source copy and 22-table roundtrip", sha(run / "input.json") == contract["native_input_sha256"] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 22 and all(after.get(name) == table for name, table in before.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion zero errors", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in conversion and "Starting simulation..." in conversion and "Saving results ..." in conversion)
    ck("warning meaning", Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1, "2076": 1, "2077": 1}) and "TFRMS ignored for autonomous mission station: BASE-01" in conversion and "TTOMS ignored for autonomous mission station: BASE-01" in conversion)
    ck("nonempty native output", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
    child_report, parent_report = report(run / "report-raw.json"), report(parent_run / "report-raw.json")
    ck("report table set", set(child_report) == set(parent_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("summary parity", child_report["ResultSummary"] == parent_report["ResultSummary"] and abs(rows(child_report["ResultSummary"])[0]["MSUF"] - 2 / 3) < 1e-5)
    system, stock = rows(child_report["SystemResults"]), rows(child_report["StockTotalResults"])
    parent_system, parent_stock = rows(parent_report["SystemResults"]), rows(parent_report["StockTotalResults"])
    ck("72 aligned bins", len(system) == len(stock) == len(parent_system) == len(parent_stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
    ck("one fault repair demand", sum(r["NFAIL"] or 0 for r in system) == sum(r["NREPT"] or 0 for r in system) == sum(r["NDF"] or 0 for r in stock) == 1)
    ck("one versus three hour backorder", abs(sum(r["NBO"] or 0 for r in stock) / 2 - 1) < 1e-6 and abs(sum(r["NBO"] or 0 for r in parent_stock) / 2 - 3) < 1e-6)
    ck("two hours more availability", abs((sum(r["NSYA"] or 0 for r in system) - sum(r["NSYA"] or 0 for r in parent_system)) / 2 - 2) < 1e-5)
    ck("report divergence bins", {i for i in range(72) if system[i] != parent_system[i]} == {20, 22, 23, 24, 25, 26} and {i for i in range(72) if stock[i] != parent_stock[i]} == {20, 22, 23, 24, 25})
    ck("terminal readiness and backorder", system[-1]["NSYRY"] == 1 and stock[-1]["NBO"] == 0 and stock[-1]["PNB"] == 1)
    events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("failure and demand inside isolation", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in events and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in events and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in events)
    ck("depot spare ID0 held", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in events and "Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1" in events)
    ck("failed ID1 held", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  scheduled transport task 0" in events)
    ck("nothing moves during isolation", not any(float(m.group(1)) < 11 for m in re.finditer(r"Time: ([\d.]+)  scheduled transport task \d+ (?:starts with|arrives with)", events)))
    ck("bidirectional zero-hour reconnect", "Time: 11  scheduled transport task 0 starts with 1 items/systems, transport time: 0" in events and "Time: 11  scheduled transport task 1 starts with 1 items/systems, transport time: 0" in events and events.count("Time: 11  scheduled transport task 0 arrives with 1 items/systems") == 1 and events.count("Time: 11  scheduled transport task 1 arrives with 1 items/systems") == 1)
    ck("spare/backorder and aircraft ready", "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in events and "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1" in events and "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in events)
    ck("failed ID1 repair and restock", "Time: 11 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" in events and "Time: 12 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in events)
    ck("two physical transports closed", events.count("starts with 1 items/systems, transport time: 0") == events.count("arrives with 1 items/systems") == 2)
    ck("one item cycle", events.count("critical random failure added") == events.count("Backorder added") == events.count("Backorder removed") == events.count("Take replacement item") == events.count("Put back replacement item") == 1)
    ck("mission outcomes", events.count("mission aborted:") == 1 and events.count("mission success:") == 2 and "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in events and "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:" in events)
    ck("no resource allocation", "requests resources: no resources needed" in events and "allocated to maintenance task" not in events)
    result = {"schema": "simlox-e11-autonomous-support-gap-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
