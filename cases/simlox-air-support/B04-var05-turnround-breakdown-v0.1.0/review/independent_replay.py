"""Independent standard-library replay of sealed B04.var05 raw evidence."""

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
RUN_ID = "b04-var05-turnbreak-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
B04 = ROOT / "B04-cross-midnight-turnround-v1.0.1"
B04_RUN = B04 / "runs" / "b04-v101-turnround-20260930-01"
B02 = ROOT / "B02-serial-preparation-v1.0.2"
B02_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\B02-serial-preparation-v1.0.2\runs\b02-v102-ssh-20260929-01")
A02 = ROOT / "A02-single-aircraft-repeated-missions"
A02_RUNS = Path(r"C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02")
CHILD_SHA = "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f"
PARENT_SHA = "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"
CLOSURE_SHA = "58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545"
B04_CLOSURE_SHA = "85d25bd8fa2a053639ca9a93b3bbdd78a5c04e3db9a5d826e27998d500f95ae1"
B02_CLOSURE_SHA = "3bbaffe3460da2195a4084cb3b92e1fc9c605a5d01380619abf92e3cd107f570"
A02_CLOSURE_SHAS = {"a02-bound-final-20260927-03": "fc0cc2d0578d2e8d126e79886ab2ba72238a725aea86c361ede6d48dadc6a69a",
                     "a02-bound-replay-20260927-04": "9a44bc9f5d52cfd2178545315b6cd9b380585e98c36502025b329e380f1909d1"}
REPORT_PARENT_SHA = "ea429a8c563f50256ca24168e8ae103222e5fe01918fbb52c40c6adf64a66897"
SOURCE_SHAS = {"child_input": CHILD_SHA, "child_contract": "5292459de185e04ef445ff89e4e20cb1c8d9148151f767340b59893d089d3020",
               "runner_script": "8dc0600ffcb5979bc1e855c93b5d3528eb0df838f85ca409bd58e1b38c931be4",
               "behavior_validator": "1d56c6c0338866aa92d4124146eb2fbe0d0307ebd3e41c7031b9ee377d988325",
               "expected_ledger_delta": "5659de210fd4f9eca999b616615eb62f124ea0a8ff789f1718549a7ae0b239dc",
               "accepted_input": PARENT_SHA, "accepted_closure": B04_CLOSURE_SHA,
               "accepted_report": REPORT_PARENT_SHA, "prereq_closure": B02_CLOSURE_SHA,
               "prelaunch_approval": "c74aebc95afddd34b3f389645fa831d5deb71bf6a486543cb463b6aa4e4d8b7b"}
SYSTEM_OVERRIDES = {
    48: {"NSYMP": 1.0, "NSYMT": 0.0, "NPSTA": 1.0},
    49: {"NSYMO": 0.5, "NSYMP": 0.0, "NSYMR": 0.5, "FTMO": 0.5, "STACC": 0.5, "NPSTA": 0.0, "NPSUC": 1.0},
    50: {"NPSUC": 0.0},
    53: {"NSYMO": 0.5, "NSYMT": 0.5, "FTMO": 0.5, "STACC": 0.5},
    54: {"NSYRY": 0.5, "NSYMA": 0.5, "NSYMT": 0.5},
    55: {"NSYRY": 1.0, "NSYMA": 0.0, "NSYMT": 0.0},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    raw = path.read_bytes().decode("utf-8-sig")
    cleaned = []
    quoted = escaped = False
    for i, char in enumerate(raw):
        if quoted:
            cleaned.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            cleaned.append(char)
        elif char == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
            continue
        else:
            cleaned.append(char)
    return json.loads("".join(cleaned))


def source_cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        cols = [c["name"] for c in table["columns"]]
        for instance_number, instance in enumerate(table["instances"]):
            for row_number, row in enumerate(instance["rows"]):
                if len(row) != len(cols):
                    raise ValueError("nonrectangular source")
                for col, value in zip(cols, row):
                    key = (table["name"], instance_number, row_number, col)
                    if key in result:
                        raise ValueError("duplicate source cell")
                    result[key] = value
    return result


def populated(doc, root):
    result = {}
    for table in doc[root]["tables"]:
        if any(instance["rows"] for instance in table["instances"]):
            if table["name"] in result:
                raise ValueError("duplicate table")
            result[table["name"]] = table
    return result


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def require(self, condition, description):
        self.count += 1
        if not condition:
            self.failures.append(description)

    def seal(self, folder, closure, raw_key, count, label):
        files = closure[raw_key]
        self.require(len(files) == count, f"{label} seal count")
        for name, record in sorted(files.items()):
            path = folder / name
            self.require(path.is_file(), f"{label} missing {name}")
            if path.is_file():
                self.require(path.stat().st_size == record["bytes"], f"{label} bytes {name}")
                self.require(sha(path) == record["sha256"], f"{label} SHA {name}")


def source_paths():
    return {
        "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
        "contract_review": HERE / "independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py", "shared_parser": ROOT / "tools" / "validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py", "expected_ledger_delta": CASE / "expected-ledger-delta.json",
        "runner_script": CASE / "run_native_ssh.ps1", "accepted_input": B04 / "turnround-input.json",
        "accepted_contract": B04 / "contract.json", "accepted_signoff": B04 / "cli-scope-signoff-2026-09-30.md",
        "accepted_closure": B04_RUN / "closure.json", "accepted_report": B04_RUN / "report-raw.json",
        "prereq_input": B02 / "native-input.json", "prereq_closure": B02_RUN / "closure.json",
        "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "installed_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "prelaunch_approval": HERE / "independent-prelaunch-go.json",
    }


def event_matches(log, time, fragment):
    hits = []
    for line in log.splitlines():
        match = re.match(r"^Time:\s*([0-9.]+)\s+(.*)$", line)
        if match and abs(float(match.group(1)) - time) <= 0.00011 and fragment in match.group(2):
            hits.append(line)
    return hits


def replay():
    c = Checks()
    c.require(RUN.name == RUN_ID and RUN.is_dir(), "child run identity")
    c.require(sha(RUN / "closure.json") == CLOSURE_SHA, "child closure SHA")
    closure, invocation = load(RUN / "closure.json"), load(RUN / "invocation.json")
    c.require(closure.get("run_id") == invocation.get("run_id") == RUN_ID and closure.get("error") is None, "closure status")
    c.require(closure.get("invocation_sha256") == sha(RUN / "invocation.json"), "invocation seal")
    c.seal(RUN, closure, "raw", 13, "child")
    c.require({p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"} == set(closure["raw"]),
              "no unsealed child raw files")
    for name, folder, expected_sha, count in (("B04", B04_RUN, B04_CLOSURE_SHA, 12),
                                               ("B02", B02_RUN, B02_CLOSURE_SHA, 11)):
        c.require(sha(folder / "closure.json") == expected_sha, f"{name} closure SHA")
        control = load(folder / "closure.json")
        c.seal(folder, control, "raw", count, name)
    c.require(sha(A02 / "native-input.json") == "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8", "A02 source SHA")
    c.require(sha(A02 / "cli-scope-signoff-2026-09-29.md") == "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e", "A02 signoff SHA")
    for name, expected in A02_CLOSURE_SHAS.items():
        folder = A02_RUNS / name
        c.require(sha(folder / "closure.json") == expected, f"A02 {name} closure SHA")
        record = load(folder / "closure.json")
        c.require(record.get("run_id") == name, f"A02 {name} identity")
        c.seal(folder, record, "artifacts", 12, f"A02 {name}")
        c.require(sha(folder / "invocation.json") == record["invocation_sha256"], f"A02 {name} invocation SHA")
    before = closure["source_hashes_before"]
    paths = source_paths()
    c.require(before == closure["source_hashes_after"] == invocation["source_hashes_before"], "source before/after parity")
    c.require(set(before) == set(paths), "source labels complete")
    for label, path in sorted(paths.items()):
        c.require(path.is_file(), f"source present {label}")
        if path.is_file():
            c.require(sha(path) == before.get(label), f"source SHA {label}")
    for label, expected in SOURCE_SHAS.items():
        c.require(before.get(label) == expected, f"fixed source pin {label}")
    c.require(invocation.get("input_sha256") == CHILD_SHA and invocation.get("runner_script_sha256") == SOURCE_SHAS["runner_script"],
              "invocation source identity")
    c.require(invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True
              and "sshd.exe" in invocation.get("ssh_ancestor_names", []), "SSH0 ancestry")
    gui = invocation.get("gui", {})
    c.require(gui.get("pid") == 13340 and gui.get("session_id") == 1
              and gui.get("start_unix_ms") == 1790590196826, "GUI PID/session/start")
    c.require(invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue", "global mutex")
    c.require(sha(RUN / "input.json") == CHILD_SHA == sha(CASE / "native-input.json"), "copied child input")
    parent_cells = source_cells(load(B04 / "turnround-input.json"))
    child_cells = source_cells(load(CASE / "native-input.json"))
    c.require(len(parent_cells) == 204 and len(child_cells) == 221, "204-to-221 authored cell topology")
    changed = {key: (parent_cells[key], child_cells[key]) for key in parent_cells.keys() & child_cells.keys()
               if parent_cells[key] != child_cells[key]}
    added = {key: child_cells[key] for key in child_cells.keys() - parent_cells.keys()}
    expected_added = {("Tasks", 0, 1, field): value for field, value in
                      {"TID": "TURN-STEPS", "DESCR": "Serial 10+20-minute post-mission turnround",
                       "TCID": None, "TLID": None, "NOTE": None}.items()}
    for row, seq, sid, duration in ((2, 1, "INSPECT", 1 / 6), (3, 2, "SERVICE", 1 / 3)):
        expected_added.update({("TaskBreakDown", 0, row, field): value for field, value in
                               {"TID": "TURN-STEPS", "SEQ": seq, "SUTID": sid, "DURN": duration,
                                "DURND": None, "NOTE": None}.items()})
    c.require(changed == {("MissionTurnround", 0, 0, "TID"): (None, "TURN-STEPS")}, "one existing source cell")
    c.require(added == expected_added and not (parent_cells.keys() - child_cells.keys()), "exact three appended source rows")
    authored = populated(load(RUN / "input.json"), "model")
    exported = populated(load(RUN / "roundtrip-raw.json"), "model")
    c.require(len(authored) == 18 and set(authored) <= set(exported), "18 authored row-containing tables survive")
    for name, table in sorted(authored.items()):
        c.require(exported.get(name, {}).get("columns") == table["columns"]
                  and exported.get(name, {}).get("instances") == table["instances"], f"roundtrip {name}")
    for name in sorted(set(exported) - set(authored)):
        c.require(all(all(cell is None for cell in row)
                      for instance in exported[name]["instances"] for row in instance["rows"]),
                  f"native-only placeholder has no populated cell: {name}")
    steps = load(RUN / "steps.json")
    c.require([step.get("name") for step in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"],
              "six stage order")
    for i, step in enumerate(steps):
        c.require(step.get("status") == "completed" and step.get("exit_code") == 0
                  and step.get("gui_preserved") is True, f"step {i} exit/status/GUI")
    c.require([item["name"] for item in invocation.get("planned_commands", [])] == ["import", "export", "calc", "jsonreport"],
              "four planned native commands")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    c.require(re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
              == [("0", "2", "0")], "converter 0/2/0")
    c.require(re.findall(r"\(warning #(\d+)\)", run_log) == ["108", "126"]
              and "(error #" not in run_log, "only warnings 108/126")
    c.require((RUN / "model.sxo").stat().st_size > 4 and (RUN / "model.log").stat().st_size > 0,
              "substantive SXO and physical log")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    events = [
        (20.5, "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        (20.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>"),
        (20.5, "preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (20.5, "system preparation task 0 on <TEACH-AIR-01,0> started"),
        (21, "system preparation task 0 on <TEACH-AIR-01,0> completed"),
        (21, "preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (21.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting"),
        (22, "<BASIC-MISSION,TEACH-UNIT,0,0,0> task starting: <TEACH-AIR-01,0>"),
        (23, "<BASIC-MISSION,TEACH-UNIT,0,0,0> task completed: <TEACH-AIR-01,0>"),
        (23.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success"),
        (23.5, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>"),
        (23.5, "system turnround task 1 on <TEACH-AIR-01,0> started"),
        (23.5, "subtask 2 seqno 1 within system turnround task 1 on <TEACH-AIR-01,0> started"),
        (23.6667, "subtask 2 seqno 1 within system turnround task 1 on <TEACH-AIR-01,0> completed"),
        (23.6667, "subtask 3 seqno 2 within system turnround task 1 on <TEACH-AIR-01,0> started"),
        (23.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission preassigns a system: <TEACH-AIR-01,0>"),
        (23.75, "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        (24, "subtask 3 seqno 2 within system turnround task 1 on <TEACH-AIR-01,0> completed"),
        (24, "system turnround task 1 on <TEACH-AIR-01,0> completed"),
        (24, "turnround ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>"),
        (24, "System arrives <TEACH-AIR-01,0>, mission success"),
        (24, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system: <TEACH-AIR-01,0>"),
        (24, "preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (24, "system preparation task 2 on <TEACH-AIR-01,0> started"),
        (24.1667, "subtask 4 seqno 1 within system preparation task 2 on <TEACH-AIR-01,0> completed"),
        (24.1667, "subtask 5 seqno 2 within system preparation task 2 on <TEACH-AIR-01,0> started"),
        (24.5, "subtask 5 seqno 2 within system preparation task 2 on <TEACH-AIR-01,0> completed"),
        (24.5, "system preparation task 2 on <TEACH-AIR-01,0> completed"),
        (24.5, "preparation ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (24.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
        (25.25, "<BASIC-MISSION,TEACH-UNIT,0,0,1> task starting: <TEACH-AIR-01,0>"),
        (26.25, "<BASIC-MISSION,TEACH-UNIT,0,0,1> task completed: <TEACH-AIR-01,0>"),
        (26.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
        (26.75, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed: <TEACH-AIR-01,0>"),
        (26.75, "system turnround task 3 on <TEACH-AIR-01,0> started"),
        (26.75, "subtask 6 seqno 1 within system turnround task 3 on <TEACH-AIR-01,0> started"),
        (26.9167, "subtask 6 seqno 1 within system turnround task 3 on <TEACH-AIR-01,0> completed"),
        (26.9167, "subtask 7 seqno 2 within system turnround task 3 on <TEACH-AIR-01,0> started"),
        (27.25, "subtask 7 seqno 2 within system turnround task 3 on <TEACH-AIR-01,0> completed"),
        (27.25, "system turnround task 3 on <TEACH-AIR-01,0> completed"),
        (27.25, "turnround ended, mission: <BASIC-MISSION,TEACH-UNIT,0,0,1>"),
        (27.25, "System arrives <TEACH-AIR-01,0>, mission success"),
        (27.25, "systems ready: 1 :<TEACH-AIR-01,0>"),
    ]
    for time, fragment in events:
        c.require(len(event_matches(log, time, fragment)) >= 1, f"event h{time}: {fragment}")
    for task_id, pairs in ((0, ((0, 20.5, 20.6667), (1, 20.6667, 21))),
                           (2, ((4, 24, 24.1667), (5, 24.1667, 24.5)))):
        for subtask_id, start, end in pairs:
            seq = 1 if subtask_id in (0, 4) else 2
            base = f"subtask {subtask_id} seqno {seq} within system preparation task {task_id} on <TEACH-AIR-01,0>"
            for verb, time in (("started", start), ("requests resources: no resources needed", start),
                               ("starts performing", start), ("completed", end)):
                c.require(len(event_matches(log, time, f"{base} {verb}")) >= 1,
                          f"preparation lifecycle h{time}: {base} {verb}")
    for task_id, pairs in ((1, ((2, 23.5, 23.6667), (3, 23.6667, 24))),
                           (3, ((6, 26.75, 26.9167), (7, 26.9167, 27.25)))):
        for subtask_id, start, end in pairs:
            for verb, time in (("started", start), ("requests resources: no resources needed", start),
                               ("resource availability test", start), ("starts performing", start), ("completed", end)):
                fragment = f"subtask {subtask_id} seqno {1 if subtask_id in (2,6) else 2} within system turnround task {task_id} on <TEACH-AIR-01,0> {verb}"
                c.require(len(event_matches(log, time, fragment)) >= 1, f"turnround lifecycle h{time}: {fragment}")
    c.require(len(re.findall(r"(?m)^Time: [0-9.]+\s+subtask \d+ seqno [12] within system (?:preparation|turnround) task \d+ on <TEACH-AIR-01,0> started$", log)) == 8,
              "exactly eight authored subtask starts")
    c.require(not re.search(r"(?i)mission cancelled|mission aborted|failure occurred|PMTask.*started|backorder|resource wait", log),
              "no cancellation/failure/PM/backorder/resource wait")
    child_report = populated(load(RUN / "report-raw.json"), "report")
    parent_report = populated(load(B04_RUN / "report-raw.json"), "report")
    c.require(set(child_report) == set(parent_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
              "no unexpected report tables")
    expected_file = load(CASE / "expected-ledger-delta.json")
    c.require({int(k): v for k, v in expected_file["system_results_overrides"].items()} == SYSTEM_OVERRIDES
              and expected_file["result_summary_overrides"] == {}
              and expected_file["stock_total_results_overrides"] == {}, "predeclared report delta map")
    report_cells = 0
    for name in sorted(parent_report):
        a, b = parent_report[name], child_report[name]
        c.require(a["columns"] == b["columns"] and len(a["instances"]) == len(b["instances"]) == 1,
                  f"report table schema {name}")
        cols = [x["name"] for x in a["columns"]]
        ra, rb = a["instances"][0]["rows"], b["instances"][0]["rows"]
        c.require(len(ra) == len(rb) == {"ProblemDescription": 1, "ResultSummary": 1,
                                        "SystemResults": 72, "StockTotalResults": 72}[name],
                  f"report row count {name}")
        c.require(a["instances"][0]["instance_name"] == b["instances"][0]["instance_name"], f"instance {name}")
        for row_index, (old, new) in enumerate(zip(ra, rb)):
            c.require(len(old) == len(new) == len(cols), f"report row width {name}/{row_index}")
            for field, prior, actual in zip(cols, old, new):
                expected = SYSTEM_OVERRIDES.get(row_index, {}).get(field, prior) if name == "SystemResults" else prior
                c.require(actual == expected, f"report cell {name}/{row_index}/{field}")
                report_cells += 1
    # These two columns are integral occupancy fractions over the half-hour bins.
    sys_table = child_report["SystemResults"]
    columns = [x["name"] for x in sys_table["columns"]]
    rows = sys_table["instances"][0]["rows"]
    c.require(all(abs(row[columns.index("STINT")] - index * 0.5) < 1e-9
                  and abs(row[columns.index("ETINT")] - (index + 1) * 0.5) < 1e-9
                  for index, row in enumerate(rows)), "72 contiguous half-hour System bins")
    c.require(rows[-1][columns.index("NSYRY")] == 1, "terminal ready")
    result = {"schema": "simlox-b04-var05-independent-replay/v1",
              "decision": "GO_BOUNDED" if not c.failures else "NO_GO",
              "checks": c.count, "failures": c.failures, "run_id": RUN_ID,
              "closure_sha256": CLOSURE_SHA, "report_cells_checked": report_cells,
              "system_changed_cells": sum(len(v) for v in SYSTEM_OVERRIDES.values()),
              "scope": "one deterministic linked two-step turnround and resulting second-wave timing",
              "limits": ["one aircraft, two missions, fixed seed and installed SIMLOX 2017 CLI",
                         "no resource contention, item faults, GUI visual or general turnround semantics"]}
    return result


if __name__ == "__main__":
    try:
        verdict = replay()
    except Exception as exc:
        verdict = {"schema": "simlox-b04-var05-independent-replay/v1", "decision": "NO_GO", "checks": 0,
                   "failures": [f"exception: {type(exc).__name__}: {exc}"], "run_id": RUN_ID}
    (HERE / "independent-verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    raise SystemExit(0 if verdict["decision"] == "GO_BOUNDED" else 1)
