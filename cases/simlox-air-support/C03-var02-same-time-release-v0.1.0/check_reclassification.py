"""Author read-only classification of the accepted C03 same-time crew release."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE
REPO = CASE.parents[2]
SOURCE = CASE.parent / "C03-shared-crew-formation-v1.0.2"
RAW = Path(
    r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support"
    r"\C03-shared-crew-formation-v1.0.2\runs"
)
RUNS = {
    "staffing_1": (SOURCE / "inputs" / "staffing-1.json", "c03-v102-staff1-ssh-20260929-02"),
    "staffing_2": (SOURCE / "inputs" / "staffing-2.json", "c03-v102-staff2-ssh-20260929-04"),
}
OUT = HERE / "author-validation.json"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = False
    escaped = False
    for index, char in enumerate(text):
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
            while following < len(text) and text[following].isspace():
                following += 1
            if following == len(text) or text[following] not in "}]":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def tables(model):
    return {table["name"]: table for table in model["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def overlap(left, right, start, end):
    return max(0.0, min(right, end) - max(left, start))


def equal(actual, expected, tolerance=3e-5):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) <= tolerance
    return actual == expected


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)


def git_blob(path: Path):
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.relative_to(REPO).as_posix()}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def check_report(checks: Checks, arm: str, source_model, report):
    capacity = int(arm[-1])
    successful = capacity > 0
    report_tables = tables(report["report"])
    shape = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11),
             "SystemResults": (72, 40), "StockTotalResults": (72, 16),
             "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
    checks.check(set(report_tables) == set(shape), f"{arm} six report tables")
    for name, (height, width) in shape.items():
        checks.check(len(rows(report_tables[name])) == height and len(report_tables[name]["columns"]) == width,
                     f"{arm} {name} shape")
    description = rows(tables(source_model)["ProblemDescription"])[0][0]
    checks.check(rows(report_tables["ProblemDescription"])[0][0] == description, f"{arm} description")
    summary = [1, 0, 36, int(successful), 0, int(successful), 0, int(successful), 0, int(successful), 0]
    for index, (actual, expected) in enumerate(zip(rows(report_tables["ResultSummary"])[0], summary)):
        checks.check(actual == expected, f"{arm} summary {index}")
    if capacity == 2:
        ready_end, mission_end = 9, 9
        prep_spans, reserve_spans, flight_spans = [(7.5, 8, 2)], [], [(8, 9, 2)]
        prep_success_bins = {8: 2}
    elif capacity == 1:
        ready_end, mission_end = 9.5, 9.5
        prep_spans, reserve_spans, flight_spans = [(7.5, 8, 2), (8, 8.5, 1)], [(8, 8.5, 1)], [(8.5, 9.5, 2)]
        prep_success_bins = {8: 1, 8.5: 1}
    else:
        ready_end, mission_end = 8.5, 8.5
        prep_spans, reserve_spans, flight_spans = [(7.5, 8.5, 2)], [], []
        prep_success_bins = {}
    system = report_tables["SystemResults"]
    sys_columns = [column["name"] for column in system["columns"]]
    for index, row in enumerate(rows(system)):
        start, end = index / 2, (index + 1) / 2
        weighted = lambda spans: sum(qty * overlap(start, end, left, right) for left, right, qty in spans) / 0.5
        ready = weighted([(0, 7.5, 2), (ready_end, 36, 2)])
        prep = weighted(prep_spans)
        reserved = weighted(reserve_spans)
        flight = weighted(flight_spans)
        expected = {name: 0 for name in sys_columns}
        expected.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": start,
                         "ETINT": end, "NSYA": 2, "SYDT": None, "NSYRY": ready, "NSYMA": 2 - ready,
                         "NSYMP": prep, "NSYMR": reserved, "NSYMO": flight, "FTMO": flight / 2,
                         "STACC": flight, "NPSTA": 2 if start == 7.5 else 0,
                         "NPSUC": prep_success_bins.get(start, 0)})
        for column, actual in zip(sys_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} System {index} {column}: {actual} vs {expected[column]}")
    stock = report_tables["StockTotalResults"]
    stock_columns = [column["name"] for column in stock["columns"]]
    for index, row in enumerate(rows(stock)):
        expected = {name: 0 for name in stock_columns}
        expected.update({"STINT": index / 2, "ETINT": (index + 1) / 2, "PNB": 1})
        for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected[name] = None
        for column, actual in zip(stock_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} Stock {index} {column}")
    resource = report_tables["ResourceResults"]
    resource_columns = [column["name"] for column in resource["columns"]]
    for index, row in enumerate(rows(resource)):
        start, end = index / 2, (index + 1) / 2
        usage = (2 * overlap(start, end, 7.5, 8) if capacity == 2 else
                 overlap(start, end, 7.5, 8.5) if capacity == 1 else 0) / 0.5
        waiting = (overlap(start, end, 7.5, 8) if capacity == 1 else
                   2 * overlap(start, end, 7.5, 8.5) if capacity == 0 else 0) / 0.5
        expected = {name: 0 for name in resource_columns}
        expected.update({"RID": "Total over all Resources", "STID": "Total over all Stations",
                         "STINT": start, "ETINT": end, "NR": capacity, "NRA": capacity,
                         "NRN": capacity, "NRUM": usage, "NRW": waiting})
        for column, actual in zip(resource_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} Resource {index} {column}: {actual} vs {expected[column]}")
    total = report_tables["ResourceResultsTotal"]
    total_columns = [column["name"] for column in total["columns"]]
    expected_total = {name: 0 for name in total_columns}
    expected_total.update({"RID": "Total over all Resources", "STID": "Total over all Stations",
                           "NR": capacity, "NRA": capacity, "NRN": capacity,
                           "NRUM": (1 / 36) if successful else 0,
                           "NRW": (0.5 / 36) if capacity == 1 else (2 / 36) if capacity == 0 else 0})
    for column, actual in zip(total_columns, rows(total)[0]):
        checks.check(equal(actual, expected_total[column]), f"{arm} ResourceTotal {column}")
    return report_tables


def check_events(checks: Checks, arm: str, run: Path):
    log = (run / "model.log").read_text(errors="replace")
    capacity = int(arm[-1])
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    aircraft = ["<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"]
    required = [
        "Time: 7.5 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        f"Time: 7.5 {mission} mission created:",
        f"Time: 7.5 {mission} mission activated, systems requested: 2",
    ]
    required.extend(f"Time: 7.5 {mission} mission allocates system: {item}" for item in aircraft)
    required.extend(f"Time: 7.5 {item} preparation started, mission: {mission}" for item in aircraft)
    for index, item in enumerate(aircraft):
        required.append(f"Time: 7.5  subtask {index} seqno 1 within system preparation task {index} on {item} requests resources")
    if capacity == 2:
        required.extend([
            "Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 1",
            f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} starts performing, planned to last for 0.5 hours",
            "Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
            f"Time: 7.5  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} starts performing, planned to last for 0.5 hours",
            "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            f"Time: 8 {aircraft[0]} preparation ended, mission: {mission}",
            "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 2",
            f"Time: 8 {aircraft[1]} preparation ended, mission: {mission}",
        ])
        launch, arrival = "8", "9"
    elif capacity == 1:
        required.extend([
            "Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
            f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} starts performing, planned to last for 0.5 hours",
            "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            "Time: 8  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
            f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} starts performing, planned to last for 0.5 hours",
            f"Time: 8 {aircraft[0]} preparation ended, mission: {mission}",
            "Time: 8.5  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            f"Time: 8.5 {aircraft[1]} preparation ended, mission: {mission}",
        ])
        launch, arrival = "8.5", "9.5"
    else:
        required.extend([
            f"Time: 8.5 {mission} mission cancelled:",
            f"Time: 8.5  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} resource waiting stopped",
            f"Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} resource waiting stopped",
            f"Time: 8.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :{aircraft[0]},{aircraft[1]}",
        ])
        launch = arrival = None
    if launch is not None:
        required.extend([
            f"Time: {launch} {mission} mission starting, duration: 1 : {aircraft[0]},{aircraft[1]}",
            f"Time: {arrival} {mission} mission success:",
            f"Time: {arrival} {mission} mission completed: {aircraft[0]},{aircraft[1]}",
            f"Time: {arrival} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :{aircraft[0]},{aircraft[1]}",
        ])
    for fragment in required:
        checks.check(log.count(fragment) == 1, f"{arm} event {fragment}")
    checks.check(log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK") == (2 if capacity else 0), f"{arm} crew availability success count")
    checks.check(log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") == (0 if capacity == 2 else 1 if capacity == 1 else 2), f"{arm} crew availability failure count")
    checks.check(log.count("allocated to maintenance task: 1") == (2 if capacity else 0), f"{arm} exact booking count")
    checks.check(log.count("deallocated from  maintenance task: 1") == (2 if capacity else 0), f"{arm} exact release count")
    checks.check(log.count("starts performing, planned to last for 0.5 hours") == (2 if capacity else 0), f"{arm} exact work count")
    checks.check(log.count("resource waiting stopped") == (2 if capacity == 0 else 0), f"{arm} stopped waits")
    checks.check(log.count("mission starting, duration: 1") == int(capacity > 0), f"{arm} launch count")
    checks.check(log.count("mission success:") == int(capacity > 0), f"{arm} mission success notices")
    checks.check(log.count("mission cancelled:") == int(capacity == 0), f"{arm} cancellation count")
    if capacity == 1:
        checks.check(log.find("Time: 8  <P-CREW at <BASE-01,0>> deallocated") < log.find("Time: 8  <P-CREW at <BASE-01,0>> allocated"), f"{arm} release before regrant")
        checks.check(log.find("Time: 8  subtask 1 seqno 1") < log.find(f"Time: 8.5 {mission} mission starting"), f"{arm} aircraft1 work before formation launch")


def check_h8_order(checks: Checks, run: Path):
    log = (run / "model.log").read_text(errors="replace")
    fragments = [
        "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
        "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> frees resources",
        "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "Time: 8 <BASE-01,0> trig missions and tasks waiting for resources",
        "  Tasks waiting for resources at: <BASE-01,0> 1",
        "  < subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1>, C, 0.5>",
        "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource availability test",
        "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
        "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> resource received",
        "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> books resources",
        "Time: 8  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
        "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours",
    ]
    cursor = 0
    for fragment in fragments:
        position = log.find(fragment, cursor)
        checks.check(position >= cursor, f"staffing_1 ordered h8 {fragment}")
        if position >= cursor:
            cursor = position + len(fragment)
    checks.check(log.count("Time: 8  <P-CREW at <BASE-01,0>> deallocated") == 1, "one h8 release")
    checks.check(log.count("Time: 8  <P-CREW at <BASE-01,0>> allocated") == 1, "one h8 regrant")


def main():
    checks = Checks()
    contract_path = CASE / "contract.json"
    contract = read_json(contract_path)
    contract_sha = "5c441afe4cd33bfda4a955e4df90bff442b923a40d7e3981692be609a748ba05"
    checks.check(sha(contract_path) == contract_sha, "frozen C03.var02 contract")
    checks.check(sha(CASE / "review/independent-contract-2026-10-07.md") == "2adbab57984b3ef79ae5292b40710e2c9d37423260de092f0173952cdb80d627", "independent contract review")
    source_pins = contract["accepted_source"]
    for relative, key in (
        ("contract.json", "contract"),
        ("evidence-2026-09-29.md", "evidence_report"),
        ("review/independent-readonly-2026-09-29.json", "original_independent_review"),
    ):
        path = SOURCE / relative
        expected = source_pins[key]
        checks.check(path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"], f"accepted C03 {relative}")
    parent = CASE.parent / contract["published_staffing_parent"]["package"]
    for relative, key in (
        ("contract.json", "contract"),
        ("evidence-index.json", "evidence_index"),
        ("cli-scope-signoff-2026-10-07.md", "scope_signoff"),
        ("review/independent-verdict.json", "independent_verdict"),
    ):
        path = parent / relative
        expected = contract["published_staffing_parent"][key]
        checks.check(path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"], f"published C03.var01 {relative}")
    tracked = subprocess.run(
        ["git", "ls-files", "--", SOURCE.relative_to(REPO).as_posix()],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    expected_sources = {item["path"]: item for item in source_pins["published_source_files"]}
    checks.check(len(tracked) == len(expected_sources) == 16, "16 accepted source identities")
    for relative in tracked:
        local = REPO / relative
        name = local.relative_to(SOURCE).as_posix()
        checks.check(name in expected_sources, f"listed accepted source {name}")
        if name not in expected_sources:
            continue
        record = expected_sources[name]
        blob = git_blob(local)
        checks.check(local.stat().st_size == record["local_disk"]["bytes"] and sha(local) == record["local_disk"]["sha256"], f"local source {name}")
        checks.check(blob is not None and len(blob) == record["published_git"]["bytes"] and sha_bytes(blob) == record["published_git"]["sha256"], f"Git source {name}")
        checks.check(blob == local.read_bytes() or name == ".gitignore" and local.read_bytes().replace(b"\r\n", b"\n") == blob, f"source byte relation {name}")
    checks.check(sha(Path(contract["manual"]["installed_pdf_path"])) == contract["manual"]["installed_pdf_sha256"], "installed manual")
    source_models = {}
    report_tables = {}
    run_info = {}
    gui_identity = None
    for arm, (source_file, run_id) in RUNS.items():
        role = "one_crew" if arm == "staffing_1" else "two_crew"
        pin = source_pins["arms"][role]
        run = RAW / run_id
        closure = read_json(run / "closure.json")
        invocation = read_json(run / "invocation.json")
        checks.check(run_id == pin["run_id"] and str(run) == pin["raw_location"], f"{arm} original run")
        for label, path, key in (
            ("input", source_file, "input"),
            ("closure", run / "closure.json", "closure"),
            ("invocation", run / "invocation.json", "invocation"),
            ("model log", run / "model.log", "model_log"),
            ("report", run / "report-raw.json", "report_raw"),
        ):
            expected = pin[key]
            checks.check(path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"], f"{arm} {label} pin")
        checks.check(closure["run_id"] == run_id and len(closure["raw"]) == len(pin["raw"]) == 11, f"{arm} closure 11 raw")
        checks.check(sha(run / "invocation.json") == closure["invocation_sha256"] and closure["input_sha256"] == sha(source_file), f"{arm} closure provenance")
        checks.check(invocation["input_sha256"] == sha(source_file) and invocation["contract_sha256"] == sha(SOURCE / "contract.json"), f"{arm} invocation source")
        for name, seal in sorted(pin["raw"].items()):
            file = run / name
            checks.check(
                name in closure["raw"] and closure["raw"][name] == seal
                and file.is_file() and file.stat().st_size == seal["bytes"] and sha(file) == seal["sha256"],
                f"{arm} raw seal {name}",
            )
        checks.check((run / "input.json").read_bytes() == source_file.read_bytes(), f"{arm} exact native input copy")
        checks.check(
            invocation["session_id"] == 0 and invocation["ssh_connection_present"]
            and "sshd.exe" in invocation["ssh_ancestor_names"]
            and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue",
            f"{arm} SSH0 and mutex",
        )
        gui = invocation["coexisting_gui"]
        identity = (gui["pid"], gui["session_id"], gui["process_start_utc"])
        checks.check(gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"], f"{arm} preserved GUI")
        if gui_identity is None:
            gui_identity = identity
        else:
            checks.check(identity == gui_identity, f"{arm} same GUI identity")
        stages = read_json(run / "steps.json")
        checks.check([step["name"] for step in stages] == ["import", "export", "calc", "jsonreport"], f"{arm} four native steps")
        for step in stages:
            checks.check(step["exit_code"] == 0 and step["coexisting_gui_present_after"], f"{arm} guarded {step['name']}")
        calc = (run / "run.log").read_text(errors="replace").lower()
        checks.check("errors: 0" in calc and "warnings: 2" in calc and "notes: 0" in calc
                     and "warning #108" in calc and "warning #126" in calc, f"{arm} converter set")
        checks.check((run / "model.sxo").stat().st_size > 4, f"{arm} usable SXO")
        model = read_json(source_file)["model"]
        source_models[arm] = model
        authored = tables(model)
        exported = tables(native_json(run / "roundtrip-raw.json")["model"])
        checks.check(set(authored) == set(exported) and len(authored) == 31, f"{arm} 31 table schema")
        checks.check(sum(bool(rows(table)) for table in authored.values()) == 20
                     and sum(any(any(value is not None for value in row) for row in rows(table)) for table in authored.values()) == 17,
                     f"{arm} 20 row-containing/17 value-bearing")
        for name, table in authored.items():
            native = exported[name]
            checks.check([c["name"] for c in table["columns"]] == [c["name"] for c in native["columns"]], f"{arm} roundtrip columns {name}")
            checks.check(len(native["instances"]) >= len(table["instances"]), f"{arm} roundtrip instances {name}")
            for before, after in zip(table["instances"], native["instances"]):
                checks.check(before.get("instance_name") == after.get("instance_name"), f"{arm} instance name {name}")
                checks.check(len(after["rows"]) >= len(before["rows"])
                             and all(all(value is None for value in row) for row in after["rows"][len(before["rows"]):]),
                             f"{arm} only empty native-added rows {name}")
                for source_row, native_row in zip(before["rows"], after["rows"]):
                    for index, value in enumerate(source_row):
                        checks.check(value == native_row[index], f"{arm} roundtrip {name} cell {index}")
        check_events(checks, arm, run)
        report_tables[arm] = check_report(checks, arm, model, native_json(run / "report-raw.json"))
        run_info[arm] = {"run_id": run_id, "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"])}
    check_h8_order(checks, RAW / RUNS["staffing_1"][1])
    left = tables(source_models["staffing_1"])
    right = tables(source_models["staffing_2"])
    differences = []
    checks.check(set(left) == set(right), "paired source table set")
    for name, table in left.items():
        other = right[name]
        checks.check(table["columns"] == other["columns"] and len(table["instances"]) == len(other["instances"]), f"paired schema {name}")
        for instance_index, (before, after) in enumerate(zip(table["instances"], other["instances"])):
            checks.check(before.get("instance_name") == after.get("instance_name") and len(before["rows"]) == len(after["rows"]), f"paired instance {name}")
            for row_index, (lrow, rrow) in enumerate(zip(before["rows"], after["rows"])):
                for column_index, (lval, rval) in enumerate(zip(lrow, rrow)):
                    if lval != rval:
                        differences.append((name, instance_index, row_index, table["columns"][column_index]["name"], lval, rval))
    checks.check(differences == [("ResourceAllocation", 0, 0, "RQTY", 1, 2)], f"sole source cell {differences}")
    counts = {}
    for name in report_tables["staffing_1"]:
        a = report_tables["staffing_1"][name]
        b = report_tables["staffing_2"][name]
        left_rows, right_rows = rows(a), rows(b)
        checks.check(a["columns"] == b["columns"] and len(left_rows) == len(right_rows), f"report shape pair {name}")
        count = 0
        for row_index, (lrow, rrow) in enumerate(zip(left_rows, right_rows)):
            for column_index, (lval, rval) in enumerate(zip(lrow, rrow)):
                same = equal(lval, rval)
                count += int(not same)
                checks.check(same if name in ("ProblemDescription", "ResultSummary", "StockTotalResults") else True,
                             f"paired invariant {name} {row_index} {column_index}")
        counts[name] = count
    checks.check(counts == {
        "ProblemDescription": 0, "ResultSummary": 0, "SystemResults": 12,
        "StockTotalResults": 0, "ResourceResults": 219, "ResourceResultsTotal": 4,
    }, f"exact report difference counts {counts}")
    cells = {arm: sum(len(rows(table)) * len(table["columns"]) for table in report_tables[arm].values()) for arm in RUNS}
    checks.check(all(value == 5210 for value in cells.values()), "5210 report cells per arm")
    result = {
        "schema": "simlox-c03-var02-author-readonly-reclassification/v1",
        "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
        "checks_passed": checks.count - len(checks.failures),
        "checks_total": checks.count,
        "failures": checks.failures,
        "contract_sha256": sha(contract_path),
        "runs": run_info,
        "raw_seals": sum(item["raw_seals"] for item in run_info.values()),
        "report_cells_each": cells,
        "report_difference_counts": counts,
        "new_native_run_count": 0,
        "scope": "Two accepted fixed-seed C03 CLI runs, with one-crew h8 release/retest/regrant/work and a two-crew control.",
        "limits": "The logged same-time order is source-bound; no general scheduling, fairness, priority, deadline, GUI or cross-engine claim.",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": checks.count, "failures": checks.failures[:25]}, indent=2))


if __name__ == "__main__":
    main()