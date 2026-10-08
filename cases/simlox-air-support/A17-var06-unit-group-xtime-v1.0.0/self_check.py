"""Private under-hash mutation checks; no SIMLOX or accepted checker invocation."""

from __future__ import annotations

import copy
import json

from event_ledger import semantic
from model_common import EXPORT_SHA, HERE, INPUT_SHA, compare_tables, read_pinned_json, strict_json
from report_oracle import expected_report


def rejected(action) -> None:
    try:
        action()
    except (AssertionError, ValueError, KeyError, TypeError, UnicodeDecodeError):
        return
    raise AssertionError("private mutation unexpectedly passed")


def replace_line(lines: list[str], index: int, old: str, new: str) -> list[str]:
    clone = list(lines)
    assert old in clone[index]
    clone[index] = clone[index].replace(old, new, 1)
    assert clone != lines
    return clone


def encode_lines(lines: list[str]) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def main() -> None:
    negatives = 0
    raw = (HERE / "prospective-log-oracle.bytes").read_bytes()
    assert semantic(raw)["physical_lines"] == 60
    lines = raw.decode("utf-8").splitlines()
    for index, old, new in [
        (13, "<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"),
        (16, "<TEACH-AIR-01,1>", "<TEACH-AIR-01,0>"),
        (16, "TEACH-UNIT-2", "TEACH-UNIT"),
        (28, "Time: 8", "Time: 8.5"),
        (29, "Time: 8.5", "Time: 9.5"),
        (30, "Time: 9.5", "Time: 10"),
        (39, "turnround ended", "turnround started"),
        (40, "BASE-01", "BASE-02"),
        (53, "TEACH-UNIT-2", "TEACH-UNIT"),
    ]:
        clone = replace_line(lines, index, old, new)
        rejected(lambda clone=clone: semantic(encode_lines(clone)))
        negatives += 1
    for a, b in [(13, 16), (40, 43), (50, 53)]:
        clone = list(lines)
        clone[a], clone[b] = clone[b], clone[a]
        assert clone != lines
        rejected(lambda clone=clone: semantic(encode_lines(clone)))
        negatives += 1
    for index in (41, 42, 48, 51, 52, 58):
        clone = list(lines)
        del clone[index]
        rejected(lambda clone=clone: semantic(encode_lines(clone)))
        negatives += 1

    inp = read_pinned_json(HERE / "native-input.json", INPUT_SHA)
    exp = read_pinned_json(HERE / "child-roundtrip-oracle.json", EXPORT_SHA)
    assert compare_tables(inp["model"]["tables"], copy.deepcopy(inp["model"]["tables"])) == 203
    assert compare_tables(exp["model"]["tables"], copy.deepcopy(exp["model"]["tables"])) == 387
    for source, table_name, row_idx, column_name, wrong in [
        (inp, "UnitGroupMember", 1, "XTIME", 0.0),
        (inp, "UnitGroupMember", 1, "XTIME", True),
        (inp, "UnitGroupMember", 0, "XTIME", 1.0),
        (inp, "UnitGroupMember", 1, "USTID", "TEACH-UNIT"),
        (exp, "UnitGroupMember", 1, "XTIME", 0),
        (exp, "UnitGroupMember", 1, "XTIME", True),
        (exp, "MissionType", 0, "DURN", False),
    ]:
        clone = copy.deepcopy(source)
        t = next(t for t in clone["model"]["tables"] if t["name"] == table_name)
        col = [c["name"] for c in t["columns"]].index(column_name)
        t["instances"][0]["rows"][row_idx][col] = wrong
        rejected(lambda source=source, clone=clone: compare_tables(source["model"]["tables"], clone["model"]["tables"]))
        negatives += 1
    for source in (inp, exp):
        clone = copy.deepcopy(source)
        clone["model"]["tables"].pop()
        rejected(lambda source=source, clone=clone: compare_tables(source["model"]["tables"], clone["model"]["tables"]))
        negatives += 1
        for mutation in ("row_list_to_dict", "rows_list_to_dict"):
            clone = copy.deepcopy(source)
            instance = clone["model"]["tables"][0]["instances"][0]
            if mutation == "row_list_to_dict":
                row = instance["rows"][0]
                instance["rows"][0] = {row[0]: "inert"}
            else:
                instance["rows"] = {"0": instance["rows"][0]}
            rejected(lambda source=source, clone=clone: compare_tables(source["model"]["tables"], clone["model"]["tables"]))
            negatives += 1
        for mutation in ("key_bool_to_int", "key_removed", "key_extra_field"):
            clone = copy.deepcopy(source)
            table = next(t for t in clone["model"]["tables"] if t["name"] == "System")
            column = next(c for c in table["columns"] if c["name"] == "SID")
            assert column["key"] is True
            if mutation == "key_bool_to_int":
                column["key"] = 1
            elif mutation == "key_removed":
                del column["key"]
            else:
                column["extra"] = "inert"
            rejected(lambda source=source, clone=clone: compare_tables(source["model"]["tables"], clone["model"]["tables"]))
            negatives += 1
    rejected(lambda: strict_json(b'{"model":1,"model":2}'))
    rejected(lambda: strict_json(b'{"model":NaN}'))
    negatives += 2

    report = expected_report()
    tables = report["report"]["tables"]
    assert compare_tables(tables, copy.deepcopy(tables)) == 4966
    for kind in ("stotd_zero", "stotd_bool", "stacc_shift", "mtacc_null", "missing_fixed_row",
                 "extra_column", "wrong_unit", "system_ready_bool", "stock_null",
                 "row_list_to_dict", "rows_list_to_dict", "key_bool_to_int",
                 "key_removed", "key_extra_field"):
        clone = copy.deepcopy(tables)
        fixed = clone[4]
        if kind == "stotd_zero":
            fixed["instances"][0]["rows"][0][22] = 0
        elif kind == "stotd_bool":
            fixed["instances"][0]["rows"][0][22] = True
        elif kind == "stacc_shift":
            fixed["instances"][0]["rows"][0][20] = 0
        elif kind == "mtacc_null":
            fixed["instances"][0]["rows"][0][7] = None
        elif kind == "missing_fixed_row":
            fixed["instances"][0]["rows"].pop()
        elif kind == "extra_column":
            fixed["columns"].append({"datatype": "double", "name": "EXTRA"})
        elif kind == "wrong_unit":
            fixed["instances"][0]["rows"][0][0] = "TEACH-UNIT-2"
        elif kind == "system_ready_bool":
            clone[6]["instances"][0]["rows"][0][4] = True
        elif kind == "row_list_to_dict":
            row = clone[0]["instances"][0]["rows"][0]
            clone[0]["instances"][0]["rows"][0] = {row[0]: "inert"}
        elif kind == "rows_list_to_dict":
            instance = clone[0]["instances"][0]
            instance["rows"] = {"0": instance["rows"][0]}
        elif kind in ("key_bool_to_int", "key_removed", "key_extra_field"):
            column = next(c for c in clone[2]["columns"] if c["name"] == "UNID")
            assert column["key"] is True
            if kind == "key_bool_to_int":
                column["key"] = 1
            elif kind == "key_removed":
                del column["key"]
            else:
                column["extra"] = "inert"
        else:
            clone[7]["instances"][0]["rows"][0][9] = None
        assert json.dumps(clone, sort_keys=True) != json.dumps(tables, sort_keys=True)
        rejected(lambda clone=clone: compare_tables(tables, clone))
        negatives += 1
    print(json.dumps({"schema": "a17-var06-author-private-self-check/v100", "passed": True,
                      "negative_clones_rejected": negatives, "source_cells": 203, "export_cells": 387,
                      "report_cells": 4966, "physical_lines": 60,
                      "native_calls": 0, "accepted_checker_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
