"""Independent standard-library read-only replay of D02.var04 and D06 control.

Does not import author code or execute the SIMLOX native application.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "D06-explicit-position-direct-repair-v1.0.0"
PARENT_INPUT = PARENT_CASE / "native-input.json"
PARENT_RUN = PARENT_CASE / "runs/d06-position-cm-v100-ssh-20260930-02"
RUN_ID = "d02-var04-cross-cm-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUTPUT = CASE / "review/independent-cross-cm-2026-09-30.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
CHILD_SHA = "19aaca9e7b9ae6eab68685e622a254c7c20f44ef671425f047ee7c05dfdad91c"


def sha(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path, native=False):
    content = path.read_text(encoding="utf-8-sig")
    if native:
        content = re.sub(r",\s*([}\]])", r"\1", content)
    return json.loads(content)


def tables(document, key="model"):
    return {table["name"]: table for table in document[key]["tables"]}


def rows(table):
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row)) for part in table["instances"] for row in part["rows"]]


def event_times(log, expression):
    return [float(match.group(1)) for match in re.finditer(expression, log, re.M)]


def main():
    checks = []

    def check(name, actual, expected, tolerance=None):
        passed = actual == expected if tolerance is None else abs(actual - expected) <= tolerance
        checks.append({"name": name, "passed": passed, "actual": actual, "expected": expected})

    child = load(CASE / "native-input.json")
    parent = load(PARENT_INPUT)
    contract = load(CASE / "contract.json")
    delta = load(CASE / "parent-diff.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    parent_invocation = load(PARENT_RUN / "invocation.json")
    parent_closure = load(PARENT_RUN / "closure.json")
    steps = load(RUN / "steps.json")
    exported = load(RUN / "roundtrip-raw.json", native=True)
    report = load(RUN / "report-raw.json", native=True)
    parent_report = load(PARENT_RUN / "report-raw.json", native=True)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")

    check("accepted D06 parent SHA", sha(PARENT_INPUT), PARENT_SHA)
    check("frozen D02.var04 source SHA", sha(CASE / "native-input.json"), CHILD_SHA)
    check("contract source binding", [contract["parent"]["input_sha256"], contract["native_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("parent diff source binding", [delta["parent_input_sha256"], delta["child_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("native run input copy SHA", sha(RUN / "input.json"), CHILD_SHA)
    check("child invocation input/parent binding", [invocation["input_sha256"], invocation["parent_sha256"]], [CHILD_SHA, PARENT_SHA])
    check("parent invocation input binding", parent_invocation["input_sha256"], PARENT_SHA)
    check("child run id", [invocation["run_id"], closure["run_id"]], [RUN_ID, RUN_ID])
    check("child closure binds invocation", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("parent closure binds invocation", parent_closure["invocation_sha256"], sha(PARENT_RUN / "invocation.json"))
    check("child source unchanged during native run", closure["source_hashes_before"], closure["source_hashes_after"])
    check("child invocation and closure fingerprints agree", invocation["source_hashes_before"], closure["source_hashes_before"])
    check("parent source unchanged during native run", parent_closure["source_hashes_before"], parent_closure["source_hashes_after"])
    for key, path in {"input": CASE / "native-input.json", "parent": PARENT_INPUT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}.items():
        check(f"child sealed local {key}", sha(path), closure["source_hashes_before"][key])
    for label, folder, seal in (("child", RUN, closure), ("parent", PARENT_RUN, parent_closure)):
        check(f"{label} closure no error", seal["error"], None)
        check(f"{label} twelve raw artifacts", len(seal["raw"]), 12)
        for name, claim in sorted(seal["raw"].items()):
            path = folder / name
            check(f"{label} sealed raw {name}", [path.stat().st_size, sha(path)], [claim["bytes"], claim["sha256"]])
    check("session-0 SSH, GUI and queue guard", [invocation["execution_mode"], invocation["session_id"], invocation["ssh_connection_present"],
                                             invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]],
          ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
    check("five step names", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
    check("five steps successful with GUI preserved", all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps), True)
    check("native import/export completion markers", ["Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"),
                                                        "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig")], [True, True])
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    check("conversion errors/warnings/notes", conversion.groups() if conversion else None, ("0", "1", "0"))
    check("only logging warning #108", re.findall(r"warning #(\d+)", run_log), ["108"])

    pt, ct, et = tables(parent), tables(child), tables(exported)
    changed = sorted(name for name in pt if pt[name] != ct.get(name))
    check("same model tables", sorted(pt), sorted(ct))
    check("only description and CM location changed", changed, ["CMLocation", "ProblemDescription"])
    check("diff exact changed names", sorted(delta["changed_tables_only"]), changed)
    check("33 parent tables unchanged", len(pt) - len(changed), 33)
    check("diff exact changed tables", all(delta["changed_tables"][name] == {"parent": pt[name], "child": ct[name]} for name in changed), True)
    check("no added tables", delta["added_tables_only"], [])
    before, after = rows(pt["CMLocation"])[0], rows(ct["CMLocation"])[0]
    check("only CM duration differs", [key for key in before if before[key] != after[key]], ["CMT"])
    check("CMT half-hour to 15.5h", [before["CMT"], after["CMT"]], [0.5, 15.5])
    check("same FMID, aircraft and base", [after["FMID"], after["ID"], after["STID"]], ["FM-POS-A", "TEACH-AIR-01", "BASE-01"])
    check("failure mode clock and frequency unchanged", [rows(ct["FailureMode"])[0][key] for key in ("FMID", "MID", "FRQ", "OPID")],
          ["FM-POS-A", "POS-A", 300000.0, "OPHOURS"])
    check("scheduled missions unchanged", [r["STIM"] for r in rows(ct["OperationProfile"])], [8.0, 20.0, 32.0])
    check("horizon and seed unchanged", [rows(ct["Control"])[0][key] for key in ("SIMPE", "RCEND", "RSEED")], [36.0, 36.0, "1"])
    populated = [name for name, table in ct.items() if any(part["rows"] for part in table["instances"])]
    check("18 row-containing source tables", len(populated), 18)
    check("all row-containing source tables roundtrip", all(ct[name] == et.get(name) for name in populated), True)
    check("no missing native export tables", sorted(ct.keys() - et.keys()), [])

    fail_pattern = r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical CM failure mode added, now"
    child_failures = event_times(log, fail_pattern)
    parent_failures = event_times(parent_log, fail_pattern)
    check("one child FM-POS-A failure", child_failures, [9.8829])
    check("two parent FM-POS-A failures", parent_failures, [9.8829, 33.8602])
    check("child failure names position A", log.count("Failure Mode: FM-POS-A on materiel: <POS-A,0>"), 2)
    check("first child mission aborts", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission aborted:"), [9.8829])
    check("child mission object creation hours", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission created:"), [7.0, 19.0, 31.0])
    check("first and third launch, second does not", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission starting, duration: 2"), [8.0, 32.0])
    check("second mission waits", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,1> mission waiting:"), [19.0])
    check("second mission cancellation", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:"), [20.3333])
    check("second mission never allocated a system", re.search(r"<BASIC-MISSION,TEACH-UNIT,0,0,1> mission allocates system", log) is None, True)
    check("third mission succeeds", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission success:"), [34.0])
    check("first return and system CM start", [event_times(log, r"^Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>,"),
                                              event_times(log, r"^Time: ([0-9.]+)  system CM task 0 on <TEACH-AIR-01,0> started$")], [[10.0, 34.0], [10.0]])
    check("CM task bears FM-POS-A and planned 15.5h", [log.count("system CM task 0 on <TEACH-AIR-01,0> FMID: FM-POS-A"),
                                                       log.count("starts performing, planned to last for 15.5 hours")], [1, 1])
    check("CM completes and aircraft ready 25.5", [event_times(log, r"^Time: ([0-9.]+)  system CM task 0 on <TEACH-AIR-01,0> completed$"),
                                                   event_times(log, r"^Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> Maintained system arrives")], [[25.5], [25.5]])
    check("parent second mission success and third abort", [event_times(parent_log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission success:"),
                                                          event_times(parent_log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission aborted:")], [[22.0], [9.8829, 33.8602]])

    rt, prt = tables(report, "report"), tables(parent_report, "report")
    system, stock = rows(rt["SystemResults"]), rows(rt["StockTotalResults"])
    parent_system = rows(prt["SystemResults"])
    check("one summary and 72 system/stock bins", [len(rows(rt["ResultSummary"])), len(system), len(stock)], [1, 72, 72])
    for name, ledger in (("system", system), ("stock", stock)):
        check(f"{name} aligned half-hour 0-36 bins", [(r["STINT"], r["ETINT"]) for r in ledger],
              [(i / 2, (i + 1) / 2) for i in range(72)])
    check("child one failure and repair completion", [sum(r["NFAIL"] for r in system), sum(r["NREPT"] for r in system)], [1, 1])
    check("parent two failures and repair completions", [sum(r["NFAIL"] for r in parent_system), sum(r["NREPT"] for r in parent_system)], [2, 2])
    check("child failure/repair completion bins", [[r["STINT"] for r in system if r["NFAIL"]], [r["STINT"] for r in system if r["NREPT"]]], [[9.5], [25.5]])
    check("continuous repair occupancy 10-25.5", [r["STINT"] for r in system if r["NSYRP"]], [i / 2 for i in range(20, 51)])
    check("15.5 system repair aircraft-hours", sum(r["NSYRP"] for r in system) * 0.5, 15.5)
    check("no mission operating bins 20-22", all(r["NSYMO"] == 0 for r in system if 20 <= r["STINT"] < 22), True)
    check("one aircraft ready after repair and terminal", [system[51]["NSYRY"], system[-1]["NSYRY"]], [1, 1])
    check("no PM/stock activity", [sum(r[key] or 0 for r in system) for key in ("NPMT", "NPMS", "NROBT")]
          + [sum(r["NBO"] for r in stock), sum(r["NDF"] for r in stock)], [0, 0, 0, 0, 0])
    check("one repetition and 36h result horizon", [rows(rt["ResultSummary"])[0][key] for key in ("NREP", "RTILW", "RTIUP")], [1, 0, 36])

    result = {
        "schema": "simlox-d02-var04-independent-cross-cm-readonly/v1",
        "reviewer": "independent standard-library read-only replay; no author imports or native calls",
        "case_id": "D02", "variant_id": "D02.var04", "run_id": RUN_ID,
        "parent_run_id": PARENT_RUN.name,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks,
        "hashes": {"parent_input": sha(PARENT_INPUT), "child_input": sha(CASE / "native-input.json"),
                   "child_invocation": sha(RUN / "invocation.json"), "child_closure": sha(RUN / "closure.json"),
                   "child_model_log": sha(RUN / "model.log"), "child_report_raw": sha(RUN / "report-raw.json"),
                   "parent_model_log": sha(PARENT_RUN / "model.log"), "parent_report_raw": sha(PARENT_RUN / "report-raw.json")},
        "observed": {"failure_hour": 9.8829, "cm_interval": [10, 25.5], "cancelled_mission": {"created": 19,
                     "cancelled": 20.3333, "scheduled_launch": 20, "launched": False},
                     "third_mission": {"launch": 32, "success": 34},
                     "conversion": {"errors": 0, "warnings": 1, "warning_codes": [108]},
                     "repair_aircraft_hours": 15.5, "terminal_ready_aircraft": 1},
        "decision": "bounded_cross_mission_direct_cm_accepted" if all(c["passed"] for c in checks) else "review_failed",
        "limits": [
            "One FMID, one seed and one 15.5-hour direct system CM demonstrate this cancellation timing, not a general mission queue or priority algorithm.",
            "The second mission was created and waited, then cancelled without aircraft allocation or launch; SystemResults has no separate mission cancellation metric, so cancellation is established by native event log and operation-bin absence.",
            "CMT is calendar turnaround, not measured labor time. Position alternatives, replacement, personnel capacity, GUI visuals and cross-engine behavior are untested.",
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
