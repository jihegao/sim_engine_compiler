"""Independent read-only replay of A06.var03's sealed native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
PARENT_CASE = AIR / "A06-extendable-prepared-gap-v1.0.0"
STOP_CASE = AIR / "A06-var04-horizon-suspension-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
CHILD = CASE / "native-input.json"
B01 = AIR / "B01-fixed-preparation-v1.0.1" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
RUN_ID = "a06-var03-report-window-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
PARENT_RUN = PARENT_CASE / "runs" / "a06-extendable-prepared-gap-v100-ssh-20260930-01"
STOP_RUN = STOP_CASE / "runs" / "a06-var04-horizon-suspension-v100-ssh-20260930-01"
OUT = CASE / "review" / "independent-window-2026-09-30.json"
PARENT_SHA = "5b53aa2cbaacb283e15bb7e7852afba215ec7fe5961434c3c2ce6f06768125c7"
CHILD_SHA = "0fcd389734758af9b0c5c1b5ae4adfbca27135153954384b2cf7333ac4c9b3ff"
B01_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX JSON sometimes contains trailing commas. Strip only those outside strings.
        out, quoted, escaped = [], False, False
        for i, c in enumerate(text):
            if quoted:
                out.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
                out.append(c)
            elif c == "," and re.match(r"\s*[}\]]", text[i + 1:]):
                continue
            else:
                out.append(c)
        text = "".join(out)
    return json.loads(text)


def table(doc: dict, root: str, name: str) -> dict:
    found = [x for x in doc[root]["tables"] if x["name"] == name]
    if len(found) != 1:
        raise ValueError((name, len(found)))
    return found[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    fields = [x["name"] for x in t["columns"]]
    return [dict(zip(fields, r)) for inst in t["instances"] for r in inst["rows"]]


def close(a: float, b: float, tol: float = 1e-5) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=tol)


def main() -> None:
    checks = []

    def ck(name: str, actual: object, expected: object) -> None:
        ok = actual == expected
        checks.append({"name": name, "passed": ok, **({} if ok else
            {"actual": repr(actual)[:600], "expected": repr(expected)[:600]})})

    contract, parent, child = load(CASE / "contract.json"), load(PARENT), load(CHILD)
    ck("accepted parent bytes", sha(PARENT), PARENT_SHA)
    ck("frozen child bytes", sha(CHILD), CHILD_SHA)
    ck("B01 preparation reference bytes", sha(B01), B01_SHA)
    ck("installed manual bytes", sha(MANUAL), MANUAL_SHA)
    ck("accepted parent signoff", (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(), True)
    ck("contract source hashes", (contract["parent"]["input_sha256"],
        contract["native_input_sha256"], contract["source"]["manual_pdf_sha256"]),
       (PARENT_SHA, CHILD_SHA, MANUAL_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("same model table set", set(pt), set(ct))
    ck("exact changed tables", changed, {"Control", "ProblemDescription", "ResultCollection"})
    ck("schemas fixed", all(pt[n]["columns"] == ct[n]["columns"] for n in pt), True)
    pc, cc = rows(parent, "model", "Control")[0], rows(child, "model", "Control")[0]
    ck("only Control RCEND 16 to 12.5", {k: (v, cc[k]) for k, v in pc.items() if v != cc[k]},
       {"RCEND": (16, 12.5)})
    ck("SIMPE remains 16 and RCINT remains .5", (cc["SIMPE"], cc["RCINT"]), (16, .5))
    pr, cr = rows(parent, "model", "ResultCollection"), rows(child, "model", "ResultCollection")
    ck("two ResultCollection RCEND 16 to 12.5", [(a["RTYPE"], a["RCEND"], b["RCEND"])
        for a, b in zip(pr, cr)], [("MISSION", 16, 12.5), ("SYSTEM", 16, 12.5)])
    ck("ResultCollection changes only RCEND", all({k: v for k, v in a.items() if k != "RCEND"} ==
        {k: v for k, v in b.items() if k != "RCEND"} for a, b in zip(pr, cr)), True)
    pd, cd = rows(parent, "model", "ProblemDescription")[0], rows(child, "model", "ProblemDescription")[0]
    ck("description is label only", set(k for k in pd if pd[k] != cd[k]), {"PDESC"})
    ck("mission and seed unchanged", (rows(child, "model", "MissionType"), cc["RSEED"]),
       (rows(parent, "model", "MissionType"), pc["RSEED"]))

    inv, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("run copy exact child", (sha(RUN / "input.json"),
       (RUN / "input.json").read_bytes() == CHILD.read_bytes()), (CHILD_SHA, True))
    ck("invocation source and identity", (inv["case_id"], inv["variant"], inv["run_id"],
       inv["input_sha256"], inv["parent_sha256"]),
       ("A06", "window", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("session0 SSH/mutex/GUI", (inv["execution_mode"], inv["session_id"],
       inv["ssh_connection_present"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
       inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
       bool(inv["gui"]["start_utc"])),
       ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner guard text", all(s in runner for s in ("SSH_CONNECTION", "sshd.exe",
       "WaitOne(0)", "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("closure invocation hash", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure clean/stable", (closure["run_id"], closure["error"],
       closure["source_hashes_before"] == closure["source_hashes_after"]), (RUN_ID, None, True))
    ck("invocation/closure source map", inv["source_hashes_before"], closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": PARENT, "preparation_source": B01,
       "contract": CASE / "contract.json", "builder": CASE / "build.py",
       "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        ck("source seal " + name, closure["source_hashes_before"][name], sha(path))
    ck("raw file inventory", set(closure["raw"]),
       {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        p = RUN / name
        ck("raw bytes/hash " + name, (stamp["bytes"], stamp["sha256"]),
           (p.stat().st_size, sha(p)))
    ck("four native steps plus checker", [(s["name"], s["status"], s["exit_code"],
        s["gui_preserved"]) for s in steps], [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("actual arguments bound to plan", [s["arguments"] for s in steps[:4]],
       [s["arguments"] for s in inv["planned_commands"]])

    export = load(RUN / "roundtrip-raw.json", native=True)
    populated = [t for t in child["model"]["tables"] if any(i["rows"] for i in t["instances"])]
    ck("16 source row-containing tables", len(populated), 16)
    ck("all source business rows and schemas roundtrip", all(
       table(export, "model", t["name"])["columns"] == t["columns"] and
       table(export, "model", t["name"])["instances"] == t["instances"]
       for t in populated), True)
    rt = load(RUN / "roundtrip-validation.json")
    ck("native roundtrip checker file", (rt["passed"], rt["differences"],
       rt["source_sha256"], rt["roundtrip_sha256"]),
       (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion 0 errors 2 warnings 0 notes", re.findall(
       r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog),
       [("0", "2", "0")])
    ck("warnings #108/#126", sorted(re.findall(r"warning #(\d+)", runlog)), ["108", "126"])

    log = (RUN / "model.log").read_bytes()
    parent_log = (PARENT_RUN / "model.log").read_bytes()
    events = log.decode("utf-8-sig", errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    ck("complete event log byte-identical to parent", log, parent_log)
    ck("second failure and suspension at12.2431", (
       "Time: 12.2431 <TEACH-AIR-01,1> critical random failure added" in events,
       f"Time: 12.2431 {mission} mission suspended: <TEACH-AIR-01,2>" in events),
       (True, True))
    ck("replacement prep and failed-aircraft repair complete after window", (
       f"Time: 12.7431 <TEACH-AIR-01,0> preparation ended, mission: {mission}" in events,
       "Time: 12.7431  direct repair subtask 5 seqno 0 within system DIRP task 5 on <TEACH-AIR-01,1> completed" in events),
       (True, True))
    ck("same mission resumes after window and succeeds at13", (
       f"Time: 12.7431 {mission} system attached: <TEACH-AIR-01,0>" in events,
       f"Time: 12.7431 {mission} mission resumed: <TEACH-AIR-01,2>(Susp),<TEACH-AIR-01,0>(Susp)" in events,
       f"Time: 13 {mission} mission success:" in events,
       f"Time: 13 {mission} mission completed:" in events), (True, True, True, True))
    ck("three aircraft ready by event trace at13", "Time: 13 <TEACH-UNIT at <BASE-01,0>> systems ready: 3" in events, True)

    report = load(RUN / "report-raw.json", native=True)
    parent_report = load(PARENT_RUN / "report-raw.json", native=True)
    stop_report = load(STOP_RUN / "report-raw.json", native=True)
    sys = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    psys = rows(parent_report, "report", "SystemResults")
    pstock = rows(parent_report, "report", "StockTotalResults")
    ssys = rows(stop_report, "report", "SystemResults")
    sstock = rows(stop_report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    stop_summary = rows(stop_report, "report", "ResultSummary")[0]
    ck("25 half-hour report bins end12.5", (len(sys), len(stock), all(
       x["STINT"] == i/2 and x["ETINT"] == (i+1)/2 for i, x in enumerate(sys)),
       all(x["STINT"] == i/2 and x["ETINT"] == (i+1)/2 for i, x in enumerate(stock))),
       (25, 25, True, True))
    ck("system report exact parent first25", sys, psys[:25])
    ck("stock report exact parent first25", stock, pstock[:25])
    ck("stock report same as stop control", stock, sstock)
    ck("system first24 same as stop control", sys[:24], ssys[:24])
    ck("final-bin SYDT/NSYDT completed downtime distinction", {
       k: (ssys[24][k], sys[24][k]) for k in sys[24] if ssys[24][k] != sys[24][k]},
       {"SYDT": (None, .5), "NSYDT": (0, 1)})
    integrals = {k: sum((r[k] or 0)*.5 for r in sys)
       for k in ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP")}
    stop_integrals = {k: sum((r[k] or 0)*.5 for r in ssys) for k in integrals}
    ck("window integrals same as stop control", integrals, stop_integrals)
    ck("fractional aircraft-hour integrals", [close(integrals[k], v) for k, v in (
       ("NSYMO", 7.48628825), ("STACC", 7.48628825),
       ("NSYMS", .75685586), ("NSYRP", .75685586),
       ("NSYMP", 1.75685586))], [True]*5)
    ck("window failure/repair/prep counters", tuple(sum((r[k] or 0) for r in sys)
       for k in ("NFAIL", "NREPT", "NPSTA", "NPSUC")), (2, 1, 4, 3))
    ck("stock demand/backorder zero in window", all((r[k] or 0) == 0 for r in stock
       for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("full-simulation summary scope", (summary["RTILW"], summary["RTIUP"],
       summary["MTMF"], summary["STMF"], summary["MSTF"], summary["MSUF"]),
       (0, 16, 1, 1, 0, 0))
    ck("summary differs from stop control", (stop_summary["RTIUP"],
       close(stop_summary["MTMF"], .935786), summary["MTMF"]), (12.5, True, 1))
    ck("manual p645 completed-period semantics", all(s in __import__("pypdf").PdfReader(str(MANUAL)).pages[644].extract_text()
       for s in ("where the system maintenance and the related downtime period start",
                 "not concluded at the", "simulation period")), True)

    passed = all(x["passed"] for x in checks)
    result = {
       "schema": "simlox-a06-var03-window-independent-readonly/v1",
       "reviewer": "Independent raw replay; pypdf used only for installed manual page text; no author validator import or native invocation",
       "passed": passed, "passed_count": sum(x["passed"] for x in checks),
       "failed_count": sum(not x["passed"] for x in checks),
       "failed": [x for x in checks if not x["passed"]], "checks": checks,
       "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
           "invocation": sha(RUN / "invocation.json"), "closure": sha(RUN / "closure.json"),
           "model_log": sha(RUN / "model.log"), "report_raw": sha(RUN / "report-raw.json"),
           "parent_model_log": sha(PARENT_RUN / "model.log"),
           "parent_report_raw": sha(PARENT_RUN / "report-raw.json"),
           "stop_model_log": sha(STOP_RUN / "model.log"),
           "stop_report_raw": sha(STOP_RUN / "report-raw.json")},
       "observed": {"simulation_end_hour": 16, "result_window_end_hour": 12.5,
           "second_suspension_hour": 12.2431, "resumption_hour": 12.7431,
           "mission_completion_hour": 13, "report_bins": 25,
           "window_integrals_aircraft_hours": integrals,
           "window_failures": 2, "window_completed_repairs": 1,
           "window_preparation_starts": 4, "window_preparation_completions": 3,
           "full_simulation_summary_MTMF": summary["MTMF"],
           "full_simulation_summary_STMF": summary["STMF"],
           "final_window_bin_SYDT": sys[24]["SYDT"],
           "final_window_bin_NSYDT": sys[24]["NSYDT"]},
       "decision": "bounded_report_window_crossing_accepted" if passed else "review_rejected_pending_resolution",
       "limits": [
           "The 25 SystemResults bins end at 12.5, while ResultSummary RTIUP=16 and the event log capture the full simulation; these scopes must remain separate.",
           "The final SystemResults bin contains interval averages, not a point-in-time state at hour 12.5.",
           "SYDT=.5/NSYDT=1 in the 12.0-12.5 bin reflects a completed downtime period registered at its start; it does not show maintenance completed by 12.5.",
           "Post-window resumption and completion are supported by model.log, not by the truncated interval bins.",
           "One fixed seed and an observed stochastic failure timeline; other result-window boundaries, GUI visual content, and cross-engine equivalence remain untested."],
       "publication_state": "independent_review_only"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
       "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
