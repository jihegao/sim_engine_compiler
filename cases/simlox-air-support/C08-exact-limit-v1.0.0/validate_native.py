"""Author replay of the sealed C08.var04 exact-limit native run."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "c08-exact-limit-20260930-02"
RUN = HERE / "runs" / RUN_ID
PARENT = HERE.parent / "C08-shift-maxut-v1.0.0" / "maxut-one-input.json"
SOURCE = HERE / "exact-limit-input.json"
PARENT_SHA = "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5"
INPUT_SHA = "dc75e99a8007fe74c7a830633657c32957877b9eb0a162588f7dedc6bc1f428b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    obj = next(t for t in doc["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in obj["columns"]], [row for ins in obj["instances"] for row in ins["rows"]]


def check() -> dict:
    issues: list[str] = []

    def require(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    require(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"] == diff["parent_input_sha256"], "accepted parent fingerprint")
    require(sha(SOURCE) == sha(RUN / "input.json") == INPUT_SHA == contract["input_sha256"] == diff["child_input_sha256"], "child fingerprint")
    require(contract["parent_publication_id"] == "C08.var02.shift_maxut_one.1.0.0", "published parent identity")
    a = {t["name"]: t for t in parse_native(PARENT)["model"]["tables"]}
    b = {t["name"]: t for t in parse_native(SOURCE)["model"]["tables"]}
    require(a.keys() == b.keys() and sorted(n for n in a if a[n] != b[n]) == ["ProblemDescription", "TaskBreakDown"], "only intended tables differ")
    require(a["TaskBreakDown"]["instances"][0]["rows"] == [["PREP-FIXED", 1, "INSPECT", 2, None, None]] and b["TaskBreakDown"]["instances"][0]["rows"] == [["PREP-FIXED", 1, "INSPECT", 1, None, None]], "sole business field DURN 2 to 1")
    require(a["MissionPreparation"] == b["MissionPreparation"] and b["MissionPreparation"]["instances"][0]["rows"][0][3] == 2, "scalar retained, breakdown overrides")
    require(a["ShiftResource"] == b["ShiftResource"] and b["ShiftResource"]["instances"][0]["rows"][0][4] == 1, "MAXUT and pool retained")

    inv = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    require(inv["run_id"] == closure["run_id"] == RUN_ID and inv["variant"] == "exact-limit" and inv["case_id"] == "C08", "run identity")
    require(inv["input_sha256"] == INPUT_SHA and inv["parent_sha256"] == PARENT_SHA, "invocation source hashes")
    require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "guarded session-0 SSH queue")
    require(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "runtime source stability")
    for key, path in {"input": SOURCE, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        require(closure["source_hashes_before"][key] == sha(path), f"source seal {key}")
    require(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five guarded steps")
    for name, item in closure["raw"].items():
        path = RUN / name
        require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], f"raw seal {name}")
    require(json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"], "roundtrip checker")
    before = populated(parse_native(RUN / "input.json"))
    after = populated(parse_native(RUN / "roundtrip-raw.json"))
    require(len(before) == 24 and all(after.get(n) == v for n, v in before.items()), "24 source tables roundtrip")

    calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
    require(not re.findall(r"error\s+#\d+", calc, re.I) and "Errors: 0, Warnings: 2, Notes: 0" in calc and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"}, "zero-error conversion")
    require((RUN / "model.sxo").stat().st_size > 4 and (RUN / "report-raw.json").stat().st_size > 4, "nonempty output and report")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    require("out of utilisation time" not in log and "is stopped due to resource time-out" not in log, "no MAXUT stop at exact completion")
    require("Time: 24.5  <P-CREW at <BASE-01,0>> set time to max utilisation: 0" in log, "limit reached on release")
    for aircraft in (0, 1):
        ident = f"<TEACH-AIR-01,{aircraft}>"
        start = f"Time: 23.5  subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident} starts performing"
        done = f"Time: 24.5  subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident} completed"
        prep = f"Time: 24.5 {ident} preparation ended"
        require(start in log and done in log and prep in log and log.index(start) < log.index(done) < log.index(prep), f"aircraft {aircraft} ordered one-hour completion")
    require("Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log, "mission and terminal two ready")
    parent_log = (HERE.parent / "C08-shift-maxut-v1.0.0" / "runs" / "c08-maxut-one-20260930-01" / "model.log").read_text(encoding="utf-8-sig")
    require("Time: 24.5  <P-CREW at <BASE-01,0>> out of utilisation time" in parent_log and "is stopped due to resource time-out" in parent_log, "accepted positive timeout contrast")

    report = parse_native(RUN / "report-raw.json")
    cols, rows = table(report, "ResultSummary")
    require(len(rows) == 1 and all(rows[0][cols.index(n)] == 1 for n in ("MTMF", "MSTF", "MSUF", "STMF")), "one successful mission metrics")
    cols, rows = table(report, "ResourceResultsTotal")
    require(len(rows) == 1 and rows[0][cols.index("NR")] == 2 and math.isclose(rows[0][cols.index("NRUM")], 2 / 36, abs_tol=1e-6) and rows[0][cols.index("NRW")] == 0, "two crew-hours and no waiting")
    cols, rows = table(report, "ResourceResults")
    require(len(rows) == 72 and all(r[cols.index("NR")] == 2 for r in rows), "72-bin two crew resource ledger")
    require({i: r[cols.index("NRUM")] for i, r in enumerate(rows) if r[cols.index("NRUM")]} == {47: 2, 48: 2} and all(r[cols.index("NRW")] == 0 for r in rows), "only 23.5-24.5 resource work")
    cols, rows = table(report, "SystemResults")
    require(len(rows) == 72 and all(r[cols.index("NFAIL")] == 0 for r in rows) and rows[-1][cols.index("NSYRY")] == 2 and [rows[i][cols.index("NSYMO")] for i in (56, 57)] == [2, 2], "system ledger and terminal readiness")
    cols, rows = table(report, "StockTotalResults")
    require(len(rows) == 72 and all(r[cols.index(n)] == 0 for r in rows for n in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")), "zero stock ledger")

    return {"schema": "simlox-c08-exact-limit-author-validation/v1", "passed": not issues, "issues": issues, "run_id": RUN_ID, "input_sha256": INPUT_SHA, "closure_sha256": sha(RUN / "closure.json"), "model_log_sha256": sha(RUN / "model.log"), "report_raw_sha256": sha(RUN / "report-raw.json"), "scope": "two one-hour preparations complete at the MAXUT limit at 24.5, with no timeout and a successful 28-29 mission"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)
