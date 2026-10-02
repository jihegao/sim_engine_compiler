"""Replay all eight source-sealed REPF0.5 seed realizations."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var03-repf-zero-v1.0.0/repairable-input.json"
INSTALL = {"manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
           "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
           "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json",
       "model.log", "import.log", "export.log", "run.log", "report-export.log",
       "roundtrip-validation.json", "steps.json"}
EXPECTED = {
    1: ((1, 2), (), (1, 2), (0,), (), 2, 1, 1, 0, 0),
    2: ((1, 2, 3), (1, 2, 3), (), (0, 1, 2), (1, 2, 3), 3, 0, 0, 0, 1),
    3: ((1, 2, 3), (2,), (1, 3), (0,), (), 3, 0, 2, 1, 0),
    4: ((1, 2, 3), (1, 2, 3), (), (0, 1, 2), (1, 2, 3), 3, 0, 0, 0, 1),
    5: ((1, 2, 3), (2,), (1, 3), (0,), (), 3, 0, 2, 1, 0),
    6: ((1, 2, 3), (1, 2, 3), (), (0, 1, 2), (1, 2, 3), 3, 0, 0, 0, 1),
    7: ((1, 2, 3), (1, 3), (2,), (0, 1), (1,), 3, 0, 1, 1, 1),
    8: ((1, 2, 3), (2,), (1, 3), (0,), (), 3, 0, 2, 1, 0),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def near(actual: object, target: float, tol: float = 1e-4) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(float(actual), target, abs_tol=tol)


def rows(report: dict, name: str) -> list[dict]:
    table, = [x for x in report["report"]["tables"] if x["name"] == name]
    columns = [x["name"] for x in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def events(log: str, pattern: str) -> list[tuple[float, int]]:
    return [(float(t), int(i)) for t, i in re.findall(pattern, log)]


def times(log: str, pattern: str) -> list[float]:
    return [float(t) for t in re.findall(pattern, log)]


def main() -> None:
    checks: dict[str, bool] = {}

    def ck(name: str, condition: bool) -> None:
        assert name not in checks
        checks[name] = bool(condition)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    ck("parent_and_contract", sha(PARENT) == contract["direct_parent"]["sha256"] ==
       diff["parent_sha256"] and sha(HERE / "contract.json") ==
       "fdb65b278859e73325d740552ccb644e683ca9ae0e586f355fd179da261bff3e" and
       sha(HERE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"] and
       contract["preselected_seeds"] == diff["preselected_seeds"] == list(range(1, 9)))
    ck("installed_sources", sha(INSTALL["manual"]) == contract["installed_source_sha256"]["manual_pdf"] and
       sha(INSTALL["dictionary"]) == contract["installed_source_sha256"]["table_dictionary"] and
       sha(INSTALL["simlox_exe"]) == contract["installed_source_sha256"]["simlox_exe"])
    evidence = {}
    repair_routes = discard_routes = 0
    for seed in range(1, 9):
        name = f"seed-{seed}"
        source = HERE / f"{name}-input.json"
        run = HERE / f"runs/h02-var03-half-seed{seed}-v100-ssh-20261002-02"
        invocation, closure, steps = (load(run / file) for file in
                                      ("invocation.json", "closure.json", "steps.json"))
        expected = EXPECTED[seed]
        source_hash = contract["sources_sha256"][str(seed)]
        ck(f"{name}.source", sha(source) == source_hash == diff["arms"][str(seed)]["input_sha256"] and
           diff["arms"][str(seed)]["values"] == {"REPF_before": 1.0, "REPF_after": .5,
                                                    "RSEED_before": "1", "RSEED_after": str(seed)} and
           diff["arms"][str(seed)]["changed_tables"] ==
           (["DamageItem", "ProblemDescription"] if seed == 1 else
            ["Control", "DamageItem", "ProblemDescription"]) and
           len(populated(parse_native(source))) == 24)
        hashes = closure["source_hashes_before"]
        ck(f"{name}.closure", invocation["variant"] == name and
           invocation["run_id"] == closure["run_id"] == run.name and
           closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["error"] is None and hashes == closure["source_hashes_after"] ==
           invocation["source_hashes_before"] and sha(run / "input.json") == source_hash and
           hashes["input"] == source_hash and hashes["parent"] == sha(PARENT) and
           hashes["contract"] == sha(HERE / "contract.json") and
           hashes["builder"] == sha(HERE / "build.py") and
           hashes["exact_diff"] == sha(HERE / "exact-diff.json") and
           hashes["diff_checker"] == sha(HERE / "describe_diff.py") and
           hashes["checker"] == sha(HERE / "check_roundtrip.py") and
           hashes["runner_script"] == sha(HERE / "run_native_ssh.ps1") and
           all(hashes[k] == sha(path) for k, path in INSTALL.items()))
        ck(f"{name}.guard", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
           [x["name"] for x in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(x["status"] == ("calc_observed" if x["name"] == "calc" else "completed") and
               x["exit_code"] == 0 and x["gui_preserved"] for x in steps))
        ck(f"{name}.raw_seals", set(closure["raw"]) == RAW and all(
           (run / file).stat().st_size == seal["bytes"] and sha(run / file) == seal["sha256"]
           for file, seal in closure["raw"].items()))
        roundtrip = load(run / "roundtrip-validation.json")
        authored = populated(parse_native(source))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{name}.roundtrip", roundtrip["passed"] and not roundtrip["differences"] and
           roundtrip["variant"] == name and len(roundtrip["populated_tables"]) == 24 and
           all(exported.get(table) == values for table, values in authored.items()))
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{name}.conversion", "Input conversion completed. Errors: 0, Warnings: 2" in converter and
           "warning #108" in converter and "warning #2053" in converter and
           (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        starts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission starting, duration: 2")
        aborts = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission aborted:")
        cancels = times(log, r"Time: ([\d.]+) <BASIC-MISSION[^\n]*mission cancelled:")
        damage = events(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
        removed = events(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>[^\n]*damaged")
        repaired = events(log, r"Time: ([\d.]+)  item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
        discarded = events(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item discarded: <TEACH-LRU-01,0,(\d+)>")
        issued = events(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
        returned = events(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
        boadd = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder added")
        boremove = times(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was")
        surp_end = times(log, r"Time: ([\d.]+)  system SURP task \d+ on <TEACH-AIR-01,0> completed")
        ready = times(log, r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>")
        expected_damage, expected_repair, expected_discard, expected_issue, expected_return, \
            expected_starts, expected_cancels, expected_boadd, expected_boremove, expected_ready = expected
        ck(f"{name}.event_identification", tuple(i for _, i in damage) == expected_damage and
           tuple(i for _, i in removed) == expected_damage and
           tuple(i for _, i in repaired) == expected_repair and
           tuple(i for _, i in discarded) == expected_discard and
           tuple(i for _, i in issued) == expected_issue and
           tuple(i for _, i in returned) == expected_return and
           set(expected_repair).isdisjoint(expected_discard) and
           set(expected_repair) | set(expected_discard) == set(expected_damage))
        ck(f"{name}.event_timing", starts == [8, 20, 32][:expected_starts] and
           len(aborts) == len(damage) == expected_starts and len(cancels) == expected_cancels and
           len(boadd) == expected_boadd and len(boremove) == expected_boremove and
           len(surp_end) == len(ready) == expected_starts - expected_boadd + expected_boremove and
           all(starts[j] < damage[j][0] < starts[j] + 2 and near(aborts[j], damage[j][0]) and
               removed[j][0] > damage[j][0] for j in range(len(damage))) and
           all(next(t for t, i in removed if i == item) <= t for t, item in repaired + discarded) and
           len(repaired) == len(returned) + len(boremove) and
           not any(word in log for word in ("random failure added", "CM failure mode added", "subject to attrition")))
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, table) for table in
                                  ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(f"{name}.report_shape", len(summary) == 1 and len(system) == len(stock) == 72 and
           all(near(system[j]["STINT"], j * .5) and near(system[j]["ETINT"], (j + 1) * .5) and
               near(stock[j]["STINT"], j * .5) and near(stock[j]["ETINT"], (j + 1) * .5)
               for j in range(72)))
        ck(f"{name}.state_partition", all(
           near(sum(row[k] or 0 for k in ("NSYA", "NSYUA", "NSYLA")), 1) and
           near(sum(row[k] or 0 for k in ("NSYRY", "NSYMA", "NSYUA", "NSYLA")), 1)
           for row in system))
        ck(f"{name}.report_events", sum(row["NDAM"] or 0 for row in system) == len(damage) and
           sum(row["NREPT"] or 0 for row in system) == len(surp_end) and
           sum(row["NFAIL"] or 0 for row in system) == 0 and
           sum(row["NDD"] or 0 for row in stock) == len(damage) and
           sum(row["NWT"] or 0 for row in stock) == len(surp_end) and
           all(near(row["NSYLA"], 0) for row in system))
        ck(f"{name}.terminal", near(system[-1]["NSYRY"], expected_ready) and
           near(system[-1]["NSYUA"], 1 - expected_ready) and
           near(stock[-1]["NBO"], 1 - expected_ready) and
           near(stock[-1]["PNB"], expected_ready) and
           near(summary[0]["MSTF"], expected_starts / 3) and
           near(summary[0]["MSUF"], 0) and
           (any((row["NBO"] or 0) > 0 for row in stock) == bool(boadd)))
        repair_routes += len(repaired)
        discard_routes += len(discarded)
        evidence[str(seed)] = {
            "run_id": run.name, "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
            "damage": damage, "repaired": repaired, "discarded": discarded,
            "issued": issued, "stock_return": returned, "backorder_added": boadd,
            "backorder_removed": boremove, "mission_starts": starts,
            "mission_aborts": aborts, "mission_cancellations": cancels,
            "terminal_ready": system[-1]["NSYRY"], "terminal_backorder": stock[-1]["NBO"],
            "terminal_nominal_stock": stock[-1]["PNB"], "summary": summary[0]}
    ck("both_routes_observed", repair_routes > 0 and discard_routes > 0 and
       evidence["7"]["repaired"] and evidence["7"]["discarded"])
    diagnostic = {}
    for seed in range(1, 5):
        run = HERE / f"runs/h02-var03-half-seed{seed}-v100-ssh-20261002-01"
        closure = load(run / "closure.json")
        ck(f"seed-{seed}.excluded_diagnostic", closure["error"] == "roundtrip checker exit=1" and
           closure["source_hashes_before"]["checker"] ==
           "94959653600cf886d04d13e2b3dea48cf88c4b07f3669ffc22f94478e51cbbaa" and
           closure["source_hashes_before"]["runner_script"] ==
           "ef1f27fb69a5351fd519f0e29c32d6caed4501ae7afafe3bf33cb44e0c9ba7b2" and
           "roundtrip-validation.json" not in closure["raw"])
        diagnostic[str(seed)] = {"run_id": run.name, "closure_sha256": sha(run / "closure.json"),
                                 "error": closure["error"]}
    result = {"schema": "simlox-h02-var03-repf-half-seeds-v100-author-validation/v1",
              "passed": all(checks.values()), "checks": len(checks),
              "differences": [name for name, passed in checks.items() if not passed],
              "accepted_runs": evidence, "excluded_diagnostics": diagnostic,
              "accepted_raw_seals": 96, "observed_repair_events": repair_routes,
              "observed_discard_events": discard_routes,
              "scope": "eight_preselected_fixed_seed_repf_half_realizations_no_population_estimate",
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
