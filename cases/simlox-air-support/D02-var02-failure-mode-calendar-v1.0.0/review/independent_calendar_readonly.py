"""Independent standard-library replay of D02.var02 against sealed D06 control.

Reads frozen inputs and raw CLI artifacts only. Does not import author code or
invoke the native application.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT_CASE = BASE / "D06-explicit-position-direct-repair-v1.0.0"
PARENT_INPUT = PARENT_CASE / "native-input.json"
PARENT_RUN = PARENT_CASE / "runs/d06-position-cm-v100-ssh-20260930-02"
RUN_ID = "d02-var02-calendar-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUTPUT = CASE / "review/independent-calendar-2026-09-30.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
CHILD_SHA = "23b550dbc4e0aea4d6d328fe4805a4eb50af81f3af54ccd6353e45bce933271b"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path, native: bool = False):
    content = path.read_text(encoding="utf-8-sig")
    if native:
        content = re.sub(r",\s*([}\]])", r"\1", content)
    return json.loads(content)


def table_map(doc, key="model"):
    return {t["name"]: t for t in doc[key]["tables"]}


def table_rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for part in table["instances"] for row in part["rows"]]


def event_times(log: str, expression: str):
    return [float(match.group(1)) for match in re.finditer(expression, log, re.M)]


def main():
    checks = []

    def check(name, actual, expected, tolerance=None):
        passed = actual == expected if tolerance is None else abs(actual - expected) <= tolerance
        checks.append({"name": name, "passed": passed, "actual": actual, "expected": expected})

    child = read_json(CASE / "native-input.json")
    parent = read_json(PARENT_INPUT)
    contract = read_json(CASE / "contract.json")
    delta = read_json(CASE / "parent-diff.json")
    invoke = read_json(RUN / "invocation.json")
    closure = read_json(RUN / "closure.json")
    parent_invoke = read_json(PARENT_RUN / "invocation.json")
    parent_closure = read_json(PARENT_RUN / "closure.json")
    steps = read_json(RUN / "steps.json")
    export = read_json(RUN / "roundtrip-raw.json", native=True)
    report = read_json(RUN / "report-raw.json", native=True)
    parent_report = read_json(PARENT_RUN / "report-raw.json", native=True)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")

    check("accepted D06 source SHA", sha(PARENT_INPUT), PARENT_SHA)
    check("frozen calendar source SHA", sha(CASE / "native-input.json"), CHILD_SHA)
    check("contract source binding", [contract["parent"]["input_sha256"], contract["native_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("exact diff source binding", [delta["parent_input_sha256"], delta["child_input_sha256"]], [PARENT_SHA, CHILD_SHA])
    check("copied native input SHA", sha(RUN / "input.json"), CHILD_SHA)
    check("child invocation source identity", [invoke["input_sha256"], invoke["parent_sha256"]], [CHILD_SHA, PARENT_SHA])
    check("parent invocation source identity", parent_invoke["input_sha256"], PARENT_SHA)
    check("child run identity", [invoke["run_id"], closure["run_id"]], [RUN_ID, RUN_ID])
    check("child closure binds invocation", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("parent closure binds invocation", parent_closure["invocation_sha256"], sha(PARENT_RUN / "invocation.json"))
    check("child source fingerprints stable", closure["source_hashes_before"], closure["source_hashes_after"])
    check("child invocation/closure fingerprints agree", invoke["source_hashes_before"], closure["source_hashes_before"])
    check("parent source fingerprints stable", parent_closure["source_hashes_before"], parent_closure["source_hashes_after"])
    for key, path in {"input": CASE / "native-input.json", "parent": PARENT_INPUT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}.items():
        check(f"child sealed local {key} bytes", sha(path), closure["source_hashes_before"][key])
    for label, folder, seal in [("child", RUN, closure), ("parent", PARENT_RUN, parent_closure)]:
        check(f"{label} closure no error", seal["error"], None)
        check(f"{label} closure twelve raw hashes", len(seal["raw"]), 12)
        for name, claim in sorted(seal["raw"].items()):
            path = folder / name
            check(f"{label} raw {name}", [path.stat().st_size, sha(path)], [claim["bytes"], claim["sha256"]])
    check("session-0 SSH/GUI/queue guard", [invoke["execution_mode"], invoke["session_id"], invoke["ssh_connection_present"], invoke["gui"]["pid"], invoke["gui"]["session_id"], invoke["queue_mutex"]],
          ["ssh_cli_v1", 0, True, 13340, 1, "Global\\SimloxIssue18NativeQueue"])
    check("five native/checker steps", [s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
    check("all five steps exit zero and preserve GUI", all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps), True)
    check("native import/export markers", ["Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"),
                                           "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig")], [True, True])
    status = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    check("conversion error/warning/note counts", status.groups() if status else None, ("0", "1", "0"))
    check("only event-log warning #108", re.findall(r"warning #(\d+)", run_log), ["108"])

    pt, ct, et = table_map(parent), table_map(child), table_map(export)
    changed = sorted(name for name in pt if pt[name] != ct.get(name))
    check("same table set", sorted(pt), sorted(ct))
    check("only description and FailureMode tables change", changed, ["FailureMode", "ProblemDescription"])
    check("diff describes exact tables", sorted(delta["changed_tables_only"]), changed)
    check("33 parent tables unchanged", len(pt) - len(changed), 33)
    check("no added tables", delta["added_tables_only"], [])
    check("recorded table diff equals raw models", all(delta["changed_tables"][name] == {"parent": pt[name], "child": ct[name]} for name in changed), True)
    parent_modes = table_rows(pt["FailureMode"])
    child_modes = table_rows(ct["FailureMode"])
    check("one mode retains identity, frequency, criticality", [[r["FMID"], r["MID"], r["FRQ"], r["CRITF"]] for r in child_modes],
          [["FM-POS-A", "POS-A", 300000.0, 1.0]])
    check("only FailureMode.OPID behavior field changes", [
        {key: value for key, value in parent_modes[0].items() if key != "OPID"},
        {key: value for key, value in child_modes[0].items() if key != "OPID"}],
        [{key: value for key, value in parent_modes[0].items() if key != "OPID"}] * 2)
    check("OPHOURS to CALHOURS", [parent_modes[0]["OPID"], child_modes[0]["OPID"]], ["OPHOURS", "CALHOURS"])
    check("description-only label change", len(table_rows(ct["ProblemDescription"])), 1)
    check("traditional FRT remains absent", [table_rows(ct["System"])[0]["FRT"], table_rows(ct["Item"])[0]["FRT"]], [None, None])
    populated = [name for name, table in ct.items() if any(part["rows"] for part in table["instances"])]
    check("18 source row-containing tables", len(populated), 18)
    check("exact native roundtrip for every source row-containing table", all(ct[name] == et.get(name) for name in populated), True)
    check("native export contains all source table names", sorted(ct.keys() - et.keys()), [])

    failure_pattern = r"^Time: ([0-9.]+) <TEACH-AIR-01,0> critical CM failure mode added, now"
    child_failures = event_times(log, failure_pattern)
    parent_failures = event_times(parent_log, failure_pattern)
    check("five child failure times", child_failures, [1.8829, 4.84945, 21.2495, 26.7141, 34.2389])
    check("two parent failure times", parent_failures, [9.8829, 33.8602])
    check("five child failures all FM-POS-A on POS-A", log.count("Failure Mode: FM-POS-A on materiel: <POS-A,0>"), 6)
    check("child no other named mode", sorted(set(re.findall(r"Failure Mode: ([^ ]+)", log))), ["FM-POS-A"])
    check("four idle calendar failures", [t for t in child_failures if not any(a <= t < b for a, b in [(8, 10), (20, 22), (32, 34)])],
          [1.8829, 4.84945, 26.7141, 34.2389])
    check("no parent idle failure", [t for t in parent_failures if not any(a <= t < b for a, b in [(8, 10), (20, 22), (32, 34)])], [])
    check("child missions launch at same hours", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission starting, duration: 2"), [8.0, 20.0, 32.0])
    check("child one mission abort", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission aborted:"), [21.2495])
    check("child two mission successes", event_times(log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission success:"), [10.0, 34.0])
    check("parent two mission aborts", event_times(parent_log, r"^Time: ([0-9.]+) <BASIC-MISSION[^\n]* mission aborted:"), [9.8829, 33.8602])
    check("child five FMID system CM starts", event_times(log, r"^Time: ([0-9.]+)  system CM task \d+ on <TEACH-AIR-01,0> started$"), child_failures[:2] + [21.7495] + child_failures[3:])
    check("child five CM completions", event_times(log, r"^Time: ([0-9.]+)  system CM task \d+ on <TEACH-AIR-01,0> completed$"), [2.3829, 5.34945, 22.2495, 27.2141, 34.7389])
    check("each CM task names FM-POS-A", len(re.findall(r"^Time: [0-9.]+  system CM task \d+ on <TEACH-AIR-01,0> FMID: FM-POS-A$", log, re.M)), 5)
    check("each CM performs for half an hour", len(re.findall(r"starts performing, planned to last for 0.5 hours", log)), 5)
    check("terminal ready after fifth repair", event_times(log, r"^Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> Maintained system arrives"),
          [2.3829, 5.34945, 22.2495, 27.2141, 34.7389])

    child_rt = table_map(report, "report")
    parent_rt = table_map(parent_report, "report")
    system = table_rows(child_rt["SystemResults"])
    stock = table_rows(child_rt["StockTotalResults"])
    parent_system = table_rows(parent_rt["SystemResults"])
    check("child one summary and 72 system/stock bins", [len(table_rows(child_rt["ResultSummary"])), len(system), len(stock)], [1, 72, 72])
    check("parent 72 system bins", len(parent_system), 72)
    for name, data in [("system", system), ("stock", stock)]:
        check(f"child {name} 0-36 half-hour bins", [(r["STINT"], r["ETINT"]) for r in data], [(i / 2, (i + 1) / 2) for i in range(72)])
    check("child failures and completed repairs", [sum(r["NFAIL"] for r in system), sum(r["NREPT"] for r in system)], [5, 5])
    check("parent failures and completed repairs", [sum(r["NFAIL"] for r in parent_system), sum(r["NREPT"] for r in parent_system)], [2, 2])
    check("child failure bins", [r["STINT"] for r in system if r["NFAIL"]], [1.5, 4.5, 21.0, 26.5, 34.0])
    check("child repair completion bins", [r["STINT"] for r in system if r["NREPT"]], [2.0, 5.0, 22.0, 27.0, 34.5])
    check("child CM system occupancy aircraft-hours", sum(r["NSYRP"] for r in system) * 0.5, 2.5, tolerance=1e-5)
    check("no PM or replacement report events", [sum(r[key] or 0 for r in system) for key in ("NPMT", "NPMS", "NROBT", "NRCFG")], [0, 0, 0, 0])
    check("stock ledger no backorder or issue", all(r["NBO"] == 0 and r["NDF"] == 0 and r["NDD"] == 0 and r["NDR"] == 0 for r in stock), True)
    check("terminal one ready aircraft", [system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYUA"]], [1, 0, 0])
    summary = table_rows(child_rt["ResultSummary"])[0]
    check("one repetition and 36-hour horizon", [summary["NREP"], summary["RTILW"], summary["RTIUP"]], [1, 0, 36])

    result = {
        "schema": "simlox-d02-var02-independent-calendar-readonly/v1",
        "reviewer": "independent standard-library read-only replay; no author import or native call",
        "case_id": "D02", "variant_id": "D02.var02", "run_id": RUN_ID,
        "parent_run_id": PARENT_RUN.name,
        "passed": all(c["passed"] for c in checks),
        "passed_count": sum(c["passed"] for c in checks),
        "failed_count": sum(not c["passed"] for c in checks),
        "checks": checks,
        "hashes": {"child_input": sha(CASE / "native-input.json"), "parent_input": sha(PARENT_INPUT),
                   "child_invocation": sha(RUN / "invocation.json"), "child_closure": sha(RUN / "closure.json"),
                   "child_model_log": sha(RUN / "model.log"), "child_report_raw": sha(RUN / "report-raw.json"),
                   "parent_model_log": sha(PARENT_RUN / "model.log"), "parent_report_raw": sha(PARENT_RUN / "report-raw.json")},
        "observed": {"calendar_failure_hours": child_failures, "operation_failure_hours": parent_failures,
                     "calendar_idle_failure_hours": [1.8829, 4.84945, 26.7141, 34.2389],
                     "calendar_mission_abort_hour": 21.2495, "calendar_success_hours": [10, 34],
                     "calendar_cm_completion_hours": [2.3829, 5.34945, 22.2495, 27.2141, 34.7389],
                     "conversion": {"errors": 0, "warnings": 1, "warning_codes": [108]}},
        "limits": [
            "This compares one FMID in one fixed-seed 36-hour model; counts are stochastic realizations with unequal calendar and operation exposure, not a rate estimate.",
            "The four idle failures are observed in ground intervals between missions, not in a deliberately all-idle long-horizon test.",
            "The single mission abort changes mission outcome; other missions succeed. No traditional FRT clock, extra failure mode, replacement or resource behavior is tested.",
            "Native CLI log/report evidence does not establish GUI visual behavior or cross-engine equivalence.",
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
