"""In-memory semantic negative checks for independent I03.var05 reader.

Each mutation is sent directly to the semantic gate after a clean pure baseline;
no fabricated actual run directory or native evidence is created.
"""

import copy
import json
from pathlib import Path
import struct

import independent_replay as reader


def rejects(label, callback, record):
    try:
        callback()
    except (AssertionError, ValueError, UnicodeError, KeyError, TypeError):
        record.append(label)
        return
    raise AssertionError(("semantic mutation escaped", label))


def f32_adjacent(value, sign):
    bit = struct.unpack("<I", struct.pack("<f", value))[0]
    return struct.unpack("<f", struct.pack("<I", bit + sign))[0]


def main():
    baseline = reader.Audit()
    pure = reader.pure_source_event_report(baseline)
    contract, parent, prediction = pure["contract"], pure["parent"], pure["prediction"]
    canonical = pure["canonical_report"]
    child_report = reader.make_pure_child_report(contract, canonical)
    _, lines = reader.predicted_log_lines(reader.Audit())
    rejected = []

    parser_bad = {
        "duplicate_json_key": b'{"model":{},"model":{}}',
        "nan_constant": b'{"model":NaN}',
        "infinity_constant": b'{"model":Infinity}',
        "overflow_exponent": b'{"model":{"x":1e999}}',
        "malformed_root": b'["model"]',
    }
    for name, raw in parser_bad.items():
        if name == "malformed_root":
            rejects(name, lambda raw=raw: reader.recursive_same(reader.parse_json(raw), prediction, reader.Audit()), rejected)
        else:
            rejects(name, lambda raw=raw: reader.parse_json(raw), rejected)
    rejects("extra_native_trailing_comma", lambda: reader.parse_json(b'{"report":{"tables":[],},}', native=True), rejected)

    source_mutations = {
        "TFDT_bool": lambda doc: doc["model"]["tables"][23]["instances"][0]["rows"][1].__setitem__(5, False),
        "TFDT_wrong_zero": lambda doc: doc["model"]["tables"][23]["instances"][0]["rows"][1].__setitem__(5, 0.5),
        "source_extra_table": lambda doc: doc["model"]["tables"].append(copy.deepcopy(doc["model"]["tables"][0])),
        "source_duplicate_instance": lambda doc: doc["model"]["tables"][23]["instances"].append(copy.deepcopy(doc["model"]["tables"][23]["instances"][0])),
        "source_database_bool": lambda doc: doc["model"].__setitem__("database_version", True),
        "source_extra_root_key": lambda doc: doc.__setitem__("extra", 1),
    }
    for name, mutation in source_mutations.items():
        doc = copy.deepcopy(prediction)
        mutation(doc)
        rejects(name, lambda doc=doc: reader.recursive_same(doc, prediction, reader.Audit()), rejected)

    accepted_export = reader.accepted_parent_roundtrip(parent, reader.Audit())
    export_mutations = {
        "export_duplicate_table": lambda doc: doc["model"]["tables"].append(copy.deepcopy(doc["model"]["tables"][0])),
        "export_bad_placeholder": lambda doc: doc["model"]["tables"][5]["instances"][0]["rows"][0].__setitem__(0, 0),
        "export_bool_double": lambda doc: doc["model"]["tables"][2]["instances"][0]["rows"][0].__setitem__(1, True),
        "export_column_key_type": lambda doc: doc["model"]["tables"][23]["columns"][0].__setitem__("key", 1),
        "export_wrong_instance": lambda doc: doc["model"]["tables"][23]["instances"][0].__setitem__("instance_name", "WRONG"),
    }
    for name, mutation in export_mutations.items():
        doc = copy.deepcopy(accepted_export)
        mutation(doc)
        raw = json.dumps(doc, ensure_ascii=False).encode()
        rejects(name, lambda raw=raw: reader.check_roundtrip(parent, raw, reader.Audit()), rejected)

    log_mutations = {
        "h10_printed_delay_half": ("transfer time: 0", "transfer time: 0.5"),
        "h10_arrival_late": ("Time: 10  resource transfer task 2 (IN)  arrives", "Time: 10.5  resource transfer task 2 (IN)  arrives"),
        "h10_receipt_wrong_quantity": ("transfer arrives: 1", "transfer arrives: 2"),
        "h8_release_free_two": ("available now: 1", "available now: 2"),
        "h8_backorder_missing": ("Resource transfer backorder removed", "Resource transfer backorder LOST"),
        "wrong_horizon": ("36", "35"),
        "other_event_unknown": ("mission starting, duration: 1", "mission starting, duration: 9"),
    }
    for name, (old, new) in log_mutations.items():
        change = list(lines)
        if name == "wrong_horizon":
            change[1] = new
        else:
            hits = [i for i, line in enumerate(change) if old in line]
            assert hits, (name, old)
            change[hits[0]] = change[hits[0]].replace(old, new, 1)
        raw = ("\n".join(change) + "\n").encode()
        rejects(name, lambda raw=raw: reader.check_typed_child_log(raw, reader.Audit()), rejected)
    for name, mutation in (
        ("duplicate_IN_receipt", lambda x: x.insert(next(i for i,v in enumerate(x) if "transfer arrives: 1" in v), next(v for v in x if "transfer arrives: 1" in v))),
        ("missing_IN_arrival", lambda x: x.pop(next(i for i,v in enumerate(x) if "task 2 (IN)  arrives" in v))),
        ("reorder_receipt_before_arrival", lambda x: x.insert(next(i for i,v in enumerate(x) if "task 2 (IN)  arrives" in v), x.pop(next(i for i,v in enumerate(x) if "transfer arrives: 1" in v)))),
        ("extra_same_template_ready", lambda x: x.append(next(v for v in x if "System ready" in v))),
    ):
        change = list(lines)
        mutation(change)
        raw = ("\n".join(change) + "\n").encode()
        rejects(name, lambda raw=raw: reader.check_typed_child_log(raw, reader.Audit()), rejected)

    def report_change(name, table, row, column, value):
        doc = copy.deepcopy(child_report)
        t = next(t for t in doc["report"]["tables"] if t["name"] == table)
        ci = [c["name"] for c in t["columns"]].index(column)
        t["instances"][0]["rows"][row][ci] = value
        rejects(name, lambda doc=doc: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)

    report_change("NREP_float", "ResultSummary", 0, "NREP", 1.0)
    report_change("System_zero_residue", "SystemResults", 0, "NSYWR", 1e-9)
    report_change("System_identity_wrong", "SystemResults", 0, "UNID", "wrong")
    report_change("Stock_null_to_zero", "StockTotalResults", 0, "WTS", 0)
    report_change("Stock_presentation_wrong", "StockTotalResults", 0, "PNB", 0)
    report_change("Resource_h10_old", "ResourceResults", 20, "NR", 1)
    report_change("Resource_h10_nominal_old", "ResourceResults", 20, "NRN", 1)
    report_change("Resource_early_return", "ResourceResults", 19, "NRA", 2)
    report_change("Resource_wrong_identity", "ResourceResults", 20, "STID", "wrong")
    report_change("Total_null", "ResourceResultsTotal", 0, "NR", None)
    total = next(t for t in child_report["report"]["tables"] if t["name"] == "ResourceResultsTotal")
    cols = [c["name"] for c in total["columns"]]
    for name in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        value = total["instances"][0]["rows"][0][cols.index(name)]
        for direction in (-1, 1):
            report_change(f"Total_{name}_{direction:+d}ULP", "ResourceResultsTotal", 0, name, f32_adjacent(value, direction))
    doc = copy.deepcopy(child_report)
    doc["report"]["tables"][2]["columns"][0]["key"] = 1
    rejects("report_bool_key_to_int", lambda: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)
    doc = copy.deepcopy(child_report)
    doc["report"]["tables"].append(copy.deepcopy(doc["report"]["tables"][0]))
    rejects("report_extra_table", lambda: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)
    doc = copy.deepcopy(child_report)
    doc["report"]["tables"][4]["instances"][0]["rows"][20][4] = float("inf")
    rejects("report_nonfinite", lambda: reader.check_report(contract, "child", doc, canonical, reader.Audit()), rejected)

    print(json.dumps({"decision": "STATIC_ONLY_SELF_CHECK", "baseline_checks": baseline.checks,
        "parent_report_cells": pure["parent_report_cells"],
        "prospective_child_report_cells": pure["prospective_child_report_cells"],
        "semantic_rejections": len(rejected), "rejected": rejected, "native_started": False}, sort_keys=True))


if __name__ == "__main__":
    main()
