"""Replay fixed-seed G06 ONLM=N against accepted ONLM=Y raw evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G05-unavailable-standby-v1.0.3"
RUNS = {"Y": PARENT / "runs/g05-unavailable-v103-ssh-20261002-01",
        "N": HERE / "runs/g06-deferred-v100-ssh-20261002-01"}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(value: object, expected: float, tolerance: float = 1e-4) -> bool:
    return isinstance(value, (int, float)) and math.isclose(
        float(value), expected, rel_tol=0, abs_tol=tolerance)


def rows(report: dict, name: str) -> list[dict]:
    found = [table for table in report["report"]["tables"] if table["name"] == name]
    assert len(found) == 1
    columns = [column["name"] for column in found[0]["columns"]]
    return [dict(zip(columns, row)) for instance in found[0]["instances"]
            for row in instance["rows"]]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, condition: bool) -> None:
        if name in checks:
            raise ValueError(name)
        checks[name] = bool(condition)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent_source, child_source = PARENT / "unavailable-input.json", HERE / "deferred-input.json"
    ck("frozen_source_hashes", sha(parent_source) == contract["parent"]["sha256"] and
       sha(child_source) == contract["child_sha256"] and
       sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and
       diff["parent_sha256"] == sha(parent_source) and
       diff["source_sha256"] == sha(child_source))
    ck("exact_two_table_delta", set(diff["parent_to_deferred"]) ==
       {"ProblemDescription", "RBDParallel"})
    source_rows = {}
    for arm, path in (("Y", parent_source), ("N", child_source)):
        document = native_json(path)
        source_rows[arm] = authored_tables(document)
        ck(f"{arm}.row_tables", len(source_rows[arm]) == 23)
    ck("source_only_description_and_onlm", all(
       source_rows["Y"][name] == source_rows["N"][name]
       for name in source_rows["Y"] if name not in {"ProblemDescription", "RBDParallel"}) and
       source_rows["Y"]["RBDParallel"][0] == source_rows["N"]["RBDParallel"][0])

    results = {}
    for arm, run in RUNS.items():
        package = PARENT if arm == "Y" else HERE
        source = parent_source if arm == "Y" else child_source
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm}.source_and_invocation", sha(run / "input.json") == sha(source) and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] and
           closure["source_hashes_before"]["input"] == sha(source) and
           closure["error"] is None)
        ck(f"{arm}.guarded_session", invocation["session_id"] == 0 and
           invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm}.five_steps", [step["name"] for step in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(step["status"] == "completed" and step["exit_code"] == 0 and
               step["gui_preserved"] for step in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and
           sha(run / name) == seal["sha256"] for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        after = authored_tables(native_json(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           all(after.get(name) == value for name, value in source_rows[arm].items()))
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0" in
           (run / "run.log").read_text(encoding="utf-8-sig", errors="replace") and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        switches = [(float(t), old, new, float(end)) for t, old, new, end in re.findall(
            r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. "
            r"switch over started\. Will be finished at ([\d.]+)\.", log)]
        failures = [(float(t), severity) for t, severity in re.findall(
            r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now", log)]
        repairs = {mode: (float(t), int(task)) for t, task, mode in re.findall(
            r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)}
        repair_ends = [(float(t), int(task)) for t, task in re.findall(
            r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
        ck(f"{arm}.faults_and_switches", failures == [(8.94145, "noncritical"),
                                                       (17.5636, "noncritical")] and
           switches == [(8.94145, "POS-B", "POS-A", 9.44145),
                        (17.5636, "POS-A", "POS-C", 18.0636)])
        ck(f"{arm}.mission", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log and
           "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and
           " mission aborted:" not in log)
        expected_starts = ((8.94145, 17.5636) if arm == "Y" else (34.0, 34.0))
        ck(f"{arm}.repair_starts", len(repairs) == 2 and
           near(repairs["FM-POS-B"][0], expected_starts[0]) and
           near(repairs["FM-POS-A"][0], expected_starts[1]) and
           "starts performing, planned to last for 40 hours" in log and
           "starts performing, planned to last for 0.5 hours" in log)
        expected_A_end = 18.0636 if arm == "Y" else 34.5
        ck(f"{arm}.A_done_B_open", repair_ends == [(expected_A_end, repairs["FM-POS-A"][1])] and
           "system CM task 0 on <TEACH-AIR-01,0> completed" not in log)
        report = native_json(run / "report-raw.json")
        system, stock, summary = (rows(report, name) for name in
                                  ("SystemResults", "StockTotalResults", "ResultSummary"))
        ck(f"{arm}.aligned_bins", len(system) == len(stock) == 72 and all(
           near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
           near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
           for i in range(72)))
        ck(f"{arm}.system_exposure", near(.5 * sum(row["NSYSW"] or 0 for row in system), 1) and
           near(.5 * sum(row["NSYMO"] or 0 for row in system), 25) and
           sum(row["NFAIL"] or 0 for row in system) == 2 and
           sum(row["NREPT"] or 0 for row in system) == 1 and
           [row["STINT"] for row in system if row["NREPT"]] ==
           ([18.0] if arm == "Y" else [34.5]))
        ck(f"{arm}.terminal_and_stock", near(system[-1]["NSYRY"], 0) and
           near(system[-1]["NSYUA"], 1) and near(system[-1]["NSYRP"], 1) and
           all(near(row[key] or 0, 0) for row in stock
               for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
        ck(f"{arm}.continuous_summary", len(summary) == 1 and
           summary[0]["NREP"] == 1 and near(summary[0]["MTMF"], 1) and
           near(summary[0]["STMF"], 25 / 26) and
           near(summary[0]["MSTF"], 0) and near(summary[0]["MSUF"], 0))
        results[arm] = {"run_id": run.name, "input_sha256": sha(run / "input.json"),
                        "closure_sha256": sha(run / "closure.json"),
                        "model_log_sha256": sha(run / "model.log"),
                        "report_sha256": sha(run / "report-raw.json"),
                        "faults": failures, "switches": switches,
                        "repair_starts": repairs, "repair_ends": repair_ends,
                        "NREPT_bin_start": [row["STINT"] for row in system if row["NREPT"]]}
    ck("paired_repair_timing", near(results["Y"]["repair_starts"]["FM-POS-B"][0], 8.94145) and
       near(results["N"]["repair_starts"]["FM-POS-B"][0], 34) and
       near(results["Y"]["repair_starts"]["FM-POS-A"][0], 17.5636) and
       near(results["N"]["repair_starts"]["FM-POS-A"][0], 34) and
       results["Y"]["NREPT_bin_start"] == [18.0] and
       results["N"]["NREPT_bin_start"] == [34.5])
    result = {"schema": "simlox-g06-online-direct-cm-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": results, "raw_seals": 24,
              "scope": "one_fixed_seed_continuous_direct_CM_ONLM_Y_versus_N_pair",
              "publication_state": "not_published"}
    output = HERE / "author-validation.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen author validation differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "sha256": sha(output)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
