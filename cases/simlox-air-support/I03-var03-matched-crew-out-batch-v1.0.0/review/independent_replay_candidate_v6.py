"""Independent I03.var03 two-arm evidence reader. Draft: no native acceptance yet.

This code consumes the frozen design and accepted parent; synthetic predictions cannot
substitute for the two future original native run directories and their closure seals.
"""
import argparse
import hashlib
import json
import math
import re
import struct
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CASE = Path(__file__).resolve().parents[1]
CONTRACT = CASE / "contract.json"
PARENT = REPO / "cases/simlox-air-support/I03-var01-crew-out-in-v1.0.0"
PARENT_INPUT = PARENT / "out-input.json"
PARENT_RUN = PARENT / "runs/i03-var01-crew-transfer-v100-ssh-20261005-01"
ROLES = ("control_out1", "child_out2")


def digest(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def no_constant(value):
    raise ValueError("nonfinite JSON number: " + value)


def parse_json(raw, native=False):
    text = raw.decode("utf-8-sig")
    if native:
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
            elif ch == ',' and i + 1 < len(text) and re.match(r"\s*[}\]]", text[i + 1:]):
                continue
            else:
                out.append(ch)
        text = "".join(out)
    result = json.loads(text, object_pairs_hook=unique, parse_constant=no_constant)
    def finite(v):
        if type(v) is float and not math.isfinite(v):
            raise ValueError("nonfinite JSON float")
        if type(v) is dict:
            for child in v.values():
                finite(child)
        if type(v) is list:
            for child in v:
                finite(child)
    finite(result)
    return result


def same_type(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(same_type(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(same_type(x, y) for x, y in zip(a, b))
    return a == b


def num_equal(a, b):
    return type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and a == b


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def tables(doc, root):
    assert set(doc) == {root} and set(doc[root]) == {"database_version", "tables"} if root == "model" else set(doc) == {root} and set(doc[root]) == {"tables"}
    arr = doc[root]["tables"]
    names = [t["name"] for t in arr]
    assert len(names) == len(set(names)), "duplicate table name"
    for t in arr:
        names_i = [x["instance_name"] for x in t["instances"]]
        assert len(names_i) == len(set(names_i)), "duplicate instance name"
    return arr


def table(doc, root, name):
    return next(t for t in tables(doc, root) if t["name"] == name)


def parent_and_predictions(contract):
    pin = contract["source_delta"]["base"]
    raw = PARENT_INPUT.read_bytes()
    assert digest(raw) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}
    parent = parse_json(raw)
    names = [t["name"] for t in tables(parent, "model")]
    assert names == contract["source_delta"]["parent_model"]["tables_in_order"]
    assert parent["model"]["database_version"] == 20160627
    output = {}
    for role in ROLES:
        child = deepcopy(parent)
        ra = table(child, "model", "ResourceAllocation")["instances"][0]["rows"]
        assert ra[0][:3] == ["AIR_BASIC", "P-CREW", "BASE-01"] and ra[0][3] == 2
        ra[0][3] = 3
        d = next(x for x in contract["source_delta"]["per_arm_changes"][role] if x["table"] == "ProblemDescription")
        table(child, "model", "ProblemDescription")["instances"][0]["rows"][0][0] = d["to"]
        tr = table(child, "model", "ResourceTransfer")["instances"][0]["rows"]
        assert tr == [["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None]]
        if role == "child_out2":
            tr[0][4] = 2
        output[role] = child
    return parent, output


def verify_input(expected, actual):
    assert same_type(expected, actual), "source exact cells/metadata"
    assert len(tables(actual, "model")) == 32


def verify_roundtrip(authored, exported):
    aa, ee = tables(authored, "model"), tables(exported, "model")
    assert authored["model"]["database_version"] == exported["model"]["database_version"]
    assert [t["name"] for t in aa] == [t["name"] for t in ee]
    cells = 0
    for x, y in zip(aa, ee):
        assert set(x) == set(y) == {"name", "columns", "instances"}
        assert same_type(x["columns"], y["columns"]), x["name"] + " column metadata"
        assert len(x["instances"]) == len(y["instances"]) == 1
        xi, yi = x["instances"][0], y["instances"][0]
        assert set(xi) == set(yi) == {"instance_name", "rows"}
        assert xi["instance_name"] == yi["instance_name"]
        sr, er = xi["rows"], yi["rows"]
        if not sr:
            assert er == [[None] * len(x["columns"])], x["name"] + " null placeholder"
        else:
            assert len(sr) == len(er)
            for a, b in zip(sr, er):
                assert len(a) == len(b) == len(x["columns"])
                for left, right, col in zip(a, b, x["columns"]):
                    dt = col["datatype"]
                    assert (num_equal(left, right) if dt in ("double", "float", "integer", "int") and left is not None else same_type(left, right)), x["name"] + "/" + col["name"]
                    cells += 1
    return cells


def frac(start, end, left, right):
    return max(0, min(end, right) - max(start, left)) / (right - left)


def predicted_timeline(role):
    assert role in ("accepted_parent",) + ROLES
    first = {"start": 7.5, "prep": [(7.5, 8), (7.5, 8)], "wait": [], "first_end": 8, "last_end": 8, "launch": 8, "return": 9}
    serial = {"start": 19.5, "prep": [(19.5, 20), (20, 20.5)], "wait": [(19.5, 20)], "first_end": 20, "last_end": 20.5, "launch": 20.5, "return": 21.5}
    parallel = {"start": 19.5, "prep": [(19.5, 20), (19.5, 20)], "wait": [], "first_end": 20, "last_end": 20, "launch": 20, "return": 21}
    if role == "accepted_parent":
        return {"waves": [first, serial], "opening": 2, "physical": [(0, 8, 2), (8, 36, 1)], "nominal": [(0, 7.75, 2), (7.75, 36, 1)]}
    if role == "control_out1":
        return {"waves": [first, parallel], "opening": 3, "physical": [(0, 7.75, 3), (7.75, 36, 2)], "nominal": [(0, 7.75, 3), (7.75, 36, 2)]}
    return {"waves": [first, serial], "opening": 3, "physical": [(0, 7.75, 3), (7.75, 8, 2), (8, 36, 1)], "nominal": [(0, 7.75, 3), (7.75, 36, 1)]}


def make_expected_report(contract, model, role, timeline):
    gate = contract["report_gate"]
    waves = timeline["waves"]
    sz = gate["system_field_classes"]["source_event_zero"] + gate["system_field_classes"]["bounded_native_presentation_zero"]
    rz = gate["resource_fields"]["source_event_zero"]
    stock_zero = gate["stock_fields"]["exact_zero"]
    stock_null = gate["stock_fields"]["bounded_undefined_null"]
    system, stock, resource = [], [], []
    for i in range(72):
        lo, hi = i / 2, (i + 1) / 2
        s = {k: 0 for k in sz}
        assigned = sum(2 * frac(w["start"], w["return"], lo, hi) for w in waves)
        mission = sum(2 * frac(w["launch"], w["return"], lo, hi) for w in waves)
        use = sum(frac(a, b, lo, hi) for w in waves for a, b in w["prep"])
        wait = sum(frac(a, b, lo, hi) for w in waves for a, b in w["wait"])
        ready_prepared = sum(frac(w["first_end"], w["last_end"], lo, hi) for w in waves)
        s.update(UNID="Total over all Units", SID="Total over all Systems", STINT=lo, ETINT=hi,
                 NSYRY=2 - assigned, NSYMA=assigned, NSYMO=mission, NSYMP=use + wait,
                 NSYMR=ready_prepared, NSYA=2, FTMO=mission / 2, STACC=mission, SYDT=None,
                 NPSTA=sum(2 for w in waves if lo <= w["start"] < hi),
                 NPSUC=sum((lo <= a < hi) for w in waves for a in [w["prep"][0][1], w["prep"][1][1]]))
        system.append(s)
        q = {k: 0 for k in stock_zero}
        q.update(STINT=lo, ETINT=hi, PNB=1)
        q.update({k: None for k in stock_null})
        stock.append(q)
        r = {k: 0 for k in rz}
        def avg(intervals):
            return sum(qty * frac(a, b, lo, hi) for a, b, qty in intervals)
        r.update(RID="Total over all Resources", STID="Total over all Stations", STINT=lo, ETINT=hi,
                 NR=avg(timeline["physical"]), NRA=avg(timeline["physical"]), NRN=avg(timeline["nominal"]), NRUM=use, NRW=wait)
        resource.append(r)
    total = {k: 0 for k in rz}
    total.update(RID="Total over all Resources", STID="Total over all Stations")
    for k in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        total[k] = f32(sum(r[k] * .5 for r in resource) / 36)
    if role in ROLES:
        want = gate["source_event_integrals_by_arm"][role]
        got = {k: sum(s[k] * .5 for s in system) for k in want if k not in ("NPSTA", "NPSUC")}
        assert got == want, (role, got, want)
        assert {k: total[k] for k in gate["resource_fields"]["total_expected_float32"][role]} == gate["resource_fields"]["total_expected_float32"][role]
    desc = table(model, "model", "ProblemDescription")["instances"][0]["rows"][0][0]
    return {"ProblemDescription": [{"PDESC": desc}],
            "ResultSummary": [gate["result_summary_expected"]],
            "SystemResults": system, "StockTotalResults": stock,
            "ResourceResults": resource, "ResourceResultsTotal": [total]}


def check_report(contract, model, role, timeline, doc):
    expected = make_expected_report(contract, model, role, timeline)
    tt = tables(doc, "report")
    topo = contract["report_gate"]["topology"]
    assert [t["name"] for t in tt] == [t["name"] for t in topo]
    parent_doc = parse_json((PARENT_RUN / "out-report-raw.json").read_bytes(), native=True)
    parent_meta = {t["name"]: t["columns"] for t in tables(parent_doc, "report")}
    count = 0
    for t, spec in zip(tt, topo):
        name = spec["name"]
        assert set(t) == {"name", "columns", "instances"}
        assert same_type(t["columns"], parent_meta[name])
        assert [c["name"] for c in t["columns"]] == spec["columns"]
        assert len(t["instances"]) == 1
        inst = t["instances"][0]
        assert set(inst) == {"instance_name", "rows"} and inst["instance_name"] == spec["instance_name"]
        assert len(inst["rows"]) == spec["rows"]
        for row, want in zip(inst["rows"], expected[name]):
            assert len(row) == len(spec["columns"])
            for col, value in zip(spec["columns"], row):
                target = want[col]
                dtype = t["columns"][spec["columns"].index(col)]["datatype"]
                good = (type(value) is int and value == target) if dtype == "integer" else (num_equal(value, target) if dtype in ("double", "float") and target is not None else same_type(value, target))
                assert good, (role, name, col, value, target)
                count += 1
    assert count == contract["report_gate"]["cells_per_arm"]
    return count


def pure_parent_check():
    c = parse_json(CONTRACT.read_bytes())
    parent, predicted = parent_and_predictions(c)
    timeline = predicted_timeline("accepted_parent")
    report = parse_json((PARENT_RUN / "out-report-raw.json").read_bytes(), native=True)
    return check_report(c, parent, "accepted_parent", timeline, report)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pure-parent", action="store_true")
    args = p.parse_args()
    if args.pure_parent:
        print(json.dumps({"mode": "PURE_PARENT_STATIC", "cells": pure_parent_check(), "new_native_calls": 0}, sort_keys=True))
    else:
        raise RuntimeError("sealed dual-arm replay awaits original new runs and frozen provenance schemas")


if __name__ == "__main__":
    main()





# The following grammar is derived from the accepted parent raw log's native
# vocabulary. It normalizes only object serials and printed state quantities;
# the role-specific ledger below restores exact identities, counts and values.
_TIMED = re.compile(r"^Time: ((?:0|[1-9][0-9]*)(?:\.[0-9]+)?)\s+(.*)$")
_TRANSFER = re.compile(r"resource transfer task (\d+) \(OUT\)\s+(.*)\Z")
_BOOK = re.compile(r"<P-CREW at <BASE-01,0>> allocated to maintenance task: 1\s+available now: (\d+)\Z")
_RELEASE = re.compile(r"<P-CREW at <BASE-01,0>> deallocated from\s+maintenance task: 1\s+available now: (\d+)\Z")
_READY = re.compile(r"<TEACH-AIR-01,([01])> nbr ready (increased|decreased) at unit: <TEACH-UNIT at <BASE-01,0>>\Z")


def signature(text):
    text = _TIMED.sub(lambda m: m.group(2), text).strip()
    text = re.sub(r"<BASIC-MISSION,TEACH-UNIT,0,0,[01]>", "<MISSION>", text)
    text = re.sub(r"<TEACH-AIR-01,[01]>", "<AIR>", text)
    text = re.sub(r"\b(resource transfer task|system preparation task|subtask) \d+", lambda m: m.group(1) + " N", text)
    text = re.sub(r"available now: \d+", "available now: Q", text)
    text = re.sub(r"(?:starts|arrives) with \d+ resources", lambda m: m.group(0).split(" with ")[0] + " with Q resources", text)
    text = re.sub(r"\bNbr: \d+", "Nbr: Q", text)
    text = re.sub(r"P-CREW \d+", "P-CREW Q", text)
    text = re.sub(r"resources at: <BASE-01,0> \d+", "resources at: <BASE-01,0> Q", text)
    text = re.sub(r"systems ready: \d+", "systems ready: Q", text)
    return text


def parse_typed_log(raw, role):
    assert role in ("accepted_parent",) + ROLES
    lines = raw.decode("utf-8-sig").splitlines()
    assert lines[:2] == ["SIMLOX LOG FILE", "36"]
    parent_lines = (PARENT_RUN / "out.log").read_bytes().decode("utf-8-sig").splitlines()
    permitted = {signature(x) for x in parent_lines[2:] if x.strip()}
    events = []
    previous = -1.0
    for n, line in enumerate(lines[2:], start=3):
        if not line.strip():
            continue
        assert signature(line) in permitted, ("unknown log family", n, line)
        m = _TIMED.fullmatch(line)
        if m:
            hour = float(m.group(1))
            assert math.isfinite(hour) and 0 <= hour <= 36 and hour >= previous, (n, hour)
            previous = hour
            events.append({"line": n, "hour": hour, "body": m.group(2).strip(), "continuations": []})
        else:
            assert events and line[0].isspace(), ("orphan continuation", n, line)
            events[-1]["continuations"].append(line.strip())
    assert events and events[-1]["hour"] == 36
    return events


def selected(events, body, hour=None):
    hits = [e for e in events if e["body"] == body and (hour is None or e["hour"] == hour)]
    assert len(hits) == 1, ("event cardinality", body, hour, [(x["line"], x["hour"]) for x in hits])
    return hits[0]


def ordered(*events):
    assert all(a["line"] < b["line"] for a, b in zip(events, events[1:])), "same-time causal order"


def check_transfer_and_local(events, role):
    opening = 2 if role == "accepted_parent" else 3
    back_add = [e for e in events if e["body"] == "<P-CREW at <BASE-01,0>> Resource transfer backorder added"]
    back_remove = [e for e in events if e["body"] == "<P-CREW at <BASE-01,0>> Resource transfer backorder removed"]
    expected_back = role in ("accepted_parent", "child_out2")
    assert [e["hour"] for e in back_add] == ([7.75] if expected_back else [])
    assert [e["hour"] for e in back_remove] == ([8] if expected_back else [])
    demand = selected(events, "<P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer", 7.75)
    created, starts, arrivals = {}, {}, {}
    for e in events:
        m = _TRANSFER.fullmatch(e["body"])
        if not m:
            continue
        ident, action = int(m.group(1)), m.group(2)
        if action == "created: starting from  <P-CREW at <BASE-01,0>>":
            assert ident not in created
            created[ident] = e
        elif (q := re.fullmatch(r"starts with (\d+) resources, transfer time: 0", action)):
            assert ident not in starts
            starts[ident] = (e, int(q.group(1)))
        elif (q := re.fullmatch(r"arrives with (\d+) resources", action)):
            assert ident not in arrivals
            arrivals[ident] = (e, int(q.group(1)))
        else:
            raise AssertionError(("unknown transfer action", e))
    assert created and created.keys() == starts.keys() == arrivals.keys()
    tranches = []
    zeros = []
    for ident, c in created.items():
        s, quantity = starts[ident]
        a, arrived = arrivals[ident]
        assert quantity == arrived and quantity in (0, 1)
        assert c["hour"] == s["hour"] == a["hour"] and c["hour"] in (7.75, 8)
        if c["hour"] == 7.75:
            ordered(c, demand, s, a)
        else:
            ordered(demand, c, s, a)
        (tranches if quantity else zeros).append((ident, s))
    want_tranches = [8] if role == "accepted_parent" else [7.75] if role == "control_out1" else [7.75, 8]
    assert [e["hour"] for _, e in tranches] == want_tranches
    assert len(zeros) <= 1 and all(e["hour"] == 7.75 for _, e in zeros)
    assert sum(q for _, q in starts.values()) == (2 if role == "child_out2" else 1)
    if expected_back:
        ordered(demand, back_add[0], back_remove[0], tranches[-1][1])
    free, booked, completed = opening, 0, 0
    positive_lines = {e["line"] for _, e in tranches if e["hour"] == 7.75}
    reservation_lines = {e["line"] for e in back_remove}
    booking_edges, release_edges = [], []
    active_owners = set()
    pending_book = pending_release = None
    sub_book = re.compile(r"subtask (\d+) seqno 1 within system preparation task \1 on <TEACH-AIR-01,([01])> books resources\Z")
    sub_free = re.compile(r"subtask (\d+) seqno 1 within system preparation task \1 on <TEACH-AIR-01,([01])> frees resources\Z")
    for e in events:
        m_book, m_rel = _BOOK.fullmatch(e["body"]), _RELEASE.fullmatch(e["body"])
        sb, sf = sub_book.fullmatch(e["body"]), sub_free.fullmatch(e["body"])
        if sb:
            assert pending_book is None
            pending_book = (int(sb.group(1)), int(sb.group(2)))
            assert pending_book not in active_owners
        if sf:
            assert pending_release is None
            pending_release = (int(sf.group(1)), int(sf.group(2)))
            assert pending_release in active_owners
        if e["line"] in positive_lines or e["line"] in reservation_lines:
            assert free >= 1
            free -= 1
            completed += 1
        elif m_book:
            assert free >= 1 and pending_book is not None
            free -= 1
            booked += 1
            active_owners.add(pending_book)
            pending_book = None
            assert int(m_book.group(1)) == free
            booking_edges.append(e)
        elif m_rel:
            assert booked >= 1 and pending_release is not None
            free += 1
            booked -= 1
            active_owners.remove(pending_release)
            pending_release = None
            assert int(m_rel.group(1)) == free
            release_edges.append(e)
        assert free >= 0 and booked >= 0 and free + booked + completed == opening, (e["line"], free, booked, completed)
        for c in e["continuations"]:
            if c.startswith("Free resources at:"):
                assert c == f"Free resources at: <BASE-01,0> P-CREW {free}"
                assert e["body"] == "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period"
            if c.startswith("Missions and tasks using resources at:"):
                assert c == f"Missions and tasks using resources at: <BASE-01,0> {booked}"
                assert m_book or e["body"] == "resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period"
                listings = [x for x in e["continuations"] if x.startswith("< subtask ")]
                observed = set()
                for listing in listings:
                    found = re.fullmatch(r"< subtask (\d+) seqno 1 within system preparation task \1 on <TEACH-AIR-01,([01])>, C, 1, 0\.5>", listing)
                    assert found is not None, listing
                    observed.add((int(found.group(1)), int(found.group(2))))
                assert len(listings) == len(observed) == booked and observed == active_owners
            if c.startswith("Resource transfer backorders at:"):
                if e in back_add:
                    assert c == "Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: 1 Backorders:<OUT,7.75>,"
                elif e in back_remove:
                    assert c == "Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: 0"
                else:
                    raise AssertionError("backorder snapshot wrong owner")
            if c.startswith("Resource transfer backorders at:"):
                want = 1 if expected_back and e["hour"] == 7.75 else 0
                assert f"Nbr: {want}" in c and (("Backorders:<OUT,7.75>" in c) == (want == 1))
            if c in ("no failures", "no PMTasks"):
                assert " System arrives " in e["body"]
    assert pending_book is None and pending_release is None and not active_owners
    assert len(booking_edges) == len(release_edges) == 4
    if expected_back:
        assert release_edges[0]["line"] < back_remove[0]["line"] < release_edges[1]["line"]
        assert back_remove[0]["line"] < created[tranches[-1][0]]["line"] < release_edges[1]["line"]
    terminal = (1, 0, 2) if role == "child_out2" else (2, 0, 1) if role == "control_out1" else (1, 0, 1)
    assert (free, booked, completed) == terminal
    assert sum(c == "no failures" for e in events for c in e["continuations"]) == 4
    assert sum(c == "no PMTasks" for e in events for c in e["continuations"]) == 4
    return {"positive_tranches": [(i, e["hour"]) for i, e in tranches], "terminal": terminal,
            "bookings": booking_edges, "releases": release_edges}


def check_missions_and_aircraft(events, role):
    waves = predicted_timeline(role)["waves"]
    mission_starts, mission_ends = [], []
    task_ids = set()
    ready = set()
    ready_edges = []
    for e in events:
        m = _READY.fullmatch(e["body"])
        if not m:
            continue
        air, action = int(m.group(1)), m.group(2)
        if action == "increased":
            assert air not in ready
            ready.add(air)
        else:
            assert air in ready
            ready.remove(air)
        ready_edges.append((e["hour"], air, action))
    actual_ready = set()
    snapshot_count = 0
    for e in events:
        match = _READY.fullmatch(e["body"])
        if match:
            air, action = int(match.group(1)), match.group(2)
            if action == "increased":
                assert air not in actual_ready
                actual_ready.add(air)
            else:
                assert air in actual_ready
                actual_ready.remove(air)
        m = re.fullmatch(r"<TEACH-UNIT at <BASE-01,0>> systems ready: ([0-2]) :(.*)", e["body"])
        if m:
            listed = re.findall(r"<TEACH-AIR-01,([01])>", m.group(2))
            assert len(listed) == len(set(listed)) == int(m.group(1)) == len(actual_ready)
            assert {int(x) for x in listed} == actual_ready
            snapshot_count += 1
    assert snapshot_count == 5
    expected_ready = [(0, 0, "increased"), (0, 1, "increased")]
    for w in waves:
        expected_ready += [(w["start"], 0, "decreased"), (w["start"], 1, "decreased")]
        expected_ready += [(w["return"], 0, "increased"), (w["return"], 1, "increased")]
    assert ready_edges == expected_ready and ready == {0, 1}
    for index, w in enumerate(waves):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>"
        order = selected(events, "<TEACH-UNIT> mission ordered: BASIC-MISSION", w["start"])
        create = selected(events, mission + " mission created:", w["start"])
        activate = selected(events, mission + " mission activated, systems requested: 2", w["start"])
        launch = selected(events, mission + " mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", w["launch"])
        task_start = selected(events, mission + " task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", w["launch"] + .25)
        task_end = selected(events, mission + " task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", w["launch"] + .75)
        success = selected(events, mission + " mission success:", w["return"])
        complete = selected(events, mission + " mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", w["return"])
        ordered(order, create, activate, launch, task_start, task_end, success, complete)
        mission_starts.append(launch["hour"])
        mission_ends.append(complete["hour"])
        for aircraft in (0, 1):
            air = f"<TEACH-AIR-01,{aircraft}>"
            task_candidates = [e for e in events if e["hour"] == w["start"] and re.fullmatch(r"system preparation task (\d+) on " + re.escape(air) + r" started", e["body"])]
            assert len(task_candidates) == 1, ("task identity", index, aircraft)
            taskid = int(re.fullmatch(r"system preparation task (\d+) on " + re.escape(air) + r" started", task_candidates[0]["body"]).group(1))
            prep_start = selected(events, air + " preparation started, mission: " + mission, w["start"])
            prep_end = selected(events, air + " preparation ended, mission: " + mission, w["prep"][aircraft][1])
            main_start = selected(events, f"system preparation task {taskid} on {air} started", w["start"])
            main_end = selected(events, f"system preparation task {taskid} on {air} completed", w["prep"][aircraft][1])
            assert taskid not in task_ids
            task_ids.add(taskid)
            sub = f"subtask {taskid} seqno 1 within system preparation task {taskid} on {air}"
            sub_start = selected(events, sub + " started", w["start"])
            request = selected(events, sub + " requests resources", w["start"])
            booking_hour = w["prep"][aircraft][0]
            tests = [e for e in events if e["body"] == sub + " resource availability test"]
            waiting = bool(w["wait"] and aircraft == 1)
            assert [e["hour"] for e in tests] == ([w["start"], booking_hour] if waiting else [booking_hour])
            assert [e["continuations"] for e in tests] == ([
                ["Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed"],
                ["Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK"]
            ] if waiting else [["Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK"]])
            received = [e for e in events if e["body"] == sub + " resource received"]
            assert [e["hour"] for e in received] == ([booking_hour] if waiting else [])
            booking = selected(events, sub + " books resources", booking_hour)
            if waiting:
                ordered(tests[0], tests[1], received[0], booking)
            else:
                ordered(tests[0], booking)
            work = selected(events, sub + " starts performing, planned to last for 0.5 hours", w["prep"][aircraft][0])
            sub_complete = selected(events, sub + " completed", w["prep"][aircraft][1])
            frees = selected(events, sub + " frees resources", w["prep"][aircraft][1])
            remote = selected(events, f"subtask {taskid} seqno 1 check return remote resources", w["prep"][aircraft][1])
            transport = selected(events, "<P-CREW at <BASE-01,0>> check for return transport: 1", w["prep"][aircraft][1]) if w["prep"][aircraft][1] not in (8, 20) else None
            ordered(prep_start, main_start, sub_start, request, booking, work, sub_complete, frees, remote, main_end, prep_end, launch)
            arrival = selected(events, f"<TEACH-AIR-01,BASE-01,0> System arrives {air}, mission success,", w["return"])
            assert arrival["continuations"] == ["no failures", "no PMTasks"]
            soon = selected(events, f"<TEACH-AIR-01,BASE-01,0> System soon ready {air}, estimated remaining time: 0", w["return"])
            turn_start = selected(events, air + " turnround started, mission: " + mission + " reduction factor: 1", w["return"])
            turn_end = selected(events, air + " turnround ended, mission: " + mission, w["return"])
            ready_lines = [e for e in events if e["body"] == f"<TEACH-AIR-01,BASE-01,0> System ready {air}" and e["hour"] == w["return"]]
            assert len(ready_lines) == 2
            ordered(complete, soon, turn_start, turn_end, arrival, ready_lines[0], ready_lines[1])
    assert len(task_ids) == 4
    queue = [(e["hour"], c, e["body"]) for e in events for c in e["continuations"] if c.startswith("Tasks waiting for resources at:")]
    if role == "control_out1":
        assert [(h, int(c.rsplit(" ", 1)[1])) for h, c, _ in queue] == [(0, 0), (0, 0), (8, 0), (8, 0), (20, 0), (20, 0), (24, 0)]
    else:
        assert [(h, int(c.rsplit(" ", 1)[1])) for h, c, _ in queue] == [(0, 0), (0, 0), (8, 0), (8, 0), (20, 1), (20, 0), (20.5, 0), (24, 0)]
    assert mission_starts == [w["launch"] for w in waves] and mission_ends == [w["return"] for w in waves]
    assert sum(e["body"].endswith("mission success:") for e in events) == 2
    return waves


def physical_from_original(raw, role):
    events = parse_typed_log(raw, role)
    check_family_cardinality(events, role)
    transfer = check_transfer_and_local(events, role)
    waves = check_missions_and_aircraft(events, role)
    return {"waves": waves, "physical": predicted_timeline(role)["physical"],
            "nominal": predicted_timeline(role)["nominal"], "opening": predicted_timeline(role)["opening"],
            "transfer": transfer, "typed_events": len(events)}





def check_family_cardinality(events, role):
    """Exact source-bound native diagnostic vocabulary/counts; zero OUT tasks vary."""
    from collections import Counter
    baseline = parse_typed_log((PARENT_RUN / "out.log").read_bytes(), "accepted_parent") if role != "accepted_parent" else events
    actual = Counter(signature(e["body"]) for e in events)
    wanted = Counter(signature(e["body"]) for e in baseline)
    for name in tuple(wanted):
        if name.startswith("resource transfer task N (OUT)"):
            del wanted[name]
            actual.pop(name, None)
    if role == "control_out1":
        deltas = {
            "<P-CREW at <BASE-01,0>> Resource transfer backorder added": -1,
            "<P-CREW at <BASE-01,0>> Resource transfer backorder removed": -1,
            "subtask N seqno 1 within system preparation task N on <AIR> resource availability test": -1,
            "subtask N seqno 1 within system preparation task N on <AIR> resource received": -1,
        }
        for name, delta in deltas.items():
            wanted[name] += delta
            if wanted[name] == 0:
                del wanted[name]
    assert actual == wanted, ("timed event family count", actual - wanted, wanted - actual)
    parent_cont = Counter(signature(c) for e in baseline for c in e["continuations"])
    actual_cont = Counter(signature(c) for e in events for c in e["continuations"])
    if role == "control_out1":
        deltas = {
            "< subtask N seqno 1 within system preparation task N on <AIR>, C, 0.5>": -1,
            "< subtask N seqno 1 within system preparation task N on <AIR>, C, 1, 0.5>": 1,
            "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed": -1,
            "Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: Q": -1,
            "Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: Q Backorders:<OUT,7.75>,": -1,
            "Tasks waiting for resources at: <BASE-01,0> Q": -1,
        }
        for name, delta in deltas.items():
            parent_cont[name] += delta
            if parent_cont[name] == 0:
                del parent_cont[name]
    assert actual_cont == parent_cont, ("continuation family count", actual_cont - parent_cont, parent_cont - actual_cont)
    for e in events:
        cont = e["continuations"]
        if " System arrives " in e["body"]:
            assert cont == ["no failures", "no PMTasks"]
        elif any(c in ("no failures", "no PMTasks") for c in cont):
            raise AssertionError("return diagnostics on wrong owner")
        if any(c.startswith("Availability test on") for c in cont):
            assert e["body"].endswith("resource availability test") and sum(c.startswith("Availability test on") for c in cont) == 1
        if any(c.startswith("Tasks waiting for resources at:") for c in cont):
            assert e["body"] == "<BASE-01,0> trig missions and tasks waiting for resources" or e["body"].endswith("Next random failure will occur 1e+010")
        if any(c.startswith("< subtask ") for c in cont):
            assert e["body"].endswith("books resources") or e["body"] == "<BASE-01,0> trig missions and tasks waiting for resources" or "allocated to maintenance task" in e["body"]



