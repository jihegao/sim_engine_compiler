"""Independent standard-library replay for A13.var06 v1.0.1 role matrix."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
PARENT = AIR / "A13-start-dependence-v1.0.0" / "dependent-input.json"
VARIANTS = ("fixed-fixed", "prec-cont-control", "prec-cont-dependency",
            "dep-cont-control", "dep-cont-dependency")
RUNS = {v: CASE / "runs" / f"a13-var06-{v}-v101-20261001-01" for v in VARIANTS}
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS = []
REJECTED = "prec-cont-dependency"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path):
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, char in enumerate(raw):
        if quoted:
            out.append(char)
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == '"': quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == ',' and raw[i+1:].lstrip().startswith(('}', ']')):
            continue
        else:
            out.append(char)
    return json.loads(''.join(out))


def check(name, condition, detail=None):
    CHECKS.append({"name": name, "passed": bool(condition),
                   **({"detail": detail} if detail is not None else {})})


def close(actual, expected):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=1e-6, rel_tol=0)


def tables(doc, root="model"):
    result = {}
    for t in doc[root]["tables"]:
        assert t["name"] not in result
        result[t["name"]] = t
    return result


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def delta(a, b):
    return {name: {"before": a.get(name), "after": b.get(name)}
            for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name)}


def occupancy(a, b, periods):
    return sum(max(0., min(b, end) - max(a, start))*weight
               for start, end, weight in periods)/(b-a)


def expected_system(variant, field, a, b):
    fixed = variant == "fixed-fixed"
    suspended = variant == "dep-cont-dependency"
    follow_end = 14 if fixed else 12
    assigned = occupancy(a, b, [(7, 12, 1), (9, follow_end, 1)])
    operating = occupancy(a, b, [(8, 12, 1)] +
                          ([(12, 14, 1)] if fixed else [] if suspended else [(10, 12, 1)]))
    susp = occupancy(a, b, [(10, 12, 1)]) if suspended else 0
    values = {"UNID": "Total over all Units", "SID": "Total over all Systems",
              "STINT": a, "ETINT": b, "NSYRY": 2-assigned, "NSYMA": assigned,
              "NSYMO": operating, "NSYMS": susp,
              "NSYMR": assigned-operating-susp, "NSYA": 2,
              "FTMO": operating/2, "STACC": operating, "SYDT": None}
    return values.get(field, 0)


def source_checks():
    contract, manifest = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check("frozen revised contract SHA and identity", sha(CASE / "contract.json") ==
          "91c140b3ec55ea1f9290587570313f05ab695a09aebb4f625e26101803b62288" and
          contract["case_id"] == "A13" and contract["variant_id"] == "A13.var06" and
          contract["case_version"] == "1.0.1-candidate" and contract["publication_state"] == "not_published")
    check("installed manual and dictionary SHA", sha(manual) == contract["source"]["manual_sha256"] and
          sha(dictionary) == contract["source"]["dictionary_sha256"])
    check("manual FIXED-role conflict retained", "Pages 188 and 289" in contract["source"]["conflict"] and
          "page 287" in contract["source"]["conflict"])
    check("accepted A13 parent source and signoff", sha(PARENT) == contract["parent"]["input_sha256"] ==
          manifest["parent_sha256"] and
          "accepted" in (CASE / contract["parent"]["signoff"]).read_text(encoding="utf-8").lower())
    check("exact diff frozen SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    parent = tables(native(PARENT))
    sources = {v: tables(native(CASE / f"{v}-input.json")) for v in VARIANTS}
    for v, source in sources.items():
        check(f"{v} source SHA", sha(CASE / f"{v}-input.json") ==
              contract["inputs_sha256"][v] == manifest["inputs_sha256"][v])
        check(f"{v} exact full parsed-table parent delta", delta(parent, source) ==
              manifest["changed_tables"][v])
        role = {r["MTID"]: r for r in records(source["MissionType"])}
        continuous = "RECON" if v.startswith("prec-cont") else "FOLLOW" if v.startswith("dep-cont") else None
        check(f"{v} exact MPAT/travel role", set(role) == {"RECON", "FOLLOW"} and
              all(role[mt]["MPAT"] == ("CONTINUOUS" if mt == continuous else None) and
                  role[mt]["TFOUT"] == (None if mt == continuous else .25) and
                  role[mt]["TFRET"] == (None if mt == continuous else .25)
                  for mt in role))
    for role in ("prec-cont", "dep-cont"):
        control = sources[role + "-control"]
        dependent = sources[role + "-dependency"]
        check(f"{role} matched pair only dependence/description", set(delta(control, dependent)) ==
              {"MissionDependence", "ProblemDescription"} and
              "MissionDependence" not in control and
              len(rows(dependent["MissionDependence"])) == 1)
    check("fixed reference dependence retained", rows(sources["fixed-fixed"]["MissionDependence"]) ==
          rows(parent["MissionDependence"]))
    return contract


def run_checks(v, contract):
    run = RUNS[v]
    inv, closure = read(run / "invocation.json"), read(run / "closure.json")
    source = CASE / f"{v}-input.json"
    before = closure["source_hashes_before"]
    check(f"{v} run/input identity", inv["run_id"] == closure["run_id"] == run.name and
          inv["variant"] == v and inv["case_id"] == "A13" and
          inv["case_version"] == contract["case_version"] and
          Path(inv["original_run_dir"]).resolve() == run.resolve() and
          inv["input_sha256"] == sha(source) == sha(run / "input.json"))
    check(f"{v} source stable through native run", before == closure["source_hashes_after"] ==
          inv["source_hashes_before"] and before["input"] == sha(source) and
          before["parent"] == sha(PARENT) and before["contract"] == sha(CASE / "contract.json") and
          before["builder"] == sha(CASE / "build.py") and
          before["exact_diff"] == sha(CASE / "exact-diff.json") and
          before["diff_checker"] == sha(CASE / "describe_diff.py") and
          before["checker"] == sha(CASE / "check_roundtrip.py") and
          before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    check(f"{v} runtime/invocation sealed", closure["invocation_sha256"] == sha(run / "invocation.json") and
          closure["error"] is None and all(inv[k + "_sha256"] == before[k] for k in
          ("parent", "contract", "builder", "checker", "python", "runner_script", "simlox_exe")))
    check(f"{v} complete raw inventory", set(closure["raw"]) ==
          {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
    for name, meta in closure["raw"].items():
        check(f"{v} raw SHA {name}", (run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"])
    check(f"{v} session0 SSH/GUI/mutex", inv["session_id"] == 0 and
          inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    steps = read(run / "steps.json")
    expected = (["import", "export", "calc"] +
                ([] if v == REJECTED else ["jsonreport"]) +
                ["check_import_export"])
    check(f"{v} guarded ordered native steps", [s["name"] for s in steps] == expected and
          all(s["status"] == ("calc_observed" if s["name"] == "calc" else "completed") and
              s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps) and
          all(steps[i]["completed_utc"] <= steps[i+1]["started_utc"] for i in range(len(steps)-1)) and
          all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(3)) and
          steps[-1]["arguments"] == inv["planned_check"]["arguments"] and
          (v == REJECTED or steps[3]["arguments"] == inv["planned_report"]["arguments"]))
    wanted, exported = tables(native(source)), tables(native(run / "roundtrip-raw.json"))
    populated = {name for name, t in wanted.items() if rows(t)}
    check(f"{v} populated source-table count", len(populated) ==
          (13 if v.endswith("control") else 14))
    for name in sorted(populated):
        check(f"{v} exact source roundtrip {name}", wanted[name] == exported.get(name))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if v == REJECTED:
        check("nonfixed precedent exact START converter error #223",
              "Form: MissionDependence\nrec 1: (error #223) Dependency type equal to Start requires that precedent mission is FIXED:  TEACH-UNIT/RECON//8.000000" in
              calc.replace("\r\n", "\n") and calc.count("(error #223)") == 1)
        check("nonfixed precedent one error, warnings108/126", "Errors: 1, Warnings: 2, Notes: 0" in calc and
              calc.count("warning #108") == calc.count("warning #126") == 1 and
              calc.count("(error #") == 1)
        check("nonfixed precedent unusable SXO/no report", (run / "model.sxo").stat().st_size == 4 and
              not (run / "model.log").exists() and not (run / "report-raw.json").exists())
        return None
    check(f"{v} converter zero errors, expected warnings", "Errors: 0, Warnings: 2, Notes: 0" in calc and
          calc.count("warning #108") == calc.count("warning #126") == 1 and
          "Saving results" in calc and "(error #" not in calc)
    check(f"{v} valid SXO/event/report", (run / "model.sxo").stat().st_size > 1000 and
          (run / "model.log").stat().st_size > 1000 and
          (run / "report-raw.json").stat().st_size > 1000)
    return ((run / "model.log").read_bytes(), tables(native(run / "report-raw.json"), root="report"))


def event_checks(v, raw):
    event = raw.decode("utf-8-sig", errors="replace")
    recon, follow = "<RECON,TEACH-UNIT,0,0,0>", "<FOLLOW,TEACH-UNIT,0,0,1>"
    check(f"{v} RECON launch8/success12", f"Time: 8 {recon} mission starting, duration: 4 : <TEACH-AIR-01,0>" in event and
          f"Time: 12 {recon} mission success:" in event and
          f"Time: 12 {recon} mission completed: <TEACH-AIR-01,0>" in event)
    follow_start = 12 if v == "fixed-fixed" else 10
    follow_end = 14 if v == "fixed-fixed" else 12
    check(f"{v} FOLLOW launch and success", f"Time: {follow_start} {follow} mission starting, duration: 2 : <TEACH-AIR-01,1>" in event and
          f"Time: {follow_end} {follow} mission success:" in event and
          f"Time: {follow_end} {follow} mission completed: <TEACH-AIR-01,1>" in event)
    if v == "dep-cont-dependency":
        check("nonfixed dependent START suspension10–12", f"Time: 10 {follow} mission suspended: <TEACH-AIR-01,1>" in event and
              f"Time: 12 {follow} mission resumed: <TEACH-AIR-01,1>(Susp)" in event and
              f"Time: 12 {follow} task starting: <TEACH-AIR-01,1>" in event and
              f"Time: 12 {follow} task completed: <TEACH-AIR-01,1>" in event)
    else:
        check(f"{v} no FOLLOW suspension", f"{follow} mission suspended:" not in event)
    check(f"{v} terminal two ready, no fault/abort", f"Time: {follow_end} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in event and
          "critical random failure" not in event and "mission aborted:" not in event and
          "mission cancelled:" not in event and event.count("mission starting, duration:") == 2)


def ledger_checks(v, report):
    check(f"{v} report table inventory", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = records(report["ResultSummary"])
    factor = 2/3 if v == "dep-cont-dependency" else 1
    check(f"{v} fixed and operating summary metrics", len(summary) == 1 and summary[0]["NREP"] == 1 and
          summary[0]["RTIUP"] == 24 and close(summary[0]["MTMF"], factor) and
          close(summary[0]["STMF"], factor) and
          summary[0]["MSTF"] == summary[0]["MSUF"] == 1 and
          all(summary[0][k] == 0 for k in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    system, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    check(f"{v} 48 aligned half-hour bins", len(system) == len(stock) == 48 and
          all(close(series[i]["STINT"], i/2) and close(series[i]["ETINT"], (i+1)/2)
              for series in (system, stock) for i in range(48)))
    for i, row in enumerate(system):
        for field, actual in row.items():
            wanted = expected_system(v, field, i/2, (i+1)/2)
            check(f"{v} System bin{i:02d} {field}",
                  actual == wanted if wanted is None or isinstance(wanted, str) else close(actual, wanted))
    nullable = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
    for i, row in enumerate(stock):
        for field, actual in row.items():
            wanted = (i/2 if field == "STINT" else (i+1)/2 if field == "ETINT" else
                      None if field in nullable else 1 if field == "PNB" else 0)
            check(f"{v} Stock bin{i:02d} {field}", actual == wanted if wanted is None else close(actual, wanted))
    expected_op = 4 if v == "dep-cont-dependency" else 6
    check(f"{v} exposure/suspension/inventory/terminal", close(sum(r["NSYMO"]*.5 for r in system), expected_op) and
          close(sum(r["STACC"]*.5 for r in system), expected_op) and
          close(sum(r["NSYMS"]*.5 for r in system), 2 if v == "dep-cont-dependency" else 0) and
          close(system[-1]["NSYRY"], 2) and close(system[-1]["NSYA"], 2))


def main():
    try:
        contract = source_checks()
        evidence = {}
        for v in VARIANTS:
            result = run_checks(v, contract)
            if result:
                evidence[v] = result
                event_checks(v, result[0])
                ledger_checks(v, result[1])
        check("matched CONTINUOUS controls both valid", set(evidence) ==
              {"fixed-fixed", "prec-cont-control", "dep-cont-control", "dep-cont-dependency"})
    except Exception as exc:
        check("reviewer completed without exception", False, repr(exc))
    failed = [c for c in CHECKS if not c["passed"]]
    result = {
        "schema": "simlox-a13-var06-independent-readonly/v1",
        "case_id": "A13.var06", "version": "1.0.1-candidate",
        "passed": not failed, "check_count": len(CHECKS),
        "passed_count": len(CHECKS)-len(failed), "failures": failed,
        "decision": "GO_bounded_start_role_matrix" if not failed else "NO_GO_evidence_mismatch",
        "finding": "With valid CONTINUOUS-role controls, native conversion rejects a non-FIXED precedent with MissionDependence error #223 and unusable SXO. A CONTINUOUS dependent with FIXED precedent is accepted: FOLLOW starts at 10, suspends until RECON succeeds at 12, then completes at 12 with zero positive operating time. Its MTMF/STMF are 2/3; fixed-reference and controls are 1.",
        "limits": ["One explicit START edge, two no-failure aircraft, fixed seed and one SIMLOX 2017 executable. The conversion result supports the FIXED-precedent rule for this case, not a general rule or error precedence.",
                   "Accepted CONTINUOUS-dependent outcome is a specific zero-operating-duration completion after suspension, not proof of ordinary CONTINUOUS mission success semantics.",
                   "Manual p287 disagrees with pp188/289; GUI visual content and cross-engine behavior unverified."],
        "source_sha256": {"parent": sha(PARENT), "contract": sha(CASE / "contract.json"),
                          "exact_diff": sha(CASE / "exact-diff.json"),
                          **{v: sha(CASE / f"{v}-input.json") for v in VARIANTS}},
        "raw_sha256": {v: {"closure": sha(run / "closure.json"),
                           "run_log": sha(run / "run.log"),
                           **({"model_log": sha(run / "model.log"),
                               "report": sha(run / "report-raw.json")} if v != REJECTED else
                              {"sxo": sha(run / "model.sxo")})} for v, run in RUNS.items()},
        "checks": CHECKS,
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in
                      ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
