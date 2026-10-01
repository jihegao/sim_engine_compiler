"""Replay the frozen G05 passive-standby native pair and its raw evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import SOURCES, authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"g05-passive-{arm}-v100-ssh-20261002-01" for arm in SOURCES}
PARENT = ROOT / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
SUPPORT = ROOT / "G04-series-active-parallel-v1.0.1" / "parallel-input.json"
PARENT_SHA = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
SUPPORT_SHA = "ea56a9daf8705189c9162529355b28636ef7db168987b17ee90cdedbe9bb4b6f"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
FAILURE_TIMES = {"zero": [8.94145, 17.0636], "half": [8.94145, 17.5636]}
SWITCH_ENDS = {"zero": [8.94145, 17.0636], "half": [9.44145, 18.0636]}
PATHS = [("POS-B", "POS-A", "FM-POS-B"), ("POS-A", "POS-C", "FM-POS-A")]


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
    check(arm, "priority_transition_paths", len(switches) == len(stops) == 2 and all(
          (switches[i][1], switches[i][2]) == (stops[i][1], stops[i][2]) == PATHS[i][:2]
          for i in range(2)))
    check(arm, "switchover_timing", len(switches) == len(stops) == 2 and all(
          near(switches[i][0], FAILURE_TIMES[arm][i], 1e-5) and
          near(switches[i][3], SWITCH_ENDS[arm][i], 1e-5) and
          near(stops[i][0], SWITCH_ENDS[arm][i], 1e-5) and
          near(switches[i][3] - switches[i][0], 0 if arm == "zero" else 0.5, 1e-5)
          for i in range(2)))
    failure_events = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", match.group(3))
        failure_events.append((float(match.group(1)), match.group(2), modes))
    check(arm, "two_operated_failures", len(failure_events) == 2 and all(
          near(event[0], FAILURE_TIMES[arm][i], 1e-5) and event[1] == "noncritical" and
          event[2][-1] == (PATHS[i][2], PATHS[i][0]) and len(event[2]) == i + 1
          for i, event in enumerate(failure_events)) and log.count("CM failure mode added") == 2)
    check(arm, "no_passive_failure_before_activation", len(failure_events) == 2 and len(switches) == 2 and
          failure_events[0][2][-1][1] == switches[0][1] and
          failure_events[1][0] > stops[0][0] and failure_events[1][2][-1][1] == switches[1][1])
    check(arm, "mission_success", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log and
          "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and
          log.count(" mission success:") >= 1 and " mission aborted:" not in log)
    starts = [(float(t), int(i), mode) for t, i, mode in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    check(arm, "postmission_parallel_cm", len(starts) == len(ends) == 2 and
          all(near(t, 34) and i == n and mode == PATHS[n][2] for n, (t, i, mode) in enumerate(starts)) and
          all(near(t, 34.5) and i == n for n, (t, i) in enumerate(ends)))

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
    check(arm, "switch_and_operating_exposure", near(switches_reported, 0 if arm == "zero" else 1) and
          near(operating, 26 if arm == "zero" else 25) and
          near(operating + switches_reported, 26))
    check(arm, "failure_repair_ledger", near(sum(row["NFAIL"] for row in system), 2) and
          near(sum(row["NREPT"] for row in system), 2) and
          near(sum(row["SYDT"] or 0 for row in system), 0.5) and
          near(0.5 * sum(row["NSYRP"] or 0 for row in system), 0.5))
    check(arm, "event_report_bins", [row["STINT"] for row in system if row["NFAIL"]] ==
          ([8.5, 17] if arm == "zero" else [8.5, 17.5]) and
          [row["STINT"] for row in system if row["NREPT"]] == [34.5])
    check(arm, "stock_zero", all(near(row[key] or 0, 0) for row in stock
          for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    check(arm, "terminal_ready", near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYRP"], 0) and
          near(system[-1]["NSYMO"], 0))
    check(arm, "summary_success", len(summary) == 1 and summary[0]["NREP"] == 1 and
          near(summary[0]["RTIUP"], 36) and near(summary[0]["MSUF"], 1))
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
    check("pair", "same_first_operated_sample", near(data["zero"]["failure_events"][0][0],
                                                  data["half"]["failure_events"][0][0], 1e-5))
    check("pair", "second_failure_shifted_by_switch", near(
        data["half"]["failure_events"][1][0] - data["zero"]["failure_events"][1][0], 0.5, 1e-5))
    check("pair", "switch_vs_operation", near(data["half"]["switch_hours"] - data["zero"]["switch_hours"], 1) and
          near(data["zero"]["operating_hours"] - data["half"]["operating_hours"], 1))
    result = {"schema": "simlox-g05-passive-switchover-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [key for key, passed in checks.items() if not passed],
              "run_ids": {arm: path.name for arm, path in RUNS.items()}, "raw_seals": 24,
              "arms": data, "scope": "fixed_seed_passive_priority_and_zero_vs_half_hour_switch",
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
