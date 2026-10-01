"""Author replay of the G05 nested passive switch from sealed native evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/g05-nested-v100-ssh-20261002-01"
PARENT_RUN = ROOT / "G05-passive-switchover-v1.0.0/runs/g05-passive-half-v100-ssh-20261002-01"
PARENT = ROOT / "G05-passive-switchover-v1.0.0/half-input.json"
TEMPLATE = ROOT / "G04-nested-series-parallel-v1.0.0/and-input.json"
SOURCE_SHA = "acefc1855fe55cdb9f977c5545ad3d5f780dfc78687c17aa9ce74acbb765dd62"
PARENT_SHA = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
TEMPLATE_SHA = "658cdfcc374a13754c0980888137dd05bb0b94c4dfad5386bab5292fc414dd15"
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
        "input": HERE / "nested-input.json", "parent": PARENT, "support": TEMPLATE,
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
    check("parent_template", sha(PARENT) == sources["parent"] == PARENT_SHA and
          sha(TEMPLATE) == sources["support"] == TEMPLATE_SHA)
    check("source_seals", set(sources) == set(files) and
          sources == closure["source_hashes_before"] == closure["source_hashes_after"] and
          all(sources[name] == sha(path) for name, path in files.items()))
    check("invocation_closure", invocation["case_id"] == "G05" and invocation["arm"] == "nested" and
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
          roundtrip["source_sha256"] == SOURCE_SHA and len(before) == 25 and
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
    check("one_child_switch", len(switches) == len(stops) == 1 and
          switches[0][1:3] == stops[0][1:] == ("POS-B", "POS-A") and
          near(switches[0][0], 8.94145, 1e-5) and near(switches[0][3], 9.44145, 1e-5) and
          near(stops[0][0], 9.44145, 1e-5) and near(switches[0][3] - switches[0][0], 0.5, 1e-5))
    check("two_failure_states", len(failures) == 2 and
          near(failures[0][0], 8.94145, 1e-5) and failures[0][1] == "noncritical" and
          failures[0][2] == [("FM-POS-B", "POS-B")] and
          near(failures[1][0], 17.5636, 1e-4) and failures[1][1] == "critical" and
          failures[1][2] == [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")] and
          event["log"].count("CM failure mode added") == 2 and "FM-POS-C" not in event["log"])
    check("parent_path_contrast", len(parent_event["switches"]) == len(parent_event["stops"]) == 2 and
          [(x[1], x[2]) for x in parent_event["switches"]] ==
          [("POS-B", "POS-A"), ("POS-A", "POS-C")] and
          len(parent_event["failures"]) == 2 and parent_event["failures"][1][1] == "noncritical" and
          near(parent_event["failures"][1][0], failures[1][0], 1e-4))
    check("mission_abort", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in event["log"] and
          "Time: 17.5636 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in event["log"] and
          "Time: 24.0636 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in event["log"] and
          " mission success:" not in event["log"])
    check("postreturn_parallel_cm", len(event["repairs"]) == len(event["repair_ends"]) == 2 and
          all(near(t, 24.0636, 1e-4) and i == n and fm == ["FM-POS-B", "FM-POS-A"][n]
              for n, (t, i, fm) in enumerate(event["repairs"])) and
          all(near(t, 24.5636, 1e-4) and i == n for n, (t, i) in enumerate(event["repair_ends"])))

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
    check("series_root_switch_occupancy", near(switch_hours, 0.5, 2e-5) and
          [row["STINT"] for row in system if row["NSYSW"]] == [8.5, 9.0] and
          near(system[17]["NSYSW"], 0.11710087955, 2e-5) and
          near(system[18]["NSYSW"], 0.88289910555, 2e-5) and
          near(operating_hours, 15.5636, 2e-4))
    check("failure_repair_ledger", near(sum(row["NFAIL"] for row in system), 2) and
          near(sum(row["NREPT"] for row in system), 2) and
          near(sum(row["SYDT"] or 0 for row in system), 0.5) and
          near(0.5 * sum(row["NSYRP"] or 0 for row in system), 0.5))
    check("event_report_bins", [row["STINT"] for row in system if row["NFAIL"]] == [8.5, 17.5] and
          [row["STINT"] for row in system if row["NREPT"]] == [24.5] and
          near(system[49]["NREPT"], 2))
    check("stock_zero", all(near(row[key] or 0, 0) for row in stock
          for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    check("terminal_ready", near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYRP"], 0) and
          near(system[-1]["NSYMO"], 0))
    check("summary_abort", len(summary) == 1 and summary[0]["NREP"] == 1 and
          near(summary[0]["RTIUP"], 36) and near(summary[0]["MSUF"], 0))
    parent_report = native_json(PARENT_RUN / "report-raw.json")
    parent_system = records(parent_report, "SystemResults")
    parent_summary = records(parent_report, "ResultSummary")
    check("parent_report_contrast", len(parent_system) == 72 and len(parent_summary) == 1 and
          near(0.5 * sum(row["NSYSW"] or 0 for row in parent_system), 1.0) and
          near(parent_summary[0]["MSUF"], 1) and near(summary[0]["MSUF"], 0))

    result = {"schema": "simlox-g05-nested-switch-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "run_id": RUN.name, "accepted_parent_run_id": PARENT_RUN.name, "raw_seals": 12,
              "input_sha256": sha(RUN / "input.json"), "invocation_sha256": sha(RUN / "invocation.json"),
              "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"),
              "report_sha256": sha(RUN / "report-raw.json"),
              "switches": switches, "stops": stops, "failure_events": failures,
              "parent_switches": parent_event["switches"], "parent_failure_events": parent_event["failures"],
              "switch_hours": switch_hours, "operating_hours": operating_hours,
              "scope": "fixed_seed_nested_series_with_two_branch_passive_switch_and_terminal_fault",
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
