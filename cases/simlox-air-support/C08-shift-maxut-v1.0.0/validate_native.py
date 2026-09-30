"""Author replay of one guarded native MAXUT shift-limit run."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "c08-maxut-one-20260930-01"
RUN = HERE / "runs" / RUN_ID
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
CONTROL = HERE.parent / "C07-repeat-nested-v1.0.0" / "runs" / "c07-explicit-pair-20260930-01"
SOURCE = HERE / "maxut-one-input.json"
INPUT_SHA = "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5"
PARENT_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str, section: str = "report") -> tuple[list[str], list[list]]:
    item = next(t for t in doc[section]["tables"] if t["name"] == name)
    return [c["name"] for c in item["columns"]], [r for ins in item["instances"] for r in ins["rows"]]


def check() -> dict:
    issues: list[str] = []
    def demand(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    exact = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    demand(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"] == exact["parent_sha256"], "accepted C07 parent")
    demand(sha(SOURCE) == sha(RUN / "input.json") == INPUT_SHA == contract["input_sha256"] == exact["child_sha256"], "frozen source")
    a = {t["name"]: t for t in parse_native(PARENT)["model"]["tables"]}
    b = {t["name"]: t for t in parse_native(SOURCE)["model"]["tables"]}
    demand(a.keys() == b.keys() and sorted(n for n in a if a[n] != b[n]) == ["ProblemDescription", "ShiftResource"] == exact["changed_tables"], "exact parent delta")
    demand(a["ShiftResource"]["instances"][0]["rows"] == [["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]] and b["ShiftResource"]["instances"][0]["rows"] == [["DAY-OPEN", "BASE-01", "P-CREW", 2, 1.0, None]], "sole MAXUT business change")
    demand(sha(HERE / "exact-diff.json") == "1e4c9e3c9c8485e9310484762b1317ba026fa21ab8b652b3c63eb3674cc71414", "exact diff frozen")

    inv = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    demand(inv["run_id"] == closure["run_id"] == RUN_ID and inv["variant"] == "maxut-one" and inv["case_id"] == "C08", "run identity")
    demand(inv["parent_sha256"] == PARENT_SHA and inv["input_sha256"] == INPUT_SHA, "invocation sources")
    demand(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "session-zero SSH and mutex")
    demand(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
    demand(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "source seals")
    for key, path in {"input": SOURCE, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        demand(closure["source_hashes_before"][key] == sha(path), f"runtime source {key}")
    demand(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    demand([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five native/check steps")
    for name, item in closure["raw"].items():
        path = RUN / name
        demand(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
    demand(json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], "roundtrip checker")
    imported = populated(parse_native(RUN / "input.json"))
    exported = populated(parse_native(RUN / "roundtrip-raw.json"))
    demand(len(imported) == 24 and all(exported.get(n) == t for n, t in imported.items()), "24 row-containing tables roundtrip")
    demand(exported["ShiftResource"]["rows"][0][4] == 1.0, "native MAXUT one retained")

    calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
    demand(re.findall(r"error\s+#(\d+)", calc, re.I) == [] and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"} and "Errors: 0, Warnings: 2, Notes: 0" in calc, "zero-error conversion")
    demand((RUN / "model.sxo").stat().st_size > 4 and (RUN / "report-raw.json").stat().st_size > 4, "usable output")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    demand("Time: 24.5  <P-CREW at <BASE-01,0>> out of utilisation time" in log and "Time: 26  resource shift 3 starting" in log, "pool limit and next shift reset")
    for aircraft in (0, 1):
        ident = f"<TEACH-AIR-01,{aircraft}>"
        demand(f"Time: 24.5  subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident} is stopped due to resource time-out, time left= 1" in log, f"aircraft {aircraft} positive stop")
        demand(f"Time: 26  subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident} starts performing, planned to last for 1 hours" in log, f"aircraft {aircraft} restart")
        demand(f"Time: 27 {ident} preparation ended" in log, f"aircraft {aircraft} preparation finish")
    demand("Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log, "mission and terminal two ready")
    control_log = (CONTROL / "model.log").read_text(encoding="utf-8-sig")
    demand("out of utilisation time" not in control_log and "Time: 26.5 <TEACH-AIR-01,0> preparation ended" in control_log, "control contrast")

    report = parse_native(RUN / "report-raw.json")
    reference = parse_native(CONTROL / "report-raw.json")
    current_tables = {t["name"]: t for t in report["report"]["tables"]}
    control_tables = {t["name"]: t for t in reference["report"]["tables"]}
    demand(current_tables.keys() == control_tables.keys(), "report table identity")
    demand(sorted(n for n in current_tables if current_tables[n] != control_tables[n]) == ["ProblemDescription", "ResourceResults", "ResourceResultsTotal", "SystemResults"], "bounded control report differences")
    demand(current_tables["ResultSummary"] == control_tables["ResultSummary"] and current_tables["StockTotalResults"] == control_tables["StockTotalResults"], "mission totals and stock equal control")
    cols, rr = table(report, "ResourceResultsTotal")
    demand(len(rr) == 1 and rr[0][cols.index("NR")] == 2 and math.isclose(rr[0][cols.index("NRUM")], 4 / 36, abs_tol=1e-6) and math.isclose(rr[0][cols.index("NRW")], 3 / 36, abs_tol=1e-6), "four crew-hours work and three resource-hours wait")
    cols, rr = table(report, "ResourceResults")
    demand(len(rr) == 72 and all(row[cols.index("NR")] == 2 for row in rr), "72-bin nominal resource two")
    expect_work = {47: 2, 48: 2, 52: 2, 53: 2}
    expect_wait = {49: 2, 50: 2, 51: 2}
    demand({i: row[cols.index("NRUM")] for i, row in enumerate(rr) if row[cols.index("NRUM")]} == expect_work, "exact MAXUT work bins")
    demand({i: row[cols.index("NRW")] for i, row in enumerate(rr) if row[cols.index("NRW")]} == expect_wait, "exact MAXUT wait bins")
    cols, rr = table(report, "SystemResults")
    demand(len(rr) == 72 and all(row[cols.index("NFAIL")] == 0 for row in rr) and rr[-1][cols.index("NSYRY")] == 2 and [rr[i][cols.index("NSYMO")] for i in (56, 57)] == [2, 2], "system ledger and terminal state")
    cols, rr = table(report, "StockTotalResults")
    demand(len(rr) == 72 and all(row[cols.index(n)] == 0 for row in rr for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "zero stock movement")

    return {"schema": "simlox-c08-shift-maxut-author-validation/v1", "passed": not issues, "issues": issues,
            "run_id": RUN_ID, "input_sha256": INPUT_SHA, "closure_sha256": sha(RUN / "closure.json"),
            "report_raw_sha256": sha(RUN / "report-raw.json"), "model_log_sha256": sha(RUN / "model.log"),
            "scope": "one two-crew first-day MAXUT1 shift limit and reset"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
