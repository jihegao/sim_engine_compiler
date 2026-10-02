"""Replay the bounded I02.var01 IN evidence without invoking SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "runs" / "i02-var01-in-v102-ssh-20261002-01"
REPORT = HERE / "runs" / "i02-var01-item-results-v102-ssh-20261002-01"
SOURCE_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"
PARENT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
SETTINGS_SHA = "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, name: str) -> list[dict]:
    matches = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(matches) == 1, (name, len(matches))
    columns = [c["name"] for c in matches[0]["columns"]]
    return [dict(zip(columns, row, strict=True)) for instance in matches[0]["instances"]
            for row in instance["rows"]]


def main() -> None:
    checks: list[dict] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract = read(HERE / "contract.json")
    check("source_and_parent_pins", sha(HERE / "native-input.json") == SOURCE_SHA
          and sha(HERE / "../E04-upstream-transport-fast-v1.0.0/native-input.json") == PARENT_SHA
          and contract["source_sha256"] == SOURCE_SHA)
    check("report_settings_reproducible", sha(HERE / "runs/report-settings/item-position-results.sxs") == SETTINGS_SHA)

    native_closure = read(NATIVE / "closure.json")
    report_closure = read(REPORT / "closure.json")
    for label, folder, closure in (("native", NATIVE, native_closure), ("selected_report", REPORT, report_closure)):
        check(f"{label}_closure_clean", closure["error"] is None
              and closure["source_hashes_before"] == closure["source_hashes_after"])
        check(f"{label}_raw_sealed", all((folder / name).is_file()
              and (folder / name).stat().st_size == meta["bytes"]
              and sha(folder / name) == meta["sha256"]
              for name, meta in closure["raw"].items()))
        check(f"{label}_invocation_sealed", sha(folder / "invocation.json") == closure["invocation_sha256"])
    check("native_source_pins", native_closure["source_hashes_before"]["input"] == SOURCE_SHA
          and native_closure["source_hashes_before"]["parent"] == PARENT_SHA)
    check("report_source_pins", report_closure["source_hashes_before"]["sxo"]
          == native_closure["raw"]["model.sxo"]["sha256"]
          and report_closure["source_hashes_before"]["settings"] == SETTINGS_SHA
          and report_closure["source_hashes_before"]["runner"] == sha(HERE / "probe_item_report_results_ssh.ps1"))
    steps = read(NATIVE / "steps.json")
    check("native_steps", len(steps) == 5 and all(step["exit_code"] == 0
          and step["gui_preserved"] and step["error"] is None for step in steps))
    roundtrip = read(NATIVE / "roundtrip-validation.json")
    check("authored_roundtrip", roundtrip["passed"] and len(roundtrip["populated_tables"]) == 22)
    run_log = (NATIVE / "run.log").read_text(encoding="utf-8-sig")
    check("conversion", "Input conversion completed. Errors: 0, Warnings: 1" in run_log)

    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    expected_events = (
        "Time: 4  item transfer task 0 (IN)  created",
        "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
        "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
        "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
    )
    check("physical_transfer_and_later_demand", all(event in log for event in expected_events)
          and log.count("item transfer task 0 (IN)  arrives with 1 items") == 1)

    report = read(REPORT / "item-report-raw.json")
    items = table(report, "ItemResults")
    check("item_result_grid", len(items) == 72 and all(
        row["IID"] == "TEACH-LRU-01" and row["STID"] == "DEPOT-01"
        and row["STINT"] == index / 2 and row["ETINT"] == (index + 1) / 2
        for index, row in enumerate(items)))
    check("nominal_increase_at_h4", all(row["STSZ"] == (1 if index < 8 else 2)
          for index, row in enumerate(items)))
    check("on_hand_increase_at_h4", all(row["STOHA"] == 1 for row in items[:8])
          and all(row["STOHA"] == 2 for row in items[8:20]))
    check("later_stock_is_separate", items[20]["STSZ"] == 2 and items[20]["STOHA"] == 1
          and items[20]["NDF"] == 1 and items[26]["STOHA"] < 2
          and all(row["STOHA"] == 2 for row in items[27:]))
    check("item_backorders_zero", all(row["NBO"] == 0 for row in items))
    total = table(report, "ItemResultsTotal")
    check("nominal_time_average", len(total) == 1
          and abs(total[0]["STSZ"] - (4 + 2 * 32) / 36) < 1e-6
          and total[0]["STOHA"] <= total[0]["STSZ"])
    check("selected_report_export", report_closure["exit_code"] == 0
          and "Export completed!" in (REPORT / "report-export.log").read_text(encoding="utf-8-sig"))

    result = {"schema": "simlox-i02-var01-in-author-validation/v1",
              "case_id": "I02.var01.IN", "source_sha256": SOURCE_SHA,
              "native_run": NATIVE.name, "selected_report_run": REPORT.name,
              "checks": checks, "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks), "check_count": len(checks),
              "claim": "One scheduled IN transfer increases DEPOT nominal and on-hand LRU stock from 1 to 2 at h4.",
              "limits": "One LRU, one station, one seed, TFDT=0; later demand and repair are distinct events."}
    output = HERE / "review" / "author-native-validation-2026-10-02.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
