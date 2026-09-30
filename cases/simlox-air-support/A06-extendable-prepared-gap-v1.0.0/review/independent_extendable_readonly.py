"""Independent standard-library raw replay of A06 extendable prepared gap."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A05-var02-prepared-spare-probe-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
B01 = CASE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
CHILD = CASE / "native-input.json"
RUN_ID = "a06-extendable-prepared-gap-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-extendable-2026-09-30.json"
PARENT_SHA = "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d"
B01_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
CHILD_SHA = "5b53aa2cbaacb283e15bb7e7852afba215ec7fe5961434c3c2ce6f06768125c7"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
GAPS = ((9.8829, 10.3829), (12.2431, 12.7431))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p: Path, native: bool = False) -> dict:
    raw = p.read_text(encoding="utf-8-sig")
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


def table(d: dict, root: str, name: str) -> dict:
    found = [t for t in d[root]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"{name} table count {len(found)}")
    return found[0]


def rows(d: dict, root: str, name: str) -> list[dict]:
    t = table(d, root, name)
    fields = [c["name"] for c in t["columns"]]
    return [dict(zip(fields, row)) for inst in t["instances"] for row in inst["rows"]]


def near(x: float, y: float, tol: float = 1e-4) -> bool:
    return math.isclose(x, y, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        ok = actual == expected
        checks.append({"name": name, "passed": ok, **({} if ok else {
            "actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract, parent, child = read(CASE / "contract.json"), read(PARENT), read(CHILD)
    ck("accepted continuous parent SHA", sha(PARENT), PARENT_SHA)
    ck("frozen extendable child SHA", sha(CHILD), CHILD_SHA)
    ck("accepted B01 preparation SHA", sha(B01), B01_SHA)
    ck("installed manual SHA", sha(MANUAL), MANUAL_SHA)
    ck("accepted parent signoff exists", (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(), True)
    ck("contract binds source/manual hashes", (
        contract["parent"]["input_sha256"], contract["native_input_sha256"],
        contract["source"]["manual_pdf_sha256"]),
        (PARENT_SHA, CHILD_SHA, MANUAL_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    ck("model table set identical", set(pt), set(ct))
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("exact two changed tables", changed, {"ProblemDescription", "MissionType"})
    ck("29 unchanged tables", len(set(pt)-changed), 29)
    ck("table schemas identical", all(pt[n]["columns"] == ct[n]["columns"] for n in pt), True)
    pmission, mission = rows(parent, "model", "MissionType")[0], rows(child, "model", "MissionType")[0]
    ck("sole mission field MPAT continuous-to-extendable", [
        (k, v, mission[k]) for k, v in pmission.items() if v != mission[k]],
        [("MPAT", "CONTINUOUS", "EXTENDABLE")])
    ck("sole other field descriptive label", [
        (k, v, rows(child, "model", "ProblemDescription")[0][k])
        for k, v in rows(parent, "model", "ProblemDescription")[0].items()
        if v != rows(child, "model", "ProblemDescription")[0][k]],
        [("PDESC", "A05 continuous four-hour three-aircraft fixed-preparation probe",
          "A06 extendable four-hour prepared-replacement probe")])
    ctl = rows(child, "model", "Control")[0]
    ck("four-hour two-aircraft requirement and 16h horizon retained", (
        mission["DURN"], mission["NOS"], mission["MNOS"],
        rows(child, "model", "SystemDeployment")[0]["QTYPS"],
        rows(child, "model", "System")[0]["FRT"],
        rows(child, "model", "OperationProfile")[0]["STIM"],
        ctl["SIMPE"], ctl["RCINT"], ctl["RSEED"]),
        (4, 2, 2, 3, 300000, 8, 16, .5, "1"))
    ck("preparation and direct repair rows unchanged", (
        ct["MissionPreparation"], ct["Tasks"], ct["SystemRepair"]),
        (pt["MissionPreparation"], pt["Tasks"], pt["SystemRepair"]))
    ck("no item stock/replacement source", all(not rows(child, "model", n) for n in
       ("Item", "ItemStructure", "StockAllocation", "ItemReplacement")), True)

    inv, closure, steps = [read(RUN / n) for n in
                           ("invocation.json", "closure.json", "steps.json")]
    ck("copied run input byte-identical", (
        sha(RUN / "input.json"), (RUN / "input.json").read_bytes() == CHILD.read_bytes()),
        (CHILD_SHA, True))
    ck("invocation identity and parent", (
        inv["case_id"], inv["variant"], inv["run_id"],
        inv["input_sha256"], inv["parent_sha256"]),
        ("A06", "extendable", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("session0 SSH, mutex, GUI PID13340", (
        inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"],
        "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
        inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
        bool(inv["gui"]["start_utc"])),
        ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner contains SSH/queue/GUI assertions", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("invocation SHA sealed", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure no error and source stable", (
        closure["run_id"], closure["error"],
        closure["source_hashes_before"] == closure["source_hashes_after"]),
        (RUN_ID, None, True))
    ck("invocation/closure source hashes agree", inv["source_hashes_before"],
       closure["source_hashes_before"])
    paths = {"input": CHILD, "parent": PARENT, "preparation_source": B01,
             "contract": CASE / "contract.json", "builder": CASE / "build.py",
             "checker": CASE / "check_roundtrip.py",
             "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in paths.items():
        ck(f"source seal {key}", closure["source_hashes_before"][key], sha(path))
    ck("all raw files in closure", set(closure["raw"]),
       {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (stamp["bytes"], stamp["sha256"]),
           (path.stat().st_size, sha(path)))
    ck("four native steps plus checker exit0/GUI preserved", [
        (x["name"], x["status"], x["exit_code"], x["gui_preserved"])
        for x in steps], [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("CLI arguments match plan", [x["arguments"] == y["arguments"] for x, y
        in zip(steps[:4], inv["planned_commands"])], [True]*4)

    export = read(RUN / "roundtrip-raw.json", native=True)
    populated = [t for t in child["model"]["tables"]
                 if any(i["rows"] for i in t["instances"])]
    ck("16 source row-containing tables", len(populated), 16)
    ck("native export preserves all source business rows", all(
        table(export, "model", t["name"])["columns"] == t["columns"] and
        table(export, "model", t["name"])["instances"] == t["instances"]
        for t in populated), True)
    rt = read(RUN / "roundtrip-validation.json")
    ck("roundtrip checker agrees", (
        rt["passed"], rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
        (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion 0 errors, 2 warnings, 0 notes", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        conversion), [("0", "2", "0")])
    ck("warnings #108 and #126", sorted(re.findall(r"warning #(\d+)", conversion)),
       ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def count(s: str) -> int:
        return event.count(s)
    ck("start at8 for four active hours", count(
        f"Time: 8 {mid} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"), 1)
    ck("two failure times and identities", (
        count("critical random failure added"),
        count("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added"),
        count("Time: 12.2431 <TEACH-AIR-01,1> critical random failure added")),
        (2, 1, 1))
    cycles = [
        ("first", "9.8829", "10.3829", "0", "1", "2"),
        ("second", "12.2431", "12.7431", "1", "2", "0")]
    for label, start, end, failed, survivor, replacement in cycles:
        ck(f"{label} failure aborts failed participant only", count(
            f"<TEACH-AIR-01,{failed}> aborts its mission"), 1)
        ck(f"{label} suspension and resume times/identities", (
            count(f"Time: {start} {mid} mission suspended: <TEACH-AIR-01,{survivor}>"),
            count(f"Time: {end} {mid} mission resumed: <TEACH-AIR-01,{survivor}>(Susp),<TEACH-AIR-01,{replacement}>(Susp)")),
            (1, 1))
        ck(f"{label} replacement prepares and attaches after half hour", (
            count(f"Time: {start} {mid} mission allocates system: <TEACH-AIR-01,{replacement}>"),
            count(f"Time: {start} <TEACH-AIR-01,{replacement}> preparation started, mission: {mid}"),
            count(f"Time: {end} <TEACH-AIR-01,{replacement}> preparation ended, mission: {mid}"),
            count(f"Time: {end} {mid} system attached: <TEACH-AIR-01,{replacement}>")),
            (1, 1, 1, 1))
        ck(f"{label} failed aircraft repaired in parallel", (
            count(f"Time: {start} <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,{failed}>"),
            count(f"Time: {end} <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,{failed}>")),
            (1, 1))
    ck("hour13 mission end after both gaps", (
        count(f"Time: 13 {mid} mission success:"),
        count(f"Time: 13 {mid} mission completed: <TEACH-AIR-01,2>,<TEACH-AIR-01,0>"),
        count(f"Time: 12 {mid} mission completed:")),
        (1, 1, 0))
    ck("all three aircraft ready at13", count(
        "Time: 13 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :"), 1)
    ck("only deployed aircraft instances0/1/2", sorted(set(re.findall(
        r"<TEACH-AIR-01,(\d+)>", event))), ["0", "1", "2"])

    report = read(RUN / "report-raw.json", native=True)
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    ck("32 aligned half-hour system and stock bins", (
        len(system), len(stock),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
        (32, 32, True, True))
    by = {r["STINT"]: r for r in system}
    ck("first gap fractional suspension and operation bins", (
        near(by[9.5]["NSYMS"], (10-GAPS[0][0])/.5),
        near(by[10]["NSYMS"], (GAPS[0][1]-10)/.5),
        near(by[9.5]["NSYMO"], 2*(GAPS[0][0]-9.5)/.5),
        near(by[10]["NSYMO"], 2*(10.5-GAPS[0][1])/.5)),
        (True, True, True, True))
    ck("second gap fractional suspension and operation bins", (
        near(by[12]["NSYMS"], (12.5-GAPS[1][0])/.5),
        near(by[12.5]["NSYMS"], (GAPS[1][1]-12.5)/.5),
        near(by[12]["NSYMO"], 2*(GAPS[1][0]-12)/.5, tol=5e-4),
        near(by[12.5]["NSYMO"], 2*(13-GAPS[1][1])/.5, tol=5e-4)),
        (True, True, True, True))
    integral = {k: sum((r[k] or 0)*.5 for r in system)
                for k in ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP", "NSYMA")}
    ck("four active hours from five elapsed minus two half-hour gaps", (
        near((13-8)-sum(end-start for start, end in GAPS), 4),
        near(integral["NSYMO"]/2, 4)), (True, True))
    ck("mission/suspension/repair/preparation integrals", tuple(
        near(integral[k], value) for k, value in
        (("NSYMO", 8), ("STACC", 8), ("NSYMS", 1),
         ("NSYRP", 1), ("NSYMP", 2), ("NSYMA", 12))),
        (True,)*6)
    ck("two failures/repairs, four preparations", (
        sum(r["NFAIL"] or 0 for r in system),
        sum(r["NREPT"] or 0 for r in system),
        sum(r["NPSTA"] or 0 for r in system),
        sum(r["NPSUC"] or 0 for r in system)), (2, 2, 4, 4))
    ck("stock demand/backorder zero", all((r[k] or 0) == 0 for r in stock
        for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("terminal three ready", (system[-1]["NSYRY"], system[-1]["NSYMO"],
                                  system[-1]["NSYRP"]), (3, 0, 0))
    ck("report summary MTMF/STMF1, MSTF/MSUF0", (
        summary["NREP"], summary["RTILW"], summary["RTIUP"],
        summary["MTMF"], summary["STMF"], summary["MSTF"], summary["MSUF"]),
        (1, 0, 16, 1, 1, 0, 0))
    prior_report = read(PARENT_CASE / "runs" /
                        "a05-var02-prepared-spare-v100-ssh-20260930-01" /
                        "report-raw.json", native=True)
    prior = rows(prior_report, "report", "SystemResults")
    ck("continuous parent stopped at12 with one half-hour gap", (
        near(sum((r["NSYMS"] or 0)*.5 for r in prior), .5),
        near(sum((r["NSYMO"] or 0)*.5 for r in prior), 7)),
        (True, True))

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a06-extendable-independent-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native calls",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
                   "manual": sha(MANUAL), "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"),
                   "report_raw": sha(RUN / "report-raw.json")},
        "observed": {"mission_start": 8, "suspension_intervals": GAPS,
                     "total_suspended_hours": 1, "mission_completion": 13,
                     "active_mission_hours": integral["NSYMO"]/2,
                     "report_bins": 32, "integrals_aircraft_hours": integral,
                     "failure_count": 2, "repair_count": 2,
                     "preparation_starts": 4, "preparation_completions": 4,
                     "stock_demand_count": 0, "terminal_ready_aircraft": 3,
                     "summary_MTMF": summary["MTMF"], "summary_STMF": summary["STMF"],
                     "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"]},
        "decision": "bounded_extendable_gap_compensation_accepted" if passed
                    else "review_rejected_pending_resolution",
        "limits": [
            "The installed manual (physical pp179, 266) describes EXTENDABLE completion after requested active time, with suspension gaps compensated.",
            "One stochastic fixed-seed run; the second failure after the parent's fixed end is observed, not predeclared.",
            "This does not test no-interruption, unfinished-at-horizon, crossing report-window, or generic multi-interruption policy.",
            "Hour13 event success marker coexists with continuous-family ResultSummary MSTF/MSUF=0/0.",
            "No GUI visual inspection or cross-engine equivalence."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
