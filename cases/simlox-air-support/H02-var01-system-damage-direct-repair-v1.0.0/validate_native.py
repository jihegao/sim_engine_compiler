"""Replay sealed H02.var01 attrition and system direct-repair evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: HERE / "runs" / f"h02-var01-{arm}-v100-ssh-20261002-01"
        for arm in ("attrition", "system")}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
       "report-raw.json", "model.log", "import.log", "export.log",
       "run.log", "report-export.log", "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(value: object, expected: float, tolerance: float = 1e-4) -> bool:
    return isinstance(value, (int, float)) and math.isclose(
        float(value), expected, rel_tol=0, abs_tol=tolerance)


def rows(report: dict, name: str) -> list[dict]:
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(found) == 1
    columns = [c["name"] for c in found[0]["columns"]]
    return [dict(zip(columns, row)) for instance in found[0]["instances"]
            for row in instance["rows"]]


def times(log: str, expression: str) -> list[float]:
    return [float(t) for t in re.findall(expression, log)]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, condition: bool) -> None:
        assert name not in checks
        checks[name] = bool(condition)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent = HERE.parent / "H01-var01-certain-attrition-v1.0.0/certain-input.json"
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_sources", sha(parent) == contract["accepted_parent"]["sha256"] and
       all(sha(source) == contract["sources_sha256"][arm]
           for arm, source in sources.items()) and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       sha(HERE / "contract.json") == "e56967790ab97d4e90e560d3c5a7f945fc45c8629a99bf07dd3ed277e51ad375")
    ck("exact_delta", sha(parent) == sha(sources["attrition"]) ==
       diff["parent_sha256"] == diff["attrition_sha256"] and
       sha(sources["system"]) == diff["system_sha256"] and
       not diff["removed_tables"] and set(diff["added_tables"]) == {"DamageRepair"} and
       set(diff["changed_tables"]) == {"DamageItem", "ProblemDescription"} and
       diff["changed_tables"]["DamageItem"]["before"]["instances"][0]["rows"][0][2] == "<ATTRITION>" and
       diff["changed_tables"]["DamageItem"]["after"]["instances"][0]["rows"][0][2] == "<SYSTEM>" and
       diff["added_tables"]["DamageRepair"]["instances"][0]["rows"][0][:7] ==
       ["BATTLE-LOSS", "TEACH-AIR-01", "BASE-01", 1, 0, 1, 1])
    authored = {arm: populated(parse_native(path)) for arm, path in sources.items()}
    ck("authored_tables", len(authored["attrition"]) == 16 and
       len(authored["system"]) == 17 and
       set(authored["system"]) - set(authored["attrition"]) == {"DamageRepair"})
    evidence = {}
    ledgers = {}
    for arm, run in RUNS.items():
        source = sources[arm]
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm}.source_and_closure", sha(run / "input.json") == sha(source) and
           invocation["variant"] == arm and invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] ==
           invocation["source_hashes_before"] and
           closure["source_hashes_before"]["input"] == sha(source) and
           closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and
           closure["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
           closure["source_hashes_before"]["checker"] == sha(HERE / "check_roundtrip.py") and
           closure["error"] is None)
        ck(f"{arm}.guarded_session", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm}.five_steps", [step["name"] for step in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(step["status"] in ({"calc_observed"} if step["name"] == "calc" else {"completed"}) and
               step["exit_code"] == 0 and
               step["gui_preserved"] for step in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and
           sha(run / name) == seal["sha256"] for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           all(exported.get(name) == value for name, value in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        warnings = 2 if arm == "attrition" else 3
        ck(f"{arm}.conversion", f"Input conversion completed. Errors: 0, Warnings: {warnings}" in converter and
           "warning #108" in converter and "warning #126" in converter and
           ("warning #254" in converter) == (arm == "system") and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        cancellations = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission cancelled:")
        successes = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission success:")
        damage = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-LOSS occured")
        attrition = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,0> subject to attrition")
        ck(f"{arm}.no_ordinary_failure", "random failure added" not in log and
           "CM failure mode added" not in log)
        if arm == "attrition":
            ck("attrition.log", starts == [8] and not successes and
               len(damage) == len(attrition) == len(aborts) == 1 and
               near(damage[0], 8.78145) and near(attrition[0], damage[0]) and
               near(aborts[0], damage[0]) and len(cancellations) == 2 and
               near(cancellations[0], 20.3333) and near(cancellations[1], 32.3333) and
               "system DIRP task" not in log)
        else:
            repairs_start = times(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours")
            repairs_end = times(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> completed")
            ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
            ck("system.events", starts == [8, 20, 32] and not successes and
               not cancellations and not attrition and len(damage) == len(aborts) == 3 and
               all(starts[i] < damage[i] < starts[i] + 2 and near(aborts[i], damage[i])
                   for i in range(3)))
            ck("system.repairs", len(repairs_start) == len(repairs_end) == len(ready) == 3 and
               all(damage[i] < repairs_start[i] and
                   near(repairs_end[i] - repairs_start[i], 1, 1e-3) and
                   near(ready[i], repairs_end[i]) for i in range(3)) and
               ready[0] < 20 and ready[1] < 32 and ready[2] < 36)
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shapes", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near((row["NSYA"] or 0) + (row["NSYUA"] or 0) + (row["NSYLA"] or 0), 1) and
           near((row["NSYRY"] or 0) + (row["NSYMA"] or 0) +
                (row["NSYUA"] or 0) + (row["NSYLA"] or 0), 1)
           for row in system))
        ck(f"{arm}.event_bins", sum(row["NDAM"] or 0 for row in system) ==
           (0 if arm == "attrition" else 3) and
           sum(row["NREPT"] or 0 for row in system) ==
           (0 if arm == "attrition" else 3) and
           sum(row["NFAIL"] or 0 for row in system) == 0)
        lost = .5 * sum(row["NSYLA"] or 0 for row in system)
        repair = .5 * sum(row["NSYRP"] or 0 for row in system)
        if arm == "attrition":
            ck("attrition.report", near(lost, 36 - damage[0]) and near(repair, 0) and
               near(system[-1]["NSYLA"], 1) and near(system[-1]["NSYRY"], 0) and
               near(summary[0]["MSTF"], 1 / 3) and near(summary[0]["MSUF"], 0))
        else:
            ck("system.report", near(lost, 0) and near(repair, 3, 1e-3) and
               near(system[-1]["NSYLA"], 0) and near(system[-1]["NSYRY"], 1) and
               near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 0))
        ledgers[arm] = {"system": system, "stock": stock, "summary": summary[0]}
        evidence[arm] = {"run_id": run.name, "input_sha256": sha(source),
                         "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "mission_starts": starts, "mission_aborts": aborts,
                         "mission_cancellations": cancellations,
                         "damage": damage, "attrition": attrition,
                         "lost_aircraft_hours": lost, "repair_hours": repair,
                         "terminal_ready": system[-1]["NSYRY"],
                         "terminal_lost": system[-1]["NSYLA"],
                         "summary": summary[0]}
    ck("stock_all_cells_equal", ledgers["attrition"]["stock"] == ledgers["system"]["stock"])
    result = {"schema": "simlox-h02-var01-system-direct-repair-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "one_fixed_seed_attrition_vs_system_direct_repair",
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
