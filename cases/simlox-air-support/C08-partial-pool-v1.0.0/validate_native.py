"""Author replay of the sealed C08.var03 staggered partial-pool pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENTS = {
    "stagger-unlimited": (HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json", "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"),
    "stagger-maxut": (HERE.parent / "C08-shift-maxut-v1.0.0" / "maxut-one-input.json", "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5"),
}
INPUTS = {
    "stagger-unlimited": ("f69be976c2afa0515670f76737397b3fc1258b0fcc16a1243086ded579f34ee4", "c08-partial-unlimited-20260930-01"),
    "stagger-maxut": ("415c1a918dd643f3db869e28c02ceebbde68c887847df222ec3780ae9c4deb75", "c08-partial-maxut-20260930-01"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(doc: dict, section: str) -> dict:
    return {t["name"]: t for t in doc[section]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for ins in table["instances"] for row in ins["rows"]]


def selected(table: dict, column: str) -> list:
    index = [c["name"] for c in table["columns"]].index(column)
    return [r[index] for r in rows(table)]


def check() -> dict:
    issues: list[str] = []

    def require(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    require(contract["accepted_parent_publication_ids"] == ["C07.var04.repeat_nested_two_window.1.0.0", "C08.var02.shift_maxut_one.1.0.0"], "accepted parent publications")
    sources = {}
    for variant, (input_sha, _) in INPUTS.items():
        source = HERE / f"{variant}-input.json"
        parent, parent_sha = PARENTS[variant]
        require(sha(parent) == parent_sha == diff["accepted_parent_input_sha256"][variant], f"{variant} accepted parent hash")
        require(sha(source) == input_sha == contract["input_sha256"][variant] == diff["child_input_sha256"][variant], f"{variant} frozen input hash")
        a = tables(parse_native(parent), "model")
        b = tables(parse_native(source), "model")
        require(a.keys() == b.keys() and sorted(n for n in a if a[n] != b[n]) == ["MissionType", "OperationProfile", "ProblemDescription"], f"{variant} exact parent tables")
        require(rows(a["MissionType"])[0][2:4] == [2, 2] and rows(b["MissionType"])[0][2:4] == [1, 1], f"{variant} one-aircraft missions")
        require(len(rows(a["OperationProfile"])) == 1 and [r[2] for r in rows(b["OperationProfile"])] == [28, 28.5] and rows(b["OperationProfile"])[0] == rows(a["OperationProfile"])[0], f"{variant} two staggered rows")
        require(a["ShiftResource"] == b["ShiftResource"] and rows(b["ShiftResource"])[0][3] == 2, f"{variant} pool unchanged")
        sources[variant] = b
    u, m = sources["stagger-unlimited"], sources["stagger-maxut"]
    require(sorted(n for n in u if u[n] != m[n]) == ["ProblemDescription", "ShiftResource"] and rows(u["ShiftResource"])[0] == ["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None] and rows(m["ShiftResource"])[0] == ["DAY-OPEN", "BASE-01", "P-CREW", 2, 1, None], "paired MAXUT sole business difference")

    logs: dict[str, str] = {}
    reports: dict[str, dict] = {}
    for variant, (input_sha, run_id) in INPUTS.items():
        run = HERE / "runs" / run_id
        inv = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
        parent, parent_sha = PARENTS[variant]
        require(inv["run_id"] == closure["run_id"] == run_id and inv["variant"] == variant and inv["case_id"] == "C08", f"{variant} run identity")
        require(inv["input_sha256"] == input_sha and inv["parent_sha256"] == parent_sha, f"{variant} invocation fingerprints")
        require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{variant} session0 SSH mutex")
        require(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, f"{variant} GUI identity")
        require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], f"{variant} source stability")
        for key, path in {"input": HERE / f"{variant}-input.json", "parent": parent, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
            require(closure["source_hashes_before"][key] == sha(path), f"{variant} source seal {key}")
        require(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{variant} invocation seal")
        require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), f"{variant} five guarded steps")
        for name, item in closure["raw"].items():
            path = run / name
            require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"{variant} raw seal {name}")
        require(json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], f"{variant} roundtrip checker")
        source_rows = populated(parse_native(run / "input.json"))
        export_rows = populated(parse_native(run / "roundtrip-raw.json"))
        require(len(source_rows) == 24 and all(export_rows.get(n) == t for n, t in source_rows.items()), f"{variant} 24-table roundtrip")
        calc = (run / "run.log").read_text(encoding="utf-8-sig")
        require(not re.findall(r"error\s+#\d+", calc, re.I) and "Errors: 0, Warnings: 2, Notes: 0" in calc and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"}, f"{variant} zero-error conversion")
        require((run / "model.sxo").stat().st_size > 4 and (run / "report-raw.json").stat().st_size > 4, f"{variant} nonempty output")
        logs[variant] = (run / "model.log").read_text(encoding="utf-8-sig")
        reports[variant] = tables(parse_native(run / "report-raw.json"), "report")

    control, limited = logs["stagger-unlimited"], logs["stagger-maxut"]
    for variant, log in logs.items():
        for aircraft, start in ((0, 23.5), (1, 24)):
            ident = f"<TEACH-AIR-01,{aircraft}>"
            require(f"Time: {start} {ident} preparation started" in log and f"Time: {start}  subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident} starts performing" in log, f"{variant} aircraft {aircraft} staggered start")
        require("Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "Time: 28.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting" in log and "Time: 29.5 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success" in log, f"{variant} two mission outcomes")
        require("Time: 29.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log, f"{variant} terminal two aircraft ready")
    require("out of utilisation time" not in control and "is stopped due to resource time-out" not in control, "unlimited control no MAXUT stop")
    require("Time: 25  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to shift change, time left= 0.5" in control and "Time: 25  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> is stopped due to shift change, time left= 1" in control, "control first shift boundary")
    require("Time: 26.5 <TEACH-AIR-01,0> preparation ended" in control and "Time: 27 <TEACH-AIR-01,1> preparation ended" in control, "control reset and finishes")
    require("Time: 24.75  <P-CREW at <BASE-01,0>> out of utilisation time" in limited and "Time: 26  resource shift 3 starting" in limited, "limited pool timeout and reset")
    require("Time: 24  <P-CREW at <BASE-01,0>> set time to max utilisation: 0.75" in limited, "partial-busy pool recomputation")
    require("Time: 24.75  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to resource time-out, time left= 0.75" in limited and "Time: 24.75  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> is stopped due to resource time-out, time left= 1.25" in limited, "different remaining work at pooled stop")
    require("Time: 26.75 <TEACH-AIR-01,0> preparation ended" in limited and "Time: 27.25 <TEACH-AIR-01,1> preparation ended" in limited, "limited reset and finishes")

    a, b = reports["stagger-unlimited"], reports["stagger-maxut"]
    require(a.keys() == b.keys() and sorted(n for n in a if a[n] != b[n]) == ["ProblemDescription", "ResourceResults", "ResourceResultsTotal", "SystemResults"], "bounded report differences")
    require(a["ResultSummary"] == b["ResultSummary"] and a["StockTotalResults"] == b["StockTotalResults"], "mission totals and stock equal")
    for variant, expected_work, expected_wait, wait_hours in (
        ("stagger-unlimited", {47: 1, 48: 2, 49: 2, 52: 2, 53: 1}, {50: 2, 51: 2}, 2),
        ("stagger-maxut", {47: 1, 48: 2, 49: 1, 52: 2, 53: 1.5, 54: 0.5}, {49: 1, 50: 2, 51: 2}, 2.5),
    ):
        report = reports[variant]
        summary = report["ResultSummary"]
        require(len(rows(summary)) == 1 and all(selected(summary, n) == [1] for n in ("MTMF", "MSTF", "MSUF", "STMF")), f"{variant} two successful missions metrics")
        total = report["ResourceResultsTotal"]
        require(len(rows(total)) == 1 and selected(total, "NR") == [2] and math.isclose(selected(total, "NRUM")[0], 4 / 36, abs_tol=1e-6) and math.isclose(selected(total, "NRW")[0], wait_hours / 36, abs_tol=1e-6), f"{variant} resource hour totals")
        resource = report["ResourceResults"]
        require(len(rows(resource)) == 72 and all(v == 2 for v in selected(resource, "NR")), f"{variant} 72-bin nominal pool")
        require({i: v for i, v in enumerate(selected(resource, "NRUM")) if v} == expected_work and {i: v for i, v in enumerate(selected(resource, "NRW")) if v} == expected_wait, f"{variant} exact work/wait bins")
        system = report["SystemResults"]
        require(len(rows(system)) == 72 and all(v == 0 for v in selected(system, "NFAIL")) and selected(system, "NSYRY")[-1] == 2 and [selected(system, "NSYMO")[i] for i in (56, 57, 58)] == [1, 2, 1], f"{variant} system mission bins and terminal ready")
        stock = report["StockTotalResults"]
        require(len(rows(stock)) == 72 and all(v == 0 for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT") for v in selected(stock, n)), f"{variant} zero stock movement")

    return {"schema": "simlox-c08-partial-pool-author-validation/v1", "passed": not issues, "issues": issues,
            "runs": [{"variant": variant, "run_id": run_id, "input_sha256": input_sha,
                      "closure_sha256": sha(HERE / "runs" / run_id / "closure.json"),
                      "model_log_sha256": sha(HERE / "runs" / run_id / "model.log"),
                      "report_raw_sha256": sha(HERE / "runs" / run_id / "report-raw.json")}
                     for variant, (input_sha, run_id) in INPUTS.items()],
            "scope": "staggered two-crew pool: first half-hour one busy, then two; MAXUT1 stops both at 24.75 with 0.75/1.25 hours left, reset at 26, two missions succeed"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
