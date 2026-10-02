"""Replay the frozen two-LRU PROB control and eight seeded native ledgers."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ARMS = ["control", *(f"seed-{i}" for i in range(1, 9))]
RUNS = {arm: HERE / "runs" / f"h02-var02-{arm.replace('-', '')}-v100-ssh-20261002-01" for arm in ARMS}
PARENT = HERE.parent / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
QUANTITY = HERE.parent / "G01-var05-qty-two-v1.0.0/native-input.json"
INSTALL = {"manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
OBSERVED = {
    "control": [[], [], []],
    "seed-1": [[2, 3], [4, 5], [6]],
    "seed-2": [[2], [3, 4], []],
    "seed-3": [[2], [3], [4]],
    "seed-4": [[2, 3], [], [4, 5]],
    "seed-5": [[2], [3], [4]],
    "seed-6": [[2], [3, 4], []],
    "seed-7": [[2, 3], [4], [5]],
    "seed-8": [[], [2, 3], [4]],
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(actual: object, expected: float, tol: float = 1e-3) -> bool:
    return isinstance(actual, (float, int)) and math.isclose(float(actual), expected, rel_tol=0, abs_tol=tol)


def rows(report: dict, name: str) -> list[dict]:
    table, = [t for t in report["report"]["tables"] if t["name"] == name]
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def matches(log: str, pattern: str) -> list[tuple[float, int]]:
    return [(float(t), int(i)) for t, i in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}
    def ck(name: str, condition: bool) -> None:
        assert name not in checks
        checks[name] = bool(condition)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    sources = {arm: HERE / ("control-input.json" if arm == "control" else f"{arm}-input.json") for arm in ARMS}
    expected = {"control": contract["sources_sha256"]["control"],
                **{f"seed-{i}": contract["sources_sha256"][str(i)] for i in range(1, 9)}}
    ck("frozen_sources", sha(HERE / "contract.json") ==
       "db6713f6d58677736184483627403793c137ef08fdd8ec8b09ba8e0594a567ef" and
       sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"] and
       sha(QUANTITY) == contract["quantity_reference"]["sha256"] == diff["quantity_reference_sha256"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       contract["preselected_seeds"] == diff["preselected_seeds"] == list(range(1, 9)) and
       all(sha(path) == expected[arm] for arm, path in sources.items()))
    ck("exact_delta", diff["parent_to_control_changed_tables"] ==
       ["DamageItem", "ItemStructure", "ProblemDescription", "StockAllocation"] and
       all(diff["arms"][str(i)]["sha256"] == expected[f"seed-{i}"] and
           diff["arms"][str(i)]["changed_tables"] ==
           (["DamageItem", "ProblemDescription"] if i == 1 else
            ["Control", "DamageItem", "ProblemDescription"]) and
           diff["arms"][str(i)]["damage_probability_after"] == .5 and
           diff["arms"][str(i)]["seed_after"] == str(i) for i in range(1, 9)))
    ck("installed_sources", sha(INSTALL["manual"]) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(INSTALL["dictionary"]) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(INSTALL["simlox_exe"]) == contract["installed_source_sha256"]["simlox_exe"])
    authored = {arm: populated(parse_native(path)) for arm, path in sources.items()}
    ck("authored_tables", all(len(tables) == 24 for tables in authored.values()))

    evidence = {}
    for arm, run in RUNS.items():
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        hashes = closure["source_hashes_before"]
        ck(f"{arm}.closure", invocation["variant"] == arm and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["error"] is None and hashes == closure["source_hashes_after"] and
           hashes["input"] == sha(run / "input.json") == expected[arm] and
           hashes["parent"] == sha(PARENT) and hashes["quantity_reference"] == sha(QUANTITY) and
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
           roundtrip["variant"] == arm and len(roundtrip["populated_tables"]) == 24 and
           all(exported.get(name) == values for name, values in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 2" in converter and
           "warning #108" in converter and "warning #2053" in converter and
           (run / "model.sxo").stat().st_size > 4)

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = matches(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*?,0,0,(\d+)> mission starting, duration: 2")
        damage = [(float(t), [int(i) for i in re.findall(r"<TEACH-LRU-01,0,(\d+)>", suffix)])
                  for t, suffix in re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: ([^\n]*)", log)]
        aborts = matches(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*?,0,0,(\d+)> mission aborted:")
        successes = matches(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*?,0,0,(\d+)> mission completed:")
        issued = matches(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
        removed = matches(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>[^\n]*damaged")
        returned = matches(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
        task_starts = matches(log, r"Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> started")
        task_ends = matches(log, r"Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> completed")
        item_starts = matches(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> starts performing, planned to last for 1 hours")
        item_ends = matches(log, r"Time: ([\d.]+)  item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
        actual = [ids for _, ids in damage]
        wanted = OBSERVED[arm]
        item_count = sum(map(len, wanted))
        affected = sum(bool(ids) for ids in wanted)
        flattened = [i for group in wanted for i in group]
        ck(f"{arm}.physical_events", starts == [(8., 0), (20., 1), (32., 2)] and
           actual == wanted and len(damage) == 3 and
           all(len(ids) == len(set(ids)) <= 2 and start < time < start + 2
               for (start, _), (time, ids) in zip(starts, damage)) and
           len(set(flattened)) == item_count and
           len(aborts) == affected and len(successes) == 3 - affected and
           [i for _, i in aborts] == [j for j, ids in enumerate(wanted) if ids] and
           [i for _, i in successes] == [j for j, ids in enumerate(wanted) if not ids] and
           all(near(aborts[k][0], damage[i][0]) for k, (i, ids) in enumerate(
               (pair for pair in enumerate(wanted) if pair[1]))) and
           not any(word in log for word in ("random failure added", "CM failure mode added", "subject to attrition")))
        ck(f"{arm}.stock_cycle", len(issued) == len(removed) == len(returned) == item_count and
           [i for _, i in removed] == flattened and
           Counter(i for _, i in returned) == Counter(flattened) and
           len(set(i for _, i in issued)) == item_count and
           all(issued[k][0] <= removed[k][0] < next(t for t, i in returned if i == removed[k][1]) < 36
               for k in range(item_count)) and "discard" not in log.lower())
        ck(f"{arm}.tasks", len(task_starts) == len(task_ends) ==
           len(item_starts) == len(item_ends) == item_count and
           Counter(i for _, i in task_starts) == Counter(i for _, i in task_ends) and
           Counter(i for _, i in item_ends) == Counter(flattened) and
           all(near(next(t for t, j in task_ends if j == i) - t, .5)
               for t, i in task_starts) and
           all(near(next(t for t, j in item_ends if j == i) - t, 1)
               for t, i in item_starts))

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
           sum(row["NREPT"] or 0 for row in system) == item_count and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           sum(row["NDD"] or 0 for row in stock) == item_count and
           sum(row["NWT"] or 0 for row in stock) == item_count and
           near(exposure, .5 * affected) and
           all(near(row["NSYLA"], 0) for row in system) and
           all(near(row["NBO"], 0) for row in stock))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1) and
           near(stock[-1]["NBO"], 0) and near(summary[0]["MSTF"], 1) and
           near(summary[0]["MSUF"], (3 - affected) / 3))
        evidence[arm] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "damaged_physical_ids": actual, "replacement_stock_issues": issued,
                         "removed_damaged_items": removed, "repaired_stock_returns": returned,
                         "abort_count": len(aborts), "successful_missions": len(successes),
                         "system_repair_hours": exposure, "terminal_ready": system[-1]["NSYRY"]}
    frequencies = Counter(len(ids) for arm in ARMS[1:] for ids in OBSERVED[arm])
    ck("cohort_distribution", dict(frequencies) == {0: 4, 1: 12, 2: 8} and
       sum(len(ids) for arm in ARMS[1:] for ids in OBSERVED[arm]) == 28)
    result = {"schema": "simlox-h02-var02-two-lru-prob-half-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, ok in checks.items() if not ok],
              "runs": evidence, "raw_seals": 108,
              "cohort_event_consequence_counts": {str(i): frequencies[i] for i in (0, 1, 2)},
              "scope": "one_directly_mounted_two_identical_lru_item_type_and_eight_preselected_seeds",
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
