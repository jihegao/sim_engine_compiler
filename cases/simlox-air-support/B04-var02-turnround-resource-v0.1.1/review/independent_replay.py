"""Independent, read-only replay of sealed B04.var02 v0.1.1 CLI evidence.

Uses the Python standard library only and does not import the author validator.
Only the deterministic verdict in this review directory is written.
"""

import hashlib
import json
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
RUN_ID = "b04-var02-turn-resource-v011-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "B04-var05-turnround-breakdown-v0.1.0"
PARENT_RUN = PARENT / "runs/b04-var05-turnbreak-v010-ssh-20261006-01"
C01 = ROOT / "C01-personnel-capacity-v1.0.2"
C01_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C01-personnel-capacity-v1.0.2\runs\c01-v102-cap2-ssh-20260929-05")
INPUT_SHA = "0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5"
CLOSURE_SHA = "e9fb116596e60ad9d80d2c888c3c4f5c41543d44baee58130111082cc9b6e723"
PARENT_CLOSURE_SHA = "58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545"
C01_CLOSURE_SHA = "770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163"
FIXED_SOURCE = {
    "child_input": INPUT_SHA,
    "child_contract": "eddc9b1221ac6f0c1acb4c55764bb218c61b251ca58435fb8f2f14efc3b8d49d",
    "contract_review": "cfb0ba4ee149e9d98af0988eeb2602ecc854be48523034f911b549ef0b542597",
    "runner_script": "76740d885a9685aee5457a011b988a5451c8f426f9fb51331f40d3976c928a51",
    "behavior_validator": "fabc0b7f2185690e1a617a49baec3dc4f275be4ddbb371cd8ee11e9d8c615b08",
    "prelaunch_approval": "ae8f6f50a82373bad8d835f3dfec45297d1aa8a8998bcd2f378577a6a6e95d2e",
    "accepted_input": "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f",
    "accepted_closure": PARENT_CLOSURE_SHA,
    "accepted_report": "df1c6055ce7cd32dea0e02112ab752bc34ec2484311e7d0baa44b04910a1c87a",
    "prereq_input": "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c",
    "prereq_closure": C01_CLOSURE_SHA,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    """Parse native trailing-comma JSON in memory, preserving raw file bytes."""
    raw = path.read_bytes().decode("utf-8-sig")
    out = []
    quoted = escaped = False
    for i, char in enumerate(raw):
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
        elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        names = [column["name"] for column in table["columns"]]
        for ins_no, instance in enumerate(table["instances"]):
            for row_no, row in enumerate(instance["rows"]):
                if len(row) != len(names):
                    raise ValueError("nonrectangular source " + table["name"])
                result.update({(table["name"], ins_no, row_no, name): value
                               for name, value in zip(names, row)})
    return result


def tables(doc, root):
    result = {}
    for table in doc[root]["tables"]:
        if table["name"] in result:
            raise ValueError("duplicate table " + table["name"])
        result[table["name"]] = table
    return result


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def need(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)

    def near(self, actual, expected, label, tolerance=1e-7):
        self.need(isinstance(actual, (int, float)) and
                  math.isclose(actual, expected, abs_tol=tolerance, rel_tol=0), label)

    def sealed(self, folder, closure, expected_count, label):
        records = closure["raw"]
        self.need(len(records) == expected_count, label + " raw count")
        for name, record in sorted(records.items()):
            path = folder / name
            self.need(path.is_file(), label + " present " + name)
            if path.is_file():
                self.need(path.stat().st_size == record["bytes"], label + " size " + name)
                self.need(sha(path) == record["sha256"], label + " SHA " + name)


def source_paths():
    return {
        "child_input": CASE / "native-input.json",
        "child_contract": CASE / "contract.json",
        "contract_review": HERE / "independent-contract-go-2026-10-07.md",
        "builder": CASE / "build.py",
        "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py",
        "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py",
        "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json",
        "accepted_contract": PARENT / "contract.json",
        "accepted_signoff": PARENT / "cli-scope-signoff-2026-10-06.md",
        "accepted_closure": PARENT_RUN / "closure.json",
        "accepted_report": PARENT_RUN / "report-raw.json",
        "prereq_input": C01 / "inputs/capacity-2.json",
        "prereq_closure": C01_RUN / "closure.json",
        "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "installed_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "prelaunch_approval": HERE / "independent-prelaunch-go.json",
    }


def time_lines(log, fragment):
    found = []
    context_time = None
    for line_no, line in enumerate(log.splitlines()):
        match = re.match(r"^Time: ([0-9.]+) (.*)$", line)
        if match:
            context_time = float(match.group(1))
        if context_time is not None and fragment in line:
            found.append((context_time, line_no))
    return found


def replay():
    c = Checks()
    c.need(RUN.is_dir() and RUN.name == RUN_ID, "run path")
    c.need(sha(RUN / "closure.json") == CLOSURE_SHA, "fixed closure SHA")
    closure, invocation = load(RUN / "closure.json"), load(RUN / "invocation.json")
    c.need(closure["run_id"] == invocation["run_id"] == RUN_ID and closure["error"] is None, "closure identity/success")
    c.need(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation SHA")
    c.sealed(RUN, closure, 13, "child")
    c.need({p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"} == set(closure["raw"]),
           "no unsealed child raw")
    for label, folder, fixed, count in (("parent", PARENT_RUN, PARENT_CLOSURE_SHA, 13),
                                        ("C01", C01_RUN, C01_CLOSURE_SHA, 11)):
        c.need(sha(folder / "closure.json") == fixed, label + " closure SHA")
        c.sealed(folder, load(folder / "closure.json"), count, label)

    before = closure["source_hashes_before"]
    c.need(before == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after/invocation")
    paths = source_paths()
    c.need(set(before) == set(paths), "complete source label set")
    for key, path in sorted(paths.items()):
        c.need(path.is_file(), "source present " + key)
        if path.is_file():
            c.need(sha(path) == before.get(key), "source SHA " + key)
    for key, fixed in FIXED_SOURCE.items():
        c.need(before.get(key) == fixed, "fixed source pin " + key)
    c.need(invocation["input_sha256"] == INPUT_SHA and invocation["contract_sha256"] == FIXED_SOURCE["child_contract"]
           and invocation["runner_script_sha256"] == FIXED_SOURCE["runner_script"], "invocation file identity")
    c.need(invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True
           and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 and sshd ancestry")
    gui = invocation["gui"]
    c.need(gui["pid"] == 13340 and gui["session_id"] == 1 and gui["start_unix_ms"] == 1790590196826, "GUI identity")
    c.need(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    c.need(sha(RUN / "input.json") == sha(CASE / "native-input.json") == INPUT_SHA, "copied frozen source")

    parent_cells = cells(load(PARENT / "native-input.json"))
    child_cells = cells(load(CASE / "native-input.json"))
    c.need(len(parent_cells) == 221 and len(child_cells) == 249, "221-to-249 cells")
    c.need(not (parent_cells.keys() - child_cells.keys()), "no removed parent cells")
    c.need(all(child_cells[key] == value for key, value in parent_cells.items()), "all parent cells unchanged")
    additions = {key: value for key, value in child_cells.items() if key not in parent_cells}
    expected_rows = {
        ("Resource", 0): ["P-CREW", "Turnround crew", None, None, None, "SPECIAL", None, None],
        ("ResourceAllocation", 0): ["AIR_BASIC", "P-CREW", "BASE-01", 1, None],
        ("SubTaskResource", 0): ["TURN-STEPS", 1, "P-CREW", 1, 1, None, None, None, None],
        ("ResultCollection", 2): ["RESOURCE", 0.5, 0, 36.0, None, None],
    }
    expected_additions = {}
    child_tables = tables(load(CASE / "native-input.json"), "model")
    for (name, row_no), values in expected_rows.items():
        for column, value in zip(child_tables[name]["columns"], values):
            expected_additions[(name, 0, row_no, column["name"])] = value
    c.need(additions == expected_additions and len(additions) == 28, "exact four-row/28-cell delta")

    authored = tables(load(RUN / "input.json"), "model")
    exported = tables(load(RUN / "roundtrip-raw.json"), "model")
    row_tables = {name for name, table in authored.items() if any(x["rows"] for x in table["instances"])}
    c.need(len(row_tables) == 21, "21 authored row-containing tables")
    for name in sorted(row_tables):
        a, b = authored[name], exported.get(name)
        c.need(b is not None and b["columns"] == a["columns"] and b["instances"] == a["instances"],
               "exact authored roundtrip " + name)
    for name in sorted(set(exported) - row_tables):
        c.need(all(all(cell is None for cell in row)
                   for inst in exported[name]["instances"] for row in inst["rows"]),
               "extra export table only null: " + name)

    steps = load(RUN / "steps.json")
    c.need([s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"],
           "six guarded stage order")
    for i, step in enumerate(steps):
        c.need(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True,
               "stage exit/status/GUI " + str(i))
    c.need([x["name"] for x in invocation["planned_commands"]] == ["import", "export", "calc", "jsonreport"],
           "four planned native calls")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    c.need(re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
           == [("0", "2", "0")], "converter 0/2/0")
    c.need(re.findall(r"\(warning #(\d+)\)", run_log) == ["108", "126"] and "(error #" not in run_log,
           "only warning 108/126")
    c.need((RUN / "model.sxo").stat().st_size > 4 and (RUN / "model.log").stat().st_size > 0,
           "substantive native simulation output")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    timeline = [
        (20.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>"),
        (20.5, "preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (21, "preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (21.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting"),
        (22, "<BASIC-MISSION,TEACH-UNIT,0,0,0> task starting: <TEACH-AIR-01,0>"),
        (23, "<BASIC-MISSION,TEACH-UNIT,0,0,0> task completed: <TEACH-AIR-01,0>"),
        (23.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success"),
        (23.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>"),
        (23.5, "turnround started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (23.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission preassigns a system: <TEACH-AIR-01,0>"),
        (24, "turnround ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (24, "System arrives <TEACH-AIR-01,0>, mission success"),
        (24, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,0>"),
        (24, "preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (24.5, "preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (24.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
        (25.25, "<BASIC-MISSION,TEACH-UNIT,0,0,1> task starting: <TEACH-AIR-01,0>"),
        (26.25, "<BASIC-MISSION,TEACH-UNIT,0,0,1> task completed: <TEACH-AIR-01,0>"),
        (26.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
        (26.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed: <TEACH-AIR-01,0>"),
        (26.75, "turnround started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (27.25, "turnround ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (27.25, "System arrives <TEACH-AIR-01,0>, mission success"),
        (27.25, "systems ready: 1 :<TEACH-AIR-01,0>"),
    ]
    for hour, fragment in timeline:
        hits = [(time, line) for time, line in time_lines(log, fragment) if abs(time - hour) < 0.00011]
        c.need(len(hits) == 1, "event " + fragment)
    subtask_windows = [
        (0, 1, "preparation", 20.5, 20.6667), (1, 2, "preparation", 20.6667, 21),
        (2, 1, "turnround", 23.5, 23.6667), (3, 2, "turnround", 23.6667, 24),
        (4, 1, "preparation", 24, 24.1667), (5, 2, "preparation", 24.1667, 24.5),
        (6, 1, "turnround", 26.75, 26.9167), (7, 2, "turnround", 26.9167, 27.25),
    ]
    for number, seq, kind, start, end in subtask_windows:
        base = f"subtask {number} seqno {seq} within system {kind} task "
        for suffix, time in (("started", start), ("starts performing", start), ("completed", end)):
            hits = time_lines(log, base)
            hits = [(t, n) for t, n in hits if suffix in log.splitlines()[n]]
            c.need(len(hits) == 1 and abs(hits[0][0] - time) < 0.00011,
                   f"subtask {number} {suffix}")
    c.need(len(re.findall(r"(?m)^Time: [0-9.]+  subtask \d+ seqno [12] within system (?:preparation|turnround) task \d+ on <TEACH-AIR-01,0> started$", log)) == 8,
           "exactly eight subtask starts")

    for index, (number, task_no, start, end) in enumerate(((2, 1, 23.5, 23.6667), (6, 3, 26.75, 26.9167))):
        base = f"subtask {number} seqno 1 within system turnround task {task_no} on <TEACH-AIR-01,0> "
        fragments = [base + "started", base + "requests resources", base + "resource availability test",
                     "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
                     base + "books resources", "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
                     base + "starts performing, planned to last for 0.166667 hours", base + "completed",
                     base + "frees resources", "<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1"]
        positions = []
        for i, fragment in enumerate(fragments):
            hits = time_lines(log, fragment)
            expected_time = start if i < 7 else end
            matching = [(t, line) for t, line in hits if abs(t - expected_time) < 0.00011]
            c.need(len(matching) == 1, f"lease {index} event {i}")
            if matching:
                positions.append(matching[0][1])
        c.need(len(positions) == 10 and positions == sorted(positions) and len(set(positions)) == 10,
               f"lease {index} strict line order")
    for phrase in ("allocated to maintenance task: 1  available now: 0",
                   "deallocated from  maintenance task: 1  available now: 1"):
        c.need(len(time_lines(log, phrase)) == 2, "only two P-CREW " + phrase)
    c.need(not re.search(r"(?i)mission cancelled|mission aborted|failure occurred|PMTask.*started|backorder|resource wait|request for: 1 NOT OK", log),
           "no cancel/fault/PM/stock/resource wait")

    report = tables(load(RUN / "report-raw.json"), "report")
    parent_report = tables(load(PARENT_RUN / "report-raw.json"), "report")
    names = [table["name"] for table in load(RUN / "report-raw.json")["report"]["tables"]]
    c.need(names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults",
                     "ResourceResults", "ResourceResultsTotal"], "six report tables in order")
    c.need(set(parent_report) == set(names[:4]), "parent four-table topology")
    compared_cells = 0
    for name, expected_rows, expected_cols in (("ProblemDescription", 1, 1), ("ResultSummary", 1, 11),
                                                ("SystemResults", 72, 40), ("StockTotalResults", 72, 16)):
        a, b = parent_report[name], report[name]
        c.need(a["columns"] == b["columns"] and len(b["columns"]) == expected_cols, name + " schema")
        c.need(len(a["instances"]) == len(b["instances"]) == 1 and
               a["instances"][0]["instance_name"] == b["instances"][0]["instance_name"], name + " instance")
        old, new = a["instances"][0]["rows"], b["instances"][0]["rows"]
        c.need(len(old) == len(new) == expected_rows, name + " row count")
        for row_no, (old_row, new_row) in enumerate(zip(old, new)):
            c.need(len(old_row) == len(new_row) == expected_cols, f"{name} row width {row_no}")
            for column, before, after in zip((x["name"] for x in a["columns"]), old_row, new_row):
                c.need(after == before, f"{name}[{row_no}].{column}")
                compared_cells += 1
    c.need(compared_cells == 4044, "all 4044 parent report cells")

    resource = report["ResourceResults"]
    resource_columns = [x["name"] for x in resource["columns"]]
    c.need(resource_columns == ["RID", "STID", "STINT", "ETINT", "NR", "NRMO", "NRMA", "NRUM",
                                "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO"], "resource 16 columns")
    c.need(len(resource["instances"]) == 1 and len(resource["instances"][0]["rows"]) == 72, "72 resource intervals")
    bins = resource["instances"][0]["rows"]
    resource_cells = 0
    for i, row in enumerate(bins):
        c.need(len(row) == 16, f"resource row {i} width")
        expected = ["Total over all Resources", "Total over all Stations", i / 2, (i + 1) / 2,
                    1, 0, 0, 1 / 3 if i in (47, 53) else 0, 0, 0, 1, 1, 0, 0, 0, 0]
        for field, actual, want in zip(resource_columns, row, expected):
            if isinstance(want, str):
                c.need(actual == want, f"ResourceResults[{i}].{field}")
            else:
                c.near(actual, want, f"ResourceResults[{i}].{field}")
            resource_cells += 1
    c.near(sum(row[resource_columns.index("NRUM")] * 0.5 for row in bins), 1 / 3,
           "two leases total 1/3 person-hour")
    total = report["ResourceResultsTotal"]
    total_columns = [x["name"] for x in total["columns"]]
    c.need(total_columns == ["RID", "STID", "NR", "NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRA",
                             "NRN", "NRF", "NRRI", "NRRT", "NRRO"], "resource total 14 columns")
    c.need(len(total["instances"]) == 1 and len(total["instances"][0]["rows"]) == 1, "one resource total row")
    total_row = total["instances"][0]["rows"][0]
    c.need(len(total_row) == 14, "resource total row width")
    expected_total = ["Total over all Resources", "Total over all Stations", 1, 0, 0, 1 / 108,
                      0, 0, 1, 1, 0, 0, 0, 0]
    for field, actual, want in zip(total_columns, total_row, expected_total):
        if isinstance(want, str):
            c.need(actual == want, "ResourceResultsTotal." + field)
        else:
            c.near(actual, want, "ResourceResultsTotal." + field)
        resource_cells += 1
    c.near(total_row[total_columns.index("NRUM")],
           sum(row[resource_columns.index("NRUM")] * 0.5 for row in bins) / 36,
           "resource total mean reconciles with intervals")

    return {"schema": "simlox-b04-var02-independent-replay/v1",
            "decision": "GO_BOUNDED" if not c.failures else "NO_GO", "checks": c.count,
            "failures": c.failures, "run_id": RUN_ID, "closure_sha256": CLOSURE_SHA,
            "parent_report_cells": compared_cells, "resource_report_cells": resource_cells,
            "scope": "one deterministic sufficient P-CREW turnround resource on two task instances",
            "limits": ["one aircraft, two missions, one sufficient resource and one fixed seed",
                       "no resource contention, shortage, shifts, substitution, GUI visual or cross-engine claim"]}


if __name__ == "__main__":
    try:
        verdict = replay()
    except Exception as exc:
        verdict = {"schema": "simlox-b04-var02-independent-replay/v1", "decision": "NO_GO",
                   "checks": 0, "failures": [f"exception: {type(exc).__name__}: {exc}"], "run_id": RUN_ID}
    (HERE / "independent-verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    raise SystemExit(0 if verdict["decision"] == "GO_BOUNDED" else 1)
