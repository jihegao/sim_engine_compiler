"""Independent, read-only replay of the sealed A03.var01 native result."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
PARENT = CASES / "A03-two-aircraft-formation-v1.0.1"
A02 = CASES / "A02-single-aircraft-repeated-missions"
RUN_ID = "a03-var01-one-of-two-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
TAG = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIR = "<TEACH-AIR-01,0>"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path) -> dict:
    """Remove only trailing commas outside JSON strings, in memory."""
    data = path.read_text(encoding="utf-8-sig")
    output: list[str] = []
    inside = escaped = False
    for pos, char in enumerate(data):
        if inside:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                inside = False
        elif char == '"':
            inside = True
            output.append(char)
        elif char == ",":
            ahead = pos + 1
            while ahead < len(data) and data[ahead].isspace():
                ahead += 1
            if ahead == len(data) or data[ahead] not in "]}":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def table_map(document: dict, section: str) -> dict[str, dict]:
    tables = document[section]["tables"]
    result = {item["name"]: item for item in tables}
    if len(result) != len(tables):
        raise ValueError(f"duplicate {section} table")
    return result


def grid(table: dict) -> tuple[list[str], list[list]]:
    fields = [column["name"] for column in table["columns"]]
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    if len(set(fields)) != len(fields) or any(len(row) != len(fields) for row in rows):
        raise ValueError("malformed report table")
    return fields, rows


def replay() -> dict:
    failures: list[str] = []
    count = 0

    def require(label: str, truth: bool) -> None:
        nonlocal count
        count += 1
        if not truth:
            failures.append(label)

    def eq(label: str, found, wanted) -> None:
        require(f"{label}: {found!r} != {wanted!r}", found == wanted)

    def close(label: str, found, wanted: float, tolerance: float = 1e-5) -> None:
        require(f"{label}: {found!r} != {wanted!r}",
                isinstance(found, (int, float)) and abs(found - wanted) <= tolerance)

    try:
        contract = native_json(CASE / "contract.json")
        accepted = contract["accepted_parent"]
        parent_run = Path(accepted["local_run_dir"])
        prior = contract["instructional_prerequisite"]
        closure = native_json(RUN / "closure.json")
        invocation = native_json(RUN / "invocation.json")
        steps = native_json(RUN / "steps.json")
        approval = native_json(CASE / "review/independent-prelaunch-go.json")
        eq("run identity", closure["run_id"], RUN_ID)
        eq("run invocation identity", invocation["run_id"], RUN_ID)
        eq("run closure error", closure["error"], None)
        eq("invocation seal", digest(RUN / "invocation.json"), closure["invocation_sha256"])
        eq("source before/after", closure["source_hashes_before"], closure["source_hashes_after"])
        eq("invocation source record", invocation["source_hashes_before"], closure["source_hashes_before"])
        source = closure["source_hashes_before"]
        source_paths = {
            "child_input": CASE / "native-input.json",
            "child_contract": CASE / "contract.json",
            "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
            "builder": CASE / "build.py",
            "parent_diff_checker": CASE / "check_parent_diff.py",
            "negative_checker": CASE / "check_negative_control.py",
            "negative_control": CASE / "review/negative-control-accepted-parent.json",
            "roundtrip_checker": CASE / "check_roundtrip.py",
            "behavior_validator": CASE / "validate_native_cli.py",
            "runner_script": CASE / "run_native_ssh.ps1",
            "accepted_input": PARENT / "native-input.json",
            "accepted_contract": PARENT / "contract.json",
            "accepted_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
            "accepted_verdict": PARENT / "review/independent-readonly-2026-09-29.json",
            "accepted_closure": parent_run / "closure.json",
            "a02_input": A02 / "native-input.json",
            "a02_signoff": A02 / "cli-scope-signoff-2026-09-29.md",
            "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
            "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
        }
        eq("source path set", set(source), set(source_paths))
        for name, path in sorted(source_paths.items()):
            eq(f"source {name}", digest(path), source[name])
        eq("accepted input literal", source["accepted_input"], accepted["input_sha256"])
        eq("accepted contract literal", source["accepted_contract"], accepted["contract_sha256"])
        eq("accepted signoff literal", source["accepted_signoff"], accepted["signoff_sha256"])
        eq("accepted reviewer literal", source["accepted_verdict"], accepted["independent_review_sha256"])
        eq("accepted closure literal", source["accepted_closure"], accepted["closure_sha256"])
        eq("A02 input literal", source["a02_input"], prior["input_sha256"])
        eq("A02 signoff literal", source["a02_signoff"], prior["signoff_sha256"])
        eq("manual literal", source["installed_manual"], contract["manual"]["installed_pdf_sha256"])
        for field, name in (("contract_sha256", "child_contract"), ("runner_sha256", "runner_script"),
                            ("validator_sha256", "behavior_validator"), ("input_sha256", "child_input")):
            eq(f"approved {field}", approval[field], source[name])
        eq("approved decision/run", (approval["decision"], approval["run_id"]), ("GO_PRELAUNCH", RUN_ID))
        eq("invocation input/contract/runner", (invocation["input_sha256"], invocation["contract_sha256"],
                                                 invocation["runner_script_sha256"]),
           (source["child_input"], source["child_contract"], source["runner_script"]))
        eq("run input copy", digest(RUN / "input.json"), source["child_input"])

        parent_closure = native_json(parent_run / "closure.json")
        eq("parent closure identity", parent_closure["run_id"], accepted["run_id"])
        eq("parent raw count", len(parent_closure["raw"]), 11)
        for name, seal in sorted(parent_closure["raw"].items()):
            path = parent_run / name
            eq(f"parent {name} size", path.stat().st_size, seal["bytes"])
            eq(f"parent {name} SHA", digest(path), seal["sha256"])
        eq("child raw count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            eq(f"child {name} size", path.stat().st_size, seal["bytes"])
            eq(f"child {name} SHA", digest(path), seal["sha256"])

        eq("SSH session", invocation["session_id"], 0)
        eq("SSH connection", invocation["ssh_connection_present"], True)
        require("sshd ancestry", "sshd.exe" in invocation["ssh_ancestor_names"])
        eq("global mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        eq("GUI identity", [invocation["gui"][k] for k in ("pid", "session_id", "start_unix_ms")],
           [13340, 1, 1790590196826])
        names = [step["name"] for step in steps]
        eq("five ordered stages", names, ["import", "export", "check_import_export", "calc", "jsonreport"])
        for number, step in enumerate(steps):
            eq(f"step {number} outcome", (step["status"], step["exit_code"], step["gui_preserved"]),
               ("completed", 0, True))
            require(f"step {number} timestamps", step["started_utc"] <= step["completed_utc"])
        planned = invocation["planned_commands"]
        eq("four planned native commands", [x["name"] for x in planned],
           ["import", "export", "calc", "jsonreport"])
        for item in planned:
            step = next(x for x in steps if x["name"] == item["name"])
            eq(f"command {item['name']}", step["arguments"], item["arguments"])

        parent = table_map(native_json(PARENT / "native-input.json"), "model")
        child = table_map(native_json(CASE / "native-input.json"), "model")
        eq("authored table names", list(child), list(parent))
        changed = []
        cell_count = 0
        for name, old in parent.items():
            new = child[name]
            eq(f"{name} columns", new["columns"], old["columns"])
            eq(f"{name} instances", len(new["instances"]), len(old["instances"]))
            fields = [column["name"] for column in old["columns"]]
            for ii, (old_instance, new_instance) in enumerate(zip(old["instances"], new["instances"])):
                eq(f"{name} instance name {ii}", new_instance["instance_name"], old_instance["instance_name"])
                eq(f"{name} row count {ii}", len(new_instance["rows"]), len(old_instance["rows"]))
                for ri, (old_row, new_row) in enumerate(zip(old_instance["rows"], new_instance["rows"])):
                    eq(f"{name} row width {ri}", len(new_row), len(old_row))
                    for column, (before, after) in enumerate(zip(old_row, new_row)):
                        cell_count += 1
                        if before != after:
                            changed.append([name, ii, ri, fields[column], before, after])
        eq("authored cell count", cell_count, 155)
        eq("sole QTYPS delta", changed, [["SystemDeployment", 0, 0, "QTYPS", 2, 1]])
        field, rows = grid(child["MissionType"])
        eq("mission minimum", [rows[0][field.index(x)] for x in ("NOS", "MNOS")], [2, 2])
        exported = table_map(native_json(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in child.items() if any(i["rows"] for i in table["instances"])]
        eq("row-containing table count", len(authored), 13)
        for name in authored:
            eq(f"roundtrip {name} columns", exported[name]["columns"], child[name]["columns"])
            eq(f"roundtrip {name} instances", exported[name]["instances"], child[name]["instances"])
        roundtrip = native_json(RUN / "roundtrip-validation.json")
        eq("roundtrip passed", roundtrip["passed"], True)
        eq("roundtrip source/export/SXI hashes",
           (roundtrip["source_sha256"], roundtrip["roundtrip_sha256"], roundtrip["sxi_sha256"]),
           (source["child_input"], digest(RUN / "roundtrip-raw.json"), digest(RUN / "model.sxi")))

        converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        require("converter 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter)
        eq("converter warning codes", sorted(re.findall(r"\(warning #(\d+)\)", converter)), ["108", "126"])
        eq("converter error codes", re.findall(r"\(error #(\d+)\)", converter), [])
        require("valid SXO", (RUN / "model.sxo").stat().st_size > 4)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
        def found(fragment: str) -> list[tuple[int, float, str]]:
            matches = []
            for i, line in enumerate(lines):
                if fragment in line:
                    match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
                    if not match:
                        raise ValueError(f"missing timestamp: {line}")
                    matches.append((i, float(match.group(1)), line))
            return matches

        def one(fragment: str, time: float, tolerance: float = 1e-4) -> tuple[int, float, str]:
            matches = found(fragment)
            eq(f"one event {fragment}", len(matches), 1)
            if len(matches) != 1:
                raise ValueError(f"event count differs: {fragment}")
            close(f"event time {fragment}", matches[0][1], time, tolerance)
            return matches[0]

        eq("log horizon", lines[1], "36")
        one("<TEACH-UNIT> mission ordered: BASIC-MISSION", 7)
        created = one(TAG + " mission created:", 7)
        one(TAG + " mission activated, systems requested: 2", 7)
        assigned = one(TAG + " mission allocates system: " + AIR, 7)
        down = one(AIR + " nbr ready decreased", 7)
        wait = one(TAG + " mission waiting:  timeout at 8.33333", 7)
        cancelled = one(TAG + " mission cancelled:", 8 + 1 / 3)
        returned = one("System arrives " + AIR, 8 + 1 / 3)
        up = [x for x in found(AIR + " nbr ready increased") if x[1] > 0]
        eq("one release ready event", len(up), 1)
        close("release ready time", up[0][1], cancelled[1], 1e-4)
        eq("mission event order", sorted([created[0], assigned[0], down[0], wait[0], cancelled[0], returned[0], up[0][0]]),
           [created[0], assigned[0], down[0], wait[0], cancelled[0], returned[0], up[0][0]])
        eq("one terminal mission", len([x for x in lines if " mission cancelled:" in x]), 1)
        eq("only aircraft ID0", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])
        for term in (" mission starting,", " mission success:", " mission completed:",
                     " task starting:", " task completed:"):
            eq(f"no {term}", found(term), [])
        require("no physical failure/PM", not re.search(r"failure occurs|PM task starting|BATTLE-HIT", "\n".join(lines), re.I))
        parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        require("accepted parent two-aircraft launch", "Time: 8 " + TAG +
                " mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in parent_log)
        require("accepted parent h10 completion", "Time: 10 " + TAG +
                " mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in parent_log)

        report = table_map(native_json(RUN / "report-raw.json"), "report")
        parent_report = table_map(native_json(parent_run / "report-raw.json"), "report")
        eq("report table names", list(report), list(parent_report))
        system_fields, system_rows = grid(report["SystemResults"])
        parent_fields, parent_rows = grid(parent_report["SystemResults"])
        eq("System fields", system_fields, parent_fields)
        eq("System 72x40", (len(system_rows), len(system_fields)), (72, 40))
        variable = {"STINT", "ETINT", "NSYRY", "NSYMA", "NSYMR", "NSYA", "NSYMO", "FTMO", "STACC"}
        for field in system_fields:
            if field not in variable | {"UNID", "SID"}:
                values = {repr(row[system_fields.index(field)]) for row in parent_rows}
                eq(f"stable parent field {field}", len(values), 1)
        duration = returned[1] - assigned[1]
        for i, row in enumerate(system_rows):
            start, end = i / 2, (i + 1) / 2
            reserved = max(0, min(end, returned[1]) - max(start, assigned[1])) / .5
            expected = {"STINT": start, "ETINT": end, "NSYRY": 1 - reserved,
                        "NSYMA": reserved, "NSYMR": reserved, "NSYA": 1,
                        "NSYMO": 0, "FTMO": 0, "STACC": 0}
            for col, field in enumerate(system_fields):
                target = expected[field] if field in expected else parent_rows[i][col]
                if field in expected:
                    close(f"System[{i}].{field}", row[col], target)
                else:
                    eq(f"System[{i}].{field}", row[col], target)
        close("reserved aircraft-hours", sum(row[system_fields.index("NSYMA")] * .5 for row in system_rows), duration)
        close("ready aircraft-hours", sum(row[system_fields.index("NSYRY")] * .5 for row in system_rows), 36 - duration)
        close("flight aircraft-hours", sum(row[system_fields.index("NSYMO")] * .5 for row in system_rows), 0)
        close("terminal ready", system_rows[-1][system_fields.index("NSYRY")], 1)
        stock_fields, stock_rows = grid(report["StockTotalResults"])
        prior_stock_fields, prior_stock_rows = grid(parent_report["StockTotalResults"])
        eq("Stock 72x16", (len(stock_rows), len(stock_fields)), (72, 16))
        eq("Stock fields", stock_fields, prior_stock_fields)
        for i, (row, prior_row) in enumerate(zip(stock_rows, prior_stock_rows)):
            for col, (value, prior_value) in enumerate(zip(row, prior_row)):
                eq(f"Stock[{i}].{stock_fields[col]}", value, prior_value)
        summary_fields, summary_rows = grid(report["ResultSummary"])
        prior_summary_fields, _ = grid(parent_report["ResultSummary"])
        eq("11 summary fields", len(summary_fields), 11)
        eq("summary field names", summary_fields, prior_summary_fields)
        eq("one summary row", len(summary_rows), 1)
        for field, value in zip(summary_fields, summary_rows[0]):
            close(f"Summary.{field}", value, {"NREP": 1, "RTILW": 0, "RTIUP": 36}.get(field, 0))
        description_fields, description_rows = grid(report["ProblemDescription"])
        old_description_fields, old_description_rows = grid(parent_report["ProblemDescription"])
        eq("ProblemDescription fields", description_fields, old_description_fields)
        eq("ProblemDescription rows", description_rows, old_description_rows)
    except Exception as error:
        failures.append(f"replay exception: {type(error).__name__}: {error}")
    result = {
        "schema": "a03-var01-independent-replay/v1",
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "checks": count,
        "failures": failures,
        "run_id": RUN_ID,
        "closure_sha256": digest(RUN / "closure.json"),
        "observed_trace": "temporarily_assigned" if not failures else "unconfirmed",
        "limits": ["One seed, one scheduled wave, one aircraft below MNOS2.",
                   "No general assignment, alternate availability, GUI, or cross-engine claim."],
    }
    return result


def main() -> int:
    result = replay()
    target = CASE / "review/independent-verdict.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["decision"] == "GO_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
