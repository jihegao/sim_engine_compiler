"""Independent read-only replay of the A06.var01 no-interruption run."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT_CASE = CASE.parent / "A05-continuous-baseline-v1.0.1"
PARENT = PARENT_CASE / "native-continuous.json"
CHILD = CASE / "native-input.json"
RUN_ID = "a06-var01-no-interruption-v100-ssh-20260930-02"
RUN = CASE / "runs" / RUN_ID
CONTROL_RUN = PARENT_CASE / "runs" / "a05-continuous-four-hour-v101-ssh-20260930-01"
FAILED_RUN = CASE / "runs" / "a06-var01-no-interruption-v100-ssh-20260930-01"
OUT = CASE / "review" / "independent-no-interruption-2026-09-30.json"
PARENT_SHA = "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea"
CHILD_SHA = "6d508cb4af5f997785be802c0527cd6f50918cde78714406ae2106e7b421ca6c"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        # Native exports permit trailing commas. Remove them only outside quoted strings.
        out, inside, escape = [], False, False
        for i, char in enumerate(raw):
            if inside:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    inside = False
            elif char == '"':
                inside = True
                out.append(char)
            elif char == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
                continue
            else:
                out.append(char)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    matches = [t for t in doc[root]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError((name, len(matches)))
    return matches[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    fields = [c["name"] for c in t["columns"]]
    return [dict(zip(fields, r)) for inst in t["instances"] for r in inst["rows"]]


def near(value: float, expected: float) -> bool:
    return math.isclose(value, expected, abs_tol=1e-6, rel_tol=0)


def main() -> None:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        passed = actual == expected
        checks.append({"name": name, "passed": passed, **({} if passed else
            {"actual": repr(actual)[:600], "expected": repr(expected)[:600]})})

    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    parent, child = load(PARENT), load(CHILD)
    check("accepted A05 source hash", sha(PARENT), PARENT_SHA)
    check("frozen A06 child hash", sha(CHILD), CHILD_SHA)
    check("manual hash", sha(MANUAL), MANUAL_SHA)
    check("accepted A05 signoff exists", (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").is_file(), True)
    check("contract source bindings", (contract["parent"]["input_sha256"],
       contract["native_input_sha256"], contract["source"]["manual_pdf_sha256"]),
       (PARENT_SHA, CHILD_SHA, MANUAL_SHA))
    pt = {t["name"]: t for t in parent["model"]["tables"]}
    ct = {t["name"]: t for t in child["model"]["tables"]}
    changed = {n for n in pt if pt[n] != ct[n]}
    check("same model table names", set(pt), set(ct))
    check("exactly two changed tables", changed, {"ProblemDescription", "MissionType"})
    check("29 other tables identical", len(set(pt)-changed), 29)
    check("schemas identical", all(pt[n]["columns"] == ct[n]["columns"] for n in pt), True)
    pm, cm = rows(parent, "model", "MissionType")[0], rows(child, "model", "MissionType")[0]
    check("sole mission field delta", {k: (v, cm[k]) for k, v in pm.items() if v != cm[k]},
       {"MPAT": ("CONTINUOUS", "EXTENDABLE")})
    pp, cp = rows(parent, "model", "ProblemDescription")[0], rows(child, "model", "ProblemDescription")[0]
    check("sole description delta", set(k for k in pp if pp[k] != cp[k]), {"PDESC"})
    check("mission length/strength unchanged", (cm["DURN"], cm["NOS"], cm["MNOS"]), (4, 2, 2))
    check("exact-diff input bindings", (diff["parent_sha256"], diff["child_sha256"]),
       (PARENT_SHA, CHILD_SHA))
    check("exact-diff changed table names", set(diff["changed_tables_only"]), changed)
    check("exact-diff tables truly equal source", all(diff["changed_tables"][n] ==
       {"before": pt[n], "after": ct[n]} for n in changed), True)

    inv, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    check("run input copy exact", (sha(RUN / "input.json"),
       (RUN / "input.json").read_bytes() == CHILD.read_bytes()), (CHILD_SHA, True))
    check("invocation identity and source", (inv["case_id"], inv["variant"], inv["run_id"],
       inv["input_sha256"], inv["parent_sha256"]),
       ("A06", "no-interruption", RUN_ID, CHILD_SHA, PARENT_SHA))
    check("session-0 SSH, mutex, GUI identity", (inv["execution_mode"], inv["session_id"],
       inv["ssh_connection_present"], "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
       inv["queue_mutex"], inv["gui"]["pid"], inv["gui"]["session_id"],
       bool(inv["gui"]["start_utc"])),
       ("ssh_cli_v1", 0, True, True, "Global\\SimloxIssue18NativeQueue", 13340, 1, True))
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("runner SSH/queue/GUI guard statements", all(s in runner for s in
       ("SSH_CONNECTION", "sshd.exe", "WaitOne(0)",
        "Global\\SimloxIssue18NativeQueue", "13340", "Assert-Gui")), True)
    check("closure invocation hash", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    check("closure clean and source unchanged", (closure["run_id"], closure["error"],
       closure["source_hashes_before"] == closure["source_hashes_after"]), (RUN_ID, None, True))
    check("invocation/closure source map", inv["source_hashes_before"], closure["source_hashes_before"])
    sources = {"input": CHILD, "parent": PARENT, "contract": CASE / "contract.json",
       "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
       "runner_script": CASE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        check("source seal " + name, closure["source_hashes_before"][name], sha(path))
    check("12 raw artifact inventory", (len(closure["raw"]), set(closure["raw"])),
       (12, {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}))
    for name, record in closure["raw"].items():
        path = RUN / name
        check("raw seal " + name, (record["bytes"], record["sha256"]),
           (path.stat().st_size, sha(path)))
    check("four CLI steps plus checker successful, GUI preserved", [
       (s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(n, "completed", 0, True) for n in
        ("import", "export", "calc", "jsonreport", "check_import_export")])
    check("step arguments same as invocation plan", [s["arguments"] for s in steps[:4]],
       [s["arguments"] for s in inv["planned_commands"]])
    check("first attempt explicitly excluded", (load(FAILED_RUN / "closure.json")["error"],
       [s["exit_code"] for s in load(FAILED_RUN / "steps.json")]),
       ("roundtrip checker exit=1", [0, 0, 0, 0, 1]))

    exported = load(RUN / "roundtrip-raw.json", native=True)
    source_tables = [t for t in child["model"]["tables"] if any(i["rows"] for i in t["instances"])]
    check("13 source row-containing tables", len(source_tables), 13)
    check("export exactly preserves source business rows and schemas", all(
       table(exported, "model", t["name"])["columns"] == t["columns"] and
       table(exported, "model", t["name"])["instances"] == t["instances"]
       for t in source_tables), True)
    rt = load(RUN / "roundtrip-validation.json")
    check("checker artifact corroborates independent roundtrip", (rt["passed"],
       rt["differences"], rt["source_sha256"], rt["roundtrip_sha256"]),
       (True, [], CHILD_SHA, sha(RUN / "roundtrip-raw.json")))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("conversion 0 errors, 2 warnings, 0 notes", re.findall(
       r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", runlog),
       [("0", "2", "0")])
    check("warning codes #108 and #126", sorted(re.findall(r"warning #(\d+)", runlog)),
       ["108", "126"])

    event_bytes = (RUN / "model.log").read_bytes()
    control_event_bytes = (CONTROL_RUN / "model.log").read_bytes()
    events = event_bytes.decode("utf-8-sig", errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    check("event log byte-identical to accepted A05 continuous", event_bytes, control_event_bytes)
    check("prepared pair and mission start8", all(s in events for s in (
       f"Time: 7 <TEACH-AIR-01,0> preparation ended, mission: {mission}",
       f"Time: 7 <TEACH-AIR-01,1> preparation ended, mission: {mission}",
       f"Time: 8 {mission} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")), True)
    check("both aircraft complete and mission succeeds at12", all(s in events for s in (
       f"Time: 12 {mission} task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
       f"Time: 12 {mission} mission success:",
       f"Time: 12 {mission} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")), True)
    check("no suspension, failure, repair, stock request", all(s not in events.lower() for s in
       ("mission suspended", "critical random failure added", "direct repair subtask",
        "backorder", "stock demand")), True)
    check("both aircraft ready after turnaround", "Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in events, True)

    report = load(RUN / "report-raw.json", native=True)
    control_report = load(CONTROL_RUN / "report-raw.json", native=True)
    system, control_system = rows(report, "report", "SystemResults"), rows(control_report, "report", "SystemResults")
    stock, control_stock = rows(report, "report", "StockTotalResults"), rows(control_report, "report", "StockTotalResults")
    summary, control_summary = rows(report, "report", "ResultSummary"), rows(control_report, "report", "ResultSummary")
    check("32 aligned half-hour system and stock bins through16", (len(system), len(stock),
       all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(system)),
       all(r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for i, r in enumerate(stock))),
       (32, 32, True, True))
    check("system ledger exactly equals continuous control", system, control_system)
    check("stock ledger exactly equals continuous control", stock, control_stock)
    check("summary exactly equals continuous control", summary, control_summary)
    check("summary full simulation and success fraction", (summary[0]["RTILW"],
       summary[0]["RTIUP"], summary[0]["MTMF"], summary[0]["STMF"],
       summary[0]["MSTF"], summary[0]["MSUF"]), (0, 16, 1, 1, 0, 0))
    integrals = {k: sum((r[k] or 0)*.5 for r in system)
       for k in ("NSYMO", "STACC", "NSYMS", "NSYRP", "NSYMP")}
    check("eight aircraft-hours operating, zero suspended/repair/prep", tuple(
       near(integrals[k], v) for k, v in
       (("NSYMO", 8), ("STACC", 8), ("NSYMS", 0), ("NSYRP", 0), ("NSYMP", 0))),
       (True, True, True, True, True))
    check("no failures, completed repairs or prep tasks in bins", tuple(
       sum((r[k] or 0) for r in system) for k in
       ("NFAIL", "NREPT", "NPSTA", "NPSUC")), (0, 0, 0, 0))
    check("zero stock demand/backorders", all((r[k] or 0) == 0 for r in stock
       for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NWT")), True)
    check("terminal readiness final bin", (system[-1]["NSYRY"], system[-1]["NSYA"],
       system[-1]["NSYMO"], system[-1]["NSYMS"]), (2, 2, 0, 0))
    child_description = rows(report, "report", "ProblemDescription")
    control_description = rows(control_report, "report", "ProblemDescription")
    check("raw report differs only in descriptive label", (
       {t["name"] for t in report["report"]["tables"] if t !=
        table(control_report, "report", t["name"])},
       child_description[0]["PDESC"] == cp["PDESC"],
       control_description[0]["PDESC"] == pp["PDESC"]),
       ({"ProblemDescription"}, True, True))

    passed = all(c["passed"] for c in checks)
    result = {"schema": "simlox-a06-var01-no-interruption-independent-readonly/v1",
       "reviewer": "Standalone Python standard-library raw replay; no author imports or native invocation",
       "passed": passed, "passed_count": sum(c["passed"] for c in checks),
       "failed_count": sum(not c["passed"] for c in checks),
       "failed": [c for c in checks if not c["passed"]], "checks": checks,
       "hashes": {"input": sha(CHILD), "parent_input": sha(PARENT),
          "invocation": sha(RUN / "invocation.json"), "closure": sha(RUN / "closure.json"),
          "model_log": sha(RUN / "model.log"), "report_raw": sha(RUN / "report-raw.json"),
          "control_model_log": sha(CONTROL_RUN / "model.log"),
          "control_report_raw": sha(CONTROL_RUN / "report-raw.json")},
       "observed": {"accepted_run": RUN_ID, "excluded_run": FAILED_RUN.name,
          "mission_start": 8, "mission_completion": 12,
          "report_bins": 32, "integrated_aircraft_hours": integrals,
          "final_ready_aircraft": system[-1]["NSYRY"],
          "summary_MTMF": summary[0]["MTMF"], "summary_STMF": summary[0]["STMF"],
          "summary_MSTF": summary[0]["MSTF"], "summary_MSUF": summary[0]["MSUF"]},
       "decision": "bounded_no_interruption_equality_accepted" if passed else
          "review_rejected_pending_resolution",
       "limits": [
          "This is a one-seed no-failure two-aircraft example, not generic equivalence of EXTENDABLE and CONTINUOUS under interruption.",
          "The event log says mission success, while both patterns' ResultSummary MSTF/MSUF fields are zero; those fields are not used as mission-success counts here.",
          "Report files differ in ProblemDescription label even though event log, summary, SystemResults and StockTotalResults match.",
          "The earlier -01 run failed its roundtrip checker and is excluded; this review accepts only sealed -02.",
          "No GUI visual inspection or cross-engine equivalence."],
       "publication_state": "independent_review_only"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "passed_count": result["passed_count"],
       "failed": result["failed"], "output": str(OUT)}))


if __name__ == "__main__":
    main()
