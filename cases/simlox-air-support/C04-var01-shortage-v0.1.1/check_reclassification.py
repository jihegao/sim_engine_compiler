"""Author read-only classification of three accepted C04 shortage runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE
REPO = CASE.parents[2]
SOURCE = CASE.parent / "C04-deadline-cancellation-v1.0.0"
PARENT = CASE.parent / "C03-shared-crew-formation-v1.0.2"
RAW = SOURCE / "runs"
RUNS = {
    arm: (SOURCE / "inputs" / f"{arm}.json", f"c04-v100-{arm}-ssh-20260929-02")
    for arm in ("crew-equal", "aircraft-missing", "crew-zero")
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
    successful = arm == "crew-equal"
    aircraft_quantity = 1 if arm == "aircraft-missing" else 2
    crew_capacity = {"crew-equal": 1, "aircraft-missing": 2, "crew-zero": 0}[arm]
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
    completion = 9.5 if successful else 8.0
    prep_spans = ([(7.5, 8, 2), (8, 8.5, 1)] if successful
                  else [(7.5, 8, aircraft_quantity)])
    reserve_spans = [(8, 8.5, 1)] if successful else []
    flight_spans = [(8.5, 9.5, 2)] if successful else []
    prep_success_bins = {8: 1, 8.5: 1} if successful else ({8: 1} if arm == "aircraft-missing" else {})
    system = report_tables["SystemResults"]
    sys_columns = [column["name"] for column in system["columns"]]
    for index, row in enumerate(rows(system)):
        start, end = index / 2, (index + 1) / 2
        weighted = lambda spans: sum(qty * overlap(start, end, left, right) for left, right, qty in spans) / 0.5
        ready = weighted([(0, 7.5, aircraft_quantity), (completion, 36, aircraft_quantity)])
        prep = weighted(prep_spans)
        reserved = weighted(reserve_spans)
        flight = weighted(flight_spans)
        expected = {name: 0 for name in sys_columns}
        expected.update({"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": start,
                         "ETINT": end, "NSYA": aircraft_quantity, "SYDT": None,
                         "NSYRY": ready, "NSYMA": aircraft_quantity - ready,
                         "NSYMP": prep, "NSYMR": reserved, "NSYMO": flight, "FTMO": flight / 2,
                         "STACC": flight, "NPSTA": aircraft_quantity if start == 7.5 else 0,
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
        usage_end = 8.5 if successful else (8 if arm == "aircraft-missing" else 7.5)
        usage = overlap(start, end, 7.5, usage_end) / 0.5
        waiting_quantity = {"crew-equal": 1, "aircraft-missing": 0, "crew-zero": 2}[arm]
        waiting = waiting_quantity * overlap(start, end, 7.5, 8) / 0.5
        expected = {name: 0 for name in resource_columns}
        expected.update({"RID": "Total over all Resources", "STID": "Total over all Stations",
                         "STINT": start, "ETINT": end, "NR": crew_capacity, "NRA": crew_capacity,
                         "NRN": crew_capacity, "NRUM": usage, "NRW": waiting})
        for column, actual in zip(resource_columns, row):
            checks.check(equal(actual, expected[column]), f"{arm} Resource {index} {column}: {actual} vs {expected[column]}")
    total = report_tables["ResourceResultsTotal"]
    total_columns = [column["name"] for column in total["columns"]]
    expected_total = {name: 0 for name in total_columns}
    expected_total.update({"RID": "Total over all Resources", "STID": "Total over all Stations",
                           "NR": crew_capacity, "NRA": crew_capacity, "NRN": crew_capacity,
                           "NRUM": {"crew-equal": 1, "aircraft-missing": 0.5, "crew-zero": 0}[arm] / 36,
                           "NRW": {"crew-equal": 0.5, "aircraft-missing": 0, "crew-zero": 1}[arm] / 36})
    for column, actual in zip(total_columns, rows(total)[0]):
        checks.check(equal(actual, expected_total[column]), f"{arm} ResourceTotal {column}")
    return report_tables


def ordered(checks: Checks, label: str, log: str, fragments: list[str]):
    cursor = 0
    for fragment in fragments:
        position = log.find(fragment, cursor)
        checks.check(position >= cursor, f"{label} order {fragment}")
        if position >= cursor:
            cursor = position + len(fragment)


def check_events(checks: Checks, arm: str, run: Path):
    log = (run / "model.log").read_text(errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    aircraft = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")
    common = [
        f"Time: 7.5 {mission} mission created:",
        f"Time: 7.5 {mission} mission allocates system: {aircraft[0]}",
        f"Time: 7.5 {mission} mission allocates system: {aircraft[1]}",
        f"Time: 7.5 {aircraft[0]} preparation started, mission: {mission}",
        f"Time: 7.5 {aircraft[1]} preparation started, mission: {mission}",
        f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} requests resources",
        f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} starts performing, planned to last for 0.5 hours",
        f"Time: 7.5  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} requests resources",
        "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed",
    ]
    for fragment in common:
        checks.check(log.count(fragment) == 1, f"{arm} common event {fragment}")
    h8 = [
        f"Time: 8  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} completed",
        f"Time: 8  subtask 0 seqno 1 within system preparation task 0 on {aircraft[0]} frees resources",
        "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "Time: 8 <BASE-01,0> trig missions and tasks waiting for resources",
        "  Tasks waiting for resources at: <BASE-01,0> 1",
        f"  < subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]}, C, 0.5>",
        f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} resource availability test",
        "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
        f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} resource received",
        f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} books resources",
        "Time: 8  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
        f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} starts performing, planned to last for 0.5 hours",
    ]
    ordered(checks, arm + " h8", log, h8)
    checks.check(log.count("allocated to maintenance task: 1") == 2 and
                 log.count("deallocated from  maintenance task: 1") == 2, f"{arm} two physical leases/releases")
    checks.check(log.count("starts performing, planned to last for 0.5 hours") == 2, f"{arm} two task starts")
    if arm != "crew-after":
        h85 = [
            f"Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} completed",
            f"Time: 8.5  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} frees resources",
            "Time: 8.5  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            f"Time: 8.5 {aircraft[1]} preparation ended, mission: {mission}",
            f"Time: 8.5 {mission} mission starting, duration: 1 : {aircraft[0]},{aircraft[1]}",
            f"Time: 9.5 {mission} mission success:",
            f"Time: 9.5 {mission} mission completed: {aircraft[0]},{aircraft[1]}",
            f"Time: 9.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :{aircraft[0]},{aircraft[1]}",
        ]
        ordered(checks, arm + " equal/success", log, h85)
        checks.check(log.count("mission cancelled:") == 0 and log.count("mission starting, duration: 1") == 1,
                     f"{arm} launched without cancellation")
    else:
        h849 = [
            f"Time: 8.49 {mission} mission cancelled:",
            f"Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} ordered to stop",
            f"Time: 8.49  system preparation task 1 on {aircraft[1]} stopped",
            f"Time: 8.49 {aircraft[1]} preparation ended, mission: {mission}",
            f"Time: 8.49 {aircraft[1]} turnround started, mission: {mission} reduction factor: 0.98",
            f"Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} frees resources",
            "Time: 8.49  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
            f"Time: 8.49  subtask 1 seqno 1 within system preparation task 1 on {aircraft[1]} stopped",
            f"Time: 8.49 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :{aircraft[1]},{aircraft[0]}",
        ]
        ordered(checks, arm + " cancellation/cleanup", log, h849)
        checks.check(log.count("mission cancelled:") == 1 and log.count("mission starting, duration: 1") == 0
                     and log.count("mission success:") == 0, f"{arm} no launch/success")
        checks.check(log.count("subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> completed") == 0,
                     f"{arm} second preparation remains incomplete")


def check_shortage_events(checks: Checks, arm: str, run: Path):
    log = (run / "model.log").read_text(errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    a0, a1 = "<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"
    ordered(checks, arm + " mission", log, [
        "Time: 7.5 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        f"Time: 7.5 {mission} mission created:",
        f"Time: 7.5 {mission} mission activated, systems requested: 2",
        f"Time: 7.5 {mission} mission allocates system: {a0}",
        f"Time: 8 {mission} mission cancelled:",
    ])
    checks.check(log.count("mission cancelled:") == 1 and
                 log.count("mission starting, duration:") == 0 and
                 log.count("mission success:") == 0 and
                 log.count("mission completed:") == 0,
                 f"{arm} one cancellation and no launch/success")
    if arm == "aircraft-missing":
        ordered(checks, arm + " physical", log, [
            f"Time: 7.5 {mission} mission allocates system: {a0}",
            f"Time: 7.5 {a0} preparation started, mission: {mission}",
            f"Time: 7.5 {mission} mission waiting:  timeout at 8",
            "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
            f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {a0} books resources",
            f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {a0} starts performing, planned to last for 0.5 hours",
            f"Time: 8  subtask 0 seqno 1 within system preparation task 0 on {a0} completed",
            "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 2",
            f"Time: 8 {a0} preparation ended, mission: {mission}",
            f"Time: 8 {mission} mission cancelled:",
            f"Time: 8 {a0} turnround started, mission: {mission} reduction factor: 1",
            f"Time: 8 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{a0}",
        ])
        checks.check(a1 not in log, "missing arm no physical aircraft ID1")
        checks.check(log.count("allocated to maintenance task: 1") == 1 and
                     log.count("deallocated from  maintenance task: 1") == 1 and
                     log.count("starts performing, planned to last for 0.5 hours") == 1,
                     "missing arm one physical crew lease/work/release")
    else:
        ordered(checks, arm + " allocation/wait", log, [
            f"Time: 7.5 {mission} mission allocates system: {a0}",
            f"Time: 7.5 {mission} mission allocates system: {a1}",
            f"Time: 7.5 {a0} preparation started, mission: {mission}",
            f"Time: 7.5 {a1} preparation started, mission: {mission}",
            f"Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on {a0} resource availability test",
            "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed",
            f"Time: 7.5  subtask 1 seqno 1 within system preparation task 1 on {a1} resource availability test",
            "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed",
            f"Time: 8 {mission} mission cancelled:",
            f"Time: 8  subtask 0 seqno 1 within system preparation task 0 on {a0} ordered to stop",
            f"Time: 8  subtask 0 seqno 1 within system preparation task 0 on {a0} resource waiting stopped",
            f"Time: 8 {a0} turnround started, mission: {mission} reduction factor: 0",
            f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {a1} ordered to stop",
            f"Time: 8  subtask 1 seqno 1 within system preparation task 1 on {a1} resource waiting stopped",
            f"Time: 8 {a1} turnround started, mission: {mission} reduction factor: 0",
            f"Time: 8 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :{a0},{a1}",
        ])
        checks.check(log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") == 2,
                     "zero crew two failed availability tests")
        checks.check("allocated to maintenance task:" not in log and
                     "deallocated from  maintenance task:" not in log and
                     "starts performing, planned to last for 0.5 hours" not in log,
                     "zero crew no physical crew lease or work")


def flatten(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from flatten(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from flatten(child, path + (index,))
    else:
        yield path, value


def main():
    checks = Checks()
    contract_path = CASE / "contract.json"
    contract = read_json(contract_path)
    checks.check(sha(contract_path) == "eaddbcbb400107d3c8aa1f64151a04e85303448e3997efc4b22512db6b313191",
                 "corrected v0.1.1 contract")
    checks.check(sha(CASE / "review/independent-contract-go-2026-10-07.md") ==
                 "f306b54828e5427ef93bc5fc4d7adc26849413b1fc86b4c35470014173c6684d",
                 "independent contract GO")
    old = CASE.parent / "C04-var01-shortage-v0.1.0"
    checks.check(sha(old / "contract.json") == "0f9acd39449e62f205d61b4219229e5d4eb7a2992be4a098c420d66749723d3d",
                 "excluded v0.1.0 contract")
    checks.check(sha(old / "review/independent-contract-no-go-2026-10-07.md") ==
                 "4cf248f77eb0c9212c04b88778757d075ab85cd6890b364513a0545701ab9e15",
                 "excluded v0.1.0 NO_GO")
    accepted = contract["accepted_source"]
    for relative, key in (("contract.json", "contract"), ("evidence-2026-09-29.md", "evidence_report"),
                          ("review/independent-readonly-2026-09-29.json", "independent_review")):
        path = SOURCE / relative
        record = accepted[key]
        checks.check(path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"C04 source {relative}")
    tracked = subprocess.run(["git", "ls-files", "--", SOURCE.relative_to(REPO).as_posix()],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
    expected = {record["path"]: record for record in accepted["published_source_files"]}
    checks.check(len(tracked) == len(expected) == 25, "25 accepted C04 source files")
    for relative in tracked:
        path = REPO / relative
        name = path.relative_to(SOURCE).as_posix()
        checks.check(name in expected, f"C04 listed source {name}")
        if name not in expected:
            continue
        record = expected[name]
        blob = git_blob(path)
        checks.check(path.stat().st_size == record["local_disk"]["bytes"] and sha(path) == record["local_disk"]["sha256"],
                     f"C04 local source {name}")
        checks.check(blob is not None and len(blob) == record["published_git"]["bytes"]
                     and sha_bytes(blob) == record["published_git"]["sha256"],
                     f"C04 Git source {name}")
    parent = contract["direct_c03_parent"]
    for relative, key in (("contract.json", "contract"), ("evidence-2026-09-29.md", "evidence_report"),
                          ("review/independent-readonly-2026-09-29.json", "independent_review")):
        path = PARENT / relative
        record = parent[key]
        checks.check(path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"C03 parent {relative}")
    parent_input = REPO / parent["staffing_one_input"]["path"]
    checks.check(parent_input.stat().st_size == parent["staffing_one_input"]["bytes"]
                 and sha(parent_input) == parent["staffing_one_input"]["sha256"], "C03 parent staffing-one input")
    for role in ("staffing_zero_input", "staffing_two_input"):
        record = parent[role]
        path = REPO / record["path"]
        checks.check(path.stat().st_size == record["bytes"] and sha(path) == record["sha256"],
                     f"C03 parent {role}")
    parent_run = Path(parent["staffing_one_run"]["local_run_dir"])
    for key, name in (("closure", "closure.json"), ("invocation", "invocation.json")):
        record = parent["staffing_one_run"][key]
        path = parent_run / name
        checks.check(path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"C03 parent {name}")
    parent_closure = read_json(parent_run / "closure.json")
    checks.check(parent_closure["raw"] == parent["staffing_one_run"]["raw"]
                 and len(parent_closure["raw"]) == 11, "C03 parent closure raw map")
    for name, record in sorted(parent_closure["raw"].items()):
        path = parent_run / name
        checks.check(path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"C03 parent raw {name}")
    manual = contract["manual"]
    path = Path(manual["installed_pdf_path"])
    checks.check(path.stat().st_size == manual["installed_pdf"]["bytes"]
                 and sha(path) == manual["installed_pdf"]["sha256"], "installed manual pin")
    horizon = RAW / contract["excluded_evidence"]["horizon_wait"]["run_id"]
    record = contract["excluded_evidence"]["horizon_wait"]["run_log"]
    checks.check((horizon / "run.log").stat().st_size == record["bytes"]
                 and sha(horizon / "run.log") == record["sha256"]
                 and (horizon / "model.sxo").stat().st_size == 4, "excluded horizon-wait failure")
    source_models = {}
    report_tables = {}
    run_info = {}
    gui_identity = None
    for arm, (source_file, run_id) in RUNS.items():
        run = RAW / run_id
        pin = accepted["arms"][arm]
        closure = read_json(run / "closure.json")
        invocation = read_json(run / "invocation.json")
        checks.check(pin["run_id"] == run_id and pin["local_run_dir"] == str(run), f"{arm} final run")
        for label, path, key in (("input", source_file, "input"),
                                 ("parent diff", REPO / pin["parent_diff"]["path"], "parent_diff"),
                                 ("closure", run / "closure.json", "closure"),
                                 ("invocation", run / "invocation.json", "invocation"),
                                 ("model log", run / "model.log", "model_log"),
                                 ("report", run / "report-raw.json", "report_raw")):
            expected_seal = pin[key]
            checks.check(path.stat().st_size == expected_seal["bytes"] and sha(path) == expected_seal["sha256"],
                         f"{arm} {label}")
        checks.check(closure["run_id"] == run_id and closure["raw"] == pin["raw"]
                     and len(closure["raw"]) == 11 and sha(run / "invocation.json") == closure["invocation_sha256"],
                     f"{arm} closure and invocation")
        checks.check(closure["input_sha256"] == invocation["input_sha256"] == sha(source_file)
                     and invocation["contract_sha256"] == sha(SOURCE / "contract.json"),
                     f"{arm} original source/contract")
        for name, record in sorted(pin["raw"].items()):
            path = run / name
            checks.check(path.is_file() and path.stat().st_size == record["bytes"]
                         and sha(path) == record["sha256"], f"{arm} raw {name}")
        checks.check((run / "input.json").read_bytes() == source_file.read_bytes(), f"{arm} input copy")
        checks.check(invocation["session_id"] == 0 and invocation["ssh_connection_present"]
                     and "sshd.exe" in invocation["ssh_ancestor_names"]
                     and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{arm} SSH0/mutex")
        gui = invocation["coexisting_gui"]
        identity = (gui["pid"], gui["session_id"], gui["process_start_utc"])
        checks.check(gui["pid"] == 13340 and gui["session_id"] == 1 and gui["responding_at_preflight"],
                     f"{arm} GUI preflight")
        if gui_identity is None:
            gui_identity = identity
        else:
            checks.check(gui_identity == identity, f"{arm} same GUI identity")
        stages = read_json(run / "steps.json")
        checks.check([step["name"] for step in stages] == ["import", "export", "calc", "jsonreport"],
                     f"{arm} four steps")
        for step in stages:
            checks.check(step["exit_code"] == 0 and step["coexisting_gui_present_after"], f"{arm} {step['name']} guarded")
        calc = (run / "run.log").read_text(errors="replace").lower()
        checks.check("errors: 0" in calc and "warnings: 2" in calc and "notes: 0" in calc
                     and "warning #108" in calc and "warning #126" in calc, f"{arm} converter 0/2/0")
        checks.check((run / "model.sxo").stat().st_size > 4, f"{arm} valid SXO")
        source_json = read_json(source_file)
        model = source_json["model"]
        source_models[arm] = source_json
        authored = tables(model)
        exported = tables(native_json(run / "roundtrip-raw.json")["model"])
        checks.check(set(authored) == set(exported) and len(authored) == 31, f"{arm} 31 table names")
        checks.check(len(list(flatten(source_json))) == 979
                     and sum(len(row) for table in authored.values() for row in rows(table)) == 201,
                     f"{arm} 979 JSON leaves/201 row cells")
        for name, table in authored.items():
            native = exported[name]
            checks.check([c["name"] for c in table["columns"]] == [c["name"] for c in native["columns"]],
                         f"{arm} roundtrip columns {name}")
            checks.check(len(native["instances"]) >= len(table["instances"]), f"{arm} roundtrip instances {name}")
            for before, after in zip(table["instances"], native["instances"]):
                checks.check(before.get("instance_name") == after.get("instance_name"), f"{arm} roundtrip instance name {name}")
                checks.check(len(after["rows"]) >= len(before["rows"])
                             and all(all(value is None for value in row) for row in after["rows"][len(before["rows"]):]),
                             f"{arm} only native all-null added rows {name}")
                for source_row, native_row in zip(before["rows"], after["rows"]):
                    for index, value in enumerate(source_row):
                        checks.check(value == native_row[index], f"{arm} roundtrip {name} cell {index}")
        if arm == "crew-equal":
            check_events(checks, arm, run)
        else:
            check_shortage_events(checks, arm, run)
        report_tables[arm] = check_report(checks, arm, model, native_json(run / "report-raw.json"))
        run_info[arm] = {"run_id": run_id, "closure_sha256": sha(run / "closure.json"), "raw_seals": len(closure["raw"])}
    parent_inputs = {
        "crew-equal": parent["staffing_one_input"],
        "aircraft-missing": parent["staffing_two_input"],
        "crew-zero": parent["staffing_zero_input"],
    }
    for arm in RUNS:
        parent_flat = dict(flatten(read_json(REPO / parent_inputs[arm]["path"])))
        child_flat = dict(flatten(source_models[arm]))
        differences = [(path, parent_flat[path], value) for path, value in child_flat.items() if parent_flat[path] != value]
        changed = {(path, before, after) for path, before, after in differences}
        op_path = next(path for path, before, after in differences if before == 1.0 and after == 0.5)
        expected = {(op_path, 1.0, 0.5)}
        if arm == "aircraft-missing":
            deployment = tables(source_models[arm]["model"])["SystemDeployment"]
            qty_col = [c["name"] for c in deployment["columns"]].index("QTYPS")
            check_path = ("model", "tables", list(tables(source_models[arm]["model"])).index("SystemDeployment"),
                          "instances", 0, "rows", 0, qty_col)
            expected.add((check_path, 2, 1))
        checks.check(changed == expected, f"{arm} exact direct C03 parent delta {differences}")
        op = tables(source_models[arm]["model"])["OperationProfile"]
        columns = [column["name"] for column in op["columns"]]
        checks.check(rows(op)[0][columns.index("DTIM")] == 0.5
                     and rows(op)[0][columns.index("STIM")] == 8.0, f"{arm} operation cutoff")
    equal_flat = dict(flatten(source_models["crew-equal"]))
    for arm, expected_changes in (
        ("aircraft-missing", {("SystemDeployment", "QTYPS", 2, 1), ("ResourceAllocation", "RQTY", 1, 2)}),
        ("crew-zero", {("ResourceAllocation", "RQTY", 1, 0)}),
    ):
        current = dict(flatten(source_models[arm]))
        changes = []
        for path, value in current.items():
            if equal_flat[path] != value:
                table = source_models[arm]["model"]["tables"][path[2]]
                changes.append((table["name"], table["columns"][path[-1]]["name"], equal_flat[path], value))
        checks.check(set(changes) == expected_changes and len(changes) == len(expected_changes),
                     f"{arm} exact matched source delta {changes}")
    expected_counts = {
        "aircraft-missing": dict(zip(contract["report_gate"]["table_order"], [0, 4, 158, 0, 218, 5])),
        "crew-zero": dict(zip(contract["report_gate"]["table_order"], [0, 4, 16, 0, 219, 5])),
    }
    counts = {}
    for arm in ("aircraft-missing", "crew-zero"):
        counts[arm] = {}
        for name, base_table in report_tables["crew-equal"].items():
            candidate = report_tables[arm][name]
            left_rows, right_rows = rows(base_table), rows(candidate)
            checks.check(base_table["columns"] == candidate["columns"] and len(left_rows) == len(right_rows),
                         f"{arm} paired report shape {name}")
            count = 0
            for index, (left, right) in enumerate(zip(left_rows, right_rows)):
                for column, (x, y) in enumerate(zip(left, right)):
                    count += int(x != y)
                    if name in ("ProblemDescription", "StockTotalResults"):
                        checks.check(x == y, f"{arm} unchanged {name} {index} {column}")
            counts[arm][name] = count
        checks.check(counts[arm] == expected_counts[arm], f"{arm} report difference counts {counts[arm]}")
    cells = {arm: sum(len(rows(table)) * len(table["columns"]) for table in report_tables[arm].values())
             for arm in RUNS}
    checks.check(all(value == 5210 for value in cells.values()), "5210 report cells in each arm")
    result = {
        "schema": "simlox-c04-var01-author-readonly-reclassification/v1",
        "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
        "checks_passed": checks.count - len(checks.failures),
        "checks_total": checks.count,
        "failures": checks.failures,
        "contract_sha256": sha(contract_path),
        "runs": run_info,
        "accepted_raw_seals": sum(item["raw_seals"] for item in run_info.values()),
        "parent_raw_seals": len(parent_closure["raw"]),
        "report_cells_each": cells,
        "report_difference_counts_vs_crew_equal": counts,
        "new_native_run_count": 0,
        "scope": "Three reused fixed-seed C04 CLI runs: aircraft-missing and crew-zero shortages versus equal-cutoff positive control.",
        "limits": "Aircraft-missing changes QTYPS and RQTY jointly; no reason-code, universal deadline, GUI or cross-engine claim.",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "checks": checks.count, "failures": checks.failures[:25]}, indent=2))


if __name__ == "__main__":
    main()
