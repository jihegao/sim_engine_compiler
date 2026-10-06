"""Independent, standard-library replay of sealed A02.var02 evidence.

Reads existing inputs and native outputs. Never calls SIMLOX or author validators.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
RUN_ID = "a02-var02-third-cutoff-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "A02-single-aircraft-repeated-missions"
PREREQ = ROOT / "A01-single-aircraft-single-mission"
J05 = ROOT / "J05-horizon-v1.0.0"
J05_RUN = J05 / "runs" / "j05-horizon-rcend9-v100-20261001-01"
RAW_ROOT = Path(
    "C:/Users/user/Documents/Codex/2026-09-27/"
    "simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_json(path: Path) -> dict:
    """Parse SIMLOX JSON, dropping trailing commas only in memory."""
    source = path.read_text(encoding="utf-8-sig")
    result: list[str] = []
    quoted = False
    escaped = False
    for index, char in enumerate(source):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            result.append(char)
            continue
        if char == ",":
            lookahead = index + 1
            while lookahead < len(source) and source[lookahead].isspace():
                lookahead += 1
            if lookahead < len(source) and source[lookahead] in "]}":
                continue
        result.append(char)
    return json.loads("".join(result))


def table_map(document: dict, key: str) -> dict[str, dict]:
    tables = document[key]["tables"]
    result = {table["name"]: table for table in tables}
    if len(result) != len(tables):
        raise ValueError(f"duplicate {key} table name")
    return result


def report_rows(table: dict) -> tuple[list[str], list[list]]:
    columns = [column["name"] for column in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError("invalid report table shape")
    return columns, rows


def main() -> int:
    checks = 0
    failures: list[str] = []
    categories: dict[str, int] = {}

    def check(category: str, label: str, actual, expected) -> None:
        nonlocal checks
        checks += 1
        categories[category] = categories.get(category, 0) + 1
        if actual != expected:
            failures.append(f"{category}: {label}: {actual!r} != {expected!r}")

    try:
        contract = parse_json(CASE / "contract.json")
        child_input = parse_json(CASE / "native-input.json")
        parent_input = parse_json(PARENT / "native-input.json")
        closure = parse_json(RUN / "closure.json")
        invocation = parse_json(RUN / "invocation.json")
        steps = parse_json(RUN / "steps.json")

        source_paths = {
            "child_input": CASE / "native-input.json",
            "child_contract": CASE / "contract.json",
            "contract_review_prior": HERE / "independent-contract-go-2026-10-06.md",
            "contract_review": HERE / "independent-contract-revision-go-2026-10-06.md",
            "analogue_input": J05 / "rcend9-input.json",
            "analogue_contract": J05 / "contract.json",
            "analogue_signoff": J05 / "cli-scope-signoff-2026-10-01.md",
            "analogue_verdict": J05 / "review/independent-readonly-2026-10-01.json",
            "analogue_closure": J05_RUN / "closure.json",
            "analogue_log": J05_RUN / "model.log",
            "analogue_report": J05_RUN / "report-raw.json",
            "negative_checker": CASE / "check_negative_control.py",
            "negative_control": HERE / "negative-control-accepted-parent.json",
            "builder": CASE / "build.py",
            "parent_diff": CASE / "check_parent_diff.py",
            "roundtrip_checker": CASE / "check_roundtrip.py",
            "behavior_validator": CASE / "validate_native_cli.py",
            "runner_script": CASE / "run_native_ssh.ps1",
            "accepted_input": PARENT / "native-input.json",
            "accepted_contract": PARENT / "contract.json",
            "accepted_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
            "accepted_index": PARENT / "evidence-index.json",
            "accepted_final_closure": RAW_ROOT / "A02/a02-bound-final-20260927-03/closure.json",
            "accepted_replay_closure": RAW_ROOT / "A02/a02-bound-replay-20260927-04/closure.json",
            "prereq_input": PREREQ / "native-input.json",
            "prereq_contract": PREREQ / "contract.json",
            "prereq_signoff": PREREQ / "cli-scope-signoff-2026-09-29.md",
            "prereq_index": PREREQ / "evidence-index.json",
            "prereq_final_closure": RAW_ROOT / "A01/a01-bound-final-20260927-03/closure.json",
            "prereq_replay_closure": RAW_ROOT / "A01/a01-bound-replay-20260927-04/closure.json",
            "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "installed_dictionary": Path(
                "C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"
            ),
            "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            "python": Path(
                "C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
            ),
            "prelaunch_approval": HERE / "independent-prelaunch-go.json",
        }
        before = closure["source_hashes_before"]
        after = closure["source_hashes_after"]
        check("provenance", "35 source keys", set(before), set(source_paths))
        check("provenance", "source before/after", after, before)
        check("provenance", "invocation source map", invocation["source_hashes_before"], before)
        for name, source_path in source_paths.items():
            check("provenance", name, sha(source_path), before[name])
        check("provenance", "contract parent SHA", before["accepted_input"], contract["accepted_parent"]["input_sha256"])
        check("provenance", "contract analogue SHA", before["analogue_input"], contract["accepted_j05_var05_analogue"]["input_sha256"])
        check("provenance", "contract SHA", before["child_contract"], sha(CASE / "contract.json"))
        check("provenance", "run identity", closure["run_id"], RUN_ID)
        check("provenance", "invocation identity", invocation["run_id"], RUN_ID)
        check("provenance", "closure error", closure["error"], None)
        check("provenance", "invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        check("provenance", "copied input", sha(RUN / "input.json"), before["child_input"])

        raw = closure["raw"]
        check("raw", "12 child raw names", len(raw), 12)
        for name, pin in sorted(raw.items()):
            raw_path = RUN / name
            check("raw", f"{name} SHA", sha(raw_path), pin["sha256"])
            check("raw", f"{name} size", raw_path.stat().st_size, pin["bytes"])
        parent_raw_count = 0
        for label, package, contract_key in (
            ("A01", PREREQ, "prerequisite_a01"),
            ("A02", PARENT, "accepted_parent"),
        ):
            index = parse_json(package / "evidence-index.json")
            check("raw", f"{label} two accepted runs", len(index["runs"]), 2)
            for entry in index["runs"]:
                for name, pin in sorted(entry["artifacts"].items()):
                    path = RAW_ROOT / label / entry["run_id"] / name
                    check("raw", f"{label} {entry['run_id']} {name} SHA", sha(path), pin["sha256"])
                    check("raw", f"{label} {entry['run_id']} {name} size", path.stat().st_size, pin["bytes"])
                    parent_raw_count += 1
        check("raw", "68 A01/A02 seals", parent_raw_count, 68)
        analogue = parse_json(J05_RUN / "closure.json")
        check("raw", "J05 closure error", analogue["error"], None)
        check("raw", "12 J05 raw names", len(analogue["raw"]), 12)
        for name, pin in sorted(analogue["raw"].items()):
            path = J05_RUN / name
            check("raw", f"J05 {name} SHA", sha(path), pin["sha256"])
            check("raw", f"J05 {name} size", path.stat().st_size, pin["bytes"])

        check("guard", "session 0", invocation["session_id"], 0)
        check("guard", "sshd ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("guard", "SSH connection", invocation["ssh_connection_present"], True)
        check("guard", "mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("guard", "GUI identity", [invocation["gui"][k] for k in ("pid", "session_id", "start_unix_ms")],
              [13340, 1, 1790590196826])
        check("guard", "five completed steps", [(step["name"], step["status"], step["exit_code"], step["gui_preserved"]) for step in steps],
              [(name, "completed", 0, True) for name in ("import", "export", "check_import_export", "calc", "jsonreport")])

        parent_tables = table_map(parent_input, "model")
        child_tables = table_map(child_input, "model")
        check("source", "31 table names", list(child_tables), list(parent_tables))
        changed: list[tuple] = []
        authored_cells = 0
        for table_name, old_table in parent_tables.items():
            new_table = child_tables[table_name]
            check("source", f"{table_name} columns", new_table["columns"], old_table["columns"])
            check("source", f"{table_name} instance count", len(new_table["instances"]), len(old_table["instances"]))
            for instance_index, (old_instance, new_instance) in enumerate(zip(old_table["instances"], new_table["instances"])):
                check("source", f"{table_name} instance {instance_index} name", new_instance["instance_name"], old_instance["instance_name"])
                check("source", f"{table_name} instance {instance_index} rows", len(new_instance["rows"]), len(old_instance["rows"]))
                for row_index, (old_row, new_row) in enumerate(zip(old_instance["rows"], new_instance["rows"])):
                    check("source", f"{table_name} instance {instance_index} row {row_index} width", len(new_row), len(old_row))
                    for column_index, (old_value, new_value) in enumerate(zip(old_row, new_row)):
                        authored_cells += 1
                        if old_value != new_value:
                            changed.append((table_name, instance_index, row_index, old_table["columns"][column_index]["name"], old_value, new_value))
        check("source", "179 authored cells", authored_cells, 179)
        check("source", "sole SYSTEM RCEND delta", changed, [("ResultCollection", 0, 1, "RCEND", 36, 33)])

        exported = table_map(parse_json(RUN / "roundtrip-raw.json"), "model")
        authored_names = [name for name, table in child_tables.items() if any(instance["rows"] for instance in table["instances"])]
        check("roundtrip", "13 row-containing source tables", len(authored_names), 13)
        for name in authored_names:
            check("roundtrip", f"{name} columns", exported[name]["columns"], child_tables[name]["columns"])
            check("roundtrip", f"{name} instances", exported[name]["instances"], child_tables[name]["instances"])
        roundtrip_note = parse_json(RUN / "roundtrip-validation.json")
        check("roundtrip", "native checker passed", roundtrip_note["passed"], True)
        check("roundtrip", "native checker source SHA", roundtrip_note["source_sha256"], before["child_input"])
        check("roundtrip", "native checker export SHA", roundtrip_note["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))

        converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter", "zero errors two warnings zero notes",
              "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
        check("converter", "warning codes", re.findall(r"\(warning #(\d+)\)", converter), ["108", "126"])
        check("converter", "no error code", re.findall(r"\(error #(\d+)\)", converter), [])
        check("converter", "usable SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        parent_log = RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"] / "model.log"
        child_log = RUN / "model.log"
        check("event", "exact accepted event-log bytes", child_log.read_bytes(), parent_log.read_bytes())
        log_lines = child_log.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        for identity, start, end in ((0, 8, 10), (1, 20, 22), (2, 32, 34)):
            tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{identity}>"
            for event, time in (("mission starting, duration: 2 : <TEACH-AIR-01,0>", start),
                                ("mission success:", end),
                                ("mission completed: <TEACH-AIR-01,0>", end)):
                matches = [line for line in log_lines if tag in line and event in line]
                check("event", f"mission {identity} {event} count", len(matches), 1)
                if matches:
                    check("event", f"mission {identity} {event} hour", matches[0].startswith(f"Time: {time} "), True)
        arrivals = [line for line in log_lines if "System arrives <TEACH-AIR-01,0>, mission success" in line]
        check("event", "three successful physical returns", len(arrivals), 3)
        check("event", "third return at h34", any(line.startswith("Time: 34 ") for line in arrivals), True)
        check("event", "no mission cancellation", any("mission cancelled:" in line for line in log_lines), False)
        check("event", "only physical aircraft zero", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(log_lines)))), ["0"])

        parent_report = table_map(parse_json(RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"] / "report-raw.json"), "report")
        child_report = table_map(parse_json(RUN / "report-raw.json"), "report")
        check("report", "same report table names", list(child_report), list(parent_report))
        old_columns, old_system = report_rows(parent_report["SystemResults"])
        new_columns, new_system = report_rows(child_report["SystemResults"])
        check("report", "System 40 columns", len(new_columns), 40)
        check("report", "System columns unchanged", new_columns, old_columns)
        check("report", "parent 72 System rows", len(old_system), 72)
        check("report", "child 66 System rows", len(new_system), 66)
        for row_index, new_row in enumerate(new_system):
            for column_index, field in enumerate(new_columns):
                check("report", f"System row {row_index} {field}", new_row[column_index], old_system[row_index][column_index])
        check("report", "last System interval", [new_system[-1][new_columns.index(k)] for k in ("STINT", "ETINT")], [32.5, 33])
        check("report", "last System interval in flight", new_system[-1][new_columns.index("FTMO")], 1)
        check("report", "last System interval not ready", new_system[-1][new_columns.index("NSYRY")], 0)

        for name in child_report:
            if name == "SystemResults":
                continue
            old_columns, old_rows = report_rows(parent_report[name])
            new_columns, new_rows = report_rows(child_report[name])
            check("report", f"{name} columns", new_columns, old_columns)
            check("report", f"{name} row count", len(new_rows), len(old_rows))
            if name == "StockTotalResults":
                check("report", "Stock 16 columns", len(new_columns), 16)
                check("report", "Stock 72 rows", len(new_rows), 72)
            if name == "ResultSummary":
                check("report", "summary 11 fields", len(new_columns), 11)
            for row_index, (old_row, new_row) in enumerate(zip(old_rows, new_rows)):
                for column_index, field in enumerate(new_columns):
                    check("report", f"{name} row {row_index} {field}", new_row[column_index], old_row[column_index])
        summary_columns, summary_rows = report_rows(child_report["ResultSummary"])
        check("report", "simulation upper bound remains 36", summary_rows[0][summary_columns.index("RTIUP")], 36)
        check("report", "summary all three missions succeed", [summary_rows[0][summary_columns.index(k)] for k in ("MTMF", "MSTF", "MSUF", "STMF")], [1, 1, 1, 1])

    except Exception as error:
        failures.append(f"replay exception: {type(error).__name__}: {error}")

    result = {
        "schema": "independent-a02-var02-third-cutoff-v010-replay/v1",
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": checks,
        "categories": dict(sorted(categories.items())),
        "failures": failures,
        "run_id": RUN_ID,
        "closure_sha256": sha(RUN / "closure.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "report_raw_sha256": sha(RUN / "report-raw.json"),
        "scope": "one fixed-seed single-aircraft SYSTEM collection cutoff h33 during third h32-34 mission",
        "limits": [
            "No generic collection-end behavior or incomplete-mission terminal claim.",
            "The event log, rather than truncated System rows, proves h34 mission success and return.",
            "No GUI visual, cross-engine, alternate interval or other A02.var02 arm claim.",
        ],
    }
    output = HERE / "independent-verdict.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": checks, "failures": failures[:8],
                      "verdict_sha256": sha(output)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
