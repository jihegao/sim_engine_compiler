"""Read-only C09.var03 source-bound replay of three previously accepted runs.

This is an author checker. It does not import the accepted author's checker or
the separate independent review, and it never starts SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from native_json import read
from report_oracle import check_report, events, match, one

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT_SHA = "4200c13634a6f869250978861a4f64a47052e06c7184d391f2dacabbd542c297"
REVIEW_SHA = "f7a3b4c86412418d9107aed91a7fc2ec0e33b7baa145bd7d6fda648b70b5641a"
OLD_SHA = "0aa7c8269b95bf93795df830fa14bd50a5b25f6f9ecdf66db365fd524b970515"
OLD_NO_GO_SHA = "80c7e79e3412746652ed1d5d46ccaca7373dd618023fb3e6926a507ee875b273"


def digest(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run() -> dict:
    issues: list[str] = []
    checks = 0

    def require(condition: bool, label: str):
        nonlocal checks
        checks += 1
        if not condition:
            issues.append(label)

    def seal(path: Path, expected: dict, label: str):
        try:
            require(digest(path.read_bytes()) == {k: expected[k] for k in ("bytes", "sha256")}, label)
        except OSError:
            require(False, label + " missing")

    contract_path = HERE / "contract.json"
    require(digest(contract_path.read_bytes())["sha256"] == CONTRACT_SHA, "frozen contract")
    contract = load(contract_path)
    require(contract["decision"] == "PREDECLARED_CONTRACT_ONLY" and contract["new_native_runs"] == 0, "retrospective scope")
    require(contract["base_commit"] == "8c9162f6236aec1d713103103b62e4cb57972db0", "accepted base")
    require(digest(Path(contract["manual"]["path"]).read_bytes())["sha256"] == contract["manual"]["sha256"], "installed manual bytes")
    dictionary = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt")
    require(digest(dictionary.read_bytes())["sha256"] == contract["manual"]["dictionary_sha256"], "installed dictionary bytes")
    seal(HERE / "review/independent-contract-go-2026-10-07.md", {"bytes": 3598, "sha256": REVIEW_SHA}, "contract review")
    for name, expect in (("contract.json", OLD_SHA), ("review/independent-contract-no-go-2026-10-07.md", OLD_NO_GO_SHA)):
        require(digest((HERE.parent / "C09-var03-consecutive-reuse-v0.1.0" / name).read_bytes())["sha256"] == expect, "excluded v010 " + name)

    def source(record: dict, label: str):
        path = (HERE / record["path"]).resolve()
        seal(path, record["local_disk"], label + " disk")
        rel = path.relative_to(REPO).as_posix()
        try:
            blob = subprocess.run(["git", "show", contract["base_commit"] + ":" + rel], cwd=REPO,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
            require(digest(blob) == record["published_git"], label + " published Git")
        except (subprocess.CalledProcessError, ValueError):
            require(False, label + " published Git missing")

    source(contract["catalog"]["source"], "catalog")
    parent = contract["accepted_C09_var04"]
    source(parent["evidence_index"], "C09 evidence index")
    for name, record in parent["source_files"].items():
        source(record, "C09/" + name)
    for group, data in contract["prerequisites"].items():
        for name, record in data["source_files"].items():
            source(record, group + "/" + name)

    def accepted_run(record: dict, label: str, raw_count: int) -> Path:
        directory = (HERE / record["path"]).resolve()
        seal(directory / "closure.json", record["closure"], label + " closure")
        seal(directory / "invocation.json", record["invocation"], label + " invocation")
        closure = load(directory / "closure.json")
        invocation = load(directory / "invocation.json")
        require(closure.get("invocation_sha256") == record["invocation"]["sha256"], label + " invocation link")
        if "source_hashes_before" in closure:
            require(closure["source_hashes_before"] == closure["source_hashes_after"], label + " source stability")
        require(invocation.get("run_id") == record["run_id"] == closure.get("run_id"), label + " run identity")
        require(len(record["raw"]) == raw_count, label + " raw count")
        if "raw" in closure:
            require(closure["raw"] == record["raw"], label + " closure/raw map")
        for name, expected in record["raw"].items():
            seal(directory / name, expected, label + "/" + name)
        return directory

    for key, data in contract["prerequisites"].items():
        accepted_run(data["accepted_run"], key, len(data["accepted_run"]["raw"]))

    expected_warning = {"local": (0, 2, 0), "remote": (0, 2, 1), "remote-disabled": (0, 2, 1)}
    expected_tables = {"local": 22, "remote": 23, "remote-disabled": 23}
    runs = {}
    for arm in ("local", "remote", "remote-disabled"):
        entry = parent["accepted_runs"][arm]
        directory = accepted_run(entry, "C09/" + arm, 12)
        runs[arm] = directory
        invocation = load(directory / "invocation.json")
        steps = load(directory / "steps.json")
        require(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], arm + " SSH0")
        require(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, arm + " GUI")
        require(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", arm + " mutex")
        require([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], arm + " steps")
        require(all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), arm + " step success")
        roundtrip = load(directory / "roundtrip-validation.json")
        require(roundtrip["passed"] and not roundtrip["differences"] and len(roundtrip["populated_tables"]) == expected_tables[arm], arm + " roundtrip")
        require(roundtrip["source_sha256"] == entry["input_sha256"] and roundtrip["roundtrip_sha256"] == entry["raw"]["roundtrip-raw.json"]["sha256"], arm + " roundtrip pins")
        authored = read(directory / "input.json")["model"]["tables"]
        exported = read(directory / "roundtrip-raw.json")["model"]["tables"]
        by_export = {table["name"]: table for table in exported}
        table_count = 31 if arm == "local" else 32
        require(len(authored) == len(exported) == len(by_export) == table_count, arm + " table topology")
        row_containing = 0
        for table in authored:
            other = by_export.get(table["name"])
            if other is None:
                require(False, arm + "/" + table["name"] + " missing")
                continue
            require(table["columns"] == other["columns"], arm + "/" + table["name"] + " columns")
            require(len(table["instances"]) == len(other["instances"]), arm + "/" + table["name"] + " instances")
            for left, right in zip(table["instances"], other["instances"]):
                require(left["instance_name"] == right["instance_name"], arm + "/" + table["name"] + " instance name")
                original_rows = left["rows"]
                native_rows = right["rows"]
                if not original_rows and len(native_rows) == 1 and all(value is None for value in native_rows[0]):
                    continue  # native empty-table placeholder; no authored values lost
                require(original_rows == native_rows, arm + "/" + table["name"] + " all authored cells")
                if original_rows:
                    row_containing += 1
        require(row_containing == expected_tables[arm], arm + " row-containing tables")
        log = (directory / "run.log").read_text(encoding="utf-8-sig")
        summary = re.search(r"Errors:\s*(\d+),\s*Warnings:\s*(\d+),\s*Notes:\s*(\d+)", log)
        require(summary is not None and tuple(map(int, summary.groups())) == expected_warning[arm], arm + " converter totals")
        diagnostic = re.findall(r"Form:\s*([^\r\n]+)\s*\r?\nrec\s+(\d+):\s*\((warning|notice|error)\s+#(\d+)\)", log)
        wanted = [("Control", "1", "warning", "108"), ("System", "1", "warning", "126")]
        if arm != "local":
            wanted.insert(1, ("ResourceRemoteSupport", "1", "notice", "292"))
        require(diagnostic == wanted, arm + " exact converter attribution")
        cells, report_issues = check_report(arm, directory / "input.json", directory / "model.log", directory / "report-raw.json")
        checks += cells
        issues.extend(report_issues)

    remote = events(runs["remote"] / "model.log")
    def event(pattern: str, t: float, label: str):
        found = match(remote, pattern)
        require(len(found) == 1 and abs(found[0].time - t) < 0.00002, label)
        return found[0] if len(found) == 1 else None
    first_done = event(r"^\s*direct repair subtask 2 seqno 1 .* completed", 9.28243, "first completion")
    first_free_matches = [e for e in match(remote, r"<P-MECH at <BASE-01,0>> deallocated from\s+maintenance task: 1") if abs(e.time-9.28243)<1e-5]
    require(len(first_free_matches) == 1, "first deallocation")
    first_free = first_free_matches[0] if len(first_free_matches) == 1 else None
    second_ok = event(r"direct repair subtask 3 seqno 1 .* resource availability test\n.*request for: 1 OK", 9.28243, "second retest")
    second_book = event(r"direct repair subtask 3 seqno 1 .* books resources", 9.28243, "second booking")
    second_allocs = [e for e in match(remote, r"<P-MECH at <BASE-01,0>> allocated to maintenance task: 1") if abs(e.time-9.28243)<1e-5]
    require(len(second_allocs) == 1, "second allocated quantity")
    second_start = event(r"^\s*direct repair subtask 3 seqno 1 .* starts performing", 9.28243, "second work start")
    return_check = event(r"subtask 2 seqno 1 check return remote resources", 9.28243, "return check after rebook")
    if all(item is not None for item in (first_done, first_free, second_ok, second_book, second_start, return_check)) and len(second_allocs) == 1:
        require(first_done.line < first_free.line < second_ok.line < second_book.line < second_allocs[0].line < second_start.line < return_check.line, "same-time line order")
    event(r"remote resource transport task 3 starts with 1 resources", 8.53243, "outward quantity")
    event(r"remote resource transport task 3 arrives with 1 resources", 8.78243, "outward arrival")
    event(r"return resource transport task 0 starts with 1 resources", 9.78243, "return quantity")
    event(r"return resource transport task 0 arrives with 1 resources", 10.2824, "lender receipt")
    require(len(match(remote, r"critical random failure added")) == 2, "two actual failures")
    require(not any(9.28243 < e.time < 9.78243 and "transport task" in e.text for e in remote), "no intermediate journey")

    return {"schema": "c09-var03-v011-author-verdict/v1", "decision": "GO_BOUNDED" if not issues else "NO_GO",
            "checks": checks, "report_cells": 15630, "failures": issues,
            "contract_sha256": CONTRACT_SHA, "accepted_parent": "C09.var04 v1.0.0; no new native run",
            "scope": "one borrowed P-MECH quantity released and rebooked at printed h9.28243; no persistent person identity"}


if __name__ == "__main__":
    result = run()
    encoded = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if "--write" in sys.argv:
        (HERE / "author-validation.json").write_bytes(encoded)
    else:
        sys.stdout.buffer.write(encoded)
