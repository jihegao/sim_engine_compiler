"""Independent standard-library replay of the sealed A02.var03 same-time run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REVIEW = Path(__file__).resolve().parent
CASE = REVIEW.parent
ROOT = CASE.parent
RUN_ID = "a02-var03-same-time-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
A01 = ROOT / "A01-single-aircraft-single-mission"
A02 = ROOT / "A02-single-aircraft-repeated-missions"
ANALOGUE = ROOT / "A02-var01-insufficient-gap-v0.1.1"
ANALOGUE_RUN = ANALOGUE / "runs/a02-var01-insufficient-gap-v011-ssh-20261006-01"
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    """Drop SIMLOX trailing commas in memory only; retain raw bytes on disk."""
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
            continue
        if char == '"':
            quoted = True
            out.append(char)
            continue
        if char == ",":
            next_index = index + 1
            while next_index < len(source) and source[next_index].isspace():
                next_index += 1
            if next_index < len(source) and source[next_index] in "]}":
                continue
        out.append(char)
    return json.loads("".join(out))


def tables(document: dict, kind: str) -> dict[str, dict]:
    entries = document[kind]["tables"]
    by_name = {entry["name"]: entry for entry in entries}
    if len(by_name) != len(entries):
        raise ValueError(f"duplicate {kind} table")
    return by_name


def shape(table: dict) -> tuple[list[str], list[list]]:
    columns = [item["name"] for item in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError("invalid table shape")
    return columns, rows


def main() -> int:
    count = 0
    categories: dict[str, int] = {}
    failures: list[str] = []

    def check(group: str, label: str, got, wanted) -> None:
        nonlocal count
        count += 1
        categories[group] = categories.get(group, 0) + 1
        if got != wanted:
            failures.append(f"{group} {label}: {got!r} != {wanted!r}")

    try:
        contract = native_json(CASE / "contract.json")
        parent_input = native_json(A02 / "native-input.json")
        child_input = native_json(CASE / "native-input.json")
        closure = native_json(RUN / "closure.json")
        invocation = native_json(RUN / "invocation.json")
        steps = native_json(RUN / "steps.json")

        sources = {
            "child_input": CASE / "native-input.json",
            "child_contract": CASE / "contract.json",
            "contract_review": REVIEW / "independent-contract-go-2026-10-06.md",
            "analogue_input": ANALOGUE / "native-input.json",
            "analogue_contract": ANALOGUE / "contract.json",
            "analogue_signoff": ANALOGUE / "cli-scope-signoff-2026-10-06.md",
            "analogue_index": ANALOGUE / "evidence-index.json",
            "analogue_verdict": ANALOGUE / "review/independent-verdict.json",
            "analogue_closure": ANALOGUE_RUN / "closure.json",
            "analogue_log": ANALOGUE_RUN / "model.log",
            "analogue_report": ANALOGUE_RUN / "report-raw.json",
            "negative_checker": CASE / "check_negative_control.py",
            "negative_control": REVIEW / "negative-control-accepted-parent-and-analogue.json",
            "builder": CASE / "build.py",
            "parent_diff": CASE / "check_parent_diff.py",
            "roundtrip_checker": CASE / "check_roundtrip.py",
            "behavior_validator": CASE / "validate_native_cli.py",
            "runner_script": CASE / "run_native_ssh.ps1",
            "accepted_input": A02 / "native-input.json",
            "accepted_contract": A02 / "contract.json",
            "accepted_signoff": A02 / "cli-scope-signoff-2026-09-29.md",
            "accepted_index": A02 / "evidence-index.json",
            "accepted_final_closure": RAW_ROOT / "A02/a02-bound-final-20260927-03/closure.json",
            "accepted_replay_closure": RAW_ROOT / "A02/a02-bound-replay-20260927-04/closure.json",
            "prereq_input": A01 / "native-input.json",
            "prereq_contract": A01 / "contract.json",
            "prereq_signoff": A01 / "cli-scope-signoff-2026-09-29.md",
            "prereq_index": A01 / "evidence-index.json",
            "prereq_final_closure": RAW_ROOT / "A01/a01-bound-final-20260927-03/closure.json",
            "prereq_replay_closure": RAW_ROOT / "A01/a01-bound-replay-20260927-04/closure.json",
            "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
            "prelaunch_approval": REVIEW / "independent-prelaunch-go.json",
        }
        before = closure["source_hashes_before"]
        check("source", "source key set", set(before), set(sources))
        check("source", "unchanged source closure", closure["source_hashes_after"], before)
        check("source", "invocation source closure", invocation["source_hashes_before"], before)
        for name, path in sources.items():
            check("source", name, digest(path), before[name])
        check("source", "child contract pin", before["child_contract"], digest(CASE / "contract.json"))
        check("source", "accepted A02 pin", before["accepted_input"], contract["accepted_parent"]["input_sha256"])
        check("source", "analogue pin", before["analogue_input"], contract["accepted_cancellation_analogue"]["input_sha256"])
        check("source", "run input copy", digest(RUN / "input.json"), before["child_input"])

        check("raw", "run identity", closure["run_id"], RUN_ID)
        check("raw", "invocation identity", invocation["run_id"], RUN_ID)
        check("raw", "closure error", closure["error"], None)
        check("raw", "invocation SHA", digest(RUN / "invocation.json"), closure["invocation_sha256"])
        check("raw", "12 child raw files", len(closure["raw"]), 12)
        for name, pin in sorted(closure["raw"].items()):
            path = RUN / name
            check("raw", f"child {name} SHA", digest(path), pin["sha256"])
            check("raw", f"child {name} bytes", path.stat().st_size, pin["bytes"])
        parent_raw = 0
        for label, package in (("A01", A01), ("A02", A02)):
            evidence = native_json(package / "evidence-index.json")
            check("raw", f"{label} two sealed runs", len(evidence["runs"]), 2)
            for entry in evidence["runs"]:
                for name, pin in sorted(entry["artifacts"].items()):
                    path = RAW_ROOT / label / entry["run_id"] / name
                    check("raw", f"{label}/{entry['run_id']}/{name} SHA", digest(path), pin["sha256"])
                    check("raw", f"{label}/{entry['run_id']}/{name} bytes", path.stat().st_size, pin["bytes"])
                    parent_raw += 1
        check("raw", "68 parent raw seals", parent_raw, 68)
        analogue_closure = native_json(ANALOGUE_RUN / "closure.json")
        check("raw", "analogue closure error", analogue_closure["error"], None)
        check("raw", "12 analogue raw files", len(analogue_closure["raw"]), 12)
        for name, pin in sorted(analogue_closure["raw"].items()):
            path = ANALOGUE_RUN / name
            check("raw", f"analogue {name} SHA", digest(path), pin["sha256"])
            check("raw", f"analogue {name} bytes", path.stat().st_size, pin["bytes"])

        check("guard", "SSH session 0", invocation["session_id"], 0)
        check("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        check("guard", "SSH connection", invocation["ssh_connection_present"], True)
        check("guard", "global queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("guard", "GUI PID/session/start", [invocation["gui"][k] for k in ("pid", "session_id", "start_unix_ms")],
              [13340, 1, 1790590196826])
        check("guard", "five completed steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
              [(n, "completed", 0, True) for n in ("import", "export", "check_import_export", "calc", "jsonreport")])

        old = tables(parent_input, "model")
        new = tables(child_input, "model")
        check("model", "31 model tables", list(new), list(old))
        differences = []
        cell_count = 0
        for name, before_table in old.items():
            after_table = new[name]
            check("model", f"{name} columns", after_table["columns"], before_table["columns"])
            check("model", f"{name} instance count", len(after_table["instances"]), len(before_table["instances"]))
            for instance_index, (before_instance, after_instance) in enumerate(zip(before_table["instances"], after_table["instances"])):
                check("model", f"{name} instance {instance_index} name", after_instance["instance_name"], before_instance["instance_name"])
                check("model", f"{name} instance {instance_index} row count", len(after_instance["rows"]), len(before_instance["rows"]))
                for row_index, (before_row, after_row) in enumerate(zip(before_instance["rows"], after_instance["rows"])):
                    check("model", f"{name} row {row_index} width", len(after_row), len(before_row))
                    for column_index, (before_value, after_value) in enumerate(zip(before_row, after_row)):
                        cell_count += 1
                        if before_value != after_value:
                            differences.append((name, instance_index, row_index, before_table["columns"][column_index]["name"], before_value, after_value))
        check("model", "179 authored cells", cell_count, 179)
        check("model", "sole second STIM 20-to-8", differences, [("OperationProfile", 0, 1, "STIM", 20, 8)])
        op_columns, op_rows = shape(new["OperationProfile"])
        check("model", "three OperationProfile rows", len(op_rows), 3)
        check("model", "schedule 8/8/32", [row[op_columns.index("STIM")] for row in op_rows], [8, 8, 32])
        check("model", "duplicate profile key", [op_rows[i][:2] for i in (0, 1)], [op_rows[0][:2], op_rows[0][:2]])

        export = tables(native_json(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in new.items() if any(instance["rows"] for instance in table["instances"])]
        check("roundtrip", "13 row-containing authored tables", len(authored), 13)
        for name in authored:
            check("roundtrip", f"{name} columns", export[name]["columns"], new[name]["columns"])
            check("roundtrip", f"{name} instances/rows", export[name]["instances"], new[name]["instances"])
        rt = native_json(RUN / "roundtrip-validation.json")
        check("roundtrip", "native roundtrip passed", rt["passed"], True)
        check("roundtrip", "roundtrip source SHA", rt["source_sha256"], before["child_input"])
        check("roundtrip", "roundtrip output SHA", rt["roundtrip_sha256"], digest(RUN / "roundtrip-raw.json"))
        converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter", "0/2/0 summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
        check("converter", "only warnings 108/126", re.findall(r"\(warning #(\d+)\)", converter), ["108", "126"])
        check("converter", "no errors", re.findall(r"\(error #(\d+)\)", converter), [])
        check("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def matching(fragment: str) -> list[tuple[int, str]]:
            return [(position, line) for position, line in enumerate(lines) if fragment in line]
        def times(fragment: str) -> list[float]:
            found = matching(fragment)
            values = []
            for _, line in found:
                stamp = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                if not stamp:
                    raise ValueError(f"missing time on {line!r}")
                values.append(float(stamp.group(1)))
            return values
        check("event", "native horizon", lines[1], "36")
        check("event", "three mission orders", times("mission ordered: BASIC-MISSION"), [7, 7, 31])
        for identity, start, end in ((0, 8, 10), (2, 32, 34)):
            tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{identity}>"
            check("event", f"mission {identity} created", times(tag + " mission created:"), [start - 1])
            check("event", f"mission {identity} allocation", times(tag + " mission allocates system: <TEACH-AIR-01,0>"), [start - 1])
            check("event", f"mission {identity} launch", times(tag + " mission starting, duration: 2 : <TEACH-AIR-01,0>"), [start])
            check("event", f"mission {identity} task", times(tag + " task starting: <TEACH-AIR-01,0>"), [start + .5])
            check("event", f"mission {identity} task complete", times(tag + " task completed: <TEACH-AIR-01,0>"), [end - .5])
            check("event", f"mission {identity} success", times(tag + " mission success:"), [end])
            check("event", f"mission {identity} complete", times(tag + " mission completed: <TEACH-AIR-01,0>"), [end])
        losing = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
        check("event", "competing mission created", times(losing + " mission created:"), [7])
        check("event", "competing mission requests system", times(losing + " mission activated, systems requested: 1"), [7])
        check("event", "waiting timeout marker", len(matching(losing + " mission waiting:  timeout at 8.33333")), 1)
        check("event", "competing cancellation", times(losing + " mission cancelled:"), [8.33333])
        check("event", "loser never allocated/started/completed", [line for _, line in matching(losing) if any(term in line for term in
              ("mission allocates", "mission starting", "task starting", "task completed", "mission success", "mission completed"))], [])
        check("event", "exactly one cancellation", times(" mission cancelled:"), [8.33333])
        check("event", "exactly two starts", times(" mission starting, duration: 2"), [8, 32])
        check("event", "exactly two successes", times(" mission success:"), [10, 34])
        check("event", "exactly two physical arrivals", times("System arrives <TEACH-AIR-01,0>, mission success"), [10, 34])
        check("event", "only aircraft 0", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])
        order = [matching(fragment)[0][0] for fragment in (
            "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission created:",
            "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system:",
            "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission created:",
            "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission waiting:",
            "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration:",
            "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:",
            "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:",
        )]
        check("event", "observed early order", order, sorted(order))
        check("event", "no fault/damage/PM task", any(re.search(r"failure occurs|BATTLE-HIT|PM task starting", line, re.I) for line in lines), False)

        parent_report = tables(native_json(RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"] / "report-raw.json"), "report")
        child_report = tables(native_json(RUN / "report-raw.json"), "report")
        check("report", "report table names", list(child_report), list(parent_report))
        parent_columns, parent_system = shape(parent_report["SystemResults"])
        columns, system = shape(child_report["SystemResults"])
        check("report", "System 72 rows", len(system), 72)
        check("report", "System 40 columns", len(columns), 40)
        check("report", "System columns unchanged", columns, parent_columns)
        for index, row in enumerate(system):
            hour = index / 2
            state = "flight" if 8 <= hour < 10 or 32 <= hour < 34 else "reserved" if 7 <= hour < 8 or 31 <= hour < 32 else "ready"
            template = parent_system[{"ready": 0, "reserved": 14, "flight": 16}[state]]
            for column_index, field in enumerate(columns):
                expected = hour if field == "STINT" else hour + .5 if field == "ETINT" else template[column_index]
                check("report", f"System row {index} {field}", row[column_index], expected)
        check("report", "ready-hour integral", sum(row[columns.index("NSYRY")] * .5 for row in system), 30)
        check("report", "flight-hour integral", sum(row[columns.index("FTMO")] * .5 for row in system), 4)
        check("report", "terminal ready", system[-1][columns.index("NSYRY")], 1)
        stock_columns, stock = shape(child_report["StockTotalResults"])
        old_stock_columns, old_stock = shape(parent_report["StockTotalResults"])
        check("report", "Stock 72 rows", len(stock), 72)
        check("report", "Stock 16 columns", len(stock_columns), 16)
        check("report", "Stock columns", stock_columns, old_stock_columns)
        for index, row in enumerate(stock):
            for field, got, expected in zip(stock_columns, row, old_stock[index]):
                check("report", f"Stock row {index} {field}", got, expected)
        summary_columns, summary = shape(child_report["ResultSummary"])
        parent_summary_columns, parent_summary = shape(parent_report["ResultSummary"])
        check("report", "11 summary fields", len(summary_columns), 11)
        check("report", "summary columns", summary_columns, parent_summary_columns)
        check("report", "one summary row", len(summary), 1)
        for field, got, parent_value in zip(summary_columns, summary[0], parent_summary[0]):
            if field in ("MTMF", "MSTF", "MSUF", "STMF"):
                check("report", f"summary {field} 2/3", isinstance(got, (int, float)) and abs(got - 2/3) < 1e-6, True)
            else:
                check("report", f"summary {field} parent parity", got, parent_value)
        desc_columns, desc = shape(child_report["ProblemDescription"])
        parent_desc_columns, parent_desc = shape(parent_report["ProblemDescription"])
        check("report", "ProblemDescription columns", desc_columns, parent_desc_columns)
        check("report", "ProblemDescription rows", desc, parent_desc)

    except Exception as error:
        failures.append(f"replay exception: {type(error).__name__}: {error}")

    result = {
        "schema": "independent-a02-var03-same-time-v010-replay/v1",
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": count,
        "categories": dict(sorted(categories.items())),
        "failures": failures,
        "run_id": RUN_ID,
        "closure_sha256": digest(RUN / "closure.json"),
        "model_log_sha256": digest(RUN / "model.log"),
        "report_raw_sha256": digest(RUN / "report-raw.json"),
        "scope": "one fixed-seed, single-aircraft duplicate-key simultaneous mission competition",
        "limits": [
            "Mission identity 0 won this run; the native log does not establish a general tie-order rule.",
            "No database duplicate-key export compatibility or other mission-count/deadline claim.",
            "No GUI visual, cross-engine or general A02.var03 conclusion.",
        ],
    }
    output = REVIEW / "independent-verdict.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": count,
                      "failures": failures[:8], "verdict_sha256": digest(output)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
