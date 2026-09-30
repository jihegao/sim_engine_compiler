"""Replay the sealed C07 explicit-zero versus omitted shift-resource pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-cross-shift-gap-v1.0.0" / "draos-y-input.json"
PARENT_SHA = "cab26bedc1c5bbadadc82476c34e6e4bd6e71624bebeebe46e4ca342a616674d"
RUNS = {"qty-zero": "c07-shift-qty-zero-20260930-02",
        "row-absent": "c07-shift-row-absent-20260930-02"}
INPUT_SHA = {"qty-zero": "f7cb574c61dae7383e175403664eaac5cc85cde3551e46a7be3a8af4e66e46de",
             "row-absent": "022bb73c6479b126bc5d6412141dfe19bbbc5a121323e430984340c047cc891e"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [r for inst in table["instances"] for r in inst["rows"]]


def check() -> dict:
    issues: list[str] = []

    def demand(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
    exact = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    demand(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"], "accepted parent")
    demand(exact["pair_changed_tables"] == ["ProblemDescription", "ShiftResource"], "exact pair delta")
    logs: dict[str, str] = {}
    reports: dict[str, dict] = {}
    observed: dict[str, dict] = {}
    for variant, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        source = HERE / f"{variant}-input.json"
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        demand(sha(source) == sha(run / "input.json") == INPUT_SHA[variant] == contract["input_sha256"][variant], f"{variant}: source fingerprint")
        demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant, f"{variant}: run identity")
        demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{variant}: SSH session")
        demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{variant}: queue and GUI")
        demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant}: runtime source stability")
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            demand(closure["source_hashes_before"][key] == sha(path), f"{variant}: runtime {key} seal")
        demand(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant}: invocation seal")
        demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{variant}: step order")
        demand(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant}: guarded step success")
        for name, item in closure["raw"].items():
            path = run / name
            demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{variant}: raw seal {name}")
        checker = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
        demand(checker["passed"] and checker["variant"] == variant, f"{variant}: native roundtrip checker")
        source_tables = {t["name"]: t for t in parse_native(run / "input.json")["model"]["tables"]}
        export_tables = {t["name"]: t for t in parse_native(run / "roundtrip-raw.json")["model"]["tables"]}
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        demand(len(before) == (24 if variant == "qty-zero" else 23) and all(after.get(n) == t for n, t in before.items()), f"{variant}: row-containing source equality")
        source_shift = source_tables["ShiftResource"]
        exported_shift = export_tables["ShiftResource"]
        demand(source_shift["columns"] == exported_shift["columns"], f"{variant}: ShiftResource schema")
        source_rows = [r for inst in source_shift["instances"] for r in inst["rows"]]
        exported_rows = [r for inst in exported_shift["instances"] for r in inst["rows"]]
        if variant == "qty-zero":
            demand(source_rows == exported_rows == [["DAY-OPEN", "BASE-01", "P-CREW", 0, None, None]], "explicit-zero row")
        else:
            demand(source_rows == [] and len(exported_rows) == 1 and exported_rows[0] == [None] * 6, "omitted row exports only null placeholder")
        warnings: set[str] = set()
        for name in ("import.log", "export.log", "run.log", "report-export.log"):
            content = (run / name).read_text(encoding="utf-8-sig", errors="replace")
            demand(not re.search(r"\(error\s+#\d+\)", content, re.I), f"{variant}: error in {name}")
            warnings.update(re.findall(r"warning\s+#(\d+)", content, re.I))
        demand(warnings == {"108", "126"}, f"{variant}: warnings")
        demand("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in (run / "run.log").read_text(encoding="utf-8-sig"), f"{variant}: conversion summary")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        for aircraft in (0, 1):
            sid = f"TEACH-AIR-01,{aircraft}"
            for hour, left in ((8, "1.5"), (10, "0.5")):
                demand(f"Time: {hour}  subtask {aircraft} seqno 1 within system preparation task {aircraft} on <{sid}> is stopped due to shift change, time left= {left}" in log, f"{variant}: stop {sid} {hour}")
            for hour, duration in ((7.5, "2"), (9, "1.5"), (11, "0.5")):
                demand(f"Time: {hour}  subtask {aircraft} seqno 1 within system preparation task {aircraft} on <{sid}> starts performing, planned to last for {duration} hours" in log, f"{variant}: start/resume {sid} {hour}")
            demand(f"Time: 11.5  subtask {aircraft} seqno 1 within system preparation task {aircraft} on <{sid}> completed" in log, f"{variant}: task complete {sid}")
        demand("Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, f"{variant}: mission")
        demand("mission cancelled" not in log, f"{variant}: no cancellation")
        report = parse_native(run / "report-raw.json")
        cols, rr = rows(report, "ResultSummary")
        demand(len(rr) == 1 and rr[0][cols.index("MTMF")] == 1 and rr[0][cols.index("NREP")] == 1, f"{variant}: summary")
        cols, rr = rows(report, "ResourceResultsTotal")
        demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and math.isclose(rr[0][cols.index("NRUM")], 4 / 36, abs_tol=1e-6) and math.isclose(rr[0][cols.index("NRW")], 4 / 36, abs_tol=1e-6), f"{variant}: four work/wait resource-hours")
        cols, rr = rows(report, "ResourceResults")
        demand(len(rr) == 72 and [rr[i][cols.index("NRUM")] for i in range(15, 23)] == [2, 0, 0, 2, 2, 0, 0, 2], f"{variant}: use bins")
        demand([rr[i][cols.index("NRW")] for i in range(15, 23)] == [0, 2, 2, 0, 0, 2, 2, 0], f"{variant}: wait bins")
        cols, rr = rows(report, "SystemResults")
        demand(len(rr) == 72 and rr[-1][cols.index("NSYRY")] == 2 and all(r[cols.index("NFAIL")] == 0 for r in rr), f"{variant}: terminal systems")
        cols, rr = rows(report, "StockTotalResults")
        demand(len(rr) == 72 and all(r[cols.index(name)] == 0 for r in rr for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{variant}: stock zeros")
        logs[variant] = log
        reports[variant] = report
        observed[variant] = {"run_id": run_id, "input_sha256": INPUT_SHA[variant], "closure_sha256": sha(run / "closure.json"),
                             "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"), "warnings": sorted(warnings)}
    demand(logs["qty-zero"] == logs["row-absent"], "native event logs differ")
    qt = {t["name"]: t for t in reports["qty-zero"]["report"]["tables"]}
    at = {t["name"]: t for t in reports["row-absent"]["report"]["tables"]}
    demand(sorted(n for n in qt.keys() | at.keys() if qt.get(n) != at.get(n)) == ["ProblemDescription"], "report differs beyond description")
    return {"schema": "simlox-c07-missing-shift-resource-author-validation/v1", "passed": not issues,
            "issues": issues, "exact_diff_sha256": sha(HERE / "exact-diff.json"), "observed": observed,
            "scope": "explicit zero versus omitted shift-resource row during two first-day shifts"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
