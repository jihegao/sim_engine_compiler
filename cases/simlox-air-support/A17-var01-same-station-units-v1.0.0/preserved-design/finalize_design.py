"""Close provenance and decision scope for the A17.var01 prospective design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SELECTION_DIR = REPO / "tmp/a17-var01-root-selection-v100-20261008/20261008T161341097647Z-37e713c2"
SELECTION = SELECTION_DIR / "receipt.json"
SELECTION_SHA = "75a009a4754a842604bc96d588a5ac5a896d1cde8028768b53e93e16e7f9f7ea"


def digest(path: Path) -> dict:
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def save_absent(name: str, obj: object) -> dict:
    path = HERE / name
    assert not path.exists(), str(path)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return digest(path)


def main() -> None:
    assert digest(SELECTION)["sha256"] == SELECTION_SHA
    selected = json.loads(SELECTION.read_text(encoding="utf-8"))
    initial = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    graph = json.loads((HERE / "log-oracle.json").read_text(encoding="utf-8"))
    report = json.loads((HERE / "report-oracle.json").read_text(encoding="utf-8"))
    assert report["cell_count"] == 4044
    assert selected["source_disk_git_pairs"] == 41 and selected["mandatory_original_count"] == 61
    pair_path = SELECTION_DIR / "accepted-source-pairs.json"
    assert digest(pair_path)["sha256"] == selected["source_pair_file"]["sha256"]
    pairs = json.loads(pair_path.read_text(encoding="utf-8"))
    assert len(pairs) == 41
    for row in selected["required_local_sources"] + selected["mandatory_originals"]:
        got = digest(Path(row["path"]))
        assert got["bytes"] == row["bytes"] and got["sha256"] == row["sha256"]

    pins = {
        "schema": "a17-var01-prospective-source-pins/v1",
        "selection_receipt": digest(SELECTION),
        "accepted_source_pairs": digest(pair_path),
        "accepted_source_pair_count": 41,
        "required_local_sources": selected["required_local_sources"],
        "required_local_source_count": len(selected["required_local_sources"]),
        "mandatory_originals": selected["mandatory_originals"],
        "mandatory_original_count": 61,
        "catalog_local_501": {"path": str(SELECTION_DIR / "catalog-local-501.json.bytes"), **selected["catalog_local"]},
        "catalog_git_501": {"path": str(SELECTION_DIR / "catalog-git-501.json.bytes"), **selected["catalog_git"]},
        "identity_rule": "Distinct local and Git catalog bytes are separately pinned; no normalized byte-equality assertion.",
        "A17_parent_index": "absent; the accepted catalog entry, signoff, independent result, closure and original raw files are the parent evidence",
    }
    for key in ("catalog_local_501", "catalog_git_501"):
        got = digest(Path(pins[key]["path"]))
        assert got["bytes"] == pins[key]["bytes"] and got["sha256"] == pins[key]["sha256"]
    pins_pin = save_absent("source-pins.json", pins)

    graph["decision_arms"] = {
        "primary_expected": {
            "second_unit_base_instance_index": 0,
            "second_aircraft_base_controller_index": 0,
            "h10_return_block_order": [0, 1],
            "status_if_all_other_gates_pass": "bounded_acceptance_candidate",
            "basis": "Accepted A03 one-unit same-base and A17 distinct-base logs both render station/controller index0 and ID0 then ID1; this is a predeclared hypothesis, not an established two-unit/shared-base law.",
        },
        "other_seven_finite_forms": {
            "status": "diagnostic_NO_GO_for_primary_contract",
            "purpose": "Preserve and classify a controller/index/order surprise without changing the oracle after observation. A separate contract would be required to accept any such branch.",
        },
        "outside_eight_forms": "NO_GO_unmodeled_trace",
    }
    graph_pin = save_absent("log-oracle-v2.json", graph)

    contract = dict(initial)
    contract["schema"] = "a17-var01-prospective-contract/v2"
    contract["source_pins"] = pins_pin
    contract["log_oracle"] = graph_pin
    contract["report_oracle"] = digest(HERE / "report-oracle.json")
    contract["initial_design_draft"] = digest(HERE / "contract.json")
    contract["initial_log_graph_draft"] = digest(HERE / "log-oracle.json")
    contract["decision_table"] = {
        "expected_primary_trace_and_derived_report": "CONTRACT_PASS_CANDIDATE_ONLY_AFTER_NATIVE_AND_INDEPENDENT_REVIEW",
        "finite_nonprimary_log_arm": "NO_GO_PRESERVED_DIAGNOSTIC",
        "unlisted_log_or_converter_diagnostic": "NO_GO_PRESERVED_DIAGNOSTIC",
        "missing_or_extra_report_cell_or_wrong_type": "NO_GO_PRESERVED_DIAGNOSTIC",
        "source_export_mismatch": "NO_GO_BEFORE_CALCULATION",
        "preflight_or_path_gate_failure": "NO_GO_BEFORE_NATIVE",
    }
    contract["acceptance_predicate"] = (
        "Only the primary expected log arm, exact source/export/path/converter gate, "
        "physical unit and aircraft conservation, and all 4044 derived typed report cells "
        "may become a bounded pass after one future native run and independent review. "
        "The seven other finite render arms are recorded as diagnostics and are NO_GO under this contract."
    )
    contract["unresolved_pre_native_risks"] = [
        "Two distinct explicit units sharing BASE-01 have no accepted exact controller-index or h10 printer-order precedent.",
        "BASE-02 remains a defined unused Station row; converter note/warning behavior is unobserved.",
        "The aggregate report expectation is source/event derived and corroborated by A03/A17; the two-unit shared-base middle configuration is unobserved.",
    ]
    contract_pin = save_absent("contract-v2.json", contract)
    text = f"""# A17.var01 prospective shared-base contract

This is a **design-only** hypothesis. No child input, package, SSH preflight, native run, accepted checker run, or catalog mutation was made. The governing machine-readable contract is `contract-v2.json` ({contract_pin['bytes']} bytes, SHA-256 `{contract_pin['sha256']}`). The initial `contract.json` and `log-oracle.json` are preserved drafts; v2 makes the decision rule explicit.

## Source and scope

The accepted A17 parent is `A17.two_units.1.0.0`; its package has no `evidence-index.json`. `source-pins.json` binds the fresh root selection receipt, 41 accepted disk/Git source pairs, 12 local source files, 61 mandatory original files, and distinct local/Git catalog 501 byte streams. A17 derives from accepted A03 1.0.1, which derives from accepted A02 1.0.0. The installed SIMLOX manual permits multiple explicit units at a base (physical pp.178 and 196) and documents UnitGroup mission selection (pp.184–185, 309–313). It does not specify the shared-base diagnostic controller index or complete same-hour printer order.

Change only `Unit[TEACH-UNIT-2].STID` from `BASE-02` to `BASE-01`, plus the exact editorial `ProblemDescription.PDESC` shown in the contract. Keep 36 hours, fixed parent seed, two deployment rows of one aircraft each, distinct explicit unit IDs, UnitGroup priorities, and one h8–10 two-aircraft mission. `BASE-02` remains defined but unused. One business cell and one editorial cell change among 203 authored cells.

## Physical and log hypothesis

`log-oracle-v2.json` gives an exhaustive 60-line/52-timed-line causal graph, six untimed return continuations, full ID0/ID1 ownership, h0 one-ready-per-unit, h7 two allocations and preparation, h8 joint launch, h8.5–9.5 task, h10 success and two independent complete return blocks, and h24 day marker. The graph predeclares eight finite render forms from two possible second-unit station indices, two possible second-aircraft controller indices, and two whole-block h10 orders. **Only** index0/index0/ID0-then-ID1 is the expected contract-pass candidate. The other seven are preserved diagnostic NO_GO results; they cannot be promoted by fitting a native observation. Missing, additional, interleaved, or unrecognized lines are NO_GO. This does not claim a general controller or tie-order law.

Accepted A03 demonstrates two aircraft sharing BASE-01 **within one unit**, with outer controller index0 and ready count 1 then 2. Accepted A17 demonstrates two **distinct** units at different bases, each with one ready aircraft and outer controller index0. Neither is the proposed two-unit/shared-base configuration. Therefore simple BASE-02 text substitution does not establish the full log.

## Complete report prediction

`report-oracle.json` contains all 4,044 prospective cells. Its 72 half-hour SystemResults rows are generated from the physical phase ledger: both aircraft ready outside [7,10), assigned on [7,10), reserved on [7,8), operating on [8,10); one of one group missions flies, with two systems accepted. Aggregate identity and time bounds are explicit; all other 30 System columns are exact declared typed constants, including availability 2, no faults/maintenance/downtime and null undefined SYDT. ResultSummary's 11 exact values follow one repetition and one successful mission. StockTotalResults has 72 matching half-hour bins and 14 explicitly declared constant columns from no item demand. PDESC is the sole predicted difference. A03's accepted same-base/one-unit report and A17's accepted two-base/two-unit report agree in all 4,043 non-PDESC typed cells, corroborating this aggregate prediction without proving shared-base event order. No StationResults table exists.

Conversion must produce zero errors, exactly documented warning codes 108/126, no note, and exact raw Input/Output/File paths; the proposed forward-slash `File: .../model.sxi` line is 191 ASCII bytes, below the prior 199-byte bound. An extra unused-station diagnostic or any source/export mismatch is NO_GO. Later construction must fresh-check physical path absence and ancestors, source/Git pins, GUI/session/mutex state, preflight receipt, and independent GO_PRELAUNCH. No native dispatch is authorized by this design.

The scope is one fixed seed, two explicit units at one station, and one group mission. It excludes implicit units, other station capacities, general physical identity or tie order, GUI behavior, cross-engine equivalence, performance, whole A17.var01, and Issue #18 completion.
"""
    path = HERE / "design.md"
    assert not path.exists()
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(json.dumps({"contract": contract_pin, "source_pins": pins_pin, "log": graph_pin, "design": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
