"""Independent read-only I03.var02 source, event, and 5,210-cell replay.

The child branch is prospective until its guarded run exists. No author checker
is imported; expected values are computed from frozen source and event edges.
"""

import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
from copy import deepcopy
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = next(p for p in PKG.parents if (p / ".git").exists())
BASE = "2e9f1e178056469a9903640ff970a5f2375274d4"
CONTRACT_SHA = "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"
PARENT_RUN = REPO / "cases/simlox-air-support/I03-var01-crew-out-in-v1.0.0/runs/i03-var01-crew-transfer-v100-ssh-20261005-01"
CHILD_RUN = PKG / "runs/i03-var02-idle-out-v102-ssh-20261007-01"


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


def git_blob(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=REPO)


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


def numeric(actual, expected):
    return (type(actual) in (int, float) and type(expected) in (int, float)
            and math.isfinite(actual) and math.isfinite(expected) and actual == expected)


def native_json(raw):
    text = raw.decode("utf-8-sig")
    # The accepted exporter emits precisely one trailing comma. The replacement
    # only changes an in-memory parsing copy, never the sealed raw evidence.
    return json.loads(re.sub(r",(?=\s*[}\]])", "", text))


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


def source_pins(contract, a):
    lineage = contract["source_lineage"]
    a.ok(hashlib.sha256((PKG / "contract.json").read_bytes()).hexdigest() == CONTRACT_SHA,
         "frozen contract")
    a.ok(contract["run_id"] == CHILD_RUN.name and contract["ownership"]["base_commit"] == BASE,
         "run/base identity")
    for key in ("root_selection_receipt", "root_live_context", "accepted_parent_index"):
        rec = lineage[key]
        exact(REPO / rec["path"], rec, a, key)
    catalog = lineage["catalog_at_selection"]
    archive = exact(PKG / catalog["owned_exact_archive"], catalog["owned_archive_pin"], a, "catalog archive")
    a.ok(pin(git_blob(catalog["path"])) == catalog["published_git_at_base"], "catalog base Git")
    old = json.loads(archive)
    live = json.loads((REPO / catalog["path"]).read_bytes())
    a.ok(len(old["entries"]) == 490 and len(live["entries"]) >= 490,
         "catalog entry count")
    a.ok(same_type(old["entries"], live["entries"][:490]), "catalog original prefix")
    a.ok(same_type({k: v for k, v in old.items() if k != "entries"},
                   {k: v for k, v in live.items() if k != "entries"}), "catalog metadata")
    ids = [e["publication_id"] for e in live["entries"]]
    a.ok(len(ids) == len(set(ids)) and all(type(i) is str and i for i in ids), "catalog unique IDs")
    if len(live["entries"]) == 490:
        a.ok(pin((REPO / catalog["path"]).read_bytes()) == catalog["historical_original_at_selection_pin"],
             "catalog prepublication exact")
    for rec in lineage["accepted_source_local_vs_published_git_at_base"]:
        exact(REPO / rec["path"], rec["local_disk"], a, rec["path"] + " local")
        a.ok(pin(git_blob(rec["path"])) == rec["published_git_at_base"], rec["path"] + " Git")
    for rec in lineage["accepted_original_run_records"]:
        exact(Path(rec["path"]), rec, a, rec["path"])
    for rec in lineage["installed"].values():
        exact(Path(rec["path"]), rec, a, rec["path"])
    for rec in (lineage["excluded_v100_NO_GO_files"] + lineage["excluded_v101_NO_GO_files"] +
                lineage["owned_historical_root_context"]):
        exact(PKG / rec["owned_inert_copy"], rec, a, rec["owned_inert_copy"])
        original = REPO / rec["original_path"]
        if original.exists():
            exact(original, rec, a, rec["original_path"])


def parent_and_prediction(contract, a):
    src = REPO / contract["scope"]["source_parent"]
    raw = src.read_bytes()
    a.ok(hashlib.sha256(raw).hexdigest() == contract["scope"]["source_parent_sha256"], "parent input")
    parent = json.loads(raw)
    source_tables(parent, "model", a)
    a.ok(parent["model"]["database_version"] == 20160627, "database version")
    predicted = deepcopy(parent)
    for t in predicted["model"]["tables"]:
        if t["name"] == "ProblemDescription":
            t["instances"][0]["rows"][0][0] = contract["source_delta"]["allowed_changes_exactly"][0]["to"]
        elif t["name"] == "ResourceTransfer":
            t["instances"][0]["rows"][0][3] = 6.0
    different = []
    for old, new in zip(parent["model"]["tables"], predicted["model"]["tables"]):
        if old != new:
            different.append(old["name"])
    a.ok(different == ["ProblemDescription", "ResourceTransfer"], "sole two source tables")
    transfer = source_tables(predicted, "model", a)["ResourceTransfer"]["instances"][0]["rows"]
    a.ok(transfer == [contract["source_delta"]["child_transfer_row"]], "child transfer source")
    return parent, predicted


def roundtrip(authored, exported, a, label):
    left = source_tables(authored, "model", a)
    right = source_tables(exported, "model", a)
    a.ok(authored["model"]["database_version"] == exported["model"]["database_version"],
         label + " database version")
    a.ok([t["name"] for t in tables(authored, "model")] ==
         [t["name"] for t in tables(exported, "model")], label + " ordered table names")
    for name, source in left.items():
        target = right[name]
        a.ok(same_type(source["columns"], target["columns"]), label + "/" + name + " columns")
        a.ok([i["instance_name"] for i in source["instances"]] ==
             [i["instance_name"] for i in target["instances"]], label + "/" + name + " instances")
        a.ok(len(source["instances"]) == len(target["instances"]), label + "/" + name + " instance count")
        for x, y in zip(source["instances"], target["instances"]):
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


def expected_report(contract, model, role):
    assert role in ("busy", "idle")
    topology = contract["report_gate"]["topology"]
    template = {t["name"]: t for t in topology}
    desc = next(t for t in model["model"]["tables"] if t["name"] == "ProblemDescription")["instances"][0]["rows"][0][0]
    busy = role == "busy"
    launch = (8.0 if busy else 8.5, 20.5)
    prep = (7.5, 19.5)
    physical_out = 8.0 if busy else 6.0
    nominal_out = 7.75 if busy else 6.0
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
        for wave, start in enumerate(prep):
            first_end = start + .5
            mission_start = launch[wave]
            mission_end = mission_start + 1
            if start <= t < mission_end:
                s["NSYRY"] = 0
                s["NSYMA"] = 2
            if t == start:
                s["NSYMP"] = 2
                s["NPSTA"] = 2
            if first_end <= t < mission_start:
                s["NSYMP"] = 1
                s["NSYMR"] = 1
            if t == first_end:
                s["NPSUC"] += 2 if mission_start == first_end else 1
            if t == mission_start and mission_start != first_end:
                s["NPSUC"] += 1
            if mission_start <= t < mission_end:
                s["NSYMO"] = 2
                s["FTMO"] = 1
                s["STACC"] = 2
        system.append(s)
        q = {k: 0 for k in stock_zero}
        q.update(STINT=t, ETINT=t + .5, PNB=1)
        q.update({k: None for k in stock_null})
        stock.append(q)
        r = {k: 0 for k in resource_zero}
        # Every boundary is an exact quarter- or half-hour source/event edge.
        # The busy comparator's 7.75 nominal change averages to 1.5 in one bin.
        physical = 2 if t < physical_out else 1
        nominal = 1.5 if busy and t == 7.5 else (2 if t < nominal_out else 1)
        use = (2 if busy and t == 7.5 else 1) if t in (7.5, 8.0, 19.5, 20.0) else 0
        if busy and t == 8.0:
            use = 0
        wait = 1 if t == 19.5 or (not busy and t == 7.5) else 0
        r.update(RID="Total over all Resources", STID="Total over all Stations", STINT=t, ETINT=t + .5,
                 NR=physical, NRA=physical, NRN=nominal, NRUM=use, NRW=wait)
        resource.append(r)
    total = {k: 0 for k in resource_zero}
    total.update(RID="Total over all Resources", STID="Total over all Stations")
    for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        total[field] = f32(sum(row[field] * .5 for row in resource) / 36)
    summary = contract["report_gate"]["result_summary_expected"]
    expected = {"ProblemDescription": [{"PDESC": desc}], "ResultSummary": [summary],
                "SystemResults": system, "StockTotalResults": stock,
                "ResourceResults": resource, "ResourceResultsTotal": [total]}
    assert [len(expected[t["name"]]) for t in topology] == [1, 1, 72, 72, 72, 1]
    return expected


def compare_report(contract, model, doc, role, a):
    expected = expected_report(contract, model, role)
    got_tables = tables(doc, "report")
    topology = contract["report_gate"]["topology"]
    a.ok([t["name"] for t in got_tables] == [t["name"] for t in topology], role + " report table order")
    a.ok(len(got_tables) == 6, role + " report table count")
    cells = 0
    for table, spec in zip(got_tables, topology):
        name = spec["name"]
        a.ok([c["name"] for c in table["columns"]] == spec["columns"], role + "/" + name + " columns")
        a.ok(len(table["instances"]) == 1 and table["instances"][0]["instance_name"] == spec["instance_name"],
             role + "/" + name + " instance")
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
    out = native_json((PARENT_RUN / "out-roundtrip-raw.json").read_bytes())
    roundtrip(parent, out, a, "accepted busy out")
    report = native_json((PARENT_RUN / "out-report-raw.json").read_bytes())
    expected = compare_report(contract, parent, report, "busy", a)
    return expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-only", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    a = Audit()
    contract = json.loads((PKG / "contract.json").read_bytes())
    source_pins(contract, a)
    parent, predicted = parent_and_prediction(contract, a)
    parent_replay(contract, parent, a)
    if args.self_check:
        predicted_report = expected_report(contract, predicted, "idle")
        a.ok(len(predicted_report["SystemResults"]) == 72, "synthetic child report rows")
    elif not args.control_only:
        a.ok(CHILD_RUN.exists(), "sealed child run required")
        # Native child receipt, log and report checks are completed after the
        # author runner's frozen exact schema handoff; absence fails closed.
        raise AssertionError("child schema not yet frozen; no acceptance")
    print(json.dumps({"schema": "i03-var02-independent-replay/draft-v1", "status": "STATIC_ONLY",
                      "checks": a.checks, "parent_report_cells": 5210,
                      "child_report_cells_predicted": 5210}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
