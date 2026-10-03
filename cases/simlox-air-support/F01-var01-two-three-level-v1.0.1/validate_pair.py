"""Read-only author replay of the frozen F01.var01 two/three-level pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"f01-var01-{arm}-v101-ssh-20261004-01" for arm in ("two", "three")}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    t = next(x for x in report["report"]["tables"] if x["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for ins in t["instances"] for row in ins["rows"]]


def events(log: str, pattern: str) -> list[tuple]:
    return [(float(m.group(1)), *m.groups()[1:]) for m in re.finditer(pattern, log, re.M)]


def main() -> None:
    failures: list[str] = []
    checks = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    diff = load(HERE / "exact-diff.json")
    ck(contract["case_id"] == "F01" and contract["variant_id"] == "F01.var01", "contract identity")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff pin")
    ck(diff["two_from_e05"]["left_sha256"] == contract["accepted_two_level_parent"]["input_sha256"], "E05 diff parent")
    ck(diff["three_from_g01"]["left_sha256"] == contract["accepted_three_level_parent"]["input_sha256"], "G01 diff parent")
    ck(diff["three_from_two"]["left_sha256"] == contract["two_level_input_sha256"] and diff["three_from_two"]["right_sha256"] == contract["three_level_input_sha256"], "paired diff fingerprints")
    ck([x["table"] for x in diff["three_from_two"]["changed_tables"]] == ["ProblemDescription", "Item", "ItemStructure", "ItemRepair", "StockAllocation", "ItemReplacement"], "six-table topology")
    parent_paths = {
        "two": ROOT / contract["accepted_two_level_parent"]["package"] / "native-input.json",
        "three": ROOT / contract["accepted_three_level_parent"]["package"] / "native-input.json",
    }
    for arm in RUNS:
        ck(sha(parent_paths[arm]) == contract[f"accepted_{arm}_level_parent"]["input_sha256"], f"{arm} parent source")
        p = ROOT / contract[f"accepted_{arm}_level_parent"]["package"] / "runs" / contract[f"accepted_{arm}_level_parent"]["run_id"] / "closure.json"
        ck(sha(p) == contract[f"accepted_{arm}_level_parent"]["native_closure_sha256"], f"{arm} parent native closure")
    diagnostic = contract["preceding_unpublished_diagnostic"]
    ck(sha(ROOT / diagnostic["package"] / "runs" / diagnostic["run_id"] / "closure.json") == diagnostic["closure_sha256"], "prior diagnostic closure")

    data = {}
    for arm, run in RUNS.items():
        source = HERE / f"{arm}-level-input.json"
        expected_sha = contract[f"{arm}_level_input_sha256"]
        ck(sha(source) == sha(run / "input.json") == expected_sha, f"{arm} frozen/run input")
        invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(invocation["arm"] == closure["arm"] == arm and invocation["run_id"] == closure["run_id"] == run.name, f"{arm} arm/run identity")
        ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH0")
        ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{arm} queue/GUI")
        ck(closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json"), f"{arm} closure")
        ck(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], f"{arm} unchanged source")
        ck(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), f"{arm} contract seal")
        for key, name in (("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
            ck(closure["source_hashes_before"][key] == sha(HERE / name), f"{arm} {name} seal")
        ck(set(closure["raw"]) == RAW, f"{arm} 12 raw files")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{arm} raw {name}")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps), f"{arm} five steps")
        ck((run / "model.sxi").stat().st_size > 1000 and (run / "model.sxo").stat().st_size > 1000, f"{arm} valid-size model/output")
        roundtrip = load(run / "roundtrip-validation.json")
        authored, exported = populated(parse_native(source)), populated(parse_native(run / "roundtrip-raw.json"))
        ck(roundtrip["passed"] and not roundtrip["differences"] and len(authored) == {"two": 20, "three": 21}[arm], f"{arm} populated roundtrip count")
        for name, table in authored.items():
            ck(exported.get(name) == table, f"{arm} exported {name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1, f"{arm} converter")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        fault = events(log, r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical random failure added")
        demand = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,(\d+)>")
        issue = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
        lru_return = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
        ck(len(fault) == len(demand) == len(issue) == len(lru_return) == 2, f"{arm} two LRU cycles")
        if len(demand) == len(issue) == len(lru_return) == 2:
            for i in range(2):
                ck(demand[i][1] == lru_return[i][1], f"{arm} repaired LRU physical identity {i}")
                ck(demand[i][0] <= issue[i][0] < lru_return[i][0], f"{arm} LRU demand/repair order {i}")
            ck(issue[1][1] == lru_return[0][1] and lru_return[0][0] < issue[1][0], f"{arm} repaired LRU reissued")
        ck(len(events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:")) == 2 and len(events(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:")) == 1, f"{arm} mission outcomes")
        ck("Backorder added" not in log and "requests resources: no resources needed" in log, f"{arm} no backorder/resource scarcity")
        ck("Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in log, f"{arm} terminal-ready event")
        report = parse_native(run / "report-raw.json")
        summary, system, stock = (rows(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
        ck(len(summary) == 1 and abs(summary[0]["MSUF"] - 1 / 3) < 1e-6, f"{arm} summary mission success")
        ck(len(system) == len(stock) == 72, f"{arm} report intervals")
        for i, (sys, stk) in enumerate(zip(system, stock)):
            ck(sys["STINT"] == stk["STINT"] == i / 2 and sys["ETINT"] == stk["ETINT"] == (i + 1) / 2, f"{arm} interval {i}")
            ck(stk["NBO"] == 0, f"{arm} no backorder bin {i}")
        ck(sum(x["NFAIL"] for x in system) == sum(x["NREPT"] for x in system) == 2, f"{arm} failure/repair totals")
        ck(sum(x["NDF"] for x in stock) == 2 and system[-1]["NSYRY"] == 1, f"{arm} stock demands/terminal")
        data[arm] = {"log": log, "fault": fault, "demand": demand, "issue": issue, "return": lru_return,
                     "summary": summary, "system": system, "stock": stock, "closure_sha256": sha(run / "closure.json")}

    for arm in ("two", "three"):
        log = data[arm]["log"]
        if arm == "two":
            direct = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,(\d+)>")
            finish = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,(\d+)>")
            ck(len(direct) == len(finish) == 2 and not events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Item demand arrives"), "two: direct LRU only")
            for i in range(min(len(direct), len(finish))):
                ck(direct[i][1] == finish[i][1] == data[arm]["demand"][i][1] and abs(finish[i][0] - direct[i][0] - 1.0) < 1e-4, f"two: direct LRU repair {i}")
        else:
            nested = events(log, r"^Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)> from position <TEACH-AIR-01,BASE-01,0> subitem failed: <TEACH-SRU-01,0,(\d+)>")
            sru_demand = events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> item requiring maintenance is <TEACH-SRU-01,0,(\d+)>")
            sru_issue = events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Take replacement item <TEACH-SRU-01,0,(\d+)> from stock")
            sru_return = events(log, r"^Time: ([\d.]+) <TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,(\d+)> to stock")
            ck(len(nested) == len(sru_demand) == len(sru_issue) == len(sru_return) == 2, "three: two nested SRU cycles")
            if len(nested) == len(sru_demand) == len(sru_issue) == len(sru_return) == 2:
                for i in range(2):
                    ck(nested[i][1] == data[arm]["demand"][i][1] and nested[i][2] == sru_demand[i][1] == sru_return[i][1], f"three: nested physical identities {i}")
                    ck(sru_demand[i][0] == sru_issue[i][0] and sru_return[i][0] > sru_issue[i][0], f"three: SRU issue/return {i}")
                ck(sru_issue[1][1] == sru_return[0][1], "three: repaired SRU reissued")
            surp_start = events(log, r"^Time: ([\d.]+)  item SURP task \d+ on <TEACH-LRU-01,0,(\d+)> started")
            surp_end = events(log, r"^Time: ([\d.]+)  item SURP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
            sru_dirp_start = events(log, r"^Time: ([\d.]+)  item DIRP task \d+ on <TEACH-SRU-01,0,(\d+)> started")
            sru_dirp_end = events(log, r"^Time: ([\d.]+)  item DIRP task \d+ on <TEACH-SRU-01,0,(\d+)> completed")
            ck(len(surp_start) == len(surp_end) == len(sru_dirp_start) == len(sru_dirp_end) == 2, "three: two SURP/DIRP tasks")
            for i in range(min(len(surp_start), len(surp_end), len(sru_dirp_start), len(sru_dirp_end))):
                ck(surp_start[i][1] == surp_end[i][1] == data[arm]["demand"][i][1] and abs(surp_end[i][0] - surp_start[i][0] - .75) < 1e-4, f"three: specific SURP 0.75 {i}")
                ck(sru_dirp_start[i][1] == sru_dirp_end[i][1] == sru_return[i][1] and abs(sru_dirp_end[i][0] - sru_dirp_start[i][0] - 1.0) < 1e-4, f"three: SRU DIRP 1h {i}")
            ck(log.count("planned to last for 0.375 hours") == 4, "three: four SURP half-steps")

    for name in ("summary", "system", "stock"):
        ck(data["two"][name] == data["three"][name], f"observed paired {name} equality")
    result = {"schema": "simlox-f01-var01-two-three-author-replay/v1", "passed": not failures,
              "checks": checks, "failures": failures, "case_id": "F01", "variant_id": "F01.var01",
              "arms": {arm: {"run_id": RUNS[arm].name, "closure_sha256": data[arm]["closure_sha256"],
                              "fault_hours": [t for t, *_ in data[arm]["fault"]], "lru_demand_count": len(data[arm]["demand"]),
                              "repaired_lru_reissue": data[arm]["issue"][1][1] == data[arm]["return"][0][1]}
                       for arm in RUNS},
              "paired_result_summary_equal": data["two"]["summary"] == data["three"]["summary"],
              "paired_system_all_72_equal": data["two"]["system"] == data["three"]["system"],
              "paired_stock_all_72_equal": data["two"]["stock"] == data["three"]["stock"],
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    (HERE / "author-validation-2026-10-04.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
