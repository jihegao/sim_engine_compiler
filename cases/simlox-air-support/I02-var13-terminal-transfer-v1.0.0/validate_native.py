"""Source-bound author replay of the two I02.var13 native endpoint runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
ARMS = ("transit", "backorder")
STATIONS = ("depot", "base")
SELECTORS = {"depot": ("item-position-results.sxs", "2cc8e6c0ea3470ea33fe3fbd42fcaae4c6e5a36e33d645aef8b56f0fa21262d9"),
             "base": ("base-item-position-results.sxs", "10fe133a68250503041a18bfc6512b03326af9f073c294b9d954a4a3340f260b")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, name: str) -> list[dict]:
    found = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(found) == 1
    keys = [c["name"] for c in found[0]["columns"]]
    return [dict(zip(keys, row, strict=True)) for ins in found[0]["instances"] for row in ins["rows"]]


def sealed(folder: Path, count: int) -> bool:
    inv, closed = read(folder / "invocation.json"), read(folder / "closure.json")
    return (closed["error"] is None and closed["run_id"] == folder.name
            and closed["invocation_sha256"] == sha(folder / "invocation.json")
            and closed["source_hashes_before"] == closed["source_hashes_after"] == inv["source_hashes_before"]
            and len(closed["raw"]) == count
            and all((folder / name).stat().st_size == seal["bytes"]
                    and sha(folder / name) == seal["sha256"] for name, seal in closed["raw"].items()))


def main() -> None:
    checks: list[dict] = []

    def check(name: str, value: bool) -> None:
        checks.append({"name": name, "passed": bool(value)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    for station, (filename, expected) in SELECTORS.items():
        check(f"selector_{station}", sha(RUNS / "report-settings" / filename) == expected)
    logs, rows, reports = {}, {}, {}
    for arm in ARMS:
        cfg = contract["arms"][arm]
        parent = HERE.parent / cfg["accepted_parent"]
        check(f"parent_{arm}", sha(parent) == cfg["parent_sha256"] == diff[arm]["parent_sha256"])
        check(f"input_{arm}", sha(HERE / f"{arm}-input.json") == cfg["input_sha256"] == diff[arm]["input_sha256"])
        check(f"delta_{arm}", diff[arm]["changed_tables"] == ["Control", "OperationProfile", "ProblemDescription", "ResultCollection"]
              and diff[arm]["other_tables_identical"] == 28
              and diff[arm]["operation_profile_after"][0][2:5] == [0.0, "SCHEDULED", 0])
        folder = RUNS / f"i02-var13-{arm}-v100-ssh-20261002-01"
        check(f"native_seal_{arm}", sealed(folder, 12))
        inv, closed = read(folder / "invocation.json"), read(folder / "closure.json")
        check(f"native_source_{arm}", closed["source_hashes_before"]["input"] == cfg["input_sha256"]
              and closed["source_hashes_before"]["parent"] == cfg["parent_sha256"]
              and closed["source_hashes_before"]["runner_script"] == sha(HERE / "run_native_ssh.ps1")
              and closed["source_hashes_before"]["contract"] == sha(HERE / "contract.json"))
        check(f"native_guard_{arm}", inv["session_id"] == 0 and inv["gui"]["pid"] == 13340
              and "sshd.exe" in inv["ssh_ancestor_names"]
              and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        steps = read(folder / "steps.json")
        check(f"native_steps_{arm}", [s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"]
              and all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
        rt = read(folder / "roundtrip-validation.json")
        check(f"roundtrip_{arm}", rt["passed"] and rt["variant"] == arm and len(rt["populated_tables"]) == 22)
        check(f"conversion_{arm}", "Input conversion completed. Errors: 0," in
              (folder / "run.log").read_text(encoding="utf-8-sig"))
        logs[arm] = (folder / "model.log").read_text(encoding="utf-8-sig")
        check(f"no_mission_{arm}", "mission ordered" not in logs[arm].lower()
              and "mission started" not in logs[arm].lower())
        rows[arm], reports[arm] = {}, {}
        for station in STATIONS:
            target = RUNS / f"i02-var13-{arm}-{station}-item-v100-ssh-20261002-01"
            check(f"report_seal_{arm}_{station}", sealed(target, 2))
            ri, rc = read(target / "invocation.json"), read(target / "closure.json")
            check(f"report_pin_{arm}_{station}", ri["source_closure_sha256"] == sha(folder / "closure.json")
                  and rc["source_hashes_before"]["sxo"] == closed["raw"]["model.sxo"]["sha256"]
                  and rc["source_hashes_before"]["settings"] == SELECTORS[station][1]
                  and rc["source_hashes_before"]["runner"] == sha(HERE / "report_native_ssh.ps1")
                  and rc["exit_code"] == 0)
            reports[arm][station] = read(target / "item-report-raw.json")
            rows[arm][station] = table(reports[arm][station], "ItemResults")
            horizon = cfg["endpoint_hour"]
            check(f"grid_{arm}_{station}", len(rows[arm][station]) == horizon * 2
                  and all(r["IID"] == "TEACH-LRU-01"
                          and r["STID"] == ("DEPOT-01" if station == "depot" else "BASE-01")
                          and r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2
                          for i, r in enumerate(rows[arm][station])))
            check(f"summary_{arm}_{station}", table(reports[arm][station], "ResultSummary")[0]["RTIUP"] == horizon)

    transit, backorder = logs["transit"], logs["backorder"]
    check("transit_departure", "Time: 6  item transfer task 1 (BETWEEN)  starts with 1 items, transfer time: 2" in transit
          and "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in transit)
    check("transit_no_arrival", "item transfer task 1 (BETWEEN)  arrives" not in transit
          and "Time: 8" not in transit)
    check("transit_initial_and_in", "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated" in transit
          and "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in transit)
    td, tb = rows["transit"]["depot"], rows["transit"]["base"]
    check("transit_station_steps", all(td[i]["STSZ"] == td[i]["STOHA"] == (1 if i < 8 else 2 if i < 12 else 1)
          and tb[i]["STSZ"] == tb[i]["STOHA"] == 0 for i in range(14)))
    check("transit_terminal_conservation", td[-1]["STOHA"] == 1 and tb[-1]["STOHA"] == 0
          and 1 + 1 == td[-1]["STOHA"] + tb[-1]["STOHA"] + 1)
    check("transfer_backorder_log", "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder added" in backorder
          and "Nbr: 1 Backorders:" in backorder
          and "Time: 2  item transfer task 0 (BETWEEN)  arrives with 0 items" in backorder)
    check("backorder_no_future_in", "Time: 4" not in backorder and "Item transfer backorder removed" not in backorder)
    bd, bb = rows["backorder"]["depot"], rows["backorder"]["base"]
    check("backorder_station_steps", all(r["STSZ"] == r["STOHA"] == r["NBO"] == 0 for r in bd)
          and all(r["STSZ"] == (0 if i < 4 else 1) and r["STOHA"] == r["NBO"] == 0
                  for i, r in enumerate(bb)))
    check("transfer_bo_not_ordinary_nbo", bd[-1]["NBO"] == bb[-1]["NBO"] == 0
          and "Item transfer backorders at:" in backorder)
    check("aircraft_terminal_ready", all(table(reports[arm]["base"], "SystemResults")[-1]["NSYRY"] == 1
          for arm in ARMS))
    result = {"schema": "simlox-i02-var13-terminal-transfer-author-validation/v1",
              "case_id": "I02", "variant_id": "I02.var13", "checks": checks,
              "passed": all(c["passed"] for c in checks),
              "passed_count": sum(c["passed"] for c in checks), "check_count": len(checks),
              "claim": "At h7 one tracked item is in a h6-to-h8 BETWEEN task, absent from both station on-hand counts. At h3 a zero-source h2 transfer backorder remains in the native log, while BASE-01 nominal STSZ is 1 and ordinary NBO is 0.",
              "limits": "Two separate accepted parents, zero mission initiation, one IID/two stations/seed1, h7 and h3 only; no active-demand priority, GUI visual or cross-engine claim."}
    output = HERE / "author-validation.json"
    output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{result['passed_count']}/{result['check_count']} checks: {output}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
