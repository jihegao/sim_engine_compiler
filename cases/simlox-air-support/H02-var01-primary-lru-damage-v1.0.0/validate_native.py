"""Replay sealed quiet E01 versus primary-LRU damage native evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {"control": HERE / "runs/h02-var01-lru-control-v100-ssh-20261002-01",
        "lru": HERE / "runs/h02-var01-lru-v100-ssh-20261002-01"}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
       "report-raw.json", "model.log", "import.log", "export.log", "run.log",
       "report-export.log", "roundtrip-validation.json", "steps.json"}
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")


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


def times(log: str, expression: str) -> list[float]:
    return [float(t) for t in re.findall(expression, log)]


def identities(log: str, expression: str) -> list[tuple[float, int]]:
    return [(float(t), int(item)) for t, item in re.findall(expression, log)]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, condition: bool) -> None:
        assert name not in checks
        checks[name] = bool(condition)

    contract = load(HERE / "contract.json")
    diff = load(HERE / "exact-diff.json")
    parent = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
    reference = HERE.parent / "H02-var01-system-damage-direct-repair-v1.0.0/system-input.json"
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_lineage", sha(parent) == contract["accepted_parent"]["sha256"] == diff["parent_sha256"] and
       sha(reference) == contract["schema_reference"]["sha256"] and
       all(sha(source) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, source in sources.items()) and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       sha(HERE / "contract.json") == "e1c24df6bbe399dcd0d3e503f0e5acec31fcc1ff9d5cf52051d14606b81afb4f")
    ck("exact_delta", set(diff["parent_to_control"]["changed_tables"]) ==
       {"ProblemDescription", "System", "Item"} and
       not diff["parent_to_control"]["added_tables"] and
       set(diff["control_to_lru"]["added_tables"]) ==
       {"DamageType", "MissionDamage", "DamageItem", "DamageReplacement"} and
       set(diff["control_to_lru"]["changed_tables"]) == {"ProblemDescription"} and
       not diff["control_to_lru"]["removed_tables"])
    authored = {arm: populated(parse_native(path)) for arm, path in sources.items()}
    ck("authored_tables", len(authored["control"]) == 20 and len(authored["lru"]) == 24)
    ck("installed_sources", sha(MANUAL) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(DICTIONARY) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(EXE) == contract["installed_source_sha256"]["simlox_exe"])
    evidence = {}
    ledgers = {}
    for arm, run in RUNS.items():
        source = sources[arm]
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm}.source_closure", sha(run / "input.json") == sha(source) and
           invocation["variant"] == arm and invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] ==
           invocation["source_hashes_before"] and
           closure["source_hashes_before"]["input"] == sha(source) and
           closure["source_hashes_before"]["parent"] == sha(parent) and
           closure["source_hashes_before"]["reference"] == sha(reference) and
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
               step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and
           sha(run / name) == seal["sha256"] for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           all(exported.get(name) == value for name, value in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 2" in converter and
           "warning #108" in converter and "warning #2053" in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        successes = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission success:")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        damage = identities(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
        ck(f"{arm}.no_ordinary_failure", "random failure added" not in log and
           "CM failure mode added" not in log and "subject to attrition" not in log)
        if arm == "control":
            ck("control.events", starts == [8, 20, 32] and successes == [10, 22, 34] and
               not aborts and not damage and "Take replacement item" not in log and
               "Item requiring maintenance arrives" not in log)
        else:
            issued = identities(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
            returned = identities(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
            removed = identities(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>[^\n]*damaged")
            surp_start = times(log, r"Time: ([\d.]+)  system SURP task \d+ on <TEACH-AIR-01,0> started")
            surp_end = times(log, r"Time: ([\d.]+)  system SURP task \d+ on <TEACH-AIR-01,0> completed")
            item_start = times(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,\d+> starts performing, planned to last for 1 hours")
            item_end = times(log, r"Time: ([\d.]+)  item DIRP task \d+ on <TEACH-LRU-01,0,\d+> completed")
            ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
            ck("lru.damage", starts == [8, 20, 32] and not successes and
               len(damage) == len(aborts) == 3 and [item for _, item in damage] == [1, 2, 3] and
               all(starts[i] < damage[i][0] < starts[i] + 2 and
                   near(aborts[i], damage[i][0]) for i in range(3)))
            ck("lru.stock_cycle", len(issued) == len(removed) == len(returned) == 3 and
               [item for _, item in issued] == [0, 1, 2] and
               [item for _, item in removed] == [1, 2, 3] and
               [item for _, item in returned] == [1, 2, 3] and
               all(damage[i][0] < issued[i][0] <= removed[i][0] < returned[i][0] and
                   returned[i][0] < (20 if i == 0 else 32 if i == 1 else 36)
                   for i in range(3)) and "discard" not in log.lower())
            ck("lru.repair_and_ready", len(surp_start) == len(surp_end) ==
               len(item_start) == len(item_end) == len(ready) == 3 and
               all(near(surp_end[i] - surp_start[i], .5, 1e-3) and
                   near(item_end[i] - item_start[i], 1, 1e-3) and
                   near(ready[i], surp_end[i]) and
                   ready[i] < (20 if i == 0 else 32 if i == 1 else 36)
                   for i in range(3)))
            ck("lru.task_breakdown", len(re.findall(r"remove subitem subtask \d+ seqno 1 within system SURP task \d+ on <TEACH-AIR-01,0> completed", log)) == 3 and
               len(re.findall(r"fit subitem subtask \d+ seqno 2 within system SURP task \d+ on <TEACH-AIR-01,0> completed", log)) == 3)
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near((row["NSYA"] or 0) + (row["NSYUA"] or 0) + (row["NSYLA"] or 0), 1) and
           near((row["NSYRY"] or 0) + (row["NSYMA"] or 0) +
                (row["NSYUA"] or 0) + (row["NSYLA"] or 0), 1)
           for row in system))
        n = 0 if arm == "control" else 3
        ck(f"{arm}.event_bins", sum(row["NDAM"] or 0 for row in system) == n and
           sum(row["NREPT"] or 0 for row in system) == n and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           sum(row["NDD"] or 0 for row in stock) == n and
           all(near(row["PNB"], 1) and near(row["NBO"], 0) for row in stock))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1) and
           near(system[-1]["NSYLA"], 0) and near(stock[-1]["PNB"], 1) and
           near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 1 if arm == "control" else 0))
        ledgers[arm] = {"summary": summary[0], "system": system, "stock": stock}
        evidence[arm] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "mission_starts": starts, "mission_successes": successes,
                         "mission_aborts": aborts, "damage": damage,
                         "operating_hours": .5 * sum(row["NSYMO"] or 0 for row in system),
                         "system_repair_hours": .5 * sum(row["NSYRP"] or 0 for row in system),
                         "terminal_ready": system[-1]["NSYRY"], "summary": summary[0]}
    ck("stock_demand_contrast", sum(row["NDD"] or 0 for row in ledgers["control"]["stock"]) == 0 and
       sum(row["NDD"] or 0 for row in ledgers["lru"]["stock"]) == 3)
    result = {"schema": "simlox-h02-var01-primary-lru-damage-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "one_fixed_seed_primary_lru_damage_replacement_and_repair",
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
