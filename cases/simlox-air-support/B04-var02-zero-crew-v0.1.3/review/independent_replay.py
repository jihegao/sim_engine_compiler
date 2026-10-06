"""Independent read-only replay of B04.var02 zero-crew native evidence.

This does not import or invoke the case's author validator or SIMLOX. The only
write is the machine-readable verdict alongside this script.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
RUN = CASE / "runs" / "b04-var02-zero-crew-v013-ssh-20261007-01"
PARENT = CASES / "B04-var02-turnround-resource-v0.1.1"
PARENT_RUN = PARENT / "runs" / "b04-var02-turn-resource-v011-ssh-20261006-01"
C01_RUN = Path(
    r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support"
    r"\C01-personnel-capacity-v1.0.2\runs\c01-v102-cap0-ssh-20260929-03"
)
VERDICT = HERE / "independent-verdict.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    """Remove native trailing commas in one pass without touching string data."""
    source = path.read_text(encoding="utf-8-sig")
    output = []
    in_string = False
    escaped = False
    for i, char in enumerate(source):
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
            next_index = i + 1
            while next_index < len(source) and source[next_index].isspace():
                next_index += 1
            if next_index == len(source) or source[next_index] not in "}]":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def tables(model):
    return {table["name"]: table for table in model["tables"]}


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


def check_seals(checks: Checks, closure, directory: Path, label: str):
    for name, record in closure["raw"].items():
        path = directory / name
        checks.check(
            path.is_file()
            and path.stat().st_size == record["bytes"]
            and sha(path) == record["sha256"],
            f"{label} raw seal {name}",
        )


def replay_b04():
    checks = Checks()
    closure = strict_json(RUN / "closure.json")
    parent_closure = strict_json(PARENT_RUN / "closure.json")
    contract = strict_json(CASE / "contract.json")
    approval = strict_json(HERE / "independent-prelaunch-go.json")
    invocation = strict_json(RUN / "invocation.json")
    steps = strict_json(RUN / "steps.json")

    check_seals(checks, closure, RUN, "child")
    check_seals(checks, parent_closure, PARENT_RUN, "parent")
    checks.check(len(closure["raw"]) == 13 and len(parent_closure["raw"]) == 13, "seal counts")
    checks.check(
        sha(RUN / "closure.json")
        == "aaa61f92f7a675361ba6e16d6fb4e92cbd2b1a0b179349f30cbc4e3a32e773ca",
        "child closure stable",
    )
    checks.check(
        sha(PARENT_RUN / "closure.json") == contract["accepted_parent"]["closure_sha256"],
        "parent closure",
    )
    checks.check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    checks.check(
        closure["source_hashes_before"]
        == closure["source_hashes_after"]
        == invocation["source_hashes_before"],
        "source frozen",
    )
    source_files = [
        ("child_input", CASE / "native-input.json"),
        ("child_contract", CASE / "contract.json"),
        ("builder", CASE / "build.py"),
        ("parent_diff_checker", CASE / "check_parent_diff.py"),
        ("roundtrip_checker", CASE / "check_roundtrip.py"),
        ("behavior_validator", CASE / "validate_native_cli.py"),
        ("runner_script", CASE / "run_native_ssh.ps1"),
        ("accepted_input", PARENT / "native-input.json"),
        ("accepted_contract", PARENT / "contract.json"),
        ("accepted_closure", PARENT_RUN / "closure.json"),
        ("accepted_report", PARENT_RUN / "report-raw.json"),
        ("prelaunch_approval", HERE / "independent-prelaunch-go.json"),
    ]
    for key, path in source_files:
        checks.check(
            path.is_file() and sha(path) == closure["source_hashes_before"][key],
            f"source {key}",
        )
    checks.check(
        approval["contract_sha256"] == sha(CASE / "contract.json")
        and approval["input_sha256"] == sha(CASE / "native-input.json")
        and approval["runner_sha256"] == sha(CASE / "run_native_ssh.ps1")
        and approval["validator_sha256"] == sha(CASE / "validate_native_cli.py"),
        "approval hashes",
    )
    checks.check(
        invocation["session_id"] == 0
        and invocation["ssh_connection_present"]
        and "sshd.exe" in invocation["ssh_ancestor_names"],
        "ssh0",
    )
    checks.check(
        invocation["gui"]["pid"] == 13340
        and invocation["gui"]["session_id"] == 1
        and invocation["gui"]["start_unix_ms"] == 1790590196826,
        "gui",
    )
    checks.check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "mutex")
    checks.check(
        [step["name"] for step in steps]
        == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"],
        "steps",
    )
    for step in steps:
        checks.check(
            step["exit_code"] == 0
            and step["gui_preserved"]
            and step["status"] == "completed",
            f"step {step['name']}",
        )

    parent_input = tables(strict_json(PARENT / "native-input.json")["model"])
    child_input = tables(strict_json(CASE / "native-input.json")["model"])
    differences = []
    cell_count = 0
    for name, parent_table in parent_input.items():
        child_table = child_input[name]
        checks.check(
            [column["name"] for column in parent_table["columns"]]
            == [column["name"] for column in child_table["columns"]],
            f"columns {name}",
        )
        for parent_instance, child_instance in zip(
            parent_table["instances"], child_table["instances"]
        ):
            checks.check(
                parent_instance["instance_name"] == child_instance["instance_name"]
                and len(parent_instance["rows"]) == len(child_instance["rows"]),
                f"instance {name}",
            )
            for row_index, (parent_row, child_row) in enumerate(
                zip(parent_instance["rows"], child_instance["rows"])
            ):
                for column_index, (before, after) in enumerate(zip(parent_row, child_row)):
                    cell_count += 1
                    if before != after:
                        differences.append(
                            (
                                name,
                                row_index,
                                parent_table["columns"][column_index]["name"],
                                before,
                                after,
                            )
                        )
    checks.check(
        cell_count == 249 and differences == [("ResourceAllocation", 0, "RQTY", 1, 0)],
        "source delta",
    )
    checks.check(
        (RUN / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes(),
        "input copy",
    )
    exported = tables(native_json(RUN / "roundtrip-raw.json")["model"])
    populated = sum(bool(rows(table)) for table in child_input.values())
    checks.check(populated == 21, "21 row-containing incl null placeholders")
    for name, authored in child_input.items():
        native = exported[name]
        checks.check(
            [column["name"] for column in authored["columns"]]
            == [column["name"] for column in native["columns"]],
            f"roundtrip columns {name}",
        )
        for authored_instance, native_instance in zip(
            authored["instances"], native["instances"]
        ):
            for authored_row, native_row in zip(
                authored_instance["rows"], native_instance["rows"]
            ):
                for index, value in enumerate(authored_row):
                    checks.check(value == native_row[index], f"roundtrip {name} {index}")

    log = (RUN / "model.log").read_text(errors="replace")
    calc = (RUN / "run.log").read_text(errors="replace").lower()
    event_tests = [
        (
            "Time: 21.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log,
            "first mission launch h21.5",
        ),
        (
            "Time: 23.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log
            and "Time: 23.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log,
            "first mission success and completion h23.5",
        ),
        (
            "Time: 23.5  system turnround task 1 on <TEACH-AIR-01,0> started" in log
            and "Time: 23.5  subtask 2 seqno 1 within system turnround task 1 on <TEACH-AIR-01,0> requests resources" in log,
            "turnround crew request h23.5",
        ),
        (
            log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") == 2
            and "Time: 24  subtask 2 seqno 1 within system turnround task 1 on <TEACH-AIR-01,0> resource availability test" in log,
            "failed one-crew tests h23.5 and h24",
        ),
        (
            "Time: 23.75 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission waiting:  timeout at 25" in log,
            "second mission waiting h23.75",
        ),
        (
            "Time: 25 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in log,
            "second mission cancellation h25",
        ),
    ]
    for condition, label in event_tests:
        checks.check(condition, label)
    for fragment in [
        "resources booked",
        "subtask 2 seqno 1 within system turnround task 1 performing",
        "subtask 3 seqno 2 within system turnround task 1 started",
        "system turnround task 1 on <TEACH-AIR-01,0> completed",
        "System arrives",
    ]:
        checks.check(fragment.lower() not in log.lower(), f"absent {fragment}")
    checks.check(
        "errors: 0" in calc and "warnings: 2" in calc and "notes: 0" in calc,
        "converter summary",
    )
    checks.check("warning #108" in calc and "warning #126" in calc, "warnings")
    checks.check((RUN / "model.sxo").stat().st_size > 4, "valid output")

    report = tables(native_json(RUN / "report-raw.json")["report"])
    parent_report = tables(native_json(PARENT_RUN / "report-raw.json")["report"])
    expected_tables = {
        "ProblemDescription",
        "ResultSummary",
        "SystemResults",
        "StockTotalResults",
        "ResourceResults",
        "ResourceResultsTotal",
    }
    checks.check(set(report) == set(parent_report) == expected_tables, "table set")
    for name, count, width in [
        ("ProblemDescription", 1, 1),
        ("ResultSummary", 1, 11),
        ("SystemResults", 72, 40),
        ("StockTotalResults", 72, 16),
        ("ResourceResults", 72, 16),
        ("ResourceResultsTotal", 1, 14),
    ]:
        checks.check(
            len(rows(report[name])) == count and len(report[name]["columns"]) == width,
            f"{name} dimensions",
        )
    for name in ["ProblemDescription", "StockTotalResults"]:
        for row_index, (actual, expected) in enumerate(
            zip(rows(report[name]), rows(parent_report[name]))
        ):
            for column_index, (value, target) in enumerate(zip(actual, expected)):
                checks.check(value == target, f"{name} {(row_index, column_index)}")
    summary_expected = [1, 0, 36, 0.5, 0, 0.5, 0, 0.5, 0, 0.5, 0]
    for index, (value, target) in enumerate(
        zip(rows(report["ResultSummary"])[0], summary_expected)
    ):
        checks.check(value == target, f"summary {index}")
    for name in ["SystemResults", "ResourceResults"]:
        table = report[name]
        columns = [column["name"] for column in table["columns"]]
        parent_rows = rows(parent_report[name])
        for row_index, actual in enumerate(rows(table)):
            for column_index, (column, value) in enumerate(zip(columns, actual)):
                if column in ("STINT", "ETINT", "UNID", "SID", "RID", "STID"):
                    target = parent_rows[row_index][column_index]
                elif name == "SystemResults" and row_index < 47:
                    target = parent_rows[row_index][column_index]
                elif name == "SystemResults" and column in ("NSYMA", "NSYMT", "NSYA"):
                    target = 1
                elif name == "SystemResults" and column == "SYDT":
                    target = None
                elif name == "ResourceResults" and column == "NRW":
                    target = int(row_index >= 47)
                else:
                    target = 0
                checks.check(
                    value == target,
                    f"{name} {(row_index, column, value, target)}",
                )
    total = report["ResourceResultsTotal"]
    total_columns = [column["name"] for column in total["columns"]]
    parent_total = rows(parent_report["ResourceResultsTotal"])[0]
    for index, (column, value) in enumerate(
        zip(total_columns, rows(total)[0])
    ):
        target = parent_total[index] if column in ("RID", "STID") else 25 / 72 if column == "NRW" else 0
        checks.check(
            value == target
            or isinstance(value, (int, float))
            and abs(value - target) < 1e-6,
            f"resource total {column}",
        )
    return checks, {
        "closure_sha256": sha(RUN / "closure.json"),
        "parent_closure_sha256": sha(PARENT_RUN / "closure.json"),
        "authored_cells": cell_count,
        "authored_row_containing_tables": populated,
        "report_cells": sum(len(rows(table)) * len(table["columns"]) for table in report.values()),
        "child_raw_seals": len(closure["raw"]),
        "parent_raw_seals": len(parent_closure["raw"]),
    }


def replay_c01():
    checks = Checks()
    closure_path = C01_RUN / "closure.json"
    checks.check(
        closure_path.is_file()
        and sha(closure_path)
        == "722e9eab571f8a7bc32aa593fe8782b30cc182a4a196b93f0f559129f85f4dcd",
        "C01 closure pin",
    )
    closure = strict_json(closure_path)
    checks.check(
        sha(C01_RUN / "input.json")
        == "02d1e3c1cdb585b73a00cf73b58f9d5fe6295c45c6fdc282a7c80c443499fdeb",
        "C01 input pin",
    )
    check_seals(checks, closure, C01_RUN, "C01")
    return checks, {"closure_sha256": sha(closure_path), "raw_seals": len(closure["raw"])}


def main():
    b04, b04_data = replay_b04()
    c01, c01_data = replay_c01()
    result = {
        "schema": "simlox-b04-var02-zero-crew-independent-replay/v1",
        "run_id": RUN.name,
        "decision": "GO_BOUNDED" if not b04.failures and not c01.failures else "NO_GO",
        "b04_checks": {"passed": b04.count - len(b04.failures), "total": b04.count, "failures": b04.failures},
        "c01_supplemental_checks": {
            "passed": c01.count - len(c01.failures),
            "total": c01.count,
            "failures": c01.failures,
        },
        "b04_evidence": b04_data,
        "c01_evidence": c01_data,
        "scope": "one fixed-seed, one-aircraft zero-capacity turnround; C01 is a mapping precedent",
    }
    VERDICT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "b04": b04.count, "c01": c01.count, "failures": b04.failures + c01.failures}, indent=2))


if __name__ == "__main__":
    main()
