"""In-memory semantic probes after the sealed source/raw replay succeeds."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from native_json import parse
from numeric_bounds import compare
from physical_ledger import physical
from replay import (CONTRACT, CONTROL, HERE, RUN, arm, output_tables_doc,
                    replay, source_delta_docs)


def rejected(callback) -> None:
    try:
        result = callback()
    except (AssertionError, ValueError, KeyError):
        return
    assert result is False, "mutation unexpectedly passed semantic gate"


def check() -> dict:
    baseline = replay()
    assert baseline["passed"] and baseline["control_report_cells"] == baseline["child_report_cells"] == 1754
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    original = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    control_source = parse(HERE.parent / "C09-var02-lender-shortage-v1.0.2/ordinary-input.json")
    child_source = parse(HERE.parent / "C09-var02-lender-shortage-v1.0.7/shortage-input.json")
    probes = []

    def log_probe(label: str, old: str, new: str) -> None:
        assert original.count(old) == 1, (label, original.count(old))
        rejected(lambda: physical(original.replace(old, new), "shortage"))
        probes.append(label)

    log_probe("printed-annotation-substitution", "return resource transport task 0 starts with 1 resources, transportation time: 0.5",
              "return resource transport task 0 starts with 1 resources, transportation time: 0.125")
    log_probe("wrong-measured-arrival", "Time: 9.59488  return resource transport task 0 arrives with 1 resources",
              "Time: 9.96988  return resource transport task 0 arrives with 1 resources")
    log_probe("wrong-return-task-id", "return resource transport task 0 arrives with 1 resources",
              "return resource transport task 9 arrives with 1 resources")
    log_probe("wrong-return-receipt-quantity", "<P-MECH at <BASE-02,0>> return transport arrives: 1",
              "<P-MECH at <BASE-02,0>> return transport arrives: 2")
    log_probe("wrong-borrower-request", "<P-MECH at <BASE-01,0>> request for: 1 failed",
              "<P-MECH at <BASE-01,0>> request for: 2 failed")
    orphan = original + "\nTime: 10.2199  <P-MECH at <BASE-02,0>> allocated to maintenance task: 1\n" + (
        "Time: 10.2199  <P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1\n")
    rejected(lambda: physical(orphan, "shortage"))
    probes.append("orphan-balanced-booking-pair")

    wrong_source = copy.deepcopy(child_source)
    table = next(t for t in wrong_source["model"]["tables"] if t["name"] == "ResourceRemoteSupport")
    col = [x["name"] for x in table["columns"]]
    table["instances"][0]["rows"][0][col.index("TTRSS")] = 0.5
    rejected(lambda: source_delta_docs(control_source, wrong_source, contract))
    probes.append("source-return-parameter")
    wrong_source = copy.deepcopy(child_source)
    wrong_source["model"]["tables"][0]["name"] += "-DRIFT"
    rejected(lambda: source_delta_docs(control_source, wrong_source, contract))
    probes.append("source-table-metadata")

    child = arm(RUN, HERE.parent / "C09-var02-lender-shortage-v1.0.7/shortage-input.json", "shortage")
    want, observed, edges = child["expected"], child["observed"], child["edges"]
    log = child["log"]
    def cell_probe(label: str, table: str, row: int, field: str, replacement) -> None:
        mutated = copy.deepcopy(observed)
        mutated[table][row][field] = replacement
        errors, cells = compare(want, mutated, edges=edges, log=log)
        assert cells == 1754 and any(f"{table}[{row}].{field}" in error for error in errors), label
        probes.append(label)

    zero = next(i for i, row in enumerate(observed["SystemResults"]) if row["FTMO"] == 0)
    cell_probe("zero-FTMO-sub-epsilon", "SystemResults", zero, "FTMO", 1e-9)
    cell_probe("HOME-wait-special-plus", "SystemResults", 18, "NSYWR", 1.00001)
    cell_probe("HOME-NRW-special-minus", "ResourceResults", 18, "NRW", 0.99999)
    fractional = next(i for i, row in enumerate(want["SystemResults"]) if isinstance(row["FTMO"], float)
                      and 0 < row["FTMO"] < 1 and row["FTMO"] != 0.5)
    cell_probe("fractional-FTMO-outside-serialization", "SystemResults", fractional, "FTMO",
               want["SystemResults"][fractional]["FTMO"] + 1e-5)
    null_row = next(i for i, row in enumerate(observed["SystemResults"]) if row["SYDT"] is None)
    cell_probe("null-downtime", "SystemResults", null_row, "SYDT", 0)
    cell_probe("discrete-count-sub-epsilon", "SystemResults", zero, "NPMT",
               observed["SystemResults"][zero]["NPMT"] + 1e-9)
    cell_probe("resource-total-integral", "ResourceResultsTotal", 0, "NRRT",
               observed["ResourceResultsTotal"][0]["NRRT"] + 1e-3)
    wrong_report = copy.deepcopy(parse(RUN / "report-raw.json"))
    wrong_report["report"]["tables"][2]["columns"][0]["name"] = "WRONG-RID"
    rejected(lambda: output_tables_doc(wrong_report))
    probes.append("report-column-order")

    # Positive precision control: a noninteger source-exact count/fleet ratio
    # may differ only within the frozen decimal serialization allowance.
    allowed = copy.deepcopy(observed)
    allowed["SystemResults"][fractional]["FTMO"] = want["SystemResults"][fractional]["FTMO"] + 1e-8
    errors, cells = compare(want, allowed, edges=edges, log=log)
    assert cells == 1754 and not errors, errors[:3]
    return {"schema": "c09-var02-return-v010-author-selfcheck/v1", "passed": True,
            "baseline_control_cells": 1754, "baseline_child_cells": 1754,
            "semantic_rejections": len(probes), "rejected_probes": probes,
            "within_declared_serialization_accepted": True,
            "original_run_decision": "NO_GO_RUN", "native_runs": 0}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(check(), sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = args.output.resolve()
        assert target.parent == HERE and not target.exists()
        target.write_bytes(text.encode("utf-8"))
    else:
        print(text, end="")
