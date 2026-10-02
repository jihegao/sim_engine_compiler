"""Replay the bounded I02.var02 OUT evidence without invoking SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "runs/i02-var02-out-v100-ssh-20261002-01"
REPORT = HERE / "runs/i02-var02-item-results-v100-ssh-20261002-01"
SOURCE_SHA = "7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"
SETTINGS_SHA = "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(report: dict, name: str) -> list[dict]:
    matches = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    columns = [c["name"] for c in matches[0]["columns"]]
    return [dict(zip(columns, row, strict=True)) for instance in matches[0]["instances"]
            for row in instance["rows"]]


def main() -> None:
    checks: list[dict] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract = read(HERE / "contract.json")
    parent = HERE / "../I02-var01-in-transfer-v1.0.2/native-input.json"
    check("frozen_source_parent", sha(HERE / "native-input.json") == SOURCE_SHA
          and sha(parent) == PARENT_SHA and contract["source_sha256"] == SOURCE_SHA)
    check("frozen_diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("selected_report_settings", sha(HERE / "runs/report-settings/item-position-results.sxs") == SETTINGS_SHA)
    native = read(NATIVE / "closure.json")
    selected = read(REPORT / "closure.json")
    for label, folder, closure, count in (("native", NATIVE, native, 12),
                                          ("selected", REPORT, selected, 2)):
        check(f"{label}_closure", closure["error"] is None and
              closure["source_hashes_before"] == closure["source_hashes_after"] and
              sha(folder / "invocation.json") == closure["invocation_sha256"])
        check(f"{label}_raw_seals", len(closure["raw"]) == count and all(
              (folder / name).stat().st_size == meta["bytes"] and
              sha(folder / name) == meta["sha256"]
              for name, meta in closure["raw"].items()))
    check("native_source_pins", native["source_hashes_before"]["input"] == SOURCE_SHA
          and native["source_hashes_before"]["parent"] == PARENT_SHA)
    check("report_sxo_settings_pins", selected["source_hashes_before"]["sxo"] ==
          native["raw"]["model.sxo"]["sha256"] and
          selected["source_hashes_before"]["settings"] == SETTINGS_SHA and
          selected["source_hashes_before"]["runner"] == sha(HERE / "probe_item_report_results_ssh.ps1"))
    steps = read(NATIVE / "steps.json")
    check("native_steps_gui", len(steps) == 5 and all(
        x["exit_code"] == 0 and x["gui_preserved"] and x["error"] is None for x in steps))
    check("authored_roundtrip", read(NATIVE / "roundtrip-validation.json")["passed"] and
          len(read(NATIVE / "roundtrip-validation.json")["populated_tables"]) == 22)
    check("conversion", "Input conversion completed. Errors: 0, Warnings: 1" in
          (NATIVE / "run.log").read_text(encoding="utf-8-sig"))
    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    events = (
        "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
        "Time: 6  item transfer task 1 (OUT)  created",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer demand arrives from OUT-transfer",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 6  item transfer task 1 (OUT)  arrives with 1 items",
        "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
        "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
    )
    check("physical_transfer_ledger", all(x in log for x in events) and
          log.count("item transfer task 1 (OUT)  arrives with 1 items") == 1)
    report = read(REPORT / "item-report-raw.json")
    items = table(report, "ItemResults")
    check("item_grid", len(items) == 72 and all(
        row["IID"] == "TEACH-LRU-01" and row["STID"] == "DEPOT-01" and
        row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2
        for i, row in enumerate(items)))
    check("in_then_out_nominal", all(row["STSZ"] == (2 if 8 <= i < 12 else 1)
          for i, row in enumerate(items)))
    check("in_then_out_on_hand", all(row["STOHA"] == (2 if 8 <= i < 12 else 1)
          for i, row in enumerate(items[:20])))
    check("later_demand_separate", items[20]["STSZ"] == 1 and
          items[20]["STOHA"] == 0 and items[20]["NDF"] == 1 and
          all(row["STSZ"] == 1 for row in items[20:]) and
          all(row["STOHA"] == 1 for row in items[27:]))
    check("depot_backorders_zero", all(row["NBO"] == 0 for row in items))
    total = table(report, "ItemResultsTotal")
    check("nominal_average", len(total) == 1 and
          abs(total[0]["STSZ"] - (4 + 2 * 2 + 30) / 36) < 1e-6 and
          total[0]["STOHA"] <= total[0]["STSZ"])
    check("report_export", selected["exit_code"] == 0 and "Export completed!" in
          (REPORT / "report-export.log").read_text(encoding="utf-8-sig"))
    result = {"schema": "simlox-i02-var02-out-author-validation/v1",
              "case_id": "I02.var02.OUT", "source_sha256": SOURCE_SHA,
              "native_run": NATIVE.name, "selected_report_run": REPORT.name,
              "checks": checks, "passed": all(x["passed"] for x in checks),
              "passed_count": sum(x["passed"] for x in checks), "check_count": len(checks),
              "claim": "After h4 IN, one h6 OUT lowers depot STSZ and STOHA from 2 to 1.",
              "limits": "One LRU/depot/seed, TFDT0, available stock; later demand is distinct."}
    output = HERE / "review/author-native-validation-2026-10-02.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
