"""Independent, read-only raw replay of D14.var05; no author imports."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "D14-var03-post-reinstallation-pm-v1.0.0"
PARENT_Y = PARENT / "native-input-monitored.json"
PARENT_N = PARENT / "native-input-system-converted.json"
PARENT_Y_CLOSURE = PARENT / "runs/d14-var03-post-reinstall-monitored-v100-ssh-20261002-01/closure.json"
PARENT_N_CLOSURE = PARENT / "runs/d14-var03-post-reinstall-system-converted-v100-ssh-20261002-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = {
    "ophours-only": "d14-var05-ophours-only-v100-ssh-20261002-01",
    "missions-plus-ophours": "d14-var05-missions-plus-ophours-v100-ssh-20261002-01",
}
COUNT = 0
FAILURES: list[str] = []


def check(condition: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not condition:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path: Path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in data(path)[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def starts(text: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(pattern, text, re.M)]


def bin_value(time: float, periods: list[tuple[float, float]]) -> int:
    return int(any(start <= time < end for start, end in periods))


def check_report(arm: str, run: Path, pm_hours: list[int]) -> dict:
    report = tables(run / "report-raw.json", "report")
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, f"{arm}: report table set")
    sys_rows = rows(report["SystemResults"])
    stock_rows = rows(report["StockTotalResults"])
    summary = rows(report["ResultSummary"])
    check(len(sys_rows) == len(stock_rows) == 96, f"{arm}: 96 aligned half-hour bins")
    check(len(summary) == 1 and summary[0] == {
        "NREP": 1, "RTILW": 0, "RTIUP": 48, "MTMF": 1, "RSMTMF": 0,
        "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0,
    }, f"{arm}: full summary factors")
    missions = [(h, h + 2) for h in (8, 20, 32, 44)]
    active = [(h - 1, h + 2) for h in (8, 20, 32, 44)]
    preparation = [(h - 1, h) for h in (8, 20, 32, 44)]
    maintenance = [(h, h + .5) for h in pm_hours]
    ready = [(0, 7), (10.5, 19), (22, 31)]
    ready += ([(34.5, 43)] if 34 in pm_hours else [(34, 43)])
    ready += [(46.5, 48)]
    npms = [10, 34, 46] if 34 in pm_hours else [10, 45]
    expected_system = {
        "NSYRY": lambda t: bin_value(t, ready),
        "NSYMA": lambda t: bin_value(t, active),
        "NSYMO": lambda t: bin_value(t, missions),
        "NSYMR": lambda t: bin_value(t, preparation),
        "NSYUA": lambda t: bin_value(t, maintenance),
        "NSYA": lambda t: 1 - bin_value(t, maintenance),
        "FTMO": lambda t: bin_value(t, missions),
        "NSYPM": lambda t: bin_value(t, maintenance),
        "NPMT": lambda t: int(t in [h + .5 for h in pm_hours]),
        "NPMS": lambda t: int(t in npms),
        "STACC": lambda t: bin_value(t, missions),
        "NSYDT": lambda t: bin_value(t, maintenance),
    }
    expected_stock = {
        "PNB": lambda t: 1,
        "NDP": lambda t: int(t in pm_hours),
        "NWT": lambda t: int(t in pm_hours),
        "NBO": lambda t: 0,
    }
    for i, (sr, st) in enumerate(zip(sys_rows, stock_rows)):
        t = i / 2
        check(sr["STINT"] == st["STINT"] == t and sr["ETINT"] == st["ETINT"] == t + .5,
              f"{arm}: bin boundaries {i}")
        for key, expected in expected_system.items():
            check(sr[key] == expected(t), f"{arm}: SystemResults {key} bin {i}")
        check(sr["SYDT"] == (.5 if t in pm_hours else None), f"{arm}: system downtime length bin {i}")
        for key, expected in expected_stock.items():
            check(st[key] == expected(t), f"{arm}: StockTotalResults {key} bin {i}")
        for key in ("NSYMC", "NSYMT", "NSYMS", "NSYRP", "NREPT", "NFAIL", "NDAM", "NROBT", "NRCFG", "NSYSW"):
            check(sr[key] == 0, f"{arm}: no unrelated SystemResults {key} bin {i}")
        for key in ("NDF", "NDD", "NDR", "NLD"):
            check(st[key] == 0, f"{arm}: no unrelated StockTotalResults {key} bin {i}")
    check(sum(r["FTMO"] * .5 for r in sys_rows) == 8, f"{arm}: eight flight hours")
    check(sum(r["NSYPM"] * .5 for r in sys_rows) == .5 * len(pm_hours), f"{arm}: PM system hours")
    check(sys_rows[-1]["NSYRY"] == stock_rows[-1]["PNB"] == 1 and stock_rows[-1]["NBO"] == 0,
          f"{arm}: terminal ready and no backorder")
    return {"report_sha256": sha(run / "report-raw.json"), "system_pm_hours": .5 * len(pm_hours)}


def main() -> int:
    contract, diff = data(CASE / "contract.json"), data(CASE / "exact-diff.json")
    check(sha(PARENT_Y) == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"], "accepted D14.var03 parent input")
    check(sha(PARENT_Y_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"], "accepted D14.var03 parent closure")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff seal")
    check(sha(MANUAL) == contract["source"]["manual_sha256"], "manual seal")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary seal")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "CLI seal")
    parent = tables(PARENT_Y, "model")
    arm_tables: dict[str, dict] = {}
    evidence: dict[str, dict] = {}
    for arm, run_id in ARMS.items():
        source = CASE / f"native-input-{arm}.json"
        run = CASE / "runs" / run_id
        model = tables(source, "model")
        arm_tables[arm] = model
        check(sha(source) == contract["inputs"][arm]["sha256"] == diff["arms"][arm]["input_sha256"], f"{arm}: source seal")
        check(set(model).issuperset(parent), f"{arm}: parent table topology")
        actual = {name: {"before": parent[name], "after": model[name]} for name in parent if parent[name] != model[name]}
        actual.update({name: {"before": None, "after": model[name]} for name in set(model) - set(parent)})
        check(actual == diff["arms"][arm]["changed"], f"{arm}: exact parent delta")
        pm = rows(model["MaterielPM"])
        check(any(r["PMID"] == "LRU-MIX" and r["MID"] == "TEACH-LRU-01" and r["MONIT"] == "Y" and r["OPID"] == "OPHOURS" and r["PMINT"] == 5 for r in pm), f"{arm}: monitored item OPHOURS five")
        closure, invocation, steps = (data(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
        check(closure["run_id"] == invocation["run_id"] == run_id and closure["arm"] == arm, f"{arm}: run identity")
        check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm}: invocation seal")
        check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], f"{arm}: stable source seals")
        pins = {"input": source, "parent_y": PARENT_Y, "parent_y_closure": PARENT_Y_CLOSURE,
                "parent_n": PARENT_N, "parent_n_closure": PARENT_N_CLOSURE,
                "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
                "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
                "checker": CASE / "check_roundtrip.py", "runner": CASE / "run_native_ssh.ps1",
                "python": PYTHON, "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
        for key, path in pins.items():
            check(sha(path) == closure["source_hashes_before"][key], f"{arm}: source seal {key}")
        check(len(closure["raw"]) == 12 and closure["error"] is None, f"{arm}: twelve raw seals and no runner error")
        for name, seal in closure["raw"].items():
            path = run / name
            check(path.exists() and path.stat().st_size == seal["bytes"], f"{arm}: raw size {name}")
            check(sha(path) == seal["sha256"], f"{arm}: raw SHA {name}")
        check(sha(run / "input.json") == sha(source), f"{arm}: raw source copy")
        check(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0 and
              "sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]], f"{arm}: SSH session zero")
        check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
              f"{arm}: queue and preserved GUI")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm}: five steps")
        for step in steps:
            check(step["exit_code"] == 0 and step["gui_preserved"] is True and step["status"] == "completed", f"{arm}: step {step['name']}")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = [name for name, t in model.items() if any(i["rows"] for i in t["instances"])]
        check(len(populated) == (21 if arm == "missions-plus-ophours" else 20), f"{arm}: populated business table count")
        for name in populated:
            check(name in exported and model[name]["columns"] == exported[name]["columns"] and model[name]["instances"] == exported[name]["instances"], f"{arm}: native roundtrip {name}")
        run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in run_log and
              "warning #108" in run_log and "(error #" not in run_log, f"{arm}: conversion diagnostics")
        check((run / "model.sxo").stat().st_size > 4 and (run / "model.log").stat().st_size > 0,
              f"{arm}: usable native output")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        for i, (start, end) in enumerate(((8, 10), (20, 22), (32, 34), (44, 46))):
            ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
            for time, event in ((start, "mission starting"), (end, "mission success"), (end, "mission completed")):
                check(f"Time: {time} {ident} {event}" in log, f"{arm}: mission {i} {event}")
        pm_hours = [10, 34, 46] if arm == "missions-plus-ophours" else [10, 46]
        pm_events = starts(log, r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> PMID: LRU-MIX")
        check(pm_events == pm_hours[1:], f"{arm}: LRU-MIX starts")
        check(starts(log, r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> PMID: SYS-SWAP") == [10], f"{arm}: first SYS-SWAP")
        for h, removed, fitted in ([(10, 0, 1)] + ([(34, 1, 0)] if 34 in pm_hours else []) + [(46, 0 if 34 in pm_hours else 1, 1 if 34 in pm_hours else 0)]):
            check(f"Time: {h} <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,{removed}>" in log,
                  f"{arm}: physical removed item ID{removed} at {h}")
            check(f"Time: {h} <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{fitted}> from stock" in log,
                  f"{arm}: physical fitted item ID{fitted} at {h}")
            check(f"Time: {h+.25:g}  item PM task" in log and f"on <TEACH-LRU-01,0,{removed}> started" in log,
                  f"{arm}: removed item PM starts at {h+.25:g}")
            check(f"Time: {h+1.25:g} <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{removed}> to stock" in log,
                  f"{arm}: item ID{removed} returned to stock at {h+1.25:g}")
        check(log.count("PMID: LRU-MIX") == len(pm_hours) - 1 and "mission aborted" not in log and "failure occurs" not in log,
              f"{arm}: PM count and no mission failure")
        report_evidence = check_report(arm, run, pm_hours)
        evidence[arm] = {"input_sha256": sha(source), "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"), **report_evidence}
    a, b = arm_tables["ophours-only"], arm_tables["missions-plus-ophours"]
    check(set(b) - set(a) == {"MaterielPMInterval"} and
          {name for name in a if a[name] != b[name]} == {"ProblemDescription"},
          "paired difference is added interval and description")
    check(rows(b["MaterielPMInterval"]) == [{"PMID": "LRU-MIX", "OPID": "MISSIONS", "PMINT": 2.0, "NOTE": None}],
          "single MISSIONS2 item PM interval")
    result = {"schema": "simlox-independent-readonly-d14-var05/v1", "passed": not FAILURES,
              "verdict": "GO: bounded monitored-item multi-counter observation" if not FAILURES else "NO-GO: independent replay failed",
              "checks_passed": COUNT - len(FAILURES), "checks_total": COUNT, "failures": FAILURES,
              "evidence": evidence,
              "finding": "Both arms complete four two-hour missions. A one-time SYS-SWAP at h10 replaces item ID0 with ID1. The MISSIONS2+OPHOURS5 arm has LRU-MIX at h34 on ID1 and h46 on reinstalled ID0; OPHOURS5-only has no h34 LRU-MIX and its first LRU-MIX is h46 on ID1. Full 96-bin System/Stock reports and terminal readiness reconcile.",
              "limits": ["The winning counter is not named in native logs or reports; MISSIONS attribution is an inference from the isolated source difference and threshold timing.",
                         "One seed, one aircraft, two physical LRUs, one system swap, and 48-hour horizon. No counter tie, other intervals, initial prelife, general scheduling, GUI visual, or cross-engine claim."]}
    out = CASE / "independent-verdict.json"
    out.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": COUNT, "failures": FAILURES,
                      "verdict": result["verdict"], "output": str(out)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
