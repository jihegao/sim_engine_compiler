"""Private under-hash mutations for the independent A17.var01 reader.

The pristine clone must pass the exact semantic function exercised by each
mutant. The outer source/raw SHA gates remain mandatory in sealed replay.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import independent_reader as reader

COUNT = 0

def rejects(label, fn, value):
    global COUNT
    try:
        fn(value)
    except (AssertionError, ValueError, KeyError, UnicodeError):
        COUNT += 1
    else:
        raise AssertionError("not rejected: " + label)

def changed_line(lines, index, old, new):
    result = lines[:]
    assert old in result[index]
    result[index] = result[index].replace(old, new, 1)
    return result

def swapped(lines, i, j):
    result = lines[:]
    result[i], result[j] = result[j], result[i]
    return result

def changed_cell(report, table, row, column, value):
    result = copy.deepcopy(report)
    result["tables"][table]["instances"][0]["rows"][row][column] = value
    return result

def main():
    lines, _ = reader.primary_lines()
    raw_log = ("\r\n".join(lines)+"\r\n").encode("utf-8")
    assert reader.physical_ledger(lines)["terminal_ready"] == 2
    assert reader.log_bytes(raw_log)["timed_lines"] == 52
    forms = json.loads((reader.CASE/"prospective-complete-log-forms.json").read_bytes())["full_forms"]
    assert len(forms) == 8
    for f in forms:
        if f["status"] != "PRIMARY_CONTRACT_PASS_CANDIDATE":
            b = ("\r\n".join(f["lines"])+"\r\n").encode("utf-8")
            rejects("nonprimary " + f["arm_id"], reader.log_bytes, b)
    rejects("log BOM", reader.log_bytes, b"\xef\xbb\xbf"+raw_log)
    rejects("log LF", reader.log_bytes, raw_log.replace(b"\r\n",b"\n"))
    rejects("log trailing blank", reader.log_bytes, raw_log+b"\r\n")
    rejects("wrong home unit", reader.physical_ledger, changed_line(lines, 6, "TEACH-UNIT-2", "TEACH-UNIT"))
    rejects("wrong source station", reader.physical_ledger, changed_line(lines, 6, "BASE-01", "BASE-02"))
    rejects("wrong station instance", reader.physical_ledger, changed_line(lines, 6, "BASE-01,0", "BASE-01,1"))
    rejects("wrong aircraft in unit line", reader.physical_ledger, changed_line(lines, 6, "TEACH-AIR-01,1", "TEACH-AIR-01,0"))
    rejects("duplicate allocation", reader.physical_ledger, changed_line(lines, 15, "TEACH-AIR-01,1", "TEACH-AIR-01,0"))
    rejects("ready decrease before allocation", reader.physical_ledger, swapped(lines, 12, 13))
    rejects("preparation end before start", reader.physical_ledger, swapped(lines, 18, 20))
    rejects("mission before preparation", reader.physical_ledger, swapped(lines, 22, 28))
    rejects("task completion before start", reader.physical_ledger, swapped(lines, 29, 30))
    rejects("turnround end before start", reader.physical_ledger, swapped(lines, 35, 39))
    rejects("arrival before turnround", reader.physical_ledger, swapped(lines, 39, 40))
    rejects("wrong return controller", reader.physical_ledger, changed_line(lines, 40, "BASE-01,0", "BASE-01,1"))
    rejects("duplicate terminal ready", reader.physical_ledger, changed_line(lines, 53, "TEACH-AIR-01,1", "TEACH-AIR-01,0"))

    report = {"tables": json.loads((reader.CASE/"prospective-report-oracle.json").read_bytes())["tables"]}
    assert reader.report_semantic(report, oracle_gate=False)["cells"] == 4044
    # Formula and metadata assertions are exercised beneath the exact-oracle gate.
    rejects("report missing table", lambda x: reader.report_semantic(x,oracle_gate=False),
            {**report,"tables":report["tables"][:-1]})
    for label,t,r,c,value in (
        ("ready count",2,14,4,1), ("mission assigned",2,14,5,1),
        ("flight count",2,16,6,1), ("reserved count",2,14,11,1),
        ("formation count",2,16,15,2), ("success count",2,16,31,1),
        ("time",2,14,2,7.25), ("wrong numeric type",2,16,6,True),
        ("wrong null",2,16,34,0), ("available constant",2,0,13,1),
        ("stock PNB",3,0,9,0), ("stock null",3,0,3,0),
        ("stock time",3,0,0,0.25), ("stock Boolean",3,0,9,True),
        ("PDESC",0,0,0,"wrong"), ("summary",1,0,2,35),
    ):
        rejects(label, lambda x: reader.report_semantic(x,oracle_gate=False),
                changed_cell(report,t,r,c,value))
    metadata = copy.deepcopy(report)
    metadata["tables"][2]["columns"][4]["datatype"] = "string"
    rejects("report metadata type", lambda x:reader.report_semantic(x,oracle_gate=False), metadata)
    rows = copy.deepcopy(report)
    rows["tables"][2]["instances"][0]["rows"].append(copy.deepcopy(rows["tables"][2]["instances"][0]["rows"][-1]))
    rejects("report extra row",lambda x:reader.report_semantic(x,oracle_gate=False),rows)

    parent_model = json.loads((reader.PARENT/"native-input.json").read_bytes())["model"]
    child_model = json.loads((reader.CASE/"native-input.json").read_bytes())["model"]
    reader.changed_model(parent_model, child_model)
    bad = copy.deepcopy(child_model)
    next(t for t in bad["tables"] if t["name"]=="Unit")["instances"][0]["rows"][1][2] = "BASE-02"
    rejects("source STID",lambda x:reader.changed_model(parent_model,x),bad)
    bad = copy.deepcopy(child_model)
    next(t for t in bad["tables"] if t["name"]=="Unit")["instances"][0]["rows"][1][3] = 1
    rejects("source unrelated cell",lambda x:reader.changed_model(parent_model,x),bad)
    parent_export = json.loads((reader.PARENT_RUN/"roundtrip-raw.json").read_bytes())["model"]
    child_export = json.loads((reader.CASE/"child-roundtrip-oracle.json").read_bytes())["model"]
    reader.changed_model(parent_export, child_export)
    bad = copy.deepcopy(child_export)
    next(t for t in bad["tables"] if t["name"]=="Unit")["instances"][0]["rows"][1][2] = None
    rejects("export STID null",lambda x:reader.changed_model(parent_export,x),bad)

    original_native = (reader.PARENT_RUN/"report-raw.json").read_bytes()
    assert reader.native_report_json(original_native)["tables"]
    native_report_key = b'"report" : {'
    assert original_native.count(native_report_key) == 1
    rejects("native duplicate key",reader.native_report_json,
            original_native.replace(native_report_key,b'"report" : {}, "report" : {',1))
    rejects("native nonfinite",reader.native_report_json,
            original_native.replace(native_report_key,b'"probe" : NaN, "report" : {',1))
    rejects("native missing marker",reader.native_report_json,
            original_native.replace(b",\r\n      ]",b"\r\n      ]",1))
    rejects("native extra marker",reader.native_report_json,
            original_native.replace(b",\r\n      ]",b",\r\n      ],\r\n      ]",1))
    assert COUNT == 7 + 3 + 13 + 19 + 3 + 4, COUNT
    print(f"PASS_INDEPENDENT_PRIVATE_NEGATIVES {COUNT}")

if __name__ == "__main__":
    main()
