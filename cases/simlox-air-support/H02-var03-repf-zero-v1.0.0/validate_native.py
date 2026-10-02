"""Replay sealed native evidence for the REPF=1 versus REPF=0 pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {arm: HERE / f"runs/h02-var03-{label}-v100-ssh-20261002-01"
        for arm, label in (("repairable", "repairable"), ("discard", "discard"))}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
       "report-raw.json", "model.log", "import.log", "export.log", "run.log",
       "report-export.log", "roundtrip-validation.json", "steps.json"}
INSTALL = {"manual_pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "table_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(actual: object, expected: float, tol: float = 1e-4) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(float(actual), expected, abs_tol=tol)


def rows(report: dict, name: str) -> list[dict]:
    table, = [t for t in report["report"]["tables"] if t["name"] == name]
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(pattern, log)]


def ids(log: str, pattern: str) -> list[tuple[float, int]]:
    return [(float(t), int(i)) for t, i in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, value: bool) -> None:
        assert name not in checks
        checks[name] = bool(value)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent = HERE.parent / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
    source = {arm: HERE / f"{arm}-input.json" for arm in RUNS}
    ck("source_lineage", sha(parent) == contract["direct_parent"]["sha256"] ==
       sha(source["repairable"]) == contract["sources_sha256"]["repairable"] and
       sha(source["discard"]) == contract["sources_sha256"]["discard"] and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       sha(HERE / "contract.json") == "b05af36a42081a94c78d366d918ee9199c2b6996767f4b18b750b2d06ec06579")
    ck("installed_sources", all(sha(INSTALL[key]) == contract["installed_source_sha256"][key]
                                for key in INSTALL))
    ck("exact_delta", diff["repairable_sha256"] == sha(source["repairable"]) and
       diff["discard_sha256"] == sha(source["discard"]) and
       diff["parent_sha256"] == sha(parent) and not diff["added_tables"] and
       not diff["removed_tables"] and set(diff["changed_tables"]) ==
       {"DamageItem", "ProblemDescription"} and diff["unchanged_table_count"] == 33 and
       diff["changed_tables"]["DamageItem"]["before"]["instances"][0]["rows"][0][4] == 1 and
       diff["changed_tables"]["DamageItem"]["after"]["instances"][0]["rows"][0][4] == 0)
    authored = {arm: populated(parse_native(path)) for arm, path in source.items()}
    ck("authored_table_count", all(len(tables) == 24 for tables in authored.values()))
    evidence, ledger = {}, {}
    for arm, run in RUNS.items():
        invocation, closure, steps = (load(run / name) for name in
                                      ("invocation.json", "closure.json", "steps.json"))
        hashes = closure["source_hashes_before"]
        ck(f"{arm}.source_closure", sha(run / "input.json") == sha(source[arm]) and
           invocation["variant"] == arm and invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           hashes == closure["source_hashes_after"] == invocation["source_hashes_before"] and
           hashes["input"] == sha(source[arm]) and hashes["parent"] == sha(parent) and
           hashes["contract"] == sha(HERE / "contract.json") and
           hashes["builder"] == sha(HERE / "build.py") and
           hashes["exact_diff"] == sha(HERE / "exact-diff.json") and
           hashes["diff_checker"] == sha(HERE / "describe_diff.py") and
           hashes["checker"] == sha(HERE / "check_roundtrip.py") and
           hashes["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
           hashes["manual"] == sha(INSTALL["manual_pdf"]) and
           hashes["dictionary"] == sha(INSTALL["table_dictionary"]) and
           hashes["simlox_exe"] == sha(INSTALL["simlox_exe"]) and
           closure["error"] is None)
        ck(f"{arm}.session_and_gui", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm}.five_steps", [x["name"] for x in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(x["status"] == ("calc_observed" if x["name"] == "calc" else "completed") and
               x["exit_code"] == 0 and x["gui_preserved"] for x in steps))
        ck(f"{arm}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
           for name, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{arm}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           all(exported.get(name) == values for name, values in authored[arm].items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm}.conversion", "Input conversion completed. Errors: 0, Warnings: 2" in converter and
           "warning #108" in converter and "warning #2053" in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        successes = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission success:")
        cancellations = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission cancelled:")
        damage = ids(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
        issued = ids(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
        returned = ids(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
        removed = ids(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>[^\n]*damaged")
        discarded = ids(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item discarded: <TEACH-LRU-01,0,(\d+)>")
        item_repair = times(log, r"Time: ([\d.]+)  item DIRP task \d+ on <TEACH-LRU-01,0,\d+> completed")
        ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
        surp_end = times(log, r"Time: ([\d.]+)  system SURP task \d+ on <TEACH-AIR-01,0> completed")
        backorder = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder added")
        ck(f"{arm}.no_random_failure_or_attrition", "random failure added" not in log and
           "CM failure mode added" not in log and "subject to attrition" not in log)
        if arm == "repairable":
            ck("repairable.event_path", starts == [8, 20, 32] and not successes and not cancellations and
               len(aborts) == len(damage) == len(issued) == len(removed) == len(returned) ==
               len(item_repair) == len(ready) == len(surp_end) == 3 and
               [i for _, i in damage] == [1, 2, 3] and [i for _, i in issued] == [0, 1, 2] and
               [i for _, i in removed] == [1, 2, 3] and [i for _, i in returned] == [1, 2, 3] and
               not discarded and not backorder and all(near(aborts[i], damage[i][0]) and
               damage[i][0] < issued[i][0] <= removed[i][0] < returned[i][0] for i in range(3)))
        else:
            ck("discard.event_path", starts == [8, 20] and not successes and len(aborts) == 2 and
               len(cancellations) == 1 and near(cancellations[0], 32.3333) and
               [i for _, i in damage] == [1, 2] and [i for _, i in issued] == [0] and
               [i for _, i in removed] == [1, 2] and [i for _, i in discarded] == [1, 2] and
               not returned and not item_repair and len(ready) == len(surp_end) == len(backorder) == 1 and
               near(backorder[0], 20.393, 1e-3) and
               all(near(discarded[i][0], removed[i][0]) for i in range(2)) and
               damage[0][0] < issued[0][0] <= removed[0][0] < ready[0] < 20 and
               damage[1][0] < backorder[0] < removed[1][0] < cancellations[0] and
               "wait for subitem" in log)
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, name) for name in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{arm}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[i]["STINT"], i * .5) and near(system[i]["ETINT"], (i + 1) * .5) and
               near(stock[i]["STINT"], i * .5) and near(stock[i]["ETINT"], (i + 1) * .5)
               for i in range(72)))
        ck(f"{arm}.state_partition", all(
           near(sum(row[k] or 0 for k in ("NSYA", "NSYUA", "NSYLA")), 1) and
           near(sum(row[k] or 0 for k in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1)
           for row in system))
        n = 3 if arm == "repairable" else 2
        ck(f"{arm}.event_bins", sum(row["NDAM"] or 0 for row in system) == n and
           sum(row["NREPT"] or 0 for row in system) == (3 if arm == "repairable" else 1) and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           sum(row["NDD"] or 0 for row in stock) == n and
           sum(row["NWT"] or 0 for row in stock) == (3 if arm == "repairable" else 1) and
           all(near(row["NSYLA"], 0) for row in system))
        ck(f"{arm}.terminal", near(system[-1]["NSYRY"], 1 if arm == "repairable" else 0) and
           near(system[-1]["NSYUA"], 0 if arm == "repairable" else 1) and
           near(stock[-1]["PNB"], 1 if arm == "repairable" else 0) and
           near(stock[-1]["NBO"], 0 if arm == "repairable" else 1) and
           near(summary[0]["MSTF"], 1 if arm == "repairable" else 2/3) and
           near(summary[0]["MSUF"], 0))
        ledger[arm] = {"summary": summary[0], "system": system, "stock": stock}
        evidence[arm] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "report_sha256": sha(run / "report-raw.json"),
                         "starts": starts, "aborts": aborts, "cancellations": cancellations,
                         "damage": damage, "issued": issued, "removed": removed,
                         "returned": returned, "discarded": discarded, "backorder": backorder,
                         "operating_hours": .5 * sum(row["NSYMO"] or 0 for row in system),
                         "system_repair_hours": .5 * sum(row["NSYRP"] or 0 for row in system),
                         "terminal_ready": system[-1]["NSYRY"], "terminal_backorder": stock[-1]["NBO"],
                         "summary": summary[0]}
    ck("paired_contrast", near(ledger["repairable"]["stock"][-1]["PNB"], 1) and
       near(ledger["discard"]["stock"][-1]["PNB"], 0) and
       near(ledger["repairable"]["system"][-1]["NSYRY"], 1) and
       near(ledger["discard"]["system"][-1]["NSYRY"], 0))
    result = {"schema": "simlox-h02-var03-repf-zero-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "runs": evidence, "raw_seals": 24, "scope": "one_seed_repf_endpoint_pair",
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
