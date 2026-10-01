"""Author replay of the fixed-seed G05 short and overlapping native pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import SOURCES, authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"g05-overlap-{arm}-v101-ssh-20261002-01" for arm in SOURCES}
PARENT_RUN = ROOT / "G05-passive-threshold-v1.0.0/runs/g05-nbreq-two-v100-ssh-20261002-01"
PARENT = ROOT / "G05-passive-threshold-v1.0.0/two-input.json"
SUPPORT = ROOT / "G05-passive-switchover-v1.0.0/half-input.json"
PARENT_SHA = "f09cc7e9d8f1843148b537125760dc02adfb51bdc1c634e5e03e138af19bb8c4"
SUPPORT_SHA = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
PRIOR = {
    "short": (ROOT / "G05-overlapping-switches-v1.0.0/runs/g05-overlap-short-v100-ssh-20261002-01",
              "70d5911c6d7144a8347e3f0742de3a77188e92bdeb597d9273fa7af582362e2e"),
    "long": (ROOT / "G05-overlapping-switches-v1.0.0/runs/g05-overlap-long-v100-ssh-20261002-01",
             "ca90bb1046dd493f57b6885b073866df883d5dea9b2af3751926b64bf7d4a8b5"),
}
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
    found = [table for table in report["report"]["tables"] if table["name"] == name]
    assert len(found) == 1, name
    columns = [column["name"] for column in found[0]["columns"]]
    return [dict(zip(columns, row)) for instance in found[0]["instances"] for row in instance["rows"]]


def events(path: Path) -> dict:
    log = path.read_text(encoding="utf-8-sig")
    starts = [(float(t), old, new, float(end)) for t, old, new, end in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[AB]) -> (POS-[CD])\]>\. "
        r"switch over started\. Will be finished at ([\d.]+)\.", log)]
    stops = [(float(t), old, new) for t, old, new in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[AB]) -> (POS-[CD])\]>\. Switch over stopped\.", log)]
    failures = []
    for match in re.finditer(r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
                             r"(.*?)\n(?=Time:|$)", log, re.S):
        modes = re.findall(r"Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", match.group(3))
        failures.append((float(match.group(1)), match.group(2), modes))
    repairs = [(float(t), int(i), fm) for t, i, fm in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    repair_ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    scheduled = [(float(t), float(next_time)) for t, next_time in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0> Next random failure will occur ([\d.e+]+)", log)]
    return {"log": log, "starts": starts, "stops": stops, "failures": failures,
            "repairs": repairs, "repair_ends": repair_ends, "scheduled": scheduled}


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
    check(arm, "parent_support", sha(PARENT) == sources["parent"] == PARENT_SHA and
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
    check(arm, "conversion", "Input conversion completed. Errors: 0" in
          (run / "run.log").read_text(encoding="utf-8-sig", errors="replace") and
          (run / "model.sxo").stat().st_size > 4)

    event = events(run / "model.log")
    starts, stops, failures = event["starts"], event["stops"], event["failures"]
    expected_starts = [(8.62763, "POS-B", "POS-C"),
                       (11.5942 if arm == "short" else 16.7498, "POS-A", "POS-D")]
    expected_ends = [9.12763, 12.0942] if arm == "short" else [17.6276, 25.7498]
    check(arm, "two_identified_switches", len(starts) == len(stops) == 2 and
          all(near(starts[i][0], expected_starts[i][0], 1e-4) and
              starts[i][1:3] == expected_starts[i][1:] and
              near(starts[i][3], expected_ends[i], 1e-4) and
              near(stops[i][0], expected_ends[i], 1e-4) and
              stops[i][1:] == expected_starts[i][1:] for i in range(2)))
    check(arm, "switch_lengths", len(starts) == 2 and all(
          near(start[3] - start[0], 0.5 if arm == "short" else 9.0, 1e-4) for start in starts))
    check(arm, "two_noncritical_operated_faults", len(failures) == 2 and all(
          near(failures[i][0], expected_starts[i][0], 1e-4) and failures[i][1] == "noncritical" and
          failures[i][2][-1] == [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")][i] and
          len(failures[i][2]) == i + 1 for i in range(2)) and
          event["log"].count("CM failure mode added") == 2 and "FM-POS-D" not in event["log"])
    check(arm, "mission_success", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in event["log"] and
          "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in event["log"] and
          " mission aborted:" not in event["log"])
    check(arm, "postmission_cm", len(event["repairs"]) == len(event["repair_ends"]) == 2 and
          all(near(t, 34) and i == n and fm == ["FM-POS-B", "FM-POS-A"][n]
              for n, (t, i, fm) in enumerate(event["repairs"])) and
          all(near(t, 34.5) and i == n for n, (t, i) in enumerate(event["repair_ends"])))

    report = native_json(run / "report-raw.json")
    system, stock, summary = (records(report, name) for name in
                              ("SystemResults", "StockTotalResults", "ResultSummary"))
    check(arm, "report_tables", {table["name"] for table in report["report"]["tables"]} ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    check(arm, "aligned_half_hour_bins", len(system) == len(stock) == 72 and all(
          near(system[i]["STINT"], i * 0.5) and near(system[i]["ETINT"], (i + 1) * 0.5) and
          near(stock[i]["STINT"], i * 0.5) and near(stock[i]["ETINT"], (i + 1) * 0.5)
          for i in range(72)))
    switch_hours = 0.5 * sum(row["NSYSW"] or 0 for row in system)
    operating_hours = 0.5 * sum(row["NSYMO"] or 0 for row in system)
    expected_union = 1.0 if arm == "short" else 25.7498 - 8.62763
    check(arm, "switch_union_and_operation", near(switch_hours, expected_union, 2e-4) and
          near(operating_hours, 26 - expected_union, 2e-4) and
          near(switch_hours + operating_hours, 26, 2e-4))
    check(arm, "failure_repair_ledger", near(sum(row["NFAIL"] for row in system), 2) and
          near(sum(row["NREPT"] for row in system), 2) and
          near(sum(row["SYDT"] or 0 for row in system), 0.5) and
          near(0.5 * sum(row["NSYRP"] or 0 for row in system), 0.5))
    check(arm, "event_report_bins", [row["STINT"] for row in system if row["NFAIL"]] ==
          ([8.5, 11.5] if arm == "short" else [8.5, 16.5]) and
          [row["STINT"] for row in system if row["NREPT"]] == [34.5])
    check(arm, "stock_zero", all(near(row[key] or 0, 0) for row in stock
          for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    check(arm, "terminal_ready", near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYRP"], 0) and
          near(system[-1]["NSYMO"], 0))
    check(arm, "summary_success", len(summary) == 1 and summary[0]["NREP"] == 1 and
          near(summary[0]["RTIUP"], 36) and near(summary[0]["MSUF"], 1))
    if arm == "long":
        check(arm, "continuous_overlap_bins", len(starts) == 2 and starts[0][0] < starts[1][0] < stops[0][0] < stops[1][0] and
              all(near(system[i]["NSYSW"], 1) for i in (33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50)) and
              near(switch_hours, 18 - (stops[0][0] - starts[1][0]), 2e-4))
        check(arm, "failure_during_first_switch", len(failures) == 2 and
              starts[0][0] < failures[1][0] < stops[0][0] and
              (8.62763, 16.7498) in event["scheduled"])
    return {"run_id": run.name, "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
            "starts": starts, "stops": stops, "failures": failures,
            "switch_hours": switch_hours, "operating_hours": operating_hours,
            "summary_success": summary[0]["MSUF"]}


def main() -> None:
    checks: dict[str, bool] = {}

    def check(arm: str, name: str, result: bool) -> None:
        key = f"{arm}.{name}"
        if key in checks:
            raise ValueError(key)
        checks[key] = bool(result)

    parent_invocation, parent_closure = (load(PARENT_RUN / name) for name in ("invocation.json", "closure.json"))
    check("parent", "accepted_binding", parent_invocation["run_id"] == parent_closure["run_id"] == PARENT_RUN.name and
          parent_invocation["input_sha256"] == PARENT_SHA == sha(PARENT_RUN / "input.json") and
          sha(PARENT_RUN / "invocation.json") == parent_closure["invocation_sha256"] and
          parent_closure["error"] is None and
          all((PARENT_RUN / name).stat().st_size == seal["bytes"] and sha(PARENT_RUN / name) == seal["sha256"]
              for name, seal in parent_closure["raw"].items()))
    check("prior", "diagnostic_logs", all(sha(path / "model.log") == expected for path, expected in PRIOR.values()))
    data = {arm: analyze(arm, check) for arm in SOURCES}
    short, long = data["short"], data["long"]
    check("pair", "same_four_branch_frozen_short", short["input_sha256"] ==
          sha(PRIOR["short"][0] / "input.json") == SOURCES["short"])
    diff = load(HERE / "exact-diff.json")
    check("pair", "single_behavioral_delta", diff["short_sha256"] == SOURCES["short"] and
          diff["long_sha256"] == SOURCES["long"] and
          set(diff["short_to_long"]) == {"ProblemDescription", "RBDParallel"} and
          diff["short_to_long"]["RBDParallel"]["before"][0][4] == 0.5 and
          diff["short_to_long"]["RBDParallel"]["after"][0][4] == 9.0)
    check("pair", "nonoverlap_vs_overlap", short["stops"][0][0] < short["starts"][1][0] and
          long["starts"][1][0] < long["stops"][0][0] and
          near(long["stops"][0][0] - long["starts"][1][0], 0.8778, 2e-4) and
          near(short["switch_hours"], 1) and near(long["switch_hours"], 17.12217, 2e-4))
    result = {"schema": "simlox-g05-overlapping-switches-v101-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "run_ids": {arm: path.name for arm, path in RUNS.items()}, "raw_seals": 24,
              "arms": data, "scope": "fixed_seed_two_operated_four_branch_overlapping_switch_intervals",
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
