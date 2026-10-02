"""Replay two sealed item-damage replacement paths and their ledgers."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
RUNS = {arm: HERE / "runs" / f"h02-var04-item-{arm}-v100-ssh-20261002-01"
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


def near(actual: object, target: float, tolerance: float = 1e-3) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(
        float(actual), target, rel_tol=0, abs_tol=tolerance)


def rows(report: dict, name: str) -> list[dict]:
    table, = [t for t in report["report"]["tables"] if t["name"] == name]
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(t) for t in re.findall(pattern, log)]


def identities(log: str, pattern: str) -> list[tuple[float, int]]:
    return [(float(t), int(i)) for t, i in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, value: bool) -> None:
        assert name not in checks
        checks[name] = bool(value)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_sources", sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       all(sha(source) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"]
           for arm, source in sources.items()) and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       sha(HERE / "contract.json") == "c093910abcdcf57ebca688abda7bc3523c7d6fada99c368d6f2bb31e597090e4")
    ck("exact_delta", not diff["parent_to_explicit"]["added_tables"] and
       not diff["parent_to_explicit"]["removed_tables"] and
       set(diff["parent_to_explicit"]["changed_tables"]) == {"ItemReplacement", "ProblemDescription"} and
       not diff["explicit_to_fallback"]["added_tables"] and
       not diff["explicit_to_fallback"]["removed_tables"] and
       set(diff["explicit_to_fallback"]["changed_tables"]) == {"DamageReplacement", "ProblemDescription"} and
       diff["parent_to_explicit"]["changed_tables"]["ItemReplacement"]["after"]["instances"][0]["rows"][0][:5] ==
       ["TEACH-AIR-01", "TEACH-LRU-01", "BASE-01", 1, 1] and
       diff["explicit_to_fallback"]["changed_tables"]["DamageReplacement"]["before"]["instances"][0]["rows"][0][:5] ==
       ["BATTLE-HIT", "BASE-01", "TEACH-AIR-01", "TEACH-LRU-01", .5] and
       not diff["explicit_to_fallback"]["changed_tables"]["DamageReplacement"]["after"]["instances"][0]["rows"])
    ck("installed_sources", sha(INSTALL["manual"]) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(INSTALL["dictionary"]) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(INSTALL["simlox_exe"]) == contract["installed_source_sha256"]["simlox_exe"])
    authored = {arm: populated(parse_native(source)) for arm, source in sources.items()}
    ck("authored_tables", len(authored["explicit"]) == 25 and len(authored["fallback"]) == 24 and
       set(authored["explicit"]) - set(authored["fallback"]) == {"DamageReplacement"})
    evidence = {}
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
           all(hashes[name] == sha(path) for name, path in INSTALL.items()))
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
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 2" in converter and
           "warning #108" in converter and "warning #2053" in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        damage = identities(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
        issued = identities(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
        removed = identities(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>[^\n]*damaged")
        returned = identities(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
        surp_start = times(log, r"Time: ([\d.]+)  system SURP task \d+ on <TEACH-AIR-01,0> started")
        surp_end = times(log, r"Time: ([\d.]+)  system SURP task \d+ on <TEACH-AIR-01,0> completed")
        item_start = times(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,\d+> starts performing, planned to last for 1 hours")
        item_end = times(log, r"Time: ([\d.]+)  item DIRP task \d+ on <TEACH-LRU-01,0,\d+> completed")
        ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
        duration = .5 if arm == "explicit" else 1
        ck(f"{arm}.damage", starts == [8, 20, 32] and len(aborts) == len(damage) == 3 and
           [i for _, i in damage] == [1, 2, 3] and
           not any(word in log for word in ("random failure added", "CM failure mode added", "subject to attrition")) and
           all(starts[i] < damage[i][0] < starts[i] + 2 and near(aborts[i], damage[i][0])
               for i in range(3)))
        ck(f"{arm}.stock_cycle", len(issued) == len(removed) == len(returned) == 3 and
           [i for _, i in issued] == [0, 1, 2] and
           [i for _, i in removed] == [1, 2, 3] and
           [i for _, i in returned] == [1, 2, 3] and
           all(damage[i][0] < issued[i][0] <= removed[i][0] < returned[i][0] and
               returned[i][0] < (20 if i == 0 else 32 if i == 1 else 36)
               for i in range(3)) and "discard" not in log.lower())
        ck(f"{arm}.tasks", len(surp_start) == len(surp_end) == len(item_start) ==
           len(item_end) == len(ready) == 3 and
           all(near(surp_end[i] - surp_start[i], duration) and
               near(item_end[i] - item_start[i], 1) and
               near(ready[i], surp_end[i]) and
               ready[i] < (20 if i == 0 else 32 if i == 1 else 36)
               for i in range(3)))
        ck(f"{arm}.task_source", len(re.findall(
           rf"remove subitem subtask \d+ seqno {1 if arm == 'explicit' else 0} within system SURP task \d+ on <TEACH-AIR-01,0> completed", log)) == 3 and
           len(re.findall(rf"fit subitem subtask \d+ seqno {2 if arm == 'explicit' else 1} within system SURP task \d+ on <TEACH-AIR-01,0> completed", log)) == 3)
        summary, system, stock = (rows(parse_native(run / "report-raw.json"), name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near(sum(row[key] or 0 for key in ("NSYA", "NSYUA", "NSYLA")), 1) and
           near(sum(row[key] or 0 for key in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1)
           for row in system))
        exposure = .5 * sum(row["NSYRP"] or 0 for row in system)
        ck(f"{arm}.report_events", sum(row["NDAM"] or 0 for row in system) == 3 and
           sum(row["NREPT"] or 0 for row in system) == 3 and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           sum(row["NDD"] or 0 for row in stock) == 3 and
           sum(row["NWT"] or 0 for row in stock) == 3 and
           near(exposure, 3 * duration) and
           all(near(row["NSYLA"], 0) for row in system) and
           all(near(row["NBO"], 0) and near(row["PNB"], 1) for row in stock))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1) and
           near(stock[-1]["NBO"], 0) and near(summary[0]["MSTF"], 1) and
           near(summary[0]["MSUF"], 0))
        evidence[arm] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "damage": damage, "issued": issued, "removed": removed,
                         "returned": returned, "system_repair_start": surp_start,
                         "system_repair_end": surp_end, "ready": ready,
                         "system_repair_hours": exposure,
                         "terminal_ready": system[-1]["NSYRY"], "summary": summary[0]}
    ck("matched_damage", evidence["explicit"]["damage"] == evidence["fallback"]["damage"])
    ck("repair_exposure_delta", near(evidence["fallback"]["system_repair_hours"] -
                                     evidence["explicit"]["system_repair_hours"], 1.5))
    result = {"schema": "simlox-h02-var04-item-replacement-fallback-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "one_fixed_seed_damage_replacement_priority_and_ordinary_item_replacement_fallback",
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
