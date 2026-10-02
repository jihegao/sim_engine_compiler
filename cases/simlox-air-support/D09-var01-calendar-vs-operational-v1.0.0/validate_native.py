"""Author replay of the frozen D09.var01 calendar/operational NCFTL pair."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D08-var03-criticality-v1.0.0"
STOCK_PARENT = HERE.parent / "E02-zero-stock-local-backorder-v1.0.0"
RUNS = {
    "calendar": ("d09-var01-calendar-v100-ssh-20261002-01", "c9645fcb8a567c89077e830916839a33dd63574b9249893f469a2ae47e5e6cce", "10.0829", "11.3329", "11.5829", "1.3329"),
    "operational": ("d09-var01-operational-v100-ssh-20261002-01", "1caac8f4cdb97a6e930b5d612360df601b541b75f99ce337f273aa334f4f460a", "20.0829", "21.4158", "21.6658", "11.4158"),
}
CLOSURE_SHA = {
    "calendar": "fb536519c47bb0d6bc1a3408066500fd310261d9c939c3796b3f62b02a7c9430",
    "operational": "db74569ea507344fb3e23498167979bca5b898598b66d4832deb22ee63652b04",
}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def report_tables(path: Path) -> dict:
    tables = parse_native(path)["report"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def main() -> int:
    differences: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            differences.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("contract and diff fixed", sha(HERE / "contract.json") == "8995baf5ccc4ef98b9ac46bb112081b03bc80cc876678129e60ccb23006a594e" and sha(HERE / "exact-diff.json") == "5add849e4d34e9206cca47e9445ca1f12547fe905381c4c817e173a5eb4af68f")
    ck("catalog identity", contract["case_id"] == "D09" and contract["variant_id"] == "D09.var01" and contract["publication_state"] == "not_published")
    ck("accepted D08 parent", sha(PARENT / "native-input-traditional.json") == contract["accepted_parent"]["input_sha256"] and sha(PARENT / "runs/d08-var03-traditional-v100-ssh-20261002-01/closure.json") == contract["accepted_parent"]["native_closure_sha256"])
    ck("accepted E02 precedent", sha(STOCK_PARENT / "native-input.json") == contract["stock_shortage_precedent"]["input_sha256"] and sha(STOCK_PARENT / "runs/e02-v100-ssh-20260929-01/closure.json") == contract["stock_shortage_precedent"]["native_closure_sha256"])
    for arm, (run_id, input_sha, escalation, repaired_item, ready, wait) in RUNS.items():
        run = HERE / "runs" / run_id
        ck(f"{arm} child/diff", sha(HERE / f"native-input-{arm}.json") == input_sha == contract["arms"][arm]["input_sha256"] == diff["children"][arm]["input_sha256"])
        ck(f"{arm} closure SHA", sha(run / "closure.json") == CLOSURE_SHA[arm])
        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} invocation source", invocation["case_id"] == "D09" and invocation["variant_id"] == "D09.var01" and invocation["arm"] == arm and invocation["input_sha256"] == input_sha and invocation["parent_sha256"] == contract["accepted_parent"]["input_sha256"] and invocation["stock_parent_sha256"] == contract["stock_shortage_precedent"]["input_sha256"])
        ck(f"{arm} guarded session", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} source closure", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
        ck(f"{arm} five native steps", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True for step in steps))
        ck(f"{arm} exact raw set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        before, after = populated(parse_native(run / "input.json")), populated(parse_native(run / "roundtrip-raw.json"))
        roundtrip = read(run / "roundtrip-validation.json")
        ck(f"{arm} authored 18-table roundtrip", sha(run / "input.json") == input_sha and roundtrip["passed"] is True and not roundtrip["differences"] and len(before) == 18 and all(after.get(name) == value for name, value in before.items()))
        conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
        ck(f"{arm} nonempty native artifacts", (run / "model.sxo").stat().st_size > 1000 and (run / "model.log").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} first noncritical failure and success", "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added" in log and "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log)
        ck(f"{arm} initial NCF queue", "Time: 10 <TEACH-AIR-01,BASE-01,0> System NCF ready" in log and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log and "Time: 10  system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in log)
        ck(f"{arm} escalation", f"Time: {escalation} <TEACH-AIR-01,0> failure becomes critical:" in log and f"Time: {escalation} <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> changed to critical" in log)
        ck(f"{arm} no physical repair before escalation", not re.search(r"Time: (?:[0-9.]+)  remove subitem.*starts performing", log[: log.index(f"Time: {escalation} <TEACH-AIR-01,0> failure becomes critical:")]))
        ck(f"{arm} same repaired LRU clears backorder", f"Time: {repaired_item} <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>" in log and f"Time: {repaired_item} <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was {wait}" in log and f"Time: {repaired_item}  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>" in log)
        ck(f"{arm} repair and ready", f"Time: {ready}  system SURP task 0 on <TEACH-AIR-01,0> completed" in log and f"Time: {ready} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
        missions = re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission (success|aborted):", log)
        ck(f"{arm} mission outcomes", missions == ([('10', 'success'), ('22', 'success'), ('34', 'success')] if arm == "calendar" else [('10', 'success'), ('20.0829', 'aborted'), ('34', 'success')]))
        if arm == "calendar":
            ck("calendar between-mission escalation", log.index("Time: 10 <BASIC-MISSION") < log.index("Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical:") < log.index("Time: 19 <TEACH-UNIT> mission ordered"))
            ck("calendar no second-mission abort", "mission aborted:" not in log)
        else:
            ck("operational pending-task mission allocation/pause", "Time: 19 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system" in log and "Time: 19 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> paused" in log)
            ck("operational midmission abort and critical resume", "Time: 20 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting" in log and "Time: 20.0829 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted:" in log and "Time: 20.1658 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> continued" in log)
        report = report_tables(run / "report-raw.json")
        ck(f"{arm} report tables", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report))
        summary, system, stock = rows(report["ResultSummary"]), rows(report["SystemResults"]), rows(report["StockTotalResults"])
        ck(f"{arm} 72 aligned half-hour bins", len(summary) == 1 and len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} failures repairs demand", sum(row["NFAIL"] for row in system) == sum(row["NREPT"] for row in system) == sum(row["NDF"] for row in stock) == 1)
        ck(f"{arm} backorder area/terminal", abs(sum(row["NBO"] for row in stock) / 2 - float(wait)) < 1e-3 and stock[-1]["NBO"] == 0 and system[-1]["NSYRY"] == 1)
        ck(f"{arm} mission summary", abs(summary[0]["MSUF"] - (1 if arm == "calendar" else 2 / 3)) < 1e-5)
    result = {"schema": "simlox-d09-var01-ncftl-v100-author-validation/v1", "passed": not differences, "checks": checks, "differences": differences, "scope": "bounded_one_seed_calendar_vs_operational_pending_repair_native_cli", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
