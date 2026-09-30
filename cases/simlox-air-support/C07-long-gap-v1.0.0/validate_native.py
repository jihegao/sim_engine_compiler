"""Author replay of one sealed native C07 48-hour off-shift-gap run."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "c07-long-gap-20260930-01"
RUN = HERE / "runs" / RUN_ID
PARENT = HERE.parent / "C07-cross-day-v1.0.0" / "cross-day-input.json"
PARENT_SHA = "b3780ff767af1653372e8dbd3f367f1fef9829b5fbf324cf6f354a19df558046"
INPUT_SHA = "f22349f7a53ebd78355398fdef44cdb0685ac568563107726f33a05bcc3ee042"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    item = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in item["columns"]], [r for inst in item["instances"] for r in inst["rows"]]


def check() -> dict:
    issues: list[str] = []
    def demand(condition: bool, label: str) -> None:
        if not condition:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    source = HERE / "long-gap-input.json"
    demand(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"], "accepted parent fingerprint")
    demand(sha(source) == sha(RUN / "input.json") == INPUT_SHA == contract["input_sha256"] == diff["input_sha256"], "frozen input")
    demand(diff["changed_tables"] == contract["changed_tables"], "six-table source delta")
    parent_tables = {t["name"]: t for t in parse_native(PARENT)["model"]["tables"]}
    child_tables = {t["name"]: t for t in parse_native(source)["model"]["tables"]}
    demand(parent_tables.keys() == child_tables.keys() and
           sorted(n for n in parent_tables if parent_tables[n] != child_tables[n]) == contract["changed_tables"],
           "actual parent-to-child six-table delta")
    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    demand(invocation["run_id"] == closure["run_id"] == RUN_ID and invocation["variant"] == "long-gap", "run identity")
    demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], "session-0 SSH")
    demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "queue and GUI")
    demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "runtime source seal")
    for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        demand(closure["source_hashes_before"][key] == sha(path), f"run-time fingerprint {key}")
    demand(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps")
    demand(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "step success and GUI")
    for name, item in closure["raw"].items():
        path = RUN / name
        demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
    demand(json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], "roundtrip checker")
    before = populated(parse_native(RUN / "input.json"))
    after = populated(parse_native(RUN / "roundtrip-raw.json"))
    demand(len(before) == 24 and all(after.get(n) == t for n, t in before.items()), "24 exact business tables")
    warnings: set[str] = set()
    for name in ("import.log", "export.log", "run.log", "report-export.log"):
        content = (RUN / name).read_text(encoding="utf-8-sig", errors="replace")
        demand(not re.search(r"\(error\s+#\d+\)", content, re.I), f"errors in {name}")
        warnings.update(re.findall(r"warning\s+#(\d+)", content, re.I))
    demand(warnings == {"108", "126"}, "warnings 108/126 only")
    demand("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in (RUN / "run.log").read_text(encoding="utf-8-sig"), "zero conversion errors")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    demand("Time: 120  Start of day no 5" in log and "Time: 168  Start of day no 7" in log, "native 48-hour day markers")
    for hour, shift in ((119, 1), (120, 2), (168, 3), (170, 4)):
        demand(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>" in log, f"shift change {hour}")
    for aircraft in (0, 1):
        frag = f"within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
        demand(f"Time: 119.5  subtask {aircraft} seqno 1 {frag} starts performing, planned to last for 2 hours" in log, f"aircraft {aircraft} starts")
        demand(f"Time: 120  subtask {aircraft} seqno 1 {frag} is stopped due to shift change, time left= 1.5" in log, f"aircraft {aircraft} stops")
        demand(f"Time: 168  subtask {aircraft} seqno 1 {frag} starts performing, planned to last for 1.5 hours" in log, f"aircraft {aircraft} resumes")
        demand(f"Time: 169.5  subtask {aircraft} seqno 1 {frag} completed" in log and f"Time: 169.5 <TEACH-AIR-01,{aircraft}> preparation ended" in log, f"aircraft {aircraft} completes")
    demand("Time: 171 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 172 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "mission cancelled" not in log, "mission 171-172 succeeds")
    report = parse_native(RUN / "report-raw.json")
    cols, rr = table(report, "ResultSummary")
    demand(len(rr) == 1 and all(rr[0][cols.index(n)] == 1 for n in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")), "mission summary")
    cols, rr = table(report, "ResourceResultsTotal")
    demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and rr[0][cols.index("NRMO")] == 0, "resource total")
    demand(math.isclose(rr[0][cols.index("NRUM")], 4 / 180, abs_tol=1e-6) and math.isclose(rr[0][cols.index("NRW")], 96 / 180, abs_tol=1e-6), "crew work/wait totals")
    cols, rr = table(report, "ResourceResults")
    demand(len(rr) == 360 and all(x[cols.index("NR")] == 2 for x in rr), "360 resource bins")
    demand([rr[i][cols.index("NRUM")] for i in range(239, 241)] == [2, 0] and
           all(rr[i][cols.index("NRUM")] == 0 for i in range(240, 336)) and
           [rr[i][cols.index("NRUM")] for i in range(336, 339)] == [2, 2, 2], "work timing bins")
    demand(all(rr[i][cols.index("NRW")] == 2 for i in range(240, 336)) and
           all(rr[i][cols.index("NRW")] == 0 for i in list(range(238, 240)) + list(range(336, 340))), "48-hour wait bins")
    cols, rr = table(report, "SystemResults")
    demand(len(rr) == 360 and rr[-1][cols.index("NSYRY")] == 2 and all(x[cols.index("NFAIL")] == 0 for x in rr), "system ready and failure bins")
    demand(all(rr[i][cols.index("NSYMP")] == 2 for i in range(239, 339)) and rr[339][cols.index("NSYMP")] == 0, "preparation system bins")
    demand([rr[i][cols.index("NSYMO")] for i in range(342, 345)] == [2, 2, 0], "mission occupancy bins")
    cols, rr = table(report, "StockTotalResults")
    demand(len(rr) == 360 and all(x[cols.index(n)] == 0 for x in rr for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "zero stock movement")
    return {"schema": "simlox-c07-long-gap-author-validation/v1", "passed": not issues, "issues": issues,
            "run_id": RUN_ID, "input_sha256": INPUT_SHA, "closure_sha256": sha(RUN / "closure.json"),
            "model_log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"),
            "warnings": sorted(warnings), "scope": "one DRAOS=N 48-hour inactive gap; calendar weekend and recurrence unverified"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
