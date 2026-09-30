"""Replay sealed native C07 cross-shift Y/N evidence and bounded behavior."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {"Y": "c07-cross-y-20260930-01", "N": "c07-cross-n-20260930-01"}
INPUT_SHA = {"Y": "cab26bedc1c5bbadadc82476c34e6e4bd6e71624bebeebe46e4ca342a616674d",
             "N": "5674f271d59e1026d16c094ea08f78b59fdb50c9e4d818cb35e48d57edd2faad"}
PARENT = HERE.parent / "C07-offshift-boundary-v1.0.0" / "draos-y-input.json"
PARENT_SHA = "fc7ca3caeefee1190a8497c8e5a32a463a96d17c426d4d97ee57673b49405a94"


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
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    demand(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"], "accepted parent fingerprint")
    demand(diff["pair_changed_tables"] == ["Control", "ProblemDescription"], "pair diff")
    observed: dict[str, dict] = {}
    for value, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        source = HERE / f"draos-{value.lower()}-input.json"
        invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        demand(sha(source) == sha(run / "input.json") == INPUT_SHA[value] == contract["input_sha256"][f"draos-{value.lower()}"], f"{value}: frozen input")
        demand(invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == f"draos-{value.lower()}", f"{value}: identity")
        demand(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{value}: session-0 SSH")
        demand(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{value}: queue and GUI")
        demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{value}: runtime source seal")
        for key, path in {"input": source, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            demand(closure["source_hashes_before"][key] == sha(path), f"{value}: {key} run-time fingerprint")
        demand(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{value}: invocation seal")
        demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{value}: steps")
        demand(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{value}: step success and GUI")
        for name, item in closure["raw"].items():
            path = run / name
            demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{value}: raw seal {name}")
        demand(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{value}: roundtrip checker")
        before = populated(parse_native(run / "input.json"))
        after = populated(parse_native(run / "roundtrip-raw.json"))
        demand(len(before) == 24 and all(after.get(n) == t for n, t in before.items()), f"{value}: 24 source tables")
        warnings: set[str] = set()
        for name in ("import.log", "export.log", "run.log", "report-export.log"):
            content = (run / name).read_text(encoding="utf-8-sig", errors="replace")
            demand(not re.search(r"\(error\s+#\d+\)", content, re.I), f"{value}: errors in {name}")
            warnings.update(re.findall(r"warning\s+#(\d+)", content, re.I))
        demand(warnings == {"108", "126"}, f"{value}: warnings")
        demand("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in (run / "run.log").read_text(encoding="utf-8-sig"), f"{value}: conversion")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        for hour, shift in ((8, 1), (9, 2), (10, 3), (11, 4)):
            demand(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>" in log, f"{value}: shift {hour}")
        if value == "Y":
            demand(len(re.findall(r"Time: 7\.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1", log)) == 2, "Y: two pre-shift bookings")
            demand("Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> is stopped due to shift change, time left= 1.5" in log, "Y: one worker paused at capacity reduction")
            demand("Time: 9  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 1.5 hours" in log, "Y: resumed after shift")
            demand("Time: 9.5  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed" in log, "Y: first work done")
            demand("Time: 10.5  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> completed" in log, "Y: second work done")
            demand("Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, "Y: mission success")
            demand("mission cancelled" not in log, "Y: no cancellation")
        else:
            demand("Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1" not in log, "N: zero pre-shift booking")
            demand("Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 2 hours" in log, "N: first shift work")
            demand("Time: 9  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to shift change, time left= 1" in log, "N: positive one-hour off-shift pause")
            demand("Time: 10  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours" in log, "N: same task resumed")
            demand("Time: 11  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed" in log, "N: first work done")
            demand("Time: 11  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> is stopped due to shift change, time left= 2" in log, "N: second work still undone")
            demand("Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled" in log and "mission starting" not in log, "N: deadline cancellation")
        report = parse_native(run / "report-raw.json")
        cols, rr = rows(report, "ResultSummary")
        demand(len(rr) == 1 and rr[0][cols.index("NREP")] == 1 and rr[0][cols.index("MTMF")] == (1 if value == "Y" else 0), f"{value}: mission summary")
        cols, rr = rows(report, "ResourceResultsTotal")
        demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and rr[0][cols.index("NRMO")] == 0, f"{value}: resource total")
        demand(math.isclose(rr[0][cols.index("NRUM")], (4 if value == "Y" else 2) / 36, abs_tol=1e-6), f"{value}: work use total")
        demand(math.isclose(rr[0][cols.index("NRW")], (1 if value == "Y" else 7) / 36, abs_tol=1e-6), f"{value}: waiting total")
        cols, series = rows(report, "ResourceResults")
        demand(len(series) == 72 and all(r[cols.index("NR")] == 2 for r in series), f"{value}: resource series")
        demand([series[i][cols.index("NRUM")] for i in (15, 16, 17, 18, 19, 20, 21, 22)] == ([2, 1, 1, 2, 1, 1, 0, 0] if value == "Y" else [0, 1, 1, 0, 0, 1, 1, 0]), f"{value}: work timing bins")
        demand([series[i][cols.index("NRW")] for i in (15, 16, 17, 18, 19, 20, 21, 22)] == ([0, 1, 1, 0, 0, 0, 0, 0] if value == "Y" else [2, 1, 1, 2, 2, 1, 1, 1]), f"{value}: wait timing bins")
        cols, series = rows(report, "SystemResults")
        demand(len(series) == 72 and series[-1][cols.index("NSYRY")] == 2 and all(r[cols.index("NFAIL")] == 0 for r in series), f"{value}: system terminal/failures")
        cols, stock = rows(report, "StockTotalResults")
        demand(len(stock) == 72 and all(r[cols.index(name)] == 0 for r in stock for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), f"{value}: stock zeros")
        observed[value] = {"run_id": run_id, "input_sha256": INPUT_SHA[value], "closure_sha256": sha(run / "closure.json"),
                           "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
                           "warnings": sorted(warnings), "mission_success": value == "Y"}
    return {"schema": "simlox-c07-cross-shift-author-validation/v1", "passed": not issues, "issues": issues,
            "exact_diff_sha256": sha(HERE / "exact-diff.json"), "observed": observed,
            "scope": "two explicit shifts, nominal two crew, in-shift one crew, DRAOS Y/N positive off-shift gap"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
