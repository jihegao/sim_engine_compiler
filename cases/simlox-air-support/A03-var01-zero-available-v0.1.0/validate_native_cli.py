"""Read-only, predeclared postrun gate for the A03 zero-available candidate."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A03-var01-one-of-two-v0.1.0"
A03 = ROOT / "A03-two-aircraft-formation-v1.0.1"
A02 = ROOT / "A02-single-aircraft-repeated-missions"
PARENT_ID = "a03-var01-one-of-two-v010-ssh-20261006-01"
RUN_ID = "a03-var01-zero-v010-ssh-20261006-01"
PARENT_RUN = PARENT / "runs" / PARENT_ID
RUN = HERE / "runs" / RUN_ID
CONTRACT_SHA = "f344c70fba41bf34103ad391f85068568316d8b4238889f531742074a4687238"
INPUT_SHA = "567c66db4faa12ab6e82ea72613f6b2d293ab608ebaed6a79f7daf2996e25f9b"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
DEADLINE = 8 + 1 / 3


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path):
    """Remove native trailing commas in memory, preserving strings and raw bytes."""
    source = path.read_text(encoding="utf-8-sig")
    output: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(source):
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
            next_index = index + 1
            while next_index < len(source) and source[next_index].isspace():
                next_index += 1
            if next_index >= len(source) or source[next_index] not in "]}":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def table_map(document: dict, section: str) -> dict[str, dict]:
    entries = document[section]["tables"]
    result = {entry["name"]: entry for entry in entries}
    if len(result) != len(entries):
        raise ValueError(f"duplicate {section} table")
    return result


def shape(table: dict) -> tuple[list[str], list[list]]:
    columns = [column["name"] for column in table["columns"]]
    if len(columns) != len(set(columns)):
        raise ValueError("duplicate column")
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("nonrectangular report")
    return columns, rows


def run_validation() -> dict:
    checks = 0
    groups: dict[str, int] = {}
    failures: list[str] = []

    def eq(group: str, label: str, actual, expected) -> None:
        nonlocal checks
        checks += 1
        groups[group] = groups.get(group, 0) + 1
        if actual != expected:
            failures.append(f"{group}/{label}: got {actual!r}; expected {expected!r}")

    def near(group: str, label: str, actual, expected: float, tol: float = 1e-4) -> None:
        eq(group, label, isinstance(actual, (float, int)) and abs(actual - expected) <= tol, True)

    try:
        contract = native_json(HERE / "contract.json")
        parent = contract["accepted_parent"]
        eq("source", "contract byte pin", digest(HERE / "contract.json"), CONTRACT_SHA)
        eq("source", "child input byte pin", digest(HERE / "native-input.json"), INPUT_SHA)
        parent_paths = {
            "input_sha256": "native-input.json",
            "contract_sha256": "contract.json",
            "signoff_sha256": "cli-scope-signoff-2026-10-06.md",
            "evidence_index_sha256": "evidence-index.json",
            "independent_verdict_sha256": "review/independent-verdict.json",
        }
        for key, filename in parent_paths.items():
            eq("parent", filename, digest(PARENT / filename), parent[key])
        eq("parent", "closure SHA", digest(PARENT_RUN / "closure.json"), parent["closure_sha256"])
        parent_index = native_json(PARENT / "evidence-index.json")
        parent_entry = next(entry for entry in parent_index["runs"] if entry["run_id"] == PARENT_ID)
        eq("parent", "indexed run ID", parent_entry["run_id"], PARENT_ID)
        eq("parent", "12 raw seals", len(parent_entry["raw"]), 12)
        for name, seal in sorted(parent_entry["raw"].items()):
            file = PARENT_RUN / name
            eq("parent_raw", f"{name} SHA", digest(file), seal["sha256"])
            eq("parent_raw", f"{name} bytes", file.stat().st_size, seal["bytes"])
        accepted_a03 = parent_index["accepted_parent"]
        prerequisite = parent_index["instructional_prerequisite"]
        for label, file, expected in (
            ("A03 input", A03 / "native-input.json", accepted_a03["input_sha256"]),
            ("A03 signoff", A03 / "cli-scope-signoff-2026-09-29.md", accepted_a03["signoff_sha256"]),
            ("A02 input", A02 / "native-input.json", prerequisite["input_sha256"]),
            ("A02 signoff", A02 / "cli-scope-signoff-2026-09-29.md", prerequisite["signoff_sha256"]),
        ):
            eq("prerequisite", label, digest(file), expected)
        installed = contract["manual_and_dictionary"]
        eq("installed", "manual SHA", digest(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")), installed["installed_pdf_sha256"])
        eq("installed", "dictionary SHA", digest(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt")), installed["installed_dictionary_sha256"])

        old = table_map(native_json(PARENT / "native-input.json"), "model")
        new = table_map(native_json(HERE / "native-input.json"), "model")
        eq("model", "31 table names and order", list(new), list(old))
        eq("model", "31 source tables", len(new), 31)
        differences = []
        cells = 0
        for name, prior in old.items():
            child = new[name]
            eq("model", f"{name} columns", child["columns"], prior["columns"])
            eq("model", f"{name} instance count", len(child["instances"]), len(prior["instances"]))
            fields = [column["name"] for column in prior["columns"]]
            for ii, (before_i, after_i) in enumerate(zip(prior["instances"], child["instances"])):
                eq("model", f"{name} instance {ii} name", after_i["instance_name"], before_i["instance_name"])
                eq("model", f"{name} instance {ii} row count", len(after_i["rows"]), len(before_i["rows"]))
                for ri, (before_row, after_row) in enumerate(zip(before_i["rows"], after_i["rows"])):
                    eq("model", f"{name} row {ri} width", len(after_row), len(before_row))
                    for ci, (before_value, after_value) in enumerate(zip(before_row, after_row)):
                        cells += 1
                        if before_value != after_value:
                            differences.append((name, ii, ri, fields[ci], before_value, after_value))
        eq("model", "authored cells", cells, 155)
        eq("model", "sole edit", differences, [("SystemDeployment", 0, 0, "QTYPS", 1, 0)])
        mt_fields, mt_rows = shape(new["MissionType"])
        eq("model", "nominal and minimum", [mt_rows[0][mt_fields.index(x)] for x in ("NOS", "MNOS")], [2, 2])

        closure = native_json(RUN / "closure.json")
        invocation = native_json(RUN / "invocation.json")
        steps = native_json(RUN / "steps.json")
        eq("closure", "run ID", closure["run_id"], RUN_ID)
        eq("closure", "invocation run ID", invocation["run_id"], RUN_ID)
        eq("closure", "invocation SHA", digest(RUN / "invocation.json"), closure["invocation_sha256"])
        eq("closure", "source before/after", closure["source_hashes_after"], closure["source_hashes_before"])
        eq("closure", "invocation source map", invocation["source_hashes_before"], closure["source_hashes_before"])
        source = closure["source_hashes_before"]
        source_files = {
            "child_input": HERE / "native-input.json",
            "child_contract": HERE / "contract.json",
            "contract_review": HERE / "review/independent-contract-go-2026-10-06.md",
            "builder": HERE / "build.py",
            "parent_diff_checker": HERE / "check_parent_diff.py",
            "roundtrip_checker": HERE / "check_roundtrip.py",
            "shared_parser": ROOT / "tools/validate_native.py",
            "behavior_validator": HERE / "validate_native_cli.py",
            "runner_script": HERE / "run_native_ssh.ps1",
            "accepted_input": PARENT / "native-input.json",
            "accepted_contract": PARENT / "contract.json",
            "accepted_signoff": PARENT / "cli-scope-signoff-2026-10-06.md",
            "accepted_index": PARENT / "evidence-index.json",
            "accepted_verdict": PARENT / "review/independent-verdict.json",
            "accepted_closure": PARENT_RUN / "closure.json",
            "a03_input": A03 / "native-input.json",
            "a03_signoff": A03 / "cli-scope-signoff-2026-09-29.md",
            "a02_input": A02 / "native-input.json",
            "a02_signoff": A02 / "cli-scope-signoff-2026-09-29.md",
            "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        }
        if "prelaunch_approval" in source:
            source_files["prelaunch_approval"] = HERE / "review/independent-prelaunch-go.json"
        eq("closure", "known source labels", sorted(source), sorted(source_files))
        for name, path in sorted(source_files.items()):
            eq("closure", f"{name} SHA", source[name], digest(path))
        eq("closure", "parent input pinned", source["accepted_input"], parent["input_sha256"])
        eq("closure", "parent closure pinned", source["accepted_closure"], parent["closure_sha256"])
        eq("closure", "child copied input", digest(RUN / "input.json"), INPUT_SHA)
        eq("closure", "invocation input", invocation["input_sha256"], INPUT_SHA)
        eq("closure", "invocation contract", invocation["contract_sha256"], CONTRACT_SHA)
        eq("closure", "invocation runner", invocation["runner_script_sha256"], digest(HERE / "run_native_ssh.ps1"))
        if "prelaunch_approval" in source:
            approval = native_json(source_files["prelaunch_approval"])
            eq("approval", "decision", approval["decision"], "GO_PRELAUNCH")
            eq("approval", "run", approval["run_id"], RUN_ID)
            for key, expected in (("contract_sha256", CONTRACT_SHA), ("input_sha256", INPUT_SHA),
                                  ("validator_sha256", digest(HERE / "validate_native_cli.py")),
                                  ("runner_sha256", digest(HERE / "run_native_ssh.ps1"))):
                eq("approval", key, approval[key], expected)
        else:
            eq("approval", "prelaunch approval source pin", False, True)
        eq("guard", "SSH session", invocation["session_id"], 0)
        eq("guard", "SSH connection", invocation["ssh_connection_present"], True)
        eq("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        eq("guard", "queue mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        eq("guard", "GUI identity", [invocation["gui"][key] for key in ("pid", "session_id", "start_unix_ms")], [13340, 1, 1790590196826])
        eq("guard", "five stages", len(steps), 5)
        eq("guard", "stage order", [stage["name"] for stage in steps], ["import", "export", "check_import_export", "calc", "jsonreport"])
        for index, step in enumerate(steps):
            eq("guard", f"step {index}", [step["status"], step["exit_code"], step["gui_preserved"]], ["completed", 0, True])
        diagnostic = closure["error"] is not None
        if not diagnostic:
            eq("closure", "12 child raw seals", len(closure["raw"]), 12)
            eq("closure", "exact child raw names", sorted(closure["raw"]), sorted((
                "input.json", "model.sxi", "import.log", "roundtrip-raw.json",
                "export.log", "roundtrip-validation.json", "steps.json",
                "model.sxo", "run.log", "model.log", "report-raw.json",
                "report-export.log",
            )))
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            eq("child_raw", f"{name} SHA", digest(path), seal["sha256"])
            eq("child_raw", f"{name} size", path.stat().st_size, seal["bytes"])
        failure_path = RUN / "failure-seal.json"
        if diagnostic:
            eq("diagnostic", "failure seal exists", failure_path.is_file(), True)
            failure_seal = native_json(failure_path)
            eq("diagnostic", "failure run ID", failure_seal["run_id"], RUN_ID)
            eq("diagnostic", "failure reason", failure_seal["error"], closure["error"])
            for name, seal in sorted(failure_seal["files"].items()):
                file = RUN / name
                eq("diagnostic", f"{name} SHA", digest(file), seal["sha256"])
                eq("diagnostic", f"{name} bytes", file.stat().st_size, seal["bytes"])
            failures.append(f"native run excluded by frozen gate: {closure['error']}")
            raise RuntimeError("sealed diagnostic; physical behavior cannot be accepted")
        eq("closure", "no failure seal", failure_path.exists(), False)

        exported = table_map(native_json(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in new.items() if any(inst["rows"] for inst in table["instances"])]
        eq("roundtrip", "13 row-containing tables", len(authored), 13)
        for name in authored:
            eq("roundtrip", f"{name} columns", exported[name]["columns"], new[name]["columns"])
            eq("roundtrip", f"{name} instances and rows", exported[name]["instances"], new[name]["instances"])
        rt = native_json(RUN / "roundtrip-validation.json")
        eq("roundtrip", "checker pass", rt["passed"], True)
        eq("roundtrip", "source SHA", rt["source_sha256"], INPUT_SHA)
        eq("roundtrip", "export SHA", rt["roundtrip_sha256"], digest(RUN / "roundtrip-raw.json"))
        eq("roundtrip", "SXI SHA", rt["sxi_sha256"], digest(RUN / "model.sxi"))
        log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        eq("converter", "zero errors", bool(re.search(r"Input conversion completed\. Errors: 0, Warnings: \d+, Notes: 0", log)), True)
        eq("converter", "no error diagnostic", re.findall(r"\(error #(\d+)\)", log), [])
        eq("converter", "accepted runner warnings", sorted(re.findall(r"\(warning #(\d+)\)", log)), ["108", "126"])
        eq("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        eq("events", "36-hour horizon", lines[1], "36")

        def found(fragment: str) -> list[tuple[int, float, str]]:
            result = []
            for index, line in enumerate(lines):
                if fragment in line:
                    match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                    if not match:
                        raise ValueError(f"event missing time: {line}")
                    result.append((index, float(match.group(1)), line))
            return result

        def times(fragment: str) -> list[float]:
            return [event[1] for event in found(fragment)]

        eq("events", "one h7 mission order", times("mission ordered: BASIC-MISSION"), [7])
        eq("events", "one mission creation", times(" mission created:"), [7])
        eq("events", "mission identity", times(MISSION + " mission created:"), [7])
        eq("events", "two requested", times(MISSION + " mission activated, systems requested: 2"), [7])
        eq("events", "waiting recorded", len(found(MISSION + " mission waiting:")) >= 1, True)
        for index, _, line in found(MISSION + " mission waiting:"):
            match = re.search(r"timeout at ([0-9]+(?:\.[0-9]+)?)", line)
            near("events", f"waiting {index} deadline", float(match.group(1)) if match else None, DEADLINE)
        terminal = [event for event in found(" mission cancelled:") if MISSION in event[2]]
        eq("events", "one cancellation", len(terminal), 1)
        near("events", "h8.33333 cancellation", terminal[0][1], DEADLINE)
        eq("events", "cancellation after creation", terminal[0][0] > found(MISSION + " mission created:")[0][0], True)
        eq("events", "no other cancellation", len(found(" mission cancelled:")), 1)
        for label, fragment in (
            ("physical aircraft reference", r"<TEACH-AIR-01,\d+>"),
            ("allocation", r"mission allocates system:"),
            ("launch", r"mission starting,"),
            ("success", r"mission success:"),
            ("completion", r"mission completed:"),
            ("maintenance/failure", r"failure occurs|PM task starting|Repair task starting|task starting:"),
            ("stock/transport", r"backorder|Delivery|transport started|stock issued|item issued"),
        ):
            eq("events", f"no {label}", bool(re.search(fragment, "\n".join(lines), re.IGNORECASE)), False)

        report = table_map(native_json(RUN / "report-raw.json"), "report")
        baseline = table_map(native_json(PARENT_RUN / "report-raw.json"), "report")
        eq("report", "four report tables", list(report), list(baseline))
        system_fields, system_rows = shape(report["SystemResults"])
        old_system_fields, _ = shape(baseline["SystemResults"])
        eq("report", "System columns", system_fields, old_system_fields)
        eq("report", "40 System fields", len(system_fields), 40)
        eq("report", "allowed zero or 72 System bins", len(system_rows) in (0, 72), True)
        if len(system_rows) == 72:
            for index, row in enumerate(system_rows):
                near("report", f"System[{index}].STINT", row[system_fields.index("STINT")], index / 2)
                near("report", f"System[{index}].ETINT", row[system_fields.index("ETINT")], (index + 1) / 2)
                for field, value in zip(system_fields, row):
                    if field in ("UNID", "SID"):
                        eq("report", f"System[{index}].{field}", value, "Total over all Units" if field == "UNID" else "Total over all Systems")
                    elif field == "SYDT":
                        eq("report", f"System[{index}].SYDT undefined", value, None)
                    elif field not in ("STINT", "ETINT"):
                        near("report", f"System[{index}].{field} zero", value, 0)
        stock_fields, stock_rows = shape(report["StockTotalResults"])
        old_stock_fields, old_stock_rows = shape(baseline["StockTotalResults"])
        eq("report", "Stock columns", stock_fields, old_stock_fields)
        eq("report", "72 Stock bins", len(stock_rows), 72)
        eq("report", "16 Stock fields", len(stock_fields), 16)
        for index, (row, expected) in enumerate(zip(stock_rows, old_stock_rows)):
            for field, value, old_value in zip(stock_fields, row, expected):
                eq("report", f"Stock[{index}].{field}", value, old_value)
        summary_fields, summary_rows = shape(report["ResultSummary"])
        parent_summary_fields, _ = shape(baseline["ResultSummary"])
        eq("report", "11 Summary fields", len(summary_fields), 11)
        eq("report", "Summary columns", summary_fields, parent_summary_fields)
        eq("report", "one Summary row", len(summary_rows), 1)
        expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36}
        for field, value in zip(summary_fields, summary_rows[0]):
            if field == "STMF":
                # Zero physical deployed systems can make this denominator undefined.
                eq("report", "Summary.STMF zero or null", value in (0, None), True)
            else:
                eq("report", f"Summary.{field}", value, expected_summary.get(field, 0))
        description_fields, description_rows = shape(report["ProblemDescription"])
        old_description_fields, old_description_rows = shape(baseline["ProblemDescription"])
        eq("report", "description columns", description_fields, old_description_fields)
        eq("report", "inherited description", description_rows, old_description_rows)

    except Exception as exc:
        failures.append(f"validator exception: {type(exc).__name__}: {exc}")

    return {
        "schema": "simlox-a03-var01-zero-author-validation/v1",
        "run_id": RUN_ID,
        "contract_sha256": CONTRACT_SHA,
        "input_sha256": INPUT_SHA,
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "passed": not failures,
        "checks": checks,
        "categories": dict(sorted(groups.items())),
        "failures": failures,
        "scope": "one explicit zero-deployment row, one fixed-seed scheduled wave and 36-hour horizon",
        "limits": [
            "Any importer/converter rejection is a sealed diagnostic and NO_GO for runtime behavior.",
            "SystemResults may contain zero rows or 72 zero-count bins; STMF may be zero or null with no deployed systems.",
            "No omitted-deployment, alternate availability, GUI or cross-engine claim.",
        ],
    }


if __name__ == "__main__":
    result = run_validation()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
