"""Author read-only replay of the frozen F01.var03 explicit nested CM candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/f01-var03-explicit-v100-ssh-20261004-04"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def matches(log: str, pattern: str) -> list[tuple]:
    return [(float(m.group(1)), *m.groups()[1:]) for m in re.finditer(pattern, log, re.M)]


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    failures: list[str] = []
    count = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    input_sha = contract["explicit_input_sha256"]
    ck(contract["case_id"] == "F01" and contract["variant_id"] == "F01.var03" and contract["version"] == "1.0.0-candidate", "contract identity")
    ck(sha(HERE / "explicit-input.json") == sha(RUN / "input.json") == input_sha, "frozen input/run fingerprint")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff fingerprint")
    ck(diff["traditional_input_sha256"] == contract["accepted_traditional_behavior_parent"]["input_sha256"] and diff["explicit_input_sha256"] == input_sha, "diff endpoints")
    ck([entry["table"] for entry in diff["changed_tables"]] == ["CMLocation", "CMReplacement", "FailureMode", "Item", "ItemRepair", "ItemReplacement", "ItemStructure", "MaterielStructure", "ProblemDescription", "System", "SystemRepair"], "11 changed tables")
    for key, filename in (("accepted_traditional_behavior_parent", "three-level-input.json"),
                          ("accepted_explicit_cm_reference", "native-input.json")):
        ref = contract[key]
        ck(sha(ROOT / ref["package"] / filename) == ref["input_sha256"], f"{key} input")
        ck(sha(ROOT / ref["package"] / "runs" / ref["run_id"] / "closure.json") == ref["closure_sha256"], f"{key} closure")
    traditional = contract["accepted_traditional_behavior_parent"]
    ck(sha(ROOT / traditional["package"] / "evidence-index.json") == traditional["evidence_index_sha256"], "traditional evidence index")

    invocation, closure, steps = (load(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN.name and invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 run identity")
    ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "queue/GUI provenance")
    ck(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"), "complete closure")
    ck(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source stability")
    for key, filename in (("build.py", "build.py"), ("describe_diff.py", "describe_diff.py"),
                          ("check_roundtrip.py", "check_roundtrip.py"), ("run_native_ssh.ps1", "run_native_ssh.ps1"),
                          ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("input", "explicit-input.json")):
        ck(closure["source_hashes_before"][key] == sha(HERE / filename), f"sealed source {key}")
    ck(set(closure["raw"]) == RAW, "12 sealed raw files")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw {name}")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps), "five native/check steps")
    ck(all(step.get("gui_preserved", True) is True for step in steps), "GUI guard each native step")
    ck((RUN / "model.sxi").stat().st_size > 1000 and (RUN / "model.sxo").stat().st_size > 1000, "valid model/output size")
    roundtrip = load(RUN / "roundtrip-validation.json")
    authored = populated(parse(RUN / "input.json"))
    exported = populated(parse(RUN / "roundtrip-raw.json"))
    ck(roundtrip["passed"] and not roundtrip["differences"] and len(authored) == 21, "21 authored populated tables")
    for name, table in authored.items():
        ck(exported.get(name) == table, f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1 and "(notice #" not in runlog, "converter exact set")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    fm = matches(log, r"^Time: ([\d.]+) <TEACH-AIR-01,0> critical CM failure mode added, now \n 1 failures: \n  Failure Mode: (FM-SRU) on materiel: <TEACH-SRU-01,0> connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-LRU-01 - TEACH-SRU-01")
    mission_abort = matches(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission aborted:")
    mission_success = matches(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission success:")
    ck(len(fm) == len(mission_abort) == 3 and len(mission_success) == 0, "three explicit critical FM/mission aborts")
    ck(all(abs(fm[i][0] - mission_abort[i][0]) < 1e-5 for i in range(min(len(fm),len(mission_abort)))), "abort at each FM")
    history = {}
    for typ, mother in (("LRU", "TEACH-AIR-01"), ("SRU", "TEACH-LRU-01")):
        item = f"TEACH-{typ}-01"
        demand = matches(log, rf"^Time: ([\d.]+) <{item},0,BASE-01,0> Item demand arrives from pos <{mother},(?:0,)?BASE-01,0> item requiring maintenance is <{item},0,(\d+)>")
        issue = matches(log, rf"^Time: ([\d.]+) <{item},0,BASE-01,0> Take replacement item <{item},0,(\d+)> from stock")
        returned = matches(log, rf"^Time: ([\d.]+) <{item},0,BASE-01,0> Put back replacement item <{item},0,(\d+)> to stock")
        ck(len(demand) == len(issue) == len(returned) == 3, f"three {typ} physical cycles")
        if len(demand) == len(issue) == len(returned) == 3:
            for i in range(3):
                ck(demand[i][1] == returned[i][1], f"{typ} failed/repaired physical identity {i}")
                ck(demand[i][0] <= issue[i][0] < returned[i][0], f"{typ} demand/issue/return order {i}")
                if i:
                    ck(issue[i][1] == returned[i-1][1] and returned[i-1][0] < issue[i][0], f"{typ} repaired item reissue {i}")
            ck(len({identity for _,identity in demand}) == 3, f"{typ} distinct failed physical items")
        levels = [int(level) for level in re.findall(rf"^  Stock at: <{item},0,BASE-01,0> Level: (\d+) Items:", log, re.M)]
        ck(levels == [1,0,1,0,1,0,1], f"{typ} seven stock snapshots")
        history[typ] = {"demand": demand, "issue": issue, "return": returned, "stock_levels": levels}
    for i in range(3):
        if all(len(history[t]["demand"]) == 3 for t in ("LRU","SRU")):
            ck(history["LRU"]["demand"][i][0] <= history["SRU"]["demand"][i][0] and history["LRU"]["return"][i][0] < history["SRU"]["return"][i][0], f"nested cycle order {i}")
    for typ, tag, duration in (("system", "TEACH-AIR-01", 0.5), ("item", "TEACH-LRU-01", 0.75), ("item", "TEACH-SRU-01", 1.0)):
        started = matches(log, rf"^Time: ([\d.]+)  {typ} CM task (\d+) on <{tag},0(?:,\d+)?> started$")
        completed = matches(log, rf"^Time: ([\d.]+)  {typ} CM task (\d+) on <{tag},0(?:,\d+)?> completed$")
        ck(len(started) == len(completed) == 3, f"three {tag} CM tasks")
        if len(started) == len(completed) == 3:
            for i in range(3):
                ck(started[i][1] == completed[i][1] and abs(completed[i][0] - started[i][0] - duration) < 2e-4, f"{tag} CM duration {i}")
    requests = re.findall(r"^Time: [\d.]+ .* requests resources: (.*)$", log, re.M)
    ck(len(requests) == 15 and all(x == "no resources needed" for x in requests), "15 no-resource subtask requests")
    ck("Backorder added" not in log and "Backorder created" not in log, "no physical backorder")
    ck("Time: 33.953 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" in log, "last system ready")

    report = parse(RUN / "report-raw.json")
    summary, system, stock = (rows(report,n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck(len(summary) == 1 and summary[0]["MSUF"] == 0 and summary[0]["MSTF"] == 1, "summary all missions abort")
    ck(len(system) == len(stock) == 72, "72 half-hour report intervals")
    if len(system) == len(stock) == 72:
        for i,(sys,stk) in enumerate(zip(system,stock)):
            ck(sys["STINT"] == stk["STINT"] == i/2 and sys["ETINT"] == stk["ETINT"] == (i+1)/2, f"interval {i}")
            ck(stk["NBO"] == 0, f"NBO interval {i}")
        ck(sum(x["NFAIL"] for x in system) == sum(x["NREPT"] for x in system) == len(fm) == 3, "report FM/repair count")
        ck(sum(x["NDF"] for x in stock) == len(history["LRU"]["demand"]) == 3, "report system stock demand")
        ck(system[-1]["NSYRY"] == 1 and system[-1]["NSYA"] == 1, "terminal ready/available")
    verdict = {"schema": "simlox-f01-var03-author-replay/v1", "run_id": RUN.name,
               "checks": count, "passed": not failures, "failures": failures,
               "observed": {"FM_count": len(fm), "FM_times": [x[0] for x in fm],
                            "mission_aborts": len(mission_abort), "physical": history,
                            "report_bins": len(system), "terminal_ready": system[-1]["NSYRY"] if system else None},
               "scope": "fixed-seed bounded explicit nested CM candidate", "publication_state": "not_published"}
    output = HERE / "author-validation-2026-10-04.json"
    output.write_bytes((json.dumps(verdict, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": verdict["passed"], "checks": count, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
