"""Pure, read-only semantic probes. The shortened return is synthetic, not native evidence."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from build import build
from numeric_bounds import compare
from physical_ledger import physical
from report_oracle import derive
from validate_native_cli import selected_prefix
from verify_sources import verify

HERE = Path(__file__).resolve().parent
CONTROL = HERE.parent / "C09-var02-lender-shortage-v1.0.2" / "runs" / "c09-var02-v102-ordinary-ssh-20261007-01" / "model.log"


def rejects(action, label: str, counts: dict) -> None:
    try:
        action()
    except (AssertionError, KeyError, ValueError, TypeError):
        counts["semantic_rejections"] += 1
    else:
        raise AssertionError(f"semantic mutation escaped: {label}")


def altered(log: str, old: str, new: str) -> str:
    assert old in log, old
    return log.replace(old, new, 1)


def main() -> dict:
    counts = {"source_verifier": 0, "builder": 0, "control_report_cells": 0,
              "synthetic_child_report_cells": 0, "semantic_rejections": 0}
    planned = HERE / "runs" / "c09-var02-v105-shortage-ssh-20261007-01"
    verify(mode="sealed_replay" if (planned / "closure.json").exists() else "preflight")
    counts["source_verifier"] = 1
    built_input, built_diff = build()
    assert (HERE / "shortage-input.json").read_bytes() == built_input
    assert (HERE / "exact-diff.json").read_bytes() == built_diff
    counts["builder"] = 1
    control = CONTROL.read_text(encoding="utf-8-sig")
    shortened = (control.replace("transportation time: 0.5", "transportation time: 0.125")
                 .replace("Time: 9.96988", "Time: 9.59488")
                 .replace("Time: 10.2199", "Time: 9.84488"))
    assert shortened != control
    original_ledger = physical(control, "ordinary")
    child_ledger = physical(shortened, "shortage")
    assert original_ledger["qualifying_return_hours"] == [0.5]
    assert child_ledger["qualifying_return_hours"] == [0.125]
    assert selected_prefix(control, original_ledger["return_start"]) == selected_prefix(shortened, child_ledger["return_start"])
    for text, arm, label in ((control, "ordinary", "control_report_cells"),
                             (shortened, "shortage", "synthetic_child_report_cells")):
        expected, edges = derive(text, horizon=12, fleet=3,
                                 description=("ordinary TTRSS equals TTRS" if arm == "ordinary" else
                                              "shortage TTRSS 0.125 child test"), with_edges=True)
        edges["special_home_boundary_valid"] = physical(text, arm)["special_home_boundary_valid"]
        errors, checked = compare(expected, deepcopy(expected), edges=edges, log=text)
        assert checked == 1754 and not errors
        counts[label] = checked
        def bad_cell(table: str, row: int, field: str, value: object) -> None:
            changed = deepcopy(expected)
            changed[table][row][field] = value
            errors, _ = compare(expected, changed, edges=edges, log=text)
            assert not errors, (table, row, field, value)
        # Exact source/count/null/identity classes and six numerical classes.
        rejects(lambda: bad_cell("SystemResults", 16, "NSYMO", 2.00001), "source whole", counts)
        rejects(lambda: bad_cell("SystemResults", 0, "FTMO", 1e-9), "FTMO zero", counts)
        rejects(lambda: bad_cell("SystemResults", 18, "NSYWR", 1.00001), "HOME special", counts)
        rejects(lambda: bad_cell("ResourceResults", 18, "NRW", 0.99999), "resource HOME special", counts)
        rejects(lambda: bad_cell("SystemResults", 0, "SYDT", 1), "null downtime", counts)
        rejects(lambda: bad_cell("ResultSummary", 0, "MTMF", True), "boolean", counts)
        rejects(lambda: bad_cell("SystemResults", 0, "NSYA", float("nan")), "nonfinite", counts)
        rejects(lambda: bad_cell("ProblemDescription", 0, "PDESC", "wrong source"), "description", counts)
        rejects(lambda: bad_cell("ResourceResultsTotal", 0, "NRUM", 1), "resource mean", counts)
    # The positive fixture reaches the same physical and full-cell paths as a
    # native child, but never substitutes for the separately guarded run.
    rejects(lambda: physical(altered(shortened, "transportation time: 0.125", "transportation time: 0.5"), "shortage"), "ordinary return", counts)
    rejects(lambda: physical(altered(shortened, "return resource transport task 0 starts with 1 resources", "return resource transport task 1 starts with 1 resources"), "shortage"), "return task ID", counts)
    rejects(lambda: physical(altered(shortened, "aiming for  <P-MECH at <BASE-02,0>>", "aiming for  <P-MECH at <BASE-01,0>>"), "shortage"), "wrong return station", counts)
    rejects(lambda: physical(altered(shortened, "starts with 1 resources, transportation time: 0.125", "starts with 2 resources, transportation time: 0.125"), "shortage"), "return quantity", counts)
    rejects(lambda: physical(altered(shortened, "<HOME-AIR,2> nbr resourcewait increased", "<HOME-AIR,2> nbr resourcewait removed"), "shortage"), "missing HOME wait", counts)
    def compare_prefix(mutated: str) -> None:
        assert selected_prefix(mutated, child_ledger["return_start"]) == selected_prefix(shortened, child_ledger["return_start"])
    rejects(lambda: compare_prefix(altered(shortened, "remote resource transport task 3 starts with 1 resources", "remote resource transport task 3 starts with 2 resources")), "pre-dispatch divergence", counts)
    # Child source bytes and accepted control seals are checked by verify() and
    # build(), not by replaying a synthetic source mutation as native evidence.
    return {"schema": "c09-var02-v105-static-self-check/v1", "passed": True,
            "counts": counts, "native_child_executed": False}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, sort_keys=True, indent=2))
