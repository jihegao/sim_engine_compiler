"""Read-only source-bound replay of the accepted B04.var05 native run."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parents[2]
SOURCE = CASE.parent / "B04-var05-turnround-breakdown-v0.1.0"
RUN = SOURCE / "runs" / "b04-var05-turnbreak-v010-ssh-20261006-01"
OUT = HERE / "independent-verdict.json"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    """Parse native trailing-comma JSON in linear time without changing strings."""
    source = path.read_text(encoding="utf-8-sig")
    output = []
    in_string = False
    escaped = False
    for index, char in enumerate(source):
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            output.append(char)
        elif char == ",":
            following = index + 1
            while following < len(source) and source[following].isspace():
                following += 1
            if following == len(source) or source[following] not in "}]":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)


def overlap(start, end, left, right):
    return max(0.0, min(end, right) - max(start, left))


def main():
    c = Checks()
    contract = read_json(CASE / "contract.json")
    closure = read_json(RUN / "closure.json")
    invocation = read_json(RUN / "invocation.json")
    evidence = read_json(SOURCE / "evidence-index.json")
    c.check(digest(CASE / "contract.json") == "cdae7dc60ab3593e48514811f9e4635bcc00f26f11039f3a189eeb4d1479e798", "classification contract")
    c.check(digest(HERE / "independent-contract-go-2026-10-07.md") == "990eb30ddb127de1e3409dec04255451ba452c0b6782b68b8ff92b6bd639161a", "contract review")
    c.check(digest(SOURCE / "native-input.json") == contract["accepted_source_run"]["input_sha256"], "source input")
    c.check(digest(SOURCE / "review" / "independent-verdict.json") == contract["accepted_source_run"]["independent_verdict_sha256"], "accepted independent verdict")
    c.check(digest(RUN / "closure.json") == contract["accepted_source_run"]["closure_sha256"], "closure")
    c.check(digest(RUN / "report-raw.json") == contract["accepted_source_run"]["report_raw_sha256"], "native report")
    c.check(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    c.check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "native source freeze")
    c.check(closure["run_id"] == contract["accepted_source_run"]["run_id"], "accepted run identity")
    c.check(len(closure["raw"]) == 13, "13 source raw records")
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        c.check(path.is_file() and path.stat().st_size == seal["bytes"] and digest(path) == seal["sha256"], f"raw seal {name}")
    c.check((RUN / "input.json").read_bytes() == (SOURCE / "native-input.json").read_bytes(), "native input copy")
    c.check(
        invocation["session_id"] == 0
        and invocation["ssh_connection_present"]
        and "sshd.exe" in invocation["ssh_ancestor_names"],
        "accepted SSH0 invocation",
    )
    c.check(
        invocation["gui"]["pid"] == 13340
        and invocation["gui"]["session_id"] == 1
        and invocation["gui"]["start_unix_ms"] == 1790590196826,
        "accepted GUI identity",
    )
    stages = read_json(RUN / "steps.json")
    c.check(
        [stage["name"] for stage in stages]
        == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"],
        "accepted native stages",
    )
    for stage in stages:
        c.check(
            stage["status"] == "completed"
            and stage["exit_code"] == 0
            and stage["gui_preserved"],
            f"accepted stage {stage['name']}",
        )
    conversion = (RUN / "run.log").read_text(errors="replace").lower()
    c.check(
        "errors: 0" in conversion
        and "warnings: 2" in conversion
        and "notes: 0" in conversion
        and "warning #108" in conversion
        and "warning #126" in conversion,
        "converter classification",
    )
    c.check((RUN / "model.sxo").stat().st_size > 4, "usable native result")

    # The accepted source is already published. Independently compare every
    # indexed source byte with both the working file and the HEAD Git blob.
    source_records = evidence["source"]
    for record in source_records:
        path = SOURCE / record["path"]
        relative = path.relative_to(REPO).as_posix()
        blob = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=REPO, capture_output=True, check=False)
        c.check(path.is_file() and path.stat().st_size == record["bytes"] and digest(path) == record["sha256"], f"published disk {record['path']}")
        c.check(blob.returncode == 0 and len(blob.stdout) == record["bytes"] and digest_bytes(blob.stdout) == record["sha256"], f"published Git blob {record['path']}")
    c.check(digest(SOURCE / "cli-scope-signoff-2026-10-06.md") == next(x["sha256"] for x in source_records if x["path"] == "cli-scope-signoff-2026-10-06.md"), "accepted signoff pin")

    log_lines = (RUN / "model.log").read_text(errors="replace").splitlines()
    def at(fragment):
        positions = [index for index, line in enumerate(log_lines) if fragment in line]
        c.check(len(positions) == 1, f"event once: {fragment}")
        return positions[0] if positions else -1

    first_id = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    second_id = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
    aircraft = "<TEACH-AIR-01,0>"
    events = [
        ("first launch", f"Time: 21.5 {first_id} mission starting, duration: 2 : {aircraft}"),
        ("first success", f"Time: 23.5 {first_id} mission success:"),
        ("first completion", f"Time: 23.5 {first_id} mission completed: {aircraft}"),
        ("turnround start", f"Time: 23.5  system turnround task 1 on {aircraft} started"),
        ("turnround seq1 start", f"Time: 23.5  subtask 2 seqno 1 within system turnround task 1 on {aircraft} started"),
        ("turnround seq1 work", f"Time: 23.5  subtask 2 seqno 1 within system turnround task 1 on {aircraft} starts performing"),
        ("turnround seq1 complete", f"Time: 23.6667  subtask 2 seqno 1 within system turnround task 1 on {aircraft} completed"),
        ("turnround seq2 start", f"Time: 23.6667  subtask 3 seqno 2 within system turnround task 1 on {aircraft} started"),
        ("turnround seq2 work", f"Time: 23.6667  subtask 3 seqno 2 within system turnround task 1 on {aircraft} starts performing"),
        ("second notice", "Time: 23.75 <TEACH-UNIT> mission ordered: BASIC-MISSION"),
        ("second created", f"Time: 23.75 {second_id} mission created:"),
        ("second activated", f"Time: 23.75 {second_id} mission activated, systems requested: 1"),
        ("second preassigned", f"Time: 23.75 {second_id} mission preassigns a system: {aircraft}"),
        ("turnround seq2 complete", f"Time: 24  subtask 3 seqno 2 within system turnround task 1 on {aircraft} completed"),
        ("turnround complete", f"Time: 24  system turnround task 1 on {aircraft} completed"),
        ("system arrives", f"Time: 24 <TEACH-AIR-01,BASE-01,0> System arrives {aircraft}, mission success"),
        ("second allocated", f"Time: 24 {second_id} mission allocates system: {aircraft}"),
        ("second prep start", f"Time: 24 {aircraft} preparation started, mission: {second_id}"),
        ("second prep complete", f"Time: 24.5 {aircraft} preparation ended, mission: {second_id}"),
        ("second launch", f"Time: 24.75 {second_id} mission starting, duration: 2 : {aircraft}"),
        ("second success", f"Time: 26.75 {second_id} mission success:"),
        ("second completion", f"Time: 26.75 {second_id} mission completed: {aircraft}"),
        ("second turnround complete", f"Time: 27.25  system turnround task 3 on {aircraft} completed"),
        ("terminal ready", f"Time: 27.25 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{aircraft}"),
    ]
    indices = {name: at(fragment) for name, fragment in events}
    c.check(list(indices.values()) == sorted(indices.values()) and all(index >= 0 for index in indices.values()), "physical event order")
    c.check(indices["second preassigned"] < indices["turnround complete"] < indices["second allocated"], "notice before release, allocation after")
    c.check(all(not ("mission allocates system" in line and second_id in line) for line in log_lines[:indices["turnround complete"]]), "no early physical allocation")
    c.check(all(not ("preparation started" in line and second_id in line) for line in log_lines[:indices["turnround complete"]]), "no early preparation")
    log = "\n".join(log_lines).lower()
    for forbidden in ["mission cancelled:", "mission aborted:", "fault occured", "pm task", "backorder", "resources waiting"]:
        c.check(forbidden not in log, f"absent {forbidden}")

    report = native_json(RUN / "report-raw.json")["report"]
    report_tables = {table["name"]: table for table in report["tables"]}
    c.check(set(report_tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "four report tables")
    expected_widths = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11), "SystemResults": (72, 40), "StockTotalResults": (72, 16)}
    for name, (count, width) in expected_widths.items():
        c.check(len(rows(report_tables[name])) == count and len(report_tables[name]["columns"]) == width, f"report dimensions {name}")
    input_tables = {table["name"]: table for table in read_json(SOURCE / "native-input.json")["model"]["tables"]}
    description = rows(input_tables["ProblemDescription"])[0][0]
    c.check(rows(report_tables["ProblemDescription"])[0][0] == description, "description source")
    summary = [1, 0, 36, 1, 0, 1, 0, 1, 0, 1, 0]
    for index, (actual, target) in enumerate(zip(rows(report_tables["ResultSummary"])[0], summary)):
        c.check(actual == target, f"summary cell {index}")

    # Occupancy is independently integrated from the logged lifecycle bounds.
    phases = {
        "NSYRY": [(0, 20.5), (27.25, 36)],
        "NSYMP": [(20.5, 21), (24, 24.5)],
        "NSYMR": [(21, 21.5), (24.5, 24.75)],
        "NSYMO": [(21.5, 23.5), (24.75, 26.75)],
        "NSYMT": [(23.5, 24), (26.75, 27.25)],
    }
    system = report_tables["SystemResults"]
    sys_columns = [column["name"] for column in system["columns"]]
    for index, row in enumerate(rows(system)):
        start = index / 2
        end = start + 0.5
        occupancy = {name: sum(overlap(start, end, a, b) for a, b in spans) / 0.5 for name, spans in phases.items()}
        expected = {name: 0 for name in sys_columns}
        expected.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": start, "ETINT": end, "NSYA": 1, "SYDT": None})
        expected.update(occupancy)
        expected["NSYMA"] = 1 - occupancy["NSYRY"]
        expected["FTMO"] = occupancy["NSYMO"]
        expected["STACC"] = occupancy["NSYMO"]
        expected["NPSTA"] = int(start in (20.5, 24))
        expected["NPSUC"] = int(start in (21, 24.5))
        for name, value in zip(sys_columns, row):
            c.check(value == expected[name] or isinstance(value, (int, float)) and isinstance(expected[name], (int, float)) and abs(value - expected[name]) < 1e-6, f"System row {index} {name}: {value} vs {expected[name]}")
    stock = report_tables["StockTotalResults"]
    stock_columns = [column["name"] for column in stock["columns"]]
    for index, row in enumerate(rows(stock)):
        expected = {name: 0 for name in stock_columns}
        expected.update({"STINT": index / 2, "ETINT": (index + 1) / 2, "PNB": 1})
        for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected[name] = None
        for name, value in zip(stock_columns, row):
            c.check(value == expected[name], f"Stock row {index} {name}: {value} vs {expected[name]}")
    report_cells = sum(len(rows(table)) * len(table["columns"]) for table in report_tables.values())
    c.check(report_cells == 4044, "4044 report cells")
    result = {
        "schema": "simlox-b04-var03-independent-readonly-replay/v1",
        "decision": "GO_BOUNDED" if not c.failures else "NO_GO",
        "checks_passed": c.count - len(c.failures),
        "checks_total": c.count,
        "failures": c.failures,
        "contract_sha256": digest(CASE / "contract.json"),
        "accepted_run_id": RUN.name,
        "accepted_closure_sha256": digest(RUN / "closure.json"),
        "accepted_raw_seals": len(closure["raw"]),
        "published_source_pins": len(source_records),
        "report_cells": report_cells,
        "scope": "Retrospective one-run classification: notice/preassignment during turnround; physical allocation after completion.",
        "limits": "No new native run, matched notice-time arm, general same-time priority, or GUI visual claim.",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": c.count, "failures": c.failures[:20]}, indent=2))


if __name__ == "__main__":
    main()
