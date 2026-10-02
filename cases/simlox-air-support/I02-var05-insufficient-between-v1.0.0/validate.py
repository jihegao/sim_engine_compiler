"""Replay the bounded I02.var05 shortage evidence without invoking SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
NATIVE = RUNS / "i02-var05-qty3-v100-ssh-20261002-01"
DEPOT = RUNS / "i02-var05-depot-results-v100-ssh-20261002-01"
BASE = RUNS / "i02-var05-base-results-v100-ssh-20261002-01"
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0"
SOURCE_SHA = "1f31540862de0f586eeacea5907be7f9fa238ae54ba4657f7211c1b64f58f1a3"
PARENT_SHA = "4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560"
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
    diff = read(HERE / "exact-diff.json")
    check("source_parent_diff_pins", sha(HERE / "native-input.json") == SOURCE_SHA
          and sha(PARENT / "native-input.json") == PARENT_SHA
          and contract["source_sha256"] == SOURCE_SHA
          and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
          and diff["parent_sha256"] == PARENT_SHA and diff["child_sha256"] == SOURCE_SHA)
    check("only_quantity_and_description", set(diff["changed_tables"]) == {"ItemTransfer", "ProblemDescription"}
          and diff["unchanged_table_count"] == 30
          and diff["changed_tables"]["ItemTransfer"]["before"]["instances"][0]["rows"][1] ==
          ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None]
          and diff["changed_tables"]["ItemTransfer"]["after"]["instances"][0]["rows"][1] ==
          ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 3, 0.0, None])

    closures = {name: read(folder / "closure.json") for name, folder in
                (("native", NATIVE), ("depot", DEPOT), ("base", BASE))}
    for name, folder, count in (("native", NATIVE, 12), ("depot", DEPOT, 2), ("base", BASE, 2)):
        c = closures[name]
        check(f"{name}_closure", c["error"] is None and c["run_id"] == folder.name
              and c["source_hashes_before"] == c["source_hashes_after"]
              and c["invocation_sha256"] == sha(folder / "invocation.json"))
        check(f"{name}_raw_seals", len(c["raw"]) == count and all(
              (folder / filename).stat().st_size == seal["bytes"]
              and sha(folder / filename) == seal["sha256"]
              for filename, seal in c["raw"].items()))
    native = closures["native"]
    check("native_source_pins", native["source_hashes_before"]["input"] == SOURCE_SHA
          and native["source_hashes_before"]["parent"] == PARENT_SHA
          and native["source_hashes_before"]["contract"] == sha(HERE / "contract.json"))
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
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
        "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder added",
        "Item transfer backorders at: <TEACH-LRU-01,0,DEPOT-01,0> Nbr: 1",
        "Time: 6  item transfer task 1 (BETWEEN)  starts with 2 items, transfer time: 0",
        "Time: 6  item transfer task 1 (BETWEEN)  arrives with 2 items",
        "Time: 6 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "Time: 6 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder removed",
        "Time: 13.1667  item transfer task 2 (BETWEEN)  starts with 1 items, transfer time: 0",
        "Time: 13.1667  item transfer task 2 (BETWEEN)  arrives with 1 items",
        "Time: 13.1667 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,2>",
    )
    check("split_and_later_completion", all(event in log for event in events)
          and log.count("Item transfer backorder added") == 1
          and log.count("Item transfer backorder removed") == 1
          and log.count("item transfer task 2 (BETWEEN)  arrives with 1 items") == 1)
    check("physical_stock_identity", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:" in log
          and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>" in log
          and "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>" in log)
    check("transfer_precedes_ordinary_backorder", log.index("Item transfer backorder added") <
          log.index("Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added") <
          log.index("Item transfer backorder removed") <
          log.index("item transfer task 2 (BETWEEN)  arrives with 1 items")
          and "Backorders at: <TEACH-LRU-01,0,DEPOT-01,0> Nbr: 1" in
          log[log.index("Item transfer backorder removed"):])

    rows: dict[str, list[dict]] = {}
    reports: dict[str, dict] = {}
    for station, folder, selector, runner in (
        ("DEPOT-01", DEPOT, "item-position-results.sxs", "probe_depot_report_ssh.ps1"),
        ("BASE-01", BASE, "base-item-position-results.sxs", "probe_base_report_ssh.ps1")):
        c = closures["depot" if station == "DEPOT-01" else "base"]
        check(f"{station}_source_selector", c["source_hashes_before"]["sxo"] ==
              native["raw"]["model.sxo"]["sha256"]
              and c["source_hashes_before"]["settings"] == SXS[station]
              and c["source_hashes_before"]["runner"] == sha(HERE / runner)
              and sha(RUNS / "report-settings" / selector) == SXS[station])
        check(f"{station}_export", c["exit_code"] == 0 and "Export completed!" in
              (folder / "report-export.log").read_text(encoding="utf-8-sig"))
        report = read(folder / "item-report-raw.json")
        reports[station] = {t["name"]: t for t in report["report"]["tables"]}
        rows[station] = table(report, "ItemResults")
        check(f"{station}_grid", len(rows[station]) == 72 and all(
              row["IID"] == "TEACH-LRU-01" and row["STID"] == station
              and row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2
              for i, row in enumerate(rows[station])))
    depot, base = rows["DEPOT-01"], rows["BASE-01"]
    check("depot_nominal_on_hand", all(row["STSZ"] == row["STOHA"] ==
          (1 if i < 8 else 2 if i < 12 else 0) for i, row in enumerate(depot)))
    check("base_nominal_full_request_at_h6", all(row["STSZ"] == (0 if i < 12 else 3)
          for i, row in enumerate(base)))
    check("base_on_hand_partial_then_final", all(
          (abs(row["STOHA"] - (0 if i < 12 else 2 if i < 20 else 1 if i < 26
                                else 5/3 if i == 26 else 2)) < 1e-5)
          for i, row in enumerate(base)))
    check("nominal_not_conserved_during_shortage", all(
          depot[i]["STSZ"] + base[i]["STSZ"] == (1 if i < 8 else 2 if i < 12 else 3)
          for i in range(72)) and base[12]["STSZ"] - base[12]["STOHA"] == 1)
    check("ordinary_depot_backorder_persists", all(row["NBO"] == (0 if i < 20 else 1)
          for i, row in enumerate(depot)) and all(row["NBO"] == 0 for row in base))
    check("terminal_stock", depot[-1]["STSZ"] == depot[-1]["STOHA"] == 0
          and depot[-1]["NBO"] == 1 and base[-1]["STSZ"] == 3
          and base[-1]["STOHA"] == 2 and base[-1]["NBO"] == 0)

    for station, label in (("DEPOT-01", "depot"), ("BASE-01", "base")):
        path = PARENT / "runs" / f"i02-var03-{label}-results-v100-ssh-20261002-01" / "item-report-raw.json"
        control = {t["name"]: t for t in read(path)["report"]["tables"]}
        changed = {name for name in control if control[name] != reports[station][name]}
        check(f"{label}_report_diff_scope", changed ==
              {"ProblemDescription", "ItemResults", "ItemResultsTotal"})
    result = {"schema": "simlox-i02-var05-insufficient-between-author-validation/v1",
              "case_id": "I02.var05.insufficient", "source_sha256": SOURCE_SHA,
              "native_run": NATIVE.name, "depot_report_run": DEPOT.name, "base_report_run": BASE.name,
              "checks": checks, "passed": all(x["passed"] for x in checks),
              "passed_count": sum(x["passed"] for x in checks), "check_count": len(checks),
              "claim": "At h6 an available-two/request-three BETWEEN moves IDs0/1 and leaves transfer backorder1; repaired ID2 completes it at h13.1667 ahead of a waiting ordinary depot backorder. Base nominal STSZ rises to3 at h6 while on-hand is2.",
              "limits": "One IN-then-BETWEEN, zero transfer delay, one seed and source/target; zero-stock, general priority, nominal split timing, reorder/procurement, GUI and parity unverified."}
    output = HERE / "review/author-native-validation-2026-10-02.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
