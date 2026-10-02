"""Replay the predeclared I01.var07 selected-category converter rejection."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var01-two-stock-points-v1.0.0/stocked-input.json"
RUNS = {arm: HERE / "runs" / f"i01-var07-{arm}-v100-ssh-20261002-01"
        for arm in ("matching", "other")}
COMMON_RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
              "import.log", "export.log", "run.log", "roundtrip-validation.json", "steps.json"}
MATCHING_EXTRA = {"report-raw.json", "model.log", "report-export.log"}
INSTALL = {"manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str) -> list[list]:
    item, = [t for t in doc["model"]["tables"] if t["name"] == name]
    return [row for inst in item["instances"] for row in inst["rows"]]


def report_rows(report: dict, name: str) -> list[dict]:
    item, = [t for t in report["report"]["tables"] if t["name"] == name]
    names = [c["name"] for c in item["columns"]]
    return [dict(zip(names, row)) for inst in item["instances"] for row in inst["rows"]]


def near(value: object, target: float, atol: float = 1e-3) -> bool:
    return isinstance(value, (int, float)) and math.isclose(float(value), target, rel_tol=0, abs_tol=atol)


def main() -> None:
    checks: dict[str, bool] = {}
    def ck(name: str, value: bool) -> None:
        assert name not in checks
        checks[name] = bool(value)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("source_fingerprints", sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       all(sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, path in sources.items()))
    ck("bounded_source_delta", set(diff["parent_to_matching"]["added_tables"]) ==
       {"TaskCategory", "TaskLevel", "MaintenanceAllocation"} and
       set(diff["matching_to_other"]["changed_tables"]) == {"Control", "ProblemDescription"} and
       not diff["matching_to_other"]["added_tables"] and
       not diff["matching_to_other"]["removed_tables"])
    docs = {arm: parse_native(path) for arm, path in sources.items()}
    ck("selected_missing_category", all(len(populated(doc)) == 23 and
       rows(doc, "ItemRepair")[0][11] == "I01-LRU-DIRP" and
       rows(doc, "StockAllocation")[0][3] == rows(doc, "StockAllocation")[1][3] == 1 and
       rows(doc, "MaintenanceAllocation") == [
           ["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
           ["AIR_ALT", "ALT-CM", "BASE", "BASE-01", None]]
       for doc in docs.values()) and
       rows(docs["matching"], "Control")[0][3] == "AIR_BASIC" and
       rows(docs["other"], "Control")[0][3] == "AIR_ALT")
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
        expected_steps = (["import", "export", "calc", "jsonreport", "check_import_export"]
                          if arm == "matching" else ["import", "export", "calc", "check_import_export"])
        ck(f"{arm}.guard", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
           [step["name"] for step in steps] == expected_steps and
           all(step["status"] == ("calc_observed" if step["name"] == "calc" else "completed") and
               step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
        expected_raw = COMMON_RAW | (MATCHING_EXTRA if arm == "matching" else set())
        ck(f"{arm}.raw_seals", set(closure["raw"]) == expected_raw and all(
           (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
           for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == 23 and
           all(exported.get(name) == value for name, value in populated(docs[arm]).items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        if arm == "matching":
            ck("matching.valid_conversion", closure["expected_outcome"] == "valid_matching_control" and
               "Input conversion completed. Errors: 0, Warnings: 1, Notes: 1" in converter and
               "notice #2034" in converter and "error #2038" not in converter and
               (run / "model.sxo").stat().st_size > 4 and
               (run / "report-raw.json").stat().st_size > 4)
            log = (run / "model.log").read_text(encoding="utf-8-sig")
            ck("matching.positive_control_events", "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log and
               "Time: 10.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> started" in log and
               "Time: 11.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> completed" in log and
               "Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item" in log and
               log.count("mission success:") == 2 and log.count("mission aborted:") == 1)
            report = parse_native(run / "report-raw.json")
            system, stock = (report_rows(report, name) for name in
                             ("SystemResults", "StockTotalResults"))
            ck("matching.report", len(system) == len(stock) == 72 and
               all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
                   near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
                   for i in range(72)) and
               sum(row["NFAIL"] or 0 for row in system) == 1 and
               near(system[-1]["NSYRY"], 1))
        else:
            ck("other.expected_rejection", closure["expected_outcome"] == "error_2038_no_valid_output" and
               "Form: TaskCategory" in converter and
               "rec 1: (error #2038) No maintenance allocation defined for task category: LRU-CM" in converter and
               "Input conversion completed. Errors: 1, Warnings: 1, Notes: 1" in converter and
               "notice #2034" in converter and
               (run / "model.sxo").stat().st_size == 4 and
               not (run / "report-raw.json").exists() and not (run / "model.log").exists())

    result = {"schema": "simlox-i01-var07-missing-allocation-v100-author-negative/v1",
              "verdict": "GO for predeclared selected-category #2038 converter rejection; no AIR_ALT simulation claim",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "raw_seals": 21, "publication_state": "bounded_negative_converter_case"}
    out = HERE / "author-negative-validation.json"
    data = (json.dumps(result, indent=2) + "\n").encode()
    if out.exists() and out.read_bytes() != data:
        raise ValueError("frozen negative validation differs")
    if not out.exists():
        out.write_bytes(data)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "sha256": sha(out)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
