"""Author replay for the source-bounded E11.var03 no-reconnection case."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e11-var03-no-reconnect-v100-ssh-20261003-01"
CLOSURE_SHA = "f299e7d9e6804041f16e98b3db13d9dac6aa1fddafaade2d0e509802f40dfaf4"
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
    ck("frozen contract/diff", contract["case_id"] == "E11" and contract["variant_id"] == "E11.var03" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted parent", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("child source", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"])
    ck("source diff", diff["changed_tables"] == ["ProblemDescription", "TransportPolicyProfile"] and diff["unchanged_parent_tables"] == 30)
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("frozen closure", sha(run / "closure.json") == CLOSURE_SHA)
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
    ck("22-table roundtrip", sha(run / "input.json") == contract["native_input_sha256"] and read(run / "roundtrip-validation.json")["passed"] is True and len(before) == 22 and all(after.get(name) == table for name, table in before.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion and valid output", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in conversion and "Starting simulation..." in conversion and "Saving results ..." in conversion and all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
    ck("warnings", Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1, "2076": 1, "2077": 1}) and "TFRMS ignored for autonomous mission station: BASE-01" in conversion and "TTOMS ignored for autonomous mission station: BASE-01" in conversion)
    child_report, parent_report = report(run / "report-raw.json"), report(parent_run / "report-raw.json")
    ck("report tables", set(child_report) == set(parent_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary, parent_summary = rows(child_report["ResultSummary"])[0], rows(parent_report["ResultSummary"])[0]
    ck("mission summary", abs(summary["MTMF"] - 1 / 3) < 1e-5 and summary["MSUF"] == 0 and abs(parent_summary["MSUF"] - 2 / 3) < 1e-5)
    system, stock = rows(child_report["SystemResults"]), rows(child_report["StockTotalResults"])
    parent_system, parent_stock = rows(parent_report["SystemResults"]), rows(parent_report["StockTotalResults"])
    ck("72 aligned bins", len(system) == len(stock) == len(parent_system) == len(parent_stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
    ck("exact changed bins", {i for i in range(72) if system[i] != parent_system[i]} == {20, *range(22, 72)} and {i for i in range(72) if stock[i] != parent_stock[i]} == {20, *range(22, 72)})
    ck("one fault, no completed repair", sum(r["NFAIL"] or 0 for r in system) == sum(r["NDF"] or 0 for r in stock) == 1 and sum(r["NREPT"] or 0 for r in system) == 0)
    ck("persistent backorder", all(stock[i]["NBO"] == (0 if i < 20 else 1) for i in range(72)) and all(stock[i]["PNB"] == (1 if i < 20 else 0) for i in range(72)))
    ck("terminal system", system[-1]["NSYRY"] == 0 and system[-1]["NSYUA"] == 1 and system[-1]["NSYA"] == 0 and system[-1]["NSYWI"] == 1)
    ck("parent terminal contrast", parent_system[-1]["NSYRY"] == 1 and parent_stock[-1]["NBO"] == 0 and parent_stock[-1]["PNB"] == 1)
    ck("availability difference", abs(sum(r["NSYA"] or 0 for r in system) / 2 - 10) < 1e-4 and abs(sum(r["NSYA"] or 0 for r in parent_system) / 2 - 34.6666667) < 1e-4)
    ck("backorder exposure", abs(sum(r["NBO"] or 0 for r in stock) / 2 - 26) < 1e-6 and abs(sum(r["NBO"] or 0 for r in parent_stock) / 2 - 1) < 1e-6)
    events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("first fault and demand", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in events and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in events and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in events)
    ck("spare removed from depot stock and queued", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in events and "Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1" in events)
    ck("failed item queued upstream", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  scheduled transport task 0" in events)
    ck("horizon sentinel tasks", events.count("scheduled to start at 1.79769e+308") == 2)
    ck("no physical transports", not re.search(r"scheduled transport task \d+ (?:starts with|arrives with)", events) and "Replacement item arrives" not in events and "<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" not in events)
    ck("repair incomplete", "Time: 10.1667  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in events and "Backorder removed" not in events and "System ready" not in events)
    ck("mission outcomes", events.count("mission aborted:") == 1 and events.count("mission cancelled:") == 2 and "Time: 20.3333 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in events and "Time: 32.3333 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission cancelled:" in events and "mission success:" not in events)
    ck("no resource allocation", "requests resources: no resources needed" in events and "allocated to maintenance task" not in events)
    result = {"schema": "simlox-e11-var03-no-reconnect-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
