"""Replay the bounded G05 unavailable-standby native observation from raw files."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import SOURCES, authored_tables, native_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/g05-unavailable-v103-ssh-20261002-01"
EXCLUDED = ROOT / "G05-unavailable-standby-v1.0.2/runs/g05-unavailable-v102-ssh-20261002-01"
PARENT = ROOT / "G05-passive-switchover-v1.0.0/half-input.json"
PARENT_RUN = ROOT / "G05-passive-switchover-v1.0.0/runs/g05-passive-half-v100-ssh-20261002-01"
SUPPORT = ROOT / "G04-three-branch-threshold-v1.0.0/one-input.json"
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
    tables = [table for table in report["report"]["tables"] if table["name"] == name]
    assert len(tables) == 1, name
    columns = [column["name"] for column in tables[0]["columns"]]
    return [dict(zip(columns, row)) for instance in tables[0]["instances"]
            for row in instance["rows"]]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, condition: bool) -> None:
        if name in checks:
            raise ValueError(name)
        checks[name] = bool(condition)

    invocation, closure, steps = (load(RUN / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    contract = load(HERE / "contract.json")
    source_hashes = closure["source_hashes_before"]
    files = {
        "input": HERE / "unavailable-input.json", "parent": PARENT, "support": SUPPORT,
        "table_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    ck("source_and_parent", sha(files["input"]) == sha(RUN / "input.json") ==
       SOURCES["unavailable"] == contract["source_sha256"] and
       sha(PARENT) == contract["parent"]["sha256"])
    ck("source_seals", set(source_hashes) == set(files) and
       source_hashes == closure["source_hashes_after"] == invocation["source_hashes_before"] and
       all(source_hashes[key] == sha(path) for key, path in files.items()))
    ck("diff_and_installed_source", sha(HERE / "exact-diff.json") ==
       contract["exact_diff_sha256"] and all(
           source_hashes[key] == contract["installed_source_sha256"][mapping]
           for key, mapping in (("simlox_exe", "simlox_exe"),
                                ("manual", "manual_pdf"),
                                ("table_dictionary", "table_dictionary"))))
    ck("invocation_closure", invocation["case_id"] == "G05" and
       invocation["arm"] == "unavailable" and
       invocation["run_id"] == closure["run_id"] == RUN.name and
       sha(RUN / "invocation.json") == closure["invocation_sha256"] and
       closure["error"] is None)
    ck("ssh_queue_gui", invocation["session_id"] == 0 and
       invocation["ssh_connection_present"] and
       "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("five_guarded_steps", [step["name"] for step in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(step["status"] == "completed" and step["exit_code"] == 0 and
           step["gui_preserved"] for step in steps))
    ck("twelve_raw_seals", set(closure["raw"]) == RAW and all(
       (RUN / name).stat().st_size == seal["bytes"] and
       sha(RUN / name) == seal["sha256"] for name, seal in closure["raw"].items()))
    roundtrip = load(RUN / "roundtrip-validation.json")
    before = authored_tables(native_json(RUN / "input.json"))
    after = authored_tables(native_json(RUN / "roundtrip-raw.json"))
    ck("exact_roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
       len(before) == 23 and all(after.get(name) == value for name, value in before.items()))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion", "Input conversion completed. Errors: 0" in conversion and
       (RUN / "model.sxo").stat().st_size > 4)
    old_closure = load(EXCLUDED / "closure.json")
    old_conversion = (EXCLUDED / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("excluded_335_diagnostic", old_closure["error"] == "calc output model.sxo absent/empty" and
       old_closure["source_hashes_before"] == old_closure["source_hashes_after"] and
       "(error #335) Out and return time fractions" in old_conversion and
       "Input conversion completed. Errors: 1" in old_conversion)
    ck("accepted_parent_pin", sha(PARENT_RUN / "input.json") == sha(PARENT) and
       load(PARENT_RUN / "closure.json")["error"] is None)

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    switches = [(float(t), old, new, float(end)) for t, old, new, end in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. "
        r"switch over started\. Will be finished at ([\d.]+)\.", log)]
    stops = [(float(t), old, new) for t, old, new in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0><G05-PASSIVE \[(POS-[ABC]) -> (POS-[ABC])\]>\. Switch over stopped\.", log)]
    ck("two_selected_switches", switches == [(8.94145, "POS-B", "POS-A", 9.44145),
                                             (17.5636, "POS-A", "POS-C", 18.0636)] and
       stops == [(9.44145, "POS-B", "POS-A"), (18.0636, "POS-A", "POS-C")])
    failures = [(float(t), severity, re.findall(
        r"Failure Mode: (FM-POS-[AB]) on materiel: <(POS-[AB]),0>", body))
        for t, severity, body in re.findall(
            r"Time: ([\d.]+) <TEACH-AIR-01,0> (noncritical|critical) CM failure mode added, now\s+"
            r"(.*?)\n(?=Time:|$)", log, re.S)]
    ck("identified_operated_faults", failures == [
        (8.94145, "noncritical", [("FM-POS-B", "POS-B")]),
        (17.5636, "noncritical", [("FM-POS-B", "POS-B"), ("FM-POS-A", "POS-A")])])
    starts = [(float(t), int(task), mode) for t, task, mode in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
    ends = [(float(t), int(task)) for t, task in re.findall(
        r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
    ck("online_cm_identified", starts == [(8.94145, 0, "FM-POS-B"),
                                          (17.5636, 1, "FM-POS-A")] and
       "Time: 8.94145  subtask 0 seqno 0 within system CM task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 40 hours" in log and
       ends == [(18.0636, 1)] and "system CM task 0 on <TEACH-AIR-01,0> completed" not in log)
    ck("unavailable_preferred_branch_at_second_selection",
       starts[0][0] < switches[1][0] < starts[0][0] + 40 and
       switches[1][1:3] == ("POS-A", "POS-C") and
       all(task != 0 or time > switches[1][0] for time, task in ends))
    ck("mission_success_and_open_repair", "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and
       " mission aborted:" not in log and
       "Time: 34 <TEACH-AIR-01,BASE-01,0> System arrives" in log and
       "FM-POS-B" in log.split("Time: 34 <TEACH-AIR-01,BASE-01,0> System arrives", 1)[1])

    report = native_json(RUN / "report-raw.json")
    system, stock, summary = (rows(report, name) for name in
                              ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck("report_tables", {table["name"] for table in report["report"]["tables"]} ==
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    ck("aligned_72_bins", len(system) == len(stock) == 72 and all(
       near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
       near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
       for i in range(72)))
    switch_hours = .5 * sum(row["NSYSW"] or 0 for row in system)
    operation_hours = .5 * sum(row["NSYMO"] or 0 for row in system)
    ck("switch_and_operation_hours", near(switch_hours, 1) and near(operation_hours, 25) and
       near(switch_hours + operation_hours, 26))
    ck("failure_and_repair_bins", sum(row["NFAIL"] or 0 for row in system) == 2 and
       sum(row["NREPT"] or 0 for row in system) == 1 and
       [row["STINT"] for row in system if row["NFAIL"]] == [8.5, 17.5] and
       [row["STINT"] for row in system if row["NREPT"]] == [18.0])
    ck("terminal_under_repair", near(system[-1]["NSYRY"], 0) and
       near(system[-1]["NSYRP"], 1) and near(system[-1]["NSYMO"], 0))
    ck("zero_stock", all(near(row[key] or 0, 0) for row in stock
       for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")))
    ck("continuous_summary", len(summary) == 1 and summary[0]["NREP"] == 1 and
       near(summary[0]["MTMF"], 1) and near(summary[0]["STMF"], 25 / 26) and
       near(summary[0]["RTIUP"], 36))
    result = {
        "schema": "simlox-g05-unavailable-standby-v103-author-validation/v1",
        "passed": all(checks.values()), "checks": len(checks),
        "differences": [name for name, passed in checks.items() if not passed],
        "run_id": RUN.name, "raw_seals": 12,
        "input_sha256": sha(RUN / "input.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "report_sha256": sha(RUN / "report-raw.json"),
        "excluded_335_closure_sha256": sha(EXCLUDED / "closure.json"),
        "switches": switches, "faults": failures, "repair_starts": starts,
        "repair_ends": ends, "switch_hours": switch_hours,
        "operating_hours": operation_hours,
        "scope": "one_fixed_seed_continuous_mission_priority_skip_while_B_online_CM_open",
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
