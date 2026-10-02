"""Independent, read-only replay of the sealed I01.var03 station pair.

Uses only the Python standard library and raw source/run artifacts. Does not
import the case builder, roundtrip checker, or validator; does not run SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
RUNS = {
    "base": "i01-var03-station-base-v100-ssh-20261002-01",
    "depot": "i01-var03-station-depot-v100-ssh-20261002-01",
}
checks = 0
failures: list[str] = []


def check(condition: bool, description: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(description)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path, native: bool = False):
    source = path.read_text(encoding="utf-8-sig")
    if native:
        # Native SIMLOX JSON exports contain trailing commas.
        source = re.sub(r",\s*([}\]])", r"\1", source)
    return json.loads(source)


def tables(document: dict, root: str) -> dict:
    return {entry["name"]: entry for entry in document[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def named_rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-7
    return a == b


def source_checks(contract: dict) -> dict:
    parent = (CASE / contract["direct_parent"]["source"]).resolve()
    check(sha(parent) == contract["direct_parent"]["sha256"], "parent source SHA")
    donor = (CASE / contract["structural_donor"]["source"]).resolve()
    check(sha(donor) == contract["structural_donor"]["sha256"], "accepted E04 structural donor SHA")
    for name in RUNS:
        check(sha(CASE / f"{name}-input.json") == contract["sources_sha256"][name], f"{name} source SHA")
    check(sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "exact diff SHA")
    check(contract["publication_state"] == "not_published", "frozen candidate status")
    left, right = [parse(CASE / f"{name}-input.json") for name in RUNS]
    lt, rt = tables(left, "model"), tables(right, "model")
    check(set(lt) == set(rt), "pair table sets")
    changed = {name for name in lt if lt[name] != rt[name]}
    check(changed == {"Control", "ProblemDescription"}, "pair changes only Control and description")
    for name in set(lt) - changed:
        check(lt[name] == rt[name], f"same pair source table {name}")
    original = tables(parse(parent), "model")
    check(set(lt) - set(original) == {"TaskCategory", "TaskLevel", "MaintenanceAllocation"},
          "exact new business tables versus accepted parent")
    check({n for n in original if n in lt and lt[n] != original[n]} ==
          {"ProblemDescription", "Station", "StationStructure", "ItemRepair", "Tasks", "StockAllocation"},
          "exact changed parent tables")
    for table in set(original) - {"ProblemDescription", "Station", "StationStructure", "ItemRepair", "Tasks", "StockAllocation"}:
        check(original[table] == lt[table], f"unchanged parent table {table}")
    lc, rc = named_rows(lt["Control"])[0], named_rows(rt["Control"])[0]
    check({key for key in lc if lc[key] != rc[key]} == {"APID"}, "APID sole Control delta")
    check((lc["APID"], rc["APID"]) == ("AIR_BASIC", "AIR_DEPOT"), "APID selected points")
    donor_tables = tables(parse(donor), "model")
    check(named_rows(lt["Station"])[1] == named_rows(donor_tables["Station"])[1], "accepted DEPOT station row")
    check(lt["StationStructure"] == donor_tables["StationStructure"], "accepted two-hour FAST support row")
    ma = named_rows(lt["MaintenanceAllocation"])
    check({(r["POINT"], r["TCID"], r["TLID"], r["STID"]) for r in ma} == {
        ("AIR_BASIC", "LRU-CM", "BASE", "BASE-01"),
        ("AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01"),
    }, "maintenance POINT topology")
    stock = named_rows(lt["StockAllocation"])
    check({(r["POINT"], r["IID"], r["STID"], r["STSIZ"]) for r in stock} == {
        ("AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1),
        ("AIR_BASIC", "TEACH-LRU-01", "DEPOT-01", 0),
        ("AIR_DEPOT", "TEACH-LRU-01", "BASE-01", 1),
        ("AIR_DEPOT", "TEACH-LRU-01", "DEPOT-01", 0),
    }, "equal stock allocation at both POINTs")
    check(not rows(lt["ItemReorder"]), "no ItemReorder source rows")
    check(named_rows(lt["Tasks"])[-1]["TID"] == "I01-LRU-DIRP", "referenced item task")
    ir = named_rows(lt["ItemRepair"])
    check({(r["IID"],r["STID"],r["DIRPT"],r["DIRPF"],r["DIRPTID"]) for r in ir} == {
        ("TEACH-LRU-01", "BASE-01", 1, 1, "I01-LRU-DIRP"),
        ("TEACH-LRU-01", "DEPOT-01", 1, 1, "I01-LRU-DIRP"),
    }, "equal direct repair rows at both stations")
    return {"base": left, "depot": right}


def run_checks(name: str, source: dict, contract: dict) -> tuple[dict, str, str]:
    directory = CASE / "runs" / RUNS[name]
    invocation = parse(directory / "invocation.json")
    closure = parse(directory / "closure.json")
    steps = parse(directory / "steps.json")
    check(invocation["run_id"] == RUNS[name], f"{name} invocation ID")
    check(closure["run_id"] == RUNS[name], f"{name} closure ID")
    check(closure["invocation_sha256"] == sha(directory / "invocation.json"), f"{name} invocation seal")
    check(invocation["input_sha256"] == contract["sources_sha256"][name], f"{name} invoked source")
    check(invocation["parent_sha256"] == contract["direct_parent"]["sha256"], f"{name} invoked parent")
    check(invocation["contract_sha256"] == sha(CASE / "contract.json"), f"{name} contract seal")
    check(invocation["source_hashes_before"]["structural_donor"] == contract["structural_donor"]["sha256"],
          f"{name} structural donor seal")
    for key, pinned in (("manual", "manual_pdf"), ("dictionary", "table_dictionary"),
                        ("simlox_exe", "simlox_exe")):
        check(invocation["source_hashes_before"][key] == contract["installed_source_sha256"][pinned],
              f"{name} installed {key} pin")
    for key, filename in (("builder", "build.py"), ("checker", "check_roundtrip.py"),
                          ("runner_script", "run_native_ssh.ps1"), ("exact_diff", "exact-diff.json")):
        check(invocation["source_hashes_before"][key] == sha(CASE / filename), f"{name} {key} seal")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0,
          f"{name} SSH session zero")
    check(invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"],
          f"{name} SSH ancestry")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{name} mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          f"{name} GUI identity")
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"],
          f"{name} source stability")
    check(closure["error"] is None, f"{name} closure error")
    check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
          f"{name} five steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None,
              f"{name} {step['name']} exit/GUI")
    check(steps[2]["status"] == "calc_observed" and all(s["status"] == "completed" for s in steps[:2] + steps[3:]),
          f"{name} step statuses")
    check(len(closure["raw"]) == 12, f"{name} 12 raw seals")
    for filename, seal in sorted(closure["raw"].items()):
        path = directory / filename
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
              f"{name} raw {filename}")
    check(sha(directory / "input.json") == contract["sources_sha256"][name], f"{name} run input")
    check(parse(directory / "input.json") == source, f"{name} run source content")
    authored, exported = tables(source, "model"), tables(parse(directory / "roundtrip-raw.json", True), "model")
    populated = {table for table in authored if rows(authored[table])}
    check(len(populated) == 24, f"{name} 24 populated business tables")
    for table in sorted(populated):
        check(table in exported and [c["name"] for c in authored[table]["columns"]] ==
              [c["name"] for c in exported[table]["columns"]] and
              len(rows(authored[table])) == len(rows(exported[table])) and
              all(len(ar) == len(er) and all(same(a, b) for a, b in zip(ar, er))
                  for ar, er in zip(rows(authored[table]), rows(exported[table]))),
              f"{name} exact {table} roundtrip")
    run_log = (directory / "run.log").read_text(encoding="utf-8-sig")
    event_log = (directory / "model.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 1" in run_log,
          f"{name} converter zero errors")
    check("warning #108" in run_log and "notice #2034" in run_log, f"{name} converter notices")
    check("warning #241" not in run_log and "error #2038" not in run_log,
          f"{name} no incomplete repair or missing category")
    check((directory / "model.sxo").stat().st_size > 4, f"{name} valid SXO")
    report = tables(parse(directory / "report-raw.json", True), "report")
    check({"ResultSummary", "SystemResults", "StockTotalResults"} <= set(report), f"{name} report tables")
    summary = named_rows(report["ResultSummary"])[0]
    for key, expected in (("NREP", 1), ("RTIUP", 36), ("MTMF", 1), ("MSTF", 1),
                          ("MSUF", 2/3), ("STMF", 1)):
        check(abs(summary[key] - expected) < 1e-6, f"{name} summary {key}")
    system = named_rows(report["SystemResults"])
    stock = named_rows(report["StockTotalResults"])
    check(len(system) == len(stock) == 72, f"{name} 72 half-hour bins")
    for index, (s, t) in enumerate(zip(system, stock)):
        hour = index / 2
        check(s["STINT"] == t["STINT"] == hour and s["ETINT"] == t["ETINT"] == hour + .5,
              f"{name} bin {index} times")
        allocated = int(any(start <= hour < end for start, end in ((7, 10), (19, 22), (31, 34))))
        flight = int(any(start <= hour < end for start, end in ((8, 10), (20, 22), (32, 34))))
        repair = int(hour == 10)
        for field, expected in (("NSYMA", allocated), ("NSYMO", flight), ("NSYRP", repair),
                                ("NSYUA", repair), ("NSYRY", 1-allocated-repair),
                                ("NFAIL", int(hour == 9.5)), ("NREPT", int(hour == 10.5))):
            check(s[field] == expected, f"{name} bin {index} {field}")
        for field, expected in (("NBO", 0), ("PNB", 1), ("NDF", repair), ("NWT", repair)):
            check(t[field] == expected, f"{name} bin {index} stock {field}")
    check(sum(row["NSYMO"] for row in system) * .5 == 6, f"{name} six flight hours")
    check(system[-1]["NSYRY"] == 1 and system[-1]["NSYUA"] == 0, f"{name} terminal ready")
    events = {
        "failure": "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added",
        "failed_id": "subitem failed: <TEACH-LRU-01,0,1>",
        "stock_init": "Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated",
        "spare_issue": "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "failed_arrives": "Time: 10.1667 <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>",
        "system_repair": "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed",
        "ready": "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
        "depot_stock_zero": "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:",
    }
    for label, phrase in events.items():
        check(phrase in event_log, f"{name} event {label}")
    for mission, hour in enumerate((8, 20, 32)):
        check(f"Time: {hour} <BASIC-MISSION,TEACH-UNIT,0,0,{mission}> mission starting, duration: 2 : <TEACH-AIR-01,0>" in event_log,
              f"{name} mission launch {hour}")
    for mission, hour in ((1, 22), (2, 34)):
        check(f"Time: {hour} <BASIC-MISSION,TEACH-UNIT,0,0,{mission}> mission success" in event_log,
              f"{name} mission success {hour}")
    check("Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in event_log,
          f"{name} first mission abort")
    check("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed" in event_log,
          f"{name} first mission completes")
    return report, event_log, run_log


def main() -> int:
    try:
        contract = parse(CASE / "contract.json")
        sources = source_checks(contract)
        results = {name: run_checks(name, sources[name], contract) for name in RUNS}
        base, depot = results["base"], results["depot"]
        for table in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check(base[0][table] == depot[0][table], f"pair aggregate report equality {table}")
        common = [
            "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added",
            "subitem failed: <TEACH-LRU-01,0,1>",
            "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
            "Time: 10.1667 <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>",
        ]
        for arm in ("base", "depot"):
            for phrase in common:
                check(phrase in results[arm][1], f"{arm} common physical item event {phrase}")
            ledger = results[arm][1]
            initial = ledger.find("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>")
            issued = ledger.find("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock")
            depleted = ledger.find("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:", issued)
            returned = ledger.find("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>")
            check(0 <= initial < issued < depleted < returned,
                  f"{arm} physical IDs and base stock 1-to-0-to-1 ledger")
            check("Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:" not in ledger,
                  f"{arm} depot does not retain the repaired spare")
        base_events = [
            "Time: 10.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> started",
            "Time: 11.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> completed",
            "Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock",
            "Level: 1 Items:<TEACH-LRU-01,0,1>",
        ]
        positions = [base[1].find(phrase) for phrase in base_events]
        check(all(p >= 0 for p in positions) and positions == sorted(positions),
              "base local item repair and stock return ordered")
        check("transport task 0 starts" not in base[1], "base no outward item transport")
        depot_events = [
            "Time: 10.1667  transport task 0 created from <BASE-01,0> to <DEPOT-01,0>",
            "Time: 10.1667  transport task 0 starts with 1 items/systems, transport time: 2",
            "Time: 12.1667  transport task 0 arrives with 1 items/systems",
            "Time: 12.1667 <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>",
            "Time: 12.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> started",
            "Time: 13.1667  item DIRP task 1 on <TEACH-LRU-01,0,1> completed",
            "Time: 13.1667  transport task 2 created from <DEPOT-01,0> to <BASE-01,0>",
            "Time: 13.1667  transport task 2 starts with 1 items/systems, transport time: 2",
            "Time: 15.1667  transport task 2 arrives with 1 items/systems",
            "Time: 15.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock",
            "Level: 1 Items:<TEACH-LRU-01,0,1>",
        ]
        positions = [depot[1].find(phrase) for phrase in depot_events]
        check(all(p >= 0 for p in positions) and positions == sorted(positions),
              "depot physical ID1 outward transport, repair, return and restock ordered")
        check("Time: 10.1667  item DIRP task 1" not in depot[1], "depot no base item repair")
        check(all("reorder" not in results[arm][1].lower() for arm in RUNS), "no reorder events")
    except Exception as exc:
        failures.append(f"replay exception: {type(exc).__name__}: {exc}")
    passed = not failures
    output = {
        "schema": "i01-var03-station-independent-review/v1",
        "case": CASE.name,
        "passed": passed,
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "verdict": "GO_BOUNDED_MAINTENANCE_STATION_APID_SELECTION" if passed else "NO_GO_REPLAY_FAILURE",
        "accepted_observation": "With complete LRU-CM/BASE MaintenanceAllocation rows at both APIDs and equal stock, AIR_BASIC repairs failed LRU ID1 at BASE-01 h10.1667-11.1667; AIR_DEPOT moves the same item two hours to DEPOT-01, repairs h12.1667-13.1667, returns two hours and restocks BASE-01 h15.1667. Both aircraft remain ready and aggregate reports match.",
        "excluded_claims": ["positive category or level filtering", "simultaneous three-allocation APID selection", "<NONE> reorder", "generic station routing"],
        "limits": "The selected station changes the downstream transport and stock timing as a coupled result; neither mechanism is isolated separately. One LRU, two WS stations, one seed, one installation. GUI visual and cross-engine parity unverified.",
        "runs": {name: {"run_id": run_id,
                        "closure_sha256": sha(CASE / "runs" / run_id / "closure.json"),
                        "report_sha256": sha(CASE / "runs" / run_id / "report-raw.json")}
                 for name, run_id in RUNS.items()},
    }
    OUT.write_bytes((json.dumps(output, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "checks_passed": output["checks_passed"],
                      "checks_total": checks, "failures": failures, "verdict": output["verdict"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
