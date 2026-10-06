"""Independent read-only replay of the sealed B01.var02 exact-notice run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REVIEW = Path(__file__).resolve().parent
CASE = REVIEW.parent
ROOT = CASE.parent
RUN_ID = "b01-var02-exact-notice-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = Path("C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/B01-fixed-preparation-v1.0.1")
PARENT_RUN = PARENT / "runs/b01-v101-ssh-20260929-06"
A01 = ROOT / "A01-single-aircraft-single-mission"
A01_RAW = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    """Accept native trailing commas in memory while leaving the sealed file untouched."""
    source = path.read_text(encoding="utf-8-sig")
    out = []
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


def tables(doc: dict, key: str) -> dict:
    values = doc[key]["tables"]
    result = {table["name"]: table for table in values}
    if len(result) != len(values):
        raise ValueError("duplicate table")
    return result


def shape(table: dict) -> tuple[list[str], list[list]]:
    columns = [column["name"] for column in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError("invalid table shape")
    return columns, rows


def main() -> int:
    checks = 0
    groups: dict[str, int] = {}
    failures: list[str] = []

    def check(group: str, label: str, actual, expected) -> None:
        nonlocal checks
        checks += 1
        groups[group] = groups.get(group, 0) + 1
        if actual != expected:
            failures.append(f"{group} {label}: {actual!r} != {expected!r}")

    try:
        contract = read_json(CASE / "contract.json")
        closure = read_json(RUN / "closure.json")
        invocation = read_json(RUN / "invocation.json")
        steps = read_json(RUN / "steps.json")
        sources = {
            "child_input": CASE / "native-input.json",
            "child_contract": CASE / "contract.json",
            "contract_review": REVIEW / "independent-contract-go-2026-10-06.md",
            "builder": CASE / "build.py",
            "parent_diff_checker": CASE / "check_parent_diff.py",
            "negative_checker": CASE / "check_negative_control.py",
            "negative_control": REVIEW / "negative-control-accepted-parent.json",
            "roundtrip_checker": CASE / "check_roundtrip.py",
            "behavior_validator": CASE / "validate_native_cli.py",
            "runner_script": CASE / "run_native_ssh.ps1",
            "accepted_input": PARENT / "native-input.json",
            "accepted_contract": PARENT / "contract.json",
            "accepted_diff": PARENT / "parent-diff.json",
            "accepted_evidence": PARENT / "evidence-2026-09-29.md",
            "accepted_verdict": PARENT / "review/independent-readonly-rerun-2026-09-29.json",
            "accepted_closure": PARENT_RUN / "closure.json",
            "prereq_input": A01 / "native-input.json",
            "prereq_contract": A01 / "contract.json",
            "prereq_signoff": A01 / "cli-scope-signoff-2026-09-29.md",
            "prereq_index": A01 / "evidence-index.json",
            "prereq_final_closure": A01_RAW / "a01-bound-final-20260927-03/closure.json",
            "prereq_replay_closure": A01_RAW / "a01-bound-replay-20260927-04/closure.json",
            "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
            "prelaunch_approval": REVIEW / "independent-prelaunch-go.json",
        }
        before = closure["source_hashes_before"]
        check("source", "key set", set(before), set(sources))
        check("source", "before/after equality", closure["source_hashes_after"], before)
        check("source", "invocation equality", invocation["source_hashes_before"], before)
        for name, path in sorted(sources.items()):
            check("source", name, sha(path), before[name])
        check("source", "parent input contract pin", before["accepted_input"], contract["accepted_parent"]["input_sha256"])
        check("source", "parent closure contract pin", before["accepted_closure"], contract["accepted_parent"]["closure_sha256"])
        check("source", "child input copied", sha(RUN / "input.json"), before["child_input"])
        check("source", "invocation contract pin", invocation["contract_sha256"], before["child_contract"])

        check("raw", "run ID", closure["run_id"], RUN_ID)
        check("raw", "invocation ID", invocation["run_id"], RUN_ID)
        check("raw", "no closure error", closure["error"], None)
        check("raw", "invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        check("raw", "12 child files", len(closure["raw"]), 12)
        for name, pin in sorted(closure["raw"].items()):
            path = RUN / name
            check("raw", f"child {name} SHA", sha(path), pin["sha256"])
            check("raw", f"child {name} size", path.stat().st_size, pin["bytes"])
        parent_closure = read_json(PARENT_RUN / "closure.json")
        check("raw", "11 parent files", len(parent_closure["raw"]), 11)
        for name, pin in sorted(parent_closure["raw"].items()):
            path = PARENT_RUN / name
            check("raw", f"B01 parent {name} SHA", sha(path), pin["sha256"])
            check("raw", f"B01 parent {name} size", path.stat().st_size, pin["bytes"])
        a01_index = read_json(A01 / "evidence-index.json")
        a01_count = 0
        for entry in a01_index["runs"]:
            for name, pin in sorted(entry["artifacts"].items()):
                path = A01_RAW / entry["run_id"] / name
                check("raw", f"A01 {entry['run_id']} {name} SHA", sha(path), pin["sha256"])
                check("raw", f"A01 {entry['run_id']} {name} size", path.stat().st_size, pin["bytes"])
                a01_count += 1
        check("raw", "34 A01 files", a01_count, 34)

        check("guard", "session", invocation["session_id"], 0)
        check("guard", "SSH", invocation["ssh_connection_present"], True)
        check("guard", "sshd ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("guard", "mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("guard", "GUI PID/session/start", [invocation["gui"][x] for x in ("pid", "session_id", "start_unix_ms")], [13340, 1, 1790590196826])
        check("guard", "five steps", [(s["name"], s["exit_code"], s["status"], s["gui_preserved"]) for s in steps], [(x, 0, "completed", True) for x in ("import", "export", "check_import_export", "calc", "jsonreport")])

        old = tables(read_json(PARENT / "native-input.json"), "model")
        new = tables(read_json(CASE / "native-input.json"), "model")
        check("source_delta", "same table names", list(new), list(old))
        differences = []
        cell_count = 0
        for name, left in old.items():
            right = new[name]
            check("source_delta", f"{name} columns", right["columns"], left["columns"])
            check("source_delta", f"{name} instance count", len(right["instances"]), len(left["instances"]))
            for i, (before_instance, after_instance) in enumerate(zip(left["instances"], right["instances"])):
                check("source_delta", f"{name} instance {i} name", after_instance["instance_name"], before_instance["instance_name"])
                check("source_delta", f"{name} instance {i} rows", len(after_instance["rows"]), len(before_instance["rows"]))
                columns = [column["name"] for column in left["columns"]]
                for j, (before_row, after_row) in enumerate(zip(before_instance["rows"], after_instance["rows"])):
                    check("source_delta", f"{name} row {j} width", len(after_row), len(before_row))
                    for k, (before_value, after_value) in enumerate(zip(before_row, after_row)):
                        cell_count += 1
                        if before_value != after_value:
                            differences.append((name, i, j, columns[k], before_value, after_value))
        check("source_delta", "167 cells", cell_count, 167)
        check("source_delta", "sole notice delta", differences, [("MissionType", 0, 0, "NOPER", 1, 0.5)])

        exported = tables(read_json(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in new.items() if any(instance["rows"] for instance in table["instances"])]
        check("roundtrip", "15 row-containing tables", len(authored), 15)
        for name in authored:
            check("roundtrip", f"{name} columns", exported[name]["columns"], new[name]["columns"])
            check("roundtrip", f"{name} instances", exported[name]["instances"], new[name]["instances"])
        roundtrip = read_json(RUN / "roundtrip-validation.json")
        check("roundtrip", "native checker passed", roundtrip["passed"], True)
        check("roundtrip", "source pin", roundtrip["source_sha256"], before["child_input"])
        check("roundtrip", "export pin", roundtrip["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
        run_text = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter", "0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_text, True)
        check("converter", "exact warnings", re.findall(r"\(warning #(\d+)\)", run_text), ["108", "126"])
        check("converter", "no errors", re.findall(r"\(error #(\d+)\)", run_text), [])
        check("converter", "usable SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def events(fragment: str) -> list[tuple[int, float, str]]:
            found = []
            for number, line in enumerate(lines):
                if fragment in line:
                    stamp = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                    if not stamp:
                        raise ValueError(f"event without timestamp: {line}")
                    found.append((number, float(stamp.group(1)), line))
            return found
        def times(fragment: str) -> list[float]:
            return [item[1] for item in events(fragment)]
        tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
        check("event", "horizon", lines[1], "36")
        for label, fragment, expected in (
            ("order", "mission ordered: BASIC-MISSION", [7.5]),
            ("creation", tag + " mission created:", [7.5]),
            ("allocation", tag + " mission allocates system: <TEACH-AIR-01,0>", [7.5]),
            ("preparation start", "<TEACH-AIR-01,0> preparation started", [7.5]),
            ("subtask performing", "system preparation task 0 on <TEACH-AIR-01,0> starts performing", [7.5]),
            ("preparation complete", "  system preparation task 0 on <TEACH-AIR-01,0> completed", [8]),
            ("preparation end", "<TEACH-AIR-01,0> preparation ended", [8]),
            ("mission start", tag + " mission starting, duration: 2", [8]),
            ("task start", tag + " task starting:", [8.5]),
            ("task complete", tag + " task completed:", [9.5]),
            ("success", tag + " mission success:", [10]),
            ("completion", tag + " mission completed:", [10]),
            ("arrival", "System arrives <TEACH-AIR-01,0>, mission success", [10]),
        ):
            check("event", label, times(fragment), expected)
        ordered = [events(fragment)[0][0] for fragment in (
            tag + " mission created:", tag + " mission allocates system:",
            "<TEACH-AIR-01,0> preparation started", "system preparation task 0 on <TEACH-AIR-01,0> starts performing",
            "  system preparation task 0 on <TEACH-AIR-01,0> completed", "<TEACH-AIR-01,0> preparation ended",
            tag + " mission starting", tag + " mission success:",
        )]
        check("event", "exact event order", ordered, sorted(ordered))
        check("event", "no cancellation", times(" mission cancelled:"), [])
        check("event", "no faults or PM", bool(re.search(r"failure occurs|BATTLE-HIT|PM task starting", "\n".join(lines), re.I)), False)
        check("event", "one aircraft identity", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])

        parent_report = tables(read_json(PARENT_RUN / "report-raw.json"), "report")
        child_report = tables(read_json(RUN / "report-raw.json"), "report")
        check("report", "same tables", list(child_report), list(parent_report))
        expected_changes = {
            (14, "NSYRY"): (0, 1), (14, "NSYMA"): (1, 0),
            (14, "NSYMP"): (1, 0), (14, "NPSTA"): (1, 0),
            (15, "NSYMP"): (0, 1), (15, "NSYMR"): (1, 0),
            (15, "NPSTA"): (0, 1), (15, "NPSUC"): (1, 0),
            (16, "NPSUC"): (0, 1),
        }
        observed_changes = {}
        for name, height, width in (("SystemResults", 72, 40), ("StockTotalResults", 72, 16), ("ResultSummary", 1, 11), ("ProblemDescription", 1, 1)):
            parent_columns, parent_rows = shape(parent_report[name])
            child_columns, child_rows = shape(child_report[name])
            check("report", f"{name} columns", child_columns, parent_columns)
            check("report", f"{name} height", len(child_rows), height)
            check("report", f"{name} width", len(child_columns), width)
            for row_index, (parent_row, child_row) in enumerate(zip(parent_rows, child_rows)):
                for column_index, (before_value, after_value) in enumerate(zip(parent_row, child_row)):
                    field = child_columns[column_index]
                    if name == "SystemResults" and (row_index, field) in expected_changes:
                        prior, expected = expected_changes[(row_index, field)]
                        check("report", f"{name}[{row_index}].{field} parent", before_value, prior)
                    else:
                        expected = before_value
                    check("report", f"{name}[{row_index}].{field}", after_value, expected)
                    if before_value != after_value:
                        observed_changes[(row_index, field)] = (before_value, after_value) if name == "SystemResults" else (name, before_value, after_value)
        check("report", "nine shifted System cells only", observed_changes, expected_changes)
        system_columns, system_rows = shape(child_report["SystemResults"])
        check("report", "terminal ready", system_rows[-1][system_columns.index("NSYRY")], 1)

    except Exception as error:
        failures.append(f"replay exception: {type(error).__name__}: {error}")

    result = {
        "schema": "independent-b01-var02-exact-notice-replay/v1",
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": checks,
        "categories": dict(sorted(groups.items())),
        "failures": failures,
        "run_id": RUN_ID,
        "closure_sha256": sha(RUN / "closure.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "report_raw_sha256": sha(RUN / "report-raw.json"),
        "scope": "one fixed-seed aircraft and mission with NOPER notice 0.5 hours before launch",
        "limits": ["The h7.5/h8 event order is observed for this frozen source and installed CLI only.", "No general same-time event priority or GUI behavior is inferred."],
    }
    output = REVIEW / "independent-verdict.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": checks, "failures": failures[:12], "verdict_sha256": sha(output)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
