"""Independent read-only replay of the sealed A16 configuration run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RUN = CASE / "runs" / "a16-two-config-v100-20261001-01"
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def near(a: float, b: float, tol: float = 1e-5) -> bool:
    return abs(a - b) < tol


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict[str, dict]:
    return {t["name"]: t for t in load(path)[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [r for instance in table["instances"] for r in instance["rows"]]


def records(table: dict) -> list[dict]:
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, r)) for r in rows(table)]


def has(log: str, time: str, suffix: str) -> bool:
    return any(line.startswith(f"Time: {time} ") and suffix in line for line in log.splitlines())


def main() -> None:
    contract = load(CASE / "contract.json")
    exact = load(CASE / "exact-diff.json")
    parent = AIR / "E01-local-spare-explicit-replacement-v1.0.0" / "native-input.json"
    donor = AIR / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
    source = CASE / "native-input.json"
    ck(sha(parent) == contract["parent_sha256"], "accepted E01 parent")
    ck(sha(donor) == contract["schema_donor_sha256"], "accepted A11 donor")
    ck(sha(source) == contract["input_sha256"], "frozen candidate input")
    ptab, ctab, donor_tables = tables(parent, "model"), tables(source, "model"), tables(donor, "model")
    ck({n for n in ptab if ptab[n] != ctab[n]} == set(exact) - {"MissionSystem"}, "exact parent table delta")
    ck(set(ctab) - set(ptab) == {"MissionSystem"}, "only MissionSystem added")
    for name, pair in exact.items():
        if name in ptab:
            ck(rows(ptab[name]) == pair["parent"], f"{name} parent exact rows")
        ck(rows(ctab[name]) == pair["child"], f"{name} child exact rows")
    ck(ctab["MissionSystem"]["columns"] == donor_tables["MissionSystem"]["columns"], "A11 MissionSystem schema")
    systems = records(ctab["System"])
    ck([r["SID"] for r in systems] == ["TEACH-AIR-01", "TEACH-CONF-A", "TEACH-CONF-B"], "three system types")
    ck(all(r["CBSID"] == "TEACH-AIR-01" and r["BSID"] is None for r in systems[1:]), "CBSID not BSID")
    ck(len(records(ctab["SystemDeployment"])) == 1 and records(ctab["SystemDeployment"])[0]["SID"] == "TEACH-AIR-01", "only base deployed")
    structure = records(ctab["ItemStructure"])
    ck([(r["IID"], r["MID"], r["QTYPM"]) for r in structure] ==
       [("TEACH-LRU-01", "TEACH-AIR-01", 1), ("TEACH-LRU-A", "TEACH-CONF-A", 1), ("TEACH-LRU-B", "TEACH-CONF-B", 1)], "base and additive LRUs")
    ck(all(r["FRT"] == 0 for r in records(ctab["Item"])), "zero item FRT")
    stock_source = records(ctab["StockAllocation"])
    ck([(r["IID"], r["STSIZ"]) for r in stock_source] == [("TEACH-LRU-01", 1), ("TEACH-LRU-A", 1), ("TEACH-LRU-B", 1)], "one local spare per LRU")
    missions = records(ctab["MissionSystem"])
    ck([(r["MTID"], r["SID"], r["NOS"], r["MNOS"]) for r in missions] ==
       [("CONF-A-MISSION", "TEACH-CONF-A", 1, 1), ("CONF-B-MISSION", "TEACH-CONF-B", 1, 1), ("BASE-MISSION", "TEACH-AIR-01", 1, 1)], "three explicit requirements")
    ck([(r["SPRID"], r["STIM"]) for r in records(ctab["OperationProfile"])] ==
       [("CONF-A-MISSION", 8), ("CONF-B-MISSION", 20), ("BASE-MISSION", 32)], "three mission schedule")
    breakdown = records(ctab["TaskBreakDown"])
    ck([(r["SUTID"], r["DURN"]) for r in breakdown] == [("<REMOVE>", 1 / 6), ("<REPLACE>", 1 / 3)], "E01 task durations")
    ck(records(ctab["SystemRepair"])[0]["SURPTID"] == "E01-SURP", "base repair task linkage")
    inv, closure = load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None, "run identity")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation sha")
    ck(inv["input_sha256"] == sha(source) == sha(RUN / "input.json"), "copied input sha")
    ck(inv["parent_sha256"] == sha(parent) and inv["contract_sha256"] == sha(CASE / "contract.json"), "parent/contract sha")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "queue mutex")
    ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source stable")
    pinned = {"input": source, "parent": parent, "mission_schema_donor": donor, "contract": CASE / "contract.json",
              "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
              "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
              "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in pinned.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"pinned {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native runtime sha")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw {name}")
    steps = load(RUN / "steps.json")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    exported = tables(RUN / "roundtrip-raw.json", "model")
    populated = {name for name, table in ctab.items() if rows(table)}
    ck(len(populated) == 21, "21 populated source tables")
    for name in populated:
        ck(name in exported and ctab[name]["columns"] == exported[name]["columns"] and rows(ctab[name]) == rows(exported[name]), f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in runlog, "zero conversion errors")
    ck("warning #108" in runlog and runlog.count("warning #2053") == 3, "expected zero-FRT warnings")
    ck((RUN / "model.sxo").stat().st_size > 100000, "valid SXO")
    log = (RUN / "model.log").read_text(errors="replace")
    for at, earlier, later, mission, sid in (
        (7, "TEACH-AIR-01", "TEACH-CONF-A", "CONF-A-MISSION,TEACH-UNIT,0,0,0", "TEACH-CONF-A"),
        (19, "TEACH-CONF-A", "TEACH-CONF-B", "CONF-B-MISSION,TEACH-UNIT,0,0,1", "TEACH-CONF-B"),
        (31, "TEACH-CONF-B", "TEACH-AIR-01", "BASE-MISSION,TEACH-UNIT,0,0,2", "TEACH-AIR-01"),
    ):
        ck(has(log, str(at), f"<{earlier},0> reconfig started, mission: <{mission}>"), f"reconfig starts {at}")
        ck(has(log, "7.33333" if at == 7 else "19.3333" if at == 19 else "31.1667", f"<{earlier},0> reconfig ended, mission: <{mission}>"), f"reconfig ends {at}")
        ck(has(log, str(at + 1), f"<{mission}> mission starting, duration: 2 : <{sid},0>"), f"mission start {at + 1}")
        ck(has(log, str(at + 3), f"<{mission}> mission success:"), f"mission success {at + 3}")
        ck(has(log, str(at + 3), f"systems ready: 1 :<{later},0>"), f"ready as {later}")
    for time, word, duration in (("7", "fit", "0.333333"), ("19", "remove", "0.166667"),
                                 ("19", "fit", "0.333333"), ("31", "remove", "0.166667")):
        ck(has(log, time, f"system reconfig {word} task") and
           has(log, time, f"starts performing, planned to last for {duration} hours"), f"{word} task at {time}")
    ck(has(log, "19.1667", "system reconfig remove task 1") and has(log, "19.3333", "system reconfig fit task 2"), "parallel A removal/B fit completion")
    ck(has(log, "7", "Take replacement item <TEACH-LRU-A,0,0> from stock") and
       has(log, "19", "Take replacement item <TEACH-LRU-B,0,2> from stock"), "A/B stock draw identities")
    ck(has(log, "19.1667", "Put back replacement item <TEACH-LRU-A,0,3> to stock") and
       has(log, "31.1667", "Put back replacement item <TEACH-LRU-B,0,4> to stock"), "A/B stock return identities")
    stock_levels = {}
    for item in ("TEACH-LRU-01", "TEACH-LRU-A", "TEACH-LRU-B"):
        levels = [int(match.group(1)) for match in re.finditer(rf"Stock at: <{re.escape(item)},0,BASE-01,0> Level: (\d+)", log)]
        stock_levels[item] = levels
    ck(stock_levels == {"TEACH-LRU-01": [1], "TEACH-LRU-A": [1, 0, 1], "TEACH-LRU-B": [1, 0, 1]}, "individual stock conservation")
    ck("critical random failure added" not in log and "mission aborted:" not in log, "no failure/abort")
    report = tables(RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    summary = records(report["ResultSummary"])
    ck(len(summary) == 1 and summary[0]["RTIUP"] == 36 and summary[0]["NREP"] == 1 and
       all(summary[0][x] == 1 for x in ("MTMF", "MSTF", "MSUF", "STMF")), "summary factors")
    sys, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    ck(len(sys) == len(stock) == 72, "72 bins")
    for i, (sr, st) in enumerate(zip(sys, stock)):
        h = i / 2
        start = next((t for t in (7, 19, 31) if t <= h < t + 1), None)
        mission = int(any(t + 1 <= h < t + 3 for t in (7, 19, 31)))
        notice = int(start is not None)
        ready = 1 - int(bool(notice or mission))
        cfg = {7: 2 / 3, 19: 2 / 3, 31: 1 / 3}.get(h, 0)
        prep = (1 - cfg) if notice else 0
        ck((sr["STINT"], sr["ETINT"], st["STINT"], st["ETINT"]) == (h, h + .5, h, h + .5), f"bin time {i}")
        ck((sr["NSYRY"], sr["NSYMA"], sr["NSYMO"], sr["NSYA"], sr["FTMO"], sr["STACC"]) ==
           (ready, int(bool(notice or mission)), mission, 1, mission, mission), f"basic system ledger {i}")
        ck(near(sr["NSYMC"], cfg) and near(sr["NSYMR"], prep) and sr["NRCFG"] == int(h in (7, 19, 31)), f"configuration ledger {i}")
        ck(sr["STREQ"] == (.5 if mission else 0) and all(sr[x] == 0 for x in ("NFAIL", "NREPT", "NPMT", "NSYRP", "NSYPM")), f"mission/no-failure ledger {i}")
        ck(st["PNB"] == 1 and st["NBO"] == 0 and st["NDR"] == int(h in (7, 19)) and
           st["NWT"] == int(h in (7, 19)) and all(st[x] == 0 for x in ("NDF", "NDD", "NDP", "NLD")), f"stock ledger {i}")
    ck(sys[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1, "terminal one-ready")
    result = {
        "schema": "simlox-a16-two-config-independent-review/v1", "passed": not failures,
        "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
        "failure_count": len(failures), "failures": failures, "stock_level_sequences": stock_levels,
        "scope": "One deterministic base-to-A-to-B-to-base three-mission sequence with local stock and E01 subtasks.",
        "limits": ["No resource-capacity contention, failures, PM, alternative seeds, GUI rendering, or cross-engine parity.",
                   "A/B stock balances come from the individual event log; the default stock report aggregates all item types."],
    }
    OUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures, "result": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
