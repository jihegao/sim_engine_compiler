"""Replay the frozen I07.var02 matched pair from sealed native evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/i07-var02-rosiz-v100-ssh-20261005-01"
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
PARENT_EVENT = PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01/model.log"
PARENT_REPORT = PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def populated(path: Path) -> dict:
    document = read(path)
    return {
        table["name"]: {
            "columns": [(column["name"], column["datatype"]) for column in table["columns"]],
            "rows": [row for instance in table["instances"] for row in instance["rows"]],
        }
        for table in document["model"]["tables"]
        if any(instance["rows"] for instance in table["instances"])
    }


def report(path: Path) -> dict:
    # SIMLOX report JSON uses trailing commas; normalize a parser copy only.
    source = path.read_text(encoding="utf-8-sig")
    parsed = json.loads(re.sub(r",\s*([}\]])", r"\1", source))
    tables = parsed["report"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> int:
    errors: list[str] = []
    count = 0

    def check(name: str, passed: bool) -> None:
        nonlocal count
        count += 1
        if not passed:
            errors.append(name)

    contract, invocation, closure, steps, outcome = (
        read(path) for path in (
            HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json",
            RUN / "steps.json", RUN / "outcome.json"
        )
    )
    check("contract/run identity", contract["variant_id"] == "I07.var02"
          and contract["run_id"] == invocation["run_id"] == closure["run_id"] == RUN.name)
    check("terminal closure", closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    check("source stable", invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
    for name, expected in invocation["source_hashes_before"].items():
        if name in ("runner", "python"):
            path = HERE / "run_native_ssh.ps1" if name == "runner" else Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
            check(f"source {name}", sha(path) == expected)
    check("session/mutex/GUI", invocation["session_id"] == 0
          and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    check("eight serial steps", [s["name"] for s in steps] == [f"{arm}_{stage}" for arm in ("control", "change") for stage in ("import", "export", "calc", "report")]
          and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    check("outcome", outcome["error"] is None and list(outcome["arms"].values()) == ["completed", "completed"])
    check("raw inventory", len(closure["raw"]) == 24)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(f"raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])

    reports: dict[str, dict] = {}
    logs: dict[str, str] = {}
    for arm in ("control", "change"):
        check(f"{arm} copied input", sha(RUN / f"{arm}-input.json") == contract["frozen_source"]["inputs_sha256"][arm])
        roundtrip = read(RUN / f"{arm}-roundtrip-check.json")
        authored = populated(RUN / f"{arm}-input.json")
        exported = populated(RUN / f"{arm}-roundtrip-raw.json")
        check(f"{arm} exact roundtrip", roundtrip["passed"] is True and len(authored) == 22
              and roundtrip["mismatches"] == [] and all(exported.get(name) == value for name, value in authored.items()))
        runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
        check(f"{arm} conversion", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog
              and Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1})
              and (RUN / f"{arm}.sxo").stat().st_size > 1000)
        check(f"{arm} report export", "Report completed" in (RUN / f"{arm}-report-export.log").read_text(encoding="utf-8-sig"))
        reports[arm] = report(RUN / f"{arm}-report-raw.json")
        logs[arm] = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
        selected = reports[arm]
        check(f"{arm} selected tables", {"ItemResults", "ItemResultsTotal", "SystemResults", "StockTotalResults", "FixedMissionResultsTotal", "ResultSummary"}.issubset(selected))
        item = rows(selected["ItemResults"])
        check(f"{arm} 72 half-hour bins", len(item) == 72 and all(row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01"
              and row["STINT"] == index / 2 and row["ETINT"] == (index + 1) / 2 for index, row in enumerate(item)))
        for index, row in enumerate(item):
            expected = 3 if index < 20 else 2 if index < 22 else 4
            check(f"{arm} depot stock bin {index}", row["STSZ"] == 4 and row["STOHA"] == expected and row["NBO"] == 0 and row["NRO"] == (1 if index == 20 else 0))
        total = rows(selected["ItemResultsTotal"])[0]
        check(f"{arm} item total", total["STSZ"] == 4 and abs(total["STOHA"] - (3 * 20 + 2 * 2 + 4 * 50) / 72) < 1e-5
              and total["NRO"] == 1 and total["NBO"] == 0)
        check(f"{arm} system/mission aggregate", len(rows(selected["SystemResults"])) == 72
              and rows(selected["SystemResults"])[-1]["NSYRY"] == 1
              and rows(selected["FixedMissionResultsTotal"])[0]["NMSTA"] == 3
              and rows(selected["FixedMissionResultsTotal"])[0]["NMSUC"] == 2
              and len(rows(selected["StockTotalResults"])) == 72)
        log = logs[arm]
        check(f"{arm} no immediate order or stock movement at h5", not re.search(r"(?m)^Time: 5(?:\.\d+)? .*?(?:reorder|Stock at:|replacement item|Delivery)", log)
              and not re.search(r"(?m)^Time: [5-9](?:\.\d+)? .*?reorder task", log))
        check(f"{arm} h10 physical issue", len(re.findall(r"Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>", log)) == 1)
        check(f"{arm} one reorder start/finish", len(re.findall(r"Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1", log)) == 1
              and len(re.findall(r"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1", log)) == 1)
        check(f"{arm} two-unit delivery identities", "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives" in log
              and all(f"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,{identity}>" in log for identity in (5, 6))
              and len(re.findall(r"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item", log)) == 2)
        check(f"{arm} base transfer receipt", "Time: 12 <TEACH-DU-01,0,BASE-01,0> Replacement item arrives <TEACH-DU-01,0,0>" in log)
        check(f"{arm} complete reorder inventory", len(re.findall(r"reorder task \d+ started", log)) == 1
              and len(re.findall(r"reorder task \d+ completed", log)) == 1
              and len(re.findall(r"Delivery with \d+ item\(s\) arrives", log)) == 1)

    check("paired raw event equality", sha(RUN / "control.log") == sha(RUN / "change.log") == sha(PARENT_EVENT))
    for name in reports["control"]:
        if name != "ProblemDescription":
            check(f"paired report {name}", reports["control"][name] == reports["change"][name])
            check(f"accepted parent report {name}", reports["control"][name] == report(PARENT_REPORT)[name])
    result = {
        "schema": "simlox-i07-var02-author-replay/v1",
        "passed": not errors,
        "checks": count,
        "differences": errors,
        "observed": "The h5 scheduled ROSIZ1 row roundtrips; neither arm orders or moves stock at h5. Both arms have the same h10 two-unit order and h11 delivery. No changed batch policy is demonstrated.",
        "publication_state": "not_published",
    }
    (HERE / "author-validation-2026-10-05.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}))
        sys.exit(1)
