"""Independent, standard-library, read-only replay of accepted C03 staffing runs.

No SIMLOX invocation, author validator import, or mutation of accepted evidence.
The only write is this review directory's deterministic LF verdict.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parents[2]
ACCEPTED = REPO / "cases/simlox-air-support/C03-shared-crew-formation-v1.0.2"
RUNS = Path(
    r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support"
    r"\C03-shared-crew-formation-v1.0.2\runs"
)
EXPECTED_CONTRACT = "652f886c5d22eaaa20f605812695055586af81209b99682d357112a8c903043f"
OLD_CONTRACT = "cc0d43a522d2aa94608db9755bb1539f1ede7d220427a796ae66fca38e8b2428"
OLD_NO_GO = "56c51d69301a8bc0056b1f51e971d8aea2fb262ecb66413d4434a1f980bdce1d"
ACCEPTED_REVIEW = ACCEPTED / "review/independent-readonly-2026-09-29.json"
FAILURES = []
CHECKS = 0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(value, label):
    global CHECKS
    CHECKS += 1
    if not value:
        FAILURES.append(label)


def equal(a, b):
    if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
        return abs(a - b) <= 1e-6
    return a == b


def check_eq(a, b, label):
    check(equal(a, b), f"{label}: {a!r} != {b!r}")


def read_json(path, normalize=False):
    text = path.read_text(encoding="utf-8-sig")
    if normalize:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(document, root):
    return {t["name"]: t for t in document[root]["tables"]}


def columns(table):
    return [column["name"] for column in table["columns"]]


def rows(table):
    return [(instance.get("instance_name", ""), row) for instance in table["instances"] for row in instance["rows"]]


def one_row(table):
    data = rows(table)
    check_eq(len(data), 1, table["name"] + " one row")
    return dict(zip(columns(table), data[0][1]))


def git_bytes(relative):
    result = subprocess.run(
        ["git", "show", "HEAD:" + relative.as_posix()],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    return result.stdout


def event(log, hour, fragment, label, count=1):
    matches = [i for i, line in enumerate(log) if line.startswith(f"Time: {hour} ") and fragment in line]
    check_eq(len(matches), count, label)
    return matches[0] if matches else -1


def report_cell(actual, expected, label):
    check_eq(actual, expected, label)


def check_report(name, capacity, report):
    expected_names = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]
    check_eq(list(report), expected_names, f"{name} report table order")
    shapes = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11), "SystemResults": (72, 40),
              "StockTotalResults": (72, 16), "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
    cell_count = 0
    for table_name, (nr, nc) in shapes.items():
        t = report[table_name]
        check_eq(len(columns(t)), nc, f"{name} {table_name} columns")
        check_eq(len(rows(t)), nr, f"{name} {table_name} rows")
        check_eq(len(t["instances"]), 1, f"{name} {table_name} instances")
        cell_count += nr * nc
    check_eq(cell_count, 5210, f"{name} report cells")

    description = one_row(report["ProblemDescription"])
    report_cell(description["PDESC"], "C03 two-aircraft shared-crew formation; no J35/F35 equivalence", f"{name} description")
    summary = one_row(report["ResultSummary"])
    positive = capacity > 0
    summary_expect = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": int(positive), "RSMTMF": 0,
                      "MSTF": int(positive), "RSMSTF": 0, "MSUF": int(positive), "RSMSUF": 0,
                      "STMF": int(positive), "RSSTMF": 0}
    for column in columns(report["ResultSummary"]):
        report_cell(summary[column], summary_expect[column], f"{name} ResultSummary.{column}")

    # Every SystemResults cell is rebuilt from the observed preparation, mission,
    # cancellation and return windows. Unlisted measures are exactly zero; SYDT is null.
    system = report["SystemResults"]
    syscols = columns(system)
    for i, (_, raw) in enumerate(rows(system)):
        h = i / 2
        expected = {c: 0 for c in syscols}
        expected.update(UNID="Total over all Units", SID="Total over all Systems", STINT=h,
                        ETINT=h + 0.5, NSYA=2, SYDT=None)
        if h < 7.5 or h >= ({2: 9, 1: 9.5, 0: 8.5}[capacity]):
            expected["NSYRY"] = 2
        else:
            expected["NSYMA"] = 2
            if capacity == 2:
                expected["NSYMP" if h == 7.5 else "NSYMO"] = 2
            elif capacity == 1:
                if h == 7.5:
                    expected["NSYMP"] = 2
                elif h == 8:
                    expected["NSYMP"] = 1
                    expected["NSYMR"] = 1
                else:
                    expected["NSYMO"] = 2
            else:
                expected["NSYMP"] = 2
        if capacity > 0 and {2: 8, 1: 8.5}[capacity] <= h < {2: 9, 1: 9.5}[capacity]:
            expected["FTMO"] = 1
            expected["STACC"] = 2
        if h == 7.5:
            expected["NPSTA"] = 2
        if capacity == 2 and h == 8:
            expected["NPSUC"] = 2
        if capacity == 1 and h in (8, 8.5):
            expected["NPSUC"] = 1
        for c, value in zip(syscols, raw):
            report_cell(value, expected[c], f"{name} SystemResults[{i}].{c}")

    stock = report["StockTotalResults"]
    stockcols = columns(stock)
    for i, (_, raw) in enumerate(rows(stock)):
        expected = {c: 0 for c in stockcols}
        expected.update(STINT=i / 2, ETINT=(i + 1) / 2, PNB=1)
        for c in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected[c] = None
        for c, value in zip(stockcols, raw):
            report_cell(value, expected[c], f"{name} StockTotalResults[{i}].{c}")

    resource = report["ResourceResults"]
    rescols = columns(resource)
    busy_integral = 0.0
    wait_integral = 0.0
    for i, (_, raw) in enumerate(rows(resource)):
        h = i / 2
        busy = 2 if capacity == 2 and h == 7.5 else (1 if capacity == 1 and h in (7.5, 8) else 0)
        wait = 1 if capacity == 1 and h == 7.5 else (2 if capacity == 0 and h in (7.5, 8) else 0)
        busy_integral += busy * 0.5
        wait_integral += wait * 0.5
        expected = {c: 0 for c in rescols}
        expected.update(RID="Total over all Resources", STID="Total over all Stations", STINT=h,
                        ETINT=h + 0.5, NR=capacity, NRUM=busy, NRW=wait, NRA=capacity, NRN=capacity)
        for c, value in zip(rescols, raw):
            report_cell(value, expected[c], f"{name} ResourceResults[{i}].{c}")
    check_eq(busy_integral, 1 if capacity else 0, f"{name} crew person-hours")
    check_eq(wait_integral, {2: 0, 1: 0.5, 0: 2}[capacity], f"{name} request wait hours")
    total = one_row(report["ResourceResultsTotal"])
    total_expect = {c: 0 for c in columns(report["ResourceResultsTotal"])}
    total_expect.update(RID="Total over all Resources", STID="Total over all Stations", NR=capacity,
                        NRUM=busy_integral / 36, NRW=wait_integral / 36, NRA=capacity, NRN=capacity)
    for c in columns(report["ResourceResultsTotal"]):
        report_cell(total[c], total_expect[c], f"{name} ResourceResultsTotal.{c}")
    return cell_count


def check_events(name, capacity, text):
    lines = text.splitlines()
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    event(lines, "7.5", mission + " mission created", f"{name} mission created")
    event(lines, "7.5", mission + " mission activated, systems requested: 2", f"{name} mission activated")
    lease_markers = {}
    for aircraft in (0, 1):
        ident = f"<TEACH-AIR-01,{aircraft}>"
        task = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on {ident}"
        event(lines, "7.5", "mission allocates system: " + ident, f"{name} allocate {aircraft}")
        event(lines, "7.5", ident + " preparation started", f"{name} preparation {aircraft}")
        event(lines, "7.5", task + " requests resources", f"{name} request {aircraft}")
        if capacity == 2 or (capacity == 1 and aircraft == 0):
            start = "7.5"
        elif capacity == 1:
            start = "8"
        else:
            start = None
        if start is not None:
            end = "8" if start == "7.5" else "8.5"
            booked = event(lines, start, task + " books resources", f"{name} book {aircraft}")
            perform = event(lines, start, task + " starts performing, planned to last for 0.5 hours", f"{name} work {aircraft}")
            released = event(lines, end, task + " frees resources", f"{name} release {aircraft}")
            lease_markers[aircraft] = (booked, released)
            event(lines, end, task + " completed", f"{name} subtask complete {aircraft}")
            check_eq(sum(line.startswith(f"Time: {end}  system preparation task {aircraft} on {ident} completed")
                         for line in lines), 1, f"{name} task complete {aircraft}")
            check(booked < perform < released, f"{name} lease order {aircraft}")
        else:
            event(lines, "8.5", task + " resource waiting stopped", f"{name} wait stop {aircraft}")
    test_lines = [line for line in lines if "Availability test on  <P-CREW at <BASE-01,0>> request for: 1" in line]
    check_eq(sum(" OK" in line for line in test_lines), {2: 2, 1: 2, 0: 0}[capacity], f"{name} successful availability tests")
    check_eq(sum(" failed" in line for line in test_lines), {2: 0, 1: 1, 0: 2}[capacity], f"{name} failed availability tests")
    check_eq(sum(" books resources" in line for line in lines), 2 if capacity else 0, f"{name} booking count")
    check_eq(sum(" frees resources" in line for line in lines), 2 if capacity else 0, f"{name} release count")
    if capacity == 1:
        check(lease_markers[0][1] < lease_markers[1][0], f"{name} release before regrant")
    if capacity:
        launch = "8" if capacity == 2 else "8.5"
        finish = "9" if capacity == 2 else "9.5"
        event(lines, launch, mission + " mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", f"{name} launch")
        event(lines, finish, mission + " mission success", f"{name} success")
        event(lines, finish, mission + " mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", f"{name} completion")
        check_eq(sum("mission cancelled:" in line for line in lines), 0, f"{name} no cancel")
    else:
        event(lines, "8.5", mission + " mission cancelled", f"{name} cancellation")
        check_eq(sum("mission starting, duration" in line for line in lines), 0, f"{name} no launch")
        check_eq(sum(" starts performing" in line for line in lines), 0, f"{name} no work")
        finish = "8.5"
    for aircraft in (0, 1):
        event(lines, finish, f"<TEACH-AIR-01,{aircraft}> nbr ready increased", f"{name} ready return {aircraft}")
    check_eq(sum("mission ordered: BASIC-MISSION" in line for line in lines), 1, f"{name} one mission")


def run():
    check_eq(sha(CASE / "contract.json"), EXPECTED_CONTRACT, "corrected contract seal")
    check_eq(sha(CASE.parent / "C03-var01-staffing-v0.1.0/contract.json"), OLD_CONTRACT, "excluded contract seal")
    check_eq(sha(CASE.parent / "C03-var01-staffing-v0.1.0/review/independent-contract-2026-10-07.md"), OLD_NO_GO, "excluded NO_GO seal")
    contract = read_json(CASE / "contract.json")
    source = contract["accepted_source"]
    for path, key in [(ACCEPTED / "contract.json", "contract_sha256"),
                      (ACCEPTED / "evidence-2026-09-29.md", "evidence_report_sha256"),
                      (ACCEPTED_REVIEW, "original_independent_report_sha256")]:
        check_eq(sha(path), source[key], f"accepted {key}")
    for path, digest in [(REPO / "cases/simlox-air-support/C02-joint-resources-v1.0.2/inputs/single-both.json", contract["catalog"]["prerequisite_source_inputs"]["C02_single_both_sha256"]),
                         (REPO / "cases/simlox-air-support/A03-two-aircraft-formation-v1.0.1/native-input.json", contract["catalog"]["prerequisite_source_inputs"]["A03_formation_sha256"])]:
        check(path.is_file(), f"prerequisite exists {path}")
        if path.is_file():
            check_eq(sha(path), digest, f"prerequisite {path.name}")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    check_eq(sha(manual), contract["manual"]["installed_pdf_sha256"], "installed manual seal")

    rel = Path("cases/simlox-air-support/C03-shared-crew-formation-v1.0.2")
    tracked = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD", "--", rel.as_posix()],
                             cwd=REPO, stdout=subprocess.PIPE, check=True).stdout.decode().splitlines()
    check_eq(len(tracked), source["published_source_file_count"], "published source count")
    dual = source["published_local_byte_exception"]
    for name in tracked:
        local = REPO / name
        published = git_bytes(Path(name))
        if local.name == dual["path"]:
            check_eq(len(local.read_bytes()), dual["local_crlf_bytes"], "local .gitignore size")
            check_eq(sha(local), dual["local_sha256"], "local .gitignore SHA")
            check_eq(len(published), dual["published_git_lf_bytes"], "Git .gitignore size")
            check_eq(hashlib.sha256(published).hexdigest(), dual["published_git_sha256"], "Git .gitignore SHA")
        else:
            check_eq(local.read_bytes(), published, f"published source {name}")

    inputs = {}
    reports = {}
    report_cells = 0
    for capacity in (2, 1, 0):
        name = f"staffing_{capacity}"
        arm = source["arms"][name]
        input_path = ACCEPTED / arm["input"]
        directory = RUNS / arm["run_id"]
        check_eq(sha(input_path), arm["input_sha256"], f"{name} input SHA")
        check_eq(sha(directory / "closure.json"), arm["closure_sha256"], f"{name} closure SHA")
        closure = read_json(directory / "closure.json")
        check_eq(closure["run_id"], arm["run_id"], f"{name} closure ID")
        check_eq(closure["input_sha256"], arm["input_sha256"], f"{name} closure input")
        check_eq(len(closure["raw"]), 11, f"{name} raw count")
        for filename, seal in closure["raw"].items():
            path = directory / filename
            check_eq(path.stat().st_size, seal["bytes"], f"{name} {filename} bytes")
            check_eq(sha(path), seal["sha256"], f"{name} {filename} SHA")
        invocation = read_json(directory / "invocation.json")
        check_eq(sha(directory / "invocation.json"), closure["invocation_sha256"], f"{name} invocation SHA")
        check_eq(invocation["run_id"], arm["run_id"], f"{name} invocation run")
        check_eq(invocation["input_sha256"], arm["input_sha256"], f"{name} invocation input")
        check_eq(invocation["contract_sha256"], source["contract_sha256"], f"{name} invocation contract")
        check_eq(invocation["session_id"], 0, f"{name} SSH session")
        check("sshd.exe" in invocation["ssh_ancestor_names"], f"{name} sshd ancestry")
        check_eq(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue", f"{name} host mutex")
        gui = invocation["coexisting_gui"]
        for key, expected in [("pid", 13340), ("session_id", 1), ("process_start_utc", "2026-09-28T10:09:56.8261381Z"), ("responding_at_preflight", True)]:
            check_eq(gui[key], expected, f"{name} GUI {key}")
        steps = read_json(directory / "steps.json")
        check_eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport"], f"{name} step order")
        for step in steps:
            check_eq(step["exit_code"], 0, f"{name} {step['name']} exit")
            check_eq(step["coexisting_gui_present_after"], True, f"{name} {step['name']} GUI")
        runlog = (directory / "run.log").read_text()
        check_eq(sorted(re.findall(r"\(warning #(\d+)\)", runlog)), ["108", "126"], f"{name} warnings")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{name} converter summary")
        check_eq(re.findall(r"\(error #\d+\)", runlog), [], f"{name} no errors")
        check((directory / "model.sxo").stat().st_size > 1000, f"{name} valid output")
        check_eq((directory / "input.json").read_bytes(), input_path.read_bytes(), f"{name} native input copy")

        authored = tables(read_json(input_path), "model")
        exported = tables(read_json(directory / "roundtrip-raw.json", normalize=True), "model")
        check_eq(list(exported), list(authored), f"{name} table names roundtrip")
        populated = [key for key, value in authored.items() if rows(value)]
        check_eq(len(populated), 20, f"{name} authored populated tables")
        for table_name in set(authored) - set(populated):
            for instance, raw in rows(exported[table_name]):
                check(all(value is None for value in raw), f"{name} {table_name} optional null placeholder {instance}")
        for table_name in populated:
            a, e = authored[table_name], exported[table_name]
            ec = columns(e)
            for col in columns(a):
                check(col in ec, f"{name} {table_name}.{col} exported")
            for definition in a["columns"]:
                exported_definition = next((item for item in e["columns"] if item["name"] == definition["name"]), {})
                check_eq(exported_definition.get("datatype"), definition["datatype"], f"{name} {table_name}.{definition['name']} datatype")
            ar, er = rows(a), rows(e)
            check_eq(len(ar), len(er), f"{name} {table_name} row count")
            for rownum, ((ai, av), (ei, ev)) in enumerate(zip(ar, er)):
                check_eq(ai, ei, f"{name} {table_name}[{rownum}] instance")
                mapped = dict(zip(ec, ev))
                for col, value in zip(columns(a), av):
                    check_eq(mapped[col], value, f"{name} {table_name}[{rownum}].{col} roundtrip")
        inputs[capacity] = authored

        log = (directory / "model.log").read_text()
        check_events(name, capacity, log)
        reports[capacity] = tables(read_json(directory / "report-raw.json", normalize=True), "report")
        report_cells += check_report(name, capacity, reports[capacity])

    check_eq(report_cells, 15630, "all report cells")
    names = list(inputs[2])
    check_eq(list(inputs[1]), names, "source table names staff1")
    check_eq(list(inputs[0]), names, "source table names staff0")
    changes = []
    for table_name in names:
        cols = columns(inputs[2][table_name])
        for capacity in (1, 0):
            check_eq(inputs[capacity][table_name]["columns"], inputs[2][table_name]["columns"], f"source {table_name} columns {capacity}")
            check_eq([instance.get("instance_name", "") for instance in inputs[capacity][table_name]["instances"]],
                     [instance.get("instance_name", "") for instance in inputs[2][table_name]["instances"]],
                     f"source {table_name} instances {capacity}")
            check_eq(len(rows(inputs[capacity][table_name])), len(rows(inputs[2][table_name])), f"source {table_name} rows {capacity}")
        for index, (_, baseline) in enumerate(rows(inputs[2][table_name])):
            for colidx, col in enumerate(cols):
                values = (baseline[colidx], rows(inputs[1][table_name])[index][1][colidx], rows(inputs[0][table_name])[index][1][colidx])
                if not (equal(values[0], values[1]) and equal(values[1], values[2])):
                    changes.append((table_name, index, col, values))
    check_eq(changes, [("ResourceAllocation", 0, "RQTY", (2, 1, 0))], "sole shared P-CREW RQTY source delta")
    allocation = one_row(inputs[2]["ResourceAllocation"])
    for field, expected in [("POINT", "AIR_BASIC"), ("RID", "P-CREW"), ("STID", "BASE-01")]:
        check_eq(allocation[field], expected, f"shared allocation {field}")
    stocks = [reports[c]["StockTotalResults"]["instances"][0]["rows"] for c in (2, 1, 0)]
    check_eq(stocks[0], stocks[1], "stock staff2/staff1 equality")
    check_eq(stocks[1], stocks[2], "stock staff1/staff0 equality")
    return {
        "schema": "c03-var01-independent-readonly/v1",
        "decision": "GO_BOUNDED" if not FAILURES else "NO_GO",
        "checks": CHECKS,
        "failures": FAILURES,
        "contract_sha256": EXPECTED_CONTRACT,
        "accepted_raw_seals": 33,
        "report_cells_compared": report_cells,
        "scope": "Three accepted fixed-seed C03 CLI runs; no native rerun or general scheduling rule.",
    }


if __name__ == "__main__":
    result = run()
    output = HERE / "independent-verdict.json"
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"decision": result["decision"], "checks": result["checks"], "failures": len(result["failures"])}, sort_keys=True))
