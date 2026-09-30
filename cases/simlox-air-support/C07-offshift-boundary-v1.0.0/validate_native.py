"""Replay the bounded C07 DRAOS pair from sealed native artifacts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {"Y": "c07-draos-y-20260930-02", "N": "c07-draos-n-20260930-01"}
SHA = {"Y": "fc7ca3caeefee1190a8497c8e5a32a463a96d17c426d4d97ee57673b49405a94",
       "N": "7f4e36bb0b4076c3f9645fa13e715e8827b6c348c906fd89dc3fead0cff8e2d5"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [r for inst in table["instances"] for r in inst["rows"]]


def check() -> dict:
    errors: list[str] = []

    def demand(value: bool, label: str) -> None:
        if not value:
            errors.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8-sig"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    demand(sha(HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json") == contract["parent_input_sha256"], "accepted parent fingerprint")
    demand(diff["pair_changed_tables"] == ["Control", "ProblemDescription"], "paired exact diff")
    observed: dict[str, dict] = {}
    for value, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        source = HERE / f"draos-{value.lower()}-input.json"
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        demand(sha(source) == sha(run / "input.json") == SHA[value] == contract["input_sha256"][f"draos-{value.lower()}"], f"{value}: source fingerprint")
        demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == f"draos-{value.lower()}", f"{value}: identity")
        demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{value}: session-0 SSH")
        demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{value}: mutex/GUI")
        demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{value}: runtime source seal")
        demand(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), f"{value}: contract seal")
        demand(closure["source_hashes_before"]["builder"] == sha(HERE / "build.py"), f"{value}: builder seal")
        demand(closure["source_hashes_before"]["checker"] == sha(HERE / "check_roundtrip.py"), f"{value}: checker seal")
        demand(closure["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"), f"{value}: runner seal")
        demand(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{value}: invocation seal")
        demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{value}: step sequence")
        demand(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{value}: step success/GUI preservation")
        for name, item in closure["raw"].items():
            path = run / name
            demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{value}: raw seal {name}")
        demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{value}: native roundtrip")
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        demand(len(before) == 24 and all(after.get(n) == t for n, t in before.items()), f"{value}: 24-table equality")
        warnings: set[str] = set()
        for name in ("import.log", "export.log", "run.log", "report-export.log"):
            log_text = (run / name).read_text(encoding="utf-8-sig", errors="replace")
            demand(not re.search(r"\(error\s+#\d+\)", log_text, re.I), f"{value}: conversion errors {name}")
            warnings.update(re.findall(r"warning\s+#(\d+)", log_text, re.I))
        demand(warnings == {"108", "126"}, f"{value}: warning set")
        demand("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in (run / "run.log").read_text(encoding="utf-8-sig"), f"{value}: conversion summary")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        start = "7.5" if value == "Y" else "7.75"
        done = "8" if value == "Y" else "8.25"
        mission_done = "9" if value == "Y" else "9.25"
        demand("Time: 7.75  resource shift 1 starting" in log and "Time: 10  resource shift 2 starting" in log, f"{value}: shift boundaries")
        for aircraft in (0, 1):
            sid = f"TEACH-AIR-01,{aircraft}"
            demand(len(re.findall(rf"Time: {start}  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> starts performing, planned to last for 0\.5 hours", log)) == 1, f"{value}: work start {sid}")
            demand(len(re.findall(rf"Time: {done}  subtask \d+ seqno 1 within system preparation task \d+ on <{sid}> completed", log)) == 1, f"{value}: work completion {sid}")
        demand(len(re.findall(rf"Time: {start}  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1", log)) == 2, f"{value}: typed crew booking")
        demand(f"Time: {done} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log, f"{value}: mission start")
        demand(f"Time: {mission_done} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, f"{value}: mission success")
        demand("mission cancelled" not in log, f"{value}: no cancellation")
        if value == "Y":
            demand("Time: 7.5  <P-CREW at <BASE-01,0>> allocated" in log, "Y: off-shift allocation")
            demand("Time: 7.75  resource shift 0 ended" in log and "planned to last for 0.25 hours" in log, "Y: shift-boundary rebooking")
        else:
            demand("Time: 7.5  <P-CREW at <BASE-01,0>> allocated" not in log, "N: no off-shift booking")
            demand("Tasks waiting for resources at: <BASE-01,0> 2" in log, "N: both tasks queued")
        report = parse_native(run / "report-raw.json")
        cols, rr = rows(report, "ResultSummary")
        demand(len(rr) == 1 and rr[0][cols.index("NREP")] == 1 and rr[0][cols.index("MTMF")] == 1, f"{value}: mission summary")
        cols, rr = rows(report, "ResourceResultsTotal")
        demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and rr[0][cols.index("NRMO")] == 0, f"{value}: resource count")
        demand((rr[0][cols.index("NRW")] == 0) == (value == "Y"), f"{value}: waiting ledger")
        cols, rr = rows(report, "ResourceResults")
        demand(len(rr) == 72 and rr[15][cols.index("NR")] == 2, f"{value}: resource series")
        cols, rr = rows(report, "SystemResults")
        demand(len(rr) == 72 and rr[-1][cols.index("NSYRY")] == 2, f"{value}: terminal aircraft")
        observed[value] = {"run_id": run_id, "input_sha256": SHA[value], "closure_sha256": sha(run / "closure.json"),
                           "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
                           "crew_work_start": start, "preparation_done": done, "mission_success": mission_done,
                           "resource_waiting_total": rows(report, "ResourceResultsTotal")[1][0][rows(report, "ResourceResultsTotal")[0].index("NRW")],
                           "warnings": sorted(warnings)}
    return {"schema": "simlox-c07-offshift-author-validation/v1", "passed": not errors, "issues": errors,
            "exact_diff_sha256": sha(HERE / "exact-diff.json"), "observed": observed,
            "scope": "fixed first-day shift with DRAOS Y/N and mission preparation before shift start"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
