"""Independent read-only D02.var01 replay against the accepted D01 control.

Uses Python's standard library, reads frozen source and sealed CLI artifacts,
and does not import author code or execute SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "D01-installed-lru-direct-repair-v1.0.0"
PARENT_INPUT = PARENT_CASE / "native-input.json"
PARENT_RUN = PARENT_CASE / "runs/d01-lru-v100-ssh-20260929-01"
RUN_ID = "d02-var01-traditional-op-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUTPUT = CASE / "review/independent-traditional-2026-09-30.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
CHILD_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def data(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(document, key="model"):
    return {table["name"]: table for table in document[key]["tables"]}


def rows(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for part in table["instances"] for row in part["rows"]]


def times(log, expression):
    return [float(m.group(1)) for m in re.finditer(expression, log, re.M)]


def main():
    checks = []

    def check(name, actual, expected, tol=None):
        passed = actual == expected if tol is None else abs(actual - expected) <= tol
        checks.append({"name": name, "passed": passed, "actual": actual, "expected": expected})

    child = data(CASE / "native-input.json")
    parent = data(PARENT_INPUT)
    contract = data(CASE / "contract.json")
    delta = data(CASE / "parent-diff.json")
    invocation = data(RUN / "invocation.json")
    closure = data(RUN / "closure.json")
    parent_invocation = data(PARENT_RUN / "invocation.json")
    parent_closure = data(PARENT_RUN / "closure.json")
    steps = data(RUN / "steps.json")
    export = data(RUN / "roundtrip-raw.json", native=True)
    report = data(RUN / "report-raw.json", native=True)
    parent_report = data(PARENT_RUN / "report-raw.json", native=True)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")

    check("accepted D01 parent SHA", sha(PARENT_INPUT), PARENT_SHA)
    check("frozen child SHA", sha(CASE / "native-input.json"), CHILD_SHA)
    check("contract source binding", [contract["parent"]["input_sha256"], contract["native_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("diff source binding", [delta["parent_input_sha256"], delta["child_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("copied run input byte equality", sha(RUN / "input.json"), CHILD_SHA)
    check("child invocation source identity", [invocation["input_sha256"], invocation["parent_sha256"]], [CHILD_SHA, PARENT_SHA])
    check("parent invocation input identity", parent_invocation["input_sha256"], PARENT_SHA)
    check("child run id", [invocation["run_id"], closure["run_id"]], [RUN_ID, RUN_ID])
    check("child closure invocation binding", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("parent closure invocation binding", parent_closure["invocation_sha256"], sha(PARENT_RUN / "invocation.json"))
    check("child source fingerprints stable", closure["source_hashes_before"], closure["source_hashes_after"])
    check("child invocation/closure fingerprint identity", invocation["source_hashes_before"], closure["source_hashes_before"])
    check("parent source fingerprints stable", parent_closure["source_hashes_before"], parent_closure["source_hashes_after"])
    for key, path in {"input": CASE / "native-input.json", "parent": PARENT_INPUT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}.items():
        check(f"child sealed local {key}", sha(path), closure["source_hashes_before"][key])
    for label, folder, seal in [("child", RUN, closure), ("parent", PARENT_RUN, parent_closure)]:
        check(f"{label} closure has no error", seal["error"], None)
        check(f"{label} has twelve raw hashes", len(seal["raw"]), 12)
        for name, claim in sorted(seal["raw"].items()):
            path = folder / name
            check(f"{label} raw {name}", [path.stat().st_size, sha(path)], [claim["bytes"], claim["sha256"]])
    check("session-0 SSH, GUI and host mutex", [invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"], invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]],
          ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
    check("native and checker steps", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
    check("steps all zero and GUI guarded", all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps), True)
    check("native import/export markers", ["Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"),
                                           "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig")], [True, True])
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    check("conversion errors/warnings/notes", conversion.groups() if conversion else None, ("0", "1", "0"))
    check("only event-log warning #108", re.findall(r"warning #(\d+)", run_log), ["108"])

    pt, ct, et = tables(parent), tables(child), tables(export)
    changed = sorted(name for name in pt if pt[name] != ct.get(name))
    check("same parent/child table set", sorted(pt), sorted(ct))
    check("only schedule/horizon/description tables change", changed,
          ["Control", "OperationProfile", "ProblemDescription", "ResultCollection"])
    check("diff changed-table set", sorted(delta["changed_tables_only"]), changed)
    check("27 unchanged tables", len(pt) - len(changed), 27)
    check("diff changed tables exact", all(delta["changed_tables"][name] == {"parent": pt[name], "child": ct[name]} for name in changed), True)
    check("no added tables", delta["added_tables_only"], [])
    control_p, control_c = rows(pt["Control"])[0], rows(ct["Control"])[0]
    check("only Control SIMPE and RCEND change", sorted(key for key in control_p if control_p[key] != control_c[key]), ["RCEND", "SIMPE"])
    check("Control horizon 36 to 60", [control_p["SIMPE"], control_p["RCEND"], control_c["SIMPE"], control_c["RCEND"]], [36.0, 36.0, 60.0, 60.0])
    schedule_p, schedule_c = rows(pt["OperationProfile"]), rows(ct["OperationProfile"])
    check("only third mission STIM changes", [r["STIM"] for r in schedule_p], [8.0, 20.0, 32.0])
    check("child mission STIM", [r["STIM"] for r in schedule_c], [8.0, 20.0, 52.0])
    check("schedule other fields unchanged", [[{key: value for key, value in row.items() if key != "STIM"} for row in s] for s in (schedule_p, schedule_c)],
          [[{key: value for key, value in row.items() if key != "STIM"} for row in schedule_p]] * 2)
    collection_p, collection_c = rows(pt["ResultCollection"]), rows(ct["ResultCollection"])
    check("only collection RCEND changes", [[{key: value for key, value in row.items() if key != "RCEND"} for row in s] for s in (collection_p, collection_c)],
          [[{key: value for key, value in row.items() if key != "RCEND"} for row in collection_p]] * 2)
    check("collection horizon 36 to 60", [[r["RCEND"] for r in s] for s in (collection_p, collection_c)], [[36.0, 36.0], [60.0, 60.0]])
    check("traditional system and item clocks unchanged", [rows(ct["System"])[0]["OPID"], rows(ct["Item"])[0]["OPID"]], ["OPHOURS", "OPHOURS"])
    check("traditional FRT values unchanged", [rows(ct["System"])[0]["FRT"], rows(ct["Item"])[0]["FRT"]], [300000, 300000])
    populated = [name for name, table in ct.items() if any(part["rows"] for part in table["instances"])]
    check("18 row-containing source tables", len(populated), 18)
    check("source rows roundtrip exactly", all(ct[name] == et.get(name) for name in populated), True)
    check("no source table missing from export", sorted(ct.keys() - et.keys()), [])

    fail_expression = r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical random failure added, now"
    failures = times(log, fail_expression)
    parent_failures = times(parent_log, fail_expression)
    check("child one traditional random failure", failures, [9.8829])
    check("parent original failure", parent_failures, [9.8829])
    check("no child failure in 22-52 no-flight gap", [t for t in failures if 22 <= t < 52], [])
    check("child mission starts", times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission starting, duration: 2"), [8.0, 20.0, 52.0])
    check("first mission abort", times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission aborted:"), [9.8829])
    check("second and third missions succeed", times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission success:"), [22.0, 54.0])
    check("failed installed item identity", log.count("subitem failed: <TEACH-LRU-01,0,1>"), 2)
    check("opening spare item zero", "Stock initiated" in log and "Level: 1 Items:<TEACH-LRU-01,0,0>" in log, True)
    check("demand of failed item one", times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,0,1>"), [10.0])
    check("spare zero issued", times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock"), [10.0])
    check("replacement subitem received", times(log, r"^Time: ([0-9.]+)  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>"), [10.0])
    check("remove/fit perform", times(log, r"^Time: ([0-9.]+)  remove subitem subtask[^\n]* starts performing") + times(log, r"^Time: ([0-9.]+)  fit subitem subtask[^\n]* starts performing"), [10.0, 10.25])
    check("system SURP completes and ready", [times(log, r"^Time: ([0-9.]+)  system SURP task 0 on <TEACH-AIR-01,0> completed"),
                                              times(log, r"^Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> Maintained system arrives")], [[10.5], [10.5]])
    check("removed item one enters local DIRP", times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,1>"), [10.25])
    check("item one repaired and restocked", [times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,1>"),
                                                  times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock")], [[11.25], [11.25]])
    check("stock stays replenished in gap after repair", "Level: 1 Items:<TEACH-LRU-01,0,1>" in log, True)
    check("no further replacement or item DIRP", log.count("Take replacement item") == 1 and log.count("Start repair of item") == 1, True)

    child_report = tables(report, "report")
    parent_report_tables = tables(parent_report, "report")
    system = rows(child_report["SystemResults"])
    stock = rows(child_report["StockTotalResults"])
    parent_system = rows(parent_report_tables["SystemResults"])
    check("120 child system and stock half-hour bins", [len(system), len(stock)], [120, 120])
    check("72 parent system half-hour bins", len(parent_system), 72)
    for name, ledger in [("system", system), ("stock", stock)]:
        check(f"{name} bins exactly 0-60", [(r["STINT"], r["ETINT"]) for r in ledger], [(i / 2, (i + 1) / 2) for i in range(120)])
    check("report child failure/repair totals", [sum(r["NFAIL"] for r in system), sum(r["NREPT"] for r in system)], [1, 1])
    check("report parent failure/repair totals", [sum(r["NFAIL"] for r in parent_system), sum(r["NREPT"] for r in parent_system)], [1, 1])
    check("child failure/repair report bins", [[r["STINT"] for r in system if r["NFAIL"]], [r["STINT"] for r in system if r["NREPT"]]], [[9.5], [10.5]])
    check("no report failure during 22-52", all(r["NFAIL"] == 0 for r in system if 22 <= r["STINT"] < 52), True)
    check("aircraft ready through 22-51 idle report bins", all(r["NSYRY"] == 1 and r["NSYRP"] == 0 for r in system if 22 <= r["STINT"] < 51), True)
    check("stock report one issue and no backorders", [sum(r["NDF"] for r in stock), sum(r["NWT"] for r in stock), sum(r["NBO"] for r in stock)], [1, 1, 0])
    check("stock issue bin at hour 10", [r["STINT"] for r in stock if r["NDF"]], [10.0])
    check("no PM report activity", [sum(r["NPMT"] for r in system), sum(r["NPMS"] for r in system)], [0, 0])
    check("one ready aircraft at 60", [system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYUA"]], [1, 0, 0])
    summary = rows(child_report["ResultSummary"])[0]
    check("one repetition, 60-hour report horizon", [summary["NREP"], summary["RTILW"], summary["RTIUP"]], [1, 0, 60])

    result = {
        "schema": "simlox-d02-var01-independent-traditional-readonly/v1",
        "reviewer": "independent standard-library read-only replay; no author imports or native process",
        "case_id": "D02", "variant_id": "D02.var01", "run_id": RUN_ID,
        "parent_run_id": PARENT_RUN.name,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks,
        "hashes": {"child_input": sha(CASE / "native-input.json"), "parent_input": sha(PARENT_INPUT),
                   "child_invocation": sha(RUN / "invocation.json"), "child_closure": sha(RUN / "closure.json"),
                   "child_model_log": sha(RUN / "model.log"), "child_report_raw": sha(RUN / "report-raw.json"),
                   "parent_model_log": sha(PARENT_RUN / "model.log"), "parent_report_raw": sha(PARENT_RUN / "report-raw.json")},
        "observed": {"child_failure_hours": failures, "parent_failure_hours": parent_failures,
                     "no_flight_gap": [22, 52], "child_mission_success_hours": [22, 54],
                     "replacement_issue": {"hour": 10, "spare_instance": 0, "failed_instance": 1},
                     "failed_item_restock_hour": 11.25, "terminal_ready_aircraft": 1,
                     "conversion": {"errors": 0, "warnings": 1, "warning_codes": [108]}},
        "limits": [
            "One seed and one 30-hour no-flight interval support an observed absence of failures, not a general proof of the OPHOURS clock algorithm.",
            "Mission preparation starts at hour 51; the 22-52 interval has no flight, while the aircraft is ready in the 22-51 idle report bins.",
            "The third mission moves from 32 to 52 and the horizon from 36 to 60, so later stochastic outcomes need not match the D01 control.",
            "Traditional item CALHOURS/MISSIONS negative tests, zero exposure, other seeds, GUI visual behavior and cross-engine equivalence remain unverified.",
        ],
        "publication_state": "independent_review_only",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": [c for c in checks if not c["passed"]],
                      "output": str(OUTPUT)}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
