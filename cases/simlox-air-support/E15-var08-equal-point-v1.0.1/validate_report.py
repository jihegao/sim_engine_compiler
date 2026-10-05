"""Replay bounded equal-point report from old sealed calculation and new report export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "E15-var08-equal-point-v1.0.0"
OLD_RUN = OLD / "runs/e15-var08-equal-point-v100-ssh-20261005-01"
RUN = HERE / "runs/e15-var08-report-only-v101-ssh-20261005-01"
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
PARENT_REPORT = PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict:
    return {table["name"]: table for table in read(path)["report"]["tables"]}


def rows(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> dict:
    failed = []
    checks = 0

    def ck(label: str, passed: bool) -> None:
        nonlocal checks
        checks += 1
        if not passed:
            failed.append(label)

    contract, old_index, old_closure = (read(p) for p in (HERE / "contract.json", OLD / "evidence-index.json", OLD_RUN / "closure.json"))
    inv, closure = read(RUN / "invocation.json"), read(RUN / "closure.json")
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["version"], contract["run_id"]) == ("E15", "E15.var08", "1.0.1-candidate", RUN.name))
    ck("old excluded lineage", old_index["publication_state"] == "excluded_diagnostic" and old_closure["error"] == "frozen equal-point event gate failed" and contract["diagnostic_parent"]["evidence_index_sha256"] == sha(OLD / "evidence-index.json") and contract["diagnostic_parent"]["closure_sha256"] == sha(OLD_RUN / "closure.json"))
    ck("old SXO/event pins", contract["diagnostic_parent"]["sxo_sha256"] == sha(OLD_RUN / "model.sxo") and contract["diagnostic_parent"]["event_log_sha256"] == sha(OLD_RUN / "model.log"))
    ck("old raw inventory", len(old_closure["raw"]) == 11)
    for name, pin in old_closure["raw"].items():
        path = OLD_RUN / name
        ck(f"old raw {name}", path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"])
    ck("new lineage", closure["diagnostic_closure_sha256"] == inv["diagnostic_closure_sha256"] == sha(OLD_RUN / "closure.json") and closure["invocation_sha256"] == sha(RUN / "invocation.json") and closure["error"] is None)
    ck("source stable", inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
    source_paths = {
        "contract": HERE / "contract.json", "diagnostic_index": OLD / "evidence-index.json",
        "diagnostic_closure": OLD_RUN / "closure.json", "diagnostic_sxo": OLD_RUN / "model.sxo",
        "diagnostic_event": OLD_RUN / "model.log", "selector": PARENT / "runs/report-settings/item-position-results.sxs",
        "selector_builder": PARENT / "make_report_settings.py",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "runner": HERE / "run_report_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for name, path in source_paths.items():
        ck(f"source {name}", sha(path) == inv["source_hashes_before"][name])
    ck("report-only command", " -report -rpts " in inv["arguments"] and " -rjexport " in inv["arguments"] and not re.search(r" -(?:calc|jimport|jexport)\b", inv["arguments"]))
    ck("SSH and GUI", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    steps = read(RUN / "steps.json")
    ck("one guarded report step", len(steps) == 1 and steps[0]["name"] == "report_only" and steps[0]["exit_code"] == 0 and steps[0]["status"] == "completed" and steps[0]["gui_preserved"] is True)
    ck("new raw inventory", set(closure["raw"]) == {"outcome.json", "report-export.log", "selected-report-raw.json", "steps.json"})
    for name, pin in closure["raw"].items():
        path = RUN / name
        ck(f"new raw {name}", path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"])
    ck("report status", read(RUN / "outcome.json")["status"] == "completed" and read(RUN / "outcome.json")["error"] is None and "Report completed" in (RUN / "report-export.log").read_text(encoding="utf-8-sig"))

    event = (OLD_RUN / "model.log").read_text(encoding="utf-8-sig")
    ck("opening physical stock", "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>," in event)
    ck("no hour-zero reorder", not re.search(r"(?m)^Time: 0 <TEACH-DU-01,0,DEPOT-01,0> reorder task", event))
    ck("hour-ten issue/order", event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>") == 1 and event.count("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1") == 1)
    ck("hour-eleven three item delivery", event.count("Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 3 item(s) arrives") == 1 and all(event.count(f"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,{i}>") == 1 for i in (4, 5, 6)))
    ck("physical terminal", "Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,4>,<TEACH-DU-01,0,5>,<TEACH-DU-01,0,6>," in event and event.count("Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>") == 1)
    ck("one reorder", len(re.findall(r"(?m)^Time: .*<TEACH-DU-01,0,DEPOT-01,0> reorder task [0-9]+ started", event)) == 1)

    report, parent_report = tables(RUN / "selected-report-raw.json"), tables(PARENT_REPORT)
    ck("ten report tables", len(report) == len(parent_report) == 10 and list(report) == list(parent_report))
    for name in ("ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"):
        ck(f"parent table {name}", report[name] == parent_report[name])
    item = rows(report["ItemResults"])
    expected = [2] * 20 + [1] * 2 + [4] * 50
    ck("72 depot bins", len(item) == 72)
    for i, row in enumerate(item):
        ck(f"depot bin {i}", row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01" and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 and row["STSZ"] == 4 and row["STOHA"] == expected[i] and row["NRO"] == (1 if i == 20 else 0) and row["NBO"] == 0)
    total = rows(report["ItemResultsTotal"])[0]
    ck("item total", total["STSZ"] == 4 and abs(total["STOHA"] - 242 / 72) < 1e-5 and total["NRO"] == 1 and total["NBO"] == 0)
    ck("terminal readiness", rows(report["FixedMissionResultsTotal"])[0]["NMSUC"] == 2 and rows(report["SystemResults"])[-1]["NSYRY"] == 1)
    return {"schema": "simlox-e15-var08-v101-author-validation/v1", "passed": not failed, "checks": checks, "differences": failed, "scope": "bounded_equal_point_report_only", "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        result = {"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
