"""Author replay of D09.var04 part, crew, and supplied native CLI arms."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ARMS = ("part-short", "crew-short", "supplied")
RUNS = {arm: HERE / "runs" / f"d09-var04-{arm}-v100-ssh-20261002-01" for arm in ARMS}
CLOSURES = {
    "part-short": "f78fbca87f943c5068cdb2f6fe1e98e799ca2cf6484996497cc0c45d9c345f32",
    "crew-short": "2e5d547b85635d9cc2b0117a54e8a09f604ddd919086c826c2becd3bce8fe15e",
    "supplied": "d1e00d178915fa9c10489c6f1934badee8a53c5dfe3b8b9a713bb7e2ed8596a9",
}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    columns = [col["name"] for col in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(name: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(name)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("frozen contract/diff", contract["case_id"] == "D09" and contract["variant_id"] == "D09.var04" and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    parent = HERE.parent / "D09-var01-calendar-vs-operational-v1.0.0"
    donor = HERE.parent / "I01-var03-three-allocation-joint-v1.0.0"
    ck("accepted parent", sha(parent / "native-input-calendar.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_input_sha256"] and sha(parent / "runs/d09-var01-calendar-v100-ssh-20261002-01/closure.json") == contract["accepted_parent"]["native_closure_sha256"])
    ck("accepted resource donor", sha(donor / "one-base-input.json") == contract["accepted_resource_and_task_donor"]["input_sha256"] and sha(donor / "runs/i01-var03-three-one-base-v100-ssh-20261002-01/closure.json") == contract["accepted_resource_and_task_donor"]["native_closure_sha256"])
    ck("two isolated controls", diff["arm_contrasts"]["part_to_supplied"]["StockAllocation"] == {"STSIZ": {"before": 0, "after": 1}} and set(diff["arm_contrasts"]["part_to_supplied"]) == {"ProblemDescription", "StockAllocation"} and diff["arm_contrasts"]["crew_to_supplied"]["ResourceAllocation"] == {"RQTY": {"before": 0, "after": 1}} and set(diff["arm_contrasts"]["crew_to_supplied"]) == {"ProblemDescription", "ResourceAllocation"})
    logs: dict[str, str] = {}
    reports: dict[str, dict[str, list[dict]]] = {}
    for arm in ARMS:
        run = RUNS[arm]
        source_sha = contract["arms"][arm]["input_sha256"]
        ck(f"{arm} input and closure", sha(HERE / f"native-input-{arm}.json") == sha(run / "input.json") == source_sha == diff["children"][arm]["input_sha256"] and sha(run / "closure.json") == CLOSURES[arm])
        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} sealed source and invocation", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["input"] == source_sha and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json") and closure["source_hashes_before"]["exact_diff"] == contract["exact_diff_sha256"])
        ck(f"{arm} SSH/GUI/mutex", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} five completed steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
        ck(f"{arm} exact raw set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        source, exported = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        roundtrip = read(run / "roundtrip-validation.json")
        ck(f"{arm} 23-table roundtrip", roundtrip["passed"] is True and not roundtrip["differences"] and len(source) == 23 and all(exported.get(name) == value for name, value in source.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} zero-error conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
        ck(f"{arm} nonempty native outputs", all((run / name).stat().st_size > 1000 for name in ("model.sxo", "model.log", "report-raw.json")))
        log = logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} first fault/mission", "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added" in log and "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log)
        tables = {table["name"]: table for table in parse_native(run / "report-raw.json")["report"]["tables"]}
        names = ("ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal")
        ck(f"{arm} required report tables", set(names).issubset(tables))
        reports[arm] = {name: rows(tables[name]) for name in names}
        system, stock, resource = (reports[arm][name] for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
        ck(f"{arm} 72 aligned half-hour bins", len(system) == len(stock) == len(resource) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == resource[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == resource[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} one failure/demand", sum(r["NFAIL"] for r in system) == sum(r["NDF"] for r in stock) == 1)
        ck(f"{arm} terminal no backorder", stock[-1]["NBO"] == 0)
    part, crew, supplied = (logs[arm] for arm in ARMS)
    ck("same fault time, distinct stock-initialized identity", "subitem failed: <TEACH-LRU-01,0,0>" in part and "subitem failed: <TEACH-LRU-01,0,1>" in crew and "subitem failed: <TEACH-LRU-01,0,1>" in supplied)
    ck("both shortages escalate at calendar limit", all("Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical:" in text for text in (part, crew)) and "failure becomes critical:" not in supplied)
    ck("part waits then critical repair", "Time: 10  system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in part and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in part and "Time: 10.0829 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> changed to critical  : repair wait notice exist" in part and "Time: 10.0829  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1" in part and "Time: 11.3329 <TEACH-LRU-01,0,BASE-01,0> Backorder removed" in part and "Time: 11.5829  system SURP task 0 on <TEACH-AIR-01,0> completed" in part)
    ck("crew waits despite reserved replacement", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in crew and crew.count("request for: 1 failed") >= 3 and "Time: 10.0829 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> changed to critical  : replacement item has arrived" in crew and "nbr resourcewait increased" in crew and "Backorder added" not in crew and "starts performing" not in crew and "Item requiring maintenance arrives" not in crew)
    ck("supplied starts active repair before limit", "Time: 10  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing" in supplied and "Time: 10  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1" in supplied and "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in supplied and "Backorder added" not in supplied)
    ck("mission dispositions", [re.findall(r"mission (success|cancelled|aborted):", logs[arm]) for arm in ARMS] == [["success"] * 3, ["success", "cancelled", "cancelled"], ["success"] * 3])
    ck("crew cancellation times", "Time: 20.3333 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in crew and "Time: 32.3333 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission cancelled:" in crew)
    ck("repair totals", [sum(r["NREPT"] for r in reports[arm]["SystemResults"]) for arm in ARMS] == [1, 0, 1])
    ck("terminal aircraft state", [reports[arm]["SystemResults"][-1]["NSYRY"] for arm in ARMS] == [1, 0, 1] and reports["crew-short"]["SystemResults"][-1]["NSYWR"] == 1)
    ck("resource availability/use/wait", [reports[arm]["ResourceResults"][-1]["NR"] for arm in ARMS] == [1, 0, 1] and all(abs(sum(r["NRUM"] for r in reports[arm]["ResourceResults"]) - expected) < 1e-6 for arm, expected in zip(ARMS, (.5, 0, .5))) and [sum(r["NRW"] for r in reports[arm]["ResourceResults"]) for arm in ARMS] == [0, 52, 0])
    ck("stock backorder occupancy", abs(sum(r["NBO"] for r in reports["part-short"]["StockTotalResults"]) / 2 - 1.3329) < 1e-4 and all(sum(r["NBO"] for r in reports[arm]["StockTotalResults"]) == 0 for arm in ("crew-short", "supplied")))
    ck("mission success fractions", [round(reports[arm]["ResultSummary"][0]["MSUF"], 6) for arm in ARMS] == [1, round(1 / 3, 6), 1])
    result = {"schema": "simlox-d09-var04-shortage-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_part_vs_crew_shortage_at_ncftl_escalation_native_cli", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
