"""Read accepted originals and write the bounded A17.var01 prospective design.

This is an authoring tool, not a native runner or an acceptance checker.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = REPO / "cases" / "simlox-air-support"
SELECT = REPO / "tmp/a17-var01-root-selection-v100-20261008/20261008T161341097647Z-37e713c2/receipt.json"
A17 = CASES / "A17-multi-unit-group-v1.0.0"
A03_REPORT = Path(
    r"C:\Users\user\Documents\Codex\2026-09-28\simlox-issue18-ssh-current"
    r"\cases\simlox-air-support\A03-two-aircraft-formation-v1.0.1"
    r"\runs\a03-v101-ssh-gui-20260929-01\report-raw.json"
)
OLD_DESC = "A17 two explicit units at two bases serving one group mission; no transfer"
NEW_DESC = "A17.var01 two explicit units at BASE-01 serving one group mission; no transfer"
SHA = {
    "selection": "75a009a4754a842604bc96d588a5ac5a896d1cde8028768b53e93e16e7f9f7ea",
    "input": "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974",
    "a17_report": "fcd289233082398dfa8531475719a6b068dadc841486d050ec71f6815356a8f4",
    "a17_log": "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e",
    "a03_report": "8ff915b97b22720da95698f111697400a6d7bf9069232a73c50f6743668d9e28",
}


def pin(path: Path, digest: str) -> bytes:
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest, str(path)
    return data


def native_json(raw: bytes) -> dict:
    text = raw.decode("utf-8-sig")
    assert len(re.findall(r",(?=\s*[}\]])", text)) == 1
    return json.loads(re.sub(r",(?=\s*[}\]])", "", text))


def typed_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def main() -> None:
    selection = json.loads(pin(SELECT, SHA["selection"]))
    assert selection["decision"] == "ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_ONLY"
    source = json.loads(pin(A17 / "native-input.json", SHA["input"]))
    report_path = A17 / "runs/a17-v100-ssh-20260929-01/report-raw.json"
    parent = native_json(pin(report_path, SHA["a17_report"]))["report"]["tables"]
    control = native_json(pin(A03_REPORT, SHA["a03_report"]))["report"]["tables"]
    lines = pin(A17 / "runs/a17-v100-ssh-20260929-01/model.log", SHA["a17_log"]).decode("utf-8-sig").splitlines()
    assert len(lines) == 60 and sum(x.startswith("Time:") for x in lines) == 52
    assert [t["name"] for t in parent] == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    assert len(parent) == len(control)

    tables = []
    constants_system = {
        "NSYMC": 0, "NSYMP": 0, "NSYMT": 0, "NSYMS": 0, "NSYUA": 0,
        "NSYA": 2, "NSYAL": 0, "NSYRP": 0, "NSYPM": 0, "NSYTP": 0,
        "NSYWR": 0, "NSYWI": 0, "NSYLA": 0, "NSYUH": 0, "NREPT": 0,
        "NPMT": 0, "NFAIL": 0, "NDAM": 0, "NPMS": 0, "NROBT": 0,
        "NRCFG": 0, "STREQ": 0, "STF": 0, "STLOW": 0, "SYDT": None,
        "SYDTU": 0, "NSYDT": 0, "NSYSW": 0, "NPSTA": 0, "NPSUC": 0,
    }
    constants_stock = {
        "NBO": 0, "NBOU": None, "ROS": None, "ROST": None, "WT": None,
        "WTT": None, "WTS": None, "PNB": 1, "NDF": 0, "NDD": 0,
        "NDR": 0, "NDP": 0, "NLD": 0, "NWT": 0,
    }
    for table in parent:
        name = table["name"]
        columns = table["columns"]
        assert len(table["instances"]) == 1
        instance_name = table["instances"][0]["instance_name"]
        if name == "ProblemDescription":
            rows = [[NEW_DESC]]
        elif name == "ResultSummary":
            rows = [[1, 0, 36, 1, 0, 1, 0, 1, 0, 1, 0]]
        elif name == "SystemResults":
            assert len(columns) == 40
            rows = []
            for bin_index in range(72):
                start = bin_index / 2
                end = start + 0.5
                dynamic = {
                    "UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": start, "ETINT": end,
                    "NSYRY": 0 if 7 <= start < 10 else 2,
                    "NSYMA": 2 if 7 <= start < 10 else 0,
                    "NSYMO": 2 if 8 <= start < 10 else 0,
                    "NSYMR": 2 if 7 <= start < 8 else 0,
                    "FTMO": 1 if 8 <= start < 10 else 0,
                    "STACC": 2 if 8 <= start < 10 else 0,
                }
                expected = dynamic | constants_system
                assert set(expected) == {c["name"] for c in columns}
                rows.append([expected[c["name"]] for c in columns])
        elif name == "StockTotalResults":
            assert len(columns) == 16
            rows = []
            for bin_index in range(72):
                start = bin_index / 2
                expected = {"STINT": start, "ETINT": start + 0.5} | constants_stock
                assert set(expected) == {c["name"] for c in columns}
                rows.append([expected[c["name"]] for c in columns])
        else:
            raise AssertionError(name)
        tables.append({"name": name, "columns": columns, "instances": [{"instance_name": instance_name, "rows": rows}]})

    cell_count = sum(len(t["columns"]) * len(t["instances"][0]["rows"]) for t in tables)
    assert cell_count == 4044
    for expected, accepted, analogue in zip(tables, parent, control, strict=True):
        assert expected["name"] == accepted["name"] == analogue["name"]
        assert expected["columns"] == accepted["columns"] == analogue["columns"]
        assert expected["instances"][0]["instance_name"] == accepted["instances"][0]["instance_name"] == analogue["instances"][0]["instance_name"]
        for row, old, other in zip(expected["instances"][0]["rows"], accepted["instances"][0]["rows"], analogue["instances"][0]["rows"], strict=True):
            for col, x, y, z in zip(expected["columns"], row, old, other, strict=True):
                if col["name"] == "PDESC":
                    assert y == OLD_DESC
                else:
                    assert typed_equal(x, y) and typed_equal(x, z), (expected["name"], col["name"], x, y, z)

    report = {"schema": "a17-var01-prospective-derived-report/v1", "cell_count": cell_count, "tables": tables}
    log_oracle = {
        "schema": "a17-var01-prospective-log-graph/v1",
        "status": "strict_predeclared_hypothesis_not_native_observation",
        "parent_lines": 60, "parent_timed_lines": 52,
        "accepted_arm_counts": {"full_lines": 60, "timed_lines": 52, "untimed_continuations": 6},
        "bounded_render_arms": {
            "second_unit_base_instance_index": [0, 1],
            "second_aircraft_base_controller_index": [0, 1],
            "h10_return_block_order": [[0, 1], [1, 0]],
            "cardinality": 8,
            "constraints": [
                "Each selected index is stable across every descriptor for that unit or aircraft.",
                "The two index choices are independent diagnostic axes, not a claim that either is a general rule.",
                "Exactly two complete return blocks and two priority-list lines with one blank continuation each are required; no coalesced or extra diagnostics.",
            ],
        },
        "event_phases": [
            {"hour": 0, "events": ["ID0 failure marker", "ID0 ready+ in TEACH-UNIT at BASE-01", "TEACH-UNIT ready count1", "ID1 failure marker", "ID1 ready+ in TEACH-UNIT-2 at BASE-01", "TEACH-UNIT-2 ready count1", "start day0"]},
            {"hour": 7, "events": ["one TEACH-GROUP mission ordered/created/activated for2", "ID0 allocated from TEACH-UNIT then ready-", "ID1 allocated from TEACH-UNIT-2 then ready-", "preparation start/end for each ID with no resource wait"]},
            {"hour": 8, "events": ["joint mission start with IDs0,1 and duration2"]},
            {"hour": 8.5, "events": ["joint task start"]},
            {"hour": 9.5, "events": ["joint task completion"]},
            {"hour": 10, "events": ["mission success before completion", "both turnround starts after completion", "two return blocks, either whole-block order"]},
            {"hour": 24, "events": ["start day1"]},
        ],
        "h10_return_block_per_id": ["turnround ended", "System arrives with mission success", "no failures continuation", "no PMTasks continuation", "ready+ at original unit", "System ready", "duplicate System ready", "original unit systems ready:1", "Repair task priority list", "blank continuation"],
        "partial_order": [
            "h0 ready before h7 allocation; exactly one aircraft remains tied to each explicit unit.",
            "h7 allocation precedes preparation; preparation precedes h8 joint start; h8.5 task start precedes h9.5 task completion.",
            "h10 mission success precedes completion; each ID's turnround start precedes its own complete return block.",
            "Return blocks may commute as units are distinct; lines within each block may not reorder or interleave.",
        ],
        "reject": ["other line count", "other timed count", "other physical ID or unit", "grouped ready counts replacing one per unit", "missing or extra mission/return/priority/continuation", "partial return block interleaving", "different task times", "failure or maintenance", "unexpected station/controller index", "unlisted converter diagnostics"],
        "interpretation_limit": "This finite eight-arm parser can support only the bounded two-unit shared-base mission behavior. It does not establish general station-controller indexing or return ordering.",
    }
    expected_file_line = "File: " + (selection["future_run"].replace("\\", "/") + "/model.sxi")
    assert expected_file_line.isascii() and len(expected_file_line.encode("ascii")) == 191
    contract = {
        "schema": "a17-var01-prospective-contract/v1",
        "decision_stage": "PROSPECTIVE_DESIGN_ONLY",
        "publication_id": "A17.var01.two_explicit_units_same_station.1.0.0",
        "parent_publication_id": "A17.two_units.1.0.0",
        "selection_receipt": {"path": str(SELECT), "bytes": SELECT.stat().st_size, "sha256": SHA["selection"]},
        "base": selection["base"], "parent_publications": selection["parent_publications"],
        "source_pair_file": selection["source_pair_file"], "source_disk_git_pairs": selection["source_disk_git_pairs"],
        "mandatory_original_count": selection["mandatory_original_count"],
        "parent_index_absent_is_not_invented": selection["parent_index_absent_is_not_invented"],
        "catalog_local": selection["catalog_local"], "catalog_git": selection["catalog_git"],
        "installed_manual_sha256": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
        "manual_physical_pages": [178, 184, 185, 196, 309, 310, 311, 312, 313],
        "source_delta": [
            {"table": "Unit", "key": "TEACH-UNIT-2", "field": "STID", "before": "BASE-02", "after": "BASE-01", "role": "sole_business_delta"},
            {"table": "ProblemDescription", "field": "PDESC", "before": OLD_DESC, "after": NEW_DESC, "role": "editorial_label"},
        ],
        "source_invariants": ["36-hour horizon", "fixed parent seed", "two explicit units", "SystemDeployment one aircraft in each distinct unit", "UnitGroup members and priorities", "one h8 two-aircraft mission, duration2", "station BASE-02 remains defined but becomes unused", "no transfer, failure, repair or item demand"],
        "source_authored_topology": {"tables": 33, "rows": 20, "cells": 203, "changed_cells": 2},
        "conversion_hypothesis": {"errors": 0, "warning_codes": [108, 126], "notes": 0, "exact_file_line": expected_file_line, "file_line_ascii_bytes": 191, "maximum_file_line_ascii_bytes": 199, "unexpected_unused_station_diagnostic": "NO_GO"},
        "log_oracle": "log-oracle.json", "report_oracle": "report-oracle.json", "report_cell_count": 4044,
        "report_rules": {
            "ProblemDescription": "one exact editorial PDESC string",
            "ResultSummary": "11 typed cells [1,0,36,1,0,1,0,1,0,1,0] from one repetition and one successful formation mission",
            "SystemResults": {"rows": 72, "columns": 40, "time_bins": "[i/2,(i+1)/2), i=0..71", "identity": "aggregate over all units/systems", "variable_columns": {"NSYRY": "2 outside [7,10), else 0", "NSYMA": "2 on [7,10), else 0", "NSYMO": "2 on [8,10), else 0", "NSYMR": "2 on [7,8), else 0", "FTMO": "1 on [8,10), else 0", "STACC": "2 on [8,10), else 0"}, "constant_columns": constants_system},
            "StockTotalResults": {"rows": 72, "columns": 16, "time_bins": "same half-hour bins", "constant_columns": constants_stock},
        },
        "analogue_comparison": "Accepted A03 same-base one-unit and A17 two-base two-unit reports agree in all 4043 typed non-PDESC cells. This corroborates aggregate invariance only; neither accepted run contains two distinct units at one base.",
        "acceptance_predicate": "Exact two-cell source delta, source-bound conversion path/diagnostics, one of eight predeclared complete 60/52 event-graph arms, per-ID/unit conservation, and all 4044 derived report cells. Any other output is NO_GO with original evidence preserved; no post-observation oracle expansion.",
        "excluded_claims": ["general station controller indexing", "exact h10 tie-order law", "implicit units", "station capacity in other models", "GUI visual behavior", "cross-engine equivalence", "performance", "whole A17.var01", "Issue18 completion"],
        "native_run_id": "a17-var01-same-station-v100-ssh-20261008-01",
        "native_run_directory": selection["future_run"],
        "native_calls_current": 0, "accepted_checker_calls_current": 0,
        "required_future_gates": ["independent prospective contract GO", "new package and method freeze", "fresh source and ownership/GUI/mutex/path guard", "zero-native SSH preflight with exact receipt", "separate independent GO_PRELAUNCH", "one unique native attempt", "independent original-byte postrun review"],
    }
    for name, body in [("report-oracle.json", report), ("log-oracle.json", log_oracle), ("contract.json", contract)]:
        path = HERE / name
        assert not path.exists(), path
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PROSPECTIVE_ONLY", "report_cells": cell_count, "log_arms": 8, "source_delta_cells": 2, "native_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
