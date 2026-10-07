"""Independent, read-only C09.var03 replay. Uses only Python's standard library.

The expected report is constructed from source and event intervals. The tested
report is never used as its own expected value. Run without arguments to write
the deterministic verdict beside this script; --self-check runs in-memory
mutations of the comparator without touching accepted files.
"""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
import subprocess
import sys
import copy
from collections import defaultdict


HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = HERE.parents[3]
CONTRACT = PKG / "contract.json"
VERDICT = HERE / "independent-verdict.json"
GIT = "git"
AIR = re.compile(r"<TEACH-AIR-01,(\d+)>")
TIME = re.compile(r"^Time:\s*([0-9.]+)\s*(.*)$")
STEP = re.compile(r"subtask (\d+) seqno 1 within system (preparation|DIRP) task (\d+) on <TEACH-AIR-01,(\d+)>")
EXPECTED_COLUMNS = {
    "ProblemDescription": "PDESC".split(),
    "ResultSummary": "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF".split(),
    "SystemResults": "UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW SYDT SYDTU NSYDT NSYSW NPSTA NPSUC".split(),
    "StockTotalResults": "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT".split(),
    "ResourceResults": "RID STID STINT ETINT NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split(),
    "ResourceResultsTotal": "RID STID NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split(),
}


class ReviewFailure(Exception):
    pass


def digest(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def expect(ok: bool, msg: str) -> None:
    if not ok:
        raise ReviewFailure(msg)


def read_json(path: pathlib.Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: pathlib.Path) -> object:
    """Strip trailing commas outside JSON strings, preserving raw file bytes."""
    s = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for i, c in enumerate(s):
        if quoted:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
            out.append(c)
        elif c == ",":
            j = i + 1
            while j < len(s) and s[j].isspace():
                j += 1
            if j == len(s) or s[j] not in "]}":
                out.append(c)
        else:
            out.append(c)
    expect(not quoted, f"unterminated JSON string: {path}")
    return json.loads("".join(out))


def table_map(document: dict, wrapper: str) -> dict:
    tables = document[wrapper]["tables"]
    out = {t["name"]: t for t in tables}
    expect(len(out) == len(tables), "duplicate table name")
    return out


def matrix(table: dict) -> tuple[list[str], list[list]]:
    cols = [c["name"] for c in table["columns"]]
    expect(len(cols) == len(set(cols)), "duplicate column")
    expect(len(table["instances"]) == 1, "unexpected instance count")
    rows = table["instances"][0]["rows"]
    expect(all(len(row) == len(cols) for row in rows), "row width")
    return cols, rows


def source_row(tables: dict, name: str, row: int = 0) -> dict:
    cols, rows = matrix(tables[name])
    return dict(zip(cols, rows[row]))


def check_pin(path: pathlib.Path, pin: dict, label: str, checks: list[str]) -> None:
    expect(path.is_file(), f"missing {label}: {path}")
    expect(digest(path.read_bytes()) == pin, f"byte pin mismatch {label}: {path}")
    checks.append(label)


def check_sources(contract: dict, checks: list[str]) -> None:
    records = [contract["catalog"]["source"], contract["accepted_C09_var04"]["evidence_index"],
               contract["accepted_C09_var04"]["independent_verdict"]]
    records.extend(contract["accepted_C09_var04"]["source_files"].values())
    for parent in contract["prerequisites"].values():
        records.extend(parent["source_files"].values())
    expect(len(records) == 32, "expected 32 source records")
    for index, record in enumerate(records):
        path = (PKG / record["path"]).resolve()
        check_pin(path, record["local_disk"], f"source-disk-{index}", checks)
        try:
            rel = path.relative_to(ROOT).as_posix()
        except ValueError as exc:
            raise ReviewFailure(f"source outside repo {path}") from exc
        proc = subprocess.run([GIT, "show", "HEAD:" + rel], cwd=ROOT, capture_output=True)
        expect(proc.returncode == 0, f"published Git blob missing {rel}")
        expect(digest(proc.stdout) == record["published_git"], f"published Git blob mismatch {rel}")
        checks.append(f"source-git-{index}")
    old = contract["excluded_v010"]
    for label in ("frozen_contract", "independent_no_go"):
        record = old[label]
        check_pin((PKG / record["path"]).resolve(),
                  {"bytes": record["bytes"], "sha256": record["sha256"]}, label, checks)
    expect(old["native_runs"] == 0 and old["classification"] == "NO_GO_CONTRACT", "excluded v010 scope")


def run_records(contract: dict) -> dict[str, dict]:
    records = dict(contract["accepted_C09_var04"]["accepted_runs"])
    for name, parent in contract["prerequisites"].items():
        records[name] = parent["accepted_run"]
    return records


def check_runs(contract: dict, checks: list[str]) -> dict[str, pathlib.Path]:
    records = run_records(contract)
    expect(len(records) == 6, "six accepted runs")
    dirs = {}
    for arm, record in records.items():
        run = (PKG / record["path"]).resolve()
        dirs[arm] = run
        check_pin(run / "closure.json", record["closure"], f"closure-{arm}", checks)
        check_pin(run / "invocation.json", record["invocation"], f"invocation-{arm}", checks)
        expect(len(record["raw"]) == record["raw_count"], f"raw count {arm}")
        for name, pin in record["raw"].items():
            check_pin(run / name, pin, f"raw-{arm}-{name}", checks)
        closure = read_json(run / "closure.json")
        invocation = read_json(run / "invocation.json")
        expect(closure["invocation_sha256"] == record["invocation"]["sha256"], f"closure invocation {arm}")
        if arm in ("local", "remote", "remote-disabled"):
            expect(closure["source_hashes_before"] == closure["source_hashes_after"], f"source drift {arm}")
            expect(invocation["source_hashes_before"] == closure["source_hashes_before"], f"invocation source drift {arm}")
        expect(invocation["run_id"] == record["run_id"] == closure["run_id"], f"run ID {arm}")
        for name, pin in record["raw"].items():
            expect(closure["raw"][name] == pin, f"closure raw mapping {arm}/{name}")
        expect(invocation["session_id"] == 0 and invocation["ssh_connection_present"], f"SSH provenance {arm}")
        expect("sshd.exe" in invocation["ssh_ancestor_names"], f"sshd ancestry {arm}")
        if arm in ("local", "remote", "remote-disabled"):
            gui = invocation["gui"]
            expect(gui["pid"] == 13340 and gui["session_id"] == 1 and
                   gui["start_utc"] == "2026-09-28T10:09:56.8261381Z", f"GUI identity {arm}")
            expect(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"mutex {arm}")
            steps = read_json(run / "steps.json")
            expect([x["name"] for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"stages {arm}")
            expect(all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps), f"stage outcome {arm}")
        checks.append(f"provenance-{arm}")
    return dirs


def check_roundtrip(run: pathlib.Path, expected_count: int, checks: list[str]) -> dict:
    source = table_map(read_json(run / "input.json"), "model")
    exported = table_map(native_json(run / "roundtrip-raw.json"), "model")
    populated = [name for name, t in source.items() if any(i["rows"] for i in t["instances"])]
    expect(len(populated) == expected_count, f"populated source table count {run}")
    for name in populated:
        expect(name in exported, f"missing exported table {name}")
        expect(source[name]["columns"] == exported[name]["columns"], f"roundtrip columns {name}")
        expect(source[name]["instances"] == exported[name]["instances"], f"roundtrip rows {name}")
        checks.append(f"roundtrip-{run.name}-{name}")
    for name, table in exported.items():
        if name not in populated:
            expect(all(all(not row or all(cell is None for cell in row) for row in i["rows"])
                       for i in table["instances"]), f"native populated unexpected {name}")
    diagnostic = read_json(run / "roundtrip-validation.json")
    expect(diagnostic["passed"] and not diagnostic["differences"], f"author roundtrip diagnostic {run}")
    return source


def check_source_matrix(sources: dict[str, dict], checks: list[str]) -> None:
    def normalized(arm: str) -> dict:
        tables = copy.deepcopy(sources[arm])
        table = tables["ProblemDescription"]
        table["instances"][0]["rows"][0][0] = "<arm description>"
        cols, rows = matrix(tables["ResourceAllocation"])
        rid, stid = cols.index("RID"), cols.index("STID")
        mechs = [row for row in rows if row[rid] == "P-MECH"]
        expect(len(mechs) == 1, f"P-MECH allocation row {arm}")
        mechs[0][stid] = "<arm station>"
        cols, rows = matrix(tables["TaskResource"])
        rows[0][cols.index("ENRMS")] = "<arm enable>"
        tables.pop("ResourceRemoteSupport", None)
        return tables
    for arm in sources:
        desc = source_row(sources[arm], "ProblemDescription")["PDESC"]
        expect(desc == "C09.var04 primary system maintenance remote resource " + arm, f"description {arm}")
        alloc = matrix(sources[arm]["ResourceAllocation"])
        ar = [dict(zip(alloc[0], row)) for row in alloc[1] if row[alloc[0].index("RID")] == "P-MECH"]
        expect(len(ar) == 1 and ar[0]["RQTY"] == 1 and ar[0]["STID"] == ("BASE-01" if arm == "local" else "BASE-02"), f"typed allocation {arm}")
        task = source_row(sources[arm], "TaskResource")
        expect(task["TID"] == "C09-DIRP" and task["RID"] == "P-MECH" and task["QTY"] == 1 and task["RPROB"] == 1,
               f"repair task resource {arm}")
        expect(task["ENRMS"] == ("N" if arm == "remote-disabled" else "Y"), f"remote enable {arm}")
        if arm == "local":
            expect("ResourceRemoteSupport" not in sources[arm], "local arm route")
        else:
            route = source_row(sources[arm], "ResourceRemoteSupport")
            expect(tuple(route[k] for k in ("RID", "STID", "RSTID", "TFRS", "TTRS", "TTRSS")) ==
                   ("P-MECH", "BASE-01", "BASE-02", .25, .5, .125), f"remote route {arm}")
        checks.append(f"source-business-{arm}")
    base = normalized("local")
    expect(normalized("remote") == base and normalized("remote-disabled") == base,
           "undeclared interarm source change")
    checks.append("exact-interarm-source-delta")


def check_converter(run: pathlib.Path, arm: str, checks: list[str]) -> None:
    raw = (run / "run.log").read_text(encoding="utf-8-sig")
    m = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", raw)
    expect(m is not None, f"converter summary {arm}")
    expect(tuple(map(int, m.groups())) == (0, 2, 0 if arm == "local" else 1), f"converter counts {arm}")
    expect(re.findall(r"\(warning #(\d+)\)", raw) == ["108", "126"], f"converter warnings {arm}")
    expect(re.findall(r"\(notice #(\d+)\)", raw) == ([] if arm == "local" else ["292"]), f"converter notices {arm}")
    expect(not re.findall(r"\(error #", raw, flags=re.I), f"converter error {arm}")
    if arm != "local":
        expect("Form: ResourceRemoteSupport\nrec 1: (notice #292) Resource not defined at receiving station, implicitly created: P-MECH/BASE-01" in raw.replace("\r\n", "\n"),
               f"contextual implicit receiver notice {arm}")
    checks.append(f"converter-{arm}")


def parse_events(path: pathlib.Path) -> list[tuple[float, str, int]]:
    events = []
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = TIME.match(raw)
        if match:
            events.append((float(match.group(1)), match.group(2), number))
    expect(events and events[0][0] == 0, f"model log initial time {path}")
    expect(all(a[0] <= b[0] for a, b in zip(events, events[1:])), f"model log time order {path}")
    return events


def selected(events: list, marker: str) -> list[tuple[float, str, int]]:
    return [e for e in events if marker in e[1]]


def one_time(events: list, marker: str) -> float:
    xs = selected(events, marker)
    expect(len(xs) == 1, f"expected one event {marker}: {len(xs)}")
    return xs[0][0]


def per_air(events: list, marker: str) -> dict[int, float]:
    out = {}
    for t, text, _ in selected(events, marker):
        hit = AIR.search(text)
        expect(hit is not None, f"missing physical aircraft {marker}")
        ident = int(hit.group(1))
        expect(ident not in out, f"duplicate physical aircraft {marker}/{ident}")
        out[ident] = t
    return out


def spans(start: dict[int, float], end: dict[int, float], horizon: float = 36.0) -> list[tuple[float, float]]:
    expect(set(start).issubset({0, 1}), "unknown start aircraft")
    expect(set(end).issubset(start), "unknown end aircraft")
    return [(s, end.get(ident, horizon)) for ident, s in sorted(start.items())]


def prep_and_repair(events: list) -> tuple[list, list]:
    starts, ends = {}, {}
    for t, text, _ in events:
        hit = STEP.search(text)
        if not hit:
            continue
        key = (hit.group(2), int(hit.group(3)), int(hit.group(4)))
        if text.endswith("starts performing, planned to last for 0.5 hours"):
            expect(key not in starts, f"duplicate performing start {key}")
            starts[key] = t
        elif text.endswith("completed"):
            expect(key not in ends, f"duplicate performing completion {key}")
            ends[key] = t
    expect(set(starts) == set(ends), "performing start/completion mismatch")
    prep = [(s, ends[k]) for k, s in starts.items() if k[0] == "preparation"]
    repair = [(s, ends[k]) for k, s in starts.items() if k[0] == "DIRP"]
    expect(len(prep) == 2, "two preparation subtasks")
    expect(len(repair) in (0, 2), "zero or two repair subtasks")
    return prep, repair


def count_spans(events: list, plus: str, minus: str) -> list[tuple[float, float]]:
    starts = per_air(events, plus)
    ends = per_air(events, minus)
    return spans(starts, ends)


def area(spans_: list[tuple[float, float]], begin: float, end: float) -> float:
    return sum(max(0.0, min(end, b) - max(begin, a)) for a, b in spans_)


def rate(spans_: list[tuple[float, float]], begin: float, end: float) -> float:
    return area(spans_, begin, end) / (end - begin)


def event_count(events: list, marker: str, begin: float, end: float) -> int:
    return sum(begin <= t < end for t, text, _ in events if marker in text)


def extract_trace(events: list, arm: str) -> dict:
    alloc = per_air(events, "mission allocates system:")
    returned = per_air(events, "turnround ended, mission:")
    prep_start = per_air(events, "preparation started, mission:")
    prep_end = per_air(events, "preparation ended, mission:")
    mission_start = one_time(events, "mission starting, duration:")
    unavailable_start = per_air(events, "System to repair <")
    ready_end = per_air(events, "System ready <")
    wait_start = per_air(events, "nbr resourcewait increased:")
    wait_end = per_air(events, "nbr resourcewait decreased:")
    prep_work, repair_work = prep_and_repair(events)
    expect(len(selected(events, "critical random failure added")) == 2, f"two failures {arm}")
    expect(set(alloc) == set(returned) == set(prep_start) == set(prep_end) == {0, 1}, f"formation identities {arm}")
    expect(alloc[0] == alloc[1] == prep_start[0] == prep_start[1] == 7.5, f"mission allocation {arm}")
    expect(prep_end[0] == prep_end[1] == mission_start == 8.0, f"mission launch {arm}")
    expect(returned[0] == returned[1] == unavailable_start[0] == unavailable_start[1] == 8.53243, f"mission return/repair {arm}")
    expect({t for t, _, _ in selected(events, "critical random failure added")} == {8.28243, 8.46988}, f"failure times {arm}")
    expect(all(abs(b - a - 0.5) < 1e-5 for a, b in prep_work + repair_work), f"subtask durations {arm}")
    if arm == "remote-disabled":
        expect(not ready_end and not repair_work and not wait_end, "disabled repair unexpectedly progresses")
    else:
        expect(set(ready_end) == {0, 1} and len(repair_work) == 2 and set(wait_end) == {1} if arm == "local" else
               set(ready_end) == {0, 1} and len(repair_work) == 2 and set(wait_end) == {0, 1}, f"repair completion/wait {arm}")
    # All ready-count changes are observed in the event log; simultaneous
    # increase/decrease at return cancel at printed time before integration.
    ready_delta = []
    for t, text, _ in events:
        if "nbr ready increased at unit:" in text:
            ready_delta.append((t, 1))
        elif "nbr ready decreased at unit:" in text:
            ready_delta.append((t, -1))
    points = sorted({0.0, 36.0, *(t for t, _ in ready_delta)})
    ready = []
    state = 0
    for a, b in zip(points, points[1:]):
        state += sum(delta for t, delta in ready_delta if t == a)
        expect(0 <= state <= 2, f"ready count conservation {arm}/{a}")
        ready.append((a, b, state))
    expect(sum(delta for _, delta in ready_delta) == 2, f"terminal two ready {arm}" if arm != "remote-disabled" else "terminal disabled ready") if arm != "remote-disabled" else None
    outward_start = selected(events, "remote resource transport task 3 starts with 1 resources")
    outward_end = selected(events, "remote resource transport task 3 arrives with 1 resources")
    return_start = selected(events, "return resource transport task 0 starts with 1 resources")
    return_end = selected(events, "return resource transport task 0 arrives with 1 resources")
    transport, loan = [], []
    if arm == "remote":
        expect(len(outward_start) == len(outward_end) == len(return_start) == len(return_end) == 1, "remote transport lifecycle")
        outward = (outward_start[0][0], outward_end[0][0])
        inward = (return_start[0][0], return_end[0][0])
        expect(outward == (8.53243, 8.78243) and inward == (9.78243, 10.2824), "remote printed transport times")
        transport = [outward, inward]
        loan = [(outward[1], inward[0])]
    else:
        expect(not (outward_start or outward_end or return_start or return_end), "nonremote transport")
    return {
        "events": events,
        "ready": ready,
        "allocated": spans(alloc, returned),
        "ongoing": [(mission_start, returned[i]) for i in (0, 1)],
        "preparing": spans(prep_start, prep_end),
        "unavailable": spans(unavailable_start, ready_end),
        "waiting": spans(wait_start, wait_end),
        "prep_work": prep_work,
        "repair_work": repair_work,
        "transport": transport,
        "loan": loan,
        "repair_starts": unavailable_start,
        "repair_ends": ready_end,
        "mission_start": mission_start,
        "mission_return": returned[0],
    }


def weighted_ready(trace: dict, a: float, b: float) -> float:
    return sum(max(0.0, min(b, end) - max(a, start)) * n for start, end, n in trace["ready"]) / (b - a)


def expected_system(trace: dict, source: dict, bin_index: int) -> dict:
    a, b = bin_index / 2, (bin_index + 1) / 2
    c = {name: 0 for name in [
        "NSYRY", "NSYMA", "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYUA", "NSYA", "NSYAL", "FTMO", "NSYRP", "NSYPM", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT", "NPMT", "NFAIL", "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STACC", "STF", "STLOW", "SYDT", "SYDTU", "NSYDT", "NSYSW", "NPSTA", "NPSUC"]}
    c.update(UNID="Total over all Units", SID="Total over all Systems", STINT=a, ETINT=b)
    c["SYDT"] = None
    c["NSYRY"] = weighted_ready(trace, a, b)
    c["NSYMA"] = rate(trace["allocated"], a, b)
    c["NSYMO"] = rate(trace["ongoing"], a, b)
    c["NSYMP"] = rate(trace["preparing"], a, b)
    c["NSYUA"] = rate(trace["unavailable"], a, b)
    c["NSYA"] = 2 - c["NSYUA"]
    c["FTMO"] = c["NSYMO"] / 2
    c["NSYRP"] = rate(trace["repair_work"], a, b)
    c["NSYWR"] = rate(trace["waiting"], a, b)
    c["NREPT"] = sum(a <= t < b and text.startswith("system DIRP task ") and text.endswith(" completed")
                      for t, text, _ in trace["events"])
    c["NFAIL"] = event_count(trace["events"], "critical random failure added", a, b)
    c["STACC"] = c["NSYMO"]
    c["NPSTA"] = event_count(trace["events"], "preparation started, mission:", a, b)
    c["NPSUC"] = event_count(trace["events"], "preparation ended, mission:", a, b)
    if a <= trace["repair_starts"][0] < b and set(trace["repair_ends"]) == {0, 1}:
        c["SYDT"] = sum(trace["repair_ends"][i] - trace["repair_starts"][i] for i in (0, 1)) / 2
        c["NSYDT"] = 2
    return c


def expected_resource(trace: dict, a: float, b: float) -> dict:
    all_work = trace["prep_work"] + trace["repair_work"]
    travel = rate(trace["transport"], a, b)
    borrowed = rate(trace["loan"], a, b)
    on_station = 3 - travel
    return {"RID": "Total over all Resources", "STID": "Total over all Stations", "STINT": a, "ETINT": b,
            "NR": on_station, "NRMO": 0, "NRMA": 0, "NRUM": rate(all_work, a, b), "NRLA": 0,
            "NRW": rate(trace["waiting"], a, b), "NRA": on_station, "NRN": 3, "NRF": 0,
            "NRRI": borrowed, "NRRT": travel, "NRRO": borrowed}


def expected_stock(a: float, b: float, baseline: dict) -> dict:
    out = dict(baseline)
    out["STINT"], out["ETINT"] = a, b
    return out


def compare_value(expected: object, actual: object, table: str, column: str, label: str) -> None:
    if expected is None or isinstance(expected, str) or isinstance(expected, bool):
        expect(type(actual) is type(expected) and actual == expected, f"{label}: {table}.{column} expected {expected!r}, got {actual!r}")
        return
    expect(isinstance(expected, (int, float)) and not isinstance(actual, bool) and isinstance(actual, (int, float)), f"{label}: type {table}.{column}")
    # Exact topology/discrete counts, including zeros. Native per-interval
    # integrated levels and totals are single-precision floating outputs.
    fractional = {
        "SystemResults": {"NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYUA", "NSYA", "FTMO", "NSYRP", "NSYWR", "STACC", "SYDT"},
        "ResourceResults": {"NR", "NRUM", "NRW", "NRA", "NRRI", "NRRT", "NRRO"},
        "ResourceResultsTotal": {"NR", "NRUM", "NRW", "NRA", "NRRI", "NRRT", "NRRO"},
        "ResultSummary": {"MTMF", "STMF"},
    }
    if column in fractional.get(table, set()):
        if float(expected).is_integer():
            expect(actual == expected, f"{label}: exact whole-bin {table}.{column} expected {expected!r}, got {actual!r}")
            return
        # Max 2 aircraft/resource-unit boundaries per half-hour: each printed
        # timestamp contributes <= 5e-6 h. With binary32 serialization, 6e-5
        # per interval is conservative but rejects a 1e-4 interior mutation.
        bound = 6e-5 if table in ("SystemResults", "ResourceResults") else 2e-5
        # The return receipt prints 10.2824, only four decimal places, so
        # transit/on-station row averages have 5e-5h / .5h uncertainty.
        if table == "ResourceResults" and column in {"NR", "NRA", "NRRT"}:
            bound = 1.1e-4
        expect(math.isfinite(float(actual)) and abs(float(actual) - float(expected)) <= bound,
               f"{label}: {table}.{column} expected {expected!r}, got {actual!r}, bound {bound}")
    else:
        expect(actual == expected, f"{label}: {table}.{column} expected {expected!r}, got {actual!r}")


def compare_table(table: str, source: dict, expected_rows: list[dict], report: dict, label: str, checks: list[str]) -> None:
    t = report[table]
    cols, observed = matrix(t)
    expect(cols == EXPECTED_COLUMNS[table], f"{label}: {table} column order/topology")
    expect(len(observed) == len(expected_rows), f"{label}: {table} row count")
    expect(set(cols) == set(expected_rows[0]), f"{label}: {table} column topology")
    for index, (actual, expected) in enumerate(zip(observed, expected_rows)):
        for col, value in zip(cols, actual):
            compare_value(expected[col], value, table, col, f"{label}/row{index}")
            checks.append(f"cell-{label}-{table}-{index}-{col}")


def expected_report(run: pathlib.Path, arm: str, trace: dict, source: dict, stock_baseline: dict) -> dict[str, list[dict]]:
    pdesc = source_row(source, "ProblemDescription")["PDESC"]
    control = source_row(source, "Control")
    mission = source_row(source, "MissionType")
    expect(control["SIMPE"] == control["RCEND"] == 36 and control["RCINT"] == 0.5 and control["NREPS"] == 1, "source horizon")
    expect(mission["NOS"] == mission["MNOS"] == 2 and mission["DURN"] == 1, "source formation")
    item_names = ("Item", "ItemStructure", "StockAllocation", "ItemReplacement", "ItemReorder", "ItemRepair")
    expect(all(not matrix(source[name])[1] for name in item_names), "no stock-producing source rows")
    expect(not any(any(word in text.lower() for word in ("item demand", "stock issue", "item taken", "item returned")) for _, text, _ in trace["events"]), "no physical stock events")
    systems = [expected_system(trace, source, i) for i in range(72)]
    stocks = [expected_stock(i / 2, (i + 1) / 2, stock_baseline) for i in range(72)]
    resources = [expected_resource(trace, i / 2, (i + 1) / 2) for i in range(72)]
    flight = area(trace["ongoing"], 0, 36) / (2 * mission["DURN"])
    summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": flight, "RSMTMF": 0,
               "MSTF": 1, "RSMSTF": 0, "MSUF": 0, "RSMSUF": 0, "STMF": flight, "RSSTMF": 0}
    total = {k: v for k, v in resources[0].items() if k not in ("STINT", "ETINT")}
    for k in total:
        if k not in ("RID", "STID"):
            total[k] = sum(row[k] for row in resources) / 72
    return {"ProblemDescription": [{"PDESC": pdesc}], "ResultSummary": [summary],
            "SystemResults": systems, "StockTotalResults": stocks,
            "ResourceResults": resources, "ResourceResultsTotal": [total]}


def check_report_instances(report: dict, checks: list[str], arm: str) -> None:
    names = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]
    expect(list(report) == names, f"six report tables/order {arm}")
    expected_names = {"ProblemDescription": "", "ResultSummary": "", "SystemResults": "Total over all Units;Total over all Systems;0.00;36.00",
                      "StockTotalResults": "0.00;36.00;", "ResourceResults": "Total over all Resources;Total over all Stations;0.00;36.00",
                      "ResourceResultsTotal": "Total over all Resources;Total over all Stations;0.00;36.00"}
    for name in names:
        expect(len(report[name]["instances"]) == 1 and report[name]["instances"][0]["instance_name"] == expected_names[name], f"instance {arm}/{name}")
        checks.append(f"instance-{arm}-{name}")


def stock_control_baseline(c03_run: pathlib.Path, checks: list[str]) -> dict:
    parent = table_map(native_json(c03_run / "report-raw.json"), "report")
    cols, rows = matrix(parent["StockTotalResults"])
    expect(len(rows) == 72, "C03 control stock shape")
    baseline = dict(zip(cols, rows[0]))
    expect(baseline == {"STINT": 0, "ETINT": 0.5, "NBO": 0, "NBOU": None, "ROS": None,
                        "ROST": None, "WT": None, "WTT": None, "WTS": None, "PNB": 1,
                        "NDF": 0, "NDD": 0, "NDR": 0, "NDP": 0, "NLD": 0, "NWT": 0}, "C03 independent stock baseline")
    for i, row in enumerate(rows):
        expected = dict(baseline, STINT=i / 2, ETINT=(i + 1) / 2)
        expect(dict(zip(cols, row)) == expected, f"C03 control stock row {i}")
    checks.append("C03-72-bin-stock-baseline")
    return baseline


def event_gates(traces: dict[str, dict], checks: list[str]) -> None:
    local, remote, disabled = (traces[k] for k in ("local", "remote", "remote-disabled"))
    expect(len(local["repair_work"]) == len(remote["repair_work"]) == 2 and not disabled["repair_work"], "repair completion contrast")
    expect(remote["repair_work"] == [(8.78243, 9.28243), (9.28243, 9.78243)], "remote printed-contiguous repair")
    expect(local["repair_work"] == [(8.53243, 9.03243), (9.03243, 9.53243)], "local repair control")
    events = remote["events"]
    at = [(text, line) for t, text, line in events if t == 9.28243]
    def index(fragment: str) -> int:
        hits = [i for i, (text, _) in enumerate(at) if fragment in text]
        expect(len(hits) == 1, f"same-time event {fragment}")
        return hits[0]
    order = ["subtask 2 seqno 1 within system DIRP task 2 on <TEACH-AIR-01,0> completed",
             "<P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1",
             "subtask 3 seqno 1 within system DIRP task 3 on <TEACH-AIR-01,1> resource availability test",
             "subtask 3 seqno 1 within system DIRP task 3 on <TEACH-AIR-01,1> resource received",
             "subtask 3 seqno 1 within system DIRP task 3 on <TEACH-AIR-01,1> books resources",
             "<P-MECH at <BASE-01,0>> allocated to maintenance task: 1",
             "subtask 3 seqno 1 within system DIRP task 3 on <TEACH-AIR-01,1> starts performing",
             "subtask 2 seqno 1 check return remote resources"]
    positions = [index(x) for x in order]
    expect(positions == sorted(positions), "same-time printed release/regrant/order")
    expect(len(selected(events, "remote resource transport task 3 starts with 1 resources")) == 1 and
           len(selected(events, "return resource transport task 0 starts with 1 resources")) == 1, "one outward and one return")
    expect(not selected(events, "Remote resource shortage"), "no lender shortage assertion")
    checks.extend(["physical-two-aircraft-contrast", "h9.28243-release-regrant-order", "one-remote-transport-each-way"])


def self_check() -> list[str]:
    probes = []
    def fails(expected, actual, table, col):
        try:
            compare_value(expected, actual, table, col, "tamper")
        except ReviewFailure:
            probes.append(f"reject-{table}.{col}")
        else:
            raise ReviewFailure(f"tamper accepted {table}.{col}")
    fails(0, 1, "SystemResults", "NFAIL")
    fails(None, 0, "SystemResults", "SYDT")
    fails("Total over all Units", "wrong unit", "SystemResults", "UNID")
    fails(0.43513, 0.43523, "SystemResults", "NSYRY")
    fails(0.5, 0.5002, "ResourceResults", "NRRT")
    fails(3, 4, "ResourceResults", "NRN")
    fails(1, 0, "StockTotalResults", "PNB")
    fails(0.0208333, 0.020934, "ResourceResultsTotal", "NRRT")
    fails(0.53243, 0.53253, "ResultSummary", "MTMF")
    compare_value(0.4351302, 0.4351302683353424, "SystemResults", "NSYRY", "precision-positive")
    probes.append("accept-bounded-native-fraction")
    return probes


def run() -> dict:
    checks: list[str] = []
    contract = read_json(CONTRACT)
    expect(digest(CONTRACT.read_bytes()) == {"bytes": 39399, "sha256": "4200c13634a6f869250978861a4f64a47052e06c7184d391f2dacabbd542c297"}, "frozen contract")
    expect(contract["version"] == "0.1.1" and contract["new_native_runs"] == 0, "contract classification")
    check_sources(contract, checks)
    dirs = check_runs(contract, checks)
    baseline = stock_control_baseline(dirs["C03_direct_parent"], checks)
    traces = {}
    sources = {}
    reports = {}
    for arm in ("local", "remote", "remote-disabled"):
        source_count = contract["predeclared_native_gates"]["roundtrip_row_tables"][arm]
        sources[arm] = check_roundtrip(dirs[arm], source_count, checks)
        check_converter(dirs[arm], arm, checks)
        traces[arm] = extract_trace(parse_events(dirs[arm] / "model.log"), arm)
        reports[arm] = table_map(native_json(dirs[arm] / "report-raw.json"), "report")
        check_report_instances(reports[arm], checks, arm)
    check_source_matrix(sources, checks)
    event_gates(traces, checks)
    report_counts = {}
    for arm in ("local", "remote", "remote-disabled"):
        expected = expected_report(dirs[arm], arm, traces[arm], sources[arm], baseline)
        start = len(checks)
        for table in ("ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"):
            compare_table(table, sources[arm], expected[table], reports[arm], arm, checks)
        count = sum(x.startswith("cell-" + arm + "-") for x in checks[start:])
        expect(count == 5210, f"{arm} report cell count {count}")
        report_counts[arm] = count
    probes = self_check()
    return {"schema": "c09-var03-independent-readonly-verdict/v1", "decision": "GO_BOUNDED", "contract_sha256": digest(CONTRACT.read_bytes())["sha256"],
            "checks": len(checks) + len(probes), "report_cells": report_counts, "tamper_probes": probes,
            "source_disk_pins": 32, "source_git_pins": 32, "raw_seals": 71, "closures": 6, "invocations": 6,
            "native_runs_created": 0, "limits": ["retrospective fixed seed", "printed-time contiguous use only", "release/rebook, not continuous booking", "no persistent person/resource-unit ID", "no lender-shortage TTRSS test"], "failures": []}


def main() -> int:
    try:
        if "--self-check" in sys.argv:
            print(json.dumps({"decision": "SELF_CHECK_PASS", "probes": self_check()}, sort_keys=True))
            return 0
        verdict = run()
    except Exception as exc:
        verdict = {"schema": "c09-var03-independent-readonly-verdict/v1", "decision": "NO_GO", "contract_sha256": digest(CONTRACT.read_bytes())["sha256"], "checks": 0, "failures": [str(exc)]}
    data = (json.dumps(verdict, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    VERDICT.write_bytes(data)
    print(json.dumps({"decision": verdict["decision"], "checks": verdict["checks"], "failures": verdict["failures"], "verdict_sha256": digest(data)["sha256"]}, sort_keys=True))
    return 0 if verdict["decision"] == "GO_BOUNDED" else 1


if __name__ == "__main__":
    sys.exit(main())
