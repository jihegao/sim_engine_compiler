"""Independent read-only raw replay for A05.var02 distinct system spare.

Uses Python's standard library. It does not import author code or call SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A05-var02-system-loss-probe-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
CHILD = CASE / "native-input.json"
REPAIR = CASE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
RUN_ID = "a05-var02-distinct-spare-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-distinct-spare-2026-09-30.json"
PARENT_SHA = "02e823bd09fd3e6a3c2f0ae59846adcb2d35bcbc6d0ee9b09d0d936ebf36b10c"
CHILD_SHA = "aab1e4050a107e8490716a9306d9eb461b5c4a0c88430c157a2699afc5a120bb"
REPAIR_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        out = []
        quoted = escape = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and re.match(r"\s*[}\]]", raw[i+1:]):
                continue
            else:
                out.append(char)
        raw = "".join(out)
    return json.loads(raw)


def tabs(doc: dict, root: str) -> dict:
    sequence = doc[root]["tables"]
    result = {t["name"]: t for t in sequence}
    if len(sequence) != len(result):
        raise ValueError("duplicate table name")
    return result


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = tabs(doc, root)[name]
    fields = [c["name"] for c in t["columns"]]
    return [dict(zip(fields, row)) for inst in t["instances"] for row in inst["rows"]]


def close(actual: float, expected: float, tol: float = 1e-4) -> bool:
    return math.isclose(actual, expected, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        passed = actual == expected
        checks.append({"name": name, "passed": passed, **({} if passed else {
            "actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract, parent, child = read(CASE / "contract.json"), read(PARENT), read(CHILD)
    check("accepted same-aircraft parent SHA", sha(PARENT), PARENT_SHA)
    check("accepted repair source SHA", sha(REPAIR), REPAIR_SHA)
    check("frozen child SHA", sha(CHILD), CHILD_SHA)
    check("parent signoff exists", (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(), True)
    check("contract parent/child binding", (
        contract["parent"]["input_sha256"], contract["native_input_sha256"]),
        (PARENT_SHA, CHILD_SHA))
    ptab, ctab = tabs(parent, "model"), tabs(child, "model")
    check("source table names unchanged", set(ptab), set(ctab))
    changed = {n for n in ptab if ptab[n] != ctab[n]}
    check("exact three changed tables", changed,
          {"ProblemDescription", "SystemDeployment", "Unit"})
    check("28 tables unchanged", len(ptab)-len(changed), 28)
    check("all table schemas identical", all(ptab[n]["columns"] == ctab[n]["columns"]
                                        for n in ptab), True)
    check("deployed aircraft 2 to 3 only", (
        [(k, v, rows(child, "model", "SystemDeployment")[0][k]) for k, v
         in rows(parent, "model", "SystemDeployment")[0].items()
         if v != rows(child, "model", "SystemDeployment")[0][k]],
        rows(child, "model", "MissionType")[0]["NOS"],
        rows(child, "model", "MissionType")[0]["MNOS"]),
        ([("QTYPS", 2, 3)], 2, 2))
    check("descriptive changes only in remaining two tables", (
        rows(parent, "model", "ProblemDescription")[0]["PDESC"],
        rows(child, "model", "ProblemDescription")[0]["PDESC"],
        rows(parent, "model", "Unit")[0]["DESCR"],
        rows(child, "model", "Unit")[0]["DESCR"]),
        ("A05 continuous four-hour two-aircraft seeded system-loss probe",
         "A05 continuous four-hour three-aircraft distinct-spare probe",
         "Two-aircraft teaching unit", "Three-aircraft teaching unit"))
    check("only description cells changed", (
        [k for k, v in rows(parent, "model", "Unit")[0].items()
         if v != rows(child, "model", "Unit")[0][k]],
        [k for k, v in rows(parent, "model", "ProblemDescription")[0].items()
         if v != rows(child, "model", "ProblemDescription")[0][k]]),
        (["DESCR"], ["PDESC"]))
    mission = rows(child, "model", "MissionType")[0]
    control = rows(child, "model", "Control")[0]
    check("failure/schedule/mission settings inherited", (
        rows(child, "model", "System")[0]["FRT"],
        mission["MPAT"], mission["DURN"],
        control["RSEED"], control["SIMPE"], control["RCINT"],
        rows(child, "model", "OperationProfile")[0]["STIM"]),
        (300000, "CONTINUOUS", 4, "1", 16, 0.5, 8))
    check("system direct repair inherited exactly", tabs(child, "model")["SystemRepair"],
          ptab["SystemRepair"])
    check("no stocked item or component spare", all(not rows(child, "model", n) for n in
          ("Item", "ItemStructure", "StockAllocation", "ItemReplacement")), True)

    invocation, closure, steps = [read(RUN / n) for n in
                                  ("invocation.json", "closure.json", "steps.json")]
    check("copied run input exact bytes", (
        sha(RUN / "input.json"), (RUN / "input.json").read_bytes() == CHILD.read_bytes()),
        (CHILD_SHA, True))
    check("invocation identity", (
        invocation["case_id"], invocation["variant"], invocation["run_id"],
        invocation["input_sha256"], invocation["parent_sha256"]),
        ("A05", "spare", RUN_ID, CHILD_SHA, PARENT_SHA))
    check("session-0 SSH, queue, GUI guard", (
        invocation["execution_mode"], invocation["session_id"],
        invocation["ssh_connection_present"],
        "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],
        invocation["queue_mutex"], invocation["gui"]["pid"],
        invocation["gui"]["session_id"], bool(invocation["gui"]["start_utc"])),
        ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("runner contains actual guards", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    check("invocation raw seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("closure clean and source stable", (
        closure["run_id"], closure["error"],
        closure["source_hashes_before"] == closure["source_hashes_after"]),
        (RUN_ID, None, True))
    check("invocation and closure source map equal", invocation["source_hashes_before"],
          closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": PARENT, "repair_parent": REPAIR,
               "contract": CASE / "contract.json", "builder": CASE / "build.py",
               "checker": CASE / "check_roundtrip.py",
               "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        check(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    check("raw closure file set", set(closure["raw"]),
          {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        path = RUN / name
        check(f"raw seal {name}", (stamp["bytes"], stamp["sha256"]),
              (path.stat().st_size, sha(path)))
    check("four CLI steps plus checker all exit0 and preserve GUI", [
        (s["name"], s["status"], s["exit_code"], s["gui_preserved"])
        for s in steps], [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    check("native CLI arguments match invocation plan", [
        a["arguments"] == b["arguments"] for a, b in
        zip(steps[:4], invocation["planned_commands"])], [True]*4)

    exported = read(RUN / "roundtrip-raw.json", native=True)
    source_tables = [t for t in child["model"]["tables"]
                     if any(inst["rows"] for inst in t["instances"])]
    check("14 source row-containing tables", len(source_tables), 14)
    check("all source business tables roundtrip exactly", all(
        tabs(exported, "model")[t["name"]]["columns"] == t["columns"] and
        tabs(exported, "model")[t["name"]]["instances"] == t["instances"]
        for t in source_tables), True)
    rt = read(RUN / "roundtrip-validation.json")
    check("checker agrees on roundtrip", (
        rt["passed"], rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
        (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("conversion totals zero errors", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        runlog), [("0", "2", "0")])
    check("warnings #108 and #126", sorted(re.findall(r"warning #(\d+)", runlog)),
          ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = event.splitlines()
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def count(fragment: str) -> int:
        return event.count(fragment)
    check("initial pair 0/1 only at hour8", count(
        f"Time: 8 {mid} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"), 1)
    check("two failure times and identities", (
        count("critical random failure added"),
        count("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added"),
        count("Time: 11.7431 <TEACH-AIR-01,1> critical random failure added")),
        (2, 1, 1))
    check("aircraft2 is initially unallocated until first demand", (
        count(f"Time: 7 {mid} mission allocates system: <TEACH-AIR-01,2>"),
        count(f"Time: 9.8829 {mid} mission allocates system: <TEACH-AIR-01,2>")),
        (0, 1))
    cycles = [
        ("first", "9.8829", "0", "2", "1"),
        ("second", "11.7431", "1", "0", "2")]
    for label, moment, failed, replacement, survivor in cycles:
        check(f"{label} failed aircraft aborts, survivor suspends", (
            count(f"<TEACH-AIR-01,{failed}> aborts its mission"),
            count(f"Time: {moment} {mid} mission suspended: <TEACH-AIR-01,{survivor}>")),
            (1, 1))
        check(f"{label} different aircraft attaches and both resume same timestamp", (
            count(f"Time: {moment} {mid} mission allocates system: <TEACH-AIR-01,{replacement}>"),
            count(f"Time: {moment} {mid} system attached: <TEACH-AIR-01,{replacement}>"),
            count(f"Time: {moment} {mid} mission resumed: <TEACH-AIR-01,{survivor}>(Susp),<TEACH-AIR-01,{replacement}>(Susp)")),
            (1, 1, 1))
        check(f"{label} failed aircraft returns for repair", (
            count(f"Time: {moment} <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,{failed}>"),
            count(f"Time: {moment} <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,{failed}>")),
            (1, 1))
    check("first repaired aircraft0 later serves as second replacement", (
        count("Time: 10.3829 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>"),
        count(f"Time: 11.7431 {mid} system attached: <TEACH-AIR-01,0>")),
        (1, 1))
    check("second repair ends after mission at12.2431", (
        count("Time: 12.2431  direct repair subtask 1 seqno 0 within system DIRP task 1 on <TEACH-AIR-01,1> completed"),
        count("Time: 12.2431 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,1>")),
        (1, 1))
    check("fixed hour12 mission end with pair2/0", (
        count(f"Time: 12 {mid} mission success:"),
        count(f"Time: 12 {mid} mission completed: <TEACH-AIR-01,2>,<TEACH-AIR-01,0>")),
        (1, 1))
    check("only aircraft instances0/1/2 in event trace", sorted(set(
        re.findall(r"<TEACH-AIR-01,(\d+)>", event))), ["0", "1", "2"])
    check("all three aircraft ready after second repair", count(
        "Time: 12.2431 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :"), 1)

    report = read(RUN / "report-raw.json", native=True)
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    check("32 aligned half-hour report bins", (
        len(system), len(stock),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
        (32, 32, True, True))
    check("two aircraft operate in every mission bin", all(
        (r["NSYMO"], r["STACC"], r["NSYMA"]) == (2, 2, 2)
        for r in system if 8 <= r["STINT"] < 12), True)
    integral = {k: sum((r[k] or 0)*0.5 for r in system)
                for k in ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYUA", "NSYMA")}
    check("mission/maintenance/repair hour integrals", tuple(
        close(integral[k], target) for k, target in
        (("NSYMO", 8), ("STACC", 8), ("NSYMS", 0),
         ("NSYRP", 1), ("NSYUA", 1), ("NSYMA", 10))),
        (True,)*6)
    check("no finite suspension in bin resolution", all(r["NSYMS"] == 0
                                                    for r in system), True)
    check("two failure and two repair counters", (
        sum(r["NFAIL"] or 0 for r in system),
        sum(r["NREPT"] or 0 for r in system)), (2, 2))
    check("report stock demand/backorder zero", all((r[k] or 0) == 0
        for r in stock for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    check("terminal ready three", (
        system[-1]["NSYRY"], system[-1]["NSYMO"], system[-1]["NSYRP"]),
        (3, 0, 0))
    check("continuous report summary 1.0 exposure, zero success counters", (
        summary["NREP"], summary["RTILW"], summary["RTIUP"],
        summary["MTMF"], summary["STMF"], summary["MSTF"], summary["MSUF"]),
        (1, 0, 16, 1, 1, 0, 0))
    prior_report = read(PARENT_CASE / "runs" / "a05-var02-system-loss-v100-ssh-20260930-01" /
                        "report-raw.json", native=True)
    previous = rows(prior_report, "report", "SystemResults")
    check("prior same-aircraft case had measurable suspension and seven operation hours", (
        close(sum((r["NSYMS"] or 0)*0.5 for r in previous), 0.5),
        close(sum((r["NSYMO"] or 0)*0.5 for r in previous), 7)), (True, True))

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a05-var02-distinct-spare-independent-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native call",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
                   "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"),
                   "report_raw": sha(RUN / "report-raw.json")},
        "observed": {"first_cycle": {"failure_hour": 9.8829, "failed": "aircraft0",
                                      "replacement": "initially ready aircraft2",
                                      "repair_complete_hour": 10.3829},
                     "second_cycle": {"failure_hour": 11.7431, "failed": "aircraft1",
                                       "replacement": "repaired aircraft0",
                                       "repair_complete_hour": 12.2431},
                     "suspension_duration_observed_hours": 0,
                     "mission_end_hour": 12,
                     "report_bins": 32, "integrals_aircraft_hours": integral,
                     "failure_count": 2, "repair_count": 2,
                     "stock_demand_count": 0, "terminal_ready_aircraft": 3,
                     "summary_MTMF": summary["MTMF"],
                     "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"]},
        "decision": "bounded_two_distinct_system_replacement_cycles_accepted" if passed
                    else "review_rejected_pending_resolution",
        "limits": [
            "Distinct ready aircraft systems replace failed mission participants; this does not test stocked item or component replacement.",
            "Both suspension/resumption pairs share a timestamp and NSYMS=0; no finite suspension interval is established.",
            "One stochastic fixed-seed run does not establish deterministic failure times or generic replacement policy.",
            "Hour-12 event success marker coexists with ResultSummary MSTF/MSUF=0/0, inherited continuous-report behavior.",
            "No GUI visual inspection or cross-engine equivalence."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
