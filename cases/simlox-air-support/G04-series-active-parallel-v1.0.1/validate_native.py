"""Replay the frozen two-arm G04 RBD source, events, ledgers and closure."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import SOURCES, native_json, row_tables

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"g04-{arm}-v101-ssh-20261002-01" for arm in SOURCES}
PARENT = ROOT / "G02-var01-position-modes-v1.0.0"
PARENT_RUN = PARENT / "runs" / "g02-var01-two-position-accepted-20261001-01"
PARENT_SHA = "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
G01_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
EXPECTED_FAILURES = [(8.62763, "FM-POS-B", "POS-B"), (20.8222, "FM-POS-B", "POS-B"),
                     (33.0996, "FM-POS-A", "POS-A")]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def records(doc: dict, name: str) -> list[dict]:
    tables = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(tables) == 1, name
    columns = [c["name"] for c in tables[0]["columns"]]
    return [dict(zip(columns, row)) for instance in tables[0]["instances"] for row in instance["rows"]]


def near(a: float, b: float, tol: float = 3e-5) -> bool:
    return isinstance(a, (int, float)) and math.isclose(float(a), b, rel_tol=0, abs_tol=tol)


def run_data(arm: str, check) -> dict:
    run = RUNS[arm]
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    source = invocation["source_hashes_before"]
    check(arm, "source_input", sha(HERE / f"{arm}-input.json") == sha(run / "input.json") == SOURCES[arm])
    check(arm, "parent_source", sha(PARENT / "native-input.json") == source["parent"] == PARENT_SHA)
    check(arm, "g01_prerequisite", sha(ROOT / "G01-var01-lru-sru-v1.0.1/native-input.json") == source["support"] == G01_SHA)
    files = {"input": HERE / f"{arm}-input.json", "parent": PARENT / "native-input.json",
             "support": ROOT / "G01-var01-lru-sru-v1.0.1/native-input.json",
             "table_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
             "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
             "contract": HERE / "contract.json", "builder": HERE / "build.py",
             "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
             "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
             "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
             "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")}
    check(arm, "all_source_seals", set(source) == set(files) and
          source == closure["source_hashes_before"] == closure["source_hashes_after"] and
          all(source[name] == sha(path) for name, path in files.items()))
    check(arm, "invocation_closure", invocation["run_id"] == closure["run_id"] == run.name and
          invocation["arm"] == arm and sha(run / "invocation.json") == closure["invocation_sha256"] and
          closure["error"] is None)
    check(arm, "ssh_queue_gui", invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    check(arm, "five_native_steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    check(arm, "twelve_raw_seals", set(closure["raw"]) == RAW and all(
          (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
          for name, seal in closure["raw"].items()))
    roundtrip = load(run / "roundtrip-validation.json")
    check(arm, "roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
          roundtrip["source_sha256"] == SOURCES[arm] and len(roundtrip["row_tables"]) == 23 and
          all(name in row_tables(native_json(run / "roundtrip-raw.json")) for name in roundtrip["row_tables"]))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(arm, "conversion", "Errors: 0, Warnings: 1, Notes: 0" in conversion and
          "(warning #108)" in conversion and (run / "model.sxo").stat().st_size > 4)
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    label = "critical" if arm == "series" else "noncritical"
    failures = [(float(t), mode, position) for t, mode, position in re.findall(
        rf"Time: ([\d.]+) <TEACH-AIR-01,0> {label} CM failure mode added, now\s+1 failures:\s+"
        r"Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", log)]
    check(arm, "position_failure_identity", len(failures) == 3 and
          all(near(t, expected[0], 1e-5) and mode == expected[1] and position == expected[2]
              for (t, mode, position), expected in zip(failures, EXPECTED_FAILURES)))
    check(arm, "exclusive_failure_class", log.count(f"{label} CM failure mode added") == 3 and
          log.count("noncritical CM failure mode added" if arm == "series" else " critical CM failure mode added") == 0)
    if arm == "series":
        check(arm, "mission_outcomes", log.count(" mission aborted:") == 3 and
              log.count(" mission success:") == 0 and
              all(f"Time: {t:g} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission aborted:" in log
                  for i, (t, _, _) in enumerate(EXPECTED_FAILURES)))
    else:
        check(arm, "mission_outcomes", log.count(" mission aborted:") == 0 and
              log.count(" mission success:") == 3 and
              all(f"Time: {t} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission success:" in log
                  for i, t in enumerate((10, 22, 34))))
    starts = [(float(t), int(i), mode) for t, i, mode in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    expected_starts = (9.12763, 21.3222, 33.5996) if arm == "series" else (10, 22, 34)
    check(arm, "three_postmission_repairs", len(starts) == len(ends) == 3 and
          all(i == j == n and mode == EXPECTED_FAILURES[n][1] and near(start, expected_starts[n]) and
              near(end - start, 0.5, 1e-4) for n, ((start, i, mode), (end, j)) in enumerate(zip(starts, ends))))
    report = native_json(run / "report-raw.json")
    system, stock, summary = (records(report, name) for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    check(arm, "report_tables", {t["name"] for t in report["report"]["tables"]} ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    check(arm, "aligned_half_hour_bins", len(system) == len(stock) == 72 and all(
          near(system[i]["STINT"], i * 0.5) and near(system[i]["ETINT"], (i + 1) * 0.5) and
          near(stock[i]["STINT"], i * 0.5) and near(stock[i]["ETINT"], (i + 1) * 0.5)
          for i in range(72)))
    check(arm, "failure_repair_ledger", near(sum(r["NFAIL"] for r in system), 3) and
          near(sum(r["NREPT"] for r in system), 3) and near(sum(r["SYDT"] or 0 for r in system), 1.5) and
          near(0.5 * sum(r["NSYRP"] or 0 for r in system), 1.5, 1e-4))
    repair_bins = (9.5, 21.5, 34) if arm == "series" else (10.5, 22.5, 34.5)
    check(arm, "event_report_bins", [r["STINT"] for r in system if r["NFAIL"]] == [8.5, 20.5, 33] and
          [r["STINT"] for r in system if r["NREPT"]] == list(repair_bins))
    check(arm, "stock_zero", all(near(r[k] or 0, 0) for r in stock
          for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    check(arm, "terminal_ready", near(system[-1]["NSYRY"], 1) and
          near(system[-1]["NSYRP"], 0) and near(system[-1]["NSYMO"], 0))
    check(arm, "summary_mission", len(summary) == 1 and summary[0]["NREP"] == 1 and
          near(summary[0]["RTIUP"], 36) and
          near(summary[0]["MSUF"], 0 if arm == "series" else 1) and
          near(summary[0]["MTMF"], 0.6748974919319153 if arm == "series" else 1))
    return {"run_id": run.name, "input_sha256": sha(run / "input.json"),
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "failures": failures,
            "cm_starts": starts, "cm_ends": ends, "mission_success_fraction": summary[0]["MSUF"],
            "system_operating_hours": 0.5 * sum(r["NSYMO"] or 0 for r in system)}


def main() -> None:
    checks = {}

    def check(arm: str, name: str, result: bool) -> None:
        key = f"{arm}.{name}"
        if key in checks:
            raise ValueError(key)
        checks[key] = bool(result)

    diagnostic = load(HERE / "diagnostic-predecessor.json")
    old = ROOT / diagnostic["package"] / "runs" / diagnostic["run_id"]
    check("pair", "v100_diagnostic_excluded", diagnostic["publication_state"] == "excluded_diagnostic" and
          sha(old / "input.json") == sha(HERE / "diagnostic-v100-series-input.json") == diagnostic["input_sha256"] and
          sha(old / "closure.json") == diagnostic["closure_sha256"] and
          sha(old / "run.log") == diagnostic["run_log_sha256"] and
          (old / "model.sxo").stat().st_size == 4 and
          (old / "run.log").read_text(encoding="utf-8-sig").count("(error #464)") == 2)
    data = {arm: run_data(arm, check) for arm in SOURCES}
    check("pair", "identical_failure_draws", data["series"]["failures"] == data["parallel"]["failures"])
    check("pair", "series_parent_event_identity", data["series"]["model_log_sha256"] ==
          sha(PARENT_RUN / "model.log"))
    series_report = native_json(RUNS["series"] / "report-raw.json")
    parent_report = native_json(PARENT_RUN / "report-raw.json")
    check("pair", "series_parent_non_description_report", [t for t in series_report["report"]["tables"]
          if t["name"] != "ProblemDescription"] == [t for t in parent_report["report"]["tables"]
          if t["name"] != "ProblemDescription"])
    check("pair", "contrast", data["series"]["mission_success_fraction"] == 0 and
          data["parallel"]["mission_success_fraction"] == 1 and
          data["parallel"]["system_operating_hours"] > data["series"]["system_operating_hours"])
    result = {"schema": "simlox-g04-v101-author-validation/v1", "passed": all(checks.values()),
              "checks": len(checks), "differences": [name for name, ok in checks.items() if not ok],
              "run_ids": {arm: run.name for arm, run in RUNS.items()}, "raw_seals": 24,
              "arms": data, "scope": "fixed_seed_explicit_series_vs_active_one_of_two_parallel",
              "publication_state": "not_published"}
    output = HERE / "author-validation.json"
    raw = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen author validation differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "report_sha256": sha(output)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
