"""Independent read-only replay of A06.var04 horizon inside second suspension."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A06-extendable-prepared-gap-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
PARENT_RUN = PARENT_CASE / "runs" / "a06-extendable-prepared-gap-v100-ssh-20260930-01"
B01 = CASE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
CHILD = CASE / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
RUN_ID = "a06-var04-horizon-suspension-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-horizon-2026-09-30.json"
PARENT_SHA = "5b53aa2cbaacb283e15bb7e7852afba215ec7fe5961434c3c2ce6f06768125c7"
CHILD_SHA = "45d034bc31e24655bbae47d4deb8d47c362e5b35ca0e8d5c538788a9dae5b0da"
B01_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
STOP = 12.5
SECOND_FAILURE = 12.2431


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


def table(doc: dict, root: str, name: str) -> dict:
    matches = [x for x in doc[root]["tables"] if x["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"{name}: {len(matches)} tables")
    return matches[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    fields = [c["name"] for c in t["columns"]]
    return [dict(zip(fields, row)) for inst in t["instances"] for row in inst["rows"]]


def near(a: float, b: float, tol: float = 1e-4) -> bool:
    return math.isclose(a, b, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        ok = actual == expected
        checks.append({"name": name, "passed": ok, **({} if ok else {
            "actual": repr(actual)[:700], "expected": repr(expected)[:700]})})

    contract, parent, child = read(CASE / "contract.json"), read(PARENT), read(CHILD)
    ck("accepted A06 parent SHA", sha(PARENT), PARENT_SHA)
    ck("frozen horizon child SHA", sha(CHILD), CHILD_SHA)
    ck("B01 preparation source SHA", sha(B01), B01_SHA)
    ck("manual PDF SHA", sha(MANUAL), MANUAL_SHA)
    ck("accepted A06 parent signoff exists", (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(), True)
    ck("contract source bindings", (
        contract["parent"]["input_sha256"], contract["native_input_sha256"],
        contract["source"]["manual_pdf_sha256"]),
        (PARENT_SHA, CHILD_SHA, MANUAL_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    ck("model table set same", set(pt), set(ct))
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("exact three changed tables", changed,
       {"Control", "ProblemDescription", "ResultCollection"})
    ck("28 unchanged tables", len(set(pt)-changed), 28)
    ck("table schemas unchanged", all(pt[n]["columns"] == ct[n]["columns"] for n in pt), True)
    oldc, newc = rows(parent, "model", "Control")[0], rows(child, "model", "Control")[0]
    ck("exact Control SIMPE/RCEND 16-to-12.5", [
        (k, v, newc[k]) for k, v in oldc.items() if v != newc[k]],
        [("SIMPE", 16, STOP), ("RCEND", 16, STOP)])
    ck("both ResultCollection RCEND 16-to-12.5", [
        (a["RTYPE"], a["RCEND"], b["RCEND"]) for a, b in zip(
            rows(parent, "model", "ResultCollection"),
            rows(child, "model", "ResultCollection"))],
        [("MISSION", 16, STOP), ("SYSTEM", 16, STOP)])
    ck("only descriptive label otherwise", [
        (k, v, rows(child, "model", "ProblemDescription")[0][k])
        for k, v in rows(parent, "model", "ProblemDescription")[0].items()
        if v != rows(child, "model", "ProblemDescription")[0][k]],
        [("PDESC", "A06 extendable four-hour prepared-replacement probe",
          "A06 extendable mission stopped during second suspension")])
    m = rows(child, "model", "MissionType")[0]
    ck("extendable four-hour mission and fixed seed retained", (
        m["MPAT"], m["DURN"], m["NOS"], m["MNOS"],
        rows(child, "model", "SystemDeployment")[0]["QTYPS"],
        rows(child, "model", "System")[0]["FRT"],
        newc["RSEED"], newc["RCINT"]),
        ("EXTENDABLE", 4, 2, 2, 3, 300000, "1", .5))

    inv, closure, steps = [read(RUN / n) for n in
                           ("invocation.json", "closure.json", "steps.json")]
    ck("run input exact source bytes", (
        sha(RUN / "input.json"), (RUN / "input.json").read_bytes() == CHILD.read_bytes()),
        (CHILD_SHA, True))
    ck("invocation identity/source binding", (
        inv["case_id"], inv["variant"], inv["run_id"],
        inv["input_sha256"], inv["parent_sha256"]),
        ("A06", "horizon", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("session0 SSH mutex GUI identity", (
        inv["execution_mode"], inv["session_id"], inv["ssh_connection_present"],
        "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
        inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
        bool(inv["gui"]["start_utc"])),
        ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner preflight/queue/GUI assertions", all(s in runner for s in (
        "SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("invocation SHA in closure", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure clean, source stable", (
        closure["run_id"], closure["error"],
        closure["source_hashes_before"] == closure["source_hashes_after"]),
        (RUN_ID, None, True))
    ck("invocation/closure source map equal", inv["source_hashes_before"],
       closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": PARENT, "preparation_source": B01,
               "contract": CASE / "contract.json", "builder": CASE / "build.py",
               "checker": CASE / "check_roundtrip.py",
               "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        ck(f"source seal {name}", closure["source_hashes_before"][name], sha(path))
    ck("all raw files in closure", set(closure["raw"]),
       {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})
    for name, stamp in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name} bytes/hash", (stamp["bytes"], stamp["sha256"]),
           (path.stat().st_size, sha(path)))
    ck("four CLI steps plus checker exit0/GUI preserved", [
        (x["name"], x["status"], x["exit_code"], x["gui_preserved"])
        for x in steps], [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("CLI arguments match invocation", [x["arguments"] == y["arguments"]
       for x, y in zip(steps[:4], inv["planned_commands"])], [True]*4)

    export = read(RUN / "roundtrip-raw.json", native=True)
    source_tables = [t for t in child["model"]["tables"]
                     if any(inst["rows"] for inst in t["instances"])]
    ck("16 source row-containing tables", len(source_tables), 16)
    ck("native export preserves source business rows", all(
        table(export, "model", t["name"])["columns"] == t["columns"] and
        table(export, "model", t["name"])["instances"] == t["instances"]
        for t in source_tables), True)
    rt = read(RUN / "roundtrip-validation.json")
    ck("roundtrip checker agreement", (
        rt["passed"], rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
        (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    conv = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion 0 errors/2 warnings", re.findall(
        r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",
        conv), [("0", "2", "0")])
    ck("warning codes 108/126", sorted(re.findall(r"warning #(\d+)", conv)),
       ["108", "126"])

    child_lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    parent_lines = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    event = "\n".join(child_lines)
    mid = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def count(s: str) -> int:
        return event.count(s)
    ck("native event prefix exactly matches accepted parent after horizon header",
       (child_lines[0], child_lines[1], child_lines[2:] ==
        parent_lines[2:2+len(child_lines)-2]),
       ("SIMLOX LOG FILE", "12.5", True))
    ck("start8, first gap9.8829-10.3829", (
        count(f"Time: 8 {mid} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>"),
        count(f"Time: 9.8829 {mid} mission suspended: <TEACH-AIR-01,1>"),
        count(f"Time: 10.3829 {mid} mission resumed: <TEACH-AIR-01,1>(Susp),<TEACH-AIR-01,2>(Susp)")),
        (1, 1, 1))
    ck("second failure/suspension at12.2431", (
        count("Time: 12.2431 <TEACH-AIR-01,1> critical random failure added"),
        count(f"Time: 12.2431 {mid} mission suspended: <TEACH-AIR-01,2>")),
        (1, 1))
    ck("replacement #0 preparation still open at stop", (
        count(f"Time: 12.2431 <TEACH-AIR-01,0> preparation started, mission: {mid}"),
        count(f"Time: 12.7431 <TEACH-AIR-01,0> preparation ended, mission: {mid}")),
        (1, 0))
    ck("failed #1 repair still open at stop", (
        count("Time: 12.2431 <TEACH-AIR-01,BASE-01,0> System to repair <TEACH-AIR-01,1>"),
        count("direct repair subtask 5 seqno 0 within system DIRP task 5 on <TEACH-AIR-01,1> completed")),
        (1, 0))
    ck("survivor #2 remains suspended, no second attachment/resume", (
        count("<TEACH-AIR-01,2> suspended on mission"),
        count(f"Time: 12.7431 {mid} system attached: <TEACH-AIR-01,0>"),
        count(f"Time: 12.7431 {mid} mission resumed:")),
        (1, 0, 0))
    ck("no mission completion or success before cutoff", (
        count(f"{mid} mission success:"), count(f"{mid} mission completed:")),
        (0, 0))

    report = read(RUN / "report-raw.json", native=True)
    parent_report = read(PARENT_RUN / "report-raw.json", native=True)
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    parent_system = rows(parent_report, "report", "SystemResults")
    parent_stock = rows(parent_report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    ck("25 aligned half-hour bins ending12.5", (
        len(system), len(stock),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
        all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
        (25, 25, True, True))
    ck("stock report exact prefix of accepted parent", stock, parent_stock[:25])
    ck("system report first24 bins exact parent prefix", system[:24], parent_system[:24])
    terminal_delta = {k: (parent_system[24][k], system[24][k]) for k in system[24]
                      if parent_system[24][k] != system[24][k]}
    ck("last bin only completion-based downtime differs", terminal_delta,
       {"SYDT": (.5, None), "NSYDT": (1, 0)})
    final_bin = system[-1]
    ck("last bin averages indicate part-bin suspension/repair/prep", (
        near(final_bin["NSYMS"], 2*(STOP-SECOND_FAILURE)),
        near(final_bin["NSYRP"], 2*(STOP-SECOND_FAILURE)),
        near(final_bin["NSYMP"], 2*(STOP-SECOND_FAILURE)),
        final_bin["NFAIL"], final_bin["NREPT"],
        final_bin["NPSTA"], final_bin["NPSUC"]),
        (True, True, True, 1, 0, 1, 0))
    integral = {k: sum((r[k] or 0)*.5 for r in system)
                for k in ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP")}
    ck("fractional report integrals", tuple(
        near(integral[k], target) for k, target in
        (("NSYMO", 7.48628825), ("STACC", 7.48628825),
         ("NSYMS", .75685586), ("NSYRP", .75685586),
         ("NSYMP", 1.75685586))), (True,)*5)
    ck("failure/repair/preparation counters", (
        sum(r["NFAIL"] or 0 for r in system),
        sum(r["NREPT"] or 0 for r in system),
        sum(r["NPSTA"] or 0 for r in system),
        sum(r["NPSUC"] or 0 for r in system)), (2, 1, 4, 3))
    ck("stock demand/backorder zero", all((r[k] or 0) == 0 for r in stock
        for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("report summary partial active fraction", (
        summary["NREP"], summary["RTILW"], summary["RTIUP"],
        near(summary["MTMF"], .935786), near(summary["STMF"], .935786),
        summary["MSTF"], summary["MSUF"]),
        (1, 0, STOP, True, True, 0, 0))
    inferred_remaining = 4 - integral["NSYMO"]/2
    ck("inferred remaining active time only", near(inferred_remaining, .256855875), True)

    passed = all(x["passed"] for x in checks)
    result = {
        "schema": "simlox-a06-var04-horizon-independent-readonly/v1",
        "reviewer": "Independent standard-library raw replay; no author imports or native invocation",
        "passed": passed, "passed_count": sum(x["passed"] for x in checks),
        "failed_count": sum(not x["passed"] for x in checks),
        "failed": [x for x in checks if not x["passed"]], "checks": checks,
        "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
                   "invocation": sha(RUN / "invocation.json"),
                   "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"),
                   "report_raw": sha(RUN / "report-raw.json"),
                   "parent_model_log": sha(PARENT_RUN / "model.log"),
                   "parent_report_raw": sha(PARENT_RUN / "report-raw.json")},
        "observed": {"stop_hour": STOP,
                     "second_suspension_start": SECOND_FAILURE,
                     "mission_completion_before_stop": False,
                     "second_replacement_preparation_open": True,
                     "second_failed_aircraft_repair_open": True,
                     "survivor_suspended_in_event_trace": True,
                     "report_bins": 25,
                     "report_integrals_aircraft_hours": integral,
                     "failure_count": 2, "completed_repair_count": 1,
                     "preparation_starts": 4, "preparation_completions": 3,
                     "stock_demand_count": 0,
                     "reported_remaining_active_hours": None,
                     "inferred_remaining_active_hours": inferred_remaining,
                     "summary_MTMF": summary["MTMF"], "summary_STMF": summary["STMF"]},
        "decision": "bounded_horizon_inside_second_suspension_accepted" if passed
                    else "review_rejected_pending_resolution",
        "limits": [
            "The last SystemResults row is a 12.0-12.5 interval average, not a point-in-time terminal state.",
            "Remaining active time is inferred from DURN minus integrated NSYMO/2, not a native remaining-work field.",
            "The final-bin SYDT/NSYDT values differ from the longer parent because completion lies beyond this horizon; do not infer zero downtime.",
            "One seed and a stop chosen from an observed stochastic failure; other cutoff boundaries are untested.",
            "No GUI visual inspection or cross-engine equivalence."
        ],
        "publication_state": "independent_review_only"
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
                      "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
