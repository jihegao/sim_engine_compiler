"""Independent, read-only G03 effective-item replay using Python stdlib only."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
PLAN = {
    "base-control": ("add", "TEACH-AIR-01", "TEACH-LRU-BASE"),
    "add-inherited": ("add", "TEACH-VAR-ADD", "TEACH-LRU-BASE"),
    "add-extra": ("add", "TEACH-VAR-ADD", "TEACH-LRU-ADD"),
    "exclude-base": ("exclude", "TEACH-VAR-EX", None),
}
checks = 0
failures: list[str] = []


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", text))


def tables(path: Path, root: str) -> dict[str, dict]:
    return {table["name"]: table for table in load(path)[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for row in rows(table)]


def event(log: str, hour: str, identity: str, suffix: str) -> bool:
    return f"Time: {hour} <{identity}> {suffix}" in log


def main() -> None:
    contract = load(CASE / "contract.json")
    delta = load(CASE / "exact-diff.json")
    donor = AIR / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
    ck(sha(donor) == contract["parents"]["repair_method"]["sha256"], "accepted D01 donor sha")
    donor_tables = tables(donor, "model")
    report_tables = {}
    observations = {}
    for variant, (branch, sid, failed_item) in PLAN.items():
        parent = AIR / "G03-base-variant-structure-v1.0.1" / f"{branch}-input.json"
        source = CASE / f"{variant}-input.json"
        ptab, ctab = tables(parent, "model"), tables(source, "model")
        ck(sha(parent) == contract["parents"][branch]["sha256"], f"{variant} accepted G03 parent")
        ck(sha(source) == contract["inputs_sha256"][variant], f"{variant} frozen input")
        ck({name for name in ptab if ptab[name] != ctab[name]} == set(delta[variant]), f"{variant} exact changed-table set")
        for name, pair in delta[variant].items():
            ck(rows(ptab[name]) == pair["parent"] and rows(ctab[name]) == pair["child"], f"{variant} exact {name} rows")
        deployment = records(ctab["SystemDeployment"])
        ck(len(deployment) == 1 and deployment[0]["SID"] == sid and deployment[0]["QTYPS"] == 1, f"{variant} only intended aircraft deployed")
        item_rows = records(ctab["Item"])
        positives = [row for row in item_rows if row["FRT"] == 300000]
        target = "TEACH-LRU-BASE" if variant == "exclude-base" else failed_item
        ck(len(positives) == 1 and positives[0]["IID"] == target and all(row["FRT"] in (0, 300000) for row in item_rows), f"{variant} isolated positive FRT")
        structure = records(ctab["ItemStructure"])
        if variant == "exclude-base":
            ck(any(row["IID"] == target and row["MID"] == sid and row["QTYPM"] == 0 for row in structure), f"{variant} QTYPM zero exclusion")
        if variant in ("add-inherited", "add-extra"):
            ck(any(row["IID"] == "TEACH-LRU-BASE" and row["MID"] == "TEACH-AIR-01" and row["QTYPM"] == 1 for row in structure), f"{variant} base inheritance source")
            ck(any(row["IID"] == "TEACH-LRU-ADD" and row["MID"] == sid and row["QTYPM"] == 1 for row in structure), f"{variant} added item source")
        ck(records(ctab["OperationProfile"])[1:] == records(donor_tables["OperationProfile"])[1:], f"{variant} donor schedule")
        ck(all(row["SURPT"] == .5 for row in records(ctab["SystemRepair"])), f"{variant} system repair half hour")
        ck(records(ctab["ItemRepair"])[0]["IID"] == target and records(ctab["ItemRepair"])[0]["DIRPT"] == 1, f"{variant} item repair one hour")
        ck(records(ctab["StockAllocation"])[0]["IID"] == target and records(ctab["StockAllocation"])[0]["STSIZ"] == 1, f"{variant} one local spare")
        run = CASE / "runs" / f"g03-effective-{variant}-v100-20261001-01"
        invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
        ck(closure["run_id"] == invocation["run_id"] == run.name and closure["error"] is None, f"{variant} run identity")
        ck(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation seal")
        ck(invocation["input_sha256"] == sha(source) == sha(run / "input.json"), f"{variant} input copied")
        ck(invocation["parent_sha256"] == sha(parent) and invocation["contract_sha256"] == sha(CASE / "contract.json"), f"{variant} parent/contract seal")
        ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant} session0 ssh")
        ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} mutex")
        ck(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant} GUI")
        ck(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant} source stable")
        pinned = {"input": source, "parent": parent, "repair_method": donor, "contract": CASE / "contract.json",
                  "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
                  "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
                  "runner_script": CASE / "run_native_ssh.ps1"}
        for key, path in pinned.items():
            ck(invocation["source_hashes_before"].get(key) == sha(path), f"{variant} sealed {key}")
        ck(invocation["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", f"{variant} runtime sha")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{variant} raw {name}")
        steps = load(run / "steps.json")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant} five steps")
        for step in steps:
            ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"{variant} step {step['name']}")
        export = tables(run / "roundtrip-raw.json", "model")
        populated = {name for name, table in ctab.items() if rows(table)}
        ck(len(populated) == 18, f"{variant} 18 populated source tables")
        for name in populated:
            ck(name in export and ctab[name]["columns"] == export[name]["columns"] and rows(ctab[name]) == rows(export[name]), f"{variant} exact roundtrip {name}")
        runlog = (run / "run.log").read_text(errors="replace")
        ck("Input conversion completed. Errors: 0" in runlog, f"{variant} zero converter errors")
        ck("warning #108" in runlog and ("warning #2053" in runlog) == (variant != "exclude-base"), f"{variant} warning profile")
        ck((run / "model.sxo").stat().st_size > 100000, f"{variant} valid SXO")
        log = (run / "model.log").read_text(errors="replace")
        for i, hour in enumerate((8, 20, 32)):
            identity = f"BASIC-MISSION,TEACH-UNIT,0,0,{i}"
            ck(event(log, str(hour), identity, f"mission starting, duration: 2 : <{sid},0>"), f"{variant} mission {i} launch")
            ck(event(log, str(hour - 1), identity, f"mission allocates system: <{sid},0>"), f"{variant} mission {i} allocation")
            if i or variant == "exclude-base":
                ck(event(log, str(hour + 2), identity, "mission success:"), f"{variant} mission {i} success")
        ck(event(log, "34", "TEACH-UNIT at <BASE-01,0>", f"systems ready: 1 :<{sid},0>"), f"{variant} terminal ready")
        if failed_item is None:
            ck("critical random failure added" not in log and "subitem failed:" not in log and "Start repair of item" not in log, f"{variant} no failure/repair")
            finite_clocks = [line for line in log.splitlines() if "Next random failure will occur" in line and "1e+010" not in line]
            ck(not finite_clocks, f"{variant} no finite next-failure clock")
            ck("Take replacement item" not in log and "Item demand arrives" not in log, f"{variant} zero replacement demand")
            ck(all(event(log, str(hour + 2), f"BASIC-MISSION,TEACH-UNIT,0,0,{i}", "mission success:") for i, hour in enumerate((8, 20, 32))), f"{variant} three successes")
        else:
            ck(event(log, "9.8829", f"{sid},0", "critical random failure added"), f"{variant} failure at 9.8829")
            ck(f"subitem failed: <{failed_item},0,1>" in log, f"{variant} failed item identity")
            ck(event(log, "9.8829", "BASIC-MISSION,TEACH-UNIT,0,0,0", "mission aborted:"), f"{variant} first mission abort")
            ck(event(log, "10", f"{failed_item},0,BASE-01,0", f"Take replacement item <{failed_item},0,0> from stock"), f"{variant} spare taken")
            ck(event(log, "10.25", f"{failed_item},0,BASE-01,0", f"Start repair of item <{failed_item},0,1>"), f"{variant} repair start")
            ck(event(log, "11.25", f"{failed_item},0,BASE-01,0", f"Finished repair of item <{failed_item},0,1>"), f"{variant} repair end")
            ck(event(log, "11.25", f"{failed_item},0,BASE-01,0", f"Put back replacement item <{failed_item},0,1> to stock"), f"{variant} spare restored")
            ck(event(log, "10.5", "TEACH-UNIT at <BASE-01,0>", f"systems ready: 1 :<{sid},0>"), f"{variant} system ready after repair")
        report = tables(run / "report-raw.json", "report")
        report_tables[variant] = report
        ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{variant} report tables")
        summary = records(report["ResultSummary"])
        ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36 and
           all(summary[0][metric] == 1 for metric in ("MTMF", "MSTF", "STMF")) and
           abs(summary[0]["MSUF"] - (1 if failed_item is None else 2 / 3)) < 1e-6, f"{variant} factors")
        sys = records(report["SystemResults"])
        stock = records(report["StockTotalResults"])
        ck(len(sys) == len(stock) == 72, f"{variant} 72 report bins")
        for i, (sr, st) in enumerate(zip(sys, stock)):
            h = i / 2
            prep = int(7 <= h < 8 or 19 <= h < 20 or 31 <= h < 32)
            mission = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
            repair = int(failed_item is not None and h == 10)
            ready = int(not (prep or mission or repair))
            ck((sr["STINT"], sr["ETINT"], st["STINT"], st["ETINT"]) == (h, h + .5, h, h + .5), f"{variant} bin time {i}")
            ck((sr["NSYRY"], sr["NSYMA"], sr["NSYMR"], sr["NSYMO"], sr["NSYUA"], sr["NSYRP"], sr["NSYA"], sr["FTMO"], sr["STACC"]) ==
               (ready, prep + mission, prep, mission, repair, repair, 1 - repair, mission, mission), f"{variant} system ledger {i}")
            ck(sr["NFAIL"] == int(failed_item is not None and h == 9.5) and sr["NREPT"] == int(failed_item is not None and h == 10.5), f"{variant} failure/repair bins {i}")
            ck((sr["SYDT"], sr["NSYDT"]) == ((.5, 1) if repair else (None, 0)), f"{variant} downtime bins {i}")
            ck(st["PNB"] == 1 and st["NDF"] == int(repair) and st["NWT"] == int(repair) and st["NBO"] == 0, f"{variant} stock bins {i}")
        ck(sys[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1, f"{variant} terminal report")
        observations[variant] = {"deployed_sid": sid, "failed_item": failed_item,
                                 "failure_hour": 9.8829 if failed_item else None,
                                 "mission_success_factor": summary[0]["MSUF"]}
    for other in ("add-inherited", "add-extra"):
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            ck(records(report_tables["base-control"][name]) == records(report_tables[other][name]), f"positive pair {other} {name} equality")
    output = {
        "schema": "simlox-g03-effective-item-independent-review/v1", "passed": not failures,
        "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
        "failure_count": len(failures), "failures": failures, "observations": observations,
        "scope": "One fixed seed, three scheduled missions, traditional LRU failure/repair, BSID base/add/exclude variants.",
        "limits": ["The exclusion branch's no-finite-clock and no-failure result is a bounded native contrast, not a proof for other stochastic paths.",
                   "No GUI rendering, cross-engine parity, or general failure-rate aggregation claim."],
    }
    OUT.write_bytes((json.dumps(output, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": output["passed"], "checks": checks, "failures": failures, "result": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
