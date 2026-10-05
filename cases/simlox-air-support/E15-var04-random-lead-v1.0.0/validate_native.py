"""Author replay of the frozen single-sample random lead claim."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
RUN_ID = "e15-var04-random-lead-v100-ssh-20261005-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01"
PARENT_REPORT = PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict:
    return {t["name"]: t for t in read(path)["report"]["tables"]}


def rows(table: dict) -> list[dict]:
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for inst in table["instances"] for row in inst["rows"]]


def populated(path: Path) -> dict:
    return {t["name"]: t for t in read(path)["model"]["tables"]
            if any(inst["rows"] for inst in t["instances"])}


def main() -> dict:
    failed: list[str] = []
    checks = 0

    def ck(name: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failed.append(name)

    contract, inv, closure = [read(p) for p in (HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json")]
    ck("frozen identity", (contract["case_id"], contract["variant_id"], contract["version"], contract["run_id"]) == ("E15", "E15.var04", "1.0.0-candidate", RUN_ID))
    ck("run identity", inv["run_id"] == closure["run_id"] == RUN_ID and closure["invocation_sha256"] == sha(RUN / "invocation.json") and closure["error"] is None)
    ck("source unchanged", inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
    source = {
        "contract": HERE / "contract.json", "input": HERE / "native-input.json",
        "builder": HERE / "build.py", "roundtrip_checker": HERE / "check_roundtrip.py",
        "parent_input": PARENT / "native-input-explicit-three.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
        "parent_index": PARENT / "evidence-index.json", "parent_event": PARENT_RUN / "model.log",
        "parent_report": PARENT_REPORT,
        "selector": PARENT / "runs/report-settings/item-position-results.sxs",
        "selector_builder": PARENT / "make_report_settings.py",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "runner": HERE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for key, path in source.items():
        ck(f"source pin {key}", sha(path) == inv["source_hashes_before"][key])
    ck("contract source pins", all(contract["source"][key + "_sha256"] == sha(source[name]) for key, name in [
        ("input", "input"), ("builder", "builder"), ("roundtrip_checker", "roundtrip_checker"),
        ("selector", "selector"), ("selector_builder", "selector_builder"),
        ("manual_pdf", "manual"), ("simlox_exe", "exe")]))
    ck("parent pins", all(contract["accepted_parent"][key] == sha(source[name]) for key, name in [
        ("input_sha256", "parent_input"), ("signoff_sha256", "parent_signoff"),
        ("evidence_index_sha256", "parent_index"), ("event_log_sha256", "parent_event"),
        ("selected_report_sha256", "parent_report")]))
    ck("session and GUI", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"]
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
       and inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    steps = read(RUN / "steps.json")
    ck("four native stages", [x["name"] for x in steps] == ["import", "export", "calc", "report"]
       and all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps))
    ck("13 raw files", set(closure["raw"]) == {"input.json", "model.sxi", "model.sxo", "model.log", "import.log",
       "export.log", "run.log", "report-export.log", "roundtrip-raw.json", "roundtrip-check.json",
       "selected-report-raw.json", "steps.json", "outcome.json"})
    for name, seal in closure["raw"].items():
        file = RUN / name
        ck(f"raw seal {name}", file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"])
    ck("copied input", sha(RUN / "input.json") == sha(source["input"]))
    check = read(RUN / "roundtrip-check.json")
    authored, exported = populated(RUN / "input.json"), populated(RUN / "roundtrip-raw.json")
    ck("exact 21 row-containing tables", check["passed"] and check["authored_populated_tables"] == 21
       and check["mismatches"] == [] and len(authored) == 21 and all(exported.get(k) == v for k, v in authored.items()))
    outcome = read(RUN / "outcome.json")
    calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("converter", outcome["result"] == "native_run_completed" and outcome["error"] is None
       and outcome["roundtrip"] == "exact" and outcome["converter_summary"] == [0, 1, 0]
       and outcome["warning_codes"] == ["108"] and re.findall(r"\(warning #(\d+)\)", calc) == ["108"])
    ck("valid output", (RUN / "model.sxo").stat().st_size > 1000
       and "Report completed" in (RUN / "report-export.log").read_text(encoding="utf-8-sig"))

    parent, child = read(source["parent_input"]), read(source["input"])
    copy = json.loads(json.dumps(parent))
    pts, cts = parent["model"]["tables"], child["model"]["tables"]
    ck("31 source tables", len(pts) == len(cts) == 31 and [t["name"] for t in pts] == [t["name"] for t in cts])
    reorder = next(t for t in copy["model"]["tables"] if t["name"] == "ItemReorder")
    old = reorder["instances"][0]["rows"][0]
    ck("parent lead fields", old[2] == 1.0 and old[9] is None)
    old[9] = "<EXP>"
    ck("sole LEADTD delta", copy == child)

    event = (RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("opening depot physical IDs", "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>," in event)
    ck("h10 depot ID0 issue", event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>") == 1
       and "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>," in event)
    orders = re.findall(r"(?m)^Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: ([0-9.]+)$", event)
    ck("one h10 sampled order", len(orders) == 1 and event.count("reorder task 0 started") == 1
       and not re.search(r"(?m)^Time: 0 .*reorder task", event))
    lead = float(orders[0]) if orders else math.nan
    ck("positive distinct sample", math.isfinite(lead) and 0 < lead < 26 and abs(lead - 1) > 1e-6)
    completed = re.findall(r"(?m)^Time: ([0-9.]+) <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was ([0-9.]+)$", event)
    ck("sampled delivery clock", len(completed) == 1 and abs(float(completed[0][0]) - (10 + lead)) < 6e-5
       and abs(float(completed[0][1]) - lead) < 1e-6 if completed else False)
    due = float(completed[0][0]) if completed else math.nan
    ck("two new IDs at delivery", event.count(f"Time: {due:g} <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives") == 1
       and event.count(f"Time: {due:g} <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,5>") == 1
       and event.count(f"Time: {due:g} <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>") == 1)
    ck("depot final physical IDs", "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,5>,<TEACH-DU-01,0,6>," in event)
    ck("base transfer and discard", "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in event
       and event.count("Item discarded: <TEACH-DU-01,0,4>") == 1)
    ck("mission and readiness", event.count("mission aborted:") == 1 and event.count("mission success:") == 2
       and "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in event)

    report, baseline = tables(RUN / "selected-report-raw.json"), tables(PARENT_REPORT)
    ck("ten selected tables", len(report) == len(baseline) == 10 and list(report) == list(baseline))
    for name in ("ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal",
                 "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"):
        ck(f"parent table {name}", report[name] == baseline[name])
    current, prior = rows(report["ItemResults"]), rows(baseline["ItemResults"])
    ck("72 depot bins", len(current) == len(prior) == 72)
    for i, (row, oldrow) in enumerate(zip(current, prior)):
        ck(f"depot bin {i}", row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01"
           and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2
           and row["STSZ"] == 4 and row["NBO"] == 0 and row["NRO"] == (1 if i == 20 else 0)
           and row["STOHA"] == (3 if i < 20 else 2 if i < 22 else 4 if i > 22 else row["STOHA"])
           and all(row[k] == oldrow[k] for k in row if k != "STOHA"))
    weighted = 2 + 2 * (11.5 - (10 + lead)) / 0.5
    ck("fractional h11 weighted on-hand", abs(current[22]["STOHA"] - weighted) < 6e-5
       and 2 < current[22]["STOHA"] < 4)
    total, parent_total = rows(report["ItemResultsTotal"])[0], rows(baseline["ItemResultsTotal"])[0]
    mean = sum(row["STOHA"] for row in current) / 72
    ck("horizon stock mean", abs(total["STOHA"] - mean) < 1e-5 and total["STOHA"] < parent_total["STOHA"]
       and all(total[k] == parent_total[k] for k in total if k != "STOHA"))
    ck("terminal readiness", rows(report["FixedMissionResultsTotal"])[0]["NMSUC"] == 2
       and rows(report["SystemResults"])[-1]["NSYRY"] == 1 and current[-1]["STOHA"] == 4)
    return {"schema": "simlox-e15-var04-v100-author-validation/v1", "passed": not failed,
            "checks": checks, "differences": failed, "sampled_lead_hours": lead,
            "delivery_event_hour": due, "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        result = {"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
