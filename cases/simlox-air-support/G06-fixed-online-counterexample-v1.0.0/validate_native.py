"""Replay the frozen G06 fixed-mission ONLM Y/N counterexample."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import authored_tables, native_json

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-unavailable-standby-v1.0.3"
RUNS = {
    "continuous_Y": PARENT / "runs/g05-unavailable-v103-ssh-20261002-01",
    "fixed_Y": HERE / "runs/g06-fixed-y-v100-ssh-20261002-01",
    "fixed_N": HERE / "runs/g06-fixed-n-v100-ssh-20261002-01",
}
SOURCES = {
    "continuous_Y": PARENT / "unavailable-input.json",
    "fixed_Y": HERE / "fixed-input.json",
    "fixed_N": HERE / "fixed-deferred-input.json",
}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def close(value: object, expected: float) -> bool:
    return isinstance(value, (int, float)) and math.isclose(float(value), expected, abs_tol=1e-4, rel_tol=0)


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(found) == 1
    t = found[0]
    return [c["name"] for c in t["columns"]], [r for i in t["instances"] for r in i["rows"]]


def changed_cells(before: tuple[list[str], list[list]], after: tuple[list[str], list[list]]) -> list[dict]:
    cols, a = before
    assert cols == after[0] and len(a) == len(after[1])
    return [{"row": ri, "column": col, "before": row[ci], "after": after[1][ri][ci]}
            for ri, row in enumerate(a) for ci, col in enumerate(cols)
            if row[ci] != after[1][ri][ci]]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, passed: bool) -> None:
        assert name not in checks
        checks[name] = bool(passed)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    ck("source_hashes", sha(SOURCES["continuous_Y"]) == contract["continuous_parent"]["sha256"] and
       sha(SOURCES["fixed_Y"]) == contract["fixed_sources_sha256"]["Y"] and
       sha(SOURCES["fixed_N"]) == contract["fixed_sources_sha256"]["N"] and
       sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    ck("exact_diffs", set(diff["parent_to_fixed"]) == {"MissionType", "ProblemDescription"} and
       set(diff["fixed_y_to_n"]) == {"RBDParallel", "ProblemDescription"} and
       diff["parent_sha256"] == sha(SOURCES["continuous_Y"]) and
       diff["source_sha256"] == sha(SOURCES["fixed_Y"]) and
       diff["deferred_sha256"] == sha(SOURCES["fixed_N"]))
    models = {arm: authored_tables(native_json(path)) for arm, path in SOURCES.items()}
    ck("all_23_input_tables", all(len(model) == 23 for model in models.values()))
    ck("fixed_y_n_source_isolation", all(models["fixed_Y"][name] == models["fixed_N"][name]
                                        for name in models["fixed_Y"]
                                        if name not in {"ProblemDescription", "RBDParallel"}))
    evidence = {}
    reports = {}
    for arm, run in RUNS.items():
        source = SOURCES[arm]
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm}.source_and_closure", sha(run / "input.json") == sha(source) and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] and
           closure["source_hashes_before"]["input"] == sha(source) and closure["error"] is None)
        ck(f"{arm}.guarded_session", invocation["session_id"] == 0 and
           invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm}.five_steps", [s["name"] for s in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
           for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = authored_tables(native_json(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           all(exported.get(name) == value for name, value in models[arm].items()))
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0" in
           (run / "run.log").read_text(encoding="utf-8-sig", errors="replace") and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        failures = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <TEACH-AIR-01,0> noncritical CM failure mode added, now", log)]
        starts = {mode: float(t) for t, mode in re.findall(
            r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)}
        completed = [float(t) for t in re.findall(
            r"Time: ([\d.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed", log)]
        ck(f"{arm}.mission_and_faults", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 26" in log and
           "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and
           "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and
           len(failures) == 2 and close(failures[0], 8.94145) and close(failures[1], 17.5636))
        expected = {"FM-POS-B": 8.94145, "FM-POS-A": 17.5636} if arm == "continuous_Y" else {
            "FM-POS-B": 34.0, "FM-POS-A": 34.0}
        ck(f"{arm}.direct_cm_starts", starts.keys() == expected.keys() and
           all(close(starts[mode], value) for mode, value in expected.items()) and
           "starts performing, planned to last for 40 hours" in log and
           "starts performing, planned to last for 0.5 hours" in log)
        ck(f"{arm}.A_done_B_open", len(completed) == 1 and
           close(completed[0], 18.0636 if arm == "continuous_Y" else 34.5))
        report = native_json(run / "report-raw.json")
        reports[arm] = {name: table(report, name) for name in
                        ("ResultSummary", "SystemResults", "StockTotalResults")}
        ck(f"{arm}.report_shapes", len(reports[arm]["ResultSummary"][1]) == 1 and
           len(reports[arm]["SystemResults"][1]) == len(reports[arm]["StockTotalResults"][1]) == 72)
        evidence[arm] = {"run_id": run.name, "input_sha256": sha(source),
                         "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "failures": failures, "cm_starts": starts, "cm_completions": completed}
    fixed_changes = {name: changed_cells(reports["fixed_Y"][name], reports["fixed_N"][name])
                     for name in reports["fixed_Y"]}
    ck("fixed_y_n_model_events_equal", evidence["fixed_Y"]["model_log_sha256"] ==
       evidence["fixed_N"]["model_log_sha256"])
    ck("fixed_y_n_report_cells_equal", all(not cells for cells in fixed_changes.values()))
    continuous_to_fixed = {name: changed_cells(reports["continuous_Y"][name], reports["fixed_Y"][name])
                           for name in reports["continuous_Y"]}
    ck("continuous_to_fixed_report_contrast", bool(continuous_to_fixed["SystemResults"]) and
       any(cell["column"] == "NREPT" for cell in continuous_to_fixed["SystemResults"]))
    result = {"schema": "simlox-g06-fixed-online-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "fixed_y_n_report_changes": fixed_changes,
              "continuous_to_fixed_report_changes": continuous_to_fixed,
              "raw_seals": 36, "scope": "one_fixed_seed_fixed_mission_direct_cm_onlm_y_vs_n_pair",
              "publication_state": "not_published"}
    output = HERE / "author-validation.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen author validation differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "differences": result["differences"], "sha256": sha(output),
                      "continuous_to_fixed_changed_cells":
                      {name: len(cells) for name, cells in continuous_to_fixed.items()}}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
