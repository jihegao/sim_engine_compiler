"""Independent, read-only replay of sealed I01.var07 negative pair.

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
    "matching": "i01-var07-matching-v100-ssh-20261002-01",
    "other": "i01-var07-other-v100-ssh-20261002-01",
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
    for name in RUNS:
        check(sha(CASE / f"{name}-input.json") == contract["sources_sha256"][name], f"{name} source SHA")
        old = CASE.parent / "I01-var03-maintenance-category-v1.0.0" / f"{name}-input.json"
        check(sha(old) == sha(CASE / f"{name}-input.json"), f"{name} disclosed old source byte reuse")
    check(sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "exact diff SHA")
    check(sha(CASE.parent / "I01-var03-maintenance-category-v1.0.0" / "exact-diff.json") ==
          sha(CASE / "exact-diff.json"), "old exact-diff byte reuse")
    for filename in ("build.py", "describe_diff.py"):
        check(sha(CASE.parent / "I01-var03-maintenance-category-v1.0.0" / filename) ==
              sha(CASE / filename), f"old {filename} byte reuse")
    check(contract["publication_state"] == "not_published", "frozen candidate status")
    left, right = [parse(CASE / f"{name}-input.json") for name in RUNS]
    lt, rt = tables(left, "model"), tables(right, "model")
    check(set(lt) == set(rt), "pair table sets")
    changed = {name for name in lt if lt[name] != rt[name]}
    check(changed == {"Control", "ProblemDescription"}, "pair changes only Control and description")
    for name in set(lt) - changed:
        check(lt[name] == rt[name], f"same pair source table {name}")
    lc, rc = named_rows(lt["Control"])[0], named_rows(rt["Control"])[0]
    check({key for key in lc if lc[key] != rc[key]} == {"APID"}, "APID sole Control delta")
    check((lc["APID"], rc["APID"]) == ("AIR_BASIC", "AIR_ALT"), "APID selected points")
    ma = named_rows(lt["MaintenanceAllocation"])
    check({(r["POINT"], r["TCID"], r["TLID"], r["STID"]) for r in ma} == {
        ("AIR_BASIC", "LRU-CM", "BASE", "BASE-01"),
        ("AIR_ALT", "ALT-CM", "BASE", "BASE-01"),
    }, "maintenance POINT topology")
    stock = named_rows(lt["StockAllocation"])
    check({(r["POINT"], r["IID"], r["STID"], r["STSIZ"]) for r in stock} == {
        ("AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1),
        ("AIR_ALT", "TEACH-LRU-01", "BASE-01", 1),
    }, "equal one-spare stock allocation")
    check(not rows(lt["ItemReorder"]), "no ItemReorder source rows")
    check(any(r["TID"] == "I01-LRU-DIRP" and r["TCID"] == "LRU-CM" for r in named_rows(lt["Tasks"])),
          "referenced LRU-CM item task")
    check(named_rows(lt["ItemRepair"])[0]["DIRPTID"] == "I01-LRU-DIRP", "item task reference")
    return {"matching": left, "other": right}


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
    check(invocation["source_hashes_before"]["contract"] == sha(CASE / "contract.json"),
          f"{name} fresh contract existed at invocation and closure")
    check(closure["error"] is None, f"{name} closure error")
    wanted_steps = (["import", "export", "calc", "jsonreport", "check_import_export"] if name == "matching"
                    else ["import", "export", "calc", "check_import_export"])
    check([step["name"] for step in steps] == wanted_steps, f"{name} expected steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None,
              f"{name} {step['name']} exit/GUI")
    check(steps[2]["status"] == "calc_observed" and all(s["status"] == "completed" for s in steps[:2] + steps[3:]),
          f"{name} step statuses")
    check(len(closure["raw"]) == (12 if name == "matching" else 9), f"{name} raw seal count")
    for filename, seal in sorted(closure["raw"].items()):
        path = directory / filename
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
              f"{name} raw {filename}")
    check(sha(directory / "input.json") == contract["sources_sha256"][name], f"{name} run input")
    check(parse(directory / "input.json") == source, f"{name} run source content")
    authored, exported = tables(source, "model"), tables(parse(directory / "roundtrip-raw.json", True), "model")
    populated = {table for table in authored if rows(authored[table])}
    check(len(populated) == 23, f"{name} 23 populated business tables")
    for table in sorted(populated):
        check(table in exported and [c["name"] for c in authored[table]["columns"]] ==
              [c["name"] for c in exported[table]["columns"]] and
              len(rows(authored[table])) == len(rows(exported[table])) and
              all(len(ar) == len(er) and all(same(a, b) for a, b in zip(ar, er))
                  for ar, er in zip(rows(authored[table]), rows(exported[table]))),
              f"{name} exact {table} roundtrip")
    run_log = (directory / "run.log").read_text(encoding="utf-8-sig")
    expected_errors = 0 if name == "matching" else 1
    check(f"Input conversion completed. Errors: {expected_errors}, Warnings: 1, Notes: 1" in run_log,
          f"{name} converter errors")
    check("warning #108" in run_log and "notice #2034" in run_log, f"{name} converter notices")
    check("warning #241" not in run_log, f"{name} no incomplete-repair warning")
    if name == "other":
        check("Form: TaskCategory\nrec 1: (error #2038) No maintenance allocation defined for task category: LRU-CM"
              in run_log.replace("\r\n", "\n"), "other exact TaskCategory #2038")
        check((directory / "model.sxo").stat().st_size == 4, "other four-byte invalid SXO")
        check(not (directory / "model.log").exists() and not (directory / "report-raw.json").exists(),
              "other no simulation event log or report")
        return None, None, run_log
    check("error #2038" not in run_log, "matching no TaskCategory error")
    check((directory / "model.sxo").stat().st_size > 4, f"{name} valid SXO")
    event_log = (directory / "model.log").read_text(encoding="utf-8-sig")
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
        matching, other = results["matching"], results["other"]
        prior = CASE.parent / "I01-var05-none-maintenance-v1.0.0" / "runs" / "i01-var05-matching-v100-ssh-20261002-01"
        check(sha(prior / "model.log") == sha(CASE / "runs" / RUNS["matching"] / "model.log"),
              "matching native events reproduce separately sealed positive control")
        check("item DIRP task 1" in matching[1], "matching item DIRP exists")
        check("Time: 11.1667  item DIRP task 1" in matching[1], "matching repair completion hour")
        check("Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in matching[1]
              and "Level: 1 Items:<TEACH-LRU-01,0,1>" in matching[1],
              "matching item stock return")
        check("reorder" not in matching[1].lower(), "matching no ItemReorder event")
        check(other[0] is None and other[1] is None, "other rejected before valid simulation")
    except Exception as exc:
        failures.append(f"replay exception: {type(exc).__name__}: {exc}")
    passed = not failures
    output = {
        "schema": "i01-var07-independent-negative-review/v1",
        "case": CASE.name,
        "passed": passed,
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "verdict": "GO_BOUNDED_NEGATIVE_TASKCATEGORY_2038_ONLY" if passed else "NO_GO_REPLAY_FAILURE",
        "accepted_observation": "Fresh AIR_BASIC matching control converts and reports, including the failed LRU ID1 direct repair and return. Fresh AIR_ALT selects only ALT-CM and has no selected LRU-CM maintenance allocation: native converter emits TaskCategory #2038, Errors:1, and a four-byte invalid SXO.",
        "excluded_claims": ["positive I01.var03 category/level/station filtering", "AIR_ALT simulation behavior", "generic missing POINT rule", "ItemReorder or procurement"],
        "limits": "The AIR_ALT arm never produced a valid simulation event log or report; calc exit code zero is not behavioral acceptance. Reused old I01.var03 source bytes do not promote its diagnostic runs. One item/category/POINT and one installation only.",
        "runs": {name: {"run_id": run_id,
                        "closure_sha256": sha(CASE / "runs" / run_id / "closure.json"),
                        "report_sha256": (sha(CASE / "runs" / run_id / "report-raw.json")
                                          if (CASE / "runs" / run_id / "report-raw.json").exists() else None)}
                 for name, run_id in RUNS.items()},
    }
    OUT.write_bytes((json.dumps(output, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "checks_passed": output["checks_passed"],
                      "checks_total": checks, "failures": failures, "verdict": output["verdict"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
