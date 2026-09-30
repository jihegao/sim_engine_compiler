"""Independent standard-library replay of A05.var03 MNOSA=1 raw evidence."""
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
CHILD = CASE / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
RUN_ID = "a05-var03-mnosa-one-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-mnosa-2026-09-30.json"
PARENT_SHA = "b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d"
CHILD_SHA = "586e9b765dd5ab69e578fa3d2ed18262b5b6148fc48862c14e6c95846241d1fa"
B01_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
FIRST, FIRST_READY = 9.8829, 10.3829
SECOND, SECOND_READY = 11.1325, 11.6325


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        out = []
        quoted = escape = False
        for i, ch in enumerate(raw):
            if quoted:
                out.append(ch)
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
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
        raise ValueError(f"{name} table count {len(found)}")
    return found[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    fields = [c["name"] for c in t["columns"]]
    return [dict(zip(fields, row)) for inst in t["instances"] for row in inst["rows"]]


def near(a: float, b: float, tol: float = 1e-4) -> bool:
    return math.isclose(a, b, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        passed = actual == expected
        checks.append({"name": name, "passed": passed, **({} if passed else {
            "actual": repr(actual)[:650], "expected": repr(expected)[:650]})})

    contract, parent, child = read(CASE / "contract.json"), read(PARENT), read(CHILD)
    ck("accepted prepared-spare parent SHA", sha(PARENT), PARENT_SHA)
    ck("frozen MNOSA child SHA", sha(CHILD), CHILD_SHA)
    ck("accepted B01 preparation source SHA", sha(B01), B01_SHA)
    ck("installed manual fingerprint", sha(MANUAL), MANUAL_SHA)
    ck("parent signoff exists", (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(), True)
    ck("contract binds parent/child/manual", (
        contract["parent"]["input_sha256"], contract["native_input_sha256"],
        contract["source"]["manual_pdf_sha256"]),
        (PARENT_SHA, CHILD_SHA, MANUAL_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    ck("source table set identical", set(pt), set(ct))
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("exact two changed tables", changed, {"ProblemDescription", "MissionType"})
    ck("29 unchanged tables", len(set(pt)-changed), 29)
    ck("all schemas unchanged", all(pt[n]["columns"] == ct[n]["columns"]
                                    for n in pt), True)
    before, after = rows(parent, "model", "MissionType")[0], rows(child, "model", "MissionType")[0]
    ck("only MNOSA null-to-one", [(k, v, after[k]) for k, v in before.items()
                                  if v != after[k]], [("MNOSA", None, 1)])
    ck("only description label changed", (
        [(k, v, rows(child, "model", "ProblemDescription")[0][k]) for k, v in
         rows(parent, "model", "ProblemDescription")[0].items()
         if v != rows(child, "model", "ProblemDescription")[0][k]]),
        [("PDESC", "A05 continuous four-hour three-aircraft fixed-preparation probe",
          "A05 continuous four-hour MNOSA-one continue control")])
    ctl = rows(child, "model", "Control")[0]
    ck("fixed mission/start/minimum/seed retained", (
        after["MPAT"], after["NOS"], after["MNOS"], after["MNOSA"], after["DURN"],
        rows(child, "model", "SystemDeployment")[0]["QTYPS"],
        rows(child, "model", "System")[0]["FRT"],
        rows(child, "model", "OperationProfile")[0]["STIM"],
        ctl["SIMPE"], ctl["RCINT"], ctl["RSEED"]),
        ("CONTINUOUS", 2, 2, 1, 4, 3, 300000, 8, 16, .5, "1"))
    ck("preparation and repair tables unchanged", (
        ct["MissionPreparation"], ct["Tasks"], ct["SystemRepair"]),
        (pt["MissionPreparation"], pt["Tasks"], pt["SystemRepair"]))
    ck("no stocked item source", all(not rows(child, "model", n) for n in
       ("Item", "ItemStructure", "StockAllocation", "ItemReplacement")), True)

    inv, closure, steps = [read(RUN / n) for n in
                           ("invocation.json", "closure.json", "steps.json")]
    ck("copied input exact bytes", (
        sha(RUN / "input.json"), (RUN / "input.json").read_bytes() == CHILD.read_bytes()),
        (CHILD_SHA, True))
    ck("invocation identity and source", (
        inv["case_id"], inv["variant"], inv["run_id"],
        inv["input_sha256"], inv["parent_sha256"]),
        ("A05", "mnosa", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("session0 SSH queue and GUI guard", (
        inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"],
        "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
        inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
        bool(inv["gui"]["start_utc"])),
        ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner has preflight/queue/GUI checks", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("closure binds invocation", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure no error/source stable", (
        closure["run_id"], closure["error"],
        closure["source_hashes_before"] == closure["source_hashes_after"]),
        (RUN_ID, None, True))
    ck("invocation/closure source agreement", inv["source_hashes_before"],
       closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": PARENT, "preparation_source": B01,
               "contract": CASE / "contract.json", "builder": CASE / "build.py",
               "checker": CASE / "check_roundtrip.py",
               "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in sources.items():
        ck(f"source seal {key}", closure["source_hashes_before"][key], sha(path))
    ck("raw closure file set", set(closure["raw"]),
       {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        p = RUN / name
        ck(f"raw seal {name}", (stamp["bytes"], stamp["sha256"]),
           (p.stat().st_size, sha(p)))
    ck("four CLI steps plus checker exit0/GUI preserved", [
        (x["name"], x["status"], x["exit_code"], x["gui_preserved"])
        for x in steps], [(name, "completed", 0, True) for name in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("CLI arguments bound to plan", [x["arguments"] == y["arguments"] for x, y
        in zip(steps[:4], inv["planned_commands"])], [True]*4)

    export = read(RUN / "roundtrip-raw.json", native=True)
    source_tables = [t for t in child["model"]["tables"]
                     if any(i["rows"] for i in t["instances"])]
    ck("16 source row-containing tables", len(source_tables), 16)
    ck("all source business rows exact in export", all(
        table(export, "model", t["name"])["columns"] == t["columns"] and
        table(export, "model", t["name"])["instances"] == t["instances"]
        for t in source_tables), True)
    rt = read(RUN / "roundtrip-validation.json")
    ck("checker agrees with native roundtrip", (
        rt["passed"], rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
        (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    conversion = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion 0 errors, 2 warnings", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        conversion), [("0", "2", "0")])
    ck("warnings #108 and #126", sorted(re.findall(r"warning #(\d+)", conversion)),
       ["108", "126"])

    event = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def count(fragment: str) -> int:
        return event.count(fragment)
    ck("formation launches on time 8-12", (
        count(f"Time: 8 {mid} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"),
        count(f"Time: 12 {mid} mission completed: <TEACH-AIR-01,2>,<TEACH-AIR-01,0>")),
        (1, 1))
    ck("two failures, affected aircraft0 then1", (
        count("critical random failure added"),
        count("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added"),
        count("Time: 11.1325 <TEACH-AIR-01,1> critical random failure added")),
        (2, 1, 1))
    ck("neither failure suspends or resumes whole mission", (
        count("mission suspended:"), count("mission resumed:")), (0, 0))
    ck("both failed aircraft abort individually", (
        count("<TEACH-AIR-01,0> aborts its mission"),
        count("<TEACH-AIR-01,1> aborts its mission")), (1, 1))
    ck("first #2 replacement prepares 9.8829-10.3829 and attaches", (
        count(f"Time: 9.8829 {mid} mission allocates system: <TEACH-AIR-01,2>"),
        count(f"Time: 9.8829 <TEACH-AIR-01,2> preparation started, mission: {mid}"),
        count(f"Time: 10.3829 <TEACH-AIR-01,2> preparation ended, mission: {mid}"),
        count(f"Time: 10.3829 {mid} system attached: <TEACH-AIR-01,2>")),
        (1, 1, 1, 1))
    ck("first #0 direct repair 9.8829-10.3829", (
        count("Time: 9.8829 <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,0>"),
        count("Time: 10.3829 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>")),
        (1, 1))
    ck("second #0 replacement prepares 11.1325-11.6325 and attaches", (
        count(f"Time: 11.1325 {mid} mission allocates system: <TEACH-AIR-01,0>"),
        count(f"Time: 11.1325 <TEACH-AIR-01,0> preparation started, mission: {mid}"),
        count(f"Time: 11.6325 <TEACH-AIR-01,0> preparation ended, mission: {mid}"),
        count(f"Time: 11.6325 {mid} system attached: <TEACH-AIR-01,0>")),
        (1, 1, 1, 1))
    ck("second #1 direct repair 11.1325-11.6325", (
        count("Time: 11.1325 <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,1>"),
        count("Time: 11.6325 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,1>")),
        (1, 1))
    ck("terminal mission success marker and three ready", (
        count(f"Time: 12 {mid} mission success:"),
        count("Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :")),
        (1, 1))
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
    ck("first continuation interval one survivor, not suspended", (
        near(by[9.5]["NSYMO"], 1+(FIRST-9.5)/.5),
        near(by[10]["NSYMO"], 1+(10.5-FIRST_READY)/.5),
        by[9.5]["NSYMS"], by[10]["NSYMS"]),
        (True, True, 0, 0))
    ck("second continuation interval one survivor, not suspended", (
        near(by[11]["NSYMO"], 1+(SECOND-11)/.5),
        near(by[11.5]["NSYMO"], 1+(12-SECOND_READY)/.5),
        by[11]["NSYMS"], by[11.5]["NSYMS"]),
        (True, True, 0, 0))
    integral = {k: sum((r[k] or 0)*.5 for r in system) for k in
                ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP", "NSYMA")}
    ck("operation/repair/prep integrals", tuple(
        near(integral[k], value) for k, value in
        (("NSYMO", 7), ("STACC", 7), ("NSYMS", 0),
         ("NSYRP", 1), ("NSYMP", 2), ("NSYMA", 10))), (True,)*6)
    ck("two failures and repairs, four prep starts/completions", (
        sum(r["NFAIL"] or 0 for r in system),
        sum(r["NREPT"] or 0 for r in system),
        sum(r["NPSTA"] or 0 for r in system),
        sum(r["NPSUC"] or 0 for r in system)), (2, 2, 4, 4))
    ck("stock demand/backorder zero", all((r[k] or 0) == 0 for r in stock
        for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("terminal three ready, no repair/operation", (
        system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYMO"]),
        (3, 0, 0))
    ck("summary MTMF1 STMF.875, no MSTF/MSUF", (
        summary["NREP"], summary["RTILW"], summary["RTIUP"],
        summary["MTMF"], near(summary["STMF"], .875),
        summary["MSTF"], summary["MSUF"]),
        (1, 0, 16, 1, True, 0, 0))
    prior_report = read(PARENT_CASE / "runs" /
                        "a05-var02-prepared-spare-v100-ssh-20260930-01" /
                        "report-raw.json", native=True)
    prior = rows(prior_report, "report", "SystemResults")
    ck("parent default-MNOS control had half-hour suspension", (
        near(sum((r["NSYMS"] or 0)*.5 for r in prior), .5),
        sum(r["NFAIL"] or 0 for r in prior)), (True, 1))

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a05-var03-mnosa-independent-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native calls",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
                   "manual": sha(MANUAL), "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"),
                   "report_raw": sha(RUN / "report-raw.json")},
        "observed": {"failures": [{"hour": FIRST, "aircraft": 0,
                                     "replacement": 2, "attached": FIRST_READY},
                                    {"hour": SECOND, "aircraft": 1,
                                     "replacement": 0, "attached": SECOND_READY}],
                     "mission_suspension_events": 0,
                     "mission_continues_with_one_aircraft_in_each_gap": True,
                     "mission_end_hour": 12, "report_bins": 32,
                     "integrals_aircraft_hours": integral,
                     "failure_count": 2, "repair_count": 2,
                     "preparation_starts": 4, "preparation_completions": 4,
                     "stock_demand_count": 0, "terminal_ready_aircraft": 3,
                     "summary_MTMF": summary["MTMF"], "summary_STMF": summary["STMF"],
                     "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"]},
        "decision": "bounded_mnosa_one_continuation_accepted" if passed
                    else "review_rejected_pending_resolution",
        "limits": [
            "The installed manual's physical page 264 defines MNOSA as the continuation minimum; MNOS still governs mission start and resumption after suspension.",
            "This one seed tests continuation during two observed failures. It does not test initial start below MNOS or resumption below MNOS.",
            "Failure times are stochastic observations, not a deterministic schedule; no generic failure or replacement policy is inferred.",
            "Continuous event success at hour12 coexists with ResultSummary MSTF/MSUF=0/0; retain both observations.",
            "No GUI visual inspection or cross-engine equivalence."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
