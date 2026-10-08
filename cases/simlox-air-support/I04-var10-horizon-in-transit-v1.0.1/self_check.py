"""Pure source, transcript, report and schema mutations; no SIMLOX call."""
from __future__ import annotations

import copy
import json

from build import generated, mutate, run, topology
from check_roundtrip import compare as compare_export
from event_ledger import oracle_lines, physical_ledger, validate as validate_log
from model_common import parse, read
from make_source_inventory import allowed_future, ignored_generated
from report_oracle import compare as compare_report, validate_oracle
from source_gate import HERE


def rejected(label, action):
    try:
        action()
    except (AssertionError, ValueError, TypeError, KeyError, IndexError):
        return label
    raise AssertionError(f"negative accepted: {label}")


def altered(value, path, replacement):
    clone = copy.deepcopy(value)
    cursor = clone
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = replacement
    return clone


def run_checks():
    assert run(False)["native_calls"] == 0
    generated_bodies = generated()
    assert topology(read(HERE / "native-input.json")) == {"tables": 34, "rows": 21, "cells": 211}
    exported = read(HERE / "child-roundtrip-oracle.json")
    assert topology(exported) == {"tables": 34, "rows": 39, "cells": 395}
    compare_export(exported, exported)
    assert generated_bodies["input"] == (HERE / "native-input.json").read_bytes()
    lines = oracle_lines()
    assert physical_ledger(lines)["transit_terminal"] == 1
    transcript = ("\r\n".join(lines) + "\r\n").encode()
    assert validate_log(transcript)["timed_lines"] == 53
    report = read(HERE / "child-report-oracle.json")
    assert validate_oracle(report) == compare_report(report, report) == 1244
    negatives = []

    def neg(label, fn):
        negatives.append(rejected(label, fn))

    neg("log line omitted", lambda: validate_log(("\r\n".join(lines[:-1]) + "\r\n").encode()))
    neg("log line inserted", lambda: validate_log(transcript + b"Time: 11 unsolicited\r\n"))
    neg("log wrong horizon", lambda: validate_log(transcript.replace(b"\r\n11\r\n", b"\r\n36\r\n", 1)))
    neg("log LF-only", lambda: validate_log(transcript.replace(b"\r\n", b"\n")))
    neg("log duplicated transfer-out", lambda: physical_ledger(lines + [lines[-1]]))
    neg("log transfer-out before ready decrement", lambda: physical_ledger(lines[:-2] + [lines[-1], lines[-2]]))
    ready_index = next(i for i, line in enumerate(lines) if "nbr ready decreased" in line and "Time: 10.5 " in line)
    neg("wrong aircraft at transfer", lambda: physical_ledger(
        altered(lines, [ready_index], lines[ready_index].replace("TEACH-AIR-01,0", "TEACH-AIR-01,1"))))
    neg("wrong source owner at transfer", lambda: physical_ledger(
        altered(lines, [ready_index], lines[ready_index].replace("TEACH-UNIT at <BASE-01", "TEACH-UNIT-2 at <BASE-02"))))
    completion_index = next(i for i, line in enumerate(lines) if "mission completed:" in line)
    neg("missing completion", lambda: physical_ledger(altered(lines, [completion_index], "Time: 10 completion omitted")))
    neg("duplicate completion", lambda: physical_ledger(lines[:completion_index + 1] + [lines[completion_index]] + lines[completion_index + 1:]))
    for table_index, row_index, column_index, replacement in (
        (0, 0, 0, "different PDESC"), (1, 0, 2, 10.0),
        (2, 20, 2, 10.25), (2, 21, 2, 10.75),
        (2, 20, 8, True), (3, 20, 2, 10.25),
    ):
        path = ["report", "tables", table_index, "instances", 0, "rows", row_index, column_index]
        neg(f"report cell {table_index}/{row_index}/{column_index}",
            lambda p=path, v=replacement: compare_report(altered(report, p, v), report))
    neg("report unexpected table", lambda: compare_report(
        altered(report, ["report", "tables", 2, "name"], "OtherResults"), report))
    neg("report wrong terminal instance", lambda: compare_report(
        altered(report, ["report", "tables", 2, "instances", 0, "instance_name"],
                "Total over all Units;Total over all Systems;0.00;36.00"), report))
    neg("report added metadata", lambda: compare_report(
        {**report, "extra": True}, report))
    neg("report boolean summary", lambda: compare_report(
        altered(report, ["report", "tables", 1, "instances", 0, "rows", 0, 0], True), report))
    neg("report oracle bad integral", lambda: validate_oracle(
        altered(report, ["report", "tables", 2, "instances", 0, "rows", 20, 7], 99)))
    neg("export wrong table name", lambda: compare_export(
        altered(exported, ["model", "tables", 17, "name"], "OtherTransfer"), exported))
    neg("export boolean double", lambda: compare_export(
        altered(exported, ["model", "tables", 17, "instances", 0, "rows", 0, 5], True), exported))
    neg("export missing table", lambda: compare_export(
        altered(exported, ["model", "tables"], exported["model"]["tables"][:-1]), exported))
    neg("source original field changed", lambda: mutate(
        altered(read(HERE.parent / "I04-var03-idle-system-between-v1.0.1/native-input.json"),
                ["model", "tables", 0, "instances", 0, "rows", 0, 0], "wrong")))
    neg("duplicate JSON key", lambda: parse(b'{"a":1,"a":2}'))
    neg("nonfinite JSON", lambda: parse(b'{"x":NaN}'))
    for permitted in ("README-publication.md", "preserved-postrun/postrun-000.bytes",
                      "review/independent-content-go.md", "runs/child/model.log",
                      "review/__pycache__/reader.pyc"):
        assert allowed_future(permitted) or ignored_generated(permitted), permitted
    for unlisted in ("unreviewed.py", "preserved-context/runs/hidden.py",
                     "review/test-output/hidden.py", "review/independent-content-x/hidden.py",
                     "preserved-context/__pycache__/hidden.pyc"):
        assert not allowed_future(unlisted) and not ignored_generated(unlisted), unlisted
    assert len(negatives) == len(set(negatives)) >= 25
    return {"schema": "i04-var10-pure-self-check/v101", "native_calls": 0,
            "source_cells": 211, "export_cells": 395, "log_lines": 61,
            "timed_records": 53, "report_cells": 1244,
            "negative_rejections": len(negatives), "negative_labels": negatives}


if __name__ == "__main__":
    print(json.dumps(run_checks(), sort_keys=True))
