"""Independent read-only replay of sealed A07 regenerative mission evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A02-single-aircraft-repeated-missions"
PARENT = PARENT_CASE / "native-input.json"
CHILD = CASE / "native-input.json"
RUN_ID = "a07-regenerative-relief-v100-ssh-20260930-01"
RUN = CASE / "runs" / RUN_ID
OUT = CASE / "review" / "independent-regenerative-2026-09-30.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
CHILD_SHA = "fed4f8343d203fc250d8b3508f3f5f9fe76ecbd1a86646d5965531d246b89240"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX emits trailing commas. Remove only those outside JSON strings.
        out, quoted, escaped = [], False, False
        for i, c in enumerate(raw):
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
            elif c == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
                continue
            else:
                out.append(c)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError((name, len(matches)))
    return matches[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, r)) for inst in t["instances"] for r in inst["rows"]]


def near(x: float, y: float, tol: float = 1e-5) -> bool:
    return math.isclose(x, y, abs_tol=tol, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        ok = actual == expected
        checks.append({"name": name, "passed": ok, **({} if ok else
            {"actual": repr(actual)[:700], "expected": repr(expected)[:700]})})

    contract, diff, parent, child = (load(p) for p in
        (CASE / "contract.json", CASE / "exact-diff.json", PARENT, CHILD))
    ck("signed A02 parent source bytes", sha(PARENT), PARENT_SHA)
    ck("frozen A07 child source bytes", sha(CHILD), CHILD_SHA)
    ck("installed manual source bytes", sha(MANUAL), MANUAL_SHA)
    ck("A02 signoff exists", (PARENT_CASE / "cli-scope-signoff-2026-09-29.md").is_file(), True)
    ck("contract source bindings", (contract["parent"]["input_sha256"],
        contract["native_input_sha256"], contract["source"]["manual_pdf_sha256"]),
       (PARENT_SHA, CHILD_SHA, MANUAL_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n for n in pt if pt[n] != ct[n]}
    ck("same table names", set(pt), set(ct))
    ck("exact five changed tables", changed,
       {"ProblemDescription", "SystemDeployment", "MissionType", "OperationProfile", "Unit"})
    ck("26 other tables unchanged", len(set(pt)-changed), 26)
    ck("all table schemas unchanged", all(pt[n]["columns"] == ct[n]["columns"] for n in pt), True)
    ck("diff parent/child hashes and table names", (diff["parent_sha256"],
       diff["child_sha256"], set(diff["changed_tables_only"]), diff["unchanged_table_count"]),
       (PARENT_SHA, CHILD_SHA, changed, 26))
    ck("diff exact before/after tables", all(diff["changed_tables"][n] ==
       {"before": pt[n], "after": ct[n]} for n in changed), True)
    pd, cd = rows(parent, "model", "SystemDeployment")[0], rows(child, "model", "SystemDeployment")[0]
    ck("deployed aircraft one to two only", {k: (v, cd[k]) for k, v in pd.items() if v != cd[k]},
       {"QTYPS": (1, 2)})
    pm, cm = rows(parent, "model", "MissionType")[0], rows(child, "model", "MissionType")[0]
    ck("mission duration and label only", {k: (v, cm[k]) for k, v in pm.items() if v != cm[k]},
       {"DESCR": ("Two-hour generic mission", "Four-hour relief mission"), "DURN": (2, 4)})
    ck("fixed mission phases and one-aircraft strength", (cm["MPAT"], cm["NOS"], cm["MNOS"],
       cm["TFOUT"], cm["TFRET"], cm["NOPER"]), (None, 1, 1, .25, .25, 1))
    old_profile, new_profile = rows(parent, "model", "OperationProfile"), rows(child, "model", "OperationProfile")
    ck("A02 scheduled profile at8/20/32", [(r["STIM"], r["ITYPE"]) for r in old_profile],
       [(8, "SCHEDULED"), (20, "SCHEDULED"), (32, "SCHEDULED")])
    ck("single regenerative profile", len(new_profile), 1)
    profile = new_profile[0]
    ck("regenerative profile values and empty initiation counts", (
       profile["STIM"], profile["ITYPE"], profile["IPER"], profile["IQTY"],
       profile["IQTYD"], profile["DTIM"], profile["SPRID"]),
       (8, "REGENERATIVE", 8, None, None, None, "BASIC-MISSION"))
    ck("unit and problem-description labels only", (
       {k for k, v in rows(parent, "model", "Unit")[0].items() if
        v != rows(child, "model", "Unit")[0][k]},
       {k for k, v in rows(parent, "model", "ProblemDescription")[0].items() if
        v != rows(child, "model", "ProblemDescription")[0][k]}),
       ({"DESCR"}, {"PDESC"}))
    ctl = rows(child, "model", "Control")[0]
    ck("horizon interval and seed retained", (ctl["SIMPE"], ctl["RCEND"], ctl["RCINT"], ctl["RSEED"]),
       (36, 36, .5, "1"))
    ck("zero system failure rate retained", rows(child, "model", "System")[0]["FRT"], 0)

    invocation, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("run input exact frozen child bytes", (sha(RUN / "input.json"),
       (RUN / "input.json").read_bytes() == CHILD.read_bytes()), (CHILD_SHA, True))
    ck("invocation identity and source hashes", (invocation["case_id"], invocation["run_id"],
       invocation["input_sha256"], invocation["parent_sha256"]),
       ("A07", RUN_ID, CHILD_SHA, PARENT_SHA))
    ck("session-0 SSH/mutex/GUI identity", (invocation["execution_mode"],
       invocation["session_id"], invocation["ssh_connection_present"],
       "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],
       invocation["queue_mutex"], invocation["gui"]["pid"],
       invocation["gui"]["session_id"], bool(invocation["gui"]["start_utc"])),
       ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    ck("runner SSH/mutex/GUI guard statements", all(s in runner for s in
       ("SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    ck("closure binds invocation bytes", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("closure clean and source stable", (closure["run_id"], closure["error"],
       closure["source_hashes_before"] == closure["source_hashes_after"]), (RUN_ID, None, True))
    ck("invocation source seal map equals closure", invocation["source_hashes_before"],
       closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": PARENT, "contract": CASE / "contract.json",
       "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
       "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        ck("source seal " + name, closure["source_hashes_before"][name], sha(path))
    ck("12 raw artifacts inventoried", (len(closure["raw"]), set(closure["raw"])),
       (12, {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}))
    for name, stamp in closure["raw"].items():
        p = RUN / name
        ck("raw seal " + name, (stamp["bytes"], stamp["sha256"]),
           (p.stat().st_size, sha(p)))
    ck("four CLI steps plus checker exit0 and GUI preserved", [
       (s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    ck("actual CLI arguments match invocation plan", [s["arguments"] for s in steps[:4]],
       [s["arguments"] for s in invocation["planned_commands"]])
    exported = load(RUN / "roundtrip-raw.json", native=True)
    populated = [t for t in child["model"]["tables"] if any(i["rows"] for i in t["instances"])]
    ck("13 row-containing source tables", len(populated), 13)
    ck("native export preserves all source business rows and columns", all(
       table(exported, "model", t["name"])["columns"] == t["columns"] and
       table(exported, "model", t["name"])["instances"] == t["instances"]
       for t in populated), True)
    roundtrip = load(RUN / "roundtrip-validation.json")
    ck("author roundtrip artifact corroborates independent comparison", (
       roundtrip["passed"], roundtrip["differences"], roundtrip["source_sha256"],
       roundtrip["roundtrip_sha256"]),
       (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("conversion zero errors two warnings", re.findall(
       r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog),
       [("0", "2", "0")])
    ck("warning codes #108/#126", sorted(re.findall(r"warning #(\d+)", runlog)),
       ["108", "126"])

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("native log 36-hour header", log.splitlines()[:2], ["SIMLOX LOG FILE", "36"])
    mission_pattern = re.compile(r"Time: (\d+(?:\.\d+)?) <BASIC-MISSION,TEACH-UNIT,0,(\d+),(\d+)> (.+)")
    mission_events = [(float(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
       for line in log.splitlines() if (m := mission_pattern.match(line))]
    ck("only four matching child IDs", {i for _, i, j, _ in mission_events} |
       {j for _, i, j, _ in mission_events}, {0, 1, 2, 3})
    def time_of(index: int, fragment: str) -> list[float]:
        return [t for t, i, j, e in mission_events if i == index and j == index and fragment in e]
    phases = {
       "created": [time_of(i, "regenerative mission created") for i in range(4)],
       "activated": [time_of(i, "mission activated") for i in range(4)],
       "started": [time_of(i, "mission starting, duration") for i in range(4)],
       "on_station": [time_of(i, "task starting") for i in range(4)],
       "back": [time_of(i, "task completed") for i in range(4)],
       "success": [time_of(i, "mission success") for i in range(4)],
       "completed": [time_of(i, "mission completed") for i in range(4)]}
    ck("four child creation times", phases["created"], [[7], [7], [9], [12]])
    ck("four activation times", phases["activated"], [[7], [9], [11], [13]])
    ck("four start times", phases["started"], [[8], [10], [12], [14]])
    ck("four OUT to ON STATION arrivals", phases["on_station"], [[9], [11], [13], [15]])
    ck("four ON STATION to BACK transitions", phases["back"], [[11], [13], [15], [15]])
    ck("four successful completion times", (phases["success"], phases["completed"]),
       ([[12], [14], [16], [16]], [[12], [14], [16], [16]]))
    ck("two resource waits and preassignments", (
       [time_of(i, "mission waiting") for i in (2, 3)],
       [time_of(i, "mission preassigns a system") for i in (2, 3)]),
       ([[11], [13]], [[12], [14]]))
    assigned = []
    for i in range(4):
        found = [re.search(r"<TEACH-AIR-01,(\d+)>", e).group(1)
           for _, j, k, e in mission_events if j == i and k == i and
           "mission starting, duration" in e]
        assigned.append(found)
    ck("alternating physical aircraft instances", assigned, [["0"], ["1"], ["0"], ["1"]])
    ck("zero-station final child, other three two hours", [
       phases["back"][i][0] - phases["on_station"][i][0] for i in range(4)],
       [2, 2, 2, 0])
    ck("successor ON STATION meets predecessor BACK", [
       phases["on_station"][i + 1][0] == phases["back"][i][0] for i in range(3)],
       [True, True, True])
    ck("no fifth child created", len(re.findall(r"regenerative mission created", log)), 4)
    ck("no failures, aborts, suspensions, repair or stock demand in log", all(
       s not in log.lower() for s in ("critical random failure added", "mission aborted",
       "mission suspended", "direct repair subtask", "backorder", "stock demand")), True)
    ck("two aircraft ready at hour16", "Time: 16 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log, True)

    report = load(RUN / "report-raw.json", native=True)
    system = rows(report, "report", "SystemResults")
    stock = rows(report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")[0]
    ck("72 aligned half-hour system/stock bins through36", (len(system), len(stock),
       all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
       all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
       (72, 72, True, True))
    def expected(h: float, spans: list[tuple[float, float, float]]) -> float:
        return next((value for lo, hi, value in spans if lo <= h < hi), 0)
    ck("per-bin operating aircraft occupancy", all(near(r["NSYMO"], expected(r["STINT"],
       [(8, 10, 1), (10, 16, 2)])) for r in system), True)
    ck("per-bin assigned aircraft occupancy", all(near(r["NSYMA"], expected(r["STINT"],
       [(7, 9, 1), (9, 16, 2)])) for r in system), True)
    ck("per-bin ready aircraft occupancy", all(near(r["NSYRY"], expected(r["STINT"],
       [(0, 7, 2), (7, 9, 1), (9, 16, 0), (16, 36, 2)])) for r in system), True)
    ck("two aircraft conserved in all bins", all(near(r["NSYA"], 2) for r in system), True)
    ck("STACC equals operating count in all bins", all(near(r["STACC"], r["NSYMO"]) for r in system), True)
    integrals = {k: sum((r[k] or 0)*.5 for r in system)
       for k in ("NSYMO", "STACC", "NSYMA", "NSYRY", "NSYMS", "NSYRP")}
    ck("operating and assigned aircraft-hours", (integrals["NSYMO"],
       integrals["STACC"], integrals["NSYMA"], integrals["NSYRY"]),
       (14, 14, 16, 56))
    ck("zero suspension and repair aircraft-hours", (integrals["NSYMS"],
       integrals["NSYRP"]), (0, 0))
    ck("zero failure, repair, preparation and PM report counts", tuple(sum((r[k] or 0)
       for r in system) for k in ("NFAIL", "NREPT", "NPSTA", "NPSUC", "NPMT")),
       (0, 0, 0, 0, 0))
    ck("zero stock demand/backorder in all bins", all((r[k] or 0) == 0 for r in stock
       for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    ck("full-run summary, STMF above one, regenerative MSTF/MSUF exclusion", (
       summary["NREP"], summary["RTILW"], summary["RTIUP"], summary["MTMF"],
       near(summary["STMF"], 7/6), summary["STMF"] > 1,
       summary["MSTF"], summary["MSUF"]), (1, 0, 36, 1, True, True, 0, 0))
    ck("terminal two ready, no active work", (system[-1]["NSYRY"],
       system[-1]["NSYMA"], system[-1]["NSYMO"], system[-1]["NSYRP"],
       stock[-1]["NBO"]), (2, 0, 0, 0, 0))

    passed = all(c["passed"] for c in checks)
    result = {"schema": "simlox-a07-regenerative-independent-readonly/v1",
       "reviewer": "Independent standard-library replay; no author code imported or native process invoked",
       "passed": passed, "passed_count": sum(c["passed"] for c in checks),
       "failed_count": sum(not c["passed"] for c in checks),
       "failed": [c for c in checks if not c["passed"]], "checks": checks,
       "hashes": {"parent_input": sha(PARENT), "child_input": sha(CHILD),
          "manual_pdf": sha(MANUAL), "invocation": sha(RUN / "invocation.json"),
          "closure": sha(RUN / "closure.json"), "model_log": sha(RUN / "model.log"),
          "report_raw": sha(RUN / "report-raw.json")},
       "observed": {"mission_children": 4, "aircraft_by_child": [int(x[0]) for x in assigned],
          "created_hours": [x[0] for x in phases["created"]],
          "start_hours": [x[0] for x in phases["started"]],
          "on_station_hours": [x[0] for x in phases["on_station"]],
          "back_hours": [x[0] for x in phases["back"]],
          "completion_hours": [x[0] for x in phases["completed"]],
          "on_station_durations_hours": [phases["back"][i][0] - phases["on_station"][i][0]
             for i in range(4)], "report_bins": 72,
          "system_integrals_aircraft_hours": integrals,
          "summary_STMF": summary["STMF"], "summary_MTMF": summary["MTMF"],
          "summary_MSTF": summary["MSTF"], "summary_MSUF": summary["MSUF"],
          "terminal_ready_aircraft": system[-1]["NSYRY"]},
       "manual_interpretation": {
          "physical_page_181": "A regenerative predecessor activates its successor before its on-station period ends; the final return may move forward to fit the period.",
          "physical_page_275": "IQTY and IQTYD are disallowed for regenerative initiation.",
          "physical_page_568": "STF/STMF may exceed one because requested regenerative system time is estimated from average sub-mission count; observed STACC can exceed that estimate.",
          "physical_page_553": "Regenerative missions are excluded from MSTF and MSUF because their number of individual starts is not defined in advance."},
       "decision": "bounded_regenerative_relief_accepted" if passed else "review_rejected_pending_resolution",
       "limits": [
          "The four child missions are one no-failure seed for a fixed template; early failure relief, resource shortage, other periods and other engines remain untested.",
          "The fourth child has OUT 14-15, zero ON STATION at hour15, and BACK 15-16; its success is an observed native event, not evidence of positive on-station work.",
          "STMF > 1 is consistent with the manual's estimated regenerative denominator; the 72 SystemResults STREQ fields are zero, so do not infer the denominator from those rows.",
          "MSTF=MSUF=0 are regenerative exclusions, not zero observed child starts or successes.",
          "GUI identity was guarded and preserved; visual content was not inspected."],
       "publication_state": "independent_review_only"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
       "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
