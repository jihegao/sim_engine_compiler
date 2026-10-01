"""Replay the frozen G05 passive NBREQ threshold pair and raw evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import SOURCES, authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"g05-nbreq-{arm}-v100-ssh-20261002-01" for arm in SOURCES}
PARENT = ROOT / "G05-passive-switchover-v1.0.0" / "half-input.json"
SUPPORT = ROOT / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
PARENT_SHA = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
SUPPORT_SHA = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
FAILURE_TIMES = [8.62763, 11.5942]
SWITCH_START, SWITCH_END = 8.62763, 9.12763
FAILURE_MODES = [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(a: object, b: float, tol: float = 1e-4) -> bool:
    return isinstance(a, (int, float)) and math.isclose(float(a), b, rel_tol=0, abs_tol=tol)


def records(report: dict, name: str) -> list[dict]:
    found = [table for table in report["report"]["tables"] if table["name"] == name]
    assert len(found) == 1, name
    columns = [column["name"] for column in found[0]["columns"]]
    return [dict(zip(columns, row)) for instance in found[0]["instances"] for row in instance["rows"]]


def analyze(arm: str, check) -> dict:
    run = RUNS[arm]
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    files = {
        "input": HERE / f"{arm}-input.json", "parent": PARENT, "support": SUPPORT,
        "table_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    sources = invocation["source_hashes_before"]
    check(arm, "source_input", sha(files["input"]) == sha(run / "input.json") == SOURCES[arm])
    check(arm, "parent_and_support", sha(PARENT) == sources["parent"] == PARENT_SHA and
          sha(SUPPORT) == sources["support"] == SUPPORT_SHA)
    check(arm, "source_seals", set(sources) == set(files) and
          sources == closure["source_hashes_before"] == closure["source_hashes_after"] and
          all(sources[name] == sha(path) for name, path in files.items()))
    check(arm, "invocation_closure", invocation["case_id"] == "G05" and invocation["arm"] == arm and
          invocation["run_id"] == closure["run_id"] == run.name and
          sha(run / "invocation.json") == closure["invocation_sha256"] and closure["error"] is None)
    check(arm, "ssh_queue_gui", invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    check(arm, "five_native_steps", [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check(arm, "twelve_raw_seals", set(closure["raw"]) == RAW and all(
          (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
          for name, seal in closure["raw"].items()))
    roundtrip = load(run / "roundtrip-validation.json")
    before = authored_tables(native_json(run / "input.json"))
    after = authored_tables(native_json(run / "roundtrip-raw.json"))
    check(arm, "exact_roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
          roundtrip["source_sha256"] == SOURCES[arm] and len(before) == 23 and
          all(after.get(name) == value for name, value in before.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(arm, "conversion", "Input conversion completed. Errors: 0" in conversion and
          (run / "model.sxo").stat().st_size > 4)

    log = (run / "model.log").read_text(encoding="utf-8-sig")
    switches = [(float(t), old, new, float(end)) for t, old, new, end in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. "
        r"switch over started\. Will be finished at ([\d.]+)\.", log)]
    stops = [(float(t), old, new) for t, old, new in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. Switch over stopped\.", log)]
    check(arm, "single_branch_switch", len(switches) == len(stops) == 1 and
          switches[0][1:3] == ("POS-B", "POS-C") and stops[0][1:] == ("POS-B", "POS-C"))
    check(arm, "switchover_timing", len(switches) == len(stops) == 1 and
          near(switches[0][0], SWITCH_START, 1e-5) and
          near(switches[0][3], SWITCH_END, 1e-5) and
          near(stops[0][0], SWITCH_END, 1e-5) and
          near(switches[0][3] - switches[0][0], 0.5, 1e-5))
    failure_events = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", match.group(3))
        failure_events.append((float(match.group(1)), match.group(2), modes))
    check(arm, "two_operated_failures", len(failure_events) == 2 and all(
          near(event[0], FAILURE_TIMES[i], 1e-5) and
          event[1] == ("critical" if arm == "two" and i == 1 else "noncritical") and
          event[2][-1] == FAILURE_MODES[i] and len(event[2]) == i + 1
          for i, event in enumerate(failure_events)) and log.count("CM failure mode added") == 2)
    check(arm, "failed_operated_and_no_c_failure", len(failure_events) == 2 and len(switches) == 1 and
          failure_events[0][2][-1][1] == switches[0][1] and
          failure_events[1][0] > stops[0][0] and failure_events[1][2][-1][1] == "POS-A" and
          "FM-POS-C" not in log)
    check(arm, "mission_start", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log)
    if arm == "one":
        check(arm, "mission_outcome", "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and
              log.count(" mission aborted:") == 0 and log.count(" mission success:") == 1)
        repair_start, repair_end = 34.0, 34.5
    else:
        check(arm, "mission_outcome", "Time: 11.5942 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log and
              "Time: 15.1884 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log and
              log.count(" mission aborted:") == 1 and log.count(" mission success:") == 0)
        repair_start, repair_end = 15.1884, 15.6884
    starts = [(float(t), int(i), mode) for t, i, mode in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    check(arm, "postmission_parallel_cm", len(starts) == len(ends) == 2 and
          all(near(t, repair_start) and i == n and mode == FAILURE_MODES[n][0]
              for n, (t, i, mode) in enumerate(starts)) and
          all(near(t, repair_end) and i == n for n, (t, i) in enumerate(ends)))

    report = native_json(run / "report-raw.json")
    system, stock, summary = (records(report, name) for name in
                              ("SystemResults", "StockTotalResults", "ResultSummary"))
    check(arm, "report_tables", {table["name"] for table in report["report"]["tables"]} ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    check(arm, "aligned_half_hour_bins", len(system) == len(stock) == 72 and all(
          near(system[i]["STINT"], i * 0.5) and near(system[i]["ETINT"], (i + 1) * 0.5) and
          near(stock[i]["STINT"], i * 0.5) and near(stock[i]["ETINT"], (i + 1) * 0.5)
          for i in range(72)))
    switches_reported = 0.5 * sum(row["NSYSW"] or 0 for row in system)
    operating = 0.5 * sum(row["NSYMO"] or 0 for row in system)
    check(arm, "switch_and_operating_exposure", near(switches_reported, 0 if arm == "one" else 0.5) and
          near(operating, 26 if arm == "one" else 6.6883705, 2e-4) and
          (arm == "one" or near(operating + switches_reported, 15.1884 - 8, 2e-4)))
    check(arm, "failure_repair_ledger", near(sum(row["NFAIL"] for row in system), 2) and
          near(sum(row["NREPT"] for row in system), 2) and
          near(sum(row["SYDT"] or 0 for row in system), 0.5) and
          near(0.5 * sum(row["NSYRP"] or 0 for row in system), 0.5))
    check(arm, "event_report_bins", [row["STINT"] for row in system if row["NFAIL"]] == [8.5, 11.5] and
          [row["STINT"] for row in system if row["NREPT"]] ==
          ([34.5] if arm == "one" else [15.5]) and
          [row["STINT"] for row in system if row["NSYSW"]] ==
          ([] if arm == "one" else [8.5, 9.0]))
    check(arm, "stock_zero", all(near(row[key] or 0, 0) for row in stock
          for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    check(arm, "terminal_ready", near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYRP"], 0) and
          near(system[-1]["NSYMO"], 0))
    check(arm, "summary_outcome", len(summary) == 1 and summary[0]["NREP"] == 1 and
          near(summary[0]["RTIUP"], 36) and near(summary[0]["MSUF"], 1 if arm == "one" else 0))
    return {"run_id": run.name, "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
            "switches": switches, "stops": stops, "failure_events": failure_events,
            "repair_starts": starts, "repair_ends": ends,
            "mission_success_fraction": summary[0]["MSUF"],
            "switch_hours": switches_reported, "operating_hours": operating}


def main() -> None:
    checks = {}

    def check(arm: str, name: str, result: bool) -> None:
        key = f"{arm}.{name}"
        if key in checks:
            raise ValueError(key)
        checks[key] = bool(result)

    data = {arm: analyze(arm, check) for arm in SOURCES}
    check("pair", "identical_failure_events", [(x[0], x[2]) for x in data["one"]["failure_events"]] ==
          [(x[0], x[2]) for x in data["two"]["failure_events"]])
    check("pair", "identical_branch_switch", data["one"]["switches"] == data["two"]["switches"] and
          data["one"]["stops"] == data["two"]["stops"])
    check("pair", "threshold_state_and_outcome", data["one"]["mission_success_fraction"] == 1 and
          data["two"]["mission_success_fraction"] == 0 and
          near(data["one"]["switch_hours"], 0) and near(data["two"]["switch_hours"], 0.5))
    result = {"schema": "simlox-g05-passive-threshold-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [key for key, passed in checks.items() if not passed],
              "run_ids": {arm: path.name for arm, path in RUNS.items()}, "raw_seals": 24,
              "arms": data, "scope": "fixed_seed_passive_two_operated_nbreq_one_vs_two",
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
