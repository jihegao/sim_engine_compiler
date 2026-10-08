"""Independent read-only I03.var05 source, physical and full-report replay.

The pure fixture is a prediction from frozen accepted evidence. Only the default
sealed mode may inspect a future original child run and issue an observed verdict.
"""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
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
    docs = lineage["required_docs"]
    audit.require(type(docs) is dict and len(docs) == 8, "eight required documents")
    for path, pin in docs.items():
        read_pin(ROOT / path, pin, audit, path)
    for record in lineage["design_history"]:
        read_pin(ROOT / record["path"], record, audit, record["path"])
    context_and_catalog(contract, audit)
    return lineage


def context_and_catalog(contract, audit):
    lineage = contract["source_lineage"]
    custody = parse_json((CASE / "context-custody.json").read_bytes())
    audit.require(custody["schema"] == "i03-var05-context-custody/v1", "context schema")
    rows = custody["records"]
    audit.require(len(rows) == 17 and len({r["original_path"] for r in rows}) == 17, "17 distinct owned context copies")
    archived = None
    for row in rows:
        audit.require(set(row) == {"original_path", "owned_copy", "bytes", "sha256", "original_if_present_must_match"}, "context row shape")
        audit.require(row["original_if_present_must_match"] is True, "original-if-present binding")
        content = read_pin(CASE / row["owned_copy"], row, audit, row["owned_copy"])
        original = ROOT / row["original_path"]
        # This one original is the live append-only catalog. Its owned selection
        # snapshot remains byte pinned; the current file is checked below by
        # typed metadata, the first 494 entries, and unique publication IDs.
        if original.exists() and row["original_path"] != "cases/simlox-air-support/publication-index-v1.json":
            original_content = original.read_bytes()
            audit.require(len(original_content) == row["bytes"] and sha(original_content) == row["sha256"], "context original " + row["original_path"])
        if row["original_path"] == "cases/simlox-air-support/publication-index-v1.json":
            archived = content
        if row["original_path"] == lineage["root_selection_receipt"]["path"]:
            audit.require(len(content) == lineage["root_selection_receipt"]["bytes"] and sha(content) == lineage["root_selection_receipt"]["sha256"], "selection receipt copy")
    audit.require(archived is not None and len(archived) == lineage["catalog_local_point_time"]["bytes"] and sha(archived) == lineage["catalog_local_point_time"]["sha256"], "owned historical catalog")
    archive_doc = parse_json(archived)
    live_doc = parse_json((ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    catalog_semantics(archive_doc, live_doc, audit)
    base = lineage["catalog_git_base_blob"]
    blob = subprocess.run(["git", "cat-file", "blob", base["oid"]], cwd=ROOT, capture_output=True, check=True).stdout
    audit.require(len(blob) == base["bytes"] and sha(blob) == base["sha256"], "distinct catalog base Git blob")
    recursive_same(parse_json(blob), archive_doc, audit, "catalog base parsed identity")


def catalog_semantics(archive_doc, live_doc, audit):
    audit.require(type(archive_doc) is type(live_doc) is dict and type(archive_doc["entries"]) is type(live_doc["entries"]) is list, "catalog typed root")
    audit.require(len(archive_doc["entries"]) == 494 and len(live_doc["entries"]) >= 494, "catalog prefix length")
    recursive_same({k: v for k, v in live_doc.items() if k != "entries"},
        {k: v for k, v in archive_doc.items() if k != "entries"}, audit, "catalog metadata")
    recursive_same(live_doc["entries"][:494], archive_doc["entries"], audit, "catalog first494")
    ids = [row["publication_id"] for row in live_doc["entries"]]
    audit.require(all(type(x) is str and x for x in ids) and len(ids) == len(set(ids)), "catalog unique IDs")


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
        audit.require(set(t) == set(base) == {"columns", "instances", "name"}, "report table key set")
        audit.require(t["name"] == base["name"] == spec["name"], "table order/name")
        recursive_same(t["columns"], base["columns"], audit, spec["name"] + ".columns")
        audit.require([c["name"] for c in t["columns"]] == spec["columns"], "column order")
        audit.require(len(t["instances"]) == 1, "one report instance")
        audit.require(set(t["instances"][0]) == {"instance_name", "rows"}, "instance key set")
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


def file_pin(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


def manifest_sources(audit):
    raw = (CASE / "prelaunch-manifest.json").read_bytes()
    manifest = parse_json(raw)
    audit.require(set(manifest) == {"schema", "run_id", "contract_sha256",
        "execution_binding_sha256", "source_count", "source_files",
        "live_catalog_prelaunch_pin", "historical_catalog_prefix_always_checked",
        "accepted_raw_records", "accepted_nonclosure_raw", "accepted_closure_records",
        "accepted_invocation_records", "new_native_runs_authorized_by_manifest",
        "independent_method_state"}, "closed manifest metadata keys")
    audit.require(manifest["schema"] == "i03-var05-in-zero-prelaunch-manifest/v1" and
        manifest["run_id"] == RUN.name and manifest["contract_sha256"] == V4_SHA,
        "frozen prelaunch manifest identity")
    audit.require(type(manifest["source_count"]) is int and
        manifest["source_count"] == len(manifest["source_files"]), "manifest source cardinality")
    audit.require(all(type(manifest[k]) is int for k in
        ("accepted_raw_records", "accepted_nonclosure_raw", "accepted_closure_records",
         "accepted_invocation_records", "historical_catalog_prefix_always_checked",
         "new_native_runs_authorized_by_manifest")), "manifest category integer types")
    audit.require((manifest["accepted_raw_records"], manifest["accepted_nonclosure_raw"],
        manifest["accepted_closure_records"], manifest["accepted_invocation_records"],
        manifest["historical_catalog_prefix_always_checked"],
        manifest["new_native_runs_authorized_by_manifest"]) == (112, 101, 7, 4, 494, 0),
        "manifest accepted custody and authorization boundary")
    audit.require(manifest["independent_method_state"] ==
        "exact methods pinned; fresh approval required",
        "manifest does not itself authorize native execution")
    rows = manifest["source_files"]
    audit.require(type(rows) is list and all(type(row) is dict and
        set(row) == {"key", "path", "bytes", "sha256"} for row in rows),
        "exact manifest source record shape")
    keys = [row["key"] for row in rows]
    paths = [row["path"] for row in rows]
    audit.require(len(keys) == len(set(keys)) and len(paths) == len(set(paths)),
        "unique manifest roles and files")
    required = {"child_contract": CASE / "contract.json",
        "execution_binding": CASE / "execution-contract.json",
        "child_input": CASE / "native-input.json",
        "behavior_validator": CASE / "validate_native_cli.py",
        "runner_script": CASE / "run_native_ssh.ps1",
        "independent_replay": CASE / "review/independent_replay.py",
        "independent_self_check": CASE / "review/independent_self_check.py"}
    indexed = {row["key"]: row for row in rows}
    audit.require(set(required) <= set(indexed), "all active roles source pinned")
    audit.require(not any(Path(p) == ROOT / "cases/simlox-air-support/publication-index-v1.json"
        for p in paths), "mutable live catalog excluded from immutable source map")
    source_map = {}
    for row in rows:
        audit.require(type(row["key"]) is str and type(row["path"]) is str and
            Path(row["path"]).is_absolute() and type(row["bytes"]) is int and
            row["bytes"] >= 0 and type(row["sha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
            "manifest source scalar types")
        audit.require(file_pin(row["path"]) ==
            {"bytes": row["bytes"], "sha256": row["sha256"]},
            "manifest source original bytes " + row["key"])
        source_map[row["key"]] = row["sha256"]
    for key, path in required.items():
        audit.require(Path(indexed[key]["path"]) == path, "active manifest role path " + key)
    audit.require("owned_source_inventory" in indexed and
        Path(indexed["owned_source_inventory"]["path"]) == CASE / "source-inventory.json",
        "frozen closed owned inventory role")
    inventory = parse_json((CASE / "source-inventory.json").read_bytes())
    audit.require(inventory["schema"] == "i03-var05-in-zero-owned-source-inventory/v1" and
        type(inventory["source_count"]) is int and
        inventory["source_count"] == len(inventory["source_files"]) and
        type(inventory["provisional_independent_methods_absent"]) is bool and
        not inventory["provisional_independent_methods_absent"],
        "final owned inventory topology")
    by_path = {row["path"]: row for row in rows}
    for record in inventory["source_files"]:
        audit.require(type(record) is dict and
            set(record) == {"relative_path", "path", "bytes", "sha256"} and
            Path(record["path"]) == CASE / record["relative_path"] and
            record["path"] in by_path and
            all(by_path[record["path"]][key] == record[key]
                for key in ("path", "bytes", "sha256")),
            "each owned closed-inventory pin appears exact in manifest")
    audit.require(source_map["child_contract"] == V4_SHA and
        source_map["child_input"] == sha((CASE / "native-input.json").read_bytes()) and
        source_map["execution_binding"] == manifest["execution_binding_sha256"],
        "contract/input/execution-binding identities")
    live_pin = manifest["live_catalog_prelaunch_pin"]
    historical_live = parse_json((CASE / "contract.json").read_bytes())["source_lineage"]["catalog_local_point_time"]
    audit.require(type(live_pin) is dict and set(live_pin) == {"path", "bytes", "sha256"} and
        Path(live_pin["path"]) == ROOT / "cases/simlox-air-support/publication-index-v1.json" and
        type(live_pin["bytes"]) is int and type(live_pin["sha256"]) is str and
        {key: live_pin[key] for key in ("bytes", "sha256")} == historical_live,
        "separate point-time live catalog identity")
    source_map_sha = sha(json.dumps(source_map, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8"))
    return raw, manifest, source_map, source_map_sha


def approval_fields(approval, manifest_raw, source_map, source_map_sha, audit):
    audit.require(approval["schema"] == "i03-var05-in-zero-independent-prelaunch-go/v1" and
        approval["decision"] == "GO_PRELAUNCH" and approval["run_id"] == RUN.name,
        "independent prelaunch decision and run identity")
    expected = {"manifest_sha256": sha(manifest_raw),
        "runner_sha256": source_map["runner_script"],
        "validator_sha256": source_map["behavior_validator"],
        "contract_sha256": V4_SHA,
        "execution_binding_sha256": source_map["execution_binding"],
        "input_sha256": source_map["child_input"],
        "source_map_sha256": source_map_sha,
        "independent_replay_sha256": source_map["independent_replay"]}
    for key, value in expected.items():
        audit.require(approval[key] == value, "approval binds " + key)


def preflight_fields(preflight, manifest_raw, source_map, source_map_sha, audit):
    audit.require(set(preflight) == {"schema", "run_id", "run_dirs_absent",
        "ssh_session", "ps_major", "ssh_ancestors", "mutex_free",
        "wts_active_gui_count", "gui", "accepted_raw_seals",
        "accepted_nonclosure_raw", "accepted_closures", "accepted_invocations",
        "excluded_failed_witness_raw", "total_original_raw", "manifest_sha256",
        "source_map_sha256", "source_hashes", "native_process_started"},
        "closed preflight receipt metadata keys")
    audit.require(preflight["schema"] == "i03-var05-in-zero-ssh-preflight/v1" and
        preflight["run_id"] == RUN.name and
        preflight["manifest_sha256"] == sha(manifest_raw) and
        preflight["source_map_sha256"] == source_map_sha,
        "actual SSH preflight source/run binding")
    recursive_same(preflight["source_hashes"], source_map, audit, "preflight source map")
    audit.require(type(preflight["ssh_session"]) is int and preflight["ssh_session"] == 0 and
        type(preflight["ps_major"]) is int and preflight["ps_major"] == 5 and
        type(preflight["mutex_free"]) is bool and preflight["mutex_free"] and
        type(preflight["run_dirs_absent"]) is bool and preflight["run_dirs_absent"] and
        type(preflight["native_process_started"]) is bool and not preflight["native_process_started"] and
        type(preflight["wts_active_gui_count"]) is int and preflight["wts_active_gui_count"] == 1 and
        type(preflight["ssh_ancestors"]) is list and
        "sshd.exe" in preflight["ssh_ancestors"],
        "actual zero-native SSH5 session0 and mutex guards")
    gui = preflight["gui"]
    audit.require(type(gui["pid"]) is int and gui["pid"] == 13340 and
        type(gui["session_id"]) is int and gui["session_id"] == 1 and
        type(gui["start_unix_ms"]) is int and gui["start_unix_ms"] == 1790590196826 and
        type(gui["responding"]) is bool and gui["responding"],
        "protected GUI exact preflight identity")
    for key, value in (("accepted_raw_seals", 112), ("accepted_nonclosure_raw", 101),
        ("accepted_closures", 7), ("accepted_invocations", 4),
        ("excluded_failed_witness_raw", 0), ("total_original_raw", 112)):
        audit.require(type(preflight[key]) is int and preflight[key] == value,
            "preflight original custody count " + key)


def preflight_and_approval(manifest_raw, manifest, source_map, source_map_sha, audit):
    approval_raw = (CASE / "review/independent-prelaunch-go.json").read_bytes()
    approval = parse_json(approval_raw)
    approval_fields(approval, manifest_raw, source_map, source_map_sha, audit)
    relative = approval["preflight_relative_path"]
    audit.require(type(relative) is str and
        re.fullmatch(r"review[\\/]preflight-ssh0-\d{8}T\d{9}Z\.json", relative) is not None,
        "direct unique preflight receipt path")
    preflight_path = CASE / relative
    audit.require(preflight_path.resolve().parent == (CASE / "review").resolve() and
        not preflight_path.is_symlink(), "preflight path stays in owned review")
    preflight_raw = preflight_path.read_bytes()
    audit.require(sha(preflight_raw) == approval["preflight_sha256"],
        "approval pins original preflight bytes")
    preflight = parse_json(preflight_raw)
    preflight_fields(preflight, manifest_raw, source_map, source_map_sha, audit)
    return approval_raw, approval, preflight_raw, preflight, preflight_path


def planned_steps():
    exe = r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"
    python = r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    q = lambda filename: '"' + str(RUN / filename) + '"'
    checker = lambda filename: '"' + str(CASE / filename) + '"'
    runq = '"' + str(RUN) + '"'
    return [
        {"name": "import", "program": exe,
         "arguments": f'-silent -jimport {q("input.json")} -save {q("model.sxi")} -log {q("import.log")} -close'},
        {"name": "export", "program": exe,
         "arguments": f'{q("model.sxi")} -silent -jexport {q("roundtrip-raw.json")} -log {q("export.log")} -close'},
        {"name": "check_import_export", "program": python,
         "arguments": f'-X utf8 -B {checker("check_roundtrip.py")} {runq}'},
        {"name": "calc", "program": exe,
         "arguments": f'{q("model.sxi")} -silent -threads 1 -calc -log {q("model-run.log")} -close'},
        {"name": "jsonreport", "program": exe,
         "arguments": f'{q("model.sxo")} -silent -jsonreport {q("report-raw.json")} -log {q("report-export.log")} -close'},
        {"name": "check_behavior", "program": python,
         "arguments": f'-X utf8 -B {checker("validate_native_cli.py")} {runq}'}]


def iso_utc(value, audit, label):
    audit.require(type(value) is str, label + " timestamp type")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    audit.require(instant.tzinfo is not None and
        instant.utcoffset().total_seconds() == 0, label + " UTC")
    return instant


def check_converter_log(raw, audit):
    content = raw.decode("utf-8-sig")
    for label, name in (("Input file", "model.sxi"),
                        ("Output file", "model.sxo"), ("File", "model.sxi")):
        found = re.findall(r"(?m)^" + re.escape(label) + r": ([^\r\n]+)\r?$", content)
        audit.require(len(found) == 1 and found[0].replace("\\", "/") ==
            str(RUN / name).replace("\\", "/"), "converter selected run " + label)
    audit.require(len(re.findall(
        r"(?m)^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0\r?$",
        content)) == 1, "converter exact 0/2/0")
    warning_blocks = re.findall(r"(?m)^Form: ([^\r\n]+)\r?\n(rec [^\r\n]+)\r?$", content)
    audit.require(warning_blocks == [
        ("Control", "rec 1: (warning #108) Enabling simulation log may generate extensive data in log file"),
        ("System", "rec 1: (warning #126) This system contains no items: TEACH-AIR-01")],
        "two ordered source-bound converter warnings")
    audit.require(re.findall(r"(?i)\b(warning|error|notice|note)\s*#(\d+)", content) ==
        [("warning", "108"), ("warning", "126")], "no extra converter diagnostic code")
    audit.require(len(re.findall(r"(?m)^Form: ", content)) == 2 and
        len(re.findall(r"(?m)^rec ", content)) == 2, "no extra converter diagnostic row")


def calc_seal_fields(calc, closure_record, disk_record, readonly, audit):
    seal = {"bytes": calc["converter_log_bytes"],
        "sha256": calc["converter_log_sha256"]}
    audit.require(type(calc["converter_log_bytes"]) is int and
        type(calc["converter_log_sha256"]) is str and
        type(calc["converter_log_validated"]) is bool and
        calc["converter_log_validated"] and
        type(readonly) is bool and readonly and
        seal == closure_record == disk_record,
        "calc immediate converter seal equals closure, disk and ReadOnly")


def run_inventory_and_steps(manifest_raw, source_map, approval_raw, approval,
                            preflight_raw, preflight_path, audit):
    audit.require(RUN.is_dir(), "unique original sealed child run exists")
    files = {p.name: p for p in RUN.iterdir() if p.is_file()}
    names = {"input.json", "model.sxi", "import.log", "roundtrip-raw.json",
        "export.log", "roundtrip-validation.json", "model.sxo", "model.log",
        "model-run.log", "report-raw.json", "report-export.log",
        "author-validation.json", "steps.json", "invocation.json", "closure.json"}
    names |= {name + "-stderr.txt" for name in
        ("import", "export", "check_import_export", "calc", "jsonreport", "check_behavior")}
    names |= {name + "-stdout.txt" for name in ("import", "export", "calc", "jsonreport")}
    audit.require(set(files) == names and len(files) == 25 and
        "failure-seal.json" not in files, "closed successful 25-file native inventory")
    invocation_raw, closure_raw = files["invocation.json"].read_bytes(), files["closure.json"].read_bytes()
    invocation, closure = parse_json(invocation_raw), parse_json(closure_raw)
    audit.require(set(invocation) == {"schema", "run_id", "created_utc",
        "original_run_dir", "input_sha256", "contract_sha256", "manifest_sha256",
        "approval_sha256", "approved_preflight_path", "approved_preflight_sha256",
        "independent_replay_sha256", "runner_script_sha256", "session_id",
        "ssh_ancestors", "gui", "queue_mutex", "working_directory",
        "planned_commands", "planned_checkers", "source_hashes_before",
        "publication_state"} and
        set(closure) == {"schema", "run_id", "invocation_sha256", "manifest_sha256",
        "approval_sha256", "approved_preflight_sha256", "source_hashes_before",
        "source_hashes_after", "raw", "step_error", "error", "publication_state"},
        "closed invocation and closure metadata keys")
    audit.require(invocation["schema"] == "i03-var05-in-zero-invocation/v1" and
        closure["schema"] == "i03-var05-in-zero-closure/v1" and
        invocation["run_id"] == closure["run_id"] == RUN.name and
        Path(invocation["original_run_dir"]) == RUN,
        "native invocation and closure run identity")
    audit.require(type(invocation["session_id"]) is int and invocation["session_id"] == 0 and
        type(invocation["ssh_ancestors"]) is list and
        "sshd.exe" in invocation["ssh_ancestors"] and
        invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
        invocation["working_directory"] ==
        r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace",
        "actual SSH0 ancestry, native queue and fixed workspace")
    gui = invocation["gui"]
    audit.require(type(gui["pid"]) is int and gui["pid"] == 13340 and
        type(gui["session_id"]) is int and gui["session_id"] == 1 and
        type(gui["start_unix_ms"]) is int and gui["start_unix_ms"] == 1790590196826 and
        type(gui["responding"]) is bool and gui["responding"],
        "protected GUI invocation identity")
    for key, wanted in (("manifest_sha256", sha(manifest_raw)),
        ("approval_sha256", sha(approval_raw)),
        ("approved_preflight_sha256", sha(preflight_raw))):
        audit.require(invocation[key] == closure[key] == wanted, "invocation/closure " + key)
    audit.require(invocation["approved_preflight_path"] == str(preflight_path) and
        invocation["independent_replay_sha256"] == source_map["independent_replay"] and
        invocation["runner_script_sha256"] == source_map["runner_script"] and
        invocation["contract_sha256"] == V4_SHA and
        invocation["input_sha256"] == source_map["child_input"] and
        closure["invocation_sha256"] == sha(invocation_raw),
        "approved exact preflight/method/input/runner/invocation chain")
    recursive_same(invocation["source_hashes_before"], source_map, audit, "source before invocation")
    recursive_same(closure["source_hashes_before"], source_map, audit, "source before closure")
    recursive_same(closure["source_hashes_after"], source_map, audit, "source after closure")
    audit.require(closure["error"] in (None, "") and closure["step_error"] in (None, "") and
        closure["publication_state"] == invocation["publication_state"] == "not_published",
        "successful run and no premature publication")
    raw = closure["raw"]
    audit.require(type(raw) is dict and set(raw) == names - {"invocation.json", "closure.json"} and
        len(raw) == 23, "closure full 23-file original raw inventory")
    for name, rec in raw.items():
        audit.require(type(rec) is dict and set(rec) == {"bytes", "sha256"} and
            type(rec["bytes"]) is int and type(rec["sha256"]) is str and
            file_pin(files[name]) == rec, "closure raw " + name)
    steps = parse_json(files["steps.json"].read_bytes())
    plan = planned_steps()
    audit.require(type(steps) is list and len(steps) == len(plan) == 6,
        "six ordered actual native/checker stages")
    recursive_same(invocation["planned_commands"],
        [plan[i] for i in (0, 1, 3, 4)], audit, "four exact native planned argv")
    recursive_same(invocation["planned_checkers"],
        [plan[i] for i in (2, 5)], audit, "two exact checker planned argv")
    previous_end = None
    for index, (step, planned) in enumerate(zip(steps, plan)):
        audit.require(set(step) == {"sequence", "name", "program", "arguments",
            "started_utc", "completed_utc", "child_pid", "child_session_id",
            "exit_code", "capture_error", "stdout_path", "stderr_path",
            "stdout_bytes", "stderr_bytes", "stdout_sha256", "stderr_sha256",
            "converter_log_bytes", "converter_log_sha256", "converter_log_validated",
            "gui_preserved", "status", "error"},
            "closed stage metadata keys " + str(index))
        audit.require(type(step["sequence"]) is int and step["sequence"] == index and
            all(step[key] == planned[key] for key in ("name", "program", "arguments")),
            "actual step sequence/program/argv " + str(index))
        started = iso_utc(step["started_utc"], audit, "step started " + str(index))
        ended = iso_utc(step["completed_utc"], audit, "step ended " + str(index))
        audit.require(started <= ended and (previous_end is None or previous_end <= started),
            "natural serial UTC intervals " + str(index))
        previous_end = ended
        audit.require(type(step["child_pid"]) is int and step["child_pid"] > 0 and
            type(step["child_session_id"]) is int and step["child_session_id"] == 0 and
            type(step["exit_code"]) is int and step["exit_code"] == 0 and
            step["capture_error"] is None and step["status"] == "completed" and
            step["error"] is None and type(step["gui_preserved"]) is bool and
            step["gui_preserved"], "natural child/session/exit/capture/GUI " + str(index))
        stdout_name = ("roundtrip-validation.json" if index == 2 else
            "author-validation.json" if index == 5 else step["name"] + "-stdout.txt")
        stderr_name = step["name"] + "-stderr.txt"
        audit.require(Path(step["stdout_path"]) == RUN / stdout_name and
            Path(step["stderr_path"]) == RUN / stderr_name,
            "original named binary stdout/stderr " + step["name"])
        for kind, name in (("stdout", stdout_name), ("stderr", stderr_name)):
            audit.require(type(step[kind + "_bytes"]) is int and
                type(step[kind + "_sha256"]) is str and
                {"bytes": step[kind + "_bytes"], "sha256": step[kind + "_sha256"]} ==
                raw[name] == file_pin(files[name]),
                "original binary stream pin " + step["name"] + ":" + kind)
        audit.require(files[stderr_name].read_bytes() == b"", "empty original stage stderr")
    calc = steps[3]
    calc_seal_fields(calc, raw["model-run.log"], file_pin(files["model-run.log"]),
        bool(os.stat(files["model-run.log"]).st_file_attributes & 1), audit)
    for index in (0, 1, 2, 4, 5):
        audit.require(steps[index]["converter_log_bytes"] is None and
            steps[index]["converter_log_sha256"] is None and
            type(steps[index]["converter_log_validated"]) is bool and
            not steps[index]["converter_log_validated"],
            "converter seal confined to calc step")
    check_converter_log(files["model-run.log"].read_bytes(), audit)
    return files, raw, steps


def sealed_content(pure, source_map, files, raw, audit):
    input_raw = files["input.json"].read_bytes()
    audit.require(sha(input_raw) == source_map["child_input"], "actual copied child source bytes")
    recursive_same(parse_json(input_raw), pure["prediction"], audit, "actual child source")
    check_roundtrip(pure["prediction"], files["roundtrip-raw.json"].read_bytes(), audit)
    roundtrip = parse_json(files["roundtrip-validation.json"].read_bytes())
    audit.require(set(roundtrip) == {"schema", "passed", "issues", "input_sha256",
        "export_sha256", "table_objects", "row_containing_tables",
        "all_null_placeholder_tables"}, "closed roundtrip checker receipt")
    audit.require(roundtrip["schema"] == "i03-var05-in-zero-roundtrip/v1" and
        type(roundtrip["passed"]) is bool and roundtrip["passed"] and
        roundtrip["issues"] == [] and
        roundtrip["input_sha256"] == source_map["child_input"] and
        roundtrip["export_sha256"] == raw["roundtrip-raw.json"]["sha256"],
        "native roundtrip checker receipt success and exact input/export")
    for key, value in (("table_objects", 32), ("row_containing_tables", 21),
                       ("all_null_placeholder_tables", 11)):
        audit.require(type(roundtrip[key]) is int and roundtrip[key] == value,
            "native roundtrip topology " + key)
    for filename, marker in (("import.log", b"Import completed!"),
                             ("export.log", b"Export completed!")):
        audit.require(marker in files[filename].read_bytes(), "native converter " + filename)
    timeline = check_typed_child_log(files["model.log"].read_bytes(), audit)
    report = parse_json(files["report-raw.json"].read_bytes(), native=True)
    cells = check_report(pure["contract"], "child", report, pure["canonical_report"], audit)
    parent_tables = pure["canonical_report"]["report"]["tables"]
    child_tables = report["report"]["tables"]
    differences = []
    for ptable, ctable in zip(parent_tables, child_tables):
        fields = [column["name"] for column in ptable["columns"]]
        for row_index, (prow, crow) in enumerate(zip(ptable["instances"][0]["rows"],
                                                   ctable["instances"][0]["rows"])):
            for field, parent_cell, child_cell in zip(fields, prow, crow):
                if parent_cell != child_cell:
                    differences.append((ptable["name"], row_index, field))
    expected_differences = [("ProblemDescription", 0, "PDESC")]
    expected_differences.extend(("ResourceResults", 20, field) for field in ("NR", "NRA", "NRN"))
    expected_differences.extend(("ResourceResultsTotal", 0, field) for field in ("NR", "NRA", "NRN"))
    audit.require(differences == expected_differences,
        "exact seven source/event derived report differences")
    behavior = parse_json(files["author-validation.json"].read_bytes())
    audit.require(set(behavior) == {"schema", "passed", "issues", "run_id",
        "input_sha256", "report_cell_checks", "typed_event_records", "timeline"},
        "closed behavior checker receipt")
    audit.require(behavior["schema"] == "i03-var05-in-zero-behavior/v1" and
        type(behavior["passed"]) is bool and behavior["passed"] and
        behavior["issues"] == [] and behavior["run_id"] == RUN.name and
        behavior["input_sha256"] == source_map["child_input"] and
        type(behavior["report_cell_checks"]) is int and behavior["report_cell_checks"] == 5210 and
        type(behavior["typed_event_records"]) is int and behavior["typed_event_records"] == 184,
        "author checker receipt exact result identity")
    btl = behavior["timeline"]
    for key, value in (("out_request", 7.75), ("out_departure", 8),
                       ("in_start", 10), ("in_task_arrival", 10),
                       ("in_local_receipt", 10), ("terminal_local", 2),
                       ("terminal_ready", 2), ("raw_lines", 250),
                       ("timed_events", 184)):
        audit.require(type(btl[key]) in (int, float) and btl[key] == value,
            "author timeline agrees with bounded independent state " + key)
    terminal = btl["microstates"]["terminal"]
    for key, value in (("local", 2), ("nominal", 2), ("booked", 0),
                       ("reserved_OUT", 0), ("departed_OUT", 1),
                       ("IN_started_unarrived", 0), ("IN_task_arrived", 1),
                       ("IN_pending_local_receipt", 0), ("locally_received_IN", 1)):
        audit.require(type(terminal[key]) is int and terminal[key] == value,
            "author terminal task-linked quantity " + key)
    return {"parent_report_cells": pure["parent_report_cells"],
        "child_report_cells": cells, "paired_cell_differences": len(differences),
        "original_run_files": len(files), "original_raw_files": len(raw),
        "native_and_checker_stages": 6, "timeline": timeline}


def sealed_replay(audit):
    pure = pure_source_event_report(audit)
    manifest_raw, manifest, source_map, source_map_sha = manifest_sources(audit)
    approval_raw, approval, preflight_raw, preflight, preflight_path = \
        preflight_and_approval(manifest_raw, manifest, source_map, source_map_sha, audit)
    files, raw, steps = run_inventory_and_steps(manifest_raw, source_map, approval_raw,
        approval, preflight_raw, preflight_path, audit)
    return sealed_content(pure, source_map, files, raw, audit)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pure-fixture", action="store_true")
    args = parser.parse_args()
    audit = Audit()
    if args.pure_fixture:
        result = pure_source_event_report(audit)
        verdict = {"decision": "STATIC_ONLY_PREDICTION", "checks": audit.checks,
            "parent_report_cells": result["parent_report_cells"],
            "prospective_child_report_cells": result["prospective_child_report_cells"],
            "timeline": result["timeline"], "native_started": False}
    else:
        result = sealed_replay(audit)
        verdict = {"decision": "GO_BOUNDED", "checks": audit.checks, **result}
    print(json.dumps(verdict, sort_keys=True))


if __name__ == "__main__":
    main()
