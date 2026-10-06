"""Strict read-only postrun validator for the frozen A03 minimum-one arm."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A03-var01-one-of-two-v0.1.0"
PARENT_RUN = PARENT / "runs/a03-var01-one-of-two-v010-ssh-20261006-01"
RUN_ID = "a03-var01-min-one-v010-ssh-20261006-01"
RUN = HERE / "runs" / RUN_ID
TAG = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIRCRAFT = "<TEACH-AIR-01,0>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path) -> dict:
    """Remove native trailing commas in memory; never alter sealed bytes."""
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


def table_map(document: dict, kind: str) -> dict[str, dict]:
    entries = document[kind]["tables"]
    result = {table["name"]: table for table in entries}
    if len(result) != len(entries):
        raise ValueError(f"duplicate {kind} table")
    return result


def shape(table: dict) -> tuple[list[str], list[list]]:
    fields = [item["name"] for item in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(fields) != len(set(fields)) or any(len(row) != len(fields) for row in rows):
        raise ValueError("invalid table shape")
    return fields, rows


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
            failures.append(f"{category} {label}: got {got!r}; expected {wanted!r}")

    def near(category: str, label: str, got, wanted: float, tolerance: float = 1e-6) -> None:
        equal(category, label, isinstance(got, (int, float)) and abs(got - wanted) <= tolerance, True)

    try:
        contract = parse(HERE / "contract.json")
        accepted = contract["accepted_parent"]
        for key, filename in (
            ("input_sha256", "native-input.json"),
            ("contract_sha256", "contract.json"),
            ("signoff_sha256", "cli-scope-signoff-2026-10-06.md"),
            ("evidence_index_sha256", "evidence-index.json"),
            ("independent_verdict_sha256", "review/independent-verdict.json"),
        ):
            equal("source", f"accepted {filename}", sha(PARENT / filename), accepted[key])
        equal("source", "accepted closure", sha(PARENT_RUN / "closure.json"), accepted["closure_sha256"])
        equal("source", "installed manual", sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")), contract["manual"]["installed_pdf_sha256"])
        old_closure = parse(PARENT_RUN / "closure.json")
        equal("parent_raw", "12 parent raw files", len(old_closure["raw"]), 12)
        for filename, seal in sorted(old_closure["raw"].items()):
            path = PARENT_RUN / filename
            equal("parent_raw", f"{filename} SHA", sha(path), seal["sha256"])
            equal("parent_raw", f"{filename} bytes", path.stat().st_size, seal["bytes"])

        closure = parse(RUN / "closure.json")
        invocation = parse(RUN / "invocation.json")
        steps = parse(RUN / "steps.json")
        equal("child_raw", "closure run ID", closure["run_id"], RUN_ID)
        equal("child_raw", "invocation run ID", invocation["run_id"], RUN_ID)
        equal("child_raw", "closure error", closure["error"], None)
        equal("child_raw", "invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        equal("child_raw", "12 child raw files", len(closure["raw"]), 12)
        for filename, seal in sorted(closure["raw"].items()):
            path = RUN / filename
            equal("child_raw", f"{filename} SHA", sha(path), seal["sha256"])
            equal("child_raw", f"{filename} bytes", path.stat().st_size, seal["bytes"])
        frozen = closure["source_hashes_before"]
        equal("source", "source map unchanged", closure["source_hashes_after"], frozen)
        equal("source", "invocation source map", invocation["source_hashes_before"], frozen)
        approved_roots = (
            HERE, PARENT, ROOT / "tools", ROOT / "A03-two-aircraft-formation-v1.0.1",
            ROOT / "A02-single-aircraft-repeated-missions",
            Path("C:/Users/user/Documents/Codex/2026-09-28/simlox-issue18-ssh-current/cases/simlox-air-support/A03-two-aircraft-formation-v1.0.1/runs"),
            Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A02"),
        )
        approved_files = [path for root in approved_roots if root.exists() for path in root.rglob("*") if path.is_file()]
        approved_files += [
            Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        ]
        approved_hashes = {sha(path) for path in approved_files}
        for label, digest in sorted(frozen.items()):
            equal("source", f"{label} resolves to frozen source bytes", digest in approved_hashes, True)
        equal("source", "run input copied", sha(RUN / "input.json"), sha(HERE / "native-input.json"))
        equal("source", "invocation input", invocation["input_sha256"], sha(HERE / "native-input.json"))
        equal("source", "invocation contract", invocation["contract_sha256"], sha(HERE / "contract.json"))
        equal("source", "invocation runner", invocation["runner_script_sha256"], sha(HERE / "run_native_ssh.ps1"))
        equal("source", "child input closure", frozen.get("child_input", frozen.get("input")), sha(HERE / "native-input.json"))
        equal("source", "child contract closure", frozen.get("child_contract", frozen.get("contract")), sha(HERE / "contract.json"))
        equal("source", "validator closure", frozen.get("behavior_validator", frozen.get("validator")), sha(HERE / "validate_native_cli.py"))
        equal("source", "accepted input closure", frozen.get("accepted_input", frozen.get("parent_input")), accepted["input_sha256"])
        equal("source", "accepted closure pin", frozen.get("accepted_closure", frozen.get("parent_closure")), accepted["closure_sha256"])
        equal("guard", "SSH session", invocation["session_id"], 0)
        equal("guard", "SSH connection", invocation["ssh_connection_present"], True)
        equal("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        equal("guard", "global mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        equal("guard", "protected GUI", [invocation["gui"][key] for key in ("pid", "session_id", "start_unix_ms")], [13340, 1, 1790590196826])
        names = [step["name"] for step in steps]
        equal("guard", "five guarded stages", len(steps), 5)
        equal("guard", "native stage sequence", [name for name in names if name != "check_import_export"], ["import", "export", "calc", "jsonreport"])
        equal("guard", "one roundtrip check", names.count("check_import_export"), 1)
        equal("guard", "roundtrip after export", names.index("check_import_export") > names.index("export"), True)
        for index, step in enumerate(steps):
            equal("guard", f"stage {index}", (step["status"], step["exit_code"], step["gui_preserved"]), ("completed", 0, True))

        parent = table_map(parse(PARENT / "native-input.json"), "model")
        child = table_map(parse(HERE / "native-input.json"), "model")
        equal("model", "table names", list(child), list(parent))
        deltas = []
        cells = 0
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
                    for column_index, (old_value, new_value) in enumerate(zip(old_row, new_row)):
                        cells += 1
                        if old_value != new_value:
                            deltas.append((name, instance_index, row_index, fields[column_index], old_value, new_value))
        equal("model", "155 authored cells", cells, 155)
        equal("model", "sole minimum-one delta", deltas, [("MissionType", 0, 0, "MNOS", 2, 1)])
        deployment_fields, deployment_rows = shape(child["SystemDeployment"])
        mission_fields, mission_rows = shape(child["MissionType"])
        equal("model", "one deployed aircraft", deployment_rows[0][deployment_fields.index("QTYPS")], 1)
        equal("model", "NOS=2 and MNOS=1", [mission_rows[0][mission_fields.index(key)] for key in ("NOS", "MNOS")], [2, 1])
        exported = table_map(parse(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in child.items() if any(instance["rows"] for instance in table["instances"])]
        equal("roundtrip", "13 row-containing authored tables", len(authored), 13)
        for name in authored:
            equal("roundtrip", f"{name} columns", exported[name]["columns"], child[name]["columns"])
            equal("roundtrip", f"{name} exact instances/rows", exported[name]["instances"], child[name]["instances"])
        roundtrip = parse(RUN / "roundtrip-validation.json")
        equal("roundtrip", "checker passed", roundtrip["passed"], True)
        equal("roundtrip", "source SHA", roundtrip["source_sha256"], sha(HERE / "native-input.json"))
        equal("roundtrip", "export SHA", roundtrip["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
        equal("roundtrip", "SXI SHA", roundtrip["sxi_sha256"], sha(RUN / "model.sxi"))
        calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        equal("converter", "0/2/0 summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc, True)
        equal("converter", "only warnings 108/126", sorted(re.findall(r"\(warning #(\d+)\)", calc)), ["108", "126"])
        equal("converter", "no errors", re.findall(r"\(error #(\d+)\)", calc), [])
        equal("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def matching(fragment: str) -> list[tuple[int, float, str]]:
            found = []
            for index, line in enumerate(lines):
                if fragment in line:
                    timestamp = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                    if not timestamp:
                        raise ValueError(f"event without timestamp: {line!r}")
                    found.append((index, float(timestamp.group(1)), line))
            return found
        def times(fragment: str) -> list[float]:
            return [event[1] for event in matching(fragment)]
        equal("events", "36h horizon", lines[1], "36")
        for label, fragment, expected in (
            ("sole order", "mission ordered: BASIC-MISSION", [7]),
            ("sole creation", TAG + " mission created:", [7]),
            ("two requested", TAG + " mission activated, systems requested: 2", [7]),
            ("aircraft0 allocation", TAG + " mission allocates system: " + AIRCRAFT, [7]),
            ("on-time launch", TAG + " mission starting, duration: 2 : " + AIRCRAFT, [8]),
            ("task work start", TAG + " task starting: " + AIRCRAFT, [8.5]),
            ("task work end", TAG + " task completed: " + AIRCRAFT, [9.5]),
            ("mission success", TAG + " mission success:", [10]),
            ("mission completion", TAG + " mission completed: " + AIRCRAFT, [10]),
            ("physical return", "System arrives " + AIRCRAFT + ", mission success", [10]),
        ):
            equal("events", label, times(fragment), expected)
        equal("events", "no other mission created", times(" mission created:"), [7])
        equal("events", "no other launches", times(" mission starting, duration: 2"), [8])
        equal("events", "no other successes", times(" mission success:"), [10])
        waiting = matching(TAG + " mission waiting:")
        equal("events", "any waiting ends by launch", all(item[1] <= 8 and item[0] < matching(TAG + " mission starting, duration: 2")[0][0] for item in waiting), True)
        equal("events", "no cancellation or abort", bool(re.search(r"mission cancelled:|mission aborted:", "\n".join(lines))), False)
        equal("events", "physical aircraft IDs", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])
        ordered = [matching(fragment)[0][0] for fragment in (
            TAG + " mission created:", TAG + " mission allocates system:",
            TAG + " mission starting, duration: 2", TAG + " mission success:", TAG + " mission completed:",
            "System arrives " + AIRCRAFT + ", mission success",
        )]
        equal("events", "event identity order", ordered, sorted(ordered))
        equal("events", "no faults or PM", bool(re.search(r"failure occurs|BATTLE-HIT|PM task starting", "\n".join(lines), re.I)), False)

        report = table_map(parse(RUN / "report-raw.json"), "report")
        old_report = table_map(parse(PARENT_RUN / "report-raw.json"), "report")
        equal("report", "same four report tables", list(report), list(old_report))
        fields, rows = shape(report["SystemResults"])
        old_fields, old_rows = shape(old_report["SystemResults"])
        equal("report", "System column identity", fields, old_fields)
        equal("report", "72 System rows", len(rows), 72)
        equal("report", "40 System columns", len(fields), 40)
        variable = {"STINT", "ETINT", "NSYRY", "NSYMA", "NSYMR", "NSYMO", "NSYA", "FTMO", "STACC"}
        stable = set(fields) - variable - {"UNID", "SID"}
        for field in sorted(stable):
            column = fields.index(field)
            equal("report", f"accepted {field} stable", len({repr(row[column]) for row in old_rows}), 1)
        for index, row in enumerate(rows):
            start, end = index / 2, (index + 1) / 2
            reserved = overlap(start, end, 7, 8) / .5
            flight = overlap(start, end, 8, 10) / .5
            expected = {"STINT": start, "ETINT": end, "NSYRY": 1 - reserved - flight,
                        "NSYMA": reserved + flight, "NSYMR": reserved,
                        "NSYMO": flight, "NSYA": 1, "FTMO": flight, "STACC": flight}
            for column, (field, value) in enumerate(zip(fields, row)):
                if field in expected:
                    near("report", f"System[{index}].{field}", value, expected[field])
                else:
                    equal("report", f"System[{index}].{field} parent-stable", value, old_rows[index][column])
        for field, wanted in (("NSYRY", 33), ("NSYMR", 1), ("NSYMO", 2), ("FTMO", 2)):
            near("report", f"{field} hour integral", sum(row[fields.index(field)] * .5 for row in rows), wanted)
        near("report", "terminal one ready", rows[-1][fields.index("NSYRY")], 1)
        stock_fields, stock_rows = shape(report["StockTotalResults"])
        old_stock_fields, old_stock_rows = shape(old_report["StockTotalResults"])
        equal("report", "Stock columns", stock_fields, old_stock_fields)
        equal("report", "72 Stock rows", len(stock_rows), 72)
        equal("report", "16 Stock columns", len(stock_fields), 16)
        for index, (row, old_row) in enumerate(zip(stock_rows, old_stock_rows)):
            for field, value, wanted in zip(stock_fields, row, old_row):
                equal("report", f"Stock[{index}].{field}", value, wanted)
        summary_fields, summary_rows = shape(report["ResultSummary"])
        old_summary_fields, _ = shape(old_report["ResultSummary"])
        equal("report", "11 Summary fields", len(summary_fields), 11)
        equal("report", "Summary columns", summary_fields, old_summary_fields)
        equal("report", "one Summary row", len(summary_rows), 1)
        for field, value in zip(summary_fields, summary_rows[0]):
            wanted = .5 if field == "STMF" else 1 if field in ("NREP", "MTMF", "MSTF", "MSUF") else 36 if field == "RTIUP" else 0
            near("report", f"Summary.{field}", value, wanted)
        description_fields, description_rows = shape(report["ProblemDescription"])
        old_description_fields, old_description_rows = shape(old_report["ProblemDescription"])
        equal("report", "description column", description_fields, old_description_fields)
        equal("report", "one description row", len(description_rows), 1)
        equal("report", "stale inherited description retained", description_rows, old_description_rows)

    except Exception as error:
        failures.append(f"validator exception: {type(error).__name__}: {error}")

    verdict = {
        "schema": "a03-var01-min-one-nominal-two-v010-author-validation/v1",
        "run_id": RUN_ID,
        "passed": not failures,
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": count,
        "categories": dict(sorted(categories.items())),
        "failures": failures,
        "scope": "one aircraft meets MNOS1 below NOS2 for one fixed-seed h8 mission",
        "limits": ["One exact source and installed CLI only; no general assignment or mission-count rule.", "Inherited ProblemDescription is stale and is retained byte-for-byte, not semantically updated."],
    }
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
