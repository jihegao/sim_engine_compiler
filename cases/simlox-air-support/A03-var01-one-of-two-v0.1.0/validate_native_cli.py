"""Strict read-only native validator for the frozen A03.var01 one-of-two test."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A03-two-aircraft-formation-v1.0.1"
PREREQ = ROOT / "A02-single-aircraft-repeated-missions"
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-28/simlox-issue18-ssh-current/cases/simlox-air-support/A03-two-aircraft-formation-v1.0.1/runs/a03-v101-ssh-gui-20260929-01")
RUN_ID = "a03-var01-one-of-two-v010-ssh-20261006-01"
RUN = HERE / "runs" / RUN_ID
TAG = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIRCRAFT = "<TEACH-AIR-01,0>"
DEADLINE = 8 + 1 / 3


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    """Parse native JSON with trailing commas in memory only."""
    source = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(source):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == ",":
            following = index + 1
            while following < len(source) and source[following].isspace():
                following += 1
            if following >= len(source) or source[following] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(document: dict, kind: str) -> dict[str, dict]:
    values = document[kind]["tables"]
    result = {entry["name"]: entry for entry in values}
    if len(result) != len(values):
        raise ValueError(f"duplicate {kind} table")
    return result


def shape(table: dict) -> tuple[list[str], list[list]]:
    columns = [field["name"] for field in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError("invalid table shape")
    return columns, rows


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left))


def main() -> int:
    count = 0
    categories: dict[str, int] = {}
    failures: list[str] = []

    def equal(category: str, label: str, got, wanted) -> None:
        nonlocal count
        count += 1
        categories[category] = categories.get(category, 0) + 1
        if got != wanted:
            failures.append(f"{category} {label}: got {got!r}, expected {wanted!r}")

    def near(category: str, label: str, got, wanted: float, tolerance: float = 1e-5) -> None:
        equal(category, label, isinstance(got, (int, float)) and abs(got - wanted) <= tolerance, True)

    try:
        contract = parse(HERE / "contract.json")
        accepted = contract["accepted_parent"]
        prerequisite = contract["instructional_prerequisite"]
        for key, filename in (("input_sha256", "native-input.json"), ("contract_sha256", "contract.json"),
                              ("signoff_sha256", "cli-scope-signoff-2026-09-29.md"),
                              ("independent_review_sha256", "review/independent-readonly-2026-09-29.json")):
            equal("source", f"accepted A03 {filename}", sha(PARENT / filename), accepted[key])
        equal("source", "accepted A03 closure", sha(PARENT_RUN / "closure.json"), accepted["closure_sha256"])
        equal("source", "A02 input", sha(PREREQ / "native-input.json"), prerequisite["input_sha256"])
        equal("source", "A02 signoff", sha(PREREQ / "cli-scope-signoff-2026-09-29.md"), prerequisite["signoff_sha256"])
        equal("source", "installed manual", sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")), contract["manual"]["installed_pdf_sha256"])
        parent_closure = parse(PARENT_RUN / "closure.json")
        equal("parent_raw", "11 parent raw files", len(parent_closure["raw"]), 11)
        for filename, seal in sorted(parent_closure["raw"].items()):
            path = PARENT_RUN / filename
            equal("parent_raw", f"{filename} SHA", sha(path), seal["sha256"])
            equal("parent_raw", f"{filename} size", path.stat().st_size, seal["bytes"])

        closure = parse(RUN / "closure.json")
        invocation = parse(RUN / "invocation.json")
        steps = parse(RUN / "steps.json")
        equal("child_raw", "run identity", closure["run_id"], RUN_ID)
        equal("child_raw", "invocation identity", invocation["run_id"], RUN_ID)
        equal("child_raw", "closure error", closure["error"], None)
        equal("child_raw", "invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        equal("child_raw", "12 sealed child files", len(closure["raw"]), 12)
        for filename, seal in sorted(closure["raw"].items()):
            path = RUN / filename
            equal("child_raw", f"{filename} SHA", sha(path), seal["sha256"])
            equal("child_raw", f"{filename} size", path.stat().st_size, seal["bytes"])
        before = closure["source_hashes_before"]
        equal("source", "before-after source pins", closure["source_hashes_after"], before)
        equal("source", "invocation source pins", invocation["source_hashes_before"], before)
        approved_roots = (HERE, PARENT, PREREQ, PARENT_RUN)
        approved_paths = [path for root in approved_roots for path in root.rglob("*") if path.is_file()]
        approved_paths += [
            Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        ]
        approved_hashes = {sha(path) for path in approved_paths}
        for label, digest in sorted(before.items()):
            equal("source", f"{label} resolves to approved frozen bytes", digest in approved_hashes, True)
        equal("source", "run input copy", sha(RUN / "input.json"), sha(HERE / "native-input.json"))
        equal("source", "input invocation", invocation["input_sha256"], sha(HERE / "native-input.json"))
        equal("source", "contract invocation", invocation["contract_sha256"], sha(HERE / "contract.json"))
        equal("source", "runner invocation", invocation["runner_script_sha256"], sha(HERE / "run_native_ssh.ps1"))
        equal("source", "child input closure", before.get("child_input", before.get("input")), sha(HERE / "native-input.json"))
        equal("source", "child contract closure", before.get("child_contract", before.get("contract")), sha(HERE / "contract.json"))
        equal("source", "validator closure", before.get("behavior_validator", before.get("validator")), sha(HERE / "validate_native_cli.py"))
        equal("source", "accepted input closure", before.get("accepted_input", before.get("parent_input")), accepted["input_sha256"])
        equal("source", "accepted closure pin", before.get("accepted_closure", before.get("parent_closure")), accepted["closure_sha256"])
        equal("guard", "session 0", invocation["session_id"], 0)
        equal("guard", "SSH connection", invocation["ssh_connection_present"], True)
        equal("guard", "sshd ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        equal("guard", "global mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        equal("guard", "protected GUI", [invocation["gui"][key] for key in ("pid", "session_id", "start_unix_ms")], [13340, 1, 1790590196826])
        names = [entry["name"] for entry in steps]
        equal("guard", "five stages", len(steps), 5)
        equal("guard", "native stage sequence", [name for name in names if name != "check_import_export"], ["import", "export", "calc", "jsonreport"])
        equal("guard", "one roundtrip stage", names.count("check_import_export"), 1)
        equal("guard", "roundtrip after export", names.index("check_import_export") > names.index("export"), True)
        for index, entry in enumerate(steps):
            equal("guard", f"step {index}", (entry["status"], entry["exit_code"], entry["gui_preserved"]), ("completed", 0, True))

        parent = tables(parse(PARENT / "native-input.json"), "model")
        child = tables(parse(HERE / "native-input.json"), "model")
        equal("model", "model table names", list(child), list(parent))
        deltas = []
        authored_cells = 0
        for name, old in parent.items():
            new = child[name]
            equal("model", f"{name} columns", new["columns"], old["columns"])
            equal("model", f"{name} instances", len(new["instances"]), len(old["instances"]))
            fields = [field["name"] for field in old["columns"]]
            for instance_index, (old_instance, new_instance) in enumerate(zip(old["instances"], new["instances"])):
                equal("model", f"{name} instance {instance_index} name", new_instance["instance_name"], old_instance["instance_name"])
                equal("model", f"{name} instance {instance_index} rows", len(new_instance["rows"]), len(old_instance["rows"]))
                for row_index, (old_row, new_row) in enumerate(zip(old_instance["rows"], new_instance["rows"])):
                    equal("model", f"{name} row {row_index} width", len(new_row), len(old_row))
                    for column_index, (before_value, after_value) in enumerate(zip(old_row, new_row)):
                        authored_cells += 1
                        if before_value != after_value:
                            deltas.append((name, instance_index, row_index, fields[column_index], before_value, after_value))
        equal("model", "155 authored cells", authored_cells, 155)
        equal("model", "one physical aircraft", deltas, [("SystemDeployment", 0, 0, "QTYPS", 2, 1)])
        mission_fields, mission_rows = shape(child["MissionType"])
        equal("model", "NOS and MNOS remain two", [mission_rows[0][mission_fields.index(key)] for key in ("NOS", "MNOS")], [2, 2])
        exported = tables(parse(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in child.items() if any(instance["rows"] for instance in table["instances"])]
        equal("roundtrip", "13 row-containing authored tables", len(authored), 13)
        for name in authored:
            equal("roundtrip", f"{name} columns", exported[name]["columns"], child[name]["columns"])
            equal("roundtrip", f"{name} exact instances and rows", exported[name]["instances"], child[name]["instances"])
        rt = parse(RUN / "roundtrip-validation.json")
        equal("roundtrip", "checker passed", rt["passed"], True)
        equal("roundtrip", "source SHA", rt["source_sha256"], sha(HERE / "native-input.json"))
        equal("roundtrip", "export SHA", rt["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
        equal("roundtrip", "SXI SHA", rt["sxi_sha256"], sha(RUN / "model.sxi"))
        calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        equal("converter", "0/2/0 summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc, True)
        equal("converter", "only warnings 108 and 126", sorted(re.findall(r"\(warning #(\d+)\)", calc)), ["108", "126"])
        equal("converter", "no error code", re.findall(r"\(error #(\d+)\)", calc), [])
        equal("converter", "valid output", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def matching(fragment: str) -> list[tuple[int, float, str]]:
            selected = []
            for index, line in enumerate(lines):
                if fragment in line:
                    timestamp = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                    if not timestamp:
                        raise ValueError(f"event lacks native timestamp: {line}")
                    selected.append((index, float(timestamp.group(1)), line))
            return selected
        def times(fragment: str) -> list[float]:
            return [event[1] for event in matching(fragment)]
        equal("events", "horizon", lines[1], "36")
        equal("events", "single order", times("mission ordered: BASIC-MISSION"), [7])
        equal("events", "single mission created", times(TAG + " mission created:"), [7])
        equal("events", "no other mission creation", times(" mission created:"), [7])
        equal("events", "requests two systems", times(TAG + " mission activated, systems requested: 2"), [7])
        allocations = matching(TAG + " mission allocates system: " + AIRCRAFT)
        equal("events", "allowed assignment count", len(allocations) in (0, 1), True)
        equal("events", "assignment at/after creation", all(7 <= item[1] <= DEADLINE + 1e-4 for item in allocations), True)
        equal("events", "no other physical aircraft", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))) , ["0"])
        terminal = [item for item in matching(TAG) if any(term in item[2] for term in ("mission cancelled:", "mission timed out:", "mission timeout:"))]
        equal("events", "exactly one cancellation or timeout", len(terminal), 1)
        cancellation = terminal[0][1]
        equal("events", "terminal identity and deadline", 7 <= cancellation <= DEADLINE + 1e-4, True)
        equal("events", "terminal after creation", terminal[0][0] > matching(TAG + " mission created:")[0][0], True)
        all_terminal = [item for item in lines if any(term in item for term in ("mission cancelled:", "mission timed out:", "mission timeout:"))]
        equal("events", "one native terminal mission event", len(all_terminal), 1)
        for index, _, line in matching(TAG + " mission waiting:"):
            timeout = re.search(r"timeout at ([0-9]+(?:\.[0-9]+)?)", line)
            equal("events", f"wait record {index} deadline", timeout is not None and float(timeout.group(1)) <= DEADLINE + 1e-4, True)
        for label, fragment in (("launch", " mission starting,"), ("success", " mission success:"),
                                ("completion", " mission completed:"), ("task start", " task starting:"),
                                ("task completion", " task completed:")):
            equal("events", f"no {label}", times(fragment), [])
        arrivals = matching("System arrives " + AIRCRAFT)
        if allocations:
            equal("events", "one physical release", len(arrivals), 1)
            release = arrivals[0][1]
            equal("events", "release at cancellation", abs(release - cancellation) <= 1e-4, True)
            equal("events", "allocation precedes release", allocations[0][1] <= release, True)
            equal("events", "allocation before cancellation", allocations[0][0] < terminal[0][0], True)
            equal("events", "allocation after creation", allocations[0][0] > matching(TAG + " mission created:")[0][0], True)
            assigned = (allocations[0][1], release)
            trace = "temporarily_assigned"
        else:
            equal("events", "no physical return in ready trace", arrivals, [])
            assigned = None
            trace = "left_ready"
        equal("events", "no failure or PM", bool(re.search(r"failure occurs|BATTLE-HIT|PM task starting", "\n".join(lines), re.I)), False)

        report = tables(parse(RUN / "report-raw.json"), "report")
        parent_report = tables(parse(PARENT_RUN / "report-raw.json"), "report")
        equal("report", "four expected tables", list(report), list(parent_report))
        fields, rows = shape(report["SystemResults"])
        old_fields, old_rows = shape(parent_report["SystemResults"])
        equal("report", "System fields", fields, old_fields)
        equal("report", "72 System rows", len(rows), 72)
        equal("report", "40 System columns", len(fields), 40)
        variable_fields = {"STINT", "ETINT", "NSYRY", "NSYMA", "NSYMR", "NSYA", "NSYMO", "FTMO", "STACC"}
        stable_fields = set(fields) - variable_fields - {"UNID", "SID"}
        for field in sorted(stable_fields):
            column = fields.index(field)
            equal("report", f"parent {field} is stable", len({repr(row[column]) for row in old_rows}), 1)
        for index, row in enumerate(rows):
            start, end = index / 2, (index + 1) / 2
            reserved = overlap(start, end, *assigned) / .5 if assigned else 0.0
            expected = {"STINT": start, "ETINT": end, "NSYRY": 1 - reserved,
                        "NSYMA": reserved, "NSYMR": reserved, "NSYA": 1,
                        "NSYMO": 0, "FTMO": 0, "STACC": 0}
            for column, (field, value) in enumerate(zip(fields, row)):
                if field in ("UNID", "SID"):
                    equal("report", f"System[{index}].{field}", value, old_rows[index][column])
                elif field in expected:
                    near("report", f"System[{index}].{field}", value, expected[field])
                else:
                    equal("report", f"System[{index}].{field} stable", value, old_rows[index][column])
        near("report", "zero flight aircraft-hours", sum(row[fields.index("NSYMO")] * .5 for row in rows), 0)
        near("report", "terminal one ready", rows[-1][fields.index("NSYRY")], 1)
        stock_fields, stock_rows = shape(report["StockTotalResults"])
        old_stock_fields, old_stock = shape(parent_report["StockTotalResults"])
        equal("report", "Stock fields", stock_fields, old_stock_fields)
        equal("report", "72 Stock rows", len(stock_rows), 72)
        equal("report", "16 Stock columns", len(stock_fields), 16)
        for index, row in enumerate(stock_rows):
            for field, got, parent_value in zip(stock_fields, row, old_stock[index]):
                equal("report", f"Stock[{index}].{field}", got, parent_value)
        summary_fields, summary_rows = shape(report["ResultSummary"])
        old_summary_fields, _ = shape(parent_report["ResultSummary"])
        equal("report", "11 Summary fields", len(summary_fields), 11)
        equal("report", "Summary columns", summary_fields, old_summary_fields)
        equal("report", "one Summary row", len(summary_rows), 1)
        for field, value in zip(summary_fields, summary_rows[0]):
            equal("report", f"Summary.{field}", value, {"NREP": 1, "RTILW": 0, "RTIUP": 36}.get(field, 0))
        description_fields, description_rows = shape(report["ProblemDescription"])
        old_description_fields, old_description_rows = shape(parent_report["ProblemDescription"])
        equal("report", "description columns", description_fields, old_description_fields)
        equal("report", "one description row", len(description_rows), 1)
        equal("report", "description unchanged", description_rows, old_description_rows)

    except Exception as error:
        failures.append(f"validator exception: {type(error).__name__}: {error}")

    verdict = {
        "schema": "a03-var01-one-of-two-v010-author-validation/v1",
        "run_id": RUN_ID,
        "passed": not failures,
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": count,
        "categories": dict(sorted(categories.items())),
        "failures": failures,
        "trace": locals().get("trace"),
        "scope": "one of two minimum aircraft, one fixed-seed scheduled mission and 36-hour horizon",
        "limits": ["Only the observed temporary-assignment or ready trace is accepted; no general assignment rule.", "No GUI, alternate minimum, mixed aircraft or cross-engine claim."],
    }
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
