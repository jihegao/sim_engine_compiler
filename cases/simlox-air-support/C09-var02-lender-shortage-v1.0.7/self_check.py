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


def linked_later_cycle(log: str) -> str:
    """Counterfactual topology/quantity fixture, not a seed/OPHOURS prediction."""
    extra = """Time: 10.30000  system DIRP task 4 on <TEACH-AIR-01,1> started
Time: 10.30000 <TEACH-AIR-01,1> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 10.30000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> started
Time: 10.30000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> requests resources
Time: 10.30000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> resource availability test
  Availability test on  <P-MECH at <BASE-01,0>> request for: 1 failed
Time: 10.30000  remote resource transport task 4 created: starting from  <P-MECH at <BASE-02,0>> aiming for  <P-MECH at <BASE-01,0>>
Time: 10.30000 <TEACH-AIR-01,1> nbr resourcewait increased:
Time: 10.30000  remote resource transport task 4 starts with 1 resources, transportation time: 0.25
Time: 10.55000  remote resource transport task 4 arrives with 1 resources
Time: 10.55000  <P-MECH at <BASE-01,0>> remote transport arrives: 1
Time: 10.55000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> resource availability test
  Availability test on  <P-MECH at <BASE-01,0>> request for: 1 OK
Time: 10.55000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> resource received
Time: 10.55000 <TEACH-AIR-01,1> nbr resourcewait decreased:
Time: 10.55000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> books resources
Time: 10.55000  <P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0
Time: 10.55000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours
Time: 11.05000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> completed
Time: 11.05000  direct repair subtask 4 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,1> frees resources
Time: 11.05000  <P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1
Time: 11.05000  return resource transport task 1 created: starting from  <P-MECH at <BASE-01,0>> aiming for  <P-MECH at <BASE-02,0>>
Time: 11.05000  system DIRP task 4 on <TEACH-AIR-01,1> completed
Time: 11.05000 <TEACH-AIR-01,1> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 11.05000  return resource transport task 1 starts with 1 resources, transportation time: 0.5
Time: 11.55000  return resource transport task 1 arrives with 1 resources
Time: 11.55000  <P-MECH at <BASE-02,0>> return transport arrives: 1
"""
    marker = "Time: 12  resource shift 0 ended"
    assert log.count(marker) == 1
    return log.replace(marker, extra + marker)


def two_repairs_one_loan(log: str) -> str:
    """Counterfactual sequential work on one loan; not fixed-seed native evidence."""
    marker = "Time: 11.05000  return resource transport task 1 starts with 1 resources"
    assert log.count(marker) == 1
    second = """Time: 11.05000  system DIRP task 5 on <TEACH-AIR-01,0> started
Time: 11.05000 <TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>
Time: 11.05000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> started
Time: 11.05000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> requests resources
Time: 11.05000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> resource availability test
  Availability test on  <P-MECH at <BASE-01,0>> request for: 1 OK
Time: 11.05000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> resource received
Time: 11.05000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> books resources
Time: 11.05000  <P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0
Time: 11.05000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> starts performing, planned to last for 0.25 hours
Time: 11.30000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> completed
Time: 11.30000  direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> frees resources
Time: 11.30000  <P-MECH at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1
Time: 11.30000  system DIRP task 5 on <TEACH-AIR-01,0> completed
Time: 11.30000 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>
"""
    log = log.replace(marker, second + marker)
    log = log.replace("Time: 11.05000  return resource transport task 1 starts with 1 resources",
                      "Time: 11.30000  return resource transport task 1 starts with 1 resources")
    log = log.replace("Time: 11.55000  return resource transport task 1", "Time: 11.80000  return resource transport task 1")
    log = log.replace("Time: 11.55000  <P-MECH at <BASE-02,0>> return transport arrives: 1",
                      "Time: 11.80000  <P-MECH at <BASE-02,0>> return transport arrives: 1")
    return log


def main() -> dict:
    counts = {"source_verifier": 0, "builder": 0, "control_report_cells": 0,
              "synthetic_child_report_cells": 0, "semantic_rejections": 0}
    planned = HERE / "runs" / "c09-var02-v107-shortage-ssh-20261007-01"
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
    assert selected_prefix(control, original_ledger) == selected_prefix(shortened, child_ledger)
    later = linked_later_cycle(shortened)
    later_ledger = physical(later, "shortage")
    assert later_ledger["outward_count"] == later_ledger["return_count"] == 2
    assert later_ledger["qualifying_return_hours"] == [0.125]
    later_expected, later_edges = derive(later, horizon=12, fleet=3,
                                        description="shortage TTRSS 0.125 child test", with_edges=True)
    later_edges["special_home_boundary_valid"] = later_ledger["special_home_boundary_valid"]
    later_errors, later_checked = compare(later_expected, deepcopy(later_expected), edges=later_edges, log=later)
    assert later_checked == 1754 and not later_errors
    counts["linked_later_cycle_full_cells"] = later_checked
    double_work = two_repairs_one_loan(later)
    double_ledger = physical(double_work, "shortage")
    assert double_ledger["outward_count"] == double_ledger["return_count"] == 2
    double_expected, double_edges = derive(double_work, horizon=12, fleet=3,
                                          description="two borrower repairs on one later loan", with_edges=True)
    double_edges["special_home_boundary_valid"] = double_ledger["special_home_boundary_valid"]
    assert double_edges["terminal_closed"] is True
    assert 0 < double_expected["ResourceResults"][-1]["NRRT"] < 1
    double_errors, double_checked = compare(double_expected, deepcopy(double_expected),
                                            edges=double_edges, log=double_work)
    assert double_checked == 1754 and not double_errors
    counts["two_repairs_one_loan_full_cells"] = double_checked
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
    rejects(lambda: physical(altered(shortened,
                                     "Time: 9.59488  <P-MECH at <BASE-02,0>> return transport arrives: 1",
                                     "Time: 9.59488  unrelated receipt interleaves\nTime: 9.59488  <P-MECH at <BASE-02,0>> return transport arrives: 1"),
                             "shortage"), "shifted typed return receipt", counts)
    rejects(lambda: physical(altered(shortened, "<HOME-AIR,2> nbr resourcewait increased", "<HOME-AIR,2> nbr resourcewait removed"), "shortage"), "missing HOME wait", counts)
    def compare_prefix(mutated: str) -> None:
        assert selected_prefix(mutated, child_ledger) == selected_prefix(shortened, child_ledger)
    rejects(lambda: compare_prefix(altered(shortened, "remote resource transport task 3 starts with 1 resources", "remote resource transport task 3 starts with 2 resources")), "pre-dispatch divergence", counts)
    rejects(lambda: physical(altered(later, "return resource transport task 1 starts with 1 resources", "return resource transport task 2 starts with 1 resources"), "shortage"), "later cross-cycle task ID", counts)
    rejects(lambda: physical(altered(later, "<P-MECH at <BASE-02,0>> return transport arrives: 1\nTime: 12", "<P-MECH at <BASE-01,0>> return transport arrives: 1\nTime: 12"), "shortage"), "later wrong-station receipt", counts)
    rejects(lambda: physical(altered(later, "system DIRP task 4 on <TEACH-AIR-01,1> completed", "system DIRP task 5 on <TEACH-AIR-01,1> completed"), "shortage"), "later unlinked repair", counts)
    rejects(lambda: physical(altered(double_work,
                                     "direct repair subtask 5 seqno 1 within system DIRP task 5 on <TEACH-AIR-01,0> books resources",
                                     "direct repair subtask 5 seqno 1 within system DIRP task 4 on <TEACH-AIR-01,0> books resources"),
                             "shortage"), "second repair wrong booking task", counts)
    marker = "Time: 12  resource shift 0 ended"
    orphan = shortened.replace(marker,
        "Time: 9.84488  <P-MECH at <BASE-02,0>> allocated to maintenance task: 1  available now: 0\n"
        "Time: 9.84488  <P-MECH at <BASE-02,0>> deallocated from  maintenance task: 1  available now: 1\n" + marker)
    assert orphan != shortened
    rejects(lambda: physical(orphan, "shortage"), "balanced orphan mechanic booking", counts)
    # Child source bytes and accepted control seals are checked by verify() and
    # build(), not by replaying a synthetic source mutation as native evidence.
    return {"schema": "c09-var02-v107-static-self-check/v1", "passed": True,
            "counts": counts, "native_child_executed": False}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, sort_keys=True, indent=2))
