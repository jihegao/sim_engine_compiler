"""Strict read-only author replay for the frozen B04.var01 exact-release run.

This module uses only the Python standard library. It does not invoke SIMLOX,
import the package's other checkers, or modify the native run. The runner can
redirect its JSON stdout to an author-verdict file after the run.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "B04-cross-midnight-turnround-v1.0.1"
RUN_ID = "b04-var01-release-boundary-v010-ssh-20261006-01"
RUN = HERE / "runs" / RUN_ID
CONTROL = PARENT / "runs/b04-v101-control-20260930-01"
TURNROUND = PARENT / "runs/b04-v101-turnround-20260930-01"
AIRCRAFT = "<TEACH-AIR-01,0>"
MISSION = [f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>" for wave in (0, 1)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    """Parse native JSON with trailing commas in memory, preserving raw bytes."""
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
            next_index = index + 1
            while next_index < len(source) and source[next_index].isspace():
                next_index += 1
            if next_index >= len(source) or source[next_index] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table_map(doc: dict, root: str) -> dict[str, dict]:
    entries = doc[root]["tables"]
    result = {table["name"]: table for table in entries}
    if len(result) != len(entries):
        raise ValueError(f"duplicate {root} table")
    return result


def shape(table: dict) -> tuple[list[str], list[list]]:
    fields = [field["name"] for field in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(fields) != len(set(fields)) or any(len(row) != len(fields) for row in rows):
        raise ValueError("invalid table shape")
    return fields, rows


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left))


def main() -> int:
    checks = 0
    groups: dict[str, int] = {}
    failures: list[str] = []

    def gate(group: str, label: str, got, wanted) -> None:
        nonlocal checks
        checks += 1
        groups[group] = groups.get(group, 0) + 1
        if got != wanted:
            failures.append(f"{group} {label}: got {got!r}, expected {wanted!r}")

    def near(group: str, label: str, got, wanted: float, tolerance: float = 1e-6) -> None:
        gate(group, label, isinstance(got, (int, float)) and abs(got - wanted) <= tolerance, True)

    try:
        contract = native_json(HERE / "contract.json")
        parent_pins = contract["accepted_parent"]
        gate("source", "accepted turnround input", sha(PARENT / "turnround-input.json"), parent_pins["turnround_input_sha256"])
        gate("source", "accepted control input", sha(PARENT / "control-input.json"), parent_pins["control_input_sha256"])
        for key, filename in (("contract_sha256", "contract.json"), ("signoff_sha256", "cli-scope-signoff-2026-09-30.md"), ("source_diff_sha256", "exact-diff.json")):
            gate("source", f"accepted {filename}", sha(PARENT / filename), parent_pins[key])
        gate("source", "installed manual", sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")), contract["manual"]["installed_pdf_sha256"])
        for label, directory, pin in (
            ("control", CONTROL, parent_pins["control_closure_sha256"]),
            ("turnround", TURNROUND, parent_pins["turnround_closure_sha256"]),
        ):
            gate("source", f"accepted {label} closure", sha(directory / "closure.json"), pin)
            old_closure = native_json(directory / "closure.json")
            gate("parent_raw", f"{label} raw file count", len(old_closure["raw"]), 12)
            for name, seal in sorted(old_closure["raw"].items()):
                path = directory / name
                gate("parent_raw", f"{label}/{name} SHA", sha(path), seal["sha256"])
                gate("parent_raw", f"{label}/{name} bytes", path.stat().st_size, seal["bytes"])

        closure = native_json(RUN / "closure.json")
        invocation = native_json(RUN / "invocation.json")
        steps = native_json(RUN / "steps.json")
        gate("child_raw", "run identity", closure["run_id"], RUN_ID)
        gate("child_raw", "invocation identity", invocation["run_id"], RUN_ID)
        gate("child_raw", "no run error", closure["error"], None)
        gate("child_raw", "invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        gate("child_raw", "12 child raw files", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            gate("child_raw", f"{name} SHA", sha(path), seal["sha256"])
            gate("child_raw", f"{name} bytes", path.stat().st_size, seal["bytes"])
        before = closure["source_hashes_before"]
        gate("source", "source stable", closure["source_hashes_after"], before)
        gate("source", "invocation source map", invocation["source_hashes_before"], before)
        approved_roots = (
            HERE, PARENT, ROOT / "B02-serial-preparation-v1.0.2",
            ROOT / "A02-single-aircraft-repeated-missions",
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
        for label, digest in sorted(before.items()):
            gate("source", f"{label} matches an approved source byte file", digest in approved_hashes, True)
        gate("source", "copied run input", sha(RUN / "input.json"), sha(HERE / "native-input.json"))
        gate("source", "child input invocation", invocation["input_sha256"], sha(HERE / "native-input.json"))
        gate("source", "child contract invocation", invocation["contract_sha256"], sha(HERE / "contract.json"))
        gate("source", "runner invocation", invocation["runner_script_sha256"], sha(HERE / "run_native_ssh.ps1"))
        gate("source", "child input closure", before.get("child_input", before.get("input")), sha(HERE / "native-input.json"))
        gate("source", "child contract closure", before.get("child_contract", before.get("contract")), sha(HERE / "contract.json"))
        gate("source", "validator closure", before.get("behavior_validator", before.get("validator")), sha(HERE / "validate_native_cli.py"))
        gate("source", "runner closure", before.get("runner_script"), sha(HERE / "run_native_ssh.ps1"))
        gate("source", "parent turnround closure", before.get("accepted_turnround_closure", before.get("accepted_closure")), sha(TURNROUND / "closure.json"))
        gate("source", "parent control closure", before.get("accepted_control_closure"), sha(CONTROL / "closure.json"))
        gate("source", "parent turnround input", before.get("accepted_turnround_input", before.get("accepted_input")), parent_pins["turnround_input_sha256"])
        gate("source", "parent control input", before.get("accepted_control_input"), parent_pins["control_input_sha256"])
        gate("guard", "SSH session", invocation["session_id"], 0)
        gate("guard", "SSH present", invocation["ssh_connection_present"], True)
        gate("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        gate("guard", "global queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        gate("guard", "GUI identity", [invocation["gui"][name] for name in ("pid", "session_id", "start_unix_ms")], [13340, 1, 1790590196826])
        step_names = [entry["name"] for entry in steps]
        gate("guard", "five guarded stages", len(steps), 5)
        gate("guard", "native stage order", [name for name in step_names if name != "check_import_export"], ["import", "export", "calc", "jsonreport"])
        gate("guard", "exact roundtrip stage", step_names.count("check_import_export"), 1)
        gate("guard", "roundtrip after export", step_names.index("check_import_export") > step_names.index("export"), True)
        for index, entry in enumerate(steps):
            gate("guard", f"stage {index} completed", (entry["status"], entry["exit_code"], entry["gui_preserved"]), ("completed", 0, True))

        parent_model = table_map(native_json(PARENT / "turnround-input.json"), "model")
        child_model = table_map(native_json(HERE / "native-input.json"), "model")
        gate("model", "table names", list(child_model), list(parent_model))
        deltas = []
        cells = 0
        for name, old_table in parent_model.items():
            new_table = child_model[name]
            gate("model", f"{name} columns", new_table["columns"], old_table["columns"])
            gate("model", f"{name} instance count", len(new_table["instances"]), len(old_table["instances"]))
            fields = [field["name"] for field in old_table["columns"]]
            for instance_number, (old_instance, new_instance) in enumerate(zip(old_table["instances"], new_table["instances"])):
                gate("model", f"{name} instance {instance_number} name", new_instance["instance_name"], old_instance["instance_name"])
                gate("model", f"{name} instance {instance_number} row count", len(new_instance["rows"]), len(old_instance["rows"]))
                for row_number, (old_row, new_row) in enumerate(zip(old_instance["rows"], new_instance["rows"])):
                    gate("model", f"{name} row {row_number} width", len(new_row), len(old_row))
                    for column_number, (old_value, new_value) in enumerate(zip(old_row, new_row)):
                        cells += 1
                        if old_value != new_value:
                            deltas.append((name, instance_number, row_number, fields[column_number], old_value, new_value))
        gate("model", "204 authored cells", cells, 204)
        gate("model", "sole DURN delta", deltas, [("MissionTurnround", 0, 0, "DURN", 1, 0.75)])
        exported_model = table_map(native_json(RUN / "roundtrip-raw.json"), "model")
        populated = [name for name, table in child_model.items() if any(any(value is not None for value in row) for instance in table["instances"] for row in instance["rows"])]
        row_containing = [name for name, table in child_model.items() if any(instance["rows"] for instance in table["instances"])]
        gate("roundtrip", "15 populated tables", len(populated), 15)
        gate("roundtrip", "18 row-containing tables", len(row_containing), 18)
        for name in row_containing:
            gate("roundtrip", f"{name} columns", exported_model[name]["columns"], child_model[name]["columns"])
            gate("roundtrip", f"{name} instances and rows", exported_model[name]["instances"], child_model[name]["instances"])
        roundtrip = native_json(RUN / "roundtrip-validation.json")
        gate("roundtrip", "native checker passed", roundtrip["passed"], True)
        gate("roundtrip", "native source seal", roundtrip["source_sha256"], sha(HERE / "native-input.json"))
        gate("roundtrip", "native export seal", roundtrip["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
        gate("roundtrip", "native SXI seal", roundtrip["sxi_sha256"], sha(RUN / "model.sxi"))
        log_text = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        gate("converter", "zero errors", re.search(r"Input conversion completed\. Errors: 0, Warnings: (\d+), Notes: 0", log_text) is not None, True)
        gate("converter", "exact warning codes", sorted(re.findall(r"\(warning #(\d+)\)", log_text)), ["108", "126"])
        gate("converter", "no error codes", re.findall(r"\(error #(\d+)\)", log_text), [])
        gate("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def events(fragment: str) -> list[tuple[int, float, str]]:
            result = []
            for index, line in enumerate(lines):
                if fragment in line:
                    match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                    if not match:
                        raise ValueError(f"event without time: {line!r}")
                    result.append((index, float(match.group(1)), line))
            return result
        def times(fragment: str) -> list[float]:
            return [event[1] for event in events(fragment)]
        gate("events", "36h horizon", lines[1], "36")
        parent_lines = (TURNROUND / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def before_first_return(items: list[str]) -> list[str]:
            selected = []
            for item in items:
                match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", item)
                if match and float(match.group(1)) < 23.5:
                    selected.append(item)
            return selected
        gate("events", "full first-mission prefix", before_first_return(lines), before_first_return(parent_lines))
        for label, fragment, expected in (
            ("two notices", "mission ordered: BASIC-MISSION", [20.5, 23.75]),
            ("first allocation", MISSION[0] + " mission allocates system: " + AIRCRAFT, [20.5]),
            ("first preparation start", AIRCRAFT + " preparation started, mission: " + MISSION[0], [20.5]),
            ("first preparation end", AIRCRAFT + " preparation ended, mission: " + MISSION[0], [21]),
            ("first launch", MISSION[0] + " mission starting, duration: 2 : " + AIRCRAFT, [21.5]),
            ("first success", MISSION[0] + " mission success:", [23.5]),
            ("first completion", MISSION[0] + " mission completed: " + AIRCRAFT, [23.5]),
            ("first turnround start", AIRCRAFT + " turnround started, mission: " + MISSION[0], [23.5]),
            ("first physical turnround task start", "  system turnround task 1 on " + AIRCRAFT + " started", [23.5]),
            ("second preassignment", MISSION[1] + " mission preassigns a system: " + AIRCRAFT, [23.75]),
            ("first physical turnround task completion", "  system turnround task 1 on " + AIRCRAFT + " completed", [24.25]),
            ("first turnround end", AIRCRAFT + " turnround ended, mission: " + MISSION[0], [24.25]),
            ("second allocation", MISSION[1] + " mission allocates system: " + AIRCRAFT, [24.25]),
            ("second preparation start", AIRCRAFT + " preparation started, mission: " + MISSION[1], [24.25]),
            ("second preparation end", AIRCRAFT + " preparation ended, mission: " + MISSION[1], [24.75]),
            ("second launch", MISSION[1] + " mission starting, duration: 2 : " + AIRCRAFT, [24.75]),
            ("second success", MISSION[1] + " mission success:", [26.75]),
            ("second completion", MISSION[1] + " mission completed: " + AIRCRAFT, [26.75]),
            ("second turnround start", AIRCRAFT + " turnround started, mission: " + MISSION[1], [26.75]),
            ("second physical turnround task start", "  system turnround task 3 on " + AIRCRAFT + " started", [26.75]),
            ("second physical turnround task completion", "  system turnround task 3 on " + AIRCRAFT + " completed", [27.5]),
            ("second turnround end", AIRCRAFT + " turnround ended, mission: " + MISSION[1], [27.5]),
        ):
            gate("events", label, times(fragment), expected)
        gate("events", "exact same-time h24.25 ordering", [events(fragment)[0][0] for fragment in (
            AIRCRAFT + " turnround ended, mission: " + MISSION[0],
            MISSION[1] + " mission allocates system:",
            AIRCRAFT + " preparation started, mission: " + MISSION[1],
        )], sorted(events(fragment)[0][0] for fragment in (
            AIRCRAFT + " turnround ended, mission: " + MISSION[0],
            MISSION[1] + " mission allocates system:",
            AIRCRAFT + " preparation started, mission: " + MISSION[1],
        )))
        gate("events", "exact same-time h24.75 ordering", [events(fragment)[0][0] for fragment in (
            AIRCRAFT + " preparation ended, mission: " + MISSION[1],
            MISSION[1] + " mission starting, duration: 2",
        )], sorted(events(fragment)[0][0] for fragment in (
            AIRCRAFT + " preparation ended, mission: " + MISSION[1],
            MISSION[1] + " mission starting, duration: 2",
        )))
        gate("events", "two starts only", times(" mission starting, duration: 2"), [21.5, 24.75])
        gate("events", "two successes only", times(" mission success:"), [23.5, 26.75])
        gate("events", "no cancellation or abort", bool(re.search(r"mission cancelled:|mission aborted:", "\n".join(lines))), False)
        gate("events", "only physical aircraft zero", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])

        previous = table_map(native_json(TURNROUND / "report-raw.json"), "report")
        current = table_map(native_json(RUN / "report-raw.json"), "report")
        gate("report", "same report tables", list(current), list(previous))
        for name, height, width in (("StockTotalResults", 72, 16), ("ResultSummary", 1, 11), ("ProblemDescription", 1, 1)):
            old_fields, old_rows = shape(previous[name])
            fields, rows = shape(current[name])
            gate("report", f"{name} columns", fields, old_fields)
            gate("report", f"{name} rows", len(rows), height)
            gate("report", f"{name} width", len(fields), width)
            for row_index, (old_row, row) in enumerate(zip(old_rows, rows)):
                for field, got, wanted in zip(fields, row, old_row):
                    gate("report", f"{name}[{row_index}].{field}", got, wanted)
        old_fields, old_rows = shape(previous["SystemResults"])
        fields, rows = shape(current["SystemResults"])
        gate("report", "System fields", fields, old_fields)
        gate("report", "72 System bins", len(rows), 72)
        gate("report", "40 System fields", len(fields), 40)
        phases = {
            "NSYMP": ((20.5, 21), (24.25, 24.75)),
            "NSYMR": ((21, 21.5),),
            "NSYMO": ((21.5, 23.5), (24.75, 26.75)),
            "NSYMT": ((23.5, 24.25), (26.75, 27.5)),
        }
        for row_index, (old_row, row) in enumerate(zip(old_rows, rows)):
            start = row_index * .5
            end = start + .5
            fractions = {field: sum(overlap(start, end, a, b) for a, b in spans) / .5 for field, spans in phases.items()}
            assigned = sum(fractions.values())
            expected = {
                **fractions,
                "NSYRY": 1 - assigned,
                "NSYMA": assigned,
                "FTMO": fractions["NSYMO"],
                "STACC": fractions["NSYMO"],
                "NPSTA": int(start <= 20.5 < end) + int(start <= 24.25 < end),
                "NPSUC": int(start <= 21 < end) + int(start <= 24.75 < end),
            }
            for field, got, old_value in zip(fields, row, old_row):
                if field == "STINT":
                    near("report", f"System[{row_index}].STINT", got, start)
                elif field == "ETINT":
                    near("report", f"System[{row_index}].ETINT", got, end)
                elif field in expected:
                    near("report", f"System[{row_index}].{field}", got, expected[field])
                else:
                    gate("report", f"System[{row_index}].{field} stable", got, old_value)
        gate("report", "terminal ready", rows[-1][fields.index("NSYRY")], 1)
        for field, wanted in (("NSYMO", 4.0), ("NSYMP", 1.0), ("NSYMT", 1.5), ("NSYMR", .5), ("NSYRY", 29.0)):
            near("report", f"{field} integral", sum(row[fields.index(field)] * .5 for row in rows), wanted)

    except Exception as error:
        failures.append(f"validator exception: {type(error).__name__}: {error}")

    result = {
        "schema": "b04-var01-exact-release-v010-author-validation/v1",
        "run_id": RUN_ID,
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "passed": not failures,
        "checks": checks,
        "groups": dict(sorted(groups.items())),
        "failures": failures,
        "scope": "one fixed-seed aircraft, two waves, MissionTurnround.DURN 0.75 hour",
        "limits": ["Same-time ordering is observed only for the frozen CLI source.", "No GUI, resource-constrained turnround, or general scheduling claim."],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
