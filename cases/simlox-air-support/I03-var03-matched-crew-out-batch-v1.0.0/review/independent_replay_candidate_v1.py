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
                assert (num_equal(value, target) if type(target) in (int, float) else same_type(value, target)), (role, name, col, value, target)
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



