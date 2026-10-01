"""Independent standard-library replay of sealed G01.var06 v1.0.1 evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
AIR = HERE.parent
PARENT = AIR / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUTPUT = HERE / "review/independent-readonly-2026-10-01.json"
RUNS = {k: HERE / "runs" / f"g01-var06-{k}-v101-ssh-20261001-01"
        for k in ("identical", "similar")}
checks = 0
failures: list[str] = []


def check(test: bool, description: str) -> None:
    global checks
    checks += 1
    if not test:
        failures.append(description)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    # Native export has optional trailing commas in JSON.
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in read(path)[root]["tables"]}


def rows(table: dict) -> list:
    return [row for inst in table["instances"] for row in inst["rows"]]


def records(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def close(actual, expected, eps=2e-4) -> bool:
    return isinstance(actual, (float, int)) and abs(actual-expected) < eps


def event(log: str, time: str, token: str) -> bool:
    return any(line.startswith(f"Time: {time} ") and token in line for line in log.splitlines())


def overlap(a: float, b: float, h: float) -> float:
    return max(0.0, min(b, h+.5)-max(a, h))/.5


def source_review(contract: dict) -> dict:
    check(digest(PARENT) == contract["parent"]["input_sha256"], "accepted E01 parent SHA")
    check(digest(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual SHA")
    check((AIR / "E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md").is_file(),
          "E01 signoff present")
    p = tables(PARENT, "model")
    sources = {}
    for kind in RUNS:
        path = HERE / f"native-{kind}.json"
        check(digest(path) == contract["native_inputs_sha256"][kind], f"{kind} input SHA")
        child = tables(path, "model")
        expect_changes = set(contract["delta"]["expected_changed_tables"][kind])
        changed = {name for name in p if child.get(name) != p[name]}
        check(set(p) == set(child) and changed == expect_changes, f"{kind} exact changed tables")
        for name in set(p)-changed:
            check(child[name] == p[name], f"{kind} invariant table {name}")
        for name in changed:
            check(child[name]["columns"] == p[name]["columns"] and
                  len(rows(child[name])) == len(rows(p[name])), f"{kind} changed table shape {name}")
        def one(name):
            return records(child[name])[0]
        system, item, structure, stock = map(one, ("System", "Item", "ItemStructure", "StockAllocation"))
        check(system["SID"] == "TEACH-AIR-01" and system["FRT"] == 600000 and system["OPID"] == "OPHOURS",
              f"{kind} system rate")
        check(item["IID"] == "TEACH-LRU-01" and item["FRT"] == 300000 and
              item["NSIMI"] == (2 if kind == "similar" else None), f"{kind} item NSIMI")
        check(structure["IID"] == "TEACH-LRU-01" and structure["MID"] == "TEACH-AIR-01" and
              structure["QTYPM"] == (1 if kind == "similar" else 2), f"{kind} QTYPM")
        check(stock["IID"] == "TEACH-LRU-01" and stock["STID"] == "BASE-01" and
              stock["STSIZ"] == 2, f"{kind} per-index stock size")
        for name, col, value in (("System", "FRT", 600000),
                                  ("StockAllocation", "STSIZ", 2),
                                  ("Item", "NSIMI", 2 if kind == "similar" else None),
                                  ("ItemStructure", "QTYPM", 1 if kind == "similar" else 2)):
            before, after = records(p[name])[0], records(child[name])[0]
            delta = {key for key in before if before[key] != after[key]}
            check(delta == ({col} if before[col] != value else set()) and after[col] == value,
                  f"{kind} field delta {name}.{col}")
        check(len([n for n, t in child.items() if rows(t)]) == 20, f"{kind} 20 populated tables")
        sources[kind] = child
    pair_change = {n for n in sources["identical"] if sources["identical"][n] != sources["similar"][n]}
    check(pair_change == {"ProblemDescription", "Item", "ItemStructure"}, "pair source isolation")
    return sources


def run_review(kind: str, source: dict, contract: dict) -> tuple[dict, str]:
    run = RUNS[kind]
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    check(inv["run_id"] == closure["run_id"] == run.name and inv["branch_kind"] == kind and
          closure["error"] is None, f"{kind} run identity")
    check(closure["invocation_sha256"] == digest(run / "invocation.json"), f"{kind} invocation seal")
    check(inv["input_sha256"] == digest(HERE / f"native-{kind}.json") == digest(run / "input.json") and
          inv["parent_sha256"] == digest(PARENT) and inv["contract_sha256"] == digest(HERE / "contract.json"),
          f"{kind} source pins")
    check(inv["session_id"] == 0 and inv["ssh_connection_present"] and
          "sshd.exe" in inv["ssh_ancestor_names"] and inv["execution_mode"] == "ssh_cli_v1",
          f"{kind} session0 SSH")
    check(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
          f"{kind} mutex/GUI")
    check(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"],
          f"{kind} source stability")
    paths = {"input": HERE / f"native-{kind}.json", "parent": PARENT,
             "contract": HERE / "contract.json", "builder": HERE / "build.py",
             "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}
    for key, path in paths.items():
        check(inv["source_hashes_before"].get(key) == digest(path), f"{kind} source seal {key}")
    check(inv["source_hashes_before"]["simlox_exe"] ==
          "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", f"{kind} runtime seal")
    for name, meta in closure["raw"].items():
        path = run / name
        check(path.is_file() and path.stat().st_size == meta["bytes"] and digest(path) == meta["sha256"],
              f"{kind} raw {name}")
    check([s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"], f"{kind} five steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and
              step["error"] is None, f"{kind} step {step['name']}")
    export = tables(run / "roundtrip-raw.json", "model")
    populated = {name for name, table in source.items() if rows(table)}
    check(len(populated) == 20, f"{kind} roundtrip 20 tables")
    for name in populated:
        check(name in export and export[name]["columns"] == source[name]["columns"] and
              rows(export[name]) == rows(source[name]), f"{kind} roundtrip {name}")
    runlog = (run / "run.log").read_text(errors="replace")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
          "warning #108" in runlog and "error #" not in runlog.lower(), f"{kind} converter")
    check((run / "model.sxo").stat().st_size > 100000, f"{kind} usable SXO")

    log = (run / "model.log").read_text(errors="replace")
    idxs, failed, spare, return_times = (
        ([0, 0, 0], [2, 3, 4], [0, 1, 2], ["10.6081", "23.1365", "34.6476"])
        if kind == "identical" else
        ([1, 1, 0], [4, 5, 6], [2, 3, 0], ["10.6081", "23.1365", "34.6476"]))
    fails = ["8.94145", "21.4698", "32.9809"]
    demands = ["9.44145", "21.9698", "33.4809"]
    removed = ["9.60812", "22.1365", "33.6476"]
    repairs_done = ["9.94145", "22.4698", "33.9809"]
    for j, (index, physical, issued) in enumerate(zip(idxs, failed, spare)):
        name = f"<TEACH-LRU-01,{index},{physical}>"
        replacement = f"<TEACH-LRU-01,{index},{issued}>"
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{j}>"
        check(event(log, str(7+12*j), f"{mission} mission allocates system: <TEACH-AIR-01,0>") and
              event(log, str(8+12*j), f"{mission} mission starting, duration: 2"),
              f"{kind} mission {j} launch")
        check(event(log, fails[j], "critical random failure added") and
              f"subitem failed: {name} connection path: TEACH-AIR-01" in log and
              event(log, fails[j], f"{mission} mission aborted:"), f"{kind} failed identity {j}")
        check(event(log, demands[j], f"Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is {name}") and
              event(log, demands[j], f"Take replacement item {replacement} from stock"),
              f"{kind} index-matched stock issue {j}")
        check(event(log, removed[j], f"Item requiring maintenance arrives {name}") and
              event(log, removed[j], f"item DIRP task {2*j+1} on {name} started"),
              f"{kind} removed item repair {j}")
        check(event(log, repairs_done[j], f"system SURP task {2*j} on <TEACH-AIR-01,0> completed") and
              event(log, repairs_done[j], "systems ready: 1 :<TEACH-AIR-01,0>"),
              f"{kind} system replacement completed {j}")
        check(event(log, return_times[j], f"Put back replacement item {name} to stock"),
              f"{kind} repaired item return {j}")
    check(log.count("mission success:") == 0 and log.count("mission aborted:") == 3 and
          "Backorder added" not in log and "transport task" not in log, f"{kind} three aborts/no backlog")
    check(event(log, "33.9809", "systems ready: 1 :<TEACH-AIR-01,0>"), f"{kind} terminal aircraft ready")
    if kind == "identical":
        check("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>" in log,
              "identical one opening stock pool")
        check("Stock at: <TEACH-LRU-01,1,BASE-01,0>" not in log and
              log.count("Stock initiated") == 1, "identical no second pool")
    else:
        for index, ids in ((0, (0, 1)), (1, (2, 3))):
            check(f"Stock at: <TEACH-LRU-01,{index},BASE-01,0> Level: 2 Items:"
                  f"<TEACH-LRU-01,{index},{ids[0]}>,<TEACH-LRU-01,{index},{ids[1]}>" in log,
                  f"similar opening pool {index}")
        check(log.count("Stock initiated") == 2 and
              "<TEACH-LRU-01,0,BASE-01,0>" in log and "<TEACH-LRU-01,1,BASE-01,0>" in log,
              "similar two per-index pools")
        check(not re.search(r"Time: (?:9\.44145|21\.9698) .*Take replacement item <TEACH-LRU-01,0,", log) and
              not re.search(r"Time: 33\.4809 .*Take replacement item <TEACH-LRU-01,1,", log),
              "no observed cross-index issue")
    for index in (set(idxs)):
        stock_levels = [int(x) for x in re.findall(
            rf"Stock at: <TEACH-LRU-01,{index},BASE-01,0> Level: (\d+)", log)]
        expected = ([2, 1, 2, 1, 2, 1, 2] if kind == "identical" else
                    [2, 1, 2] if index == 0 else [2, 1, 2, 1, 2])
        check(stock_levels == expected, f"{kind} pool {index} physical stock conservation")

    report = tables(run / "report-raw.json", "report")
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
          f"{kind} report tables")
    summary = records(report["ResultSummary"])[0]
    check(summary["NREP"] == 1 and summary["RTIUP"] == 36 and
          all(close(summary[k], v) for k, v in
              {"MTMF": .8153663873672485, "STMF": .8153663873672485,
               "MSTF": 1, "MSUF": 0}.items()), f"{kind} summary factors")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(len(system) == len(stock) == 72, f"{kind} report 72 bins")
    mission_intervals = [(8, 9.44145), (20, 21.9698), (32, 33.4809)]
    prep_intervals = [(7, 8), (19, 20), (31, 32)]
    repair_intervals = [(9.44145, 9.94145), (21.9698, 22.4698), (33.4809, 33.9809)]
    ready_intervals = [(0, 7), (9.94145, 19), (22.4698, 31), (33.9809, 36)]
    for i, (s, t) in enumerate(zip(system, stock)):
        h = i / 2
        mission = sum(overlap(a, b, h) for a, b in mission_intervals)
        prep = sum(overlap(a, b, h) for a, b in prep_intervals)
        repair = sum(overlap(a, b, h) for a, b in repair_intervals)
        ready = sum(overlap(a, b, h) for a, b in ready_intervals)
        expected_s = {"NSYRY": ready, "NSYMA": prep+mission, "NSYMO": mission,
                      "NSYMR": prep, "NSYUA": repair, "NSYA": ready+prep+mission,
                      "FTMO": mission, "NSYRP": repair,
                      "NREPT": int(h in (9.5, 22, 33.5)),
                      "NFAIL": int(h in (8.5, 21, 32.5)), "STACC": mission,
                      "SYDT": .5 if h in (9, 21.5, 33) else None,
                      "NSYDT": int(h in (9, 21.5, 33))}
        expected_t = {"PNB": 1, "NDF": int(h in (9, 21.5, 33)),
                      "NWT": int(h in (9, 21.5, 33))}
        check((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) ==
              (h, h+.5, h, h+.5), f"{kind} bin time {i}")
        check(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems",
              f"{kind} system labels {i}")
        for key, val in s.items():
            if key in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = expected_s.get(key, 0)
            check(val is None if target is None else close(val, target),
                  f"{kind} system {key} bin {i}")
        for key, val in t.items():
            if key in ("STINT", "ETINT"):
                continue
            target = (None if key in ("NBOU", "WTS") or
                      (key in ("ROS", "ROST", "WT", "WTT") and h not in (9, 21.5, 33))
                      else expected_t.get(key, 0))
            check(val is None if target is None else close(val, target),
                  f"{kind} stock {key} bin {i}")
    check(system[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and
          stock[-1]["NBO"] == 0, f"{kind} terminal report")
    return report, log


def main() -> None:
    contract = read(HERE / "contract.json")
    sources = source_review(contract)
    artifacts = {kind: run_review(kind, sources[kind], contract) for kind in RUNS}
    ir, ilog = artifacts["identical"]
    sr, slog = artifacts["similar"]
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(ir[name] == sr[name], f"paired report {name} equal")
    check(ir["ProblemDescription"] != sr["ProblemDescription"], "paired description distinct")
    for token in ("Time: 8.94145", "Time: 21.4698", "Time: 32.9809"):
        check(token in ilog and token in slog, f"common failure time {token}")
    old = AIR / "G01-var06-similar-vs-identical-v1.0.0/runs/g01-var06-identical-v100-ssh-20261001-01"
    old_validation = read(old / "roundtrip-validation.json")
    old_steps = read(old / "steps.json")
    old_runlog = (old / "run.log").read_text(errors="replace")
    check(old_validation["passed"] is False and
          [s["name"] for s in old_steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["exit_code"] == 0 for s in old_steps[:4]) and
          old_steps[4]["exit_code"] == 1 and
          "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in old_runlog and
          (old / "report-raw.json").is_file(),
          "v1.0.0 native steps completed but copied checker failed; excluded")
    result = {
        "schema": "simlox-g01-var06-independent-review/v1", "passed": not failures,
        "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
        "failure_count": len(failures), "failures": failures,
        "observed_identity": {
            "identical": {"NSIMI": 1, "QTYPM": 2, "spare_pools": {"0": [0, 1]},
                          "failed_indices": [0, 0, 0], "issued_indices": [0, 0, 0]},
            "similar": {"NSIMI": 2, "QTYPM": 1, "spare_pools": {"0": [0, 1], "1": [2, 3]},
                        "failed_indices": [1, 1, 0], "issued_indices": [1, 1, 0]}},
        "scope": "One aircraft, one fixed seed, 36 hours; observed index-matched issues and returns in two well-stocked similar-item pools versus one identical-item pool.",
        "limits": [
            "STSIZ=2 is applied per NSIMI index: similar begins with four spares total, identical with two. Inventory is not matched across branches.",
            "No similar-item pool was depleted; the absence of cross-index substitution here does not prove what happens under stockout.",
            "The common failure times and aggregate report outcomes do not alone distinguish interchangeability; typed log identities and separate stock ledgers do.",
            "v1.0.0 first run completed native import/export/calculation/report with zero conversion errors, but acceptance failed at the copied checker 21-versus-20 table count; it remains an excluded diagnostic."]}
    OUTPUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
