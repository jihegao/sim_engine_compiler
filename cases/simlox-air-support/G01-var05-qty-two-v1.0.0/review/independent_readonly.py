"""Independent read-only replay of the sealed G01.var05 quantity-two run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RUN = CASE / "runs" / "g01-var05-qty-v100-ssh-20261001-01"
PARENT_CASE = AIR / "G01-var01-lru-sru-v1.0.1"
PARENT = PARENT_CASE / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in load(path)[root]["tables"]}


def rows(t: dict) -> list:
    return [r for i in t["instances"] for r in i["rows"]]


def records(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for row in rows(t)]


def near(a, b, tol=1e-5) -> bool:
    return isinstance(a, (int, float)) and abs(a - b) <= tol


def at(log: str, when: str, phrase: str) -> bool:
    return any(s.startswith(f"Time: {when} ") and phrase in s for s in log.splitlines())


def main() -> None:
    contract = load(CASE / "contract.json")
    source = CASE / "native-input.json"
    diff = load(CASE / "exact-diff.json")
    ck(sha(PARENT) == contract["parent"]["input_sha256"], "accepted G01.var01 parent")
    ck(sha(source) == contract["native_input_sha256"], "frozen child input")
    ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "installed manual")
    p, c = tables(PARENT, "model"), tables(source, "model")
    changed = {n for n in c if c[n] != p[n]}
    ck(set(c) == set(p) and changed == set(contract["delta"]["tables"]) == set(diff["changed_tables"]), "exact four-table delta")
    ck(diff["parent_sha256"] == sha(PARENT) and diff["child_sha256"] == sha(source) and diff["unchanged_tables"] == len(c)-4, "diff fingerprints")
    for name in changed:
        ck(diff["changes"][name]["before"] == rows(p[name]) and diff["changes"][name]["after"] == rows(c[name]) and
           p[name]["columns"] == c[name]["columns"], f"exact delta {name}")
    sys_src = records(c["System"])[0]
    structure = records(c["ItemStructure"])
    stock_src = records(c["StockAllocation"])
    ck(sys_src["SID"] == "TEACH-AIR-01" and sys_src["FRT"] == 600000 and sys_src["OPID"] == "OPHOURS", "matched system rate")
    ck([(r["IID"], r["MID"], r["QTYPM"]) for r in structure] ==
       [("TEACH-LRU-01", "TEACH-AIR-01", 2), ("TEACH-SRU-01", "TEACH-LRU-01", 1)], "two interchangeable LRU positions")
    ck([(r["IID"], r["STSIZ"]) for r in stock_src] == [("TEACH-LRU-01", 2), ("TEACH-SRU-01", 1)], "local spare allocation")
    ck(all(c[n] == p[n] for n in ("Item", "ItemRepair", "ItemReplacement", "SystemRepair", "TaskBreakDown", "OperationProfile")), "rates, hierarchy repairs, tasks and missions inherited")

    inv, closure = load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None, "run identity/closure")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    ck(inv["input_sha256"] == sha(source) == sha(RUN / "input.json") and inv["parent_sha256"] == sha(PARENT) and
       inv["contract_sha256"] == sha(CASE / "contract.json"), "run source pins")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] > 0, "mutex/GUI identity")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source stable during run")
    for key, path in {"input": source, "parent": PARENT, "contract": CASE / "contract.json",
                      "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
                      "runner_script": CASE / "run_native_ssh.ps1"}.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"source seal {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "runtime seal")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw {name}")
    steps = load(RUN / "steps.json")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five recorded steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    export = tables(RUN / "roundtrip-raw.json", "model")
    populated = {n for n, t in c.items() if rows(t)}
    ck(len(populated) == 21, "21 populated source tables")
    for name in populated:
        ck(name in export and export[name]["columns"] == c[name]["columns"] and rows(export[name]) == rows(c[name]), f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and "warning #108" in runlog, "zero conversion errors")
    ck((RUN / "model.sxo").stat().st_size > 100000, "usable SXO")

    log = (RUN / "model.log").read_text(errors="replace")
    ck(at(log, "8.94145", "critical random failure added") and
       at(log, "8.94145", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:") and
       at(log, "21.6494", "critical random failure added") and
       at(log, "21.6494", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted:"), "two critical mission failures")
    ck("subitem failed: <TEACH-LRU-01,0,3> connection path: TEACH-AIR-01" in log and
       "subitem failed: <TEACH-LRU-01,0,5> connection path: TEACH-AIR-01" in log,
       "distinct failed LRU instances 3 and 5 at aircraft")
    ck("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>" in log and
       at(log, "9.44145", "Take replacement item <TEACH-LRU-01,0,1> from stock") and
       at(log, "22", "Take replacement item <TEACH-LRU-01,0,2> from stock"), "opening spare identities and separate replacement issues")
    first_failure = log.index("Time: 8.94145 <TEACH-AIR-01,0> critical random failure added")
    second_failure = log.index("Time: 21.6494 <TEACH-AIR-01,0> critical random failure added")
    ck("Take replacement item <TEACH-LRU-01,0,3>" not in log[:second_failure] and
       "Take replacement item <TEACH-LRU-01,0,5>" not in log[:second_failure] and
       "Put back replacement item <TEACH-LRU-01,0,5>" not in log[:second_failure] and
       first_failure < second_failure, "failed 3/5 were never preceding spare issues or repaired returns")
    ck(at(log, "9.44145", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,3>") and
       at(log, "22", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,5>"), "each failed installed LRU produces own demand")
    ck(at(log, "9.60812", "Item requiring maintenance arrives <TEACH-LRU-01,0,3>") and
       at(log, "9.60812", "subitem failed: <TEACH-SRU-01,0,4>") and
       at(log, "22.1667", "Item requiring maintenance arrives <TEACH-LRU-01,0,5>") and
       at(log, "22.1667", "subitem failed: <TEACH-SRU-01,0,6>"), "nested SRU failures 4/6")
    ck(at(log, "9.60812", "Take replacement item <TEACH-SRU-01,0,0> from stock") and
       at(log, "22.1667", "Take replacement item <TEACH-SRU-01,0,4> from stock"), "SRU spare and repaired-SRU reissue")
    ck(at(log, "9.44145", "system SURP task 0 on <TEACH-AIR-01,0> started") and
       at(log, "9.94145", "system SURP task 0 on <TEACH-AIR-01,0> completed") and
       at(log, "22", "system SURP task 3 on <TEACH-AIR-01,0> started") and
       at(log, "22.5", "system SURP task 3 on <TEACH-AIR-01,0> completed"), "two half-hour system exchanges")
    ck(at(log, "9.60812", "item SURP task 1 on <TEACH-LRU-01,0,3> started") and
       at(log, "10.3581", "item SURP task 1 on <TEACH-LRU-01,0,3> completed") and
       at(log, "22.1667", "item SURP task 4 on <TEACH-LRU-01,0,5> started") and
       at(log, "22.9167", "item SURP task 4 on <TEACH-LRU-01,0,5> completed"), "two .75-hour LRU/SRU replacements")
    ck(at(log, "9.98312", "item DIRP task 2 on <TEACH-SRU-01,0,4> started") and
       at(log, "10.9831", "item DIRP task 2 on <TEACH-SRU-01,0,4> completed") and
       at(log, "22.5417", "item DIRP task 5 on <TEACH-SRU-01,0,6> started") and
       at(log, "23.5417", "item DIRP task 5 on <TEACH-SRU-01,0,6> completed"), "two one-hour SRU repairs")
    ck(at(log, "10.3581", "Put back replacement item <TEACH-LRU-01,0,3> to stock") and
       at(log, "22.9167", "Put back replacement item <TEACH-LRU-01,0,5> to stock") and
       at(log, "10.9831", "Put back replacement item <TEACH-SRU-01,0,4> to stock") and
       at(log, "23.5417", "Put back replacement item <TEACH-SRU-01,0,6> to stock"), "repaired item returns")
    levels = {kind: [int(m.group(1)) for m in re.finditer(
        rf"Stock at: <{kind},0,BASE-01,0> Level: (\d+)", log)]
        for kind in ("TEACH-LRU-01", "TEACH-SRU-01")}
    ck(levels == {"TEACH-LRU-01": [2, 1, 2, 1, 2], "TEACH-SRU-01": [1, 0, 1, 0, 1]}, "physical stock conservation")
    ck(log.count("Backorder added") == 0 and "transport task" not in log, "no backorder or forwarding")
    ck(at(log, "34", "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:") and
       at(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>"), "third mission success/terminal ready")

    report = tables(RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    summary = records(report["ResultSummary"])[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and all(near(summary[k], v) for k, v in
       {"MTMF": .9069082736968994, "MSTF": 1, "MSUF": 1/3, "STMF": .9069082736968994}.items()), "summary outcomes")
    system, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, "72 half-hour system/stock bins")
    frac = (9.44145 - 9) / .5
    for i, (s, t) in enumerate(zip(system, stock)):
        h = i / 2
        prep = int(7 <= h < 8 or 19 <= h < 20 or 31 <= h < 32)
        mission = (frac if h == 9 else int(8 <= h < 9 or 20 <= h < 22 or 32 <= h < 34))
        ready = (1-frac if h == 9.5 else int(h < 7 or 10 <= h < 19 or 22.5 <= h < 31 or 34 <= h))
        repair = (1-frac if h == 9 else frac if h == 9.5 else int(h == 22))
        expected_s = {"NSYRY": ready, "NSYMA": prep + mission, "NSYMO": mission,
                      "NSYMR": prep, "NSYUA": repair, "NSYA": ready + prep + mission,
                      "FTMO": mission, "NSYRP": repair, "NREPT": int(h in (9.5, 22.5)),
                      "NFAIL": int(h in (8.5, 21.5)), "STACC": mission,
                      "SYDT": .5 if h in (9, 22) else None, "NSYDT": int(h in (9, 22))}
        expected_t = {"PNB": 1, "NDF": int(h in (9, 22)), "NWT": int(h in (9, 22))}
        ck((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) == (h, h+.5, h, h+.5), f"bin time {i}")
        ck(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems", f"system labels {i}")
        for name, value in s.items():
            if name in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = expected_s.get(name, 0)
            ck(value is None if target is None else near(value, target), f"system {name} bin {i}")
        for name, value in t.items():
            if name in ("STINT", "ETINT"):
                continue
            target = None if name in {"NBOU", "WTS"} or (name in {"ROS", "ROST", "WT", "WTT"} and h not in (9, 22)) else expected_t.get(name, 0)
            ck(value is None if target is None else near(value, target), f"stock {name} bin {i}")
    ck(system[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0, "terminal report")
    parent_report = tables(PARENT_CASE / "runs" / "g01-var01-v101-ssh-20261001-01" / "report-raw.json", "report")
    ck(records(parent_report["ResultSummary"])[0]["MSUF"] > summary["MSUF"] and
       len(records(parent_report["SystemResults"])) == 72, "bounded stochastic parent comparison")

    result = {"schema": "simlox-g01-var05-independent-review/v1", "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failure_count": len(failures), "failures": failures,
              "inferred_initial_installed_lru_ids": [3, 5], "opening_lru_spare_ids": [1, 2],
              "stock_level_sequences": levels,
              "scope": "One fixed-seed one-aircraft model with two interchangeable installed LRU positions, matched system FRT and two local LRU spares.",
              "limits": ["No initial native listing enumerates both installed LRUs simultaneously. IDs 3 and 5 are inferred as the two originals from source QTYPM=2, distinct failures at the aircraft, opening spare IDs 1/2 and absence of any earlier issue/return of 3/5.",
                         "System FRT and LRU stock were changed with QTYPM, so outcome rates and mission success are not isolated QTYPM effects.",
                         "NSIMI=2, other rates/seeds, stockout, GUI rendering and cross-engine parity remain unverified."]}
    OUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures, "report": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
