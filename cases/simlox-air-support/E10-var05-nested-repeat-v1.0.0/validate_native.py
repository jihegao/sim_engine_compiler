"""Author replay of the bounded E10.var05 nested-repeat evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e10-var05-nested-v100-ssh-20261003-01"
CLOSURE_SHA = "d6daf2d9163fa478112722075b6968435d2007e0f5d3ca59f5ab6da58e895f5e"
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
    ck("frozen contract and diff", contract["case_id"] == "E10" and contract["variant_id"] == "E10.var05" and contract["case_version"] == "1.0.0-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted parent input", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"])
    ck("accepted parent closure and index", sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"])
    ck("child input", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"])
    profiles = next(t for t in parse_native(HERE / "native-input.json")["model"]["tables"] if t["name"] == "TransportPolicyProfile")
    ck("nested repeated source shape", profiles["instances"][0]["rows"] == [
        ["DOWN-POLICY", "REPEAT-FIXED", 8.0, 2, 3.0, None, None, None, None, None],
        ["REPEAT-FIXED", "FIXED", 0.0, 1, 0.0, None, 1, 2.0, None, None],
    ])
    ck("closure seal", sha(run / "closure.json") == CLOSURE_SHA)
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("native run identity", inv["case_id"] == "E10" and inv["variant_id"] == "E10.var05" and inv["case_version"] == "1.0.0-candidate" and inv["run_id"] == closure["run_id"] == RUN_ID)
    ck("guarded SSH GUI and queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    ck("frozen local source pins", all(pins[key] == sha(HERE / name) for key, name in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
    ck("parent source pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("native executable and documentation pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("five guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        ck(f"raw {name}", (run / name).stat().st_size == meta["bytes"] > 4 and sha(run / name) == meta["sha256"])
    ck("source copy and roundtrip", sha(run / "input.json") == contract["native_input_sha256"] and read(run / "roundtrip-validation.json")["passed"] is True and populated(parse_native(run / "input.json")) == {n: populated(parse_native(run / "roundtrip-raw.json"))[n] for n in populated(parse_native(run / "input.json"))})
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion warnings", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}) and "(note #" not in conversion.lower())
    ck("nonempty native output", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
    report = {t["name"]: t for t in parse_native(run / "report-raw.json")["report"]["tables"]}
    old_report = {t["name"]: t for t in parse_native(parent_run / "report-raw.json")["report"]["tables"]}
    ck("report tables", set(report) == set(old_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        ck(f"{name} exact accepted-parent report equality", report[name] == old_report[name])
    system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck("72 aligned half-hour bins", len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
    ck("one fault, repair and demand", sum(r["NFAIL"] or 0 for r in system) == sum(r["NREPT"] or 0 for r in system) == sum(r["NDF"] or 0 for r in stock) == 1)
    ck("three-hour backorder and terminal", abs(sum(r["NBO"] or 0 for r in stock) / 2 - 3) < 1e-6 and stock[-1]["NBO"] == 0 and system[-1]["NSYRY"] == 1)
    ck("three missions", abs(rows(report["ResultSummary"])[0]["MSUF"] - 2 / 3) < 1e-5)
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("complete event log equals accepted flat comparator", (run / "model.log").read_bytes() == (parent_run / "model.log").read_bytes())
    ck("exact expanded points h8 and h11", log.count("scheduled transport task 0 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 8") == 1 and log.count("scheduled transport task 1 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11") == 1)
    ck("empty h8 departure explicitly cancelled", "Time: 8  scheduled transport task 0 cancelled with 0 items/systems" in log and log.count("cancelled with 0 items/systems") == 1)
    ck("no h8 physical shipment", "Time: 8  scheduled transport task 0 starts with" not in log and "Time: 8  transport request" not in log and "Time: 8 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives" not in log)
    ck("fault and demand after empty point", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in log and "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives" in log)
    ck("demand attaches h11 schedule", "Time: 8  scheduled transport task 1 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11" in log and "Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1" in log)
    ck("downward physical spare at h11 and h13", "Time: 11  scheduled transport task 1 starts with 1 items/systems, transport time: 2" in log and "Time: 13 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in log and "Time: 13 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 3" in log)
    ck("upward faulty item and depot repair", "Time: 10.1667  transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached" in log and "Time: 12.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>" in log and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log)
    ck("aircraft ready and later missions", "Time: 13.3333 <TEACH-AIR-01,BASE-01,0> System ready" in log and "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in log and "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:" in log)
    ck("one complete physical item cycle", log.count("critical random failure added") == 1 and log.count("Item demand arrives from pos <TEACH-AIR-01") == 1 and log.count("Backorder added") == 1 and log.count("Backorder removed") == 1 and log.count("Take replacement item") == 1 and log.count("Put back replacement item") == 1)
    ck("two transports and no open shipment", log.count("starts with 1 items/systems, transport time: 2") == log.count("arrives with 1 items/systems") == 2)
    ck("no resource demand", "requests resources: no resources needed" in log and "allocated to maintenance task" not in log)
    result = {"schema": "simlox-e10-var05-nested-repeat-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_native_cli_replay", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
