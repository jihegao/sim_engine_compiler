"""Replay the I07.var04 first-cycle observation from sealed native evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var04-old-cycle-v100-ssh-20261005-01"
PARENT_SOURCE = ROOT / "E15-var01-time-based-cycle-v1.0.0"
PARENT = ROOT / "E15-var01-time-based-cycle-v1.0.1"
PARENT_RUN = PARENT_SOURCE / "runs/e15-var01-timecycle-v100-ssh-20261005-01"
PARENT_REPORT = PARENT / "runs/e15-var01-timecycle-report-v101-ssh-20261005-01"
SELECTOR_PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model(path: Path) -> dict:
    tables = read(path)["model"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def report(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    tables = json.loads(re.sub(r",\s*([}\]])", r"\1", source))["report"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> int:
    failed: list[str] = []
    count = 0

    def check(label: str, passed: bool) -> None:
        nonlocal count
        count += 1
        if not passed:
            failed.append(label)

    contract, invocation, closure, steps, outcome = (
        read(path) for path in (HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json",
                          RUN / "steps.json", RUN / "outcome.json")
    )
    check("identity", contract["variant_id"] == "I07.var04" and contract["version"] == "1.0.0-candidate"
          and contract["run_id"] == invocation["run_id"] == closure["run_id"] == RUN.name)
    check("closure", closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json")
          and closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    source_map = {
        "contract": HERE / "contract.json", "input": HERE / "native-input.json",
        "builder": HERE / "build.py", "roundtrip_checker": HERE / "check_roundtrip.py",
        "parent_input": PARENT_SOURCE / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-05.md",
        "parent_index": PARENT / "evidence-index.json",
        "parent_event": PARENT_RUN / "model.log",
        "parent_report": PARENT_REPORT / "selected-report-raw.json",
        "selector": SELECTOR_PARENT / "runs/report-settings/item-position-results.sxs",
        "selector_builder": SELECTOR_PARENT / "make_report_settings.py",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "runner": HERE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    check("source inventory", set(source_map) == set(invocation["source_hashes_before"]))
    for name, path in source_map.items():
        check(f"source {name}", sha(path) == invocation["source_hashes_before"][name])
    check("SSH/GUI/mutex", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    check("four steps", [step["name"] for step in steps] == ["import", "export", "calc", "report"]
          and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("outcome", outcome["error"] is None and outcome["result"] == "native_run_completed"
          and outcome["roundtrip"] == "exact")
    check("raw inventory", len(closure["raw"]) == 13)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(f"raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    check("input copy", sha(RUN / "input.json") == contract["source"]["input_sha256"])
    source, parent, exported = model(RUN / "input.json"), model(PARENT_SOURCE / "native-input.json"), model(RUN / "roundtrip-raw.json")
    check("sole new row", len(parent) == 31 and len(source) == 32
          and all(source[name] == table for name, table in parent.items())
          and source["ChangesItemReorder"]["instances"][0]["rows"] == [["TEACH-DU-01", "DEPOT-01", 5.0, 1.0, None, None, 8.0, None]])
    authored = {name: table for name, table in source.items() if any(instance["rows"] for instance in table["instances"])}
    roundtrip = read(RUN / "roundtrip-check.json")
    check("22 authored-table roundtrip", len(authored) == 22 and roundtrip["passed"] is True
          and roundtrip["mismatches"] == [] and all(
              [(c["name"], c["datatype"]) for c in exported[name]["columns"]]
              == [(c["name"], c["datatype"]) for c in table["columns"]]
              and [row for i in exported[name]["instances"] for row in i["rows"]]
              == [row for i in table["instances"] for row in i["rows"]]
              for name, table in authored.items()))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("conversion", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog
          and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1, "376": 1})
          and (RUN / "model.sxo").stat().st_size > 1000)
    check("report export", "Report completed" in (RUN / "report-export.log").read_text(encoding="utf-8-sig"))
    events = (RUN / "model.log").read_text(encoding="utf-8-sig")
    check("complete parent event equality", sha(RUN / "model.log") == contract["accepted_parent"]["event_log_sha256"] == sha(PARENT_RUN / "model.log"))
    check("no h5/h8 reorder", not re.search(r"(?m)^Time: [5-9](?:\.\d+)? .*?reorder task", events)
          and not re.search(r"(?m)^Time: 5(?:\.\d+)? .*?(?:Stock at:|reorder task|Delivery with)", events))
    check("h10 issue/h12 transfer", "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>" in events
          and "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in events)
    check("one h16/h17 order", len(re.findall(r"reorder task \d+ started", events)) == 1
          and len(re.findall(r"reorder task \d+ completed", events)) == 1
          and "Time: 16 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1" in events
          and "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 1 item(s) arrives" in events
          and "Time: 17 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>" in events)
    check("physical terminal stock", "Level: 4 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,<TEACH-DU-01,0,6>" in events)
    child_report = report(RUN / "selected-report-raw.json")
    parent_report = report(PARENT_REPORT / "selected-report-raw.json")
    check("ten report tables", len(child_report) == len(parent_report) == 10
          and child_report.keys() == parent_report.keys())
    for name in child_report:
        check(f"parent report {name}", child_report[name] == parent_report[name])
    item = rows(child_report["ItemResults"])
    check("72 half-hour depot bins", len(item) == 72 and all(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01"
          and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(item)))
    for i, row in enumerate(item):
        want = 4 if i < 20 or i >= 34 else 3
        check(f"depot bin {i}", row["STSZ"] == 4 and row["STOHA"] == want
              and row["NRO"] == (1 if i == 32 else 0) and row["NBO"] == 0)
    check("terminal/mission/stock", rows(child_report["SystemResults"])[-1]["NSYRY"] == 1
          and rows(child_report["FixedMissionResultsTotal"])[0]["NMSTA"] == 3
          and rows(child_report["FixedMissionResultsTotal"])[0]["NMSUC"] == 2
          and len(rows(child_report["StockTotalResults"])) == 72)
    result = {"schema": "simlox-i07-var04-author-replay/v1", "passed": not failed,
              "checks": count, "differences": failed, "publication_state": "not_published",
              "scope": "Initial ROINT16 cycle retained until first h16 order after h5 ROINT8 source change; later eight-hour cadence unverified."}
    (HERE / "author-validation-2026-10-05.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}))
        sys.exit(1)
