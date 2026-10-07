"""Read-only meaningful source, physical and complete-report mutation probes."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from build import PARENT, build, flattened, verify_isolation
from check_roundtrip import parse
from report_oracle import DESCRIPTION, COLUMNS, INSTANCE, check_report, expected
from validate_native_cli import PARENT_RUN, check_parent, event_gate, position, records, MISSION, SEQ

HERE = Path(__file__).resolve().parent
ANALOGUE = PARENT_RUN.parent / "c02-v102-single-zero-ssh-20260929-02"


def rejects(fn, label: str) -> None:
    try:
        fn()
    except (AssertionError, KeyError, TypeError, ValueError):
        return
    raise AssertionError(f"mutation passed: {label}")


def test() -> dict:
    assert check_parent()["cells"] == 5210
    parent = parse(PARENT)
    child = build(parent)
    a, b = flattened(parent), flattened(child)
    assert len(a) == len(b) == 236
    assert sum(a[k] != b[k] for k in a) == 2
    checks = 1
    changed = copy.deepcopy(child)
    changed["model"]["tables"][-1]["name"] = "MUTATED"
    rejects(lambda: verify_isolation(parent, changed), "table metadata")
    checks += 1
    changed = copy.deepcopy(child)
    allocation = next(t for t in changed["model"]["tables"] if t["name"] == "ResourceAllocation")
    allocation["instances"][0]["rows"][2][3] = 2
    rejects(lambda: verify_isolation(parent, changed), "third source cell")
    checks += 1
    log = (ANALOGUE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    assert "request for: 1 OK" in log and "request for: 1 failed" in log
    synthetic = log.replace("<P-CREW at <BASE-01,0>> request for: 1 OK",
                            "<P-CREW at <BASE-01,0>> request for: 1 failed")
    synthetic = synthetic.replace("<E-GSE at <BASE-01,0>> request for: 1 failed",
                                  "<E-GSE at <BASE-01,0>> request for: 1 OK")
    events = records(synthetic)
    assert event_gate(events, False) == 7.58333
    checks += 1
    report = parse(ANALOGUE / "report-raw.json")
    report["report"]["tables"][0]["instances"][0]["rows"][0][0] = DESCRIPTION
    assert check_report(report, False, 7.58333, "7.58333") == 5210
    checks += 1
    def corrupt_log(old: str, new: str, label: str) -> None:
        nonlocal checks
        assert old in synthetic
        rejects(lambda: event_gate(records(synthetic.replace(old, new, 1)), False), label)
        checks += 1
    corrupt_log("<P-CREW at <BASE-01,0>> request for: 1 failed",
                "<P-CREW at <BASE-01,0>> request for: 1 OK", "crew available")
    corrupt_log("<E-GSE at <BASE-01,0>> request for: 1 OK",
                "<E-GSE at <BASE-01,0>> request for: 1 failed", "device unavailable")
    corrupt_log("mission cancelled:", "mission starting:", "missing cancellation")
    corrupt_log("TEACH-AIR-01,0> preparation started", "TEACH-AIR-01,1> preparation started", "aircraft identity")
    corrupt_log("resource availability test", "books resources\nTime: 7  <E-GSE at <BASE-01,0>> allocated to maintenance task: 1",
                "partial resource booking")
    reordered = list(events)
    i = position(reordered, SEQ + " requests resources", 7)
    j = position(reordered, SEQ + " resource availability test", 7)
    reordered[i], reordered[j] = reordered[j], reordered[i]
    rejects(lambda: event_gate(reordered, False), "h7 request/test line swap")
    checks += 1
    reordered = list(events)
    i = position(reordered, MISSION + " mission cancelled:", 7.58333)
    j = position(reordered, "System arrives <TEACH-AIR-01,0>", 7.58333)
    reordered[i], reordered[j] = reordered[j], reordered[i]
    rejects(lambda: event_gate(reordered, False), "arrival precedes cancellation")
    checks += 1
    def corrupt_report(table: int, row: int, column: str, value: object, label: str) -> None:
        nonlocal checks
        altered = copy.deepcopy(report)
        t = altered["report"]["tables"][table]
        index = [c["name"] for c in t["columns"]].index(column)
        t["instances"][0]["rows"][row][index] = value
        rejects(lambda: check_report(altered, False, 7.58333, "7.58333"), label)
        checks += 1
    corrupt_report(2, 25, "NSYMO", 1e-9, "interior zero")
    corrupt_report(2, 15, "NSYMA", 0.16670, "fraction past bound")
    corrupt_report(3, 25, "ROS", 0, "null stock")
    corrupt_report(1, 0, "NREP", 2, "summary count")
    corrupt_report(4, 71, "NR", 0, "terminal resource")
    corrupt_report(5, 0, "NRW", 0, "waiting total")
    swapped = copy.deepcopy(report)
    swapped["report"]["tables"][2]["columns"][4:6] = list(reversed(swapped["report"]["tables"][2]["columns"][4:6]))
    rejects(lambda: check_report(swapped, False, 7.58333, "7.58333"), "column order")
    checks += 1
    # The observed cancellation token retains trailing zeros; a source-whole bin stays exact.
    boundary_rows = expected(False, 7.5)
    boundary = {"report": {"tables": [
        {"name": name, "columns": [{"name": col} for col in COLUMNS[name]],
         "instances": [{"instance_name": INSTANCE[name],
                         "rows": [[row[col] for col in COLUMNS[name]] for row in rows]}]}
        for name, rows in boundary_rows.items()]}}
    assert check_report(boundary, False, 7.5, "7.50000") == 5210
    checks += 1
    idx = COLUMNS["SystemResults"].index("NSYMA")
    boundary["report"]["tables"][2]["instances"][0]["rows"][15][idx] = 1e-9
    rejects(lambda: check_report(boundary, False, 7.5, "7.50000"), "whole-bin zero at printed boundary")
    checks += 1
    return {"schema": "c02-var01-v101-static-selfcheck/v1", "passed": True,
            "source_delta_cells": 2, "parent_report_cells": 5210,
            "synthetic_child_report_cells": 5210, "checks": checks,
            "synthetic_child_is_native_evidence": False}


if __name__ == "__main__":
    print(json.dumps(test(), separators=(",", ":")))
