"""Independent, read-only replay of one excluded C05.var03 crew trace.

Uses only reviewer-authored v1.0.2 diagnostic code, never the author validator.
Raw native bytes and the original positive-pair NO_GO remain unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
ORIGINAL = CASE.parent / "C05-var03-config-resource-v1.0.2"
sys.path.insert(0, str(ORIGINAL / "review"))
import independent_failed_crew_diagnostic as diagnostic  # reviewer-owned, pinned
import independent_replay as old_replay  # reviewer-owned PREP_ONLY parser/ledgers

CONTRACT_SHA = "50c4f36e8756e1120db7c7e627cfb4713f387b5105fa116ed9d2affdce75ff8e"
CONTRACT_GO_SHA = "aef173ea82dcacb2b581d7256a58a28390d6ad0c58e30851babd57ae4dd36cd5"


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_pin(pin: dict) -> None:
    path = ROOT / pin["path"]
    assert identity(path) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}, path


def reject_tamper(report: dict, table_name: str, row_index: int, column_name: str, replacement) -> None:
    copied = copy.deepcopy(report)
    table = old_replay.tables(copied, "report")[table_name]
    columns = [column["name"] for column in table["columns"]]
    table["instances"][0]["rows"][row_index][columns.index(column_name)] = replacement
    events = old_replay.event_blocks((diagnostic.RUN / "model.log").read_bytes())
    source = old_replay.read_native_json(ORIGINAL / "crew-input.json")
    try:
        diagnostic.full_report_cells(copied, events, source)
    except AssertionError:
        return
    raise AssertionError(("tamper accepted", table_name, row_index, column_name))


def assert_claim_scope(contract: dict, crew: dict) -> None:
    assert contract["original_pair_decision"] == "NO_GO_FROZEN_PAIR"
    assert contract["radio_arm"] == "not_started_not_tested" and crew["radio_run_absent"] is True
    assert crew["physical_stock_edges"]["aircraft_fit_edges"]["item_type_to_physical_aircraft_direct_log_link"] is False


def reject_scope_tamper(contract: dict, crew: dict) -> None:
    mutated = dict(contract)
    mutated["original_pair_decision"] = "GO_BOUNDED"
    try:
        assert_claim_scope(mutated, crew)
    except AssertionError:
        pass
    else:
        raise AssertionError("false positive pair claim accepted")
    mutated = dict(contract)
    mutated["radio_arm"] = "passed"
    try:
        assert_claim_scope(mutated, crew)
    except AssertionError:
        pass
    else:
        raise AssertionError("untested radio claim accepted")
    mutated_crew = copy.deepcopy(crew)
    mutated_crew["physical_stock_edges"]["aircraft_fit_edges"]["item_type_to_physical_aircraft_direct_log_link"] = True
    try:
        assert_claim_scope(contract, mutated_crew)
    except AssertionError:
        pass
    else:
        raise AssertionError("unlogged serial edge accepted")


def main() -> dict:
    assert identity(CASE / "contract.json")["sha256"] == CONTRACT_SHA
    assert identity(CASE / "review/independent-contract-go-2026-10-07.md")["sha256"] == CONTRACT_GO_SHA
    contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8-sig"))
    assert contract["classification"] == "retrospective_single_arm_counterexample"
    assert contract["new_native_runs"] == 0 and contract["radio_arm"] == "not_started_not_tested"
    assert contract["original_pair_decision"] == "NO_GO_FROZEN_PAIR"
    assert len(contract["pins"]) == 22
    for pin in contract["pins"].values():
        check_pin(pin)
    original_contract = json.loads((ORIGINAL / "contract.json").read_text(encoding="utf-8-sig"))
    assert old_replay.accepted_source_bytes(original_contract) == 23
    accepted = old_replay.accepted_controls(original_contract)
    assert sum(item["raw_seals"] for item in accepted.values()) == 48
    crew = diagnostic.main()
    assert_claim_scope(contract, crew)
    assert crew["decision"] == "NO_GO_FROZEN_PAIR" and crew["radio_run_absent"]
    assert sum(crew["report_cells_reconciled"].values()) == 5210
    assert crew["mission_start_crew_counts"] == [0, 0]
    assert crew["resource_total_nrma"] == crew["resource_total_nrmo"] == 0
    assert crew["physical_stock_edges"]["aircraft_fit_edges"]["item_type_to_physical_aircraft_direct_log_link"] is False
    report = old_replay.read_native_json(diagnostic.RUN / "report-raw.json")
    reject_tamper(report, "ResultSummary", 0, "NREP", 2)
    reject_tamper(report, "ResourceResults", 16, "NRMO", 1)
    reject_tamper(report, "ResourceResultsTotal", 0, "NRMA", 1)
    reject_tamper(report, "ProblemDescription", 0, "PDESC", "false crew claim")
    nullable = None
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        for row_index, row in enumerate(old_replay.report_records(report, name)):
            for field, value in row.items():
                if value is None:
                    nullable = (name, row_index, field)
                    break
            if nullable:
                break
        if nullable:
            break
    assert nullable is not None
    reject_tamper(report, *nullable, 0)
    reject_scope_tamper(contract, crew)
    assert not (ORIGINAL / "runs" / "c05-var03-v102-radio-ssh-20261007-01").exists()
    assert crew["physical_stock_edges"]["TEACH-LRU-A"]["demand_position_index"] == "0"
    assert crew["physical_stock_edges"]["TEACH-LRU-B"]["demand_position_index"] == "0"
    return {
        "schema": "c05-var03-counterexample-v010-independent-replay/v1",
        "decision": "GO_BOUNDED_READONLY_COUNTEREXAMPLE",
        "contract_sha256": CONTRACT_SHA,
        "original_pair_decision": "NO_GO_FROZEN_PAIR",
        "radio_arm": "not_started_not_tested",
        "new_native_runs": 0,
        "direct_pins": len(contract["pins"]),
        "original_manifest_source_pins": crew["source_pins"],
        "accepted_source_local_git_pins": 23,
        "accepted_raw_seals": 48,
        "crew_raw_seals": crew["raw_seals"],
        "crew_closure_sha256": crew["crew_closure_sha256"],
        "crew_failure_seal_sha256": crew["crew_failure_seal_sha256"],
        "report_cells_reconciled": crew["report_cells_reconciled"],
        "report_cell_total": 5210,
        "tamper_probes_rejected": 8,
        "native_counterexample": {
            "h7_transient_crew_assignments": 2,
            "h7_assignment_releases": 2,
            "h8_launch_h10_success_with_held_crew": 0,
            "resource_total_nrma": 0,
            "resource_total_nrmo": 0,
        },
        "stock_identity_limit": "Both demand position suffixes are 0; no direct item-type-to-aircraft serial edge is logged.",
        "scope": "one sealed crew arm only; bounded read-only diagnostic, no positive pair acceptance",
    }


if __name__ == "__main__":
    payload = (json.dumps(main(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (Path(__file__).resolve().parent / "independent-verdict.json").write_bytes(payload)
    print(payload.decode("utf-8"), end="")
