"""Read-only author acceptance replay for PASSIVE 0.05-hour switchover."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var02-passive-zero-v1.0.0"
PARENT_RUN = PARENT / "runs/g10-var02-passive-zero-v100-ssh-20261003-01"
DIAGNOSTIC = HERE.parent / "G10-var04-passive-tswov-v1.0.0/runs/g10-var04-passive-tswov-v100-ssh-20261003-01"
INPUT_SHA = "f9d2dfa12c052764566e7abcbf16f9a74a18db212338e8e3718f32ce1e788ff4"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "model.log", "model_Prelife.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def times(log: str, pattern: str) -> list[float]:
    return [float(x) for x in re.findall(r"^Time: ([\d.]+) " + pattern, log, re.M)]


def validate(run: Path) -> dict:
    errors: list[str] = []
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            errors.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen child input", sha(HERE / "native-input.json") == sha(run / "input.json") == contract["native_input_sha256"] == INPUT_SHA)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"] and sha(PARENT_RUN / "closure.json") == contract["parent"]["native_closure_sha256"] and sha(PARENT / "cli-scope-signoff-2026-10-03.md") == contract["parent"]["signoff_sha256"])
    ck("excluded one-hour diagnostic bound", sha(DIAGNOSTIC / "closure.json") == contract["excluded_diagnostic"]["closure_sha256"])
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", invocation.get("case_id") == "G10" and invocation.get("case_version") == "1.0.1-candidate" and invocation.get("run_id") == run.name)
    ck("source parent bound", invocation.get("input_sha256") == INPUT_SHA and invocation.get("parent_sha256") == contract["parent"]["input_sha256"])
    for key, path in (("contract", HERE / "contract.json"), ("builder", HERE / "build.py"), ("checker", HERE / "check_roundtrip.py"), ("runner_script", HERE / "run_native_ssh.ps1"), ("parent_signoff", PARENT / "cli-scope-signoff-2026-10-03.md"), ("parent_closure", PARENT_RUN / "closure.json"), ("excluded_diagnostic_closure", DIAGNOSTIC / "closure.json"), ("manual", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), ("dictionary", Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"))):
        ck(f"bound source {key}", invocation["source_hashes_before"].get(key) == sha(path))
    ck("guarded session/GUI", invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True and "sshd.exe" in invocation.get("ssh_ancestor_names", []) and invocation.get("queue_mutex") == "Global\\SimloxIssue18NativeQueue" and invocation.get("gui", {}).get("pid") == 13340 and invocation.get("gui", {}).get("session_id") == 1)
    ck("closure source stable", closure.get("error") is None and closure.get("invocation_sha256") == sha(run / "invocation.json") and closure.get("source_hashes_before") == closure.get("source_hashes_after") == invocation.get("source_hashes_before"))
    ck("complete raw set", set(closure["raw"]) == RAW)
    for name, record in closure["raw"].items():
        path = run / name
        ck(f"sealed {name}", path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"])
    ck("five native steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    rt = load(run / "roundtrip-validation.json")
    ck("22-table roundtrip", rt["passed"] and rt["differences"] == [] and len(rt["populated_tables"]) == 22)
    source, exported = (parse_native(path) for path in (HERE / "native-input.json", run / "roundtrip-raw.json"))
    ck("all populated business rows", all(populated(exported).get(name) == table for name, table in populated(source).items()))
    redundancy = rows(exported, "model", "Redundancy")
    ck("PASSIVE positive delay 1-of-2", len(redundancy) == 1 and redundancy[0]["RLID"] == "TEACH-LRU-01" and redundancy[0]["SID"] == "TEACH-AIR-01" and redundancy[0]["NRL"] == 2 and redundancy[0]["NRLRQ"] == 1 and redundancy[0]["ACPA"] == "PASSIVE" and redundancy[0]["TSWOV"] == 0.05)
    ck("installed quantity two", any(r["IID"] == "TEACH-LRU-01" and r["MID"] == "TEACH-AIR-01" and r["QTYPM"] == 2 for r in rows(exported, "model", "ItemStructure")))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("clean conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and len(re.findall(r"\(warning #108\)", runlog)) == 1 and len(re.findall(r"\(warning #\d+\)", runlog)) == 1 and "(error #" not in runlog)
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    failure = times(log, r"<TEACH-AIR-01,0> noncritical random failure added")
    starts = times(log, r"<TEACH-AIR-01,0><TEACH-AIR-01\\IMPL_RED_LINK_0 \[IMPL_RED_LINK_0<0> -> IMPL_RED_LINK_0<1>\]>\. switch over started")
    stops = times(log, r"<TEACH-AIR-01,0><TEACH-AIR-01\\IMPL_RED_LINK_0 \[IMPL_RED_LINK_0<0> -> IMPL_RED_LINK_0<1>\]>\. Switch over stopped")
    ck("one noncritical LRU failure", len(failure) == 1 and abs(failure[0]-9.8829) < .0001 and "subitem failed: <TEACH-LRU-01,0,3>" in log)
    ck("completed positive native switch", len(starts) == len(stops) == 1 and starts == failure and abs(stops[0]-starts[0]-.05) < .0001 and "Will be finished at 9.9329" in log and "Switch over aborted" not in log)
    ck("no mission abort or critical failure", "mission aborted:" not in log and "critical random failure added" not in log.replace("noncritical random failure added", ""))
    successes = times(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission success:")
    ck("all three missions succeed", successes == [10, 22, 34])
    system_start = times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> started")
    system_end = times(log, r" system SURP task \d+ on <TEACH-AIR-01,0> completed")
    lru_start = times(log, r" item SURP task \d+ on <TEACH-LRU-01,0,3> started")
    lru_end = times(log, r" item SURP task \d+ on <TEACH-LRU-01,0,3> completed")
    sru_start = times(log, r" item DIRP task \d+ on <TEACH-SRU-01,0,4> started")
    sru_end = times(log, r" item DIRP task \d+ on <TEACH-SRU-01,0,4> completed")
    ck("base system replacement", system_start == [10] and system_end == [10.5])
    ck("nested LRU replacement", len(lru_start) == len(lru_end) == 1 and abs(lru_end[0]-lru_start[0]-.75) < .0002)
    ck("SRU direct repair", len(sru_start) == len(sru_end) == 1 and abs(sru_end[0]-sru_start[0]-1) < .0002)
    ck("LRU/SRU stock issue and closure", "Take replacement item <TEACH-LRU-01,0,1> from stock" in log and "Take replacement item <TEACH-SRU-01,0,0> from stock" in log and "Level: 2 Items:<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,3>" in log and "Level: 1 Items:<TEACH-SRU-01,0,4>" in log and "backorder" not in log.lower())
    report = parse_native(run / "report-raw.json")
    summary, systems, stocks = (rows(report, "report", name) for name in ("ResultSummary", "SystemResults", "StockTotalResults"))
    ck("one repetition all missions successful", len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["MSUF"] == 1)
    ck("72 contiguous system bins", len(systems) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i,r in enumerate(systems)))
    ck("one failure and replacement", sum(r["NFAIL"] for r in systems) == 1 and sum(r["NREPT"] for r in systems) == 1)
    ck("positive switch occupies correct bin", all(abs(r["NSYSW"]-(.1 if i == 19 else 0)) < 1e-6 for i,r in enumerate(systems)))
    ck("switch interval reduces mission operating fraction", abs(summary[0]["STMF"]-(1-.05/6)) < 1e-6 and abs(systems[19]["NSYMO"]-.9) < 1e-6 and abs(systems[19]["FTMO"]-.9) < 1e-6 and abs(systems[19]["STACC"]-.9) < 1e-6)
    ck("terminal aircraft ready", systems[-1]["NSYRY"] == systems[-1]["NSYA"] == 1 and systems[-1]["NSYRP"] == 0)
    ck("72 stock bins no backorder", len(stocks) == 72 and all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 and r["NBO"] == 0 for i,r in enumerate(stocks)))
    ck("one aggregate system demand", sum(r["NDF"] for r in stocks) == 1)
    parent_report = parse_native(PARENT_RUN / "report-raw.json")
    expected_differences = {
        ("ProblemDescription", 0, "PDESC"),
        ("ResultSummary", 0, "STMF"),
        *(("SystemResults", 19, name) for name in ("NSYMO", "FTMO", "STACC", "NSYSW")),
    }
    actual_differences = set()
    for old, new in zip(parent_report["report"]["tables"], report["report"]["tables"]):
        ck(f"matched report table {old['name']}", old["name"] == new["name"] and old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]))
        columns = [c["name"] for c in old["columns"]]
        old_rows = [row for instance in old["instances"] for row in instance["rows"]]
        new_rows = [row for instance in new["instances"] for row in instance["rows"]]
        ck(f"matched report rows {old['name']}", len(old_rows) == len(new_rows))
        actual_differences.update((old["name"], i, columns[j]) for i, (a, b) in enumerate(zip(old_rows, new_rows)) for j in range(len(columns)) if a[j] != b[j])
    ck("parent report only anticipated switch differences", actual_differences == expected_differences)
    return {"schema": "simlox-g10-var04-v101-author-validation/v1", "case_id": "G10", "variant_id": "G10.var04", "run_id": run.name, "passed": not errors, "checks": count, "differences": errors, "input_sha256": INPUT_SHA, "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
