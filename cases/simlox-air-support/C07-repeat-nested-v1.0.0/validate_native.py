"""Author replay of sealed explicit, repeated and nested C07 shift profiles."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-cross-day-v1.0.0" / "cross-day-input.json"
PARENT_SHA = "b3780ff767af1653372e8dbd3f367f1fef9829b5fbf324cf6f354a19df558046"
RUNS = {"explicit": "c07-explicit-pair-20260930-01", "repeated": "c07-repeated-pair-20260930-01",
        "nested": "c07-nested-pair-20260930-01"}
INPUT_SHA = {"explicit": "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e",
             "repeated": "32f79158605a426edc80052f1188ec0c65f91d468d10a07ab748b7f0839c053e",
             "nested": "b8098b71dcec1f2bf49674c0fbbd7c84c36a03b2dc7468af2118c07e7eae3189"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    item = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in item["columns"]], [r for ins in item["instances"] for r in ins["rows"]]


def tables(path: Path) -> dict:
    return {t["name"]: t for t in parse_native(path)["model"]["tables"]}


def check() -> dict:
    issues: list[str] = []
    def demand(condition: bool, label: str) -> None:
        if not condition:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    exact = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    demand(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"] == exact["parent_sha256"], "accepted parent")
    base = tables(PARENT)
    logs: dict[str, bytes] = {}
    reports: dict[str, dict] = {}
    observed: dict[str, dict] = {}
    for variant, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        source = HERE / f"{variant}-input.json"
        child = tables(source)
        demand(base.keys() == child.keys() and sorted(n for n in base if base[n] != child[n]) == ["ProblemDescription", "ShiftProfile"], f"{variant}: actual two-table delta")
        demand(exact["variants"][variant]["changed_tables"] == ["ProblemDescription", "ShiftProfile"], f"{variant}: frozen delta")
        demand(sha(source) == sha(run / "input.json") == INPUT_SHA[variant] == contract["input_sha256"][variant] == exact["variants"][variant]["sha256"], f"{variant}: frozen input")
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant, f"{variant}: run identity")
        demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant}: SSH session")
        demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant}: queue and GUI")
        demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant}: runtime source seal")
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            demand(closure["source_hashes_before"][key] == sha(path), f"{variant}: {key} fingerprint")
        demand(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant}: invocation seal")
        demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant}: native steps")
        demand(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant}: step success and GUI")
        for name, item in closure["raw"].items():
            path = run / name
            demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{variant}: raw seal {name}")
        demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{variant}: roundtrip checker")
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        demand(len(before) == 24 and all(after.get(n) == t for n, t in before.items()), f"{variant}: 24 exact source tables")
        warnings: set[str] = set()
        for name in ("import.log", "export.log", "run.log", "report-export.log"):
            content = (run / name).read_text(encoding="utf-8-sig", errors="replace")
            demand(not re.search(r"\(error\s+#\d+\)", content, re.I), f"{variant}: errors in {name}")
            warnings.update(re.findall(r"warning\s+#(\d+)", content, re.I))
        demand(warnings == {"108", "126"} and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in (run / "run.log").read_text(encoding="utf-8-sig"), f"{variant}: conversion")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        for hour, shift in ((23, 1), (25, 2), (26, 3), (28, 4)):
            demand(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>" in log, f"{variant}: shift {hour}")
        for aircraft in (0, 1):
            frag = f"within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
            demand(f"Time: 23.5  subtask {aircraft} seqno 1 {frag} starts performing, planned to last for 2 hours" in log, f"{variant}: aircraft {aircraft} start")
            demand(f"Time: 25  subtask {aircraft} seqno 1 {frag} is stopped due to shift change, time left= 0.5" in log, f"{variant}: aircraft {aircraft} stop")
            demand(f"Time: 26  subtask {aircraft} seqno 1 {frag} starts performing, planned to last for 0.5 hours" in log, f"{variant}: aircraft {aircraft} resume")
            demand(f"Time: 26.5  subtask {aircraft} seqno 1 {frag} completed" in log, f"{variant}: aircraft {aircraft} complete")
        demand("Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "mission cancelled" not in log, f"{variant}: mission succeeds")
        report = parse_native(run / "report-raw.json")
        cols, rr = rows(report, "ResultSummary")
        demand(len(rr) == 1 and all(rr[0][cols.index(n)] == 1 for n in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")), f"{variant}: summary")
        cols, rr = rows(report, "ResourceResultsTotal")
        demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and math.isclose(rr[0][cols.index("NRUM")], 4 / 36, abs_tol=1e-6) and math.isclose(rr[0][cols.index("NRW")], 2 / 36, abs_tol=1e-6), f"{variant}: resource totals")
        cols, rr = rows(report, "ResourceResults")
        demand(len(rr) == 72 and all(x[cols.index("NR")] == 2 for x in rr), f"{variant}: resource bins")
        demand([rr[i][cols.index("NRUM")] for i in range(47, 54)] == [2, 2, 2, 0, 0, 2, 0] and [rr[i][cols.index("NRW")] for i in range(47, 54)] == [0, 0, 0, 2, 2, 0, 0], f"{variant}: use/wait timing")
        cols, rr = rows(report, "SystemResults")
        demand(len(rr) == 72 and rr[-1][cols.index("NSYRY")] == 2 and all(x[cols.index("NFAIL")] == 0 for x in rr), f"{variant}: terminal systems")
        demand([rr[i][cols.index("NSYMP")] for i in range(47, 54)] == [2, 2, 2, 2, 2, 2, 0] and [rr[i][cols.index("NSYMO")] for i in range(56, 59)] == [2, 2, 0], f"{variant}: system timing")
        cols, rr = rows(report, "StockTotalResults")
        demand(len(rr) == 72 and all(x[cols.index(n)] == 0 for x in rr for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant}: stock zeros")
        logs[variant] = (run / "model.log").read_bytes()
        reports[variant] = report
        observed[variant] = {"run_id": run_id, "input_sha256": INPUT_SHA[variant], "closure_sha256": sha(run / "closure.json"),
                             "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "warnings": sorted(warnings)}
    demand(len(set(logs.values())) == 1, "all three native event logs byte-identical")
    report_tables = {v: {t["name"]: t for t in doc["report"]["tables"]} for v, doc in reports.items()}
    for variant in ("repeated", "nested"):
        demand(sorted(n for n in report_tables["explicit"] if report_tables["explicit"][n] != report_tables[variant][n]) == ["ProblemDescription"], f"{variant}: report equality except description")
    return {"schema": "simlox-c07-repeat-nested-author-validation/v1", "passed": not issues, "issues": issues,
            "exact_diff_sha256": sha(HERE / "exact-diff.json"), "observed": observed,
            "scope": "one first-day explicit/repeated/nested two-window equivalence under DRAOS=N"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
