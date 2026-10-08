"""Independent read-only I03.var05 source, physical and full-report replay.

The pure fixture is a prediction from frozen accepted evidence. Only the default
sealed mode may inspect a future original child run and issue an observed verdict.
"""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[4]
CASE = Path(__file__).resolve().parents[1]
PARENT = ROOT / "cases/simlox-air-support/I03-var01-crew-out-in-v1.0.0"
PARENT_RUN = PARENT / "runs/i03-var01-crew-transfer-v100-ssh-20261005-01"
RUN = CASE / "runs/i03-var05-in-zero-delay-v100-ssh-20261008-01"
V4_SHA = "95ba77bcac344e023f140a39b4f88b4f94160d07c2a4e94563ff84de592f7331"
PARENT_LOG_SHA = "673706cc043d4c5b1ce07c0692070b7931677257779fa3a67ebf190e2644f0c5"
PARENT_REPORT_SHA = "46c798558486eff6f4714d9e1783914b9a2169ec535d773d72ec2471b9959cbd"
PARENT_INPUT_SHA = "81107e9713b9e21178de4d877a146963b693af7193d0663aa9e4d32871b44e84"
PARENT_EXPORT_SHA = "2d2057fb88c65ed2fe057d969fc90e024369b324c9c90327252e9dd4f5c7f7b2"


class Audit:
    def __init__(self):
        self.checks = 0

    def require(self, condition, label):
        self.checks += 1
        assert condition, label


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, ("duplicate JSON key", key)
        result[key] = value
    return result


def reject_constant(value):
    raise AssertionError(("nonfinite JSON constant", value))


def parse_json(raw, *, native=False):
    if native:
        decoded = raw.decode("utf-8-sig")
        decoded, count = re.subn(r",(?=\s*\]\s*\}\s*\}\s*$)", "", decoded)
        assert count == 1, ("native trailing-comma location", count)
    else:
        decoded = raw.decode("utf-8-sig")
    result = json.loads(decoded, object_pairs_hook=unique, parse_constant=reject_constant)

    def finite(value):
        if type(value) is float:
            assert math.isfinite(value), "nonfinite JSON numeric (including exponent overflow)"
        elif isinstance(value, list):
            for item in value:
                finite(item)
        elif isinstance(value, dict):
            for item in value.values():
                finite(item)

    finite(result)
    return result


def recursive_same(actual, expected, audit, label="root"):
    audit.require(type(actual) is type(expected), (label, "type", type(actual), type(expected)))
    if isinstance(expected, dict):
        audit.require(set(actual) == set(expected), (label, "key set"))
        for key in expected:
            recursive_same(actual[key], expected[key], audit, f"{label}.{key}")
    elif isinstance(expected, list):
        audit.require(len(actual) == len(expected), (label, "length"))
        for i, (x, y) in enumerate(zip(actual, expected)):
            recursive_same(x, y, audit, f"{label}[{i}]")
    else:
        audit.require(actual == expected, (label, "value", actual, expected))


def numeric(actual, expected, audit, label):
    audit.require(type(actual) in (int, float) and math.isfinite(actual), (label, "finite numeric"))
    audit.require(actual == expected, (label, "numeric value", actual, expected))


def read_pin(path, pin, audit, label):
    raw = Path(path).read_bytes()
    audit.require(len(raw) == pin["bytes"], (label, "bytes"))
    audit.require(sha(raw) == pin["sha256"], (label, "sha256"))
    return raw


def case_contract(audit):
    contract_raw = (CASE / "contract.json").read_bytes()
    audit.require(len(contract_raw) == 121824 and sha(contract_raw) == V4_SHA, "frozen v4 contract")
    contract = parse_json(contract_raw)
    audit.require(contract["schema"] == "simlox-air-support-i03-var05-prospective-contract-design/v4", "v4 schema")
    return contract


def parent_source_and_raw(contract, audit):
    lineage = contract["source_lineage"]
    audit.require(lineage["mandatory_original_raw_count"] == 112, "112 original raw")
    audit.require(lineage["mandatory_source_refs_total"] == 80, "80 local/Git refs")
    refs = lineage["accepted_parent"]["all_source_refs"] + lineage["accepted_prerequisites"]["all_source_refs"]
    audit.require(len(refs) == 80 and len({r["path"] for r in refs}) == 80, "distinct refs")
    tree_raw = subprocess.run(["git", "ls-tree", "-r", "-z", lineage["base_commit"]], cwd=ROOT, capture_output=True, check=True).stdout
    tree = {}
    for rec in tree_raw.split(b"\0"):
        if rec:
            head, path = rec.split(b"\t", 1)
            mode, kind, oid = head.split(b" ")
            tree[path.decode()] = (kind.decode(), oid.decode())
    for record in refs:
        read_pin(ROOT / record["path"], record["disk"], audit, record["path"])
        audit.require(tree.get(record["path"]) == ("blob", record["oid"]), (record["path"], "base Git OID"))
        blob = subprocess.run(["git", "cat-file", "blob", record["oid"]], cwd=ROOT, capture_output=True, check=True).stdout
        audit.require(len(blob) == record["git"]["bytes"] and sha(blob) == record["git"]["sha256"], (record["path"], "Git blob"))
    for record in lineage["mandatory_original_raw"]:
        read_pin(record["path"], record, audit, record["path"])
    for key in ("installed_manual", "installed_dictionary", "installed_executable"):
        read_pin(lineage[key]["path"], lineage[key], audit, key)
    for record in lineage["design_history"]:
        read_pin(ROOT / record["path"], record, audit, record["path"])
    return lineage


def canonical_source_and_prediction(contract, audit):
    parent_raw = (PARENT / "out_in-input.json").read_bytes()
    audit.require(sha(parent_raw) == PARENT_INPUT_SHA, "parent input SHA")
    parent = parse_json(parent_raw)
    audit.require(list(parent) == ["model"] and list(parent["model"]) == ["database_version", "tables"], "source root metadata")
    audit.require(type(parent["model"]["database_version"]) is int and parent["model"]["database_version"] == 20160627, "database version")
    src_tables = parent["model"]["tables"]
    audit.require(len(src_tables) == 32 and [t["name"] for t in src_tables] == contract["source_delta"]["table_names_ordered"], "ordered 32 source tables")
    audit.require(sum(len(i["rows"]) for t in src_tables for i in t["instances"]) == 25, "25 authored rows")
    audit.require(sum(len(r) for t in src_tables for i in t["instances"] for r in i["rows"]) == 227, "227 authored cells")
    predicted = copy.deepcopy(parent)
    tables = predicted["model"]["tables"]
    problem = next(t for t in tables if t["name"] == "ProblemDescription")
    old_description = problem["instances"][0]["rows"][0][0]
    audit.require(old_description == contract["source_delta"]["parent_description"], "parent description")
    problem["instances"][0]["rows"][0][0] = contract["source_delta"]["child_description_predeclared"]
    transfer = next(t for t in tables if t["name"] == "ResourceTransfer")
    rows = transfer["instances"][0]["rows"]
    audit.require(rows == [contract["source_delta"]["unchanged_OUT_row"], contract["source_delta"]["parent_IN_row"]], "parent OUT/IN rows")
    rows[1][5] = 0.0
    audit.require(rows[1] == contract["source_delta"]["child_IN_row_expected"], "predicted IN")
    actual_child = parse_json((CASE / "native-input.json").read_bytes())
    recursive_same(actual_child, predicted, audit, "authored child")
    return parent, predicted


def check_roundtrip(authored, exported_raw, audit):
    exported = parse_json(exported_raw)
    src_tables, out_tables = authored["model"]["tables"], exported["model"]["tables"]
    audit.require(list(exported) == ["model"] and exported["model"]["database_version"] == 20160627, "export root/version")
    audit.require(len(out_tables) == len(src_tables) == 32, "32 export tables")
    audit.require(sum(len(i["rows"]) for t in out_tables for i in t["instances"]) == 36, "36 export rows")
    audit.require(sum(len(r) for t in out_tables for i in t["instances"] for r in i["rows"]) == 368, "368 export cells")
    empty = {"Item", "ItemStructure", "StationStructure", "SystemRepair", "ItemRepair", "ItemReorder", "TaskResource", "MaterielPM", "PMLocation", "StockAllocation", "ItemReplacement"}
    for source, output in zip(src_tables, out_tables):
        audit.require(source["name"] == output["name"], "export table order")
        recursive_same(output["columns"], source["columns"], audit, source["name"] + ".columns")
        audit.require(len(source["instances"]) == len(output["instances"]) == 1, "one source/export instance")
        s, o = source["instances"][0], output["instances"][0]
        recursive_same(o["instance_name"], s["instance_name"], audit, source["name"] + ".instance")
        if source["name"] in empty:
            audit.require(s["rows"] == [], "authored empty table")
            recursive_same(o["rows"], [[None] * len(source["columns"])], audit, source["name"] + ".placeholder")
        else:
            audit.require(len(o["rows"]) == len(s["rows"]), source["name"] + ".row count")
            for ri, (actual_row, authored_row) in enumerate(zip(o["rows"], s["rows"])):
                audit.require(len(actual_row) == len(authored_row) == len(source["columns"]), source["name"] + ".row width")
                for ci, (actual_cell, authored_cell, col) in enumerate(zip(actual_row, authored_row, source["columns"])):
                    label = f"{source['name']}.rows[{ri}][{ci}]"
                    if col["datatype"] == "double" and authored_cell is not None:
                        numeric(actual_cell, authored_cell, audit, label)
                    else:
                        recursive_same(actual_cell, authored_cell, audit, label)
    return exported


def accepted_parent_roundtrip(parent, audit):
    raw = (PARENT_RUN / "out_in-roundtrip-raw.json").read_bytes()
    audit.require(sha(raw) == PARENT_EXPORT_SHA, "parent export SHA")
    return check_roundtrip(parent, raw, audit)


def model_description(model):
    return next(t for t in model["model"]["tables"] if t["name"] == "ProblemDescription")["instances"][0]["rows"][0][0]


def predicted_log_lines(audit):
    parent_raw = (PARENT_RUN / "out_in.log").read_bytes()
    audit.require(sha(parent_raw) == PARENT_LOG_SHA, "parent log SHA")
    lines = parent_raw.decode("utf-8-sig").splitlines()
    audit.require(lines[:2] == ["SIMLOX LOG FILE", "36"], "parent log header")
    expected = list(lines)
    start = "Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: 0.5"
    audit.require(expected.count(start) == 1, "parent IN start cardinality")
    expected[expected.index(start)] = start[:-3] + "0"
    move_time = (
        "Time: 10.5  resource transfer task 2 (IN)  arrives with 1 resources",
        "Time: 10.5  <P-CREW at <BASE-01,0>> transfer arrives: 1",
        "Time: 10.5 <BASE-01,0> trig missions and tasks waiting for resources ",
        "Time: 10.5  <P-CREW at <BASE-01,0>> check for return transport: 1",
    )
    for old in move_time:
        audit.require(expected.count(old) == 1, ("parent IN edge", old))
        expected[expected.index(old)] = old.replace("Time: 10.5", "Time: 10", 1)
    audit.require(sum(x.startswith("Time: 10.5") for x in expected) == 0, "no prospective late IN")
    return lines, expected


def check_typed_child_log(raw, audit):
    parent, expected = predicted_log_lines(audit)
    lines = raw.decode("utf-8-sig").splitlines()
    audit.require(len(lines) == len(expected), "whole log line cardinality")
    for n, (actual, want) in enumerate(zip(lines, expected), 1):
        audit.require(actual == want, ("whole source-bound typed trace", n, actual, want))
    audit.require(lines[:2] == ["SIMLOX LOG FILE", "36"], "child horizon")
    def one(body):
        hits = [i for i, line in enumerate(lines) if line == body]
        audit.require(len(hits) == 1, ("typed cardinality", body))
        return hits[0]
    created_out = one("Time: 8  resource transfer task 1 (OUT)  created: starting from  <P-CREW at <BASE-01,0>>")
    start_out = one("Time: 8  resource transfer task 1 (OUT)  starts with 1 resources, transfer time: 0")
    arrive_out = one("Time: 8  resource transfer task 1 (OUT)  arrives with 1 resources")
    created_in = one("Time: 10  resource transfer task 2 (IN)  created: aiming for  <P-CREW at <BASE-01,0>>")
    start_in = one("Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: 0")
    arrive_in = one("Time: 10  resource transfer task 2 (IN)  arrives with 1 resources")
    receipt = one("Time: 10  <P-CREW at <BASE-01,0>> transfer arrives: 1")
    free2 = receipt + 1
    audit.require(lines[free2] == "  Free resources at: <BASE-01,0> P-CREW 2", "matching receipt free-two continuation")
    audit.require(created_out < start_out < arrive_out < created_in < start_in < arrive_in < receipt < free2, "typed transfer causal order")
    demand = one("Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer ")
    backorder = one("Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer backorder added ")
    backorder_removed = one("Time: 8  <P-CREW at <BASE-01,0>> Resource transfer backorder removed ")
    releases = [i for i, line in enumerate(lines) if line == "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1"]
    audit.require(len(releases) == 2 and demand < backorder < releases[0] < backorder_removed < releases[1] < start_out, "h8 reservation and one departure")
    audit.require(lines[backorder_removed + 1].strip().endswith("Nbr: 0"), "backorder zero snapshot")
    audit.require(lines[free2 + 1].startswith("Time: 10 <BASE-01,0> trig missions"), "receipt queue continuation")
    audit.require(sum(x.startswith("Time: 10.5") for x in lines) == 0, "no h10.5 IN")
    ledger = resource_microsteps(lines, audit)
    audit.require(ledger["local"] == ledger["nominal"] == ledger["free"] == 2, "terminal free roster")
    return {"OUT_departure": 8, "IN_start": 10, "IN_task_arrival": 10, "IN_local_receipt": 10,
        "local_after_receipt": 2, "terminal": 36, "typed_lines": len(lines), "microsteps": ledger["microsteps"]}


def resource_microsteps(lines, audit):
    local, booked, reserved, departed, received, nominal = 2, 0, 0, 0, 0, 2
    backorders = 0
    out_requests = 0
    started_in = arrived_in = pending_receipt = 0
    active_tasks = set()
    pending_book = pending_release = None
    current_hour, previous_hour = 0, -1
    microsteps = 0
    counts = {name: 0 for name in ("shift_start", "shift_end", "book", "release", "backorder_add",
        "backorder_remove", "out_depart", "out_arrive", "in_start", "in_arrive", "in_receipt", "free_snapshot")}
    timed = re.compile(r"Time: ([0-9]+(?:\.[0-9]+)?)\s+(.*)\Z")
    subbook = re.compile(r"subtask (\d+) seqno 1 within system preparation task \1 on <TEACH-AIR-01,([01])> books resources\Z")
    subfree = re.compile(r"subtask (\d+) seqno 1 within system preparation task \1 on <TEACH-AIR-01,([01])> frees resources\Z")
    allocation = re.compile(r"<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: (\d+)\Z")
    release = re.compile(r"<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: (\d+)\Z")
    transfer_start = re.compile(r"resource transfer task (\d+) \((OUT|IN)\)  starts with (\d+) resources, transfer time: ([0-9.]+)\Z")
    transfer_arrive = re.compile(r"resource transfer task (\d+) \((OUT|IN)\)  arrives with (\d+) resources\Z")
    for number, line in enumerate(lines[2:], start=3):
        match = timed.fullmatch(line)
        if match:
            current_hour = float(match.group(1))
            audit.require(math.isfinite(current_hour) and previous_hour <= current_hour <= 36, ("typed clock", number))
            previous_hour = current_hour
            body = match.group(2).strip()
        else:
            body = line.strip()
        if body == "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period":
            audit.require(current_hour == 0 and counts["shift_start"] == 0, "single shift start")
            counts["shift_start"] += 1
        elif body == "resource shift 0 ended at <P-CREW at <BASE-01,0>> time gap to next = 0":
            audit.require(current_hour == 36 and counts["shift_end"] == 0, "single shift end")
            counts["shift_end"] += 1
        elif (m := subbook.fullmatch(body)):
            task = (int(m.group(1)), int(m.group(2)))
            audit.require(pending_book is None and task not in active_tasks, "source-bound unique book owner")
            pending_book = task
        elif (m := subfree.fullmatch(body)):
            task = (int(m.group(1)), int(m.group(2)))
            audit.require(pending_release is None and task in active_tasks, "source-bound release owner")
            pending_release = task
        elif (m := allocation.fullmatch(body)):
            audit.require(pending_book is not None, "allocation follows own book edge")
            booked += 1
            active_tasks.add(pending_book)
            pending_book = None
            counts["book"] += 1
            audit.require(int(m.group(1)) == local - booked - reserved, "printed free after booking")
        elif (m := release.fullmatch(body)):
            audit.require(pending_release is not None, "release follows own free edge")
            booked -= 1
            active_tasks.remove(pending_release)
            pending_release = None
            counts["release"] += 1
            audit.require(int(m.group(1)) == local - booked - reserved, "printed free after release")
        elif body == "<P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer":
            audit.require(current_hour == 7.75 and nominal == 2 and out_requests == 0, "OUT nominal demand time")
            nominal -= 1
            out_requests += 1
        elif body == "<P-CREW at <BASE-01,0>> Resource transfer backorder added":
            audit.require(current_hour == 7.75 and backorders == 0 and local - booked - reserved == 0, "backorder due to zero free")
            backorders = 1
            counts["backorder_add"] += 1
        elif body == "<P-CREW at <BASE-01,0>> Resource transfer backorder removed":
            audit.require(current_hour == 8 and backorders == 1 and local - booked - reserved == 1, "backorder reservation after first release")
            backorders = 0
            reserved = 1
            counts["backorder_remove"] += 1
        elif (m := transfer_start.fullmatch(body)):
            ident, direction, quantity, delay = int(m.group(1)), m.group(2), int(m.group(3)), float(m.group(4))
            audit.require(delay == 0, "zero printed OUT/IN task delay")
            if direction == "OUT" and ident == 0:
                audit.require(current_hour == 7.75 and quantity == 0, "zero OUT at demand")
            elif direction == "OUT" and ident == 1:
                audit.require(current_hour == 8 and quantity == reserved == 1, "positive OUT consumes reservation")
                reserved -= quantity
                local -= quantity
                departed += quantity
                counts["out_depart"] += 1
            elif direction == "IN" and ident == 2:
                audit.require(current_hour == 10 and quantity == 1 and started_in == 0, "IN started unarrived")
                started_in += quantity
                counts["in_start"] += 1
            else:
                raise AssertionError(("unknown transfer task", ident, direction))
        elif (m := transfer_arrive.fullmatch(body)):
            ident, direction, quantity = int(m.group(1)), m.group(2), int(m.group(3))
            if direction == "OUT" and ident == 0:
                audit.require(current_hour == 7.75 and quantity == 0, "zero OUT completion")
            elif direction == "OUT" and ident == 1:
                audit.require(current_hour == 8 and quantity == 1 and departed == 1, "OUT task completion no second decrement")
                counts["out_arrive"] += 1
            elif direction == "IN" and ident == 2:
                audit.require(current_hour == 10 and quantity == started_in == 1, "IN task arrival")
                started_in -= quantity
                arrived_in += quantity
                pending_receipt += quantity
                counts["in_arrive"] += 1
            else:
                raise AssertionError(("unknown arrival task", ident, direction))
        elif body == "<P-CREW at <BASE-01,0>> transfer arrives: 1":
            audit.require(current_hour == 10 and pending_receipt == 1 and received == 0, "one matching local receipt")
            pending_receipt -= 1
            received += 1
            local += 1
            nominal += 1
            counts["in_receipt"] += 1
        elif (m := re.fullmatch(r"Free resources at: <BASE-01,0> P-CREW (\d+)", body)):
            audit.require(int(m.group(1)) == local - booked - reserved, "free continuation equals derived state")
            counts["free_snapshot"] += 1
        elif (m := re.fullmatch(r"Missions and tasks using resources at: <BASE-01,0> (\d+)", body)):
            audit.require(int(m.group(1)) == booked, "using-resource continuation")
        elif (m := re.search(r"Resource transfer backorders at:.*Nbr: (\d+)", body)):
            audit.require(int(m.group(1)) == backorders, "backorder continuation")
        elif (m := re.fullmatch(r"Tasks waiting for resources at: <BASE-01,0> (\d+)", body)):
            audit.require(int(m.group(1)) == 0, "no unmatched task waiting")
        audit.require(local == 2 - departed + received, ("local conservation", number))
        audit.require(nominal == 2 - out_requests + received, ("nominal request/receipt", number))
        audit.require(0 <= booked <= local and 0 <= reserved <= local - booked, ("bounded free", number))
        audit.require(started_in + pending_receipt + received == counts["in_start"], ("IN quantity lifecycle", number))
        microsteps += 1
    audit.require(pending_book is pending_release is None and not active_tasks, "all source tasks released")
    audit.require(started_in == pending_receipt == reserved == backorders == 0 and arrived_in == received == departed == out_requests == 1, "terminal linked transfer quantities")
    audit.require(counts == {"shift_start": 1, "shift_end": 1, "book": 4, "release": 4, "backorder_add": 1,
        "backorder_remove": 1, "out_depart": 1, "out_arrive": 1, "in_start": 1, "in_arrive": 1,
        "in_receipt": 1, "free_snapshot": 2}, "complete typed quantity cardinality")
    return {"local": local, "nominal": nominal, "free": local - booked - reserved, "microsteps": microsteps}


def parent_report(audit):
    raw = (PARENT_RUN / "out_in-report-raw.json").read_bytes()
    audit.require(sha(raw) == PARENT_REPORT_SHA, "parent original report SHA")
    return parse_json(raw, native=True)


def report_topology(contract, report, canonical, audit):
    audit.require(list(report) == ["report"] and list(report["report"]) == ["tables"], "report root keys")
    audit.require(len(report["report"]["tables"]) == 6, "six report tables")
    specs = contract["report_gate"]["topology_exact"]
    for t, base, spec in zip(report["report"]["tables"], canonical["report"]["tables"], specs):
        audit.require(list(t) == list(base) == ["columns", "instances", "name"], "report table keys")
        audit.require(t["name"] == base["name"] == spec["name"], "table order/name")
        recursive_same(t["columns"], base["columns"], audit, spec["name"] + ".columns")
        audit.require([c["name"] for c in t["columns"]] == spec["columns"], "column order")
        audit.require(len(t["instances"]) == 1, "one report instance")
        audit.require(list(t["instances"][0]) == ["instance_name", "rows"], "instance keys")
        audit.require(t["instances"][0]["instance_name"] == base["instances"][0]["instance_name"] == spec["instance_name"], "instance name")
        audit.require(len(t["instances"][0]["rows"]) == spec["rows"], "report row count")
        audit.require(all(len(r) == len(t["columns"]) for r in t["instances"][0]["rows"]), "report row width")
    audit.require(sum(len(r) for t in report["report"]["tables"] for i in t["instances"] for r in i["rows"]) == 5210, "5210 report cells")


def expected_rows(contract, role):
    assert role in ("parent", "child")
    classes = contract["report_gate"]["source_event_expected"]
    rows = {}
    rows["ProblemDescription"] = [{"PDESC": contract["source_delta"]["parent_description" if role == "parent" else "child_description_predeclared"]}]
    rows["ResultSummary"] = [dict(classes["ResultSummary"])]
    systems = []
    stock = []
    resources = []
    for n in range(72):
        a, b = n / 2, (n + 1) / 2
        assigned = 2 if (7.5 <= a < 9 or 19.5 <= a < 21) else 0
        operating = 2 if (8 <= a < 9 or 20 <= a < 21) else 0
        system = {"UNID": "Total over all Units", "SID": "Total over all Systems", "STINT": a, "ETINT": b,
            "NSYRY": 2 - assigned, "NSYMA": assigned, "NSYMO": operating,
            "NSYMP": 2 if a in (7.5, 19.5) else 0, "NSYMR": 0, "NSYA": 2,
            "FTMO": operating / 2, "STACC": operating,
            "NPSTA": 2 if a in (7.5, 19.5) else 0,
            "NPSUC": 2 if a in (8, 20) else 0, "SYDT": None}
        for name in classes["SystemResults"]["field_classes"]["source_event_zero"] + classes["SystemResults"]["field_classes"]["bounded_native_presentation_zero"]:
            system[name] = 0
        systems.append(system)
        empty_stock = {"STINT": a, "ETINT": b, "PNB": 1}
        for name in classes["StockTotalResults"]["field_classes"]["exact_zero"]:
            empty_stock[name] = 0
        for name in classes["StockTotalResults"]["field_classes"]["bounded_undefined_null"]:
            empty_stock[name] = None
        stock.append(empty_stock)
        delay_end = 10.5 if role == "parent" else 10
        roster = 2 if a < 8 or a >= delay_end else 1
        nominal = 1.5 if a == 7.5 else (1 if 7.75 <= a < delay_end else 2)
        resource = {"RID": "Total over all Resources", "STID": "Total over all Stations", "STINT": a, "ETINT": b,
            "NR": roster, "NRA": roster, "NRN": nominal,
            "NRUM": 2 if a in (7.5, 19.5) else 0, "NRW": 0}
        for name in classes["ResourceResults"]["field_classes"]["source_event_zero"]:
            resource[name] = 0
        resources.append(resource)
    rows["SystemResults"] = systems
    rows["StockTotalResults"] = stock
    rows["ResourceResults"] = resources
    duration = 70 if role == "child" else 69.5
    nominal_duration = 69.75 if role == "child" else 69.25
    total = {"RID": "Total over all Resources", "STID": "Total over all Stations",
        "NR": f32(duration / 36), "NRA": f32(duration / 36), "NRN": f32(nominal_duration / 36),
        "NRUM": f32(2 / 36), "NRW": 0}
    for name in ("NRMO", "NRMA", "NRLA", "NRF", "NRRI", "NRRT", "NRRO"):
        total[name] = 0
    rows["ResourceResultsTotal"] = [total]
    return rows


def check_report(contract, role, report, canonical, audit):
    report_topology(contract, report, canonical, audit)
    expected = expected_rows(contract, role)
    checked = 0
    for t in report["report"]["tables"]:
        cols = [c["name"] for c in t["columns"]]
        role_rows = expected[t["name"]]
        audit.require(len(role_rows) == len(t["instances"][0]["rows"]), "expected row cardinality")
        for n, row in enumerate(t["instances"][0]["rows"]):
            audit.require(set(cols) == set(role_rows[n]), (t["name"], "full field classes"))
            for name, actual in zip(cols, row):
                want = role_rows[n][name]
                if type(want) is str or want is None or name == "NREP":
                    recursive_same(actual, want, audit, f"{t['name']}[{n}].{name}")
                else:
                    numeric(actual, want, audit, f"{t['name']}[{n}].{name}")
                checked += 1
    audit.require(checked == 5210, "all 5210 cells checked")
    return checked


def make_pure_child_report(contract, canonical):
    """Build an in-memory prospective fixture from formulas and pinned metadata."""
    result = copy.deepcopy(canonical)
    expected = expected_rows(contract, "child")
    for table in result["report"]["tables"]:
        columns = [c["name"] for c in table["columns"]]
        table["instances"][0]["rows"] = [[row[c] for c in columns] for row in expected[table["name"]]]
    return result


def pure_source_event_report(audit):
    contract = case_contract(audit)
    parent_source_and_raw(contract, audit)
    parent_input, child_prediction = canonical_source_and_prediction(contract, audit)
    accepted_parent_roundtrip(parent_input, audit)
    canonical = parent_report(audit)
    parent_cells = check_report(contract, "parent", canonical, canonical, audit)
    _, child_lines = predicted_log_lines(audit)
    timeline = check_typed_child_log(("\n".join(child_lines) + "\n").encode(), audit)
    child_fixture = make_pure_child_report(contract, canonical)
    child_cells = check_report(contract, "child", child_fixture, canonical, audit)
    return {"contract": contract, "prediction": child_prediction, "parent": parent_input,
        "canonical_report": canonical, "timeline": timeline,
        "parent_report_cells": parent_cells, "prospective_child_report_cells": child_cells}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pure-fixture", action="store_true")
    args = parser.parse_args()
    if not args.pure_fixture:
        raise AssertionError("actual sealed-run protocol awaits frozen manifest/runner schema; no native acceptance")
    audit = Audit()
    result = pure_source_event_report(audit)
    print(json.dumps({"decision": "STATIC_ONLY_PREDICTION", "checks": audit.checks,
        "parent_report_cells": result["parent_report_cells"],
        "prospective_child_report_cells": result["prospective_child_report_cells"],
        "timeline": result["timeline"], "native_started": False}, sort_keys=True))


if __name__ == "__main__":
    main()
