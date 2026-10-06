"""Independent read-only replay of the sealed A03 minimum-one native run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "A03-var01-one-of-two-v0.1.0"
RUN_ID = "a03-var01-min-one-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT_RUN = PARENT / "runs/a03-var01-one-of-two-v010-ssh-20261006-01"
OUT = CASE / "review/independent-verdict.json"
CONTRACT_SHA = "b48af26f2da0e3e04fccac4f84952dd9a3abffc38a2fa7661c9cc0764058c9e3"
INPUT_SHA = "87778568dfb1ff7f8b367d2a936fc10c0653f784dd595dec9ebe7a46f36b4b13"
RUNNER_SHA = "557750f168d3ac3001465f7865dfe2e37db6664de708ae4099f33ddaec4f97c9"
VALIDATOR_SHA = "fe35e4e4101fc0d736f0d3422e10ef3d5d27f2178b04f7a6542e2802ccc5d024"
APPROVAL_SHA = "29fdeae7bfcc2ebbcd1daae5f955985dd39a0514b32a59c8c612f28cea8f83b6"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path):
    """Parse a copy in memory, removing commas outside strings before ] or }."""
    source = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = False
    escaped = False
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
            following = index + 1
            while following < len(source) and source[following].isspace():
                following += 1
            if following == len(source) or source[following] not in "]}":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def tables(document, family):
    values = document[family]["tables"]
    result = {value["name"]: value for value in values}
    if len(result) != len(values):
        raise ValueError("duplicate table name")
    return result


def rows(table):
    fields = [column["name"] for column in table["columns"]]
    values = [row for instance in table["instances"] for row in instance["rows"]]
    if len(fields) != len(set(fields)) or any(len(value) != len(fields) for value in values):
        raise ValueError("nonrectangular table")
    return fields, values


class Audit:
    def __init__(self):
        self.checks = 0
        self.failures = []

    def eq(self, label, actual, expected):
        self.checks += 1
        if actual != expected:
            self.failures.append(f"{label}: got {actual!r}, expected {expected!r}")

    def near(self, label, actual, expected, tolerance=1e-6):
        self.checks += 1
        if not isinstance(actual, (int, float)) or abs(actual - expected) > tolerance:
            self.failures.append(f"{label}: got {actual!r}, expected {expected!r} ± {tolerance}")


def main():
    audit = Audit()
    closure_hash = None
    try:
        contract = native_json(CASE / "contract.json")
        parent_info = contract["accepted_parent"]
        audit.eq("frozen contract", sha(CASE / "contract.json"), CONTRACT_SHA)
        audit.eq("frozen input", sha(CASE / "native-input.json"), INPUT_SHA)
        audit.eq("frozen runner", sha(CASE / "run_native_ssh.ps1"), RUNNER_SHA)
        audit.eq("frozen validator", sha(CASE / "validate_native_cli.py"), VALIDATOR_SHA)
        audit.eq("independent prelaunch approval", sha(CASE / "review/independent-prelaunch-go.json"), APPROVAL_SHA)
        approval = native_json(CASE / "review/independent-prelaunch-go.json")
        audit.eq("approval decision and run", (approval["decision"], approval["run_id"]), ("GO_PRELAUNCH", RUN_ID))
        for field, expected in (("contract_sha256", CONTRACT_SHA), ("input_sha256", INPUT_SHA),
                                ("runner_sha256", RUNNER_SHA), ("validator_sha256", VALIDATOR_SHA)):
            audit.eq(f"approval {field}", approval[field], expected)

        parent_paths = {
            "input_sha256": PARENT / "native-input.json",
            "contract_sha256": PARENT / "contract.json",
            "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-06.md",
            "evidence_index_sha256": PARENT / "evidence-index.json",
            "independent_verdict_sha256": PARENT / "review/independent-verdict.json",
            "closure_sha256": PARENT_RUN / "closure.json",
        }
        for field, path in parent_paths.items():
            audit.eq(f"published parent {field}", sha(path), parent_info[field])
        parent_index = native_json(PARENT / "evidence-index.json")
        parent_closure = native_json(PARENT_RUN / "closure.json")
        audit.eq("parent raw count", len(parent_closure["raw"]), 12)
        for name, seal in sorted(parent_closure["raw"].items()):
            path = PARENT_RUN / name
            audit.eq(f"parent {name} size", path.stat().st_size, seal["bytes"])
            audit.eq(f"parent {name} SHA", sha(path), seal["sha256"])
        audit.eq("parent evidence A03 source", sha(ROOT / "A03-two-aircraft-formation-v1.0.1/native-input.json"),
                 parent_index["accepted_parent"]["input_sha256"])
        audit.eq("parent evidence A02 source", sha(ROOT / "A02-single-aircraft-repeated-missions/native-input.json"),
                 parent_index["instructional_prerequisite"]["input_sha256"])
        audit.eq("parent evidence A02 signoff", sha(ROOT / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md"),
                 parent_index["instructional_prerequisite"]["signoff_sha256"])

        closure_hash = sha(RUN / "closure.json")
        closure = native_json(RUN / "closure.json")
        invocation = native_json(RUN / "invocation.json")
        steps = native_json(RUN / "steps.json")
        audit.eq("child run identity", (closure["run_id"], invocation["run_id"]), (RUN_ID, RUN_ID))
        audit.eq("child closure error", closure["error"], None)
        audit.eq("child invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        audit.eq("child raw count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            audit.eq(f"child {name} size", path.stat().st_size, seal["bytes"])
            audit.eq(f"child {name} SHA", sha(path), seal["sha256"])
        audit.eq("source before/after", closure["source_hashes_after"], closure["source_hashes_before"])
        audit.eq("invocation source map", invocation["source_hashes_before"], closure["source_hashes_before"])
        sources = {
            "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
            "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
            "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
            "negative_checker": CASE / "check_negative_control.py",
            "negative_control": CASE / "review/negative-control-accepted-parent.json",
            "roundtrip_checker": CASE / "check_roundtrip.py",
            "shared_parser": ROOT / "tools/validate_native.py",
            "behavior_validator": CASE / "validate_native_cli.py", "runner_script": CASE / "run_native_ssh.ps1",
            "accepted_input": PARENT / "native-input.json", "accepted_contract": PARENT / "contract.json",
            "accepted_signoff": PARENT / "cli-scope-signoff-2026-10-06.md",
            "accepted_index": PARENT / "evidence-index.json",
            "accepted_verdict": PARENT / "review/independent-verdict.json",
            "accepted_closure": PARENT_RUN / "closure.json",
            "a03_input": ROOT / "A03-two-aircraft-formation-v1.0.1/native-input.json",
            "a03_signoff": ROOT / "A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md",
            "a02_input": ROOT / "A02-single-aircraft-repeated-missions/native-input.json",
            "a02_signoff": ROOT / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md",
            "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
            "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
            "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
        }
        audit.eq("source map key set", set(closure["source_hashes_before"]), set(sources))
        for label, path in sorted(sources.items()):
            audit.eq(f"source {label}", sha(path), closure["source_hashes_before"][label])
        audit.eq("parent negative-control cancellation", "mission cancelled:" in (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig"), True)
        audit.eq("parent negative-control no launch", "mission starting," in (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig"), False)

        audit.eq("SSH session and connection", (invocation["session_id"], invocation["ssh_connection_present"]), (0, True))
        audit.eq("sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        audit.eq("global mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        audit.eq("protected GUI", tuple(invocation["gui"][key] for key in ("pid", "session_id", "start_unix_ms")),
                 (13340, 1, 1790590196826))
        audit.eq("ordered five stages", [step["name"] for step in steps],
                 ["import", "export", "check_import_export", "calc", "jsonreport"])
        audit.eq("planned native calls", [item["name"] for item in invocation["planned_commands"]],
                 ["import", "export", "calc", "jsonreport"])
        for index, step in enumerate(steps):
            audit.eq(f"stage {index} completed", (step["status"], step["exit_code"], step["gui_preserved"]),
                     ("completed", 0, True))
        audit.eq("roundtrip check before calc", steps[2]["completed_utc"] < steps[3]["started_utc"], True)

        source = tables(native_json(CASE / "native-input.json"), "model")
        original = tables(native_json(PARENT / "native-input.json"), "model")
        audit.eq("authored table names", list(source), list(original))
        changes = []
        cell_count = 0
        for name, old in original.items():
            new = source[name]
            audit.eq(f"{name} columns", new["columns"], old["columns"])
            audit.eq(f"{name} instance count", len(new["instances"]), len(old["instances"]))
            fields = [column["name"] for column in old["columns"]]
            for ii, (oi, ni) in enumerate(zip(old["instances"], new["instances"])):
                audit.eq(f"{name} instance {ii} name", ni["instance_name"], oi["instance_name"])
                audit.eq(f"{name} instance {ii} row count", len(ni["rows"]), len(oi["rows"]))
                for ri, (before, after) in enumerate(zip(oi["rows"], ni["rows"])):
                    audit.eq(f"{name} row {ri} width", len(after), len(fields))
                    for field, left, right in zip(fields, before, after):
                        cell_count += 1
                        if left != right:
                            changes.append([name, ii, ri, field, left, right])
        audit.eq("155 authored cells", cell_count, 155)
        audit.eq("sole source change", changes, [["MissionType", 0, 0, "MNOS", 2, 1]])
        audit.eq("copied native input", sha(RUN / "input.json"), INPUT_SHA)
        exported = tables(native_json(RUN / "roundtrip-raw.json"), "model")
        authored = [name for name, table in source.items() if any(inst["rows"] for inst in table["instances"])]
        audit.eq("13 row-containing authored tables", len(authored), 13)
        for name in authored:
            audit.eq(f"roundtrip {name} columns", exported[name]["columns"], source[name]["columns"])
            audit.eq(f"roundtrip {name} instances", exported[name]["instances"], source[name]["instances"])
        roundtrip = native_json(RUN / "roundtrip-validation.json")
        audit.eq("roundtrip checker result", roundtrip["passed"], True)
        audit.eq("roundtrip source SHA", roundtrip["source_sha256"], INPUT_SHA)
        audit.eq("roundtrip export SHA", roundtrip["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
        audit.eq("roundtrip SXI SHA", roundtrip["sxi_sha256"], sha(RUN / "model.sxi"))
        audit.eq("import completion", "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"), True)
        audit.eq("export completion", "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig"), True)
        calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
        audit.eq("converter summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc, True)
        audit.eq("sole warning codes", re.findall(r"\(warning #(\d+)\)", calc), ["108", "126"])
        audit.eq("no converter errors", re.findall(r"\(error #(\d+)\)", calc), [])
        audit.eq("valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
        audit.eq("36-hour log horizon", lines[1], "36")
        def events(fragment):
            found = []
            for position, line in enumerate(lines):
                if fragment in line:
                    match = re.match(r"Time: (\d+(?:\.\d+)?)\s", line)
                    if match is None:
                        raise ValueError("untimed event: " + line)
                    found.append((position, float(match.group(1)), line))
            return found
        def times(fragment):
            return [item[1] for item in events(fragment)]
        mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
        aircraft = "<TEACH-AIR-01,0>"
        expected_events = [
            ("order", "mission ordered: BASIC-MISSION", [7]),
            ("create", mission + " mission created:", [7]),
            ("request two", mission + " mission activated, systems requested: 2", [7]),
            ("allocate aircraft0", mission + " mission allocates system: " + aircraft, [7]),
            ("prepare start", aircraft + " preparation started, mission: " + mission, [7]),
            ("prepare end", aircraft + " preparation ended, mission: " + mission, [7]),
            ("launch", mission + " mission starting, duration: 2 : " + aircraft, [8]),
            ("task start", mission + " task starting: " + aircraft, [8.5]),
            ("task end", mission + " task completed: " + aircraft, [9.5]),
            ("success", mission + " mission success:", [10]),
            ("completion", mission + " mission completed: " + aircraft, [10]),
            ("physical return", "System arrives " + aircraft + ", mission success", [10]),
            ("ready increase", aircraft + " nbr ready increased at unit:", [0, 10]),
        ]
        for label, fragment, wanted in expected_events:
            audit.eq("event " + label, times(fragment), wanted)
        audit.eq("one mission creation", times(" mission created:"), [7])
        audit.eq("one mission launch", times(" mission starting, duration:"), [8])
        audit.eq("one mission success", times(" mission success:"), [10])
        audit.eq("no waiting/cancel/abort", any(re.search(r"mission waiting:|mission cancelled:|mission aborted:", line) for line in lines), False)
        audit.eq("only physical aircraft ID0", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])
        audit.eq("no failure/PM/stock demand", any(re.search(r"failure occurs|PM task starting|demand for item|backorder|issue item", line, re.I) for line in lines), False)
        order = [events(fragment)[0][0] for fragment in (mission + " mission allocates system:", mission + " mission starting, duration:", mission + " mission success:", mission + " mission completed:", "System arrives " + aircraft)]
        audit.eq("physical event ordering", order, sorted(order))

        report = tables(native_json(RUN / "report-raw.json"), "report")
        parent_report = tables(native_json(PARENT_RUN / "report-raw.json"), "report")
        audit.eq("four report tables", list(report), list(parent_report))
        fields, system_rows = rows(report["SystemResults"])
        parent_fields, parent_system = rows(parent_report["SystemResults"])
        audit.eq("System columns", fields, parent_fields)
        audit.eq("System shape", (len(system_rows), len(fields)), (72, 40))
        modeled = {"STINT", "ETINT", "NSYRY", "NSYMA", "NSYMR", "NSYMO", "NSYA", "FTMO", "STACC"}
        for index, row in enumerate(system_rows):
            start = index / 2
            end = start + .5
            reserved = max(0.0, min(end, 8) - max(start, 7)) / .5
            flying = max(0.0, min(end, 10) - max(start, 8)) / .5
            predicted = {"STINT": start, "ETINT": end, "NSYRY": 1 - reserved - flying,
                         "NSYMA": reserved + flying, "NSYMR": reserved, "NSYMO": flying,
                         "NSYA": 1, "FTMO": flying, "STACC": flying}
            for column, (field, value) in enumerate(zip(fields, row)):
                if field in modeled:
                    audit.near(f"System[{index}].{field}", value, predicted[field])
                else:
                    audit.eq(f"System[{index}].{field} parent parity", value, parent_system[index][column])
        for field, wanted in (("NSYRY", 33), ("NSYMR", 1), ("NSYMO", 2), ("FTMO", 2)):
            audit.near(f"System {field} aircraft-hours", sum(row[fields.index(field)] * .5 for row in system_rows), wanted)
        audit.near("terminal one ready", system_rows[-1][fields.index("NSYRY")], 1)

        stock_fields, stock_rows = rows(report["StockTotalResults"])
        parent_stock_fields, parent_stock = rows(parent_report["StockTotalResults"])
        audit.eq("Stock columns", stock_fields, parent_stock_fields)
        audit.eq("Stock shape", (len(stock_rows), len(stock_fields)), (72, 16))
        for index, (row, old) in enumerate(zip(stock_rows, parent_stock)):
            for column, field in enumerate(stock_fields):
                audit.eq(f"Stock[{index}].{field} parent parity", row[column], old[column])

        summary_fields, summary_rows = rows(report["ResultSummary"])
        parent_summary_fields, _ = rows(parent_report["ResultSummary"])
        audit.eq("Summary columns", summary_fields, parent_summary_fields)
        audit.eq("Summary shape", (len(summary_rows), len(summary_fields)), (1, 11))
        expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "RSMTMF": 0,
                            "MSTF": 1, "RSMSTF": 0, "MSUF": 1, "RSMSUF": 0, "STMF": .5, "RSSTMF": 0}
        for field, value in zip(summary_fields, summary_rows[0]):
            audit.near("Summary." + field, value, expected_summary[field])

        description_fields, description_rows = rows(report["ProblemDescription"])
        parent_description_fields, parent_description_rows = rows(parent_report["ProblemDescription"])
        audit.eq("ProblemDescription columns", description_fields, parent_description_fields)
        audit.eq("ProblemDescription unchanged stale label", description_rows, parent_description_rows)
        audit.eq("ProblemDescription source parity", description_rows, rows(source["ProblemDescription"])[1])
    except Exception as exc:
        audit.failures.append(f"replay exception: {type(exc).__name__}: {exc}")

    result = {
        "schema": "a03-var01-min-one-independent-replay/v1",
        "decision": "GO_BOUNDED" if not audit.failures else "NO_GO",
        "checks": audit.checks,
        "failures": audit.failures,
        "run_id": RUN_ID,
        "closure_sha256": closure_hash,
        "limits": ["One seed, unit, type and scheduled wave; one aircraft equals MNOS1 below NOS2.",
                   "No general assignment, alternate availability, GUI or cross-engine claim.",
                   "Inherited two-aircraft ProblemDescription remains stale; raw native JSON was normalized only in memory."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not audit.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
