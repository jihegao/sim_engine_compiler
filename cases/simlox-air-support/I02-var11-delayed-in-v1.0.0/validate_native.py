"""Read-only replay of the bounded delayed IN contrast and sealed native files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2"
NATIVE = HERE / "runs/i02-var11-in-delay2-v100-ssh-20261002-01"
REPORT = HERE / "runs/i02-var11-depot-item-v100-ssh-20261002-01"
CONTROL_NATIVE = PARENT / "runs/i02-var01-in-v102-ssh-20261002-01"
CONTROL_REPORT = PARENT / "runs/i02-var01-item-results-v102-ssh-20261002-01"
SOURCE_SHA = "7d520331ee6233a83600ff711247ec66f15d362a4f377e96a59e0d5a4b6f751c"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"
SETTINGS_SHA = "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, name: str) -> list[dict]:
    found = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(found) == 1, (name, len(found))
    cols = [c["name"] for c in found[0]["columns"]]
    return [dict(zip(cols, row, strict=True)) for instance in found[0]["instances"]
            for row in instance["rows"]]


def seals(folder: Path, closure: dict) -> bool:
    return (closure["error"] is None and closure["run_id"] == folder.name
            and sha(folder / "invocation.json") == closure["invocation_sha256"]
            and closure["source_hashes_before"] == closure["source_hashes_after"]
            and all((folder / name).stat().st_size == meta["bytes"]
                    and sha(folder / name) == meta["sha256"]
                    for name, meta in closure["raw"].items()))


def main() -> None:
    checks: list[dict] = []

    def check(name: str, value: bool) -> None:
        checks.append({"name": name, "passed": bool(value)})

    contract = read(HERE / "contract.json")
    diff = read(HERE / "exact-diff.json")
    check("source_and_parent", sha(HERE / "native-input.json") == SOURCE_SHA
          and sha(PARENT / "native-input.json") == PARENT_SHA
          and contract["source_sha256"] == SOURCE_SHA
          and contract["direct_parent"]["source_sha256"] == PARENT_SHA)
    check("single_business_field_delta", diff["item_transfer_delta"] == [["TFDT", 0.0, 2.0]]
          and diff["changed_tables"] == ["ItemTransfer", "ProblemDescription"]
          and diff["unchanged_table_count"] == 30
          and sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("reproducible_selector", sha(HERE / "runs/report-settings/item-position-results.sxs") == SETTINGS_SHA)

    nc, rc = read(NATIVE / "closure.json"), read(REPORT / "closure.json")
    pc, prc = read(CONTROL_NATIVE / "closure.json"), read(CONTROL_REPORT / "closure.json")
    for label, folder, closure, count in (
        ("child_native", NATIVE, nc, 12), ("child_report", REPORT, rc, 2),
        ("control_native", CONTROL_NATIVE, pc, 12), ("control_report", CONTROL_REPORT, prc, 2),
    ):
        check(f"{label}_sealed", seals(folder, closure) and len(closure["raw"]) == count)
    check("child_native_source_pins", nc["source_hashes_before"]["input"] == SOURCE_SHA
          and nc["source_hashes_before"]["parent"] == PARENT_SHA
          and nc["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1"))
    check("child_report_source_pins", rc["source_hashes_before"]["sxo"] == nc["raw"]["model.sxo"]["sha256"]
          and rc["source_hashes_before"]["settings"] == SETTINGS_SHA
          and rc["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
          and read(REPORT / "invocation.json")["source_closure_sha256"] == sha(NATIVE / "closure.json"))
    check("control_source_pins", pc["source_hashes_before"]["input"] == PARENT_SHA
          and prc["source_hashes_before"]["sxo"] == pc["raw"]["model.sxo"]["sha256"])
    steps = read(NATIVE / "steps.json")
    check("five_native_steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"]
          and all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
    check("guarded_session0", read(NATIVE / "invocation.json")["session_id"] == 0
          and read(REPORT / "invocation.json")["session_id"] == 0
          and read(NATIVE / "invocation.json")["gui"]["pid"] == 13340
          and read(REPORT / "invocation.json")["gui"]["pid"] == 13340)
    roundtrip = read(NATIVE / "roundtrip-validation.json")
    check("authored_roundtrip", roundtrip["passed"] and len(roundtrip["populated_tables"]) == 22)
    check("zero_conversion_errors", "Input conversion completed. Errors: 0," in
          (NATIVE / "run.log").read_text(encoding="utf-8-sig"))
    check("report_export_completed", rc["exit_code"] == 0 and "Export completed!" in
          (REPORT / "report-export.log").read_text(encoding="utf-8-sig"))

    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    control_log = (CONTROL_NATIVE / "model.log").read_text(encoding="utf-8-sig")
    events = (
        "Time: 4  item transfer task 0 (IN)  created",
        "Time: 4  item transfer task 0 (IN)  starts with 1 items, transfer time: 2",
        "Time: 6  item transfer task 0 (IN)  arrives with 1 items",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
    )
    for i, event in enumerate(events):
        check(f"physical_event_{i}", event in log)
    check("one_delayed_arrival", log.count("item transfer task 0 (IN)  arrives with 1 items") == 1)
    check("zero_delay_parent_arrival", "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in control_log)

    child, parent = read(REPORT / "item-report-raw.json"), read(CONTROL_REPORT / "item-report-raw.json")
    rows, old = table(child, "ItemResults"), table(parent, "ItemResults")
    check("aligned_half_hour_depot_grid", len(rows) == len(old) == 72 and all(
        row["IID"] == "TEACH-LRU-01" and row["STID"] == "DEPOT-01"
        and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2
        and old[i]["STINT"] == row["STINT"] for i, row in enumerate(rows)))
    check("delayed_nominal_and_onhand", all(row["STSZ"] == row["STOHA"] == (1 if i < 12 else 2)
          for i, row in enumerate(rows[:20])))
    check("control_nominal_and_onhand", all(row["STSZ"] == row["STOHA"] == (1 if i < 8 else 2)
          for i, row in enumerate(old[:20])))
    differences = [i for i, (a, b) in enumerate(zip(old, rows, strict=True)) if a != b]
    check("only_four_item_bins_differ", differences == [8, 9, 10, 11])
    check("only_stock_and_onhand_fields_differ", all(
        {key for key in old[i] if old[i][key] != rows[i][key]} == {"STSZ", "STOHA"}
        for i in differences))
    check("later_demand_and_repair", rows[20]["STSZ"] == 2 and rows[20]["STOHA"] == 1
          and rows[20]["NDF"] == 1 and rows[26]["STOHA"] < 2
          and all(row["STOHA"] == 2 for row in rows[27:]))
    check("item_backorders_zero", all(row["NBO"] == 0 for row in rows))
    totals, old_totals = table(child, "ItemResultsTotal"), table(parent, "ItemResultsTotal")
    check("horizon_average_nominal", len(totals) == len(old_totals) == 1
          and abs(totals[0]["STSZ"] - 66 / 36) < 1e-6
          and abs(old_totals[0]["STSZ"] - 68 / 36) < 1e-6)
    check("horizon_average_onhand_delta", abs((old_totals[0]["STOHA"] - totals[0]["STOHA"]) - 2 / 36) < 1e-6)
    check("unchanged_activity_totals", all(totals[0][key] == old_totals[0][key]
          for key in totals[0] if key not in ("STSZ", "STOHA")))
    for name in ("MissionResults", "MissionResultsTotal", "FixedMissionResults",
                 "FixedMissionResultsTotal", "SystemResults", "StockTotalResults", "ResultSummary"):
        check(f"same_{name}", table(child, name) == table(parent, name))
    result = {"schema": "simlox-i02-var11-delayed-in-author-validation/v1",
              "variant_id": "I02.var11", "source_sha256": SOURCE_SHA,
              "native_run_id": NATIVE.name, "item_report_run_id": REPORT.name,
              "control_native_run_id": CONTROL_NATIVE.name, "control_item_report_run_id": CONTROL_REPORT.name,
              "differing_item_result_bins": differences,
              "checks": checks, "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks), "check_count": len(checks),
              "claim": "For this tracked one-unit IN, TFDT2 starts at h4 and physically arrives at h6; depot nominal and on-hand stock both rise at h6.",
              "limits": "One IN/IID/depot, seed1, TFDT0 versus 2; unchanged downstream demand avoids testing shortage competition."}
    path = HERE / "author-validation.json"
    path.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {path}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
