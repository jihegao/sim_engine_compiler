"""Replay sealed same-position two-FM damage and concurrent CM evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H03-var01-position-fm-damage-v1.0.0/mode-input.json"
RUNS = {arm: HERE / "runs" / f"h03-var02-{arm}-v100-ssh-20261002-01"
        for arm in ("control", "two-mode")}
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
    return isinstance(actual, (float, int)) and math.isclose(
        float(actual), target, rel_tol=0, abs_tol=tolerance)


def rows(report: dict, name: str) -> list[dict]:
    table, = [t for t in report["report"]["tables"] if t["name"] == name]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(t) for t in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}
    def ck(name: str, value: bool) -> None:
        assert name not in checks
        checks[name] = bool(value)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("frozen_sources", sha(HERE / "contract.json") ==
       "82c941aff7e5cc2e80ea5c41886296eae7850b1294c2fbb2a9c64a950ee3900a" and
       sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       all(sha(path) == contract["sources_sha256"][arm.replace("-", "_")] ==
           diff[f"{arm.replace('-', '_')}_sha256"] for arm, path in sources.items()))
    changed = diff["changed_tables"]
    added_fm = changed["FailureMode"]["after"]["instances"][0]["rows"][-1]
    added_cm = changed["CMLocation"]["after"]["instances"][0]["rows"][-1]
    added_damage = changed["DamageFailureMode"]["after"]["instances"][0]["rows"][-1]
    ck("exact_delta", sha(PARENT) == sha(sources["control"]) and
       not diff["added_tables"] and not diff["removed_tables"] and
       set(changed) == {"FailureMode", "CMLocation", "DamageFailureMode", "ProblemDescription"} and
       added_fm[:6] == ["FM-POS-B", "Second position A direct repair", "POS-A", 1e-9, "OPHOURS", 1.0] and
       added_cm[:4] == ["FM-POS-B", "TEACH-AIR-01", "BASE-01", 1.0] and
       added_damage[:4] == ["BATTLE-HIT", "TEACH-AIR-01", "FM-POS-B", 1])
    ck("installed_sources", sha(INSTALL["manual"]) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(INSTALL["dictionary"]) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(INSTALL["simlox_exe"]) == contract["installed_source_sha256"]["simlox_exe"])
    authored = {arm: populated(parse_native(path)) for arm, path in sources.items()}
    ck("authored_tables", all(len(tables) == 21 for tables in authored.values()))
    evidence = {}
    for arm, run in RUNS.items():
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        hashes = closure["source_hashes_before"]
        ck(f"{arm}.closure", invocation["variant"] == arm and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["error"] is None and hashes == closure["source_hashes_after"] and
           hashes["input"] == sha(run / "input.json") == sha(sources[arm]) and
           hashes["parent"] == sha(PARENT) and
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
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == 21 and
           all(exported.get(name) == values for name, values in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 1" in converter and
           "warning #108" in converter and "warning #242" not in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        damage = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: ")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        success = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission completed: <TEACH-AIR-01,0>")
        fm = re.findall(r"Failure Mode: (FM-POS-[AB]) on materiel: <POS-A,0>", log)
        cm_starts = [(float(t), int(i)) for t, i in re.findall(
            r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> started", log)]
        cm_ends = [(float(t), int(i)) for t, i in re.findall(
            r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> completed", log)]
        cm_modes = [(float(t), int(i), m) for t, i, m in re.findall(
            r"Time: ([\d.]+)  system CM task (\d+) on <TEACH-AIR-01,0> FMID: (FM-POS-[AB])", log)]
        ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
        ck(f"{arm}.events", starts == [8, 20, 32] and len(damage) == 3 and
           all(starts[i] < damage[i] < starts[i] + 2 for i in range(3)) and
           "random failure added" not in log and "subject to attrition" not in log and
           "Damaged items: <" not in log and "system SURP task" not in log)
        ck(f"{arm}.mission", len(aborts) == len(damage) == 3 and not success and
           all(near(damage[i], aborts[i]) for i in range(3)))
        if arm == "control":
            ck("control.fm_route", fm == ["FM-POS-A"] * 3 and
               [i for _, i in cm_starts] == [0, 1, 2] and
               [i for _, i in cm_ends] == [0, 1, 2] and
               [m for _, _, m in cm_modes] == ["FM-POS-A"] * 3 and
               all(near(cm_ends[i][0] - cm_starts[i][0], .5) and
                   aborts[i] <= cm_starts[i][0] < cm_ends[i][0] and
                   cm_ends[i][0] < (20 if i == 0 else 32 if i == 1 else 36)
                   for i in range(3)) and len(ready) == 3 and
               all(near(ready[i], cm_ends[i][0]) for i in range(3)))
        else:
            ck("two_mode.fm_route", fm == ["FM-POS-A", "FM-POS-B", "FM-POS-B"] * 3 and
               log.count(" 2 failures:") == 3 and
               log.count("System partially repaired <TEACH-AIR-01,0>") == 3 and
               [i for _, i in cm_starts] == list(range(6)) and
               [i for _, i in cm_ends] == list(range(6)) and
               [(i, m) for _, i, m in cm_modes] ==
               [(i, "FM-POS-A" if i % 2 == 0 else "FM-POS-B") for i in range(6)] and
               all(near(cm_starts[2*i][0], cm_starts[2*i+1][0]) and
                   near(cm_ends[2*i][0] - cm_starts[2*i][0], .5) and
                   near(cm_ends[2*i+1][0] - cm_starts[2*i+1][0], 1.0) and
                   aborts[i] <= cm_starts[2*i][0] < cm_ends[2*i][0] < cm_ends[2*i+1][0] and
                   cm_ends[2*i+1][0] < (20 if i == 0 else 32 if i == 1 else 36)
                   for i in range(3)) and len(ready) == 3 and
               all(near(ready[i], cm_ends[2*i+1][0]) for i in range(3)))
        summary, system, stock = (rows(parse_native(run / "report-raw.json"), name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near(sum(row[k] or 0 for k in ("NSYA", "NSYUA", "NSYLA")), 1) and
           near(sum(row[k] or 0 for k in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1)
           for row in system))
        exposure = .5 * sum(row["NSYRP"] or 0 for row in system)
        ck(f"{arm}.report_events", sum(row["NDAM"] or 0 for row in system) == 3 and
           sum(row["NREPT"] or 0 for row in system) == (3 if arm == "control" else 6) and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           near(exposure, 1.5 if arm == "control" else 3.0) and
           all(near(row["NSYLA"], 0) for row in system) and
           all(near(row["NDD"], 0) and near(row["NWT"], 0) and
               near(row["NBO"], 0) and near(row["PNB"], 1) for row in stock))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1) and
           near(system[-1]["NSYUA"], 0) and near(stock[-1]["NBO"], 0) and
           near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 0))
        evidence[arm] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "damage_times": damage, "mission_abort_times": aborts,
                         "cm_starts": cm_starts, "cm_ends": cm_ends, "cm_modes": cm_modes,
                         "system_repair_hours": exposure, "terminal_ready": system[-1]["NSYRY"],
                         "summary": summary[0]}
    result = {"schema": "simlox-h03-var02-two-position-fm-damage-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24,
              "scope": "two_damage_failure_modes_on_one_position_with_concurrent_cm",
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
