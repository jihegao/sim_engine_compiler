"""Independent read-only replay of C02 joint-resource availability runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parents[2]
SOURCE = CASE.parent / "C02-joint-resources-v1.0.2"
RAW = Path(
    r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support"
    r"\C02-joint-resources-v1.0.2\runs"
)
RUNS = {
    "available": (SOURCE / "inputs" / "serial-both.json", "c02-v102-serial-both-ssh-20260929-02"),
    "equipment_zero": (SOURCE / "inputs" / "serial-equipment-zero.json", "c02-v102-serial-zero-ssh-20260929-02"),
}
OUT = HERE / "independent-verdict.json"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ",":
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following == len(text) or text[following] not in "}]":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def tables(model):
    return {table["name"]: table for table in model["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def overlap(left, right, start, end):
    return max(0.0, min(right, end) - max(left, start))


def equal(actual, expected, tolerance=3e-5):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) <= tolerance
    return actual == expected


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)


def git_blob(path: Path):
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.relative_to(REPO).as_posix()}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def check_report(checks: Checks, arm: str, source_model, report):
    successful = arm == "available"
    report_tables = tables(report["report"])
    shape = {
        "ProblemDescription": (1, 1),
        "ResultSummary": (1, 11),
        "SystemResults": (72, 40),
        "StockTotalResults": (72, 16),
        "ResourceResults": (72, 16),
        "ResourceResultsTotal": (1, 14),
    }
    checks.check(set(report_tables) == set(shape), f"{arm} six report tables")
    for name, (height, width) in shape.items():
        checks.check(len(rows(report_tables[name])) == height and len(report_tables[name]["columns"]) == width, f"{arm} {name} shape")
    source_description = rows(tables(source_model)["ProblemDescription"])[0][0]
    checks.check(rows(report_tables["ProblemDescription"])[0][0] == source_description, f"{arm} description")
    summary = [1, 0, 36, int(successful), 0, int(successful), 0, int(successful), 0, int(successful), 0]
    for index, (actual, expected) in enumerate(zip(rows(report_tables["ResultSummary"])[0], summary)):
        checks.check(actual == expected, f"{arm} summary {index}")
    system = report_tables["SystemResults"]
    sys_columns = [column["name"] for column in system["columns"]]
    prep_end = 7.5 if successful else 7 + 7 / 12
    phases = {
        "NSYRY": [(0, 7), (10 if successful else prep_end, 36)],
        "NSYMP": [(7, prep_end)],
        "NSYMR": [(7.5, 8)] if successful else [],
        "NSYMO": [(8, 10)] if successful else [],
    }
    for index, row in enumerate(rows(system)):
        start = index / 2
        end = start + 0.5
        occupation = {name: sum(overlap(start, end, left, right) for left, right in spans) / 0.5 for name, spans in phases.items()}
        expected = {name: 0 for name in sys_columns}
        expected.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": start, "ETINT": end, "NSYA": 1, "SYDT": None, "NPSTA": int(start == 7), "NPSUC": int(successful and start == 7.5)})
        expected.update(occupation)
        expected["NSYMA"] = 1 - occupation["NSYRY"]
        expected["FTMO"] = occupation["NSYMO"]
        expected["STACC"] = occupation["NSYMO"]
        for column, actual in zip(sys_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} System {index} {column}: {actual} vs {expected[column]}")
    stock = report_tables["StockTotalResults"]
    stock_columns = [column["name"] for column in stock["columns"]]
    for index, row in enumerate(rows(stock)):
        expected = {name: 0 for name in stock_columns}
        expected.update({"STINT": index / 2, "ETINT": (index + 1) / 2, "PNB": 1})
        for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected[name] = None
        for column, actual in zip(stock_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} Stock {index} {column}")
    resource = report_tables["ResourceResults"]
    resource_columns = [column["name"] for column in resource["columns"]]
    for index, row in enumerate(rows(resource)):
        start = index / 2
        end = start + 0.5
        usage = 2 * overlap(start, end, 7, 7 + 1 / 6) / 0.5 if successful else 0
        waiting = 0 if successful else overlap(start, end, 7, 7 + 7 / 12) / 0.5
        expected = {name: 0 for name in resource_columns}
        capacity = 2 if successful else 1
        expected.update({"RID": "Total over all Resources", "STID": "Total over all Stations", "STINT": start, "ETINT": end, "NR": capacity, "NRA": capacity, "NRN": capacity, "NRUM": usage, "NRW": waiting})
        for column, actual in zip(resource_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} Resource {index} {column}: {actual} vs {expected[column]}")
    total = report_tables["ResourceResultsTotal"]
    total_columns = [column["name"] for column in total["columns"]]
    expected_total = {name: 0 for name in total_columns}
    capacity = 2 if successful else 1
    expected_total.update({"RID": "Total over all Resources", "STID": "Total over all Stations", "NR": capacity, "NRA": capacity, "NRN": capacity, "NRUM": (2 / 6) / 36 if successful else 0, "NRW": 0 if successful else (7 / 12) / 36})
    for column, actual in zip(total_columns, rows(total)[0]):
        checks.check(equal(actual, expected_total[column]), f"{arm} ResourceTotal {column}")
    return report_tables


def check_events(checks: Checks, arm: str, run: Path):
    log = (run / "model.log").read_text(errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    aircraft = "<TEACH-AIR-01,0>"
    required = [
        f"Time: 7 {mission} mission allocates system: {aircraft}",
        f"Time: 7 {aircraft} preparation started, mission: {mission}",
        f"Time: 7  subtask 0 seqno 1 within system preparation task 0 on {aircraft} requests resources",
        "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
        f"Availability test on  <E-GSE at <BASE-01,0>> request for: 1 {'OK' if arm == 'available' else 'failed'}",
    ]
    if arm == "available":
        required.extend([
            "Time: 7  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
            "Time: 7  <E-GSE at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
            f"Time: 7  subtask 0 seqno 1 within system preparation task 0 on {aircraft} starts performing, planned to last for 0.166667 hours",
            "Time: 7.16667  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            "Time: 7.16667  <E-GSE at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            f"Time: 7.16667  subtask 1 seqno 2 within system preparation task 0 on {aircraft} starts performing, planned to last for 0.333333 hours",
            f"Time: 7.5 {aircraft} preparation ended, mission: {mission}",
            f"Time: 8 {mission} mission starting, duration: 2 : {aircraft}",
            f"Time: 10 {mission} mission success:",
            f"Time: 10 {mission} mission completed: {aircraft}",
            f"Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{aircraft}",
        ])
        forbidden = ["mission cancelled:", "request for: 1 failed"]
    else:
        required.extend([
            f"Time: 7.58333 {mission} mission cancelled:",
            f"Time: 7.58333  subtask 0 seqno 1 within system preparation task 0 on {aircraft} resource waiting stopped",
            f"Time: 7.58333 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{aircraft}",
        ])
        forbidden = ["allocated to maintenance task: 1", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", "mission starting, duration: 2", "mission success:"]
    positions = []
    for fragment in required:
        checks.check(log.count(fragment) == 1, f"{arm} event {fragment}")
        positions.append(log.find(fragment))
    checks.check(positions == sorted(positions) and all(index >= 0 for index in positions), f"{arm} event order")
    for fragment in forbidden:
        checks.check(fragment not in log, f"{arm} absent {fragment}")


def main():
    checks = Checks()
    contract = read_json(CASE / "contract.json")
    checks.check(sha(CASE / "contract.json") == "475f5d05aec01c27e57cbe2c2afd7fc77e3f60c5dd0e33783b834d7de2b5ba56", "classification contract")
    checks.check(sha(SOURCE / "review" / "independent-readonly-2026-09-29.json") == contract["accepted_source_pair"]["original_independent_report_sha256"], "original review provenance")
    tracked = subprocess.run(["git", "ls-files", "--", SOURCE.relative_to(REPO).as_posix()], cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
    checks.check(len(tracked) == 18, "18 published source files")
    for relative in tracked:
        local = REPO / relative
        published = git_blob(local)
        if local.name == ".gitignore":
            checks.check(local.read_bytes() == b"/runs/\r\n" and sha(local) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f", "local CRLF .gitignore")
            checks.check(published == b"/runs/\n" and sha_bytes(published) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933", "published LF .gitignore")
        else:
            checks.check(published is not None and published == local.read_bytes(), f"published byte identity {relative}")
    source_models = {}
    report_tables = {}
    run_info = {}
    for arm, (source_file, run_id) in RUNS.items():
        run = RAW / run_id
        pin = contract["accepted_source_pair"][arm]
        closure = read_json(run / "closure.json")
        invocation = read_json(run / "invocation.json")
        checks.check(sha(source_file) == pin["input_sha256"], f"{arm} source input")
        checks.check(sha(run / "closure.json") == pin["closure_sha256"], f"{arm} closure")
        checks.check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
        checks.check(closure["input_sha256"] == invocation["input_sha256"] == sha(source_file) and invocation["contract_sha256"] == sha(SOURCE / "contract.json"), f"{arm} source/contract pins")
        checks.check(closure["run_id"] == run_id and len(closure["raw"]) == 11, f"{arm} run and raw count")
        for name, seal in sorted(closure["raw"].items()):
            file = run / name
            checks.check(file.is_file() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"], f"{arm} raw seal {name}")
        checks.check((run / "input.json").read_bytes() == source_file.read_bytes(), f"{arm} input copy")
        checks.check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH0")
        stages = read_json(run / "steps.json")
        checks.check([stage["name"] for stage in stages] == ["import", "export", "calc", "jsonreport"], f"{arm} stage names")
        for stage in stages:
            checks.check(stage["exit_code"] == 0 and stage["coexisting_gui_present_after"], f"{arm} stage {stage['name']}")
        calc = (run / "run.log").read_text(errors="replace").lower()
        checks.check("errors: 0" in calc and "warnings: 2" in calc and "notes: 0" in calc and "warning #108" in calc and "warning #126" in calc, f"{arm} converter")
        checks.check((run / "model.sxo").stat().st_size > 4, f"{arm} valid SXO")
        source_model = read_json(source_file)["model"]
        source_models[arm] = source_model
        authored = tables(source_model)
        exported = tables(native_json(run / "roundtrip-raw.json")["model"])
        checks.check(set(authored) == set(exported), f"{arm} roundtrip table names")
        checks.check(sum(bool(rows(table)) for table in authored.values()) == 20 and sum(any(any(value is not None for value in row) for row in rows(table)) for table in authored.values()) == 17, f"{arm} 20 row-containing/17 value-bearing tables")
        for name, table in authored.items():
            native = exported[name]
            checks.check([column["name"] for column in table["columns"]] == [column["name"] for column in native["columns"]], f"{arm} roundtrip columns {name}")
            checks.check(len(native["instances"]) >= len(table["instances"]), f"{arm} roundtrip instance count {name}")
            for instance, native_instance in zip(table["instances"], native["instances"]):
                checks.check(len(native_instance["rows"]) >= len(instance["rows"]) and all(all(value is None for value in row) for row in native_instance["rows"][len(instance["rows"]):]), f"{arm} roundtrip only empty native-added rows {name}")
                for source_row, native_row in zip(instance["rows"], native_instance["rows"]):
                    for index, value in enumerate(source_row):
                        checks.check(value == native_row[index], f"{arm} roundtrip {name} {index}")
        check_events(checks, arm, run)
        report_tables[arm] = check_report(checks, arm, source_model, native_json(run / "report-raw.json"))
        run_info[arm] = {"run_id": run_id, "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"])}
    qualified = tables(source_models["available"])
    wrong = tables(source_models["equipment_zero"])
    differences = []
    for name, table in qualified.items():
        other = wrong[name]
        checks.check([column["name"] for column in table["columns"]] == [column["name"] for column in other["columns"]], f"source columns {name}")
        for left_instance, right_instance in zip(table["instances"], other["instances"]):
            for row_index, (left_row, right_row) in enumerate(zip(left_instance["rows"], right_instance["rows"])):
                for column_index, (before, after) in enumerate(zip(left_row, right_row)):
                    if before != after:
                        differences.append((name, row_index, table["columns"][column_index]["name"], before, after))
    checks.check(differences == [("ResourceAllocation", 2, "RQTY", 1, 0)], f"exact one-cell equipment delta {differences}")
    resource_columns = [column["name"] for column in qualified["ResourceAllocation"]["columns"]]
    resource_rows = rows(qualified["ResourceAllocation"])
    checks.check([row[resource_columns.index("RID")] for row in resource_rows] == ["P-CREW", "P-OTHER", "E-GSE"], "crew/device RID identities")
    checks.check([row[resource_columns.index("RQTY")] for row in resource_rows] == [1, 0, 1] and [row[resource_columns.index("RQTY")] for row in rows(wrong["ResourceAllocation"])] == [1, 0, 0], "crew one, equipment one-to-zero")
    demand = rows(qualified["SubTaskResource"])
    checks.check([row[:4] for row in demand] == [["PREP-FIXED", 1, "P-CREW", 1], ["PREP-FIXED", 1, "E-GSE", 1]], "joint one-each demand")
    checks.check([row[:4] for row in rows(qualified["TaskBreakDown"])] == [["PREP-FIXED", 1, "INSPECT", 1 / 6], ["PREP-FIXED", 2, "SERVICE", 1 / 3]], "serial ten-plus-twenty-minute subtasks")
    checks.check(rows(qualified["ProblemDescription"]) == rows(wrong["ProblemDescription"]), "same description")
    checks.check(rows(report_tables["available"]["ProblemDescription"]) == rows(report_tables["equipment_zero"]["ProblemDescription"]), "same reported description")
    checks.check(rows(report_tables["available"]["StockTotalResults"]) == rows(report_tables["equipment_zero"]["StockTotalResults"]), "same complete Stock ledger")
    report_cells_each = sum(len(rows(table)) * len(table["columns"]) for table in report_tables["available"].values())
    checks.check(report_cells_each == 5210, "5210 cells per report")
    result = {
        "schema": "simlox-c02-var02-independent-readonly-replay/v1",
        "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
        "checks_passed": checks.count - len(checks.failures),
        "checks_total": checks.count,
        "failures": checks.failures,
        "contract_sha256": sha(CASE / "contract.json"),
        "runs": run_info,
        "raw_seals": sum(item["raw_seals"] for item in run_info.values()),
        "report_cells_each": report_cells_each,
        "scope": "Retrospective fixed-seed E-GSE zero-capacity contrast with crew one in a joint-resource task.",
        "limits": "No new native replication, general all-or-none rule, source-derived cancellation deadline, GUI visual or cross-engine claim.",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": checks.count, "failures": checks.failures[:25]}, indent=2))


if __name__ == "__main__":
    main()
