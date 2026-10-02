"""Replay sealed H02.var04 damage-specific and ordinary system repair runs."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var01-system-damage-direct-repair-v1.0.0/system-input.json"
RUNS = {arm: HERE / "runs" / f"h02-var04-{arm}-v100-ssh-20261002-01"
        for arm in ("explicit", "fallback")}
INSTALL = {"manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(actual: object, target: float, tol: float = 1e-3) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(float(actual), target, rel_tol=0, abs_tol=tol)


def rows(report: dict, name: str) -> list[dict]:
    table, = [item for item in report["report"]["tables"] if item["name"] == name]
    columns = [col["name"] for col in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(value) for value in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, condition: bool) -> None:
        assert name not in checks
        checks[name] = bool(condition)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_sources", sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       all(sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, path in sources.items()) and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       sha(HERE / "contract.json") == "22548078839af3118443adae440e43d4cd8e17d0f930d3adc8806deceb12029d")
    ck("exact_delta", not diff["parent_to_explicit"]["added_tables"] and
       not diff["parent_to_explicit"]["removed_tables"] and
       set(diff["parent_to_explicit"]["changed_tables"]) == {"SystemRepair", "ProblemDescription"} and
       not diff["explicit_to_fallback"]["added_tables"] and
       not diff["explicit_to_fallback"]["removed_tables"] and
       set(diff["explicit_to_fallback"]["changed_tables"]) == {"DamageRepair", "ProblemDescription"} and
       diff["parent_to_explicit"]["changed_tables"]["SystemRepair"]["after"]["instances"][0]["rows"][0][:3] ==
       ["TEACH-AIR-01", "BASE-01", 2] and
       diff["explicit_to_fallback"]["changed_tables"]["DamageRepair"]["before"]["instances"][0]["rows"][0][:4] ==
       ["BATTLE-LOSS", "TEACH-AIR-01", "BASE-01", 1] and
       not diff["explicit_to_fallback"]["changed_tables"]["DamageRepair"]["after"]["instances"][0]["rows"])
    ck("installed_sources", sha(INSTALL["manual"]) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(INSTALL["dictionary"]) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(INSTALL["simlox_exe"]) == contract["installed_source_sha256"]["simlox_exe"])
    authored = {arm: populated(parse_native(path)) for arm, path in sources.items()}
    ck("authored_tables", len(authored["explicit"]) == 18 and len(authored["fallback"]) == 17 and
       set(authored["explicit"]) - set(authored["fallback"]) == {"DamageRepair"})
    evidence = {}
    ledgers = {}
    for arm, run in RUNS.items():
        source = sources[arm]
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        hashes = closure["source_hashes_before"]
        ck(f"{arm}.closure", invocation["variant"] == arm and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["error"] is None and hashes == closure["source_hashes_after"] ==
           invocation["source_hashes_before"] and sha(run / "input.json") == sha(source) and
           hashes["input"] == sha(source) and hashes["parent"] == sha(PARENT) and
           hashes["contract"] == sha(HERE / "contract.json") and
           hashes["builder"] == sha(HERE / "build.py") and
           hashes["exact_diff"] == sha(HERE / "exact-diff.json") and
           hashes["diff_checker"] == sha(HERE / "describe_diff.py") and
           hashes["checker"] == sha(HERE / "check_roundtrip.py") and
           hashes["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
           all(hashes[key] == sha(path) for key, path in INSTALL.items()))
        ck(f"{arm}.guard", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
           [step["name"] for step in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(step["status"] == ("calc_observed" if step["name"] == "calc" else "completed") and
               step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
           for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == len(authored[arm]) and
           all(exported.get(table) == values for table, values in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 3" in converter and
           all(f"warning #{number}" in converter for number in (108, 126, 254)) and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        cancels = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission cancelled:")
        damage = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-LOSS occured")
        attrition = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,0> subject to attrition")
        duration = 1 if arm == "explicit" else 2
        repairs_start = times(log, rf"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for {duration} hours")
        repairs_end = times(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> completed")
        ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
        ck(f"{arm}.events", starts == [8, 20, 32] and len(damage) == len(aborts) == 3 and
           not cancels and not attrition and not any(word in log for word in
           ("random failure added", "CM failure mode added")) and
           all(starts[i] < damage[i] < starts[i] + 2 and near(aborts[i], damage[i])
               for i in range(3)))
        ck(f"{arm}.repairs", len(repairs_start) == len(repairs_end) == len(ready) == 3 and
           all(damage[i] < repairs_start[i] and
               near(repairs_end[i] - repairs_start[i], duration) and
               near(ready[i], repairs_end[i]) for i in range(3)) and
           ready[0] < 20 and ready[1] < 32 and ready[2] < 36)
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near(sum(row[key] or 0 for key in ("NSYA", "NSYUA", "NSYLA")), 1) and
           near(sum(row[key] or 0 for key in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1)
           for row in system))
        repair_hours = .5 * sum(row["NSYRP"] or 0 for row in system)
        ck(f"{arm}.report_events", sum(row["NDAM"] or 0 for row in system) == 3 and
           sum(row["NREPT"] or 0 for row in system) == 3 and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           near(repair_hours, 3 * duration) and
           all(near(row["NSYLA"], 0) for row in system))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1) and
           near(system[-1]["NSYUA"], 0) and near(stock[-1]["NBO"], 0) and
           near(stock[-1]["PNB"], 1) and near(summary[0]["MSTF"], 1) and
           near(summary[0]["MSUF"], 0))
        ledgers[arm] = {"stock": stock, "summary": summary[0]}
        evidence[arm] = {"run_id": run.name, "input_sha256": sha(source),
                         "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "mission_starts": starts, "mission_aborts": aborts,
                         "damage": damage, "repair_start": repairs_start,
                         "repair_complete": repairs_end, "ready": ready,
                         "repair_hours": repair_hours, "terminal_ready": system[-1]["NSYRY"],
                         "summary": summary[0]}
    ck("stock_all_cells_equal", ledgers["explicit"]["stock"] == ledgers["fallback"]["stock"])
    ck("summary_equal", ledgers["explicit"]["summary"] == ledgers["fallback"]["summary"])
    ck("repair_exposure_delta", near(evidence["fallback"]["repair_hours"] -
                                     evidence["explicit"]["repair_hours"], 3))
    result = {"schema": "simlox-h02-var04-system-damage-repair-fallback-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "one_fixed_seed_damage_repair_priority_and_ordinary_system_repair_fallback",
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
