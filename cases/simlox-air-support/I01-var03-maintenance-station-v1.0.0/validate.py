"""Replay the bounded I01.var03 maintenance-station native comparison."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var01-two-stock-points-v1.0.0/stocked-input.json"
DONOR = HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json"
RUNS = {arm: HERE / "runs" / f"i01-var03-station-{arm}-v100-ssh-20261002-01"
        for arm in ("base", "depot")}
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


def near(value: object, target: float, tol: float = 1e-3) -> bool:
    return isinstance(value, (float, int)) and math.isclose(float(value), target, abs_tol=tol, rel_tol=0)


def table_rows(doc: dict, name: str) -> list[list]:
    table, = [t for t in doc["model"]["tables"] if t["name"] == name]
    return [row for instance in table["instances"] for row in instance["rows"]]


def report_rows(doc: dict, name: str) -> list[dict]:
    table, = [t for t in doc["report"]["tables"] if t["name"] == name]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    checks: dict[str, bool] = {}
    def ck(name: str, passed: bool) -> None:
        assert name not in checks, name
        checks[name] = bool(passed)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    source = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    docs = {arm: parse_native(path) for arm, path in source.items()}
    ck("source_lineage", sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       sha(DONOR) == contract["structural_donor"]["sha256"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       all(sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, path in source.items()))
    ck("controlled_delta", set(diff["parent_to_base"]["added_tables"]) ==
       {"TaskCategory", "TaskLevel", "MaintenanceAllocation"} and
       set(diff["parent_to_base"]["changed_tables"]) ==
       {"ProblemDescription", "Station", "StationStructure", "ItemRepair", "Tasks", "StockAllocation"} and
       not diff["parent_to_base"]["removed_tables"] and
       set(diff["base_to_depot"]["changed_tables"]) == {"Control", "ProblemDescription"} and
       not diff["base_to_depot"]["added_tables"] and not diff["base_to_depot"]["removed_tables"])
    ck("model_keys", all(len(populated(doc)) == 24 and table_rows(doc, "ItemReorder") == [] and
       table_rows(doc, "ResourceAllocation") == [] and
       table_rows(doc, "StockAllocation") == [
           [point, "TEACH-LRU-01", station, size, None, None, None, None, None]
           for point in ("AIR_BASIC", "AIR_DEPOT")
           for station, size in (("BASE-01", 1), ("DEPOT-01", 0))] and
       table_rows(doc, "MaintenanceAllocation") == [
           ["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
           ["AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01", None]] and
       [(r[0], r[1], r[2], r[11]) for r in table_rows(doc, "ItemRepair")] == [
           ("TEACH-LRU-01", "BASE-01", 1, "I01-LRU-DIRP"),
           ("TEACH-LRU-01", "DEPOT-01", 1, "I01-LRU-DIRP")]
       for doc in docs.values()) and
       table_rows(docs["base"], "Control")[0][3] == "AIR_BASIC" and
       table_rows(docs["depot"], "Control")[0][3] == "AIR_DEPOT")
    ck("installed_sources", all(sha(path) == contract["installed_source_sha256"][
       {"manual": "manual_pdf", "dictionary": "table_dictionary", "simlox_exe": "simlox_exe"}[key]]
       for key, path in INSTALL.items()))

    ledger: dict[str, dict] = {}
    for arm, run in RUNS.items():
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        h = closure["source_hashes_before"]
        ck(f"{arm}.closure", closure["error"] is None and h == closure["source_hashes_after"] and
           invocation["variant"] == arm and invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           h["input"] == sha(source[arm]) == sha(run / "input.json") and
           h["parent"] == sha(PARENT) and h["structural_donor"] == sha(DONOR) and
           h["contract"] == sha(HERE / "contract.json") and
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
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == 24 and
           all(exported.get(name) == value for name, value in populated(docs[arm]).items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 1" in converter and
           "warning #108" in converter and "notice #2034" in converter and
           "error #" not in converter and "warning #241" not in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ck(f"{arm}.shared_events", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log and
           "subitem failed: <TEACH-LRU-01,0,1>" in log and
           "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log and
           "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in log and
           log.count("mission aborted:") == 1 and log.count("mission success:") == 2 and
           log.count("Put back replacement item <TEACH-LRU-01,0,1> to stock") == 1)
        if arm == "base":
            ck("base.local_repair", "Time: 10.1667 <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,1>" in log and
               "Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,1>" in log and
               "Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log and
               "transport task" not in log.lower() and "Backorder added" not in log)
        else:
            ck("depot.route_repair_return", "Time: 10.1667  transport task 0 starts with 1 items/systems, transport time: 2" in log and
               "Time: 12.1667  transport task 0 arrives with 1 items/systems" in log and
               "Time: 12.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>" in log and
               "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>" in log and
               "Time: 13.1667  transport task 2 starts with 1 items/systems, transport time: 2" in log and
               "Time: 15.1667  transport task 2 arrives with 1 items/systems" in log and
               "Time: 15.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log and
               "Time: 10.1667 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added" in log and
               "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed" in log)
        ck(f"{arm}.stock_terminal", "Level: 1 Items:<TEACH-LRU-01,0,1>" in log and
           "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in log)
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (report_rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.report_values", sum(r["NFAIL"] or 0 for r in system) == 1 and
           sum(r["NREPT"] or 0 for r in system) == 1 and
           near(system[-1]["NSYRY"], 1) and near(summary[0]["MSUF"], 2 / 3) and
           all(near(r["NSYWI"], 0) and near(r["NSYLA"], 0) for r in system) and
           all(near(r["NBO"], 0) for r in stock))
        ledger[arm] = {"summary": summary, "system": system, "stock": stock,
                       "closure_sha256": sha(run / "closure.json"),
                       "model_log_sha256": sha(run / "model.log"),
                       "report_sha256": sha(run / "report-raw.json")}
    ck("aggregate_reports_equal", all(ledger["base"][key] == ledger["depot"][key]
       for key in ("summary", "system", "stock")))
    result = {"schema": "simlox-i01-var03-maintenance-station-v100-author/v1",
              "verdict": "GO for bounded APID station selection and physical routing only; positive category/level filtering and combined allocation selection unverified",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [key for key, value in checks.items() if not value],
              "runs": {arm: {key: value for key, value in data.items()
                             if key.endswith("sha256")} for arm, data in ledger.items()},
              "raw_seals": 24, "publication_state": "bounded_native_case"}
    out = HERE / "author-validation.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if out.exists() and out.read_bytes() != raw:
        raise ValueError("frozen validation differs")
    if not out.exists():
        out.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "sha256": sha(out)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
