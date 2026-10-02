"""Replay the bounded I02.var03 BETWEEN evidence without invoking SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
NATIVE = RUNS / "i02-var03-between-v100-ssh-20261002-01"
DEPOT = RUNS / "i02-var03-depot-results-v100-ssh-20261002-01"
BASE = RUNS / "i02-var03-base-results-v100-ssh-20261002-01"
SOURCE_SHA = "4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"
SXS = {"DEPOT-01": "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9",
       "BASE-01": "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"}


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
    check("source_parent_pins", sha(HERE / "native-input.json") == SOURCE_SHA
          and sha(parent) == PARENT_SHA and contract["source_sha256"] == SOURCE_SHA)
    check("exact_diff_pin", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    closures = {label: read(folder / "closure.json") for label, folder in
                (("native", NATIVE), ("depot", DEPOT), ("base", BASE))}
    for label, folder, count in (("native", NATIVE, 12), ("depot", DEPOT, 2), ("base", BASE, 2)):
        c = closures[label]
        check(f"{label}_closure", c["error"] is None and
              c["source_hashes_before"] == c["source_hashes_after"] and
              c["invocation_sha256"] == sha(folder / "invocation.json"))
        check(f"{label}_raw_seals", len(c["raw"]) == count and all(
            (folder / name).stat().st_size == meta["bytes"] and
            sha(folder / name) == meta["sha256"] for name, meta in c["raw"].items()))
    native = closures["native"]
    check("native_source_pins", native["source_hashes_before"]["input"] == SOURCE_SHA
          and native["source_hashes_before"]["parent"] == PARENT_SHA)
    steps = read(NATIVE / "steps.json")
    check("native_steps_gui", len(steps) == 5 and all(
          x["exit_code"] == 0 and x["gui_preserved"] and x["error"] is None for x in steps))
    roundtrip = read(NATIVE / "roundtrip-validation.json")
    check("authored_roundtrip", roundtrip["passed"] and len(roundtrip["populated_tables"]) == 22)
    check("conversion", "Input conversion completed. Errors: 0, Warnings: 1" in
          (NATIVE / "run.log").read_text(encoding="utf-8-sig"))

    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig")
    events = (
        "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
        "Time: 6  item transfer task 1 (BETWEEN)  created",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 6  item transfer task 1 (BETWEEN)  arrives with 1 items",
        "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>",
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
    )
    check("physical_transfer_and_demand", all(x in log for x in events) and
          log.count("item transfer task 1 (BETWEEN)  arrives with 1 items") == 1)
    check("physical_source_destination", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log
          and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log)

    rows: dict[str, list[dict]] = {}
    for station, folder, settings_file, runner in (
        ("DEPOT-01", DEPOT, "item-position-results.sxs", "probe_depot_report_ssh.ps1"),
        ("BASE-01", BASE, "base-item-position-results.sxs", "probe_base_report_ssh.ps1")):
        c = closures["depot" if station == "DEPOT-01" else "base"]
        check(f"{station}_source_selector", c["source_hashes_before"]["sxo"] ==
              native["raw"]["model.sxo"]["sha256"] and
              c["source_hashes_before"]["settings"] == SXS[station] and
              c["source_hashes_before"]["runner"] == sha(HERE / runner) and
              sha(RUNS / "report-settings" / settings_file) == SXS[station])
        check(f"{station}_export", c["exit_code"] == 0 and "Export completed!" in
              (folder / "report-export.log").read_text(encoding="utf-8-sig"))
        report = read(folder / "item-report-raw.json")
        rows[station] = table(report, "ItemResults")
        check(f"{station}_grid", len(rows[station]) == 72 and all(
            row["IID"] == "TEACH-LRU-01" and row["STID"] == station and
            row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2
            for i, row in enumerate(rows[station])))
    depot, base = rows["DEPOT-01"], rows["BASE-01"]
    check("depot_nominal", all(row["STSZ"] == (2 if 8 <= i < 12 else 1)
          for i, row in enumerate(depot)))
    check("base_nominal", all(row["STSZ"] == (0 if i < 12 else 1)
          for i, row in enumerate(base)))
    check("nominal_two_station_conservation", all(
          depot[i]["STSZ"] + base[i]["STSZ"] == (1 if i < 8 else 2)
          for i in range(72)))
    check("transfer_on_hand", all(depot[i]["STOHA"] == (2 if 8 <= i < 12 else 1)
          and base[i]["STOHA"] == (0 if i < 12 else 1) for i in range(20)))
    check("later_demand_on_hand", all(depot[i]["STOHA"] == 0 for i in range(20, 26))
          and all(base[i]["STOHA"] == 0 for i in range(20, 24))
          and all(base[i]["STOHA"] == 1 for i in range(24, 72))
          and all(depot[i]["STOHA"] == 1 for i in range(27, 72)))
    check("depot_repair_fraction", abs(depot[26]["STOHA"] - 2/3) < 1e-5)
    check("position_backorders_zero", all(row["NBO"] == 0 for row in depot + base))
    check("terminal_stock", depot[-1]["STSZ"] == depot[-1]["STOHA"] == 1
          and base[-1]["STSZ"] == base[-1]["STOHA"] == 1)
    result = {"schema": "simlox-i02-var03-between-author-validation/v1",
              "case_id": "I02.var03.BETWEEN", "source_sha256": SOURCE_SHA,
              "native_run": NATIVE.name, "depot_report_run": DEPOT.name, "base_report_run": BASE.name,
              "checks": checks, "passed": all(x["passed"] for x in checks),
              "passed_count": sum(x["passed"] for x in checks), "check_count": len(checks),
              "claim": "After h4 IN, h6 BETWEEN moves one LRU depot to base; nominal depot/base stock 2/0 becomes 1/1.",
              "limits": "Zero-delay available-stock move, one LRU/two stations/seed; later demand and repair distinct."}
    output = HERE / "review/author-native-validation-2026-10-02.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
