"""Independent prospective I03.var11 source/event/report replay.

The child branch uses a pure fixture until original child raw exists.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import struct
import subprocess
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = next(p for p in PKG.parents if (p / ".git").exists())
BASE = "50c552285f69e0b5a8bf82a8cdc6999b9e68f7cf"
CONTRACT_SHA = "67bef26d4fdec4d34e88b20e177239fb973aeba7152f72d26d4d9f9a4f9a79c1"
V100_PKG = PKG
PARENT_PKG = REPO / "cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2"
PARENT_RUN = PARENT_PKG / "runs/i03-var02-idle-out-v102-ssh-20261007-01"
CHILD_RUN = PKG / "runs/i03-var11-out-unarrived-v100-ssh-20261008-01"


class Audit:
    def __init__(self):
        self.checks = 0

    def ok(self, fact, label):
        self.checks += 1
        if not fact:
            raise AssertionError(label)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def exact(path, rec, a, label):
    raw = path.read_bytes()
    a.ok(pin(raw) == {"bytes": rec["bytes"], "sha256": rec["sha256"]}, label)
    return raw


_GIT_BLOBS = None


def git_blob(path):
    global _GIT_BLOBS
    if _GIT_BLOBS is None:
        _GIT_BLOBS = {}
        for entry in subprocess.check_output(["git", "ls-tree", "-r", "-z", BASE], cwd=REPO).split(b"\0"):
            if not entry:
                continue
            metadata, encoded_path = entry.split(b"\t", 1)
            _, kind, oid = metadata.split()
            if kind == b"blob":
                _GIT_BLOBS[encoded_path.decode("utf-8")] = oid.decode("ascii")
    return subprocess.check_output(["git", "cat-file", "blob", _GIT_BLOBS[path]], cwd=REPO)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def same_type(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_type(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same_type(x, y) for x, y in zip(a, b))
    return a == b


def check_catalog_archive(old_catalog, live_catalog, a):
    a.ok(set(old_catalog) == set(live_catalog) and
         type(old_catalog["entries"]) is type(live_catalog["entries"]) is list and
         len(old_catalog["entries"]) == 492 and len(live_catalog["entries"]) >= 492,
         "exact historical catalog shape and append-only length")
    a.ok(same_type(old_catalog["entries"], live_catalog["entries"][:492]),
         "typed historical catalog prefix")
    a.ok(same_type({k: v for k, v in old_catalog.items() if k != "entries"},
                   {k: v for k, v in live_catalog.items() if k != "entries"}),
         "typed unchanged historical catalog metadata")
    ids = [e["publication_id"] for e in live_catalog["entries"]]
    a.ok(len(ids) == len(set(ids)) and all(type(x) is str and x for x in ids),
         "unique typed catalog publication IDs")


def numeric(actual, expected):
    return (type(actual) in (int, float) and type(expected) in (int, float)
            and math.isfinite(actual) and math.isfinite(expected) and actual == expected)


def native_json(raw):
    text = raw.decode("utf-8-sig")
    # Remove native trailing commas only while outside strings. Raw bytes remain
    # untouched, including BOM, line endings and the exporter's final comma.
    out = []
    quoted = escaped = False
    for i, ch in enumerate(text):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == "," and i + 1 < len(text) and re.match(r"\s*[}\]]", text[i + 1:]):
            continue
        else:
            out.append(ch)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def no_constant(value):
        raise ValueError("nonfinite JSON number: " + value)
    doc = json.loads("".join(out), object_pairs_hook=unique, parse_constant=no_constant)
    def finite_tree(value):
        if type(value) is float and not math.isfinite(value):
            raise ValueError("nonfinite JSON float")
        if type(value) is dict:
            for child in value.values():
                finite_tree(child)
        elif type(value) is list:
            for child in value:
                finite_tree(child)
    finite_tree(doc)
    return doc


def tables(doc, root):
    return doc[root]["tables"]


def source_tables(doc, root, a):
    arr = tables(doc, root)
    names = [t["name"] for t in arr]
    a.ok(len(names) == len(set(names)) == 32, f"{root}: 32 unique tables")
    for t in arr:
        names_i = [x["instance_name"] for x in t["instances"]]
        a.ok(len(names_i) == len(set(names_i)), f"{root}/{t['name']}: unique instances")
    return {t["name"]: t for t in arr}


def parent_and_prediction(contract, a):
    src = REPO / contract["source_delta"]["parent_input"]["path"]
    raw = src.read_bytes()
    a.ok(pin(raw) == {"bytes": contract["source_delta"]["parent_input"]["bytes"],
                      "sha256": contract["source_delta"]["parent_input"]["sha256"]}, "parent input")
    parent = json.loads(raw)
    source_tables(parent, "model", a)
    a.ok(parent["model"]["database_version"] == 20160627, "database version")
    predicted = deepcopy(parent)
    for t in predicted["model"]["tables"]:
        if t["name"] == "ProblemDescription":
            t["instances"][0]["rows"][0][0] = contract["source_delta"]["allowed_changes_exactly"][0]["to"]
        elif t["name"] == "ResourceTransfer":
            t["instances"][0]["rows"][0][5] = 40.0
    different = []
    for old, new in zip(parent["model"]["tables"], predicted["model"]["tables"]):
        if old != new:
            different.append(old["name"])
    a.ok(different == ["ProblemDescription", "ResourceTransfer"], "sole two source tables")
    transfer = source_tables(predicted, "model", a)["ResourceTransfer"]["instances"][0]["rows"]
    a.ok(transfer == [contract["source_delta"]["child_transfer_row"]], "child transfer source")
    return parent, predicted


def child_input_check(predicted, child, a):
    a.ok(set(child) == {"model"} and set(child["model"]) ==
         {"database_version", "tables"}, "child source root metadata")
    left = source_tables(predicted, "model", a)
    right = source_tables(child, "model", a)
    a.ok([t["name"] for t in tables(predicted, "model")] ==
         [t["name"] for t in tables(child, "model")], "child exact ordered 32 tables")
    a.ok(same_type(predicted["model"], child["model"]),
         "child every source cell and metadata from two-cell predicted delta")
    a.ok(set(left) == set(right), "child table set")


def roundtrip(authored, exported, a, label):
    a.ok(set(authored) == set(exported) == {"model"}, label + " root keys")
    a.ok(set(authored["model"]) == set(exported["model"]) ==
         {"database_version", "tables"}, label + " model keys")
    left = source_tables(authored, "model", a)
    right = source_tables(exported, "model", a)
    a.ok(authored["model"]["database_version"] == exported["model"]["database_version"],
         label + " database version")
    a.ok([t["name"] for t in tables(authored, "model")] ==
         [t["name"] for t in tables(exported, "model")], label + " ordered table names")
    for name, source in left.items():
        target = right[name]
        a.ok(set(target) == set(source) == {"name", "columns", "instances"},
             label + "/" + name + " table keys")
        a.ok(same_type(source["columns"], target["columns"]), label + "/" + name + " columns")
        a.ok([i["instance_name"] for i in source["instances"]] ==
             [i["instance_name"] for i in target["instances"]], label + "/" + name + " instances")
        a.ok(len(source["instances"]) == len(target["instances"]), label + "/" + name + " instance count")
        for x, y in zip(source["instances"], target["instances"]):
            a.ok(set(x) == set(y) == {"instance_name", "rows"},
                 label + "/" + name + " instance keys")
            sr, er = x["rows"], y["rows"]
            if not sr:
                a.ok(len(er) == 1 and er[0] == [None] * len(source["columns"]),
                     label + "/" + name + " null placeholder")
            else:
                a.ok(len(sr) == len(er), label + "/" + name + " row count")
                for i, (srow, erow) in enumerate(zip(sr, er)):
                    a.ok(len(srow) == len(erow) == len(source["columns"]),
                         f"{label}/{name}/{i} width")
                    for j, (s, e) in enumerate(zip(srow, erow)):
                        dtype = source["columns"][j]["datatype"]
                        good = numeric(e, s) if dtype in ("float", "int", "integer", "double") and s is not None else same_type(e, s)
                        a.ok(good, f"{label}/{name}/{i}/{j}")


def interval_fraction(start, end, left, right):
    return max(0, min(end, right) - max(start, left)) / (right - left)


def source_prediction():
    return {"out_departure": 6,
            "waves": [
                {"start": 7.5, "first_end": 8, "last_end": 8.5, "launch": 8.5,
                 "end": 9.5, "bookings": [(7.5, 8), (8, 8.5)], "waits": [(7.5, 8)]},
                {"start": 19.5, "first_end": 20, "last_end": 20.5, "launch": 20.5,
                 "end": 21.5, "bookings": [(19.5, 20), (20, 20.5)], "waits": [(19.5, 20)]}]}


def expected_report(contract, model, role, timeline=None):
    assert role in ("parent", "child")
    topology = contract["report_gate"]["topology"]
    template = {t["name"]: t for t in topology}
    desc = next(t for t in model["model"]["tables"] if t["name"] == "ProblemDescription")["instances"][0]["rows"][0][0]
    assert timeline is not None, "report needs independent typed event timeline"
    assert {k: timeline[k] for k in ("out_departure", "waves")} == source_prediction(), \
        "native timeline differs from frozen source prediction"
    assert timeline.get("out_arrival") == (None if role == "child" else 6), \
        "native linked OUT task completion differs from prospective branch"
    waves = timeline["waves"]
    system, stock, resource = [], [], []
    system_zero = contract["report_gate"]["system_field_classes"]["source_event_zero"] + contract["report_gate"]["system_field_classes"]["bounded_native_presentation_zero"]
    resource_zero = contract["report_gate"]["resource_fields"]["source_event_zero"]
    stock_zero = contract["report_gate"]["stock_fields"]["exact_zero"]
    stock_null = contract["report_gate"]["stock_fields"]["bounded_undefined_null"]
    for i in range(72):
        t = i / 2
        s = {k: 0 for k in system_zero}
        s.update(UNID="Total over all Units", SID="Total over all Systems", STINT=t, ETINT=t + .5,
                 NSYRY=2, NSYMA=0, NSYMO=0, NSYMP=0, NSYMR=0, NSYA=2, FTMO=0,
                 STACC=0, SYDT=None, NPSTA=0, NPSUC=0)
        assigned = sum(2 * interval_fraction(w["start"], w["end"], t, t + .5) for w in waves)
        mission = sum(2 * interval_fraction(w["launch"], w["end"], t, t + .5) for w in waves)
        work_wait = sum(sum(interval_fraction(x, y, t, t + .5) for x, y in w["bookings"]) +
                        sum(interval_fraction(x, y, t, t + .5) for x, y in w["waits"]) for w in waves)
        prepared = sum(interval_fraction(w["first_end"], w["launch"], t, t + .5) for w in waves)
        s.update(NSYRY=2 - assigned, NSYMA=assigned, NSYMO=mission, NSYMP=work_wait,
                 NSYMR=prepared, FTMO=mission / 2, STACC=mission,
                 NPSTA=sum(2 for w in waves if t <= w["start"] < t + .5),
                 NPSUC=sum((t <= w["first_end"] < t + .5) +
                            (t <= w["last_end"] < t + .5) for w in waves))
        system.append(s)
        q = {k: 0 for k in stock_zero}
        q.update(STINT=t, ETINT=t + .5, PNB=1)
        q.update({k: None for k in stock_null})
        stock.append(q)
        r = {k: 0 for k in resource_zero}
        physical = 2 - interval_fraction(timeline["out_departure"], 36, t, t + .5)
        nominal = 2 - interval_fraction(6, 36, t, t + .5)
        use = sum(interval_fraction(x, y, t, t + .5) for w in waves for x, y in w["bookings"])
        wait = sum(interval_fraction(x, y, t, t + .5) for w in waves for x, y in w["waits"])
        r.update(RID="Total over all Resources", STID="Total over all Stations", STINT=t, ETINT=t + .5,
                 NR=physical, NRA=physical, NRN=nominal, NRUM=use, NRW=wait)
        resource.append(r)
    total = {k: 0 for k in resource_zero}
    total.update(RID="Total over all Resources", STID="Total over all Stations")
    for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        total[field] = f32(sum(row[field] * .5 for row in resource) / 36)
    integrals = {name: sum(row[name] * .5 for row in system)
                 for name in contract["report_gate"]["source_event_integrals_aircraft_hours"]}
    assert integrals == contract["report_gate"]["source_event_integrals_aircraft_hours"]
    assert {name: total[name] for name in contract["report_gate"]["resource_fields"]["total_expected_float32"]} == \
        contract["report_gate"]["resource_fields"]["total_expected_float32"]
    summary = contract["report_gate"]["result_summary_expected"]
    expected = {"ProblemDescription": [{"PDESC": desc}], "ResultSummary": [summary],
                "SystemResults": system, "StockTotalResults": stock,
                "ResourceResults": resource, "ResourceResultsTotal": [total]}
    assert [len(expected[t["name"]]) for t in topology] == [1, 1, 72, 72, 72, 1]
    return expected


def compare_report(contract, model, doc, role, a, timeline=None):
    a.ok(set(doc) == {"report"} and set(doc["report"]) == {"tables"},
         role + " report root keys")
    expected = expected_report(contract, model, role, timeline)
    got_tables = tables(doc, "report")
    topology = contract["report_gate"]["topology"]
    a.ok([t["name"] for t in got_tables] == [t["name"] for t in topology], role + " report table order")
    a.ok(len(got_tables) == 6, role + " report table count")
    parent_report = native_json((PARENT_RUN / "report-raw.json").read_bytes())
    metadata_templates = {t["name"]: t["columns"] for t in tables(parent_report, "report")}
    cells = 0
    for table, spec in zip(got_tables, topology):
        name = spec["name"]
        a.ok(set(table) == {"name", "columns", "instances"}, role + "/" + name + " table keys")
        a.ok(same_type(table["columns"], metadata_templates[name]) and
             [c["name"] for c in table["columns"]] == spec["columns"],
             role + "/" + name + " complete columns")
        a.ok(len(table["instances"]) == 1 and table["instances"][0]["instance_name"] == spec["instance_name"],
             role + "/" + name + " instance")
        a.ok(set(table["instances"][0]) == {"instance_name", "rows"},
             role + "/" + name + " instance keys")
        rows = table["instances"][0]["rows"]
        a.ok(len(rows) == spec["rows"], role + "/" + name + " rows")
        for i, (row, want) in enumerate(zip(rows, expected[name])):
            a.ok(len(row) == len(spec["columns"]), f"{role}/{name}/{i} width")
            for col, value in zip(spec["columns"], row):
                target = want[col]
                good = numeric(value, target) if target is not None and type(target) in (int, float) else same_type(value, target)
                a.ok(good, f"{role}/{name}/{i}/{col}: {value!r} != {target!r}")
                cells += 1
    a.ok(cells == 5210, role + " 5210 cells")
    return expected


def parent_replay(contract, parent, a):
    timeline = child_physical((PARENT_RUN / "model.log").read_bytes(), a)
    out = native_json((PARENT_RUN / "roundtrip-raw.json").read_bytes())
    roundtrip(parent, out, a, "accepted idle OUT")
    report = native_json((PARENT_RUN / "report-raw.json").read_bytes())
    expected = compare_report(contract, parent, report, "parent", a, timeline)
    return expected


def log_signature(line):
    """Normalize only native object/task serials; retain quantities and words."""
    s = re.sub(r"^Time: (?:[-+0-9.eE]+)\s*", "", line).strip()
    s = re.sub(r"<TEACH-AIR-01,[01]>", "<AIR>", s)
    s = re.sub(r"<BASIC-MISSION,TEACH-UNIT,0,0,[01]>", "<MISSION>", s)
    s = re.sub(r"\b(resource transfer task|system preparation task|subtask) [0-9]+",
               lambda m: m.group(1) + " N", s)
    return s


def parse_log(raw, role, a):
    lines = raw.decode("utf-8-sig").splitlines()
    a.ok(lines[:2] == ["SIMLOX LOG FILE", "36"], role + " log header")
    a.ok(all(not x or x.startswith("Time:") or x.startswith(" ") for x in lines[2:]),
         role + " timed/continuation line syntax")
    parent_lines = (PARENT_RUN / "model.log").read_bytes().decode("utf-8-sig").splitlines()
    allowed = {log_signature(x) for x in parent_lines[2:] if x.strip()}
    if role == "unarrived":
        allowed.add("resource transfer task N (OUT)  starts with 1 resources, transfer time: 40")
    backorder = {x for x in allowed if "Resource transfer backorder" in x or
                 "starts with 0 resources" in x or "arrives with 0 resources" in x or
                 "Backorders:" in x}
    timed = []
    last = -1.0
    for n, line in enumerate(lines[2:], 3):
        if not line.strip():
            continue
        sig = log_signature(line)
        a.ok(sig in allowed, f"{role} unknown native log line {n}: {line}")
        if role in ("idle", "unarrived"):
            a.ok(sig not in backorder, f"{role} forbidden transfer/backorder line {n}")
        if line.startswith("Time:"):
            m = re.match(r"^Time: ([-+0-9.eE]+)\s+(.*)$", line)
            a.ok(m is not None, f"{role} malformed timed line {n}")
            t = float(m.group(1))
            a.ok(math.isfinite(t) and 0 <= t <= 36 and t >= last,
                 f"{role} monotone finite time at line {n}")
            last = t
            timed.append((n, t, m.group(2).strip()))
    a.ok(timed and timed[-1][1] == 36, role + " terminal shift")
    return lines, timed


def parent_physical(raw, a):
    lines, timed = parse_log(raw, "busy", a)
    transfers = [(int(m.group(1)), m.group(2), t, pos)
                 for pos, t, body in timed
                 if (m := re.fullmatch(r"resource transfer task (\d+) \(OUT\)\s+(.*)", body))]
    a.ok([(n, text, t) for n, text, t, _ in transfers] == [
        (0, "created: starting from  <P-CREW at <BASE-01,0>>", 7.75),
        (0, "starts with 0 resources, transfer time: 0", 7.75),
        (0, "arrives with 0 resources", 7.75),
        (1, "created: starting from  <P-CREW at <BASE-01,0>>", 8),
        (1, "starts with 1 resources, transfer time: 0", 8),
        (1, "arrives with 1 resources", 8)], "accepted busy OUT two-task chronology")
    back = [(body, t, pos) for pos, t, body in timed if "Resource transfer backorder" in body]
    a.ok(len(back) == 2 and "added" in back[0][0] and back[0][1] == 7.75 and
         "removed" in back[1][0] and back[1][1] == 8 and back[0][2] < back[1][2],
         "accepted busy backorder")
    missions = [(body, t) for _, t, body in timed if "mission starting, duration" in body]
    success = [(body, t) for _, t, body in timed if "mission success:" in body]
    a.ok([t for _, t in missions] == [8, 20.5] and [t for _, t in success] == [9, 21.5],
         "accepted two launch/success waves")
    a.ok(sum("Availability test on" in x and "failed" in x for x in lines) == 1,
         "accepted one typed crew wait")


def child_context_and_state(lines, timed, a, role):
    """Bind every untimed continuation to its immediately preceding timed owner.

    Reconcile the unit ready pool and crew snapshots at the actual printed edge,
    independent of report averages and substring counts.
    """
    owners = {}
    previous = None
    for number, line in enumerate(lines, 1):
        if number <= 2:
            continue
        if line.startswith("Time:"):
            previous = number
            owners[number] = []
        elif line.strip():
            a.ok(previous is not None, f"orphan continuation {number}")
            owners[previous].append((number, line.strip()))
    ready_pool = set()
    crew_free, crew_booked, crew_transit, crew_completed_out = 2, 0, 0, 0
    arrivals = []
    ready_edges = []
    snapshots = []
    using = []
    booked_owner = 0
    availability_owners = []
    queues = []
    post_grant_empty_queues = []
    for pos, time, body in timed:
        continuation = [text for _, text in owners[pos]]
        if re.fullmatch(r"<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,[01]>, mission success,", body):
            a.ok(continuation == ["no failures", "no PMTasks"], f"return continuations {pos}")
            arrivals.append((time, int(re.search(r"<TEACH-AIR-01,([01])>, mission", body).group(1))))
        else:
            a.ok(not any(x in ("no failures", "no PMTasks") for x in continuation),
                 f"return continuation wrong owner {pos}")
        edge = re.fullmatch(r"<TEACH-AIR-01,([01])> nbr ready (increased|decreased) at unit: <TEACH-UNIT at <BASE-01,0>>", body)
        if edge:
            air = int(edge.group(1)); action = edge.group(2)
            if action == "increased":
                a.ok(air not in ready_pool, f"duplicate ready increase {pos}")
                ready_pool.add(air)
            else:
                a.ok(air in ready_pool, f"decrease unavailable air {pos}")
                ready_pool.remove(air)
            ready_edges.append((time, air, action, pos))
        state = re.fullmatch(r"<TEACH-UNIT at <BASE-01,0>> systems ready: ([012]) :(.*)", body)
        if state:
            listed = {int(x) for x in re.findall(r"<TEACH-AIR-01,([01])>", state.group(2))}
            a.ok(int(state.group(1)) == len(ready_pool) and listed == ready_pool and
                 len(re.findall(r"<TEACH-AIR-01,[01]>", state.group(2))) == len(listed),
                 f"typed ready snapshot {pos}")
            snapshots.append((time, tuple(sorted(listed))))
        duration = 40 if role == "unarrived" else 0
        outbound = re.fullmatch(rf"resource transfer task 0 \(OUT\)\s+starts with 1 resources, transfer time: {duration}", body)
        outbound_arrival = re.fullmatch(r"resource transfer task 0 \(OUT\)\s+arrives with 1 resources", body)
        book = re.fullmatch(r"<P-CREW at <BASE-01,0>> allocated to maintenance task: 1\s+available now: (\d+)", body)
        release = re.fullmatch(r"<P-CREW at <BASE-01,0>> deallocated from\s+maintenance task: 1\s+available now: (\d+)", body)
        if outbound:
            a.ok(crew_free == 2 and crew_booked == crew_transit == crew_completed_out == 0,
                 "OUT starts from free crew")
            crew_free -= 1; crew_transit += 1
        if outbound_arrival:
            a.ok(crew_transit == 1 and crew_completed_out == 0,
                 "linked OUT task completes its in-transfer quantity")
            crew_transit -= 1; crew_completed_out += 1
        if book:
            a.ok(crew_free >= 1, f"booking local crew {pos}")
            crew_free -= 1; crew_booked += 1
            a.ok(int(book.group(1)) == crew_free, f"booked free count {pos}")
            booked_owner += 1
        if release:
            a.ok(crew_booked >= 1, f"release booked crew {pos}")
            crew_booked -= 1; crew_free += 1
            a.ok(int(release.group(1)) == crew_free, f"released free count {pos}")
        a.ok(min(crew_free, crew_booked, crew_transit, crew_completed_out) >= 0 and
             crew_free + crew_booked + crew_transit + crew_completed_out == 2,
             f"derived crew/task-quantity conservation {pos}")
        free_snap = [x for x in continuation if x.startswith("Free resources at:")]
        if free_snap:
            a.ok(body == "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period" and
                 time == 0 and free_snap == ["Free resources at: <BASE-01,0> P-CREW 2"] and
                 crew_free == 2 and crew_booked == crew_transit == crew_completed_out == 0,
                 f"opening crew snapshot owner/state {pos}")
        if body == "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period":
            a.ok(free_snap == ["Free resources at: <BASE-01,0> P-CREW 2"], "opening crew snapshot present")
        use_snap = [x for x in continuation if x.startswith("Missions and tasks using resources at:")]
        if use_snap:
            a.ok(len(use_snap) == 1 and use_snap[0] ==
                 f"Missions and tasks using resources at: <BASE-01,0> {crew_booked}" and
                 (book is not None or body == "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period"),
                 f"booked crew snapshot owner/state {pos}")
            using.append((pos, crew_booked))
            if book:
                owner = booked_owner - 1
                a.ok(continuation == [
                    "Missions and tasks using resources at: <BASE-01,0> 1",
                    f"< subtask {owner} seqno 1 within system preparation task {owner} on <TEACH-AIR-01,{owner % 2}>, C, 1, 0.5>"],
                    f"booked task owner/quantity {pos}")
            else:
                a.ok(continuation == ["Free resources at: <BASE-01,0> P-CREW 2",
                                      "Missions and tasks using resources at: <BASE-01,0> 0"],
                     "opening crew and booking snapshot")
        available = [x for x in continuation if x.startswith("Availability test on")]
        if available:
            a.ok(body.endswith("resource availability test") and len(available) == 1,
                 f"availability continuation owner {pos}")
            availability_owners.append(pos)
        queue = [x for x in continuation if x.startswith("Tasks waiting for resources at:")]
        if queue:
            a.ok(len(queue) == 1, f"one queue continuation {pos}")
            if body == "<BASE-01,0> trig missions and tasks waiting for resources":
                count = (1 if time in (8, 20) and crew_booked == 0 else 0)
                owner = 1 if time == 8 and count else 3 if time == 20 and count else None
                want = ["Missions waiting for resources at: <BASE-01,0>",
                        f"Tasks waiting for resources at: <BASE-01,0> {count}"]
                if owner is not None:
                    want.append(f"< subtask {owner} seqno 1 within system preparation task {owner} on <TEACH-AIR-01,1>, C, 0.5>")
                a.ok(continuation == want, f"typed queue owner/count {pos}")
                queues.append((time, queue[0]))
            else:
                a.ok(body == "<TEACH-AIR-01,1> Next random failure will occur 1e+010" and
                     time in (8, 20) and queue == ["Tasks waiting for resources at: <BASE-01,0> 0"],
                     f"post-grant empty queue owner {pos}")
                post_grant_empty_queues.append((time, pos))
        a.ok(not any(x.startswith("< subtask ") for x in continuation) or
             (book is not None and use_snap) or
             (body == "<BASE-01,0> trig missions and tasks waiting for resources" and queue),
             f"orphan task listing {pos}")
        if any(x.startswith("Missions waiting for resources at:") for x in continuation):
            a.ok(body == "<BASE-01,0> trig missions and tasks waiting for resources" and queue,
                 f"orphan mission queue continuation {pos}")
        allowed_continuations = (
            "no failures", "no PMTasks", "Availability test on",
            "Free resources at:", "Missions and tasks using resources at:",
            "Missions waiting for resources at:", "Tasks waiting for resources at:",
            "< subtask ")
        for text in continuation:
            a.ok(any(text.startswith(prefix) for prefix in allowed_continuations),
                 f"unclassified untimed child diagnostic {pos}: {text}")
        a.ok(not any(x.startswith("Free resources at:") for x in continuation) or free_snap,
             f"unbound free crew {pos}")
    a.ok(ready_edges == [(0, 0, "increased", ready_edges[0][3]),
                         (0, 1, "increased", ready_edges[1][3]),
                         (7.5, 0, "decreased", ready_edges[2][3]),
                         (7.5, 1, "decreased", ready_edges[3][3]),
                         (9.5, 0, "increased", ready_edges[4][3]),
                         (9.5, 1, "increased", ready_edges[5][3]),
                         (19.5, 0, "decreased", ready_edges[6][3]),
                         (19.5, 1, "decreased", ready_edges[7][3]),
                         (21.5, 0, "increased", ready_edges[8][3]),
                         (21.5, 1, "increased", ready_edges[9][3])]
         if len(ready_edges) == 10 else False, "source-bound complete ready-pool edges")
    a.ok(snapshots == [(0, (0, 1)), (9.5, (0,)), (9.5, (0, 1)),
                       (21.5, (0,)), (21.5, (0, 1))], "ready-pool snapshots")
    a.ok(arrivals == [(9.5, 0), (9.5, 1), (21.5, 0), (21.5, 1)], "return owner/order")
    a.ok((crew_free, crew_booked, crew_transit, crew_completed_out) ==
         ((1, 0, 1, 0) if role == "unarrived" else (1, 0, 0, 1))
         and ready_pool == {0, 1}, "typed terminal crew and derived OUT-task state")
    a.ok(len(using) == 5 and [v for _, v in using] == [0, 1, 1, 1, 1],
         "opening and four booked-resource snapshots")
    a.ok(len(availability_owners) == 6, "six owned availability continuations")
    expected_finishes = (8, 8.5, 20, 20.5)
    for ident, finish_time in enumerate(expected_finishes):
        air = ident % 2
        remote = f"subtask {ident} seqno 1 check return remote resources"
        transport = "<P-CREW at <BASE-01,0>> check for return transport: 1"
        main_complete = f"system preparation task {ident} on <TEACH-AIR-01,{air}> completed"
        prep_end = (f"<TEACH-AIR-01,{air}> preparation ended, mission: "
                    f"<BASIC-MISSION,TEACH-UNIT,0,0,{ident // 2}>")
        remote_matches = [i for i, (_, t, body) in enumerate(timed)
                          if t == finish_time and body == remote]
        a.ok(len(remote_matches) == 1, f"one typed remote-return check task {ident}")
        i = remote_matches[0]
        a.ok([v[2] for v in timed[i:i + 4]] ==
             [remote, transport, main_complete, prep_end] and
             all(v[1] == finish_time for v in timed[i:i + 4]),
             f"task {ident} remote-check/main-prep completion order")
        release = [p for p, t, body in timed if t == finish_time and
                   body.startswith("<P-CREW at <BASE-01,0>> deallocated from")]
        a.ok(release and min(release) < timed[i][0],
             f"task {ident} remote check follows booked crew release")
        if air == 0:
            next_book = [p for p, t, body in timed if t == finish_time and
                         body == "<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0"]
            a.ok(len(next_book) == 1 and next_book[0] < timed[i][0],
                 f"second aircraft grant precedes first main-prep completion wave {ident // 2}")
    a.ok(sum(body == "<P-CREW at <BASE-01,0>> check for return transport: 1"
             for _, _, body in timed) == 4, "four checks without physical return transfers")
    a.ok([t for t, _ in queues] == [0, 0, 8, 8.5, 20, 20.5, 24],
         "typed wait/release queue inspections")
    a.ok([t for t, _ in post_grant_empty_queues] == [8, 20],
         "one post-grant empty queue snapshot per second-aircraft booking")
    a.ok([(t, b) for _, t, b in timed if b.startswith("Start of day no ")] ==
         [(0, "Start of day no 0"), (24, "Start of day no 1")],
         "two source-calendar day boundaries")
    a.ok([(t, b) for _, t, b in timed if b.startswith("resource shift 0 ")] == [
        (0, "resource shift 0 created at <P-CREW at <BASE-01,0>>"),
        (0, "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period"),
        (36, "resource shift 0 ended at <P-CREW at <BASE-01,0>> time gap to next = 0")],
        "single continuous crew shift")
    for wave, arrival_time in enumerate((9.5, 21.5)):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        completed = [(pos, t) for pos, t, b in timed if b ==
                     f"{mission} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"]
        a.ok(len(completed) == 1 and completed[0][1] == arrival_time,
             f"mission completion before return wave {wave}")
        for air in (0, 1):
            expected = [
                f"<TEACH-AIR-01,BASE-01,0> System soon ready <TEACH-AIR-01,{air}>, estimated remaining time: 0",
                f"<TEACH-AIR-01,{air}> turnround started, mission: {mission} reduction factor: 1",
                f"<TEACH-AIR-01,{air}> turnround ended, mission: {mission}",
                f"<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,{air}>, mission success,",
                f"<TEACH-AIR-01,{air}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>"]
            positions = []
            for body in expected:
                matches = [pos for pos, t, b in timed if t == arrival_time and b == body]
                a.ok(len(matches) == 1,
                     f"typed zero-duration turnround {wave}/{air}: {body}")
                positions.append(matches[0])
            a.ok(completed[0][0] < positions[0] and positions == sorted(positions) and
                 len(set(positions)) == len(positions),
                 f"same-time typed mission/aircraft turnround and ready order {wave}/{air}")
    a.ok(sum("System soon ready" in b for _, _, b in timed) == 4 and
         sum("turnround started" in b for _, _, b in timed) == 4 and
         sum("turnround ended" in b for _, _, b in timed) == 4 and
         sum("System ready <TEACH-AIR-01," in b for _, _, b in timed) == 8 and
         sum("Repair task priority list:" in b for _, _, b in timed) == 4,
         "complete typed return diagnostics")
    for index, (pos, time, body) in enumerate(timed):
        allocation_edge = re.fullmatch(
            r"<BASIC-MISSION,TEACH-UNIT,0,0,[01]> mission allocates system: <TEACH-AIR-01,([01])>", body)
        if allocation_edge:
            air = allocation_edge.group(1)
            a.ok(index + 1 < len(timed) and timed[index + 1][1] == time and
                 timed[index + 1][2] ==
                 f"<TEACH-AIR-01,{air}> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>",
                 f"mission allocation immediately removes typed ready aircraft {pos}")
        arrival = re.fullmatch(
            r"<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,([01])>, mission success,", body)
        if arrival:
            air = int(arrival.group(1))
            count = air + 1
            snapshot = ("<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>" if air == 0 else
                        "<TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
            expected = [
                f"<TEACH-AIR-01,{air}> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>",
                f"<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,{air}>",
                f"<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,{air}>",
                snapshot,
                "<TEACH-AIR-01,BASE-01,0> Repair task priority list:"]
            a.ok([v[2] for v in timed[index + 1:index + 6]] == expected and
                 all(v[1] == time for v in timed[index + 1:index + 6]),
                 f"return {count} ready and priority sequence {pos}")


def child_physical(raw, a, role="parent"):
    """Source-bound typed ledger. Each event is taken from a real log line."""
    lines, timed = parse_log(raw, "unarrived" if role == "child" else "idle", a)
    child_context_and_state(lines, timed, a, "unarrived" if role == "child" else "idle")
    by_task = defaultdict(list)
    by_mission = defaultdict(list)
    transfer = []
    allocation = []
    deallocation = []
    availability = []
    ready = []
    prep_task = defaultdict(list)
    prep_air = defaultdict(list)
    mission_order = []
    sentinel = []
    for pos, t, body in timed:
        if body == "<TEACH-UNIT> mission ordered: BASIC-MISSION":
            mission_order.append((t, pos))
        sent = re.fullmatch(r"<TEACH-AIR-01,([01])> Next random failure will occur 1e\+010", body)
        if sent:
            sentinel.append((int(sent.group(1)), t, pos))
        pt = re.fullmatch(r"system preparation task (\d+) on <TEACH-AIR-01,([01])> (started|completed)", body)
        if pt:
            ident, air = int(pt.group(1)), int(pt.group(2))
            a.ok(ident in range(4) and air == ident % 2, f"system prep owner {pos}")
            prep_task[ident].append((pt.group(3), t, pos))
        pa = re.fullmatch(r"<TEACH-AIR-01,([01])> preparation (started|ended), mission: <BASIC-MISSION,TEACH-UNIT,0,0,([01])>", body)
        if pa:
            air, wave = int(pa.group(1)), int(pa.group(3))
            prep_air[(wave, air)].append((pa.group(2), t, pos))
        task = re.match(r"^subtask (\d+) seqno 1 within system preparation task \1 on <TEACH-AIR-01,([01])> (.*)$", body)
        if task:
            ident, air, action = int(task.group(1)), int(task.group(2)), task.group(3)
            a.ok(ident in range(4) and air == ident % 2,
                 f"typed preparation task owner {pos}")
            by_task[ident].append((action, t, pos))
            if action == "resource availability test":
                nxt = lines[pos] if pos < len(lines) else ""
                m = re.fullmatch(r"\s*Availability test on\s+<P-CREW at <BASE-01,0>> request for: 1 (OK|failed)\s*", nxt)
                a.ok(m is not None, f"typed availability continuation {pos}")
                availability.append((ident, t, m.group(1), pos))
        transfer_m = re.match(r"^resource transfer task (\d+) \(OUT\)\s+(.*)$", body)
        if transfer_m:
            transfer.append((int(transfer_m.group(1)), transfer_m.group(2), t, pos))
        if "Resource transfer demand arrives from OUT-transfer" in body:
            transfer.append((-1, "demand", t, pos))
        alloc = re.fullmatch(r"<P-CREW at <BASE-01,0>> allocated to maintenance task: (\d+)\s+available now: (\d+)", body)
        if alloc:
            allocation.append((t, int(alloc.group(1)), int(alloc.group(2)), pos))
        dealloc = re.fullmatch(r"<P-CREW at <BASE-01,0>> deallocated from\s+maintenance task: (\d+)\s+available now: (\d+)", body)
        if dealloc:
            deallocation.append((t, int(dealloc.group(1)), int(dealloc.group(2)), pos))
        mission = re.match(r"^<BASIC-MISSION,TEACH-UNIT,0,0,([01])> (.*)$", body)
        if mission:
            by_mission[int(mission.group(1))].append((mission.group(2), t, pos))
        ready_m = re.fullmatch(r"<TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,([01])>, mission success,", body)
        if ready_m:
            ready.append((int(ready_m.group(1)), t, pos))
    a.ok(len(transfer) == (3 if role == "child" else 4) and
         {v[0] for v in transfer} == {-1, 0},
         "one typed OUT task and demand")
    transfer_order = [(text, t) for ident, text, t, _ in transfer]
    duration, arrival_time = (40, None) if role == "child" else (0, 6)
    expected_transfer = [
        ("created: starting from  <P-CREW at <BASE-01,0>>", 6),
        ("demand", 6), (f"starts with 1 resources, transfer time: {duration}", 6)]
    if role == "parent":
        expected_transfer.append(("arrives with 1 resources", arrival_time))
    a.ok(transfer_order == expected_transfer, "ordered one-unit OUT task and completion scope")
    a.ok(len(allocation) == len(deallocation) == 4, "four typed crew books/releases")
    a.ok(availability == [(0, 7.5, "OK", availability[0][3]),
                          (1, 7.5, "failed", availability[1][3]),
                          (1, 8, "OK", availability[2][3]),
                          (2, 19.5, "OK", availability[3][3]),
                          (3, 19.5, "failed", availability[4][3]),
                          (3, 20, "OK", availability[5][3])]
         if len(availability) == 6 else False, "source-bound six availability tests")
    for ident in range(4):
        start = 7.5 if ident < 2 else 19.5
        work = start + (0.5 if ident % 2 else 0)
        finish = work + .5
        got = [(action, t) for action, t, _ in by_task[ident]]
        want = [("started", start), ("requests resources", start),
                ("resource availability test", start)]
        if ident % 2:
            want.extend([("resource availability test", work), ("resource received", work)])
        want.extend([("books resources", work),
                     ("starts performing, planned to last for 0.5 hours", work),
                     ("completed", finish), ("frees resources", finish)])
        a.ok(got == want, f"task {ident} exact lifecycle")
        a.ok([(kind, t) for kind, t, _ in prep_task[ident]] ==
             [("started", start), ("completed", finish)],
             f"system prep {ident} exact lifecycle")
        a.ok([(kind, t) for kind, t, _ in prep_air[(ident // 2, ident % 2)]] ==
             [("started", start), ("ended", finish)],
             f"aircraft prep {ident} exact lifecycle")
    expected_book_times = [7.5, 8, 19.5, 20]
    expected_release_times = [8, 8.5, 20, 20.5]
    a.ok([v[0] for v in allocation] == expected_book_times and
         [v[0] for v in deallocation] == expected_release_times,
         "serial first and second wave crew bookings")
    free, booked, in_transfer, completed_out = 2, 0, 0, 0
    resource_edges = [(pos, "out", 1, 0) for ident, text, t, pos in transfer if text.startswith("starts with")]
    resource_edges += [(pos, "arrival", 1, 0) for ident, text, t, pos in transfer if text.startswith("arrives with")]
    resource_edges += [(pos, "book", qty, avail) for _, qty, avail, pos in allocation]
    resource_edges += [(pos, "release", qty, avail) for _, qty, avail, pos in deallocation]
    for pos, action, qty, avail in sorted(resource_edges):
        a.ok(qty == 1, f"one crew unit edge {pos}")
        if action == "out":
            a.ok(booked == 0 and free >= 1 and in_transfer == completed_out == 0,
                 "OUT free-unit source")
            free -= 1
            in_transfer += 1
        elif action == "arrival":
            a.ok(in_transfer == 1 and completed_out == 0, "linked transfer completion")
            in_transfer -= 1
            completed_out += 1
        elif action == "book":
            a.ok(free >= 1, f"crew available at booking {pos}")
            free -= 1
            booked += 1
            a.ok(free == avail, f"reported free after book {pos}")
        else:
            a.ok(booked >= 1, f"crew booked before release {pos}")
            booked -= 1
            free += 1
            a.ok(free == avail, f"reported free after release {pos}")
        a.ok(min(free, booked, in_transfer, completed_out) >= 0 and
             free + booked + in_transfer + completed_out == 2,
             f"source crew/task-quantity conservation {pos}")
    a.ok((free, booked, in_transfer, completed_out) ==
         ((1, 0, 1, 0) if role == "child" else (1, 0, 0, 1)),
         "typed terminal local and task quantities")
    waves = []
    for wave, start in enumerate((7.5, 19.5)):
        launch = 8.5 if wave == 0 else 20.5
        end = launch + 1
        events = by_mission[wave]
        a.ok(len(events) == 9, f"mission {wave} nine typed events")
        a.ok([(x.split(":")[0], t) for x, t, _ in events] == [
            ("mission created", start), ("mission activated, systems requested", start),
            ("mission allocates system", start), ("mission allocates system", start),
            ("mission starting, duration", launch), ("task starting", launch + .25),
            ("task completed", launch + .75), ("mission success", end),
            ("mission completed", end)], f"mission {wave} typed chronology")
        a.ok("systems requested: 2" in events[1][0] and
             events[2][0] == "mission allocates system: <TEACH-AIR-01,0>" and
             events[3][0] == "mission allocates system: <TEACH-AIR-01,1>" and
             "duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in events[4][0],
             f"mission {wave} formation and duration")
        waves.append({"start": start, "first_end": by_task[2*wave][5][1],
                      "last_end": by_task[2*wave+1][-2][1],
                      "launch": events[4][1], "end": events[-2][1],
                      "bookings": [(by_task[2*wave][3][1], by_task[2*wave][5][1]),
                                   (by_task[2*wave+1][5][1], by_task[2*wave+1][-2][1])],
                      "waits": [(by_task[2*wave+1][2][1], by_task[2*wave+1][3][1])]})
    a.ok([t for t, _ in mission_order] == [7.5, 19.5],
         "exactly two source-order missions")
    allowed_sentinels = {0, 7.5, 8, 8.5, 9.5, 19.5, 20, 20.5, 21.5}
    a.ok(all(t in allowed_sentinels for _, t, _ in sentinel),
         "diagnostic times attributed to source/event edges")
    availability_continuations = [n for n, line in enumerate(lines, 1)
                                  if line.lstrip().startswith("Availability test on")]
    a.ok(availability_continuations == [pos + 1 for _, _, _, pos in availability],
         "no orphan or duplicated availability continuation")
    wait_snapshots = []
    for pos, t, body in timed:
        if body != "<BASE-01,0> trig missions and tasks waiting for resources":
            continue
        following = []
        for line in lines[pos:]:
            if line.startswith("Time:"):
                break
            following.append(line.strip())
        if "Tasks waiting for resources at: <BASE-01,0> 1" in following:
            wait_snapshots.append((t, following))
    a.ok([t for t, _ in wait_snapshots] == [8, 20],
         "two typed second-aircraft waiting queue snapshots")
    for wave, (_, following) in enumerate(wait_snapshots):
        ident = 1 + 2 * wave
        a.ok(f"< subtask {ident} seqno 1 within system preparation task {ident} on <TEACH-AIR-01,1>, C, 0.5>"
             in following, f"waiting queue owner task {ident}")
    a.ok(sum(line.strip() == "no failures" for line in lines) == 4 and
         sum(line.strip() == "no PMTasks" for line in lines) == 4,
         "four complete no-fault aircraft return continuations")
    a.ok(ready == [(0, 9.5, ready[0][2]), (1, 9.5, ready[1][2]),
                   (0, 21.5, ready[2][2]), (1, 21.5, ready[3][2])]
         if len(ready) == 4 else False, "all four aircraft returns")
    timeline = {"out_departure": next(t for ident, text, t, _ in transfer if text.startswith("starts with")),
                "out_arrival": arrival_time, "waves": waves}
    a.ok({k: timeline[k] for k in ("out_departure", "waves")} == source_prediction()
         and timeline["out_arrival"] == (None if role == "child" else 6),
         "physical timeline equals source and linked task observation")
    return timeline


def expected_stage_plan(run_dir=CHILD_RUN):
    exe = r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"
    python = r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    commands = [
        {"name": "import", "program": exe, "arguments":
         f'-silent -jimport "{run_dir / "input.json"}" -save "{run_dir / "model.sxi"}" '
         f'-log "{run_dir / "import.log"}" -close'},
        {"name": "export", "program": exe, "arguments":
         f'"{run_dir / "model.sxi"}" -silent -jexport "{run_dir / "roundtrip-raw.json"}" '
         f'-log "{run_dir / "export.log"}" -close'},
        {"name": "calc", "program": exe, "arguments":
         f'"{run_dir / "model.sxi"}" -silent -threads 1 -calc '
         f'-log "{run_dir / "run.log"}" -close'},
        {"name": "jsonreport", "program": exe, "arguments":
         f'"{run_dir / "model.sxo"}" -silent -jsonreport "{run_dir / "report-raw.json"}" '
         f'-log "{run_dir / "report-export.log"}" -close'},
    ]
    checkers = [
        {"name": "check_import_export", "program": python,
         "arguments": f'-X utf8 -B "{PKG / "check_roundtrip.py"}" "{run_dir}"'},
        {"name": "check_behavior", "program": python,
         "arguments": f'-X utf8 -B "{PKG / "validate_native_cli.py"}" "{run_dir}"'},
    ]
    return commands, checkers


def check_step_metadata(invocation, steps, a, run_dir=CHILD_RUN):
    commands, checkers = expected_stage_plan(run_dir)
    names = ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    a.ok(type(steps) is list and [s["name"] for s in steps] == names,
         "six serial native/check stages")
    a.ok(same_type(invocation["planned_commands"], commands) and
         same_type(invocation["planned_checkers"], checkers),
         "exact native and checker executable/argv plan")
    planned_by_name = {item["name"]: item for item in commands + checkers}

    def utc_stamp(raw):
        a.ok(type(raw) is str, "native step UTC timestamp string")
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        a.ok(parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0),
             "native step timestamp explicitly UTC")
        return parsed

    previous_end = utc_stamp(invocation["created_utc"])
    for index, step in enumerate(steps):
        a.ok(type(step["sequence"]) is int and step["sequence"] == index and
             {k: step[k] for k in ("name", "program", "arguments")} == planned_by_name[step["name"]],
             "executed native/check program and argv match exact serial plan")
        started, ended = utc_stamp(step["started_utc"]), utc_stamp(step["completed_utc"])
        a.ok(previous_end <= started <= ended, "native/check stage UTC nonoverlap")
        previous_end = ended


def prospective_source_pins(contract, a):
    """Mandatory primary/context byte custody; historical catalog always checked."""
    a.ok(pin((PKG / "contract.json").read_bytes()) ==
         {"bytes": 325510, "sha256": CONTRACT_SHA}, "frozen v4 contract")
    a.ok(pin((PKG / "MODEL-LINEAGE.md").read_bytes()) ==
         {"bytes": 3959,
          "sha256": "a2a11671b994f66699fc575794082c26f38aab9d663369105471bf3c1c524924"},
         "frozen lineage")
    a.ok(contract["case_id"] == "I03" and contract["variant_id"] == "I03.var11" and
         contract["phase"] == "contract_design_only_no_model_or_native" and
         contract["ownership"]["new_native_calls_so_far"] == 0,
         "prospective classification scope")
    lineage = contract["source_lineage"]
    a.ok(lineage["base_commit"] == BASE and lineage["source_ref_count"] == 452,
         "accepted source base and count")
    refs = lineage["primary_parent_source_and_secondary_context_source_disk_vs_git_at_base"]
    a.ok(len(refs) == len({r["path"] for r in refs}) == 452,
         "452 unique accepted published source refs")
    for rec in refs:
        exact(REPO / rec["path"], rec["local_disk"], a,
              "accepted source local " + rec["path"])
        a.ok(pin(git_blob(rec["path"])) == rec["published_git_at_base"],
             "accepted source distinct Git bytes " + rec["path"])
    raws = lineage["original_raw"]
    a.ok(len(raws) == len({r["original_path"] for r in raws}) == 144 and
         sum(r["classification"] == "accepted_or_required_context" for r in raws) == 118 and
         sum(r["classification"] == "excluded_failed_v100_witness" for r in raws) == 26,
         "144 mandatory original raw paths/classes")
    for rec in raws:
        exact(Path(rec["original_path"]), rec, a,
              "mandatory original raw " + rec["original_path"])
    for rec in lineage["installed"] + lineage["required_docs"]:
        p = Path(rec["path"])
        exact(p if p.is_absolute() else REPO / p, rec, a,
              "installed/documentation " + rec["path"])
    context = lineage["root_selection_context"]
    a.ok(len(context) == len({r["owned_inert_copy"] for r in context}) == 7,
         "seven fixed inert selection copies")
    for rec in context:
        copy = PKG / rec["owned_inert_copy"]
        a.ok(copy.resolve().is_relative_to(PKG.resolve()) and
             copy.suffix == ".bytes", "contained inert selection copy")
        exact(copy, rec, a, "mandatory owned selection copy")
        original = Path(rec["path"])
        if original.exists():
            exact(original, rec, a, "selection original if present")
    catalog = lineage["catalog_at_selection"]
    a.ok(catalog["entry_count"] == 492 and
         catalog["owned_exact_archive"] == "preserved-catalog/catalog-at-selection-492.bytes",
         "fixed historical catalog archive path")
    archive = exact(PKG / catalog["owned_exact_archive"],
                    catalog["local_disk"], a, "mandatory catalog492 owned archive")
    a.ok(pin(git_blob(catalog["path"])) == catalog["published_git_at_base"],
         "distinct catalog base-Git bytes")
    old_catalog = native_json(archive)
    live_catalog = native_json((REPO / catalog["path"]).read_bytes())
    check_catalog_archive(old_catalog, live_catalog, a)
    a.ok(same_type({k: v for k, v in old_catalog.items() if k != "entries"},
                   catalog["metadata"]), "typed catalog metadata matches contract")
    return {"required_catalog_prefix_entries": 492,
            "accepted_source_refs": 452, "mandatory_original_raw": 144,
            "owned_selection_context": 7}


def pure_child_fixture(parent_raw):
    """Only a parser/oracle test input; never substitute for native child raw."""
    start = b"Time: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 0"
    arrival = b"Time: 6  resource transfer task 0 (OUT)  arrives with 1 resources"
    assert parent_raw.count(start) == parent_raw.count(arrival) == 1
    out = parent_raw.replace(start, start[:-1] + b"40", 1)
    for eol in (b"\r\n", b"\n"):
        if arrival + eol in out:
            out = out.replace(arrival + eol, b"", 1)
            break
    else:
        raise AssertionError("parent arrival line ending unavailable")
    assert arrival not in out
    return out


def pure_preflight(contract, a):
    parent, child = parent_and_prediction(contract, a)
    child_input = native_json((PKG / "native-input.json").read_bytes())
    child_input_check(child, child_input, a)
    expected_parent = parent_replay(contract, parent, a)
    raw = (PARENT_RUN / "model.log").read_bytes()
    fixture = pure_child_fixture(raw)
    timeline = child_physical(fixture, a, role="child")
    expected_child = expected_report(contract, child, "child", timeline)
    a.ok(expected_child["ProblemDescription"] != expected_parent["ProblemDescription"],
         "pure child differs in authored description")
    a.ok(all(expected_child[t] == expected_parent[t] for t in expected_parent
             if t != "ProblemDescription"),
         "pure child other five report tables independently equal")
    a.ok(sum(t["rows"] * len(t["columns"]) for t in contract["report_gate"]["topology"]) == 5210,
         "pure fixture full report scope")
    return {"parent_report_cells": 5210, "child_report_cells_predicted": 5210,
            "pure_fixture_timed_records": len([x for x in fixture.splitlines() if x.startswith(b"Time:")]),
            "pure_fixture_only": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pure-fixture", action="store_true")
    args = parser.parse_args()
    a = Audit()
    contract = native_json((PKG / "contract.json").read_bytes())
    pins = prospective_source_pins(contract, a)
    if args.pure_fixture:
        result = pure_preflight(contract, a)
        print(json.dumps({"schema": "i03-var11-independent-replay/v1",
                          "status": "STATIC_ONLY", "checks": a.checks,
                          **pins, **result}, sort_keys=True))
        return
    raise AssertionError("sealed child path pending frozen runner/manifest schema; no native acceptance")


if __name__ == "__main__":
    main()


