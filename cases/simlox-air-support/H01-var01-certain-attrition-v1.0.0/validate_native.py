"""Replay the frozen H01.var01 DAMP endpoints against guarded native evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import authored_tables, native_json

HERE = Path(__file__).resolve().parent
RUNS = {"zero": HERE / "runs/h01-zero-v100-ssh-20261002-01",
        "certain": HERE / "runs/h01-certain-v100-ssh-20261002-01"}
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
        assert name not in checks
        checks[name] = bool(condition)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent = HERE.parent / "A02-single-aircraft-repeated-missions/native-input.json"
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_sources", sha(parent) == contract["accepted_parent"]["sha256"] and
       all(sha(path) == contract["source_sha256"][arm] for arm, path in sources.items()) and
       sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and
       diff["parent_sha256"] == sha(parent) and
       diff["zero_sha256"] == sha(sources["zero"]) and
       diff["certain_sha256"] == sha(sources["certain"]))
    ck("exact_delta", diff["parent_to_zero"] == {
       "added_tables": ["DamageItem", "DamageType", "MissionDamage"],
       "changed_tables": ["ProblemDescription"]} and
       set(diff["zero_to_certain"]) == {"MissionDamage", "ProblemDescription"} and
       diff["zero_to_certain"]["MissionDamage"]["before"][0][3] == 0 and
       diff["zero_to_certain"]["MissionDamage"]["after"][0][3] == 1)
    authored = {arm: authored_tables(native_json(path)) for arm, path in sources.items()}
    ck("sixteen_authored_tables", all(len(model) == 16 for model in authored.values()))
    ck("paired_source_isolation", all(authored["zero"][name] == authored["certain"][name]
                                  for name in authored["zero"]
                                  if name not in {"MissionDamage", "ProblemDescription"}))
    evidence = {}
    for arm, run in RUNS.items():
        source = sources[arm]
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
        ck(f"{arm}.five_steps", [step["name"] for step in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(step["status"] == "completed" and step["exit_code"] == 0 and
               step["gui_preserved"] for step in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and
           sha(run / name) == seal["sha256"] for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = authored_tables(native_json(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           all(exported.get(name) == value for name, value in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 2" in converter and
           "warning #108" in converter and "warning #126" in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        mission_starts = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2", log)]
        successes = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission success:", log)]
        aborts = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:", log)]
        cancellations = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission cancelled:", log)]
        damage = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-LOSS occured", log)]
        attrition = [float(t) for t in re.findall(
            r"Time: ([\d.]+) <TEACH-AIR-01,0> subject to attrition", log)]
        ck(f"{arm}.no_ordinary_failure", "random failure added" not in log and
           "CM failure mode added" not in log)
        if arm == "zero":
            ck("zero.events", mission_starts == [8, 20, 32] and
               successes == [10, 22, 34] and not aborts and not cancellations and
               not damage and not attrition)
        else:
            ck("certain.damage_once_during_mission", mission_starts == [8] and
               not successes and len(damage) == len(attrition) == len(aborts) == 1 and
               near(damage[0], 8.78145) and 8 < damage[0] < 10 and
               near(attrition[0], damage[0]) and near(aborts[0], damage[0]) and
               "Time: 9.28145 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log)
            ck("certain.later_missions_cancelled", len(cancellations) == 2 and
               near(cancellations[0], 20.3333) and near(cancellations[1], 32.3333))
        report = native_json(run / "report-raw.json")
        summary, system, stock = (rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shapes", len(summary) == 1 and len(system) == len(stock) == 72 and all(
           near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
           near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
           for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near((row["NSYA"] or 0) + (row["NSYLA"] or 0), 1) and
           near((row["NSYRY"] or 0) + (row["NSYMA"] or 0) + (row["NSYLA"] or 0), 1)
           for row in system))
        operating = .5 * sum(row["NSYMO"] or 0 for row in system)
        lost = .5 * sum(row["NSYLA"] or 0 for row in system)
        if arm == "zero":
            ck("zero.report", near(operating, 6) and near(lost, 0) and
               near(system[-1]["NSYRY"], 1) and near(system[-1]["NSYLA"], 0) and
               near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 1))
        else:
            ck("certain.report", near(operating, damage[0] - 8) and
               near(lost, 36 - damage[0]) and
               near(system[-1]["NSYRY"], 0) and near(system[-1]["NSYLA"], 1) and
               near(summary[0]["MSTF"], 1 / 3) and near(summary[0]["MSUF"], 0))
        evidence[arm] = {"run_id": run.name, "input_sha256": sha(source),
                         "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "mission_starts": mission_starts, "mission_successes": successes,
                         "mission_aborts": aborts, "mission_cancellations": cancellations,
                         "damage": damage, "attrition": attrition,
                         "operating_hours": operating, "lost_aircraft_hours": lost,
                         "terminal_ready": system[-1]["NSYRY"],
                         "terminal_lost": system[-1]["NSYLA"],
                         "summary": summary[0], "stock_rows": stock}
    ck("stock_all_cells_equal", evidence["zero"]["stock_rows"] == evidence["certain"]["stock_rows"])
    for arm in evidence:
        evidence[arm].pop("stock_rows")
    result = {"schema": "simlox-h01-var01-certain-attrition-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "one_fixed_seed_per_mission_DAMP_zero_vs_one_with_attrition",
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
