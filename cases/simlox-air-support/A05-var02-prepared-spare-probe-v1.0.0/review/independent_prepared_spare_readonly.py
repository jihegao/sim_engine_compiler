"""Independent, read-only replay of the A05 prepared system-spare run."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A05-var02-distinct-spare-probe-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
B01 = CASE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
CHILD = CASE / "native-input.json"
RUN_ID = "a05-var02-prepared-spare-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-prepared-spare-2026-09-30.json"
PARENT_SHA = "aab1e4050a107e8490716a9306d9eb461b5c4a0c88430c157a2699afc5a120bb"
B01_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
CHILD_SHA = "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d"
FAIL, RESUME = 9.8829, 10.3829


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p: Path, native: bool = False) -> dict:
    raw = p.read_text(encoding="utf-8-sig")
    if native:
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


def tabs(doc: dict, root: str) -> dict:
    sequence = doc[root]["tables"]
    found = {t["name"]: t for t in sequence}
    if len(sequence) != len(found):
        raise ValueError("duplicate table")
    return found


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = tabs(doc, root)[name]
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for inst in t["instances"] for row in inst["rows"]]


def near(x: float, y: float, tol: float = 1e-4) -> bool:
    return math.isclose(x, y, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        passed = actual == expected
        checks.append({"name": name, "passed": passed, **({} if passed else {
            "actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract, parent, prep, child = (load(CASE / "contract.json"), load(PARENT),
                                     load(B01), load(CHILD))
    ck("accepted distinct-spare parent SHA", sha(PARENT), PARENT_SHA)
    ck("accepted B01 preparation SHA", sha(B01), B01_SHA)
    ck("frozen child SHA", sha(CHILD), CHILD_SHA)
    ck("parent signoff and B01 acceptance evidence exist", (
        (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(),
        (B01.parent / "evidence-2026-09-29.md").is_file()), (True, True))
    ck("contract source bindings", (
        contract["parent"]["input_sha256"],
        contract["preparation_source"]["input_sha256"],
        contract["native_input_sha256"]), (PARENT_SHA, B01_SHA, CHILD_SHA))
    pt, ct = tabs(parent, "model"), tabs(child, "model")
    ck("same 31 model tables", (set(pt), len(pt)), (set(ct), 31))
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("exact three changed tables", changed,
       {"ProblemDescription", "MissionPreparation", "Tasks"})
    ck("28 unchanged tables", len(pt)-len(changed), 28)
    ck("all schemas unchanged", all(pt[n]["columns"] == ct[n]["columns"]
                                    for n in pt), True)
    ck("only descriptive label changed", (
        rows(parent, "model", "ProblemDescription")[0]["PDESC"],
        rows(child, "model", "ProblemDescription")[0]["PDESC"]),
        ("A05 continuous four-hour three-aircraft distinct-spare probe",
         "A05 continuous four-hour three-aircraft fixed-preparation probe"))
    for name in ("MissionPreparation", "Tasks"):
        ck(f"{name} inherited exactly from accepted B01", ct[name],
           tabs(prep, "model")[name])
        ck(f"{name} one new source row", (len(rows(parent, "model", name)),
            len(rows(child, "model", name))), (0, 1))
    m = rows(child, "model", "MissionType")[0]
    c = rows(child, "model", "Control")[0]
    ck("continuous three-aircraft configuration unchanged", (
        m["MPAT"], m["NOS"], m["MNOS"], m["DURN"],
        rows(child, "model", "SystemDeployment")[0]["QTYPS"],
        rows(child, "model", "System")[0]["FRT"],
        c["SIMPE"], c["RCINT"], c["RSEED"]),
        ("CONTINUOUS", 2, 2, 4, 3, 300000, 16, 0.5, "1"))
    ck("no stocked item source", all(not rows(child, "model", n) for n in
       ("Item", "ItemStructure", "StockAllocation", "ItemReplacement")), True)

    inv, closure, steps = [load(RUN / n) for n in
                           ("invocation.json", "closure.json", "steps.json")]
    ck("copied input byte identity", (sha(RUN / "input.json"),
        (RUN / "input.json").read_bytes() == CHILD.read_bytes()), (CHILD_SHA, True))
    ck("invocation identity/source binding", (
        inv["case_id"], inv["variant"], inv["run_id"],
        inv["input_sha256"], inv["parent_sha256"]),
        ("A05", "prepared", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("SSH session0 queue and GUI guard", (
        inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"],
        "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
        inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
        bool(inv["gui"]["start_utc"])),
        ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner contains SSH, mutex, GUI checks", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("invocation SHA sealed", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure no error/source stable", (
        closure["run_id"], closure["error"],
        closure["source_hashes_before"] == closure["source_hashes_after"]),
        (RUN_ID, None, True))
    ck("invocation and closure source map equal", inv["source_hashes_before"],
       closure["source_hashes_before"])
    source_paths = {"input": CHILD, "parent": PARENT, "preparation_source": B01,
                    "contract": CASE / "contract.json", "builder": CASE / "build.py",
                    "checker": CASE / "check_roundtrip.py",
                    "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in source_paths.items():
        ck(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    ck("all raw files indexed", set(closure["raw"]),
       {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name} bytes/hash", (stamp["bytes"], stamp["sha256"]),
           (path.stat().st_size, sha(path)))
    ck("four native steps/checker success and GUI preserved", [
        (x["name"], x["status"], x["exit_code"], x["gui_preserved"])
        for x in steps], [(name, "completed", 0, True) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("CLI arguments match invocation", [a["arguments"] == b["arguments"]
        for a, b in zip(steps[:4], inv["planned_commands"])], [True]*4)

    exported = load(RUN / "roundtrip-raw.json", native=True)
    source_tables = [t for t in child["model"]["tables"]
                     if any(i["rows"] for i in t["instances"])]
    ck("16 row-containing source tables", len(source_tables), 16)
    ck("native export exact source business rows", all(
        tabs(exported, "model")[t["name"]]["columns"] == t["columns"] and
        tabs(exported, "model")[t["name"]]["instances"] == t["instances"]
        for t in source_tables), True)
    rt = load(RUN / "roundtrip-validation.json")
    ck("checker agrees with roundtrip", (
        rt["passed"], rt["differences"], rt["source_sha256"],
        rt["roundtrip_sha256"]),
        (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion zero errors, two warnings", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        conversion), [("0", "2", "0")])
    ck("warning codes 108 and 126", sorted(re.findall(r"warning #(\d+)", conversion)),
       ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def count(fragment: str) -> int:
        return event.count(fragment)
    ck("initial two preparation tasks are 7-7.5", tuple(
        count(f"Time: {time} <TEACH-AIR-01,{aid}> preparation {phase}, mission: {mid}")
        for aid in (0, 1) for time, phase in ((7, "started"), (7.5, "ended"))),
        (1, 1, 1, 1))
    ck("initial pair starts mission at8", count(
        f"Time: 8 {mid} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"), 1)
    ck("aircraft0 failure and survivor1 suspension at9.8829", (
        count("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added"),
        count("<TEACH-AIR-01,0> aborts its mission"),
        count(f"Time: 9.8829 {mid} mission suspended: <TEACH-AIR-01,1>")),
        (1, 1, 1))
    ck("initially unallocated aircraft2 allocated and prepares", (
        count(f"Time: 7 {mid} mission allocates system: <TEACH-AIR-01,2>"),
        count(f"Time: 9.8829 {mid} mission allocates system: <TEACH-AIR-01,2>"),
        count(f"Time: 9.8829 <TEACH-AIR-01,2> preparation started, mission: {mid}"),
        count(f"Time: 10.3829 <TEACH-AIR-01,2> preparation ended, mission: {mid}")),
        (0, 1, 1, 1))
    ck("failed aircraft0 repairs in parallel for same half hour", (
        count("Time: 9.8829 <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,0>"),
        count("Time: 9.8829  direct repair subtask 3 seqno 0 within system DIRP task 3 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours"),
        count("Time: 10.3829  direct repair subtask 3 seqno 0 within system DIRP task 3 on <TEACH-AIR-01,0> completed")),
        (1, 1, 1))
    ck("distinct #2 attaches, pair1/2 resumes at10.3829", (
        count(f"Time: 10.3829 {mid} system attached: <TEACH-AIR-01,2>"),
        count(f"Time: 10.3829 {mid} mission resumed: <TEACH-AIR-01,1>(Susp),<TEACH-AIR-01,2>(Susp)")),
        (1, 1))
    ck("repaired #0 is not the mission replacement", (
        count(f"Time: 10.3829 {mid} system attached: <TEACH-AIR-01,0>"),
        count(f"Time: 12 {mid} mission completed: <TEACH-AIR-01,1>,<TEACH-AIR-01,2>")),
        (0, 1))
    ck("fixed end at12 and terminal three ready", (
        count(f"Time: 12 {mid} mission success:"),
        count("Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :")),
        (1, 1))
    ck("only aircraft instances 0/1/2", sorted(set(re.findall(
        r"<TEACH-AIR-01,(\d+)>", event))), ["0", "1", "2"])

    report = load(RUN / "report-raw.json", native=True)
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    ck("32 aligned system/stock half-hour bins", (
        len(system), len(stock),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
        (32, 32, True, True))
    by = {r["STINT"]: r for r in system}
    ck("preparation starts/completions two plus one", (
        [(by[t]["NPSTA"], by[t]["NPSUC"]) for t in (7, 7.5, 9.5, 10)],
        sum(r["NPSTA"] or 0 for r in system),
        sum(r["NPSUC"] or 0 for r in system)),
        ([(2, 0), (0, 2), (1, 0), (0, 1)], 3, 3))
    ck("fractional suspended/repair/prep bins follow event times", tuple(
        near(by[9.5][k], (10-FAIL)/0.5) and
        near(by[10][k], (RESUME-10)/0.5)
        for k in ("NSYMS", "NSYRP", "NSYMP")), (True, True, True))
    ck("operation loss in finite gap", (
        near(by[9.5]["NSYMO"], 2*(FAIL-9.5)/0.5),
        near(by[10]["NSYMO"], 2*(10.5-RESUME)/0.5)),
        (True, True))
    integral = {k: sum((r[k] or 0)*0.5 for r in system)
                for k in ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP", "NSYMA")}
    ck("mission, suspended, repair and preparation aircraft-hours", tuple(
        near(integral[k], target) for k, target in
        (("NSYMO", 7), ("STACC", 7), ("NSYMS", 0.5),
         ("NSYRP", 0.5), ("NSYMP", 1.5), ("NSYMA", 10))),
        (True,)*6)
    ck("one failure and repair", (
        sum(r["NFAIL"] or 0 for r in system),
        sum(r["NREPT"] or 0 for r in system)), (1, 1))
    ck("stock demand/backorder zero", all((r[k] or 0) == 0 for r in stock
        for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("terminal ready three, no operation/repair", (
        system[-1]["NSYRY"], system[-1]["NSYMO"], system[-1]["NSYRP"]),
        (3, 0, 0))
    ck("summary MTMF/STMF .875, MSTF/MSUF zero", (
        summary["NREP"], summary["RTILW"], summary["RTIUP"],
        near(summary["MTMF"], .875), near(summary["STMF"], .875),
        summary["MSTF"], summary["MSUF"]),
        (1, 0, 16, True, True, 0, 0))

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a05-var02-prepared-spare-independent-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native calls",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
                   "B01_input": sha(B01), "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"),
                   "report_raw": sha(RUN / "report-raw.json")},
        "observed": {"failure_hour": FAIL, "failed_aircraft": "#0",
                     "surviving_aircraft": "#1", "distinct_replacement": "#2",
                     "replacement_preparation": [FAIL, RESUME],
                     "failed_aircraft_repair": [FAIL, RESUME],
                     "finite_suspension_hours": RESUME-FAIL,
                     "mission_end_hour": 12, "report_bins": 32,
                     "integrals_aircraft_hours": integral,
                     "failure_count": 1, "repair_count": 1,
                     "preparation_starts": 3, "preparation_completions": 3,
                     "stock_demand_count": 0, "terminal_ready_aircraft": 3,
                     "summary_MTMF": summary["MTMF"],
                     "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"]},
        "decision": "bounded_finite_suspension_distinct_system_replacement_accepted" if passed
                    else "review_rejected_pending_resolution",
        "limits": [
            "The failed #0 repairs during the same half hour; #2 is the distinct aircraft that rejoins the mission.",
            "This is a system-level ready spare, not stocked item or component replacement.",
            "Failure onset is stochastic and observed for one seed, not a predeclared deterministic interval.",
            "Hour-12 event success marker coexists with continuous ResultSummary MSTF/MSUF=0/0.",
            "No generic replacement rule, GUI visual verification or cross-engine equivalence."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
