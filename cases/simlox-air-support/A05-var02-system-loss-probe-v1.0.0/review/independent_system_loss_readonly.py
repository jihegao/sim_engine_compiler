"""Independent read-only replay of A05.var02's sealed native CLI evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "a05-var02-system-loss-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-system-loss-2026-09-30.json"
CONTROL_CASE = ROOT / "A05-continuous-baseline-v1.0.1"
CONTROL = CONTROL_CASE / "native-continuous.json"
CONTROL_RUN = CONTROL_CASE / "runs" / "a05-continuous-four-hour-v101-ssh-20260930-01"
REPAIR = ROOT / "D01-system-direct-repair-v1.0.0" / "native-input.json"
CHILD = CASE / "native-input.json"
CONTROL_SHA = "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea"
REPAIR_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
CHILD_SHA = "02e823bd09fd3e6a3c2f0ae59846adcb2d35bcbc6d0ee9b09d0d936ebf36b10c"
FAIL = 9.8829
READY = 10.3829


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path, native: bool = False) -> dict:
    raw = p.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX JSON exports have trailing commas. Remove those outside strings.
        out = []
        quoted = escaped = False
        for i, ch in enumerate(raw):
            if quoted:
                out.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
                out.append(ch)
            elif ch == "," and re.match(r"\s*[}\]]", raw[i+1:]):
                continue
            else:
                out.append(ch)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    found = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"{name}: expected one table")
    return found[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    tab = table(doc, root, name)
    fields = [c["name"] for c in tab["columns"]]
    return [dict(zip(fields, row)) for inst in tab["instances"] for row in inst["rows"]]


def near(a: float, b: float, tol: float = 1e-4) -> bool:
    return math.isclose(a, b, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        good = actual == expected
        checks.append({"name": name, "passed": good, **({} if good else {
            "actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract, parent, repair, child = (load(CASE / "contract.json"), load(CONTROL),
                                       load(REPAIR), load(CHILD))
    ck("accepted A05 full-strength parent SHA", sha(CONTROL), CONTROL_SHA)
    ck("accepted D01 repair source SHA", sha(REPAIR), REPAIR_SHA)
    ck("frozen child SHA", sha(CHILD), CHILD_SHA)
    ck("contract three-source binding", (
        contract["parent"]["input_sha256"], contract["repair_source"]["input_sha256"],
        contract["native_input_sha256"]), (CONTROL_SHA, REPAIR_SHA, CHILD_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("same parent/child table set", set(pt), set(ct))
    ck("exact three changed tables", changed,
       {"ProblemDescription", "System", "SystemRepair"})
    ck("28 unchanged tables", len(set(pt)-changed), 28)
    ck("same table schema", all(pt[n]["columns"] == ct[n]["columns"] for n in pt), True)
    ck("descriptive label only", (
        rows(parent, "model", "ProblemDescription")[0]["PDESC"],
        rows(child, "model", "ProblemDescription")[0]["PDESC"]),
        ("A05 continuous four-hour two-aircraft control",
         "A05 continuous four-hour two-aircraft seeded system-loss probe"))
    before_sys = rows(parent, "model", "System")[0]
    after_sys = rows(child, "model", "System")[0]
    ck("only System.FRT 0-to-300000", (
        [(k, v, after_sys[k]) for k, v in before_sys.items() if v != after_sys[k]],
        after_sys["OPID"]), ([('FRT', 0, 300000)], "OPHOURS"))
    ck("repair table copies accepted D01 exactly", (
        table(child, "model", "SystemRepair")["columns"],
        table(child, "model", "SystemRepair")["instances"]),
        (table(repair, "model", "SystemRepair")["columns"],
         table(repair, "model", "SystemRepair")["instances"]))
    ck("single direct repair row and half-hour duration", (
        len(rows(child, "model", "SystemRepair")),
        {k: rows(child, "model", "SystemRepair")[0][k]
         for k in ("DIRPT", "SURPT", "DIRPF", "SURPF")}),
        (1, {"DIRPT": 0.5, "SURPT": 0, "DIRPF": 1, "SURPF": 1}))
    mission = rows(child, "model", "MissionType")[0]
    dep = rows(child, "model", "SystemDeployment")[0]
    ctl = rows(child, "model", "Control")[0]
    ck("continuous two-aircraft fixed-hour configuration", (
        mission["MPAT"], mission["DURN"], mission["MNOS"], mission["NOS"],
        dep["QTYPS"], ctl["SIMPE"], ctl["RSEED"], ctl["RCINT"]),
        ("CONTINUOUS", 4, 2, 2, 2, 16, "1", 0.5))
    ck("continuous out/back fractions clear", (mission["TFOUT"], mission["TFRET"]),
       (None, None))
    ck("no component or spare source rows", all(not rows(child, "model", n) for n in
       ("Item", "ItemStructure", "StockAllocation", "ItemReplacement", "ItemRepair")), True)

    inv, closure, steps = [load(RUN / name) for name in
                           ("invocation.json", "closure.json", "steps.json")]
    ck("copied input exact source bytes", (sha(RUN / "input.json"),
        (RUN / "input.json").read_bytes() == CHILD.read_bytes()), (CHILD_SHA, True))
    ck("invocation identity and input-parent binding", (
        inv["case_id"], inv["variant"], inv["run_id"],
        inv["input_sha256"], inv["parent_sha256"]),
        ("A05", "loss", RUN_ID, CHILD_SHA, CONTROL_SHA))
    ck("session-0 SSH, queue, GUI PID 13340", (
        inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"],
        "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
        inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
        bool(inv["gui"]["start_utc"])),
        ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner guards and GUI assertion", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)", "Global\\SimloxIssue18NativeQueue",
        "13340", "Assert-Gui", "session-0 SSH required")), True)
    ck("invocation SHA closure", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure run identity and no error", (closure["run_id"], closure["error"]),
       (RUN_ID, None))
    ck("source hashes before/after stable", closure["source_hashes_before"],
       closure["source_hashes_after"])
    ck("invocation/closure source agreement", inv["source_hashes_before"],
       closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": CONTROL, "repair_parent": REPAIR,
               "contract": CASE / "contract.json", "builder": CASE / "build.py",
               "checker": CASE / "check_roundtrip.py",
               "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        ck(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    ck("all raw files in closure", set(closure["raw"]),
       {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (stamp["bytes"], stamp["sha256"]),
           (path.stat().st_size, sha(path)))
    ck("four CLI steps plus checker exit0 and GUI preserved", [
        (s["name"], s["status"], s["exit_code"], s["gui_preserved"])
        for s in steps], [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("four CLI command arguments bound", [a["arguments"] == b["arguments"]
       for a, b in zip(steps[:4], inv["planned_commands"])], [True]*4)

    exported = load(RUN / "roundtrip-raw.json", native=True)
    populated = [t for t in child["model"]["tables"]
                 if any(inst["rows"] for inst in t["instances"])]
    ck("14 source row-containing tables", len(populated), 14)
    ck("all source business rows exact after native import/export", all(
        table(exported, "model", t["name"])["columns"] == t["columns"] and
        table(exported, "model", t["name"])["instances"] == t["instances"]
        for t in populated), True)
    rt = load(RUN / "roundtrip-validation.json")
    ck("checker agrees with independent roundtrip", (
        rt["passed"], rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
        (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion 0 errors, 2 warnings, 0 notes", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        conversion), [("0", "2", "0")])
    ck("only warning #108 and #126", sorted(re.findall(r"warning #(\d+)", conversion)),
       ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = event.splitlines()
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def count(s: str) -> int:
        return event.count(s)
    ck("formation starts on time", count(
        f"Time: 8 {mid} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"), 1)
    ck("single critical failure on aircraft zero at 9.8829", (
        count("critical random failure added"),
        count("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added")), (1, 1))
    ck("affected aircraft aborts, survivor suspends", (
        count("<TEACH-AIR-01,0> aborts its mission"),
        count(f"Time: 9.8829 {mid} mission suspended: <TEACH-AIR-01,1>")), (1, 1))
    ck("failed aircraft zero returns to BASE-01 for direct repair", (
        count("Time: 9.8829 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>"),
        count("Time: 9.8829 <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,0>"),
        count("Time: 9.8829  direct repair subtask 0 seqno 0 within system DIRP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours")),
        (1, 1, 1))
    ck("direct repair completes at 10.3829 on same aircraft", (
        count("Time: 10.3829  direct repair subtask 0 seqno 0 within system DIRP task 0 on <TEACH-AIR-01,0> completed"),
        count("Time: 10.3829 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>")),
        (1, 1))
    ck("same aircraft preassigned, allocated and attached", (
        count(f"Time: 9.8829 {mid} mission preassigns a system: <TEACH-AIR-01,0>"),
        count(f"Time: 10.3829 {mid} mission allocates system: <TEACH-AIR-01,0>"),
        count(f"Time: 10.3829 {mid} system attached: <TEACH-AIR-01,0>")),
        (1, 1, 1))
    ck("both aircraft resume before fixed hour-12 end", (
        count(f"Time: 10.3829 {mid} mission resumed: <TEACH-AIR-01,1>(Susp),<TEACH-AIR-01,0>(Susp)"),
        count("<TEACH-AIR-01,1> resumed on mission"),
        count("<TEACH-AIR-01,0> resumed on mission"),
        count(f"Time: 12 {mid} mission completed: <TEACH-AIR-01,1>,<TEACH-AIR-01,0>")),
        (1, 1, 1, 1))
    ck("log success marker but no replacement instance", (
        count(f"Time: 12 {mid} mission success:"),
        sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", event)))),
        (1, ["0", "1"]))
    ck("terminal two ready after one repair", (
        count("Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,1>,<TEACH-AIR-01,0>"),
        count("Time: 10.3829  system DIRP task 0 on <TEACH-AIR-01,0> completed")), (1, 1))

    report = load(RUN / "report-raw.json", native=True)
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    ck("32 aligned half-hour system and stock bins", (
        len(system), len(stock),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
        (32, 32, True, True))
    bytime = {r["STINT"]: r for r in system}
    ck("full-strength operation before and after repair gap", all(
        (r["NSYMO"], r["NSYMA"]) == (2, 2)
        for r in system if 8 <= r["STINT"] < 9.5 or 10.5 <= r["STINT"] < 12), True)
    ck("fractional 9.5 and 10.0 operation bins", (
        near(bytime[9.5]["NSYMO"], 2*(FAIL-9.5)/0.5),
        near(bytime[10.0]["NSYMO"], 2*(10.5-READY)/0.5)), (True, True))
    ck("fractional repair bins sum to 0.5 aircraft-hour", (
        near(bytime[9.5]["NSYRP"], (10-FAIL)/0.5),
        near(bytime[10.0]["NSYRP"], (READY-10)/0.5),
        near(sum(r["NSYRP"]*0.5 for r in system), 0.5)), (True, True, True))
    ck("one failure, one repair completion", (
        sum(r["NFAIL"] or 0 for r in system),
        sum(r["NREPT"] or 0 for r in system)), (1, 1))
    integrals = {field: sum((r[field] or 0)*0.5 for r in system)
                 for field in ("NSYRY", "NSYMA", "NSYMO", "NSYMS", "NSYRP", "NSYUA", "STACC")}
    ck("system availability and operation integrals", tuple(
        near(integrals[k], v) for k, v in
        (("NSYRY", 22), ("NSYMA", 9.5), ("NSYMO", 7),
         ("NSYMS", 0.5), ("NSYRP", 0.5), ("NSYUA", 0.5), ("STACC", 7))),
        (True,)*7)
    ck("no stock demand or backorder", all((r[k] or 0) == 0 for r in stock
       for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("terminal ready two, no repair or operation", (
        system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]),
        (2, 0, 0))
    ck("report summary 0.875 and zero mission-success counters", (
        summary["NREP"], summary["RTILW"], summary["RTIUP"],
        near(summary["MTMF"], 0.875), summary["MSTF"], summary["MSUF"],
        near(summary["STMF"], 0.875)), (1, 0, 16, True, 0, 0, True))
    control_report = load(CONTROL_RUN / "report-raw.json", native=True)
    control_sys = rows(control_report, "report", "SystemResults")
    ck("failure-free continuous control has 8 mission aircraft-hours", (
        len(control_sys), near(sum(r["NSYMO"]*0.5 for r in control_sys), 8),
        sum(r["NFAIL"] or 0 for r in control_sys)), (32, True, 0))
    ck("child loses one aircraft-hour against control", near(
        sum(r["NSYMO"]*0.5 for r in control_sys) - integrals["NSYMO"], 1), True)

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a05-var02-independent-system-loss-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native process",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"input": sha(CHILD), "control_input": sha(CONTROL),
                   "repair_source": sha(REPAIR), "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"), "model_log": sha(RUN / "model.log"),
                   "report_raw": sha(RUN / "report-raw.json")},
        "observed": {"failed_aircraft": "TEACH-AIR-01,0", "failure_hour": FAIL,
                     "repair_start_hour": FAIL, "repair_end_hour": READY,
                     "reattachment_hour": READY, "resume_hour": READY,
                     "mission_end_hour": 12, "surviving_aircraft": "TEACH-AIR-01,1",
                     "aircraft_mission_hours": integrals["NSYMO"],
                     "system_maintenance_hours_NSYMS": integrals["NSYMS"],
                     "repair_aircraft_hours": integrals["NSYRP"],
                     "report_bins": 32, "stock_demand": 0,
                     "terminal_ready_aircraft": 2,
                     "summary_MTMF": summary["MTMF"], "summary_STMF": summary["STMF"],
                     "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"]},
        "decision": "bounded_same_aircraft_repair_rejoin_accepted" if passed
                    else "review_rejected_pending_resolution",
        "distinct_spare_replacement_status": "unproved_no_distinct_spare_deployed",
        "limits": [
            "One seed and one stochastic failure; no general failure timing or policy inferred.",
            "The resumed participant is the same repaired aircraft #0, not a distinct spare or replacement aircraft.",
            "Native event success at 12 coexists with ResultSummary MSTF/MSUF=0/0 and MTMF=0.875; preserve both as separate observations.",
            "Half-hour result bins provide fractional exposure, not event timestamp precision; exact event times come from model.log.",
            "No GUI visual inspection or cross-engine equivalence."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
