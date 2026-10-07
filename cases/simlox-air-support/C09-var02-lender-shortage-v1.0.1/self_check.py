"""Read-only source, control-oracle and adversarial prelaunch checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

from build import build, table_diff
from report_oracle import compare, derive
from validate_native_cli import diagnostics, output_tables, output_tables_doc, physical
from verify_sources import verify as verify_sources

HERE = Path(__file__).resolve().parent


def main() -> dict:
    source = verify_sources()
    assert source["passed"]
    c = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    pair = {arm: build(c, arm) for arm in ("ordinary", "shortage")}
    assert {t["table"] for t in table_diff(pair["ordinary"], pair["shortage"])["changed_tables"]} == {
        "ProblemDescription", "ResourceRemoteSupport"}
    for arm, value in pair.items():
        assert value == json.loads((HERE / f"{arm}-input.json").read_text(encoding="utf-8"))
    parent = (HERE / c["accepted_direct_parent"]["accepted_runs"]["remote"]["path"]).resolve()
    log = (parent / "model.log").read_text(encoding="utf-8-sig")
    actual = output_tables(parent / "report-raw.json", 36)
    expected = derive(log, horizon=36, fleet=2,
                      description="C09.var04 primary system maintenance remote resource remote")
    assert sum(len(r) for rows in expected.values() for r in rows) == 5210
    assert compare(expected, actual, horizon=36, log=log) == []
    probes = 0
    def reject(table: str, row: int, key: str, value: object) -> None:
        nonlocal probes
        altered = copy.deepcopy(actual)
        altered[table][row][key] = value
        assert compare(expected, altered, horizon=36, log=log), (table, row, key)
        probes += 1
    reject("StockTotalResults", 0, "PNB", 0)
    reject("StockTotalResults", 0, "ROS", 0)
    reject("ResourceResults", 0, "NRN", 4)
    reject("ResourceResults", 2, "NRUM", 1e-9)
    reject("SystemResults", 1, "NSYWR", 1e-9)
    reject("SystemResults", 1, "NSYPM", 1e-9)
    reject("SystemResults", 0, "SID", "wrong")
    reject("ResultSummary", 0, "RTIUP", 12)
    exact_ratio = copy.deepcopy(expected)
    exact_ratio["SystemResults"][2]["NSYMO"] = 2
    exact_ratio["SystemResults"][2]["FTMO"] = 2 / 3
    serialized_ratio = copy.deepcopy(exact_ratio)
    serialized_ratio["SystemResults"][2]["FTMO"] = 0.6666667
    assert compare(exact_ratio, serialized_ratio, horizon=36, log=log) == []
    serialized_ratio["SystemResults"][2]["FTMO"] = 0.6666767
    assert compare(exact_ratio, serialized_ratio, horizon=36, log=log)
    probes += 1
    from check_roundtrip import parse
    metadata_mutation = parse(parent / "report-raw.json")
    next(t for t in metadata_mutation["report"]["tables"] if t["name"] == "SystemResults")["instances"][0]["instance_name"] = ""
    try:
        output_tables_doc(metadata_mutation, 36)
    except AssertionError:
        probes += 1
    else:
        raise AssertionError("instance-name mutation accepted")
    raw_diag = (parent / "run.log").read_text(encoding="utf-8-sig")
    # The original has a different, accepted parent diagnostic cardinality.
    child_diag = ("Form: Control\nrec 1: (warning #108) x\n"
                  "Form: ResourceRemoteSupport\nrec 1: (notice #292) x\n"
                  "Form: System\nrec 1: (warning #126) x\nrec 2: (warning #126) x\n"
                  "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1")
    assert "Input conversion completed. Errors: 0" in raw_diag
    diagnostics(child_diag)
    for mutation in (child_diag.replace("rec 2: (warning #126)", "rec 3: (warning #126)"),
                     child_diag.replace("Warnings: 3", "Warnings: 2")):
        try:
            diagnostics(mutation)
        except AssertionError:
            probes += 1
        else:
            raise AssertionError("diagnostic mutation accepted")
    missing = log.replace("return resource transport task 0 arrives with 1 resources", "return edge removed")
    try:
        derive(missing, horizon=36, fleet=2,
               description="C09.var04 primary system maintenance remote resource remote")
    except AssertionError:
        probes += 1
    else:
        raise AssertionError("missing physical return edge accepted")
    # The accepted control has two overlapping crew bookings and one travelling
    # mechanic. Capacity and location changes must fail even if the resulting
    # report could otherwise be made to look plausible.
    pool_mutations = (
        log.replace("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
                    "<P-CREW at <BASE-01,0>> allocated to maintenance task: 2  available now: 0", 1),
        log.replace("<P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
                    "<P-MECH at <BASE-01,0>> allocated to maintenance task: 2  available now: 0", 1),
        log.replace("<P-MECH at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
                    "<P-MECH at <BASE-02,0>> allocated to maintenance task: 1  available now: 0", 1),
    )
    assert all(mutated != log for mutated in pool_mutations)
    for mutated in pool_mutations:
        try:
            derive(mutated, horizon=36, fleet=2,
                   description="C09.var04 primary system maintenance remote resource remote")
        except AssertionError:
            probes += 1
        else:
            raise AssertionError("resource capacity/location mutation accepted")
    synthetic = "\n".join([
        "Time: 8.5 remote resource transport task 3 created: starting from <P-MECH at <BASE-02,0>> aiming for <P-MECH at <BASE-01,0>>",
        "Time: 8.5 remote resource transport task 3 starts with 1 resources, transportation time: 0.25",
        "Time: 8.75 remote resource transport task 3 arrives with 1 resources",
        "Time: 8.75 <P-MECH at <BASE-01,0>> remote transport arrives: 1",
        "Time: 9 system PM task 0 on <HOME-AIR,0> started",
        "Time: 9 system PM task 0 on <HOME-AIR,0> PMID: HOME-PM9",
        "Time: 9 subtask 0 seqno 1 within system PM task 0 on <HOME-AIR,0> resource availability test",
        "  Availability test on <P-MECH at <BASE-02,0>> request for: 1 failed",
        "Time: 9 <HOME-AIR,0> nbr resourcewait increased:",
        "Time: 9.1 return resource transport task 0 created: starting from <P-MECH at <BASE-01,0>> aiming for <P-MECH at <BASE-02,0>>",
        "Time: 9.1 return resource transport task 0 starts with 1 resources, transportation time: 0.125",
        "Time: 9.225 return resource transport task 0 arrives with 1 resources",
        "Time: 9.225 <P-MECH at <BASE-02,0>> return transport arrives: 1",
        "Time: 9.225 <HOME-AIR,0> nbr resourcewait decreased:",
        "Time: 9.225 subtask 0 seqno 1 within system PM task 0 on <HOME-AIR,0> starts performing, planned to last for 0.25 hours",
        "Time: 9.475 subtask 0 seqno 1 within system PM task 0 on <HOME-AIR,0> completed",
        "Time: 9.475 system PM task 0 on <HOME-AIR,0> completed",
    ])
    assert physical(synthetic, "shortage")["qualifying_return_task_ids"] == [0]
    for tampered in (synthetic.replace("return resource transport task 0 arrives", "return resource transport task 9 arrives"),
                     synthetic.replace("within system PM task 0 on <HOME-AIR,0> resource availability test",
                                       "within system PM task 7 on <HOME-AIR,0> resource availability test"),
                     synthetic.replace("Time: 8.75 <P-MECH at <BASE-01,0>> remote transport arrives: 1",
                                       "Time: 8.76 <P-MECH at <BASE-01,0>> remote transport arrives: 1"),
                     synthetic.replace("Time: 9.225 <P-MECH at <BASE-02,0>> return transport arrives: 1",
                                       "Time: 9.225 <P-MECH at <BASE-01,0>> return transport arrives: 1")):
        try:
            physical(tampered, "shortage")
        except AssertionError:
            probes += 1
        else:
            raise AssertionError("transport or PM task-ID mutation accepted")
    # A shortage in the first loan cannot be attributed to a second, unrelated
    # return merely because that later return has the target duration.
    cross_cycle = (synthetic.replace("Time: 9.1 return resource transport task 0 starts with 1 resources, transportation time: 0.125",
                                     "Time: 9.1 return resource transport task 0 starts with 1 resources, transportation time: 0.5")
                           .replace("Time: 9.225 return resource transport task 0 arrives", "Time: 9.6 return resource transport task 0 arrives")
                           .replace("Time: 9.225 <P-MECH at <BASE-02,0>> return transport arrives", "Time: 9.6 <P-MECH at <BASE-02,0>> return transport arrives"))
    cross_cycle = cross_cycle.replace("Time: 9.225 <HOME-AIR,0> nbr resourcewait decreased:",
        "\n".join([
            "Time: 9.7 remote resource transport task 4 created: starting from <P-MECH at <BASE-02,0>> aiming for <P-MECH at <BASE-01,0>>",
            "Time: 9.7 remote resource transport task 4 starts with 1 resources, transportation time: 0.25",
            "Time: 9.95 remote resource transport task 4 arrives with 1 resources",
            "Time: 9.95 <P-MECH at <BASE-01,0>> remote transport arrives: 1",
            "Time: 10 return resource transport task 1 created: starting from <P-MECH at <BASE-01,0>> aiming for <P-MECH at <BASE-02,0>>",
            "Time: 10 return resource transport task 1 starts with 1 resources, transportation time: 0.125",
            "Time: 10.125 return resource transport task 1 arrives with 1 resources",
            "Time: 10.125 <P-MECH at <BASE-02,0>> return transport arrives: 1",
            "Time: 10.125 <HOME-AIR,0> nbr resourcewait decreased:"]))
    cross_cycle = cross_cycle.replace("Time: 9.225 subtask 0", "Time: 10.125 subtask 0")
    cross_cycle = cross_cycle.replace("Time: 9.475 subtask 0", "Time: 10.375 subtask 0")
    cross_cycle = cross_cycle.replace("Time: 9.475 system PM task", "Time: 10.375 system PM task")
    try:
        physical(cross_cycle, "shortage")
    except AssertionError:
        probes += 1
    else:
        raise AssertionError("cross-cycle shortage attribution accepted")
    # The same two trips become a valid synthetic positive only when the HOME
    # request/wait occurs during the second loan. Then swap the two return
    # arrival task IDs while preserving their printed times: task-key pairing
    # must reject it even though the positional list order is unchanged.
    second_cycle = cross_cycle.replace("Time: 9 subtask 0 seqno", "Time: 9.96 subtask 0 seqno")
    second_cycle = second_cycle.replace("Time: 9 <HOME-AIR,0> nbr resourcewait increased:",
                                        "Time: 9.96 <HOME-AIR,0> nbr resourcewait increased:")
    import re
    blocks = re.findall(r"(?ms)^Time: .*?(?=^Time: |\Z)", second_cycle)
    second_cycle = "\n".join(block.rstrip("\n") for _, block in sorted(
        enumerate(blocks), key=lambda pair: (float(re.match(r"Time: ([0-9.]+)", pair[1]).group(1)), pair[0])))
    assert physical(second_cycle, "shortage")["qualifying_return_task_ids"] == [1]
    swapped_ids = second_cycle.replace("Time: 9.6 return resource transport task 0 arrives",
                                       "Time: 9.6 return resource transport task X arrives")
    swapped_ids = swapped_ids.replace("Time: 10.125 return resource transport task 1 arrives",
                                      "Time: 10.125 return resource transport task 0 arrives")
    swapped_ids = swapped_ids.replace("Time: 9.6 return resource transport task X arrives",
                                      "Time: 9.6 return resource transport task 1 arrives")
    try:
        physical(swapped_ids, "shortage")
    except AssertionError:
        probes += 1
    else:
        raise AssertionError("cross-cycle return task-ID swap accepted")
    return {"schema":"c09-var02-v101-static-self-check/v1","passed":True,
            "parent_report_cells":5210,"adversarial_rejections":probes,
            "accepted_source_seals":source["counts"]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as exc:
        result = {"schema":"c09-var02-v101-static-self-check/v1","passed":False,
                  "error":f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    sys.exit(0 if result["passed"] else 1)
