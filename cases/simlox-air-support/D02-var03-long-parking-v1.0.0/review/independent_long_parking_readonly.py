"""Independent read-only D02.var03 replay against accepted D02.var01.

Standard library only; neither author validator nor SIMLOX is called.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "D02-var01-traditional-op-hours-v1.0.0"
PARENT_INPUT = PARENT_CASE / "native-input.json"
PARENT_RUN = PARENT_CASE / "runs/d02-var01-traditional-op-v100-ssh-20260930-01"
RUN_ID = "d02-var03-long-park-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUTPUT = CASE / "review/independent-long-parking-2026-09-30.json"
PARENT_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"
CHILD_SHA = "c1bd1294a126b199e16d55fd66ae084d382683416581b67772d7e82e532f6e24"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path, native=False):
    source = path.read_text(encoding="utf-8-sig")
    if native:
        source = re.sub(r",\s*([}\]])", r"\1", source)
    return json.loads(source)


def tables(document, key="model"):
    return {table["name"]: table for table in document[key]["tables"]}


def rows(table):
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row)) for part in table["instances"] for row in part["rows"]]


def event_times(log, pattern):
    return [float(match.group(1)) for match in re.finditer(pattern, log, re.M)]


def main():
    checks = []

    def check(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    parent, child = load(PARENT_INPUT), load(CASE / "native-input.json")
    contract, delta = load(CASE / "contract.json"), load(CASE / "parent-diff.json")
    invocation, closure, steps = (load(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    parent_invocation, parent_closure = (load(PARENT_RUN / name) for name in ("invocation.json", "closure.json"))
    export = load(RUN / "roundtrip-raw.json", native=True)
    report = load(RUN / "report-raw.json", native=True)
    parent_report = load(PARENT_RUN / "report-raw.json", native=True)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")

    check("accepted parent input SHA", sha(PARENT_INPUT), PARENT_SHA)
    check("frozen child input SHA", sha(CASE / "native-input.json"), CHILD_SHA)
    check("contract source binding", [contract["parent"]["input_sha256"], contract["native_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("diff source binding", [delta["parent_input_sha256"], delta["child_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("copied native input byte identity", sha(RUN / "input.json"), CHILD_SHA)
    check("child invocation input and parent", [invocation["input_sha256"], invocation["parent_sha256"]], [CHILD_SHA, PARENT_SHA])
    check("parent invocation input", parent_invocation["input_sha256"], PARENT_SHA)
    check("run identity", [invocation["run_id"], closure["run_id"]], [RUN_ID, RUN_ID])
    check("child closure invocation SHA", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("parent closure invocation SHA", parent_closure["invocation_sha256"], sha(PARENT_RUN / "invocation.json"))
    check("child fingerprints stable", closure["source_hashes_before"], closure["source_hashes_after"])
    check("invocation and closure fingerprints agree", invocation["source_hashes_before"], closure["source_hashes_before"])
    check("parent fingerprints stable", parent_closure["source_hashes_before"], parent_closure["source_hashes_after"])
    for key, path in {"input": CASE / "native-input.json", "parent": PARENT_INPUT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}.items():
        check(f"child sealed local {key}", sha(path), closure["source_hashes_before"][key])
    for label, folder, seal in (("child", RUN, closure), ("parent", PARENT_RUN, parent_closure)):
        check(f"{label} closure no error", seal["error"], None)
        check(f"{label} 12 raw artifacts", len(seal["raw"]), 12)
        for name, claim in sorted(seal["raw"].items()):
            path = folder / name
            check(f"{label} sealed raw {name}", [path.stat().st_size, sha(path)], [claim["bytes"], claim["sha256"]])
    check("guarded session-0 SSH", [invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"],
                                    invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]],
          ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
    check("five native/checker steps", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
    check("all steps exit zero and preserve GUI", all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps), True)
    check("native import/export completion markers", ["Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"),
                                                        "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig")], [True, True])
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    check("conversion error/warning/note counts", conversion.groups() if conversion else None, ("0", "1", "0"))
    check("only event-log warning #108", re.findall(r"warning #(\d+)", run_log), ["108"])

    pt, ct, et = tables(parent), tables(child), tables(export)
    changed = sorted(name for name in pt if pt[name] != ct.get(name))
    check("same table set", sorted(pt), sorted(ct))
    check("exact changed table names", changed, ["Control", "OperationProfile", "ProblemDescription", "ResultCollection"])
    check("diff changed table names", sorted(delta["changed_tables_only"]), changed)
    check("27 parent tables unchanged", len(pt) - len(changed), 27)
    check("diff has exact changed table objects", all(delta["changed_tables"][name] == {"parent": pt[name], "child": ct[name]} for name in changed), True)
    check("no added table", delta["added_tables_only"], [])
    control_p, control_c = rows(pt["Control"])[0], rows(ct["Control"])[0]
    check("Control only SIMPE and RCEND changed", sorted(key for key in control_p if control_p[key] != control_c[key]), ["RCEND", "SIMPE"])
    check("Control 60 to 160", [control_p["SIMPE"], control_p["RCEND"], control_c["SIMPE"], control_c["RCEND"]], [60.0, 60.0, 160.0, 160.0])
    schedule_p, schedule_c = rows(pt["OperationProfile"]), rows(ct["OperationProfile"])
    check("parent and child launch schedule", [[r["STIM"] for r in schedule_p], [r["STIM"] for r in schedule_c]], [[8.0, 20.0, 52.0], [8.0, 20.0, 152.0]])
    check("only third profile STIM changed", [[key for key in p if p[key] != c[key]] for p, c in zip(schedule_p, schedule_c)], [[], [], ["STIM"]])
    collection_p, collection_c = rows(pt["ResultCollection"]), rows(ct["ResultCollection"])
    check("only result RCEND changed", [[key for key in p if p[key] != c[key]] for p, c in zip(collection_p, collection_c)], [["RCEND"], ["RCEND"]])
    check("result RCEND 60 to 160", [[r["RCEND"] for r in collection_p], [r["RCEND"] for r in collection_c]], [[60.0, 60.0], [160.0, 160.0]])
    check("traditional System/Item OPHOURS FRT unchanged", [rows(ct[n])[0][key] for n in ("System", "Item") for key in ("OPID", "FRT")],
          ["OPHOURS", 300000, "OPHOURS", 300000])
    populated = [name for name, table in ct.items() if any(part["rows"] for part in table["instances"])]
    check("18 row-containing source tables", len(populated), 18)
    check("all row-containing tables roundtrip exactly", all(ct[name] == et.get(name) for name in populated), True)
    check("no source table missing from export", sorted(ct.keys() - et.keys()), [])

    failure_pattern = r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical random failure added, now"
    failures = event_times(log, failure_pattern)
    parent_failures = event_times(parent_log, failure_pattern)
    check("child and parent one 9.8829 failure", [failures, parent_failures], [[9.8829], [9.8829]])
    check("no failure in 22-152 no-flight gap", [time for time in failures if 22 <= time < 152], [])
    check("child first mission abort", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission aborted:"), [9.8829])
    check("child second and third successes", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission success:"), [22.0, 154.0])
    check("parent second and third successes", event_times(parent_log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission success:"), [22.0, 54.0])
    check("child launch hours", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission starting, duration: 2"), [8.0, 20.0, 152.0])
    check("third mission created and allocated at 151", [event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,2> mission created:"),
                                                          event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,2> mission allocates system:")], [[151.0], [151.0]])
    check("failed installed LRU #1", log.count("subitem failed: <TEACH-LRU-01,0,1>"), 2)
    check("spare #0 issued at 10", event_times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock"), [10.0])
    check("system replacement completes at 10.5", event_times(log, r"^Time: ([0-9.]+)  system SURP task 0 on <TEACH-AIR-01,0> completed"), [10.5])
    check("removed #1 repair/replenishment", [event_times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,1>"),
                                                 event_times(log, r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock")], [[10.25], [11.25]])
    check("no additional spare issue/repair", [log.count("Take replacement item"), log.count("Start repair of item")], [1, 1])

    rt, prt = tables(report, "report"), tables(parent_report, "report")
    system, stock = rows(rt["SystemResults"]), rows(rt["StockTotalResults"])
    parent_system = rows(prt["SystemResults"])
    check("one summary, 320 child system/stock bins", [len(rows(rt["ResultSummary"])), len(system), len(stock)], [1, 320, 320])
    check("120 parent system bins", len(parent_system), 120)
    for name, ledger in (("system", system), ("stock", stock)):
        check(f"{name} exact half-hour 0-160 bins", [(r["STINT"], r["ETINT"]) for r in ledger],
              [(i / 2, (i + 1) / 2) for i in range(320)])
    check("one failure and one repair in child and parent reports", [[sum(r["NFAIL"] for r in ledger), sum(r["NREPT"] for r in ledger)] for ledger in (system, parent_system)], [[1, 1], [1, 1]])
    check("child failure and repair bins", [[r["STINT"] for r in system if r["NFAIL"]], [r["STINT"] for r in system if r["NREPT"]]], [[9.5], [10.5]])
    check("no failure or mission operation in 22-152 report bins", all(r["NFAIL"] == 0 and r["NSYMO"] == 0 for r in system if 22 <= r["STINT"] < 152), True)
    check("ready and not in repair through 22-151 parked bins", all(r["NSYRY"] == 1 and r["NSYRP"] == 0 for r in system if 22 <= r["STINT"] < 151), True)
    check("one stock demand and zero backorder", [sum(r["NDF"] for r in stock), sum(r["NWT"] for r in stock), sum(r["NBO"] for r in stock)], [1, 1, 0])
    check("terminal one ready aircraft", [system[-1]["NSYRY"], system[-1]["NSYRP"]], [1, 0])
    check("one repetition, hour-160 stop", [rows(rt["ResultSummary"])[0][key] for key in ("NREP", "RTILW", "RTIUP")], [1, 0, 160])

    result = {
        "schema": "simlox-d02-var03-independent-long-parking-readonly/v1",
        "reviewer": "independent standard-library read-only replay; no author imports or native calls",
        "case_id": "D02", "variant_id": "D02.var03", "run_id": RUN_ID,
        "parent_run_id": PARENT_RUN.name,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks,
        "hashes": {"parent_input": sha(PARENT_INPUT), "child_input": sha(CASE / "native-input.json"),
                   "child_invocation": sha(RUN / "invocation.json"), "child_closure": sha(RUN / "closure.json"),
                   "child_model_log": sha(RUN / "model.log"), "child_report_raw": sha(RUN / "report-raw.json"),
                   "parent_model_log": sha(PARENT_RUN / "model.log"), "parent_report_raw": sha(PARENT_RUN / "report-raw.json")},
        "observed": {"first_failure_hour": 9.8829, "no_flight_gap": [22, 152], "no_failure_in_gap": True,
                     "third_mission": {"created": 151, "started": 152, "succeeded": 154},
                     "report_bins": 320, "failure_count": 1, "repair_count": 1,
                     "stock_demands": 1, "backorders": 0, "terminal_ready_aircraft": 1,
                     "conversion": {"errors": 0, "warnings": 1, "warning_codes": [108]}},
        "decision": "bounded_long_parking_cli_evidence_accepted" if all(c["passed"] for c in checks) else "review_failed",
        "limits": [
            "One seed and a single 130-hour no-flight interval support an observed quiet gap, not a general OPHOURS clock proof; no internal clock counter is reported.",
            "The aircraft is ready in 22-151 report bins; mission preparation begins at hour 151 before the hour-152 third launch.",
            "No PM during parking, dynamic state transitions, other seeds, GUI visual content or cross-engine equivalence are tested.",
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
