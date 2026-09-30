"""Independent standard-library replay of sealed A14 staggered mutual pair."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
PARENT = AIR / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
DIAGNOSTIC = AIR / "A14-mutual-stagger-v1.0.0"
RUNS = {v: CASE / "runs" / f"a14-stagger-{v}-v101-20261001-01"
        for v in ("control", "oneway", "mutual", "opposing")}
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path):
    raw = path.read_text(encoding="utf-8-sig")
    result = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            result.append(ch)
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': quoted = False
        elif ch == '"':
            quoted = True
            result.append(ch)
        elif ch == ',' and raw[i+1:].lstrip().startswith(('}', ']')):
            continue
        else:
            result.append(ch)
    return json.loads(''.join(result))


def check(name, condition, detail=None):
    CHECKS.append({"name": name, "passed": bool(condition),
                   **({"detail": detail} if detail is not None else {})})


def close(actual, expected):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-6)


def table_map(document, root="model"):
    result = {}
    for table in document[root]["tables"]:
        assert table["name"] not in result
        result[table["name"]] = table
    return result


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def delta(a, b):
    return {name: {"before": a.get(name), "after": b.get(name)}
            for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name)}


def occupancy(a, b, intervals):
    return sum(max(0., min(b, end) - max(a, start)) * weight
               for start, end, weight in intervals) / (b-a)


def expected_system(variant, field, a, b):
    finish = 12.1 if variant == "control" else 10
    mutual = variant in ("mutual", "opposing")
    assigned = occupancy(a, b, [(7, 10, 1), (7.1, finish, 1)])
    operating = occupancy(a, b, [(8.1 if mutual else 8, 10, 1),
                                 (8.1, finish, 1)])
    values = {
        "UNID": "Total over all Units", "SID": "Total over all Systems",
        "STINT": a, "ETINT": b,
        "NSYRY": 2-assigned, "NSYMA": assigned, "NSYMO": operating,
        "NSYMR": occupancy(a, b, [(7, 8, 1), (7.1, 8.1, 1)]),
        "NSYMS": occupancy(a, b, [(8, 8.1, 1)]) if mutual else 0,
        "NSYA": 2, "FTMO": operating/2, "STACC": operating,
        "SYDT": None,
    }
    return values.get(field, 0)


def source_checks():
    contract, manifest = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check("frozen contract identity and SHA", sha(CASE / "contract.json") ==
          "a0b09823bb44823684ecc5190e1f49a4f6f4a839e11da1882526ea642c0f3999" and
          contract["case_id"] == "A14" and contract["case_version"] == "1.0.1-candidate" and
          contract["publication_state"] == "not_published")
    check("manual/dictionary installed fingerprints", sha(manual) == contract["source"]["manual_sha256"] and
          sha(dictionary) == contract["source"]["dictionary_sha256"])
    check("accepted A05 parent input/signoff", sha(PARENT) == contract["parent"]["input_sha256"] ==
          manifest["sources_sha256"]["parent"] and
          "reusable_published" in (CASE / contract["parent"]["signoff"]).read_text(encoding="utf-8"))
    check("frozen exact diff fingerprint", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    sources = {v: table_map(native(CASE / f"{v}-input.json")) for v in RUNS}
    parent = table_map(native(PARENT))
    for v, source in sources.items():
        check(f"{v} source SHA/table count", sha(CASE / f"{v}-input.json") ==
              contract["inputs_sha256"][v] == manifest["sources_sha256"][v] and
              len(source) == (31 if v == "control" else 32) and
              sum(bool(rows(t)) for t in source.values()) == (13 if v == "control" else 14))
    for name, a, b in [("parent_to_control", parent, sources["control"])] + [
            (f"control_to_{v}", sources["control"], sources[v]) for v in RUNS if v != "control"]:
        check(name + " exact complete table delta", delta(a, b) == manifest["changes"][name], sorted(delta(a, b)))
    depend = {v: rows(sources[v]["MissionDependence"]) for v in RUNS if v != "control"}
    base = ["TEACH-UNIT", "EXECUTE", 8.1, "TEACH-UNIT", "SUPPORT", 8., "CONTINUOUS"]
    reverse = ["TEACH-UNIT", "SUPPORT", 8., "TEACH-UNIT", "EXECUTE", 8.1, "CONTINUOUS"]
    check("exact one-way N row", depend["oneway"] == [base + ["N", None, None]])
    check("exact mutual Y row", depend["mutual"] == [base + ["Y", None, None]])
    check("exact opposing two N rows", depend["opposing"] ==
          [base + ["N", None, None], reverse + ["N", None, None]])
    check("same staggered mission schedule", rows(sources["control"]["OperationProfile"]) ==
          [["BASIC-SCHEDULE", "SUPPORT", 8., "SCHEDULED", 1, None, 0, None, 1/3, None, None, None],
           ["BASIC-SCHEDULE", "EXECUTE", 8.1, "SCHEDULED", 1, None, 0, None, 1/3, None, None, None]])
    return contract


def run_checks(variant, contract):
    run = RUNS[variant]
    inv, closure = read(run / "invocation.json"), read(run / "closure.json")
    before = closure["source_hashes_before"]
    source = CASE / f"{variant}-input.json"
    check(f"{variant} run and source identity", inv["run_id"] == closure["run_id"] == run.name and
          inv["variant"] == variant and inv["case_id"] == "A14" and
          inv["case_version"] == contract["case_version"] and
          Path(inv["original_run_dir"]).resolve() == run.resolve() and
          inv["input_sha256"] == sha(source) == sha(run / "input.json"))
    check(f"{variant} source frozen through native run", before == closure["source_hashes_after"] ==
          inv["source_hashes_before"] and before["input"] == sha(source) and
          before["parent"] == sha(PARENT) and before["contract"] == sha(CASE / "contract.json") and
          before["builder"] == sha(CASE / "build.py") and
          before["exact_diff"] == sha(CASE / "exact-diff.json") and
          before["diff_checker"] == sha(CASE / "describe_diff.py") and
          before["checker"] == sha(CASE / "check_roundtrip.py") and
          before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    check(f"{variant} runtime/invocation seals", closure["invocation_sha256"] == sha(run / "invocation.json") and
          closure["error"] is None and all(inv[k + "_sha256"] == before[k]
          for k in ("parent", "contract", "builder", "checker", "python", "runner_script", "simlox_exe")))
    check(f"{variant} complete raw inventory", set(closure["raw"]) ==
          {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
    for name, meta in closure["raw"].items():
        check(f"{variant} raw SHA {name}", (run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"])
    check(f"{variant} session0 SSH/mutex/GUI", inv["session_id"] == 0 and inv["ssh_connection_present"] and
          "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    steps = read(run / "steps.json")
    check(f"{variant} five guarded ordered steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None
              for s in steps) and
          all(steps[i]["completed_utc"] <= steps[i+1]["started_utc"] for i in range(4)) and
          all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)) and
          steps[4]["arguments"] == inv["planned_check"]["arguments"])
    wanted = table_map(native(source))
    exported = table_map(native(run / "roundtrip-raw.json"))
    populated = {name for name, t in wanted.items() if rows(t)}
    for name in sorted(populated):
        check(f"{variant} exact source roundtrip {name}", wanted[name] == exported.get(name))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{variant} converter errors0 warnings108/126", "Errors: 0, Warnings: 2, Notes: 0" in calc and
          calc.count("warning #108") == 1 and calc.count("warning #126") == 1 and
          "Saving results" in calc)
    check(f"{variant} nonempty native model/report", (run / "model.sxo").stat().st_size > 1000 and
          (run / "report-raw.json").stat().st_size > 1000)
    return (run / "model.log").read_bytes(), table_map(native(run / "report-raw.json"), root="report")


def event_checks(v, data):
    event = data.decode("utf-8-sig", errors="replace")
    sup = "<SUPPORT,TEACH-UNIT,0,0,0>"
    exe = "<EXECUTE,TEACH-UNIT,0,0,1>"
    expected = [f"Time: 8 {sup} mission starting, duration: 2 : <TEACH-AIR-01,0>",
                f"Time: 8.1 {exe} mission starting, duration: 4 : <TEACH-AIR-01,1>",
                f"Time: 10 {sup} mission success:"]
    for i, line in enumerate(expected):
        check(f"{v} common event {i}", line in event)
    if v == "control":
        check("control EXECUTE success12.1", f"Time: 12.1 {exe} mission success:" in event and
              f"Time: 12.1 {exe} mission completed: <TEACH-AIR-01,1>" in event and
              "mission aborted:" not in event)
    else:
        check(f"{v} EXECUTE abort10", f"Time: 10 {exe} mission aborted: <TEACH-AIR-01,1>" in event and
              f"Time: 10 {exe} aborted mission completed: <TEACH-AIR-01,1>" in event and
              f"{exe} mission success:" not in event)
    if v in ("mutual", "opposing"):
        check(f"{v} SUPPORT suspends8 and resumes8.1", f"Time: 8 {sup} mission suspended: <TEACH-AIR-01,0>" in event and
              f"Time: 8.1 {sup} mission resumed: <TEACH-AIR-01,0>(Susp)" in event)
    else:
        check(f"{v} no positive SUPPORT suspension", f"{sup} mission suspended:" not in event)
    terminal = "12.1" if v == "control" else "10"
    check(f"{v} two aircraft ready after missions", f"Time: {terminal} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in event)
    check(f"{v} no failure/cancellation", "critical random failure" not in event and
          "mission cancelled:" not in event and event.count("mission starting, duration:") == 2)


def ledger_checks(v, report):
    check(f"{v} report table inventory", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = records(report["ResultSummary"])
    factor = {"control": 1, "oneway": .65, "mutual": 3.8/6,
              "opposing": 3.8/6}[v]
    check(f"{v} summary factor", len(summary) == 1 and summary[0]["NREP"] == 1 and
          summary[0]["RTIUP"] == 16 and close(summary[0]["MTMF"], factor) and
          close(summary[0]["STMF"], factor) and
          all(summary[0][k] == 0 for k in
              ("MSTF", "MSUF", "RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    system, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    check(f"{v} 32 aligned half-hour bins", len(system) == len(stock) == 32 and
          all(close(series[i]["STINT"], i/2) and close(series[i]["ETINT"], (i+1)/2)
              for series in (system, stock) for i in range(32)))
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
    expected_op = {"control": 6, "oneway": 3.9, "mutual": 3.8, "opposing": 3.8}[v]
    check(f"{v} exposure/inventory/terminal", close(sum(r["NSYMO"]*.5 for r in system), expected_op) and
          close(sum(r["STACC"]*.5 for r in system), expected_op) and
          close(sum(r["NSYMS"]*.5 for r in system), .1 if v in ("mutual", "opposing") else 0) and
          close(system[-1]["NSYRY"], 2) and close(system[-1]["NSYA"], 2))


def diagnostic_checks():
    c = read(DIAGNOSTIC / "contract.json")
    check("prior staggered diagnostic remains unpublished", c["publication_state"] == "not_published")
    for v in ("mutual", "opposing"):
        run = DIAGNOSTIC / "runs" / f"a14-stagger-{v}-v100-20261001-01"
        seal = read(run / "closure.json")
        check(f"prior {v} raw seal", seal["invocation_sha256"] == sha(run / "invocation.json") and
              all(sha(run / name) == meta["sha256"] for name, meta in seal["raw"].items()))
    a = DIAGNOSTIC / "runs" / "a14-stagger-mutual-v100-20261001-01" / "model.log"
    b = DIAGNOSTIC / "runs" / "a14-stagger-opposing-v100-20261001-01" / "model.log"
    check("prior opposing/mutual event equality was diagnostic", a.read_bytes() == b.read_bytes() and
          b"mission suspended:" in a.read_bytes())


def main():
    try:
        contract = source_checks()
        evidence = {}
        for v in RUNS:
            events, report = run_checks(v, contract)
            evidence[v] = (events, report)
            event_checks(v, events)
            ledger_checks(v, report)
        check("fresh mutual/opposing byte-identical event logs",
              evidence["mutual"][0] == evidence["opposing"][0])
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check("fresh mutual/opposing report equality " + name,
                  evidence["mutual"][1][name] == evidence["opposing"][1][name])
        diagnostic_checks()
    except Exception as exc:
        check("reviewer completed without exception", False, repr(exc))
    failed = [c for c in CHECKS if not c["passed"]]
    result = {
        "schema": "simlox-a14-mutual-stagger-independent-readonly/v1",
        "case_id": "A14.var04+var05", "version": "1.0.1-candidate",
        "passed": not failed, "check_count": len(CHECKS),
        "passed_count": len(CHECKS)-len(failed), "failures": failed,
        "decision": "GO_bounded_staggered_mutual_opposing_equivalence" if not failed else "NO_GO_evidence_mismatch",
        "finding": "In fresh sealed runs, control succeeds at 10/12.1; one-way aborts EXECUTE at 10; MUTD=Y and two opposing N rows both suspend SUPPORT for 0.1 hour at launch, then abort EXECUTE at 10. Mutual and opposing event logs are byte-identical, and all non-description report tables match.",
        "limits": ["One explicit unit, two no-failure CONTINUOUS missions and one 0.1-hour stagger; equality here does not establish general MUTD equivalence or refute all manual deadlock cases.",
                   "Prior v1.0.0 remains NO-GO. Other schedules, constraints, DTTOL, GUI visual content and cross-engine behavior are unverified."],
        "source_sha256": {"parent": sha(PARENT), "contract": sha(CASE / "contract.json"),
                          "exact_diff": sha(CASE / "exact-diff.json"),
                          **{v: sha(CASE / f"{v}-input.json") for v in RUNS}},
        "raw_sha256": {v: {"closure": sha(r / "closure.json"),
                           "model_log": sha(r / "model.log"),
                           "report": sha(r / "report-raw.json")} for v, r in RUNS.items()},
        "checks": CHECKS,
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in
                      ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
