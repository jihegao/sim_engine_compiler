"""Replay the matched I02.var05 zero-source evidence without invoking SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0/native-input.json"
PARENT_SHA = "4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560"
CONTROL_SHA = "c7b4b0214bb9d5182711984d460eeff61cb31e06a0e62d019704f2723ca13c3e"
ZERO_SHA = "00cebb18be952522b1bbfd1885edc40f2c9b4da148d000cf5326309360cc6453"
SXS = {"depot": "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9",
       "base": "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b"}
NATIVE = {"control": RUNS / "i02-var05-zero-control-v100-ssh-20261002-01",
          "zero": RUNS / "i02-var05-zero-child-v100-ssh-20261002-01"}
REPORT = {(arm, station): RUNS / f"i02-var05-zero-{arm}-{station}-v100-ssh-20261002-01"
          for arm in NATIVE for station in SXS}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(report: dict, name: str) -> list[dict]:
    matches = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    cols = [c["name"] for c in matches[0]["columns"]]
    return [dict(zip(cols, row, strict=True)) for instance in matches[0]["instances"]
            for row in instance["rows"]]


def close(folder: Path, count: int) -> bool:
    c = read(folder / "closure.json")
    return (c["error"] is None and c["run_id"] == folder.name
            and c["source_hashes_before"] == c["source_hashes_after"]
            and c["invocation_sha256"] == sha(folder / "invocation.json")
            and len(c["raw"]) == count
            and all((folder / name).stat().st_size == seal["bytes"]
                    and sha(folder / name) == seal["sha256"]
                    for name, seal in c["raw"].items()))


def near(a: float, b: float) -> bool:
    return abs(a - b) < 1e-5


def main() -> None:
    checks: list[dict] = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract = read(HERE / "contract.json")
    diff = read(HERE / "exact-diff.json")
    check("source_pins", sha(PARENT) == PARENT_SHA
          and sha(HERE / "control-input.json") == CONTROL_SHA
          and sha(HERE / "native-input.json") == ZERO_SHA
          and contract["control_sha256"] == CONTROL_SHA
          and contract["source_sha256"] == ZERO_SHA
          and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    a, b = diff["accepted_parent_to_control"], diff["matched_control_to_child"]
    check("matched_exact_diffs", a["before_sha256"] == PARENT_SHA
          and a["after_sha256"] == b["before_sha256"] == CONTROL_SHA
          and b["after_sha256"] == ZERO_SHA
          and set(a["changed_tables"]) == {"ItemTransfer", "ProblemDescription"}
          and set(b["changed_tables"]) == {"StockAllocation", "ProblemDescription"}
          and a["unchanged_table_count"] == b["unchanged_table_count"] == 30
          and a["changed_tables"]["ItemTransfer"]["after"]["instances"][0]["rows"][1][3] == 2.0
          and b["changed_tables"]["StockAllocation"]["before"]["instances"][0]["rows"][1][3] == 1
          and b["changed_tables"]["StockAllocation"]["after"]["instances"][0]["rows"][1][3] == 0)

    closures = {}
    for arm, folder in NATIVE.items():
        closures[arm] = read(folder / "closure.json")
        check(f"{arm}_native_closure_12_seals", close(folder, 12))
        expected = CONTROL_SHA if arm == "control" else ZERO_SHA
        check(f"{arm}_native_pins", closures[arm]["source_hashes_before"]["input"] == expected
              and closures[arm]["source_hashes_before"]["parent"] == PARENT_SHA
              and closures[arm]["source_hashes_before"]["contract"] == sha(HERE / "contract.json"))
        steps = read(folder / "steps.json")
        check(f"{arm}_five_gui_steps", len(steps) == 5 and all(
              x["exit_code"] == 0 and x["gui_preserved"] and x["error"] is None for x in steps))
        rt = read(folder / "roundtrip-validation.json")
        check(f"{arm}_roundtrip_conversion", rt["passed"] and len(rt["populated_tables"]) == 22
              and "Input conversion completed. Errors: 0, Warnings: 1" in
              (folder / "run.log").read_text(encoding="utf-8-sig"))

    control_log = (NATIVE["control"] / "model.log").read_text(encoding="utf-8-sig")
    zero_log = (NATIVE["zero"] / "model.log").read_text(encoding="utf-8-sig")
    check("control_h2_available_transfer", all(x in control_log for x in (
          "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
          "Time: 2  item transfer task 0 (BETWEEN)  arrives with 1 items",
          "Time: 2 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
          "Time: 4  item transfer task 1 (IN)  arrives with 1 items",
          "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>"))
          and "Item transfer backorder added" not in control_log)
    check("zero_h2_backorder_h4_completion", all(x in zero_log for x in (
          "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder added",
          "Time: 2  item transfer task 0 (BETWEEN)  starts with 0 items",
          "Time: 2  item transfer task 0 (BETWEEN)  arrives with 0 items",
          "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
          "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder removed",
          "Time: 4  item transfer task 2 (BETWEEN)  arrives with 1 items",
          "Time: 4 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>"))
          and zero_log.count("Item transfer backorder added") == 1
          and zero_log.count("Item transfer backorder removed") == 1
          and "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item" not in zero_log)
    check("zero_later_ordinary_route", all(x in zero_log for x in (
          "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
          "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added",
          "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
          "Time: 15.1667 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>")))

    reports: dict[tuple[str, str], dict] = {}
    rows: dict[tuple[str, str], list[dict]] = {}
    for (arm, station), folder in REPORT.items():
        c = read(folder / "closure.json")
        check(f"{arm}_{station}_report_closure_2_seals", close(folder, 2))
        selector = "item-position-results.sxs" if station == "depot" else "base-item-position-results.sxs"
        runner = HERE / f"probe_{arm}_{station}_report_ssh.ps1"
        check(f"{arm}_{station}_report_source_selector", c["exit_code"] == 0
              and c["source_hashes_before"]["sxo"] == closures[arm]["raw"]["model.sxo"]["sha256"]
              and c["source_hashes_before"]["settings"] == SXS[station]
              and c["source_hashes_before"]["runner"] == sha(runner)
              and sha(RUNS / "report-settings" / selector) == SXS[station]
              and "Export completed!" in (folder / "report-export.log").read_text(encoding="utf-8-sig"))
        doc = read(folder / "item-report-raw.json")
        reports[(arm, station)] = {t["name"]: t for t in doc["report"]["tables"]}
        rows[(arm, station)] = table(doc, "ItemResults")
        stid = "DEPOT-01" if station == "depot" else "BASE-01"
        check(f"{arm}_{station}_72_bin_grid", len(rows[(arm, station)]) == 72 and all(
              x["IID"] == "TEACH-LRU-01" and x["STID"] == stid
              and x["STINT"] == i / 2 and x["ETINT"] == (i + 1) / 2
              for i, x in enumerate(rows[(arm, station)])))

    cd, cb = rows[("control", "depot")], rows[("control", "base")]
    zd, zb = rows[("zero", "depot")], rows[("zero", "base")]
    check("control_depot_nominal", all(x["STSZ"] == (1 if i < 4 or i >= 8 else 0)
          for i, x in enumerate(cd)))
    check("control_base_nominal_on_hand_h2", all(x["STSZ"] == (0 if i < 4 else 1)
          and (x["STOHA"] == 0 if i < 4 else True) for i, x in enumerate(cb))
          and all(cb[i]["STOHA"] == 1 for i in range(4, 20)))
    check("zero_depot_nominal_on_hand", all(x["STSZ"] == x["STOHA"] == 0 for x in zd))
    check("zero_base_nominal_before_physical", all(x["STSZ"] == (0 if i < 4 else 1)
          and (x["STOHA"] == 0 if i < 8 else True) for i, x in enumerate(zb))
          and all(zb[i]["STOHA"] == 1 for i in range(8, 20)))
    check("zero_depot_ordinary_backorder_resolves", all(near(x["NBO"],
          0 if i < 20 else 1 if i < 26 else 1/3 if i == 26 else 0)
          for i, x in enumerate(zd)) and all(x["NBO"] == 0 for x in zb))
    check("zero_base_later_on_hand", all(near(x["STOHA"],
          0 if i < 8 else 1 if i < 20 else 0 if i < 30 else 2/3 if i == 30 else 1)
          for i, x in enumerate(zb)))
    check("terminal_stations", cd[-1]["STSZ"] == cd[-1]["STOHA"] == 1
          and cb[-1]["STSZ"] == cb[-1]["STOHA"] == 1
          and zd[-1]["STSZ"] == zd[-1]["STOHA"] == 0
          and zb[-1]["STSZ"] == zb[-1]["STOHA"] == 1
          and all(x[-1]["NBO"] == 0 for x in (cd, cb, zd, zb)))
    for station in SXS:
        left, right = reports[("control", station)], reports[("zero", station)]
        check(f"{station}_selected_table_diff_scope", {k for k in left if left[k] != right[k]} ==
              {"ProblemDescription", "ItemResults", "ItemResultsTotal"})
    result = {"schema": "simlox-i02-var05-zero-source-author-validation/v1",
              "case_id": "I02.var05.zero-source", "control_sha256": CONTROL_SHA,
              "source_sha256": ZERO_SHA, "native_runs": {k: v.name for k, v in NATIVE.items()},
              "report_runs": {f"{a}_{s}": p.name for (a, s), p in REPORT.items()},
              "checks": checks, "passed": all(x["passed"] for x in checks),
              "passed_count": sum(x["passed"] for x in checks), "check_count": len(checks),
              "claim": "The zero-source h2 BETWEEN creates transfer backorder1 and moves no physical item; h4 IN item0 clears it and a second BETWEEN delivers to base. Target STSZ is already1 at h2 while STOHA0.",
              "limits": "One matched h2 request before h4 IN, one seed and item; no generic nominal timing, zero-stock quantity matrix, priority, reorder or GUI/parity claim."}
    output = HERE / "review/author-native-validation-2026-10-02.json"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
