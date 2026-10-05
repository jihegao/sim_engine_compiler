"""Replay the frozen zero-lead reorder claim from sealed local CLI evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
RUN_ID = "e15-var02-zero-lead-v100-ssh-20261005-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01"
PARENT_REPORT = PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json"
SOURCE = {
    "contract": HERE / "contract.json",
    "input": HERE / "native-input.json",
    "builder": HERE / "build.py",
    "roundtrip_checker": HERE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-explicit-three.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "parent_index": PARENT / "evidence-index.json",
    "parent_event": PARENT_RUN / "model.log",
    "parent_report": PARENT_REPORT,
    "selector": PARENT / "runs/report-settings/item-position-results.sxs",
    "selector_builder": PARENT / "make_report_settings.py",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict[str, dict]:
    values = read(path)["report"]["tables"]
    result = {t["name"]: t for t in values}
    assert len(result) == len(values)
    return result


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def populated(path: Path) -> dict:
    values = read(path)["model"]["tables"]
    return {t["name"]: ([(c["name"], c["datatype"]) for c in t["columns"]],
                         [row for inst in t["instances"] for row in inst["rows"]])
            for t in values if any(inst["rows"] for inst in t["instances"])}


def main() -> dict:
    failed: list[str] = []
    checks = 0

    def ck(label: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failed.append(label)

    contract, inv, closure = (read(p) for p in (HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json"))
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"], contract["run_id"]) == ("E15", "E15.var02", "1.0.0-candidate", RUN_ID))
    ck("run identity and closure", inv["run_id"] == closure["run_id"] == RUN_ID and closure["invocation_sha256"] == sha(RUN / "invocation.json") and closure["error"] is None)
    ck("source stable", inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
    for name, path in SOURCE.items():
        ck(f"source {name}", sha(path) == inv["source_hashes_before"][name])
    ck("contract pins", contract["source"]["input_sha256"] == sha(SOURCE["input"]) and contract["source"]["builder_sha256"] == sha(SOURCE["builder"]) and contract["source"]["roundtrip_checker_sha256"] == sha(SOURCE["roundtrip_checker"]) and contract["accepted_parent"]["input_sha256"] == sha(SOURCE["parent_input"]) and contract["accepted_parent"]["event_log_sha256"] == sha(SOURCE["parent_event"]) and contract["accepted_parent"]["selected_report_sha256"] == sha(SOURCE["parent_report"]))
    ck("session guard", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    steps = read(RUN / "steps.json")
    ck("four guarded stages", [s["name"] for s in steps] == ["import", "export", "calc", "report"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] is True for s in steps))
    ck("raw file set", set(closure["raw"]) == {"input.json", "model.sxi", "model.sxo", "model.log", "import.log", "export.log", "run.log", "report-export.log", "roundtrip-raw.json", "roundtrip-check.json", "selected-report-raw.json", "steps.json", "outcome.json"})
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    ck("input copy", sha(RUN / "input.json") == sha(SOURCE["input"]))
    check = read(RUN / "roundtrip-check.json")
    ck("21 table roundtrip", check["passed"] is True and check["authored_populated_tables"] == 21 and check["mismatches"] == [] and populated(RUN / "input.json") == {k: populated(RUN / "roundtrip-raw.json")[k] for k in populated(RUN / "input.json")})
    outcome = read(RUN / "outcome.json")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("native outcome", outcome["result"] == "native_run_completed" and outcome["error"] is None and outcome["roundtrip"] == "exact" and outcome["converter_summary"] == [0, 1, 0] and outcome["warning_codes"] == ["108"])
    ck("converter", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in log and re.findall(r"\(warning #(\d+)\)", log) == ["108"])
    ck("valid result", (RUN / "model.sxo").stat().st_size > 1000 and "Report completed" in (RUN / "report-export.log").read_text(encoding="utf-8-sig"))

    parent_input, child_input = read(SOURCE["parent_input"]), read(SOURCE["input"])
    pt, ct = parent_input["model"]["tables"], child_input["model"]["tables"]
    ck("31 table source topology", len(pt) == len(ct) == 31 and [t["name"] for t in pt] == [t["name"] for t in ct])
    lead_parent = pt[12]["instances"][0]["rows"][0][2]
    lead_child = ct[12]["instances"][0]["rows"][0][2]
    copy = json.loads(json.dumps(parent_input))
    copy["model"]["tables"][12]["instances"][0]["rows"][0][2] = 0.0
    ck("only LEADT 1 to 0", lead_parent == 1.0 and lead_child == 0.0 and pt[12]["name"] == ct[12]["name"] == "ItemReorder" and copy == child_input)

    event = (RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("opening physical stock", "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>," in event and "Stock at: <TEACH-DU-01,0,BASE-01,0> Level: 1 Items:<TEACH-DU-01,0,3>," in event)
    ck("h10 physical issue", event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>") == 1 and "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>," in event)
    ck("physical transport", event.count("transport task 0 starts with 1 items/systems") == 1 and event.count("Time: 12  transport task 0 arrives with 1 items/systems") == 1 and event.count("Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0> to stock") == 1)
    ck("failure and repair", event.count("critical random failure added") == 1 and event.count("subitem failed: <TEACH-DU-01,0,4>") == 2 and event.count("Item discarded: <TEACH-DU-01,0,4>") == 1 and event.count("Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed") == 1)
    ck("same-time two-unit reorder", event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 0") == 1 and event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 0") == 1 and event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives") == 1 and event.count("reorder task") == 2 and "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,5>,<TEACH-DU-01,0,6>," in event)
    ck("new physical identities", event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,5>") == 1 and event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>") == 1 and not re.search(r"Time: (?:0|11) <TEACH-DU-01,0,DEPOT-01,0> (?:reorder task|Delivery with)", event))
    ck("terminal event path", event.count("mission success:") == 2 and event.count("mission aborted:") == 1 and "Time: 34 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in event)

    report, parent_report = tables(RUN / "selected-report-raw.json"), tables(PARENT_REPORT)
    ck("ten-table report", len(report) == len(parent_report) == 10 and list(report) == list(parent_report))
    for name in ("ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"):
        ck(f"parent report {name}", report[name] == parent_report[name])
    item = rows(report["ItemResults"])
    expected = [3] * 20 + [4] * 52
    ck("72 depot bins", len(item) == 72 and all(r["IID"] == "TEACH-DU-01" and r["STID"] == "DEPOT-01" and r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(item)))
    for i, row in enumerate(item):
        ck(f"depot bin {i}", row["STSZ"] == 4 and row["STOHA"] == expected[i] and row["NRO"] == (1 if i == 20 else 0) and row["NBO"] == 0)
    total, old_total = rows(report["ItemResultsTotal"])[0], rows(parent_report["ItemResultsTotal"])[0]
    ck("item total", total["STSZ"] == 4 and abs(total["STOHA"] - sum(expected) / 72) < 1e-5 and total["NRO"] == old_total["NRO"] == 1 and total["NBO"] == 0)
    ck("other total metrics", all(total[k] == old_total[k] for k in total if k != "STOHA"))
    ck("mission and terminal readiness", rows(report["FixedMissionResultsTotal"])[0]["NMSUC"] == 2 and rows(report["SystemResults"])[-1]["NSYRY"] == 1)
    result = {"schema": "simlox-e15-var02-v100-author-validation/v1", "passed": not failed, "checks": checks, "differences": failed, "scope": "bounded_zero_lead_cli_replay", "publication_state": "not_published"}
    return result


if __name__ == "__main__":
    try:
        answer = main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        answer = {"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(answer, indent=2))
    raise SystemExit(0 if answer["passed"] else 1)
