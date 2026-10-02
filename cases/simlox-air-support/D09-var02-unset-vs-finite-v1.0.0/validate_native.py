"""Author replay of D09.var02 unset NCFTL against accepted finite control."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D09-var01-calendar-vs-operational-v1.0.0"
PREREQUISITE = HERE.parent / "D08-var03-criticality-v1.0.0"
RUN_ID = "d09-var02-unset-v100-ssh-20261002-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = PARENT / "runs/d09-var01-calendar-v100-ssh-20261002-01"
INPUT_SHA = "6303f1fd3013c43f7a6c5584a324d1fe0f32befc34548c906a11233bcb269f84"
CLOSURE_SHA = "58b040c8cef5a97ab0c65848b69bb0e022716d45934d84fcb7e9cf78014e73a3"
CONTRACT_SHA = "abe24b14237b95f5e0438f9f92015a15a504b022c16731d8930440a8defc3009"
DIFF_SHA = "2362c230adfe9f0082e3413259aeaeb7816b41d347b5dae2140967453cf7d5b3"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def report(path: Path) -> dict:
    tables = parse_native(path)["report"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def main() -> int:
    issues: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            issues.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("contract identity and hash", sha(HERE / "contract.json") == CONTRACT_SHA and contract["case_id"] == "D09" and contract["variant_id"] == "D09.var02")
    ck("diff identity and hash", sha(HERE / "exact-diff.json") == DIFF_SHA and diff["child_input_sha256"] == INPUT_SHA and diff["changed_tables"]["Item"] == {"NCFTL": {"before": 0.2, "after": None}} and diff["identical_tables"] == 29)
    ck("accepted finite parent", sha(PARENT / "native-input-calendar.json") == contract["accepted_finite_parent"]["input_sha256"] and sha(PARENT_RUN / "closure.json") == contract["accepted_finite_parent"]["native_closure_sha256"])
    ck("accepted noncritical prerequisite", sha(PREREQUISITE / "native-input-traditional.json") == contract["earlier_noncritical_prerequisite"]["input_sha256"] and sha(PREREQUISITE / "runs/d08-var03-traditional-v100-ssh-20261002-01/closure.json") == contract["earlier_noncritical_prerequisite"]["native_closure_sha256"])
    ck("child source/closure", sha(HERE / "native-input-unset.json") == INPUT_SHA == contract["arms"]["unset_candidate"]["input_sha256"] and sha(RUN / "closure.json") == CLOSURE_SHA)
    invocation, closure, steps = (read(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("invocation", invocation["case_id"] == "D09" and invocation["variant_id"] == "D09.var02" and invocation["arm"] == "unset" and invocation["input_sha256"] == INPUT_SHA and invocation["parent_sha256"] == contract["accepted_finite_parent"]["input_sha256"] and invocation["prerequisite_sha256"] == contract["earlier_noncritical_prerequisite"]["input_sha256"])
    ck("SSH/GUI/queue", invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("stable source closure", closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json") and invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"] and closure["source_hashes_before"]["contract"] == CONTRACT_SHA and closure["source_hashes_before"]["exact_diff"] == DIFF_SHA)
    ck("five native steps", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True for step in steps))
    ck("exact raw set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    before, after = populated(parse_native(RUN / "input.json")), populated(parse_native(RUN / "roundtrip-raw.json"))
    rt = read(RUN / "roundtrip-validation.json")
    ck("18 authored-table roundtrip", sha(RUN / "input.json") == INPUT_SHA and rt["passed"] is True and not rt["differences"] and len(before) == 18 and all(after.get(name) == value for name, value in before.items()))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion and Counter(re.findall(r"\(warning #(\d+)\)", conversion)) == Counter({"108": 1}))
    ck("nonempty SXO/report/log", (RUN / "model.sxo").stat().st_size > 1000 and (RUN / "report-raw.json").stat().st_size > 1000 and (RUN / "model.log").stat().st_size > 1000)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    finite = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("same first noncritical fault", "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added" in log and "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added" in finite)
    ck("waiting task/backorder", "Time: 10  system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in log and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log and "Time: 10 <TEACH-AIR-01,BASE-01,0> System NCF ready" in log)
    ck("three successful missions", re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission (success|aborted):", log) == [("10", "success"), ("22", "success"), ("34", "success")])
    ck("pending task pauses and resumes", re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> paused", log) == ["19", "31"] and re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> continued", log) == ["22", "34"])
    ck("no escalation or physical repair", "failure becomes critical:" not in log and "changed to critical" not in log and "remove subitem subtask" not in log and "item DIRP task" not in log and "system SURP task 0 on <TEACH-AIR-01,0> completed" not in log)
    ck("backorder remains", "Backorder removed" not in log and "Replacement item arrives" not in log)
    ck("finite contrast", "Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical:" in finite and "Time: 11.3329 <TEACH-LRU-01,0,BASE-01,0> Backorder removed" in finite and "Time: 11.5829  system SURP task 0 on <TEACH-AIR-01,0> completed" in finite)
    child_tables, finite_tables = report(RUN / "report-raw.json"), report(PARENT_RUN / "report-raw.json")
    ck("report tables", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(child_tables))
    summary, system, stock = (rows(child_tables[name]) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
    finite_system, finite_stock = (rows(finite_tables[name]) for name in ("SystemResults", "StockTotalResults"))
    ck("72 aligned half-hour bins", len(summary) == 1 and len(system) == len(stock) == len(finite_system) == len(finite_stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
    ck("one unrepaired fault/demand", sum(row["NFAIL"] for row in system) == 1 and sum(row["NREPT"] for row in system) == 0 and sum(row["NDF"] for row in stock) == 1)
    ck("backorder through horizon", abs(sum(row["NBO"] for row in stock) / 2 - 26) < 1e-6 and stock[-1]["NBO"] == 1 and finite_stock[-1]["NBO"] == 0)
    ck("ready and mission success", system[-1]["NSYRY"] == 1 and abs(summary[0]["MSUF"] - 1) < 1e-6)
    result = {"schema": "simlox-d09-var02-unset-v100-author-validation/v1", "passed": not issues, "checks": checks, "differences": issues, "scope": "bounded_unset_vs_finite_calendar_ncftl_zero_stock_native_cli", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}, indent=2))
        raise SystemExit(1)
