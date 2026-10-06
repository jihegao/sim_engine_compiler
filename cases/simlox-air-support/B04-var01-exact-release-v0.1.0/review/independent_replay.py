"""Independent, read-only replay of the sealed B04.var01 CLI evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "B04-cross-midnight-turnround-v1.0.1"
RUN_ID = "b04-var01-release-boundary-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT_RUNS = {
    "turnround": PARENT / "runs/b04-v101-turnround-20260930-01",
    "control": PARENT / "runs/b04-v101-control-20260930-01",
}
SOURCE_PATHS = {
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
    "accepted_input": PARENT / "turnround-input.json",
    "accepted_control_input": PARENT / "control-input.json",
    "accepted_contract": PARENT / "contract.json",
    "accepted_diff": PARENT / "exact-diff.json",
    "accepted_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
    "accepted_verdict": PARENT / "review/independent-turnround-2026-09-30.json",
    "accepted_closure": PARENT_RUNS["turnround"] / "closure.json",
    "accepted_control_closure": PARENT_RUNS["control"] / "closure.json",
    "b02_input": ROOT / "B02-serial-preparation-v1.0.2/native-input.json",
    "b02_evidence": ROOT / "B02-serial-preparation-v1.0.2/evidence-2026-09-29.md",
    "a02_input": ROOT / "A02-single-aircraft-repeated-missions/native-input.json",
    "a02_signoff": ROOT / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md",
    "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
    "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
    "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
    "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict | list:
    """Read native JSON, dropping commas only when followed by an array/object end."""
    text = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = False
    escaped = False
    for pos, char in enumerate(text):
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
            tail = pos + 1
            while tail < len(text) and text[tail].isspace():
                tail += 1
            if tail == len(text) or text[tail] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(document: dict, key: str) -> dict:
    value = document[key]["tables"]
    result = {entry["name"]: entry for entry in value}
    if len(value) != len(result):
        raise ValueError(f"duplicate {key} table")
    return result


def rows(table: dict) -> list[list]:
    return [row for inst in table["instances"] for row in inst["rows"]]


def fields(table: dict) -> list[str]:
    return [column["name"] for column in table["columns"]]


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


def replay() -> dict:
    count = 0
    failed = []
    groups = {}

    def check(group: str, label: str, actual, expected) -> None:
        nonlocal count
        count += 1
        groups[group] = groups.get(group, 0) + 1
        if actual != expected:
            failed.append(f"{group}/{label}: {actual!r} != {expected!r}")

    def close(group: str, label: str, actual, expected: float) -> None:
        check(group, label, isinstance(actual, (int, float)) and abs(actual - expected) < 1e-6, True)

    contract = load(CASE / "contract.json")
    child_closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    check("closure", "child identity", child_closure["run_id"], RUN_ID)
    check("closure", "invocation identity", invocation["run_id"], RUN_ID)
    check("closure", "no child error", child_closure["error"], None)
    check("closure", "invocation SHA", sha(RUN / "invocation.json"), child_closure["invocation_sha256"])
    check("closure", "before/after source map", child_closure["source_hashes_after"], child_closure["source_hashes_before"])
    check("closure", "invocation source map", invocation["source_hashes_before"], child_closure["source_hashes_before"])
    check("closure", "source key set", set(child_closure["source_hashes_before"]), set(SOURCE_PATHS))
    for key, path in SOURCE_PATHS.items():
        check("source", key, sha(path), child_closure["source_hashes_before"][key])
    approval = load(CASE / "review/independent-prelaunch-go.json")
    check("source", "prelaunch decision", approval["decision"], "GO_PRELAUNCH")
    check("source", "prelaunch run identity", approval["run_id"], RUN_ID)
    for field, filename in (("contract_sha256", "contract.json"),
                            ("input_sha256", "native-input.json"),
                            ("runner_sha256", "run_native_ssh.ps1"),
                            ("validator_sha256", "validate_native_cli.py")):
        check("source", "prelaunch " + field, approval[field], sha(CASE / filename))
    check("source", "copied native input", sha(RUN / "input.json"), sha(CASE / "native-input.json"))
    check("source", "invocation input", invocation["input_sha256"], sha(CASE / "native-input.json"))
    check("source", "invocation contract", invocation["contract_sha256"], sha(CASE / "contract.json"))
    check("source", "invocation runner", invocation["runner_script_sha256"], sha(CASE / "run_native_ssh.ps1"))
    for label, directory in PARENT_RUNS.items():
        old = load(directory / "closure.json")
        check("parent", label + " closure", sha(directory / "closure.json"), contract["accepted_parent"][label + "_closure_sha256"])
        check("parent", label + " identity", old["run_id"], directory.name)
        check("parent", label + " raw count", len(old["raw"]), 12)
        for name, seal in old["raw"].items():
            path = directory / name
            check("parent_raw", label + "/" + name + " SHA", sha(path), seal["sha256"])
            check("parent_raw", label + "/" + name + " size", path.stat().st_size, seal["bytes"])
    check("raw", "child raw count", len(child_closure["raw"]), 12)
    check("raw", "run directory exact files", {p.name for p in RUN.iterdir() if p.is_file()}, set(child_closure["raw"]) | {"closure.json", "invocation.json"})
    for name, seal in child_closure["raw"].items():
        path = RUN / name
        check("raw", name + " SHA", sha(path), seal["sha256"])
        check("raw", name + " size", path.stat().st_size, seal["bytes"])

    steps = load(RUN / "steps.json")
    check("guard", "session", invocation["session_id"], 0)
    check("guard", "SSH", invocation["ssh_connection_present"], True)
    check("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    check("guard", "queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    check("guard", "GUI identity", tuple(invocation["gui"][key] for key in ("pid", "session_id", "start_unix_ms")), (13340, 1, 1790590196826))
    check("guard", "ordered steps", [step["name"] for step in steps], ["import", "export", "check_import_export", "calc", "jsonreport"])
    for index, step in enumerate(steps):
        check("guard", f"step {index} exit/status/GUI", (step["exit_code"], step["status"], step["gui_preserved"]), (0, "completed", True))
    check("guard", "native commands", [entry["name"] for entry in invocation["planned_commands"]], ["import", "export", "calc", "jsonreport"])
    for name in ("import", "export", "calc", "jsonreport"):
        planned = next(s for s in invocation["planned_commands"] if s["name"] == name)
        actual = next(s for s in steps if s["name"] == name)
        check("guard", name + " planned arguments", actual["arguments"], planned["arguments"])

    parent = tables(load(PARENT / "turnround-input.json"), "model")
    child = tables(load(CASE / "native-input.json"), "model")
    exported = tables(load(RUN / "roundtrip-raw.json"), "model")
    check("source", "table order", list(child), list(parent))
    changes = []
    authored_cells = 0
    row_tables = 0
    for name, old in parent.items():
        current = child[name]
        check("source", name + " column metadata", current["columns"], old["columns"])
        check("source", name + " instance count", len(current["instances"]), len(old["instances"]))
        check("source", name + " instance names", [x["instance_name"] for x in current["instances"]], [x["instance_name"] for x in old["instances"]])
        check("source", name + " row counts", [len(x["rows"]) for x in current["instances"]], [len(x["rows"]) for x in old["instances"]])
        if rows(current):
            row_tables += 1
            check("roundtrip", name + " column metadata", exported[name]["columns"], current["columns"])
            check("roundtrip", name + " instances/rows", exported[name]["instances"], current["instances"])
        columns = fields(old)
        for row_number, (old_row, new_row) in enumerate(zip(rows(old), rows(current))):
            check("source", name + f" row {row_number} width", len(new_row), len(old_row))
            for field, was, now in zip(columns, old_row, new_row):
                authored_cells += 1
                if was != now:
                    changes.append((name, row_number, field, was, now))
    check("source", "204 positional cells", authored_cells, 204)
    check("source", "sole duration change", changes, [("MissionTurnround", 0, "DURN", 1, 0.75)])
    check("roundtrip", "18 row-containing tables", row_tables, 18)
    roundtrip_verdict = load(RUN / "roundtrip-validation.json")
    check("roundtrip", "native checker passed", roundtrip_verdict["passed"], True)
    check("roundtrip", "native input pin", roundtrip_verdict["source_sha256"], sha(CASE / "native-input.json"))
    check("roundtrip", "native export pin", roundtrip_verdict["roundtrip_sha256"], sha(RUN / "roundtrip-raw.json"))
    check("roundtrip", "SXI pin", roundtrip_verdict["sxi_sha256"], sha(RUN / "model.sxi"))
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("converter", "summary 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log, True)
    check("converter", "warning codes", sorted(re.findall(r"\(warning #(\d+)\)", run_log)), ["108", "126"])
    check("converter", "error codes", re.findall(r"\(error #(\d+)\)", run_log), [])
    check("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

    lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    old_lines = (PARENT_RUNS["turnround"] / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    def stamped(line: str) -> tuple[float, str] | None:
        match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?) (.*)", line)
        return (float(match.group(1)), match.group(2)) if match else None
    check("events", "first mission prefix", [x for x in lines if stamped(x) and stamped(x)[0] < 23.5], [x for x in old_lines if stamped(x) and stamped(x)[0] < 23.5])
    air = "<TEACH-AIR-01,0>"
    mission = [f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>" for i in (0, 1)]
    expected_events = [
        (20.5, "mission ordered: BASIC-MISSION"), (23.75, "mission ordered: BASIC-MISSION"),
        (21.5, mission[0] + " mission starting, duration: 2 : " + air),
        (23.5, mission[0] + " mission success:"), (23.5, mission[0] + " mission completed: " + air),
        (23.5, air + " turnround started, mission: " + mission[0]),
        (23.75, mission[1] + " mission preassigns a system: " + air),
        (24.25, "  system turnround task 1 on " + air + " completed"),
        (24.25, air + " turnround ended, mission: " + mission[0]),
        (24.25, mission[1] + " mission allocates system: " + air),
        (24.25, air + " preparation started, mission: " + mission[1]),
        (24.75, air + " preparation ended, mission: " + mission[1]),
        (24.75, mission[1] + " mission starting, duration: 2 : " + air),
        (26.75, mission[1] + " mission success:"), (26.75, mission[1] + " mission completed: " + air),
        (26.75, air + " turnround started, mission: " + mission[1]),
        (27.5, "  system turnround task 3 on " + air + " completed"),
        (27.5, air + " turnround ended, mission: " + mission[1]),
    ]
    event_positions = []
    for expected_time, fragment in expected_events:
        hits = [(pos, stamped(line)[0]) for pos, line in enumerate(lines) if fragment in line and stamped(line)]
        check("events", fragment, [time for _, time in hits], [expected_time] if fragment != "mission ordered: BASIC-MISSION" else [20.5, 23.75])
        if hits:
            event_positions.append((fragment, hits[0][0]))
    positions = dict(event_positions)
    check("events", "h24.25 order", positions[air + " turnround ended, mission: " + mission[0]] < positions[mission[1] + " mission allocates system: " + air] < positions[air + " preparation started, mission: " + mission[1]], True)
    check("events", "h24.75 order", positions[air + " preparation ended, mission: " + mission[1]] < positions[mission[1] + " mission starting, duration: 2 : " + air], True)
    check("events", "only two launches", [stamped(x)[0] for x in lines if " mission starting, duration: 2 : " in x and stamped(x)], [21.5, 24.75])
    check("events", "only two successes", [stamped(x)[0] for x in lines if " mission success:" in x and stamped(x)], [23.5, 26.75])
    check("events", "no cancel/abort", bool(re.search(r"mission cancelled:|mission aborted:", "\n".join(lines))), False)
    check("events", "one physical aircraft", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])

    previous_report = tables(load(PARENT_RUNS["turnround"] / "report-raw.json"), "report")
    report = tables(load(RUN / "report-raw.json"), "report")
    check("report", "table set", set(report), set(previous_report))
    for name, height, width in (("StockTotalResults", 72, 16), ("ResultSummary", 1, 11), ("ProblemDescription", 1, 1)):
        older = previous_report[name]
        current = report[name]
        check("report", name + " columns", current["columns"], older["columns"])
        check("report", name + " row count", len(rows(current)), height)
        check("report", name + " width", len(fields(current)), width)
        for rix, (before, after) in enumerate(zip(rows(older), rows(current))):
            for column, was, now in zip(fields(current), before, after):
                check("report", f"{name}[{rix}].{column}", now, was)
    prior_system = previous_report["SystemResults"]
    new_system = report["SystemResults"]
    columns = fields(new_system)
    check("report", "System columns", new_system["columns"], prior_system["columns"])
    check("report", "System 72 bins", len(rows(new_system)), 72)
    check("report", "System 40 fields", len(columns), 40)
    segments = {
        "NSYMP": [(20.5, 21), (24.25, 24.75)],
        "NSYMR": [(21, 21.5)],
        "NSYMO": [(21.5, 23.5), (24.75, 26.75)],
        "NSYMT": [(23.5, 24.25), (26.75, 27.5)],
    }
    for rix, (old, current) in enumerate(zip(rows(prior_system), rows(new_system))):
        left = rix * 0.5
        right = left + 0.5
        phase = {key: sum(overlap(left, right, a, b) for a, b in spans) / 0.5 for key, spans in segments.items()}
        active = sum(phase.values())
        expected = dict(phase)
        expected.update(NSYRY=1-active, NSYMA=active, FTMO=phase["NSYMO"], STACC=phase["NSYMO"],
                        NPSTA=int(left <= 20.5 < right) + int(left <= 24.25 < right),
                        NPSUC=int(left <= 21 < right) + int(left <= 24.75 < right),
                        STINT=left, ETINT=right)
        for column, before, after in zip(columns, old, current):
            label = f"System[{rix}].{column}"
            if column in expected:
                close("system_ledger", label, after, expected[column])
            else:
                check("system_ledger", label, after, before)
    totals = {name: sum(row[columns.index(name)] * 0.5 for row in rows(new_system)) for name in ("NSYRY", "NSYMP", "NSYMR", "NSYMO", "NSYMT")}
    for name, expected in (("NSYRY", 29), ("NSYMP", 1), ("NSYMR", .5), ("NSYMO", 4), ("NSYMT", 1.5)):
        close("report", name + " integral", totals[name], expected)
    check("report", "terminal ready", rows(new_system)[-1][columns.index("NSYRY")], 1)

    return {
        "schema": "b04-var01-exact-release-independent-replay/v1",
        "run_id": RUN_ID,
        "decision": "GO_BOUNDED" if not failed else "NO_GO",
        "passed": not failed,
        "checks": count,
        "groups": dict(sorted(groups.items())),
        "failures": failed,
        "closure_sha256": sha(RUN / "closure.json"),
        "report_sha256": sha(RUN / "report-raw.json"),
        "model_log_sha256": sha(RUN / "model.log"),
        "integral_aircraft_hours": totals,
        "limits": [
            "One deterministic CLI source, aircraft, two waves, and 0.75-hour turnround only.",
            "Observed same-time event order does not establish general scheduling priority.",
            "No GUI, resource-constrained turnround, repair, or cross-engine claim.",
        ],
    }


if __name__ == "__main__":
    result = replay()
    output = Path(__file__).with_name("independent-verdict.json")
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: result[k] for k in ("decision", "checks", "closure_sha256", "failures")}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
