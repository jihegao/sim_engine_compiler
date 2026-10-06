"""Independent standard-library replay of the accepted B05.var03 source pair.

No native process or author checker is invoked. Only the verdict in this review
directory is written.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parents[2]
SOURCE = CASE.parent / "B05-var03-predefined-inspect-v1.0.0"
OUT = HERE / "independent-verdict.json"
ARMS = {
    "ordinary": ("ordinary-control-input.json", "b05-var03-ordinary-20260930-01"),
    "predefined": ("predefined-inspect-input.json", "b05-var03-predefined-20260930-01"),
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def strict_json(path: Path):
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


def table_map(model):
    return {table["name"]: table for table in model["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def overlap(a, b, c, d):
    return max(0.0, min(b, d) - max(a, c))


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)


def git_bytes(relative: Path):
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative.as_posix()}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def expect_report(checks: Checks, arm: str, source_input, report):
    tables = table_map(report["report"])
    checks.check(
        set(tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
        f"{arm} report table set",
    )
    shapes = {
        "ProblemDescription": (1, 1),
        "ResultSummary": (1, 11),
        "SystemResults": (72, 40),
        "StockTotalResults": (72, 16),
    }
    for name, (count, width) in shapes.items():
        checks.check(
            len(rows(tables[name])) == count and len(tables[name]["columns"]) == width,
            f"{arm} {name} shape",
        )
    input_tables = table_map(source_input["model"])
    checks.check(
        rows(tables["ProblemDescription"])[0][0]
        == rows(input_tables["ProblemDescription"])[0][0],
        f"{arm} description",
    )
    summary = [1, 0, 36, 1, 0, 1, 0, 1, 0, 1, 0]
    for index, (actual, target) in enumerate(
        zip(rows(tables["ResultSummary"])[0], summary)
    ):
        checks.check(actual == target, f"{arm} summary {index}")
    system = tables["SystemResults"]
    system_columns = [column["name"] for column in system["columns"]]
    phases = {
        "NSYRY": [(0, 7), (10, 36)],
        "NSYMP": [(7, 7.5)],
        "NSYMR": [(7.5, 8)],
        "NSYMO": [(8, 10)],
    }
    for index, row in enumerate(rows(system)):
        start = index / 2
        end = start + 0.5
        amounts = {
            name: sum(overlap(start, end, left, right) for left, right in spans) / 0.5
            for name, spans in phases.items()
        }
        expected = {name: 0 for name in system_columns}
        expected.update(
            {
                "UNID": "Total over all Units",
                "SID": "Total over all Systems",
                "STINT": start,
                "ETINT": end,
                "NSYA": 1,
                "SYDT": None,
                "NPSTA": int(start == 7),
                "NPSUC": int(start == 7.5),
            }
        )
        expected.update(amounts)
        expected["NSYMA"] = 1 - amounts["NSYRY"]
        expected["FTMO"] = amounts["NSYMO"]
        expected["STACC"] = amounts["NSYMO"]
        for name, actual in zip(system_columns, row):
            checks.check(actual == expected[name], f"{arm} System {index} {name}")
    stock = tables["StockTotalResults"]
    stock_columns = [column["name"] for column in stock["columns"]]
    for index, row in enumerate(rows(stock)):
        expected = {name: 0 for name in stock_columns}
        expected.update({"STINT": index / 2, "ETINT": (index + 1) / 2, "PNB": 1})
        for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected[name] = None
        for name, actual in zip(stock_columns, row):
            checks.check(actual == expected[name], f"{arm} Stock {index} {name}")
    return tables


def main():
    checks = Checks()
    contract = strict_json(CASE / "contract.json")
    checks.check(
        sha(CASE / "contract.json")
        == "7a87b8d51a44b6fc0e5ed03324e6ac362eac8ca1b264a9644b7b9a55b3122706",
        "classification contract pin",
    )
    checks.check(
        sha(HERE / "independent-contract-go-2026-10-07.md")
        == "99f0392705f5d84a8705b06614658f3f12d1e8ceac58d1fcc80f4c79ad43e7c3",
        "contract review pin",
    )
    accepted_review = SOURCE / "review" / "independent-readonly-2026-09-30.json"
    checks.check(
        sha(accepted_review)
        == contract["accepted_source_pair"]["accepted_independent_report_sha256"],
        "accepted independent review pin",
    )
    # Check both locally pinned bytes and the published HEAD blobs. The prior
    # review is provenance, never used as an implementation or result oracle.
    tracked_files = [
        "ordinary-control-input.json",
        "predefined-inspect-input.json",
        "exact-diff.json",
        "contract.json",
        "cli-scope-signoff-2026-09-30.md",
        "review/independent-readonly-2026-09-30.json",
    ]
    for name in tracked_files:
        path = SOURCE / name
        published = git_bytes(path.relative_to(REPO))
        checks.check(published is not None and published == path.read_bytes(), f"published source bytes {name}")

    arm_data = {}
    for arm, (input_name, run_id) in ARMS.items():
        source_path = SOURCE / input_name
        run = SOURCE / "runs" / run_id
        source_input = strict_json(source_path)
        closure = strict_json(run / "closure.json")
        invocation = strict_json(run / "invocation.json")
        expected_hash = contract["accepted_source_pair"][f"{arm}_input_sha256"]
        checks.check(sha(source_path) == expected_hash, f"{arm} input seal")
        checks.check(
            sha(run / "closure.json")
            == contract["accepted_source_pair"][f"{arm}_closure_sha256"],
            f"{arm} closure seal",
        )
        checks.check(
            closure["source_hashes_before"]
            == closure["source_hashes_after"]
            == invocation["source_hashes_before"],
            f"{arm} source frozen",
        )
        checks.check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
        checks.check(closure["run_id"] == run_id and len(closure["raw"]) == 12, f"{arm} run identity and 12 seals")
        for name, seal in sorted(closure["raw"].items()):
            file = run / name
            checks.check(
                file.is_file()
                and file.stat().st_size == seal["bytes"]
                and sha(file) == seal["sha256"],
                f"{arm} raw seal {name}",
            )
        checks.check((run / "input.json").read_bytes() == source_path.read_bytes(), f"{arm} native input copy")
        checks.check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH0")
        steps = strict_json(run / "steps.json")
        checks.check([stage["name"] for stage in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} stages")
        for stage in steps:
            checks.check(stage["status"] == "completed" and stage["exit_code"] == 0 and stage["gui_preserved"], f"{arm} stage {stage['name']}")
        conversion = (run / "run.log").read_text(errors="replace").lower()
        checks.check("errors: 0" in conversion and "warnings: 2" in conversion and "notes: 0" in conversion and "warning #108" in conversion and "warning #126" in conversion, f"{arm} converter")
        checks.check((run / "model.sxo").stat().st_size > 4, f"{arm} valid output")
        native_model = native_json(run / "roundtrip-raw.json")["model"]
        authored_tables = table_map(source_input["model"])
        exported_tables = table_map(native_model)
        checks.check(sum(bool(rows(table)) for table in authored_tables.values()) == 17, f"{arm} 17 row-containing tables")
        for table_name, authored in authored_tables.items():
            exported = exported_tables[table_name]
            checks.check(
                [column["name"] for column in authored["columns"]]
                == [column["name"] for column in exported["columns"]],
                f"{arm} roundtrip columns {table_name}",
            )
            for authored_instance, exported_instance in zip(authored["instances"], exported["instances"]):
                for authored_row, exported_row in zip(authored_instance["rows"], exported_instance["rows"]):
                    for index, value in enumerate(authored_row):
                        checks.check(value == exported_row[index], f"{arm} roundtrip {table_name} {index}")
        log = (run / "model.log").read_text(errors="replace")
        mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
        aircraft = "<TEACH-AIR-01,0>"
        events = [
            f"Time: 7  subtask 0 seqno 1 within system preparation task 0 on {aircraft} starts performing, planned to last for 0.166667 hours",
            f"Time: 7.16667  subtask 0 seqno 1 within system preparation task 0 on {aircraft} completed",
            f"Time: 7.16667  subtask 1 seqno 2 within system preparation task 0 on {aircraft} starts performing, planned to last for 0.333333 hours",
            f"Time: 7.5  subtask 1 seqno 2 within system preparation task 0 on {aircraft} completed",
            f"Time: 7.5 {aircraft} preparation ended, mission: {mission}",
            f"Time: 8 {mission} mission starting, duration: 2 : {aircraft}",
            f"Time: 10 {mission} mission success:",
            f"Time: 10 {mission} mission completed: {aircraft}",
            f"Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{aircraft}",
        ]
        positions = []
        for event in events:
            checks.check(log.count(event) == 1, f"{arm} event {event}")
            positions.append(log.find(event))
        checks.check(positions == sorted(positions) and all(index >= 0 for index in positions), f"{arm} event order")
        for forbidden in ["mission cancelled:", "mission aborted:", "backorder", "resource availability test failed"]:
            checks.check(forbidden not in log.lower(), f"{arm} absent {forbidden}")
        report = native_json(run / "report-raw.json")
        tables = expect_report(checks, arm, source_input, report)
        arm_data[arm] = {"source": source_input, "log_bytes": (run / "model.log").read_bytes(), "tables": tables, "closure_sha256": sha(run / "closure.json"), "raw_count": len(closure["raw"])}

    ordinary_tables = table_map(arm_data["ordinary"]["source"]["model"])
    predefined_tables = table_map(arm_data["predefined"]["source"]["model"])
    differences = []
    for name, ordinary in ordinary_tables.items():
        predefined = predefined_tables[name]
        checks.check([column["name"] for column in ordinary["columns"]] == [column["name"] for column in predefined["columns"]], f"pair columns {name}")
        for ordinary_instance, predefined_instance in zip(ordinary["instances"], predefined["instances"]):
            for row_index, (ordinary_row, predefined_row) in enumerate(zip(ordinary_instance["rows"], predefined_instance["rows"])):
                for column_index, (left, right) in enumerate(zip(ordinary_row, predefined_row)):
                    if left != right:
                        differences.append((name, row_index, ordinary["columns"][column_index]["name"], left, right))
    checks.check(len(differences) == 2 and {(name, row, column) for name, row, column, _, _ in differences} == {("ProblemDescription", 0, "PDESC"), ("TaskBreakDown", 0, "SUTID")}, "two-cell pair delta")
    checks.check(next(right for name, _, column, _, right in differences if name == "TaskBreakDown" and column == "SUTID") == "<INSPECT>" and next(left for name, _, column, left, _ in differences if name == "TaskBreakDown" and column == "SUTID") == "INSPECT", "exact INSPECT identifier contrast")
    source_types = rows(ordinary_tables["SubTaskType"])
    checks.check([row[0] for row in source_types] == ["INSPECT", "SERVICE"], "ordinary custom type definitions")
    prep_rows = rows(ordinary_tables["TaskBreakDown"])
    checks.check([row[:4] for row in prep_rows] == [["PREP-FIXED", 1, "INSPECT", 1 / 6], ["PREP-FIXED", 2, "SERVICE", 1 / 3]], "ordinary exact breakdown")
    checks.check(arm_data["ordinary"]["log_bytes"] == arm_data["predefined"]["log_bytes"], "physical log byte equality")
    report_cell_count = 0
    for name, ordinary in arm_data["ordinary"]["tables"].items():
        predefined = arm_data["predefined"]["tables"][name]
        for row_index, (left_row, right_row) in enumerate(zip(rows(ordinary), rows(predefined))):
            for column_index, (left, right) in enumerate(zip(left_row, right_row)):
                report_cell_count += 1
                checks.check(name == "ProblemDescription" or left == right, f"paired report equality {name} {(row_index, column_index)}")
    checks.check(report_cell_count == 4044, "4044 cells per report")

    verdict = {
        "schema": "simlox-b05-var06-independent-readonly-replay/v1",
        "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
        "checks_passed": checks.count - len(checks.failures),
        "checks_total": checks.count,
        "failures": checks.failures,
        "contract_sha256": sha(CASE / "contract.json"),
        "accepted_source_pair": {arm: {key: value for key, value in data.items() if key in ("closure_sha256", "raw_count")} for arm, data in arm_data.items()},
        "report_cells_each": report_cell_count,
        "scope": "Read-only classification of one accepted ordinary INSPECT versus predefined <INSPECT> preparation pair; no new native run.",
        "limits": "Generic log labels do not print SUTID; source plus exact roundtrip bounds attribution. No general semantic equivalence claim.",
    }
    OUT.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": verdict["decision"], "checks": checks.count, "failures": checks.failures[:20]}, indent=2))


if __name__ == "__main__":
    main()
