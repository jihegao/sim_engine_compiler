"""Author replay of the G05 long-switch native probe and accepted control."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/g05-activation-long-v100-ssh-20261002-01"
PARENT_RUN = ROOT / "G05-passive-switchover-v1.0.0/runs/g05-passive-half-v100-ssh-20261002-01"
PARENT = ROOT / "G05-passive-switchover-v1.0.0/half-input.json"
SUPPORT = ROOT / "G04-three-branch-threshold-v1.0.0/one-input.json"
SOURCE_SHA = "13906f9ed1ba3e739072be50a8de93479cb8f339fa8f5ebe2f1b1a7ad20ea4a1"
PARENT_SHA = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
SUPPORT_SHA = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(value: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(value, (int, float)) and math.isclose(float(value), expected, abs_tol=tol, rel_tol=0)


def records(report: dict, name: str) -> list[dict]:
    tables = [table for table in report["report"]["tables"] if table["name"] == name]
    assert len(tables) == 1, name
    columns = [column["name"] for column in tables[0]["columns"]]
    return [dict(zip(columns, row)) for instance in tables[0]["instances"] for row in instance["rows"]]


def log_events(path: Path) -> dict:
    log = path.read_text(encoding="utf-8-sig")
    switches = [(float(t), old, new, float(end)) for t, old, new, end in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. "
        r"switch over started\. Will be finished at ([\d.]+)\.", log)]
    stops = [(float(t), old, new) for t, old, new in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. Switch over stopped\.", log)]
    failures = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", match.group(3))
        failures.append((float(match.group(1)), match.group(2), modes))
    repairs = [(float(t), int(i), fm) for t, i, fm in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    repair_ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    return {"log": log, "switches": switches, "stops": stops,
            "failures": failures, "repairs": repairs, "repair_ends": repair_ends}


def main() -> None:
    checks: dict[str, bool] = {}

    def check(name: str, value: bool) -> None:
        if name in checks:
            raise ValueError(name)
        checks[name] = bool(value)

    invocation, closure, steps = (load(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    files = {
        "input": HERE / "long-input.json", "parent": PARENT, "support": SUPPORT,
        "table_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    sources = invocation["source_hashes_before"]
    check("source_input", sha(files["input"]) == sha(RUN / "input.json") == SOURCE_SHA)
    check("parent_support", sha(PARENT) == sources["parent"] == PARENT_SHA and
          sha(SUPPORT) == sources["support"] == SUPPORT_SHA)
    check("source_seals", set(sources) == set(files) and
          sources == closure["source_hashes_before"] == closure["source_hashes_after"] and
          all(sources[name] == sha(path) for name, path in files.items()))
    check("invocation_closure", invocation["case_id"] == "G05" and invocation["arm"] == "long" and
          invocation["run_id"] == closure["run_id"] == RUN.name and
          sha(RUN / "invocation.json") == closure["invocation_sha256"] and closure["error"] is None)
    check("ssh_queue_gui", invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    check("five_native_steps", [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("twelve_raw_seals", set(closure["raw"]) == RAW and all(
          (RUN / name).stat().st_size == seal["bytes"] and sha(RUN / name) == seal["sha256"]
          for name, seal in closure["raw"].items()))
    roundtrip = load(RUN / "roundtrip-validation.json")
    before = authored_tables(native_json(RUN / "input.json"))
    after = authored_tables(native_json(RUN / "roundtrip-raw.json"))
    check("exact_roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
          roundtrip["source_sha256"] == SOURCE_SHA and len(before) == 23 and
          all(after.get(name) == value for name, value in before.items()))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("conversion", "Input conversion completed. Errors: 0" in conversion and
          (RUN / "model.sxo").stat().st_size > 4)
    parent_invocation, parent_closure = (load(PARENT_RUN / name) for name in ("invocation.json", "closure.json"))
    check("accepted_parent_binding", parent_invocation["run_id"] == parent_closure["run_id"] == PARENT_RUN.name and
          parent_invocation["input_sha256"] == PARENT_SHA == sha(PARENT_RUN / "input.json") and
          sha(PARENT_RUN / "invocation.json") == parent_closure["invocation_sha256"] and
          parent_closure["error"] is None and
          parent_closure["source_hashes_before"] == parent_closure["source_hashes_after"] and
          all((PARENT_RUN / name).stat().st_size == seal["bytes"] and sha(PARENT_RUN / name) == seal["sha256"]
              for name, seal in parent_closure["raw"].items()))

    event, parent_event = log_events(RUN / "model.log"), log_events(PARENT_RUN / "model.log")
    switches, stops, failures = event["switches"], event["stops"], event["failures"]
    check("branch_paths", len(switches) == len(stops) == 2 and
          [(x[1], x[2]) for x in switches] == [("POS-B", "POS-A"), ("POS-A", "POS-C")] and
          [(x[1], x[2]) for x in stops] == [("POS-B", "POS-A"), ("POS-A", "POS-C")])
    check("long_switch_intervals", len(switches) == len(stops) == 2 and all(
          near(switches[i][3] - switches[i][0], 8.3, 1e-4) and
          near(stops[i][0], switches[i][3], 1e-4) for i in range(2)))
    check("long_event_timeline", len(switches) == len(stops) == 2 and
          near(switches[0][0], 8.94145, 1e-5) and near(stops[0][0], 17.2414, 1e-4) and
          near(switches[1][0], 25.3636, 1e-4) and near(stops[1][0], 33.6636, 1e-4))
    first_stop = "Time: 17.2414 <TEACH-AIR-01,0><G05-PASSIVE [POS-B -> POS-A]>. Switch over stopped."
    scheduled = "Time: 17.2414 <TEACH-AIR-01,0> Next random failure will occur 25.3636"
    sentinel = "Time: 8.94145 <TEACH-AIR-01,0> Next random failure will occur 1e+010"
    check("failure_schedule_after_activation", sentinel in event["log"] and
          first_stop in event["log"] and scheduled in event["log"] and
          event["log"].index(sentinel) < event["log"].index(first_stop) < event["log"].index(scheduled))
    check("two_noncritical_failures", len(failures) == 2 and all(
          near(failures[i][0], [8.94145, 25.3636][i], 1e-4) and failures[i][1] == "noncritical" and
          failures[i][2][-1] == [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")][i] and
          len(failures[i][2]) == i + 1 for i in range(2)) and
          event["log"].count("CM failure mode added") == 2)
    check("parent_control_events", len(parent_event["switches"]) == len(parent_event["stops"]) == 2 and
          len(parent_event["failures"]) == 2 and
          near(parent_event["switches"][0][0], 8.94145, 1e-5) and
          near(parent_event["stops"][0][0], 9.44145, 1e-5) and
          near(parent_event["failures"][1][0], 17.5636, 1e-4))
    check("observed_postcompletion_timing", len(stops) == len(failures) == 2 and
          failures[1][0] > stops[0][0] and
          near(failures[1][0] - stops[0][0],
               parent_event["failures"][1][0] - parent_event["stops"][0][0], 2e-4) and
          near(failures[1][0] - parent_event["failures"][1][0], 7.8, 2e-4))
    check("mission_success", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in event["log"] and
          "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in event["log"] and
          " mission aborted:" not in event["log"])
    check("postmission_cm", len(event["repairs"]) == len(event["repair_ends"]) == 2 and
          all(near(t, 34) and i == n and fm == ["FM-POS-B", "FM-POS-A"][n]
              for n, (t, i, fm) in enumerate(event["repairs"])) and
          all(near(t, 34.5) and i == n for n, (t, i) in enumerate(event["repair_ends"])))

    report = native_json(RUN / "report-raw.json")
    system, stock, summary = (records(report, name) for name in
                              ("SystemResults", "StockTotalResults", "ResultSummary"))
    check("report_tables", {table["name"] for table in report["report"]["tables"]} ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    check("aligned_half_hour_bins", len(system) == len(stock) == 72 and all(
          near(system[i]["STINT"], i * 0.5) and near(system[i]["ETINT"], (i + 1) * 0.5) and
          near(stock[i]["STINT"], i * 0.5) and near(stock[i]["ETINT"], (i + 1) * 0.5)
          for i in range(72)))
    switch_hours = 0.5 * sum(row["NSYSW"] or 0 for row in system)
    operating_hours = 0.5 * sum(row["NSYMO"] or 0 for row in system)
    check("switch_operating_exposure", near(switch_hours, 16.6, 2e-4) and
          near(operating_hours, 9.4, 2e-4) and near(switch_hours + operating_hours, 26, 2e-4))
    parent_system = records(native_json(PARENT_RUN / "report-raw.json"), "SystemResults")
    parent_switch_hours = 0.5 * sum(row["NSYSW"] or 0 for row in parent_system)
    parent_operating_hours = 0.5 * sum(row["NSYMO"] or 0 for row in parent_system)
    check("parent_exposure_contrast", near(parent_switch_hours, 1) and near(parent_operating_hours, 25) and
          near(switch_hours - parent_switch_hours, 15.6) and
          near(parent_operating_hours - operating_hours, 15.6))
    check("failure_repair_ledger", near(sum(row["NFAIL"] for row in system), 2) and
          near(sum(row["NREPT"] for row in system), 2) and
          near(sum(row["SYDT"] or 0 for row in system), 0.5) and
          near(0.5 * sum(row["NSYRP"] or 0 for row in system), 0.5))
    check("event_report_bins", [row["STINT"] for row in system if row["NFAIL"]] == [8.5, 25] and
          [row["STINT"] for row in system if row["NREPT"]] == [34.5])
    check("stock_zero", all(near(row[key] or 0, 0) for row in stock
          for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    check("terminal_ready", near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYRP"], 0) and
          near(system[-1]["NSYMO"], 0))
    check("summary_success", len(summary) == 1 and summary[0]["NREP"] == 1 and
          near(summary[0]["RTIUP"], 36) and near(summary[0]["MSUF"], 1))

    result = {"schema": "simlox-g05-activation-clock-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "run_id": RUN.name, "accepted_parent_run_id": PARENT_RUN.name, "raw_seals": 12,
              "input_sha256": sha(RUN / "input.json"), "invocation_sha256": sha(RUN / "invocation.json"),
              "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"),
              "report_sha256": sha(RUN / "report-raw.json"),
              "switches": switches, "stops": stops, "failure_events": failures,
              "parent_first_switch_stop": parent_event["stops"][0],
              "parent_second_failure": parent_event["failures"][1],
              "switch_hours": switch_hours, "operating_hours": operating_hours,
              "parent_switch_hours": parent_switch_hours, "parent_operating_hours": parent_operating_hours,
              "scope": "one_seed_observed_postcompletion_failure_event_timing",
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
