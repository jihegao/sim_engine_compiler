"""Read-only replay of the one failed v1.0.2 crew arm; no author imports."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import independent_replay as own

CASE = Path(__file__).resolve().parents[1]
RUN = CASE / "runs/c05-var03-v102-crew-ssh-20261007-01"
RADIO = CASE / "runs/c05-var03-v102-radio-ssh-20261007-01"


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def physical_stock_edges(events: list[tuple[float, str]]) -> dict:
    trace = own.stock_trace(events)
    result = {}
    launch = [(hour, body) for hour, body in events if " mission starting," in body]
    assert len(launch) == 1
    for suffix in ("A", "B"):
        kind = f"TEACH-LRU-{suffix}"
        demand_pattern = re.compile(rf"<{kind},0,BASE-01,0> Reconfiguration item demand arrives from pos <TEACH-AIR-01,BASE-01,(\d+)>")
        take_pattern = re.compile(rf"<{kind},0,BASE-01,0> Take replacement item <{kind},0,(\d+)> from stock")
        demand = [(hour, match.group(1)) for hour, body in events if (match := demand_pattern.search(body))]
        take = [(hour, match.group(1)) for hour, body in events if (match := take_pattern.search(body))]
        assert len(demand) == len(take) == 1
        assert demand[0][0] == take[0][0] == 7
        assert take[0][1] == trace[kind]["opening_ids"][0]
        # The demand's final suffix is a position index, not an aircraft ID.
        assert demand[0][1] == "0"
        prep = [(hour, body) for hour, body in events if re.match(rf"\s*<TEACH-CONF-{suffix},\d+> preparation started,", body)]
        assert len(prep) == 1 and prep[0][0] == 7.33333
        assert re.search(rf"<TEACH-CONF-{suffix},\d+>", launch[0][1])
        assert trace[kind]["terminal_level"] == 0 and not trace[kind]["arrivals"]
        result[kind] = {"demand_position_index": demand[0][1],
                        "opening_and_taken_id": take[0][1],
                        "terminal_stock_level": 0, "stock_returns": 0}
    for base in ("0", "1"):
        reconfig_start = [(hour, body) for hour, body in events if f"<TEACH-AIR-01,{base}> reconfig started," in body]
        reconfig_end = [(hour, body) for hour, body in events if f"<TEACH-AIR-01,{base}> reconfig ended," in body]
        fit_start = [(hour, body) for hour, body in events if re.match(rf"\s*system reconfig fit task \d+ on <TEACH-AIR-01,{base}> started", body)]
        fit_end = [(hour, body) for hour, body in events if re.match(rf"\s*system reconfig fit task \d+ on <TEACH-AIR-01,{base}> completed", body)]
        assert len(reconfig_start) == len(reconfig_end) == len(fit_start) == len(fit_end) == 1
        assert reconfig_start[0][0] == fit_start[0][0] == 7
        assert fit_end[0][0] == reconfig_end[0][0] == 7.33333
    result["aircraft_fit_edges"] = {"base_aircraft_ids": ["0", "1"], "start_hour": 7,
                                    "end_hour": 7.33333,
                                    "item_type_to_physical_aircraft_direct_log_link": False}
    return result


def full_report_cells(report: dict, events: list[tuple[float, str]], source: dict) -> dict:
    counts = {
        "ProblemDescription": own.check_problem_description(report, source),
        "ResultSummary": own.check_summary_report(report, events),
        "SystemResults": own.check_system_full_report(report, events, fleet=2, configured_types=2),
        "StockTotalResults": own.check_stock_report(report, events),
    }
    assigned = [(hour, body) for hour, body in events if "<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1" in body]
    deassigned = [(hour, body) for hour, body in events if "<MISSION-CREW at <BASE-01,0>> deallocated from  mission assigned: 1" in body]
    other_allocations = [(hour, body) for hour, body in events if "<MISSION-CREW at <BASE-01,0>> allocated to mission" in body and "allocated to mission assigned: 1" not in body]
    assert len(assigned) == len(deassigned) == 2 and not other_allocations
    assert all(hour == 7 for hour, _ in assigned + deassigned)
    # Every crew grant is released at the same printed timestamp, so the
    # event-derived occupancy integral is zero in all 72 half-hour bins.
    expected_rows = []
    for index in range(72):
        expected_rows.append({"RID": "Total over all Resources", "STID": "Total over all Stations",
                              "STINT": index / 2, "ETINT": (index + 1) / 2,
                              **{name: 2 for name in ("NR", "NRA", "NRN")},
                              **{name: 0 for name in ("NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRF", "NRRI", "NRRT", "NRRO")}})
    expected_total = {name: value for name, value in expected_rows[0].items() if name not in ("STINT", "ETINT")}
    native_rows = own.report_records(report, "ResourceResults")
    native_total = own.report_records(report, "ResourceResultsTotal")
    assert len(native_rows) == 72 and len(native_total) == 1
    for got, want in zip(native_rows, expected_rows):
        assert set(got) == set(want)
        for name, value in want.items():
            assert own.compare_cell(got[name], value, basis="count"), ("ResourceResults", got["STINT"], name, got[name], value)
    assert set(native_total[0]) == set(expected_total)
    for name, value in expected_total.items():
        assert own.compare_cell(native_total[0][name], value, basis="count"), ("ResourceResultsTotal", name, native_total[0][name], value)
    counts["ResourceResults"] = 72 * 16
    counts["ResourceResultsTotal"] = 14
    assert sum(counts.values()) == 5210
    return counts


def main() -> dict:
    closure = own.read_native_json(RUN / "closure.json")
    failure = own.read_native_json(RUN / "failure-seal.json")
    invocation = own.read_native_json(RUN / "invocation.json")
    manifest = own.read_native_json(CASE / "prelaunch-manifest.json")
    approval = own.read_native_json(CASE / "review/independent-prelaunch-go.json")
    assert not RADIO.exists(), "radio arm unexpectedly exists"
    assert closure["run_id"] == invocation["run_id"] == failure["run_id"] == RUN.name
    assert closure["error"] == failure["error"] == "check_behavior rejected native result"
    assert identity(RUN / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["manifest_sha256"] == approval["manifest_sha256"] == identity(CASE / "prelaunch-manifest.json")["sha256"]
    assert closure["approval_sha256"] == identity(CASE / "review/independent-prelaunch-go.json")["sha256"]
    assert closure["approved_preflight_sha256"] == approval["preflight_sha256"]
    assert invocation["session_id"] == 0 and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert invocation["gui"] == {"pid": 13340, "session_id": 1,
                                  "start_unix_ms": 1790590196826, "responding": True}
    assert len(manifest["source_files"]) == 77
    source_hashes = {record["key"]: record["sha256"] for record in manifest["source_files"]}
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == source_hashes
    for record in manifest["source_files"]:
        assert identity(Path(record["path"])) == {"bytes": record["bytes"], "sha256": record["sha256"]}
    assert len(closure["raw"]) == 13
    for name, seal in closure["raw"].items():
        assert identity(RUN / name) == seal, name
    assert len(failure["files"]) == 15
    for name, seal in failure["files"].items():
        assert identity(RUN / name) == seal, name
    steps = own.read_native_json(RUN / "steps.json")
    assert [step["name"] for step in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps[:5])
    assert steps[-1]["status"] == "failed" and steps[-1]["exit_code"] == 1
    assert all(step["gui_preserved"] is True for step in steps)
    assert all(step["child_session_id"] == 0 for step in steps if "child_session_id" in step)
    source = own.read_native_json(CASE / "crew-input.json")
    exported = own.read_native_json(RUN / "roundtrip-raw.json")
    authored_tables = own.child_roundtrip(source, exported)
    assert authored_tables == 24
    converter = own.child_converter((RUN / "run.log").read_text(encoding="utf-8-sig"))
    assert converter == 4
    report = own.read_native_json(RUN / "report-raw.json")
    report_shape = own.report_shape(report)
    assert sum(report_shape.values()) == 5210
    summary = own.report_records(report, "ResultSummary")[0]
    resource_total = own.report_records(report, "ResourceResultsTotal")[0]
    events = own.event_blocks((RUN / "model.log").read_bytes())
    stock_edges = physical_stock_edges(events)
    report_cells = full_report_cells(report, events, source)
    def matching(fragment: str) -> list[tuple[float, str]]:
        return [(hour, body) for hour, body in events if fragment in body]
    assigned = matching("<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1")
    released_assigned = matching("<MISSION-CREW at <BASE-01,0>> deallocated from  mission assigned: 1")
    released_operation_zero = matching("<MISSION-CREW at <BASE-01,0>> deallocated from  mission operation: 0")
    starts = matching(" mission starting,")
    successes = matching(" mission success:")
    completions = matching(" mission completed:")
    assert len(assigned) == len(released_assigned) == len(released_operation_zero) == 2
    assert all(hour == 7 for hour, _ in assigned + released_assigned)
    assert all(hour == 10 for hour, _ in released_operation_zero)
    assert len(starts) == len(successes) == len(completions) == 1
    assert starts[0][0] == 8 and successes[0][0] == completions[0][0] == 10
    assert starts[0][1].count("MISSION-CREW 0") == 2
    assert completions[0][1].count("MISSION-CREW 0") == 2
    assert resource_total["NRMO"] == resource_total["NRMA"] == 0
    assert summary["NREP"] == summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == summary["STMF"] == 1
    author = own.read_native_json(RUN / "author-validation.json")
    assert author["decision"] == "NO_GO" and author["failures"] == ["AssertionError: "]
    return {
        "schema": "c05-var03-v102-independent-failed-crew-diagnostic/v1",
        "decision": "NO_GO_FROZEN_PAIR",
        "run_id": RUN.name,
        "radio_run_absent": True,
        "crew_closure_sha256": identity(RUN / "closure.json")["sha256"],
        "crew_failure_seal_sha256": identity(RUN / "failure-seal.json")["sha256"],
        "raw_seals": len(closure["raw"]),
        "source_pins": len(manifest["source_files"]),
        "authored_roundtrip_tables": authored_tables,
        "converter_warnings": converter,
        "report_shape": report_shape,
        "reported_cells_present": sum(report_shape.values()),
        "report_cells_reconciled": report_cells,
        "physical_stock_edges": stock_edges,
        "native_steps": [(step["name"], step["status"], step["exit_code"]) for step in steps],
        "mission_start_hour": starts[0][0],
        "mission_completion_hour": completions[0][0],
        "h7_crew_assignments": len(assigned),
        "h7_assignment_releases": len(released_assigned),
        "h10_zero_operation_releases": len(released_operation_zero),
        "mission_start_crew_counts": [0, 0],
        "resource_total_nrma": resource_total["NRMA"],
        "resource_total_nrmo": resource_total["NRMO"],
        "summary": {name: summary[name] for name in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")},
        "failed_contract_gate": "crew1 must remain booked for each configured A/B aircraft during shared mission",
        "author_exception_cause": "resource oracle has 2 assigned starts but counts 4 mission deallocation ends, including 2 zero-quantity operation releases",
        "scope": "sealed crew arm diagnostic only; radio arm never started; all crew report cells reconciled to observed zero crew occupancy, but frozen positive booking gate fails",
    }


if __name__ == "__main__":
    data = (json.dumps(main(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (Path(__file__).resolve().parent / "independent-failed-crew-verdict.json").write_bytes(data)
    print(data.decode("utf-8"), end="")
