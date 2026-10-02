"""Replay the bounded I01 resource POINT/APID native comparison."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C01-personnel-capacity-v1.0.2/inputs/capacity-2.json"
RUNS = {arm: HERE / "runs" / f"i01-var01-resource-{arm}-v100-ssh-20261002-01"
        for arm in ("selected", "zero")}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
INSTALL = {"manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(actual: object, target: float, atol: float = 1e-4) -> bool:
    return isinstance(actual, (float, int)) and math.isclose(float(actual), target, rel_tol=0, abs_tol=atol)


def rows(report: dict, name: str) -> list[dict]:
    table, = [t for t in report["report"]["tables"] if t["name"] == name]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    checks: dict[str, bool] = {}
    def ck(name: str, passed: bool) -> None:
        assert name not in checks
        checks[name] = bool(passed)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("source_fingerprints", sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       all(sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, path in sources.items()))
    ck("bounded_delta", set(diff["parent_to_selected"]["changed_tables"]) ==
       {"ResourceAllocation", "ProblemDescription"} and
       set(diff["selected_to_zero"]["changed_tables"]) == {"Control", "ProblemDescription"} and
       diff["selected_to_zero"]["changed_tables"]["Control"]["before"]["instances"][0]["rows"][0][3] == "AIR_BASIC" and
       diff["selected_to_zero"]["changed_tables"]["Control"]["after"]["instances"][0]["rows"][0][3] == "AIR_ZERO")
    docs = {arm: parse_native(path) for arm, path in sources.items()}
    def table(doc: dict, name: str) -> list[list]:
        item, = [t for t in doc["model"]["tables"] if t["name"] == name]
        return [r for inst in item["instances"] for r in inst["rows"]]
    ck("model_keys", all(len(populated(doc)) == 20 and
       table(doc, "ResourceAllocation") == [
           ["AIR_BASIC", "P-CREW", "BASE-01", 2, None],
           ["AIR_BASIC", "P-OTHER", "BASE-01", 0, None],
           ["AIR_ZERO", "P-CREW", "BASE-01", 0, None],
           ["AIR_ZERO", "P-OTHER", "BASE-01", 0, None]] and
       table(doc, "SubTaskResource") == [
           ["PREP-FIXED", 1, "P-CREW", 2, 1, None, None, None, None]] and
       table(doc, "StockAllocation") == [] and
       not any(t["name"] == "MaintenanceAllocation" for t in doc["model"]["tables"])
       for doc in docs.values()))
    ck("installed_sources", all(sha(path) == contract["installed_source_sha256"][
       {"manual": "manual_pdf", "dictionary": "table_dictionary", "simlox_exe": "simlox_exe"}[key]]
       for key, path in INSTALL.items()))

    for arm, run in RUNS.items():
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        h = closure["source_hashes_before"]
        ck(f"{arm}.closure", invocation["variant"] == arm and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["error"] is None and h == closure["source_hashes_after"] and
           h["input"] == sha(sources[arm]) == sha(run / "input.json") and
           h["parent"] == sha(PARENT) and h["contract"] == sha(HERE / "contract.json") and
           h["builder"] == sha(HERE / "build.py") and
           h["exact_diff"] == sha(HERE / "exact-diff.json") and
           h["diff_checker"] == sha(HERE / "describe_diff.py") and
           h["checker"] == sha(HERE / "check_roundtrip.py") and
           h["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
           all(h[key] == sha(path) for key, path in INSTALL.items()))
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
           all(exported.get(name) == value for name, value in populated(docs[arm]).items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter and
           "warning #108" in converter and "warning #126" in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        common = ["Time: 7 <TEACH-AIR-01,0> preparation started",
                  "Time: 7  subtask 0 seqno 1 within system preparation task 0",
                  "request for: 2"]
        ck(f"{arm}.common_events", all(x in log for x in common) and
           log.count("mission created:") == 1 and
           "Time: 0 <TEACH-AIR-01,0> nbr ready increased" in log)
        if arm == "selected":
            phrases = ["request for: 2 OK", "allocated to maintenance task: 2  available now: 0",
                       "starts performing, planned to last for 0.166667 hours",
                       "Time: 7.16667  <P-CREW at <BASE-01,0>> deallocated",
                       "Time: 7.5 <TEACH-AIR-01,0> preparation ended",
                       "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting",
                       "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success"]
            ck("selected.event_order", all(x in log for x in phrases) and
               [log.index(x) for x in phrases] == sorted(log.index(x) for x in phrases) and
               "mission cancelled:" not in log)
        else:
            ck("zero.blocked_events", "request for: 2 failed" in log and
               "Time: 7.58333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled" in log and
               "resource waiting stopped" in log and
               "allocated to maintenance task: 2" not in log and
               "starts performing, planned to last for 0.166667 hours" not in log and
               "mission starting" not in log and "mission success:" not in log)
        report = parse_native(run / "report-raw.json")
        summary, system, resource, stock = (rows(report, name) for name in
            ("ResultSummary", "SystemResults", "ResourceResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and
           len(system) == len(resource) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(resource[i]["STINT"], i * .5) and near(resource[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        if arm == "selected":
            ck("selected.report_values", near(resource[14]["NR"], 2) and
               near(resource[14]["NRUM"], 2 / 3) and near(resource[14]["NRW"], 0) and
               near(system[14]["NPSTA"], 1) and near(system[15]["NPSUC"], 1) and
               all(near(system[i]["FTMO"], 1) for i in range(16, 20)) and
               near(summary[0]["MSUF"], 1) and near(system[-1]["NSYRY"], 1))
        else:
            ck("zero.report_values", near(resource[14]["NR"], 0) and
               near(resource[14]["NRUM"], 0) and near(resource[14]["NRW"], 2) and
               near(resource[15]["NRW"], 1 / 3) and near(system[14]["NPSTA"], 1) and
               all(near(row["NPSUC"], 0) and near(row["FTMO"], 0) for row in system) and
               near(summary[0]["MSUF"], 0) and near(system[-1]["NSYRY"], 1))
        ck(f"{arm}.no_stock", all(near(row["NBO"], 0) for row in stock))

    result = {"schema": "simlox-i01-var01-resource-points-v100-author/v1",
              "verdict": "GO only for ResourceAllocation POINT/APID selection on C01 preparation demand",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "raw_seals": 24, "publication_state": "bounded_native_case"}
    out = HERE / "author-validation.json"
    data = (json.dumps(result, indent=2) + "\n").encode()
    if out.exists() and out.read_bytes() != data:
        raise ValueError("frozen validation differs")
    if not out.exists():
        out.write_bytes(data)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "sha256": sha(out)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
