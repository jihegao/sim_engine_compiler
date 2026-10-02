"""Replay the bounded I01.var04 no-task-reference ItemRepair comparison."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var05-none-maintenance-v1.0.0/none-input.json"
RUNS = {arm: HERE / "runs" / f"i01-var04-{arm}-v100-ssh-20261002-01"
        for arm in ("referenced", "unreferenced")}
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


def near(actual: object, target: float, atol: float = 1e-3) -> bool:
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
    ck("source_fingerprints", sha(PARENT) == contract["direct_source_parent"]["sha256"] == diff["referenced_sha256"] and
       all(sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, path in sources.items()))
    ck("bounded_delta", sha(PARENT) == sha(sources["referenced"]) and
       set(diff["changed_tables"]) == {"ItemRepair", "ProblemDescription"} and
       diff["unchanged_table_count"] == 32 and
       diff["changed_tables"]["ItemRepair"]["before"]["instances"][0]["rows"][0][11] == "I01-LRU-DIRP" and
       diff["changed_tables"]["ItemRepair"]["after"]["instances"][0]["rows"][0][11] is None)
    docs = {arm: parse_native(path) for arm, path in sources.items()}
    def table(doc: dict, name: str) -> list[list]:
        item, = [t for t in doc["model"]["tables"] if t["name"] == name]
        return [r for inst in item["instances"] for r in inst["rows"]]
    ck("model_keys", all(len(populated(doc)) == 23 and table(doc, "ItemReorder") == [] and
       table(doc, "StockAllocation")[0][3] == table(doc, "StockAllocation")[1][3] == 1
       for doc in docs.values()) and
       table(docs["referenced"], "MaintenanceAllocation") ==
       [["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
        ["AIR_NONE", "LRU-CM", "BASE", "<NONE>", None]] and
       all(table(doc, "Control")[0][3] == "AIR_NONE" for doc in docs.values()))
    ck("installed_sources", all(sha(path) == contract["installed_source_sha256"][
       {"manual": "manual_pdf", "dictionary": "table_dictionary", "simlox_exe": "simlox_exe"}[key]]
       for key, path in INSTALL.items()))

    ledger = {}
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
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == 23 and
           all(exported.get(name) == value for name, value in populated(docs[arm]).items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", f"Input conversion completed. Errors: 0, Warnings: 1, Notes: {1 if arm == 'referenced' else 0}" in converter and
           "warning #108" in converter and ("notice #2034" in converter) == (arm == "referenced") and
           (run / "model.sxo").stat().st_size > 4 and
           ("warning #241" in converter) == (arm == "referenced"))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        ck(f"{arm}.shared_events", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log and
           "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item" in log and
           "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in log and
           log.count("mission success:") == 2 and log.count("mission aborted:") == 1 and
           "Backorder added" not in log)
        if arm == "unreferenced":
            ck("unreferenced.item_repair", "Time: 10.1667  item DIRP task 1" in log and
               "Time: 11.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> completed" in log and
               "Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item" in log and
               "Level: 1 Items:<TEACH-LRU-01,0,1>" in log)
        else:
            ck("referenced.incomplete_item", "Time: 10.1667 <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives" in log and
               "item DIRP task" not in log and "Put back replacement item" not in log and
               "Level: 0 Items:" in log and "reorder" not in log.lower())
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.report_values", sum(r["NFAIL"] or 0 for r in system) == 1 and
           sum(r["NREPT"] or 0 for r in system) == 1 and
           near(.5 * sum(r["NSYRP"] or 0 for r in system), .5) and
           all(near(r["NSYWI"], 0) and near(r["NSYLA"], 0) for r in system) and
           all(near(r["NBO"], 0) for r in stock) and
           near(system[-1]["NSYRY"], 1) and
           near(summary[0]["MSUF"], 2 / 3))
        ledger[arm] = {"summary": summary, "system": system, "stock": stock,
                       "closure_sha256": sha(run / "closure.json"),
                       "model_log_sha256": sha(run / "model.log"),
                       "report_sha256": sha(run / "report-raw.json")}
    ck("aggregate_reports_equal", all(ledger["referenced"][key] == ledger["unreferenced"][key]
       for key in ("summary", "system", "stock")))
    result = {"schema": "simlox-i01-var04-unreferenced-item-repair-v100-author/v1",
              "verdict": "GO for bounded no-task-reference ItemRepair activation under AIR_NONE; general allocation, reorder and item conservation unverified",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [k for k, value in checks.items() if not value],
              "runs": {k: {key: value for key, value in data.items()
                              if key.endswith("sha256")} for k, data in ledger.items()},
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
