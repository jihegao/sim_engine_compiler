"""Independent standard-library, read-only replay for A14.var02 v1.0.3."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
PARENT = AIR / "A05-var02-prepared-spare-probe-v1.0.0" / "native-input.json"
DONOR = AIR / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
RUNS = {v: CASE / "runs" / f"a14-dttol-{v}-v103-20261001-01"
        for v in ("control", "zero", "below", "edge", "above")}
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS = []
F0, F1 = 9.8829, 10.3829
EXEC_GAP = {"control": None, "zero": (F0, F1), "below": (10.3729, F1),
            "edge": None, "above": None}
FACTORS = {"control": (.93670886755, .91596639156),
           "zero": (.87341773510, .87394958735),
           "below": (.93544304371, .91512602568),
           "edge": (.93670886755, .91596639156),
           "above": (.93670886755, .91596639156)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path):
    # Native exporter emits trailing commas. Strip only outside JSON strings in memory.
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
        elif char == "," and raw[i + 1:].lstrip().startswith(("}", "]")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def check(name, condition, detail=None):
    CHECKS.append({"name": name, "passed": bool(condition), **({"detail": detail} if detail is not None else {})})


def close(actual, expected, tol=3e-5):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tol, rel_tol=0)


def table_map(doc, root="model"):
    result = {}
    for table in doc[root]["tables"]:
        assert table["name"] not in result
        result[table["name"]] = table
    return result


def table_rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in table_rows(table)]


def delta(before, after):
    return {name: {"before": before.get(name), "after": after.get(name)}
            for name in sorted(before.keys() | after.keys())
            if before.get(name) != after.get(name)}


def overlap(a, b, start, end):
    return max(0., min(b, end) - max(a, start))


def occupancy(a, b, periods):
    return sum(weight * overlap(a, b, start, end) for start, end, weight in periods) / (b-a)


def expected_system(variant, field, a, b):
    support = [(8, F0, 2), (F1, 12, 2)]
    execute = [(8, 11.9, 1)]
    if EXEC_GAP[variant]:
        start, end = EXEC_GAP[variant]
        execute = [(8, start, 1), (end, 11.9, 1)]
    op = occupancy(a, b, support + execute)
    assigned = occupancy(a, b, [(7, 11.9, 3), (11.9, 12, 2)])
    ready = occupancy(a, b, [(0, 7, 4), (7, F0, 1), (F1, 11.9, 1),
                             (11.9, 12, 2), (12, 16, 4)])
    gap = occupancy(a, b, [(F0, F1, 1)])
    suspended = gap + (occupancy(a, b, [(EXEC_GAP[variant][0], EXEC_GAP[variant][1], 1)])
                       if EXEC_GAP[variant] else 0)
    values = {
        "UNID": "Total over all Units", "SID": "Total over all Systems",
        "STINT": a, "ETINT": b, "NSYRY": ready, "NSYMA": assigned,
        "NSYMO": op, "NSYMP": occupancy(a, b, [(7, 7.5, 2), (F0, F1, 1)]),
        "NSYMS": suspended, "NSYMR": occupancy(a, b, [(7, 7.5, 1), (7.5, 8, 3)]),
        "NSYUA": gap, "NSYA": 4-gap, "FTMO": op/4,
        "NSYRP": gap, "NREPT": 1 if a == 10 else 0,
        "NFAIL": 1 if a == 9.5 else 0,
        "STREQ": occupancy(a, b, [(8, 11.9, 1.5), (11.9, 12, 1)]),
        "STACC": op, "SYDT": .5 if a == 9.5 else None,
        "NSYDT": 1 if a == 9.5 else 0,
        "NPSTA": 2 if a == 7 else 1 if a == 9.5 else 0,
        "NPSUC": 2 if a == 7.5 else 1 if a == 10 else 0,
    }
    return values.get(field, 0)


def source_replay():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check("frozen v103 contract and limits", contract["case_id"] == "A14" and
          contract["variant_id"] == "A14.var02" and contract["case_version"] == "1.0.3-candidate" and
          contract["publication_state"] == "not_published" and len(contract["predeclared_hypotheses"]) == 8)
    check("manual and dictionary source SHA", sha(manual) == contract["source"]["manual_sha256"] and
          sha(dictionary) == contract["source"]["dictionary_sha256"])
    check("accepted A05 parent and A11 donor SHA", sha(PARENT) == contract["parent"]["input_sha256"] ==
          diff["sources_sha256"]["parent"] and sha(DONOR) == contract["schema_source"]["input_sha256"] and
          "accepted" in (CASE / contract["parent"]["signoff"]).read_text(encoding="utf-8").lower())
    check("frozen exact diff SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    sources = {v: table_map(native(CASE / f"{v}-input.json")) for v in RUNS}
    parent = table_map(native(PARENT))
    donor = table_map(native(DONOR))
    check("typed MissionSystem schema from A11 donor", sources["control"]["MissionSystem"]["columns"] ==
          donor["MissionSystem"]["columns"])
    for v in RUNS:
        check(f"{v} frozen source SHA", sha(CASE / f"{v}-input.json") ==
              contract["inputs_sha256"][v] == diff["sources_sha256"][v])
        check(f"{v} source table inventory", len(sources[v]) == (32 if v == "control" else 33) and
              sum(bool(table_rows(t)) for t in sources[v].values()) == (17 if v == "control" else 18))
    for name, a, b in [("parent_to_control", parent, sources["control"])] + [
            (f"control_to_{v}", sources["control"], sources[v]) for v in RUNS if v != "control"]:
        actual = delta(a, b)
        check(name + " exact complete table delta", actual == diff["changes"][name], sorted(actual))
    for v, tolerance in (("zero", 0), ("below", .49), ("edge", .5), ("above", .51)):
        data = records(sources[v]["MissionDependence"])
        check(f"{v} one exact DTTOL row", len(data) == 1 and data[0] ==
              {"DUNID": "TEACH-UNIT", "DMTID": "EXECUTE", "DSTIM": 8,
               "PUNID": "TEACH-UNIT", "PMTID": "SUPPORT", "PSTIM": 8,
               "DTYPE": "CONTINUOUS", "MUTD": "N", "DTTOL": tolerance, "NOTE": None})
    return contract


def run_replay(variant, contract):
    run = RUNS[variant]
    inv, closure = read(run / "invocation.json"), read(run / "closure.json")
    before = closure["source_hashes_before"]
    source = CASE / f"{variant}-input.json"
    check(f"{variant} run identity and source copy", inv["run_id"] == closure["run_id"] == run.name and
          inv["variant"] == variant and inv["case_id"] == "A14" and
          Path(inv["original_run_dir"]).resolve() == run.resolve() and
          inv["input_sha256"] == sha(source) == sha(run / "input.json"))
    check(f"{variant} immutable source closure", before == closure["source_hashes_after"] == inv["source_hashes_before"] and
          before["input"] == sha(source) and before["parent"] == sha(PARENT) and
          before["schema_donor"] == sha(DONOR) and
          before["contract"] == sha(CASE / "contract.json") and
          before["builder"] == sha(CASE / "build.py") and
          before["exact_diff"] == sha(CASE / "exact-diff.json") and
          before["diff_checker"] == sha(CASE / "describe_diff.py") and
          before["checker"] == sha(CASE / "check_roundtrip.py") and
          before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    check(f"{variant} runtime/invocation seals", closure["invocation_sha256"] == sha(run / "invocation.json") and
          closure["error"] is None and all(inv[k + "_sha256"] == before[k] for k in
          ("parent", "schema_donor", "contract", "builder", "checker", "python", "runner_script", "simlox_exe")))
    check(f"{variant} complete raw inventory", set(closure["raw"]) ==
          {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
    for name, meta in closure["raw"].items():
        check(f"{variant} raw SHA {name}", (run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"])
    check(f"{variant} session0 SSH mutex GUI", inv["session_id"] == 0 and
          inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    steps = read(run / "steps.json")
    check(f"{variant} five guarded successful steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None
              for s in steps) and
          all(steps[i]["completed_utc"] <= steps[i+1]["started_utc"] for i in range(4)) and
          all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)) and
          steps[4]["arguments"] == inv["planned_check"]["arguments"])
    wanted = table_map(native(source))
    exported = table_map(native(run / "roundtrip-raw.json"))
    populated = {name for name, table in wanted.items() if table_rows(table)}
    check(f"{variant} 17/18 row-containing business tables", len(populated) == (17 if variant == "control" else 18))
    for name in sorted(populated):
        check(f"{variant} exact source table roundtrip {name}", wanted[name] == exported.get(name))
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{variant} converter errors0 warnings108/126x2", "Errors: 0, Warnings: 3, Notes: 0" in log and
          log.count("warning #108") == 1 and log.count("warning #126") == 2 and
          "Saving results" in log and "error #" not in log.lower())
    check(f"{variant} native report and SXO nonempty", (run / "model.sxo").stat().st_size > 1000 and
          (run / "report-raw.json").stat().st_size > 1000)
    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    report = table_map(native(run / "report-raw.json"), root="report")
    return event, report


def event_replay(variant, event):
    support = "<SUPPORT,TEACH-UNIT,0,0,0>"
    execute = "<EXECUTE,TEACH-UNIT,0,0,1>"
    required = [
        f"Time: 8 {support} mission starting, duration: 4 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        f"Time: 8 {execute} mission starting, duration: 3.9 : <EXEC-AIR-01,3>",
        "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added",
        f"Time: 9.8829 {support} mission suspended: <TEACH-AIR-01,1>",
        "Time: 9.8829 <TEACH-AIR-01,2> preparation started, mission:",
        "Time: 9.8829  direct repair subtask 3 seqno 0 within system DIRP task 3 on <TEACH-AIR-01,0> started",
        "Time: 10.3829 <TEACH-AIR-01,2> preparation ended, mission:",
        "Time: 10.3829  direct repair subtask 3 seqno 0 within system DIRP task 3 on <TEACH-AIR-01,0> completed",
        f"Time: 10.3829 {support} mission resumed: <TEACH-AIR-01,1>(Susp),<TEACH-AIR-01,2>(Susp)",
        f"Time: 11.9 {execute} mission success:", f"Time: 11.9 {execute} mission completed: <EXEC-AIR-01,3>",
        f"Time: 12 {support} mission success:",
        "Time: 12 <TEACH-UNIT at <BASE-01,0>> systems ready: 4 :<TEACH-AIR-01,0>,<EXEC-AIR-01,3>,<TEACH-AIR-01,1>,<TEACH-AIR-01,2>",
    ]
    for i, line in enumerate(required):
        check(f"{variant} event {i:02d}", line in event)
    check(f"{variant} exact one SUPPORT failure / all missions succeed", event.count("critical random failure added") == 1 and
          event.count("mission success:") == 2 and "mission aborted:" not in event and
          "mission cancelled:" not in event and "<EXEC-AIR-01,3> critical random failure" not in event)
    susp = [line for line in event.splitlines() if f"{execute} mission suspended:" in line]
    resumes = [line for line in event.splitlines() if f"{execute} mission resumed:" in line]
    expected_susp = ([] if variant == "control" else [8] +
                     ([F0] if variant == "zero" else [10.3729] if variant == "below" else
                      [F1] if variant == "edge" else []))
    expected_resume = ([] if variant == "control" else [8] +
                       ([F1] if variant in ("zero", "below", "edge") else []))
    def event_times(lines):
        return [float(line.split()[1]) for line in lines]
    check(f"{variant} exact EXECUTE suspend/resume times", event_times(susp) == expected_susp and
          event_times(resumes) == expected_resume,
          {"suspend": event_times(susp), "resume": event_times(resumes)})
    if variant == "edge":
        check("edge same-time suspend precedes resume", event.index(f"Time: 10.3829 {execute} mission suspended:") <
              event.index(f"Time: 10.3829 {execute} mission resumed:"))


def ledger_replay(variant, report):
    check(f"{variant} four report tables", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = records(report["ResultSummary"])
    mtmf, stmf = FACTORS[variant]
    check(f"{variant} one-rep summary factors", len(summary) == 1 and summary[0]["NREP"] == 1 and
          summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 16 and
          close(summary[0]["MTMF"], mtmf, 1e-6) and close(summary[0]["STMF"], stmf, 1e-6) and
          all(summary[0][field] == 0 for field in
              ("RSMTMF", "MSTF", "RSMSTF", "MSUF", "RSMSUF", "RSSTMF")))
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(f"{variant} 32 aligned half-hour bins", len(system) == len(stock) == 32 and
          all(close(series[i]["STINT"], i/2) and close(series[i]["ETINT"], (i+1)/2)
              for series in (system, stock) for i in range(32)))
    for i, row in enumerate(system):
        a, b = i/2, (i+1)/2
        for field, actual in row.items():
            expected = expected_system(variant, field, a, b)
            check(f"{variant} system bin{i:02d} {field}",
                  actual == expected if expected is None or isinstance(expected, str) else
                  close(actual, expected),
                  None if expected is None or actual == expected or close(actual, expected) else
                  {"actual": actual, "expected": expected})
    nullable = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
    for i, row in enumerate(stock):
        for field, actual in row.items():
            expected = (i/2 if field == "STINT" else (i+1)/2 if field == "ETINT" else
                        None if field in nullable else 1 if field == "PNB" else 0)
            check(f"{variant} stock bin{i:02d} {field}",
                  actual == expected if expected is None else close(actual, expected))
    expected_op = {"control": 10.9, "zero": 10.4, "below": 10.89,
                   "edge": 10.9, "above": 10.9}[variant]
    check(f"{variant} exposure/failure/repair/preparation integrals",
          close(sum(row["NSYMO"]*.5 for row in system), expected_op) and
          close(sum(row["STACC"]*.5 for row in system), expected_op) and
          close(sum(row["NFAIL"]*.5 for row in system), .5) and
          close(sum(row["NREPT"]*.5 for row in system), .5) and
          close(sum(row["NSYMP"]*.5 for row in system), 1.5) and
          close(system[-1]["NSYRY"], 4) and close(system[-1]["NSYA"], 4))


def diagnostics():
    for version in ("1.0.0", "1.0.1", "1.0.2"):
        case = AIR / f"A14-dttol-prepared-gap-v{version}"
        contract = read(case / "contract.json")
        check(f"v{version} diagnostic contract excluded", contract["publication_state"] == "not_published" and
              contract["case_version"].startswith(version))
        runs = sorted((case / "runs").glob("a14-dttol-*-v*-20261001-01"))
        check(f"v{version} diagnostic raw evidence exists", bool(runs) and
              all((run / "model.log").is_file() and (run / "closure.json").is_file() for run in runs))
        if version == "1.0.0":
            log = (runs[0] / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            check("v100 EXECUTE ended before SUPPORT gap", "Time: 11 <EXECUTE,TEACH-UNIT,0,0,1> mission success:" in log and
                  "Time: 11.1325" in log)
        elif version == "1.0.1":
            control = (case / "runs" / "a14-dttol-control-v101-20261001-01" / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            below = (case / "runs" / "a14-dttol-below-v101-20261001-01" / "model.log").read_text(encoding="utf-8-sig", errors="replace")
            check("v101 unmatched failure clock", "Time: 9.8829 <TEACH-AIR-01,2> critical random failure" in control and
                  "Time: 11.1325 <TEACH-AIR-01,2> critical random failure" in below and
                  "Time: 11.1325 <SUPPORT,TEACH-UNIT,0,0,0> mission suspended:" in control and
                  "<SUPPORT,TEACH-UNIT,0,0,0> mission suspended:" not in below)
        else:
            for v in ("zero", "below", "edge", "above"):
                log = (case / "runs" / f"a14-dttol-{v}-v102-20261001-01" / "model.log").read_text(encoding="utf-8-sig", errors="replace")
                check(f"v102 {v} survived contrary to abort hypothesis", "Time: 11.9 <EXECUTE,TEACH-UNIT,0,0,1> mission success:" in log and
                      "mission aborted:" not in log)


def main():
    try:
        contract = source_replay()
        for variant in RUNS:
            event, report = run_replay(variant, contract)
            event_replay(variant, event)
            ledger_replay(variant, report)
        diagnostics()
    except Exception as exc:
        check("reviewer completed without exception", False, repr(exc))
    failures = [item for item in CHECKS if not item["passed"]]
    report = {
        "schema": "simlox-a14-var02-independent-readonly/v1", "case_id": "A14.var02",
        "version": "1.0.3-candidate", "passed": not failures,
        "check_count": len(CHECKS), "passed_count": len(CHECKS)-len(failures),
        "failures": failures,
        "decision": "bounded_go_fixed_seed_dttol_gap_threshold" if not failures else "no_go_evidence_mismatch",
        "finding": "With matched SUPPORT failure on TEACH-AIR-01#0 at 9.8829 and half-hour replacement/repair gap, the dependent EXECUTE has 0.5h suspended exposure at DTTOL=0, 0.01h at 0.49, and zero-duration same-time event at 0.5; DTTOL=0.51 and control have no gap-related suspension. All EXECUTE missions succeed at 11.9 and SUPPORT at 12.",
        "diagnostic_disposition": "v1.0.0 ended EXECUTE before the gap; v1.0.1 changed failure identity; v1.0.2 contradicted its predeclared abort hypothesis. All remain excluded.",
        "limits": ["One fixed seed and one half-hour stochastic support gap; this does not establish a general tolerance law or deterministic failure time.",
                   "No absent predecessor, longer gap, multiple precedent, other mission pattern, cross-unit/profile, GUI visual or cross-engine claim."],
        "source_sha256": {"parent": sha(PARENT), "schema_donor": sha(DONOR),
                          "contract": sha(CASE / "contract.json"), "exact_diff": sha(CASE / "exact-diff.json"),
                          **{v: sha(CASE / f"{v}-input.json") for v in RUNS}},
        "native_sha256": {v: {"closure": sha(run / "closure.json"),
                              "model_log": sha(run / "model.log"),
                              "report": sha(run / "report-raw.json")} for v, run in RUNS.items()},
        "checks": CHECKS,
    }
    OUT.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: report[key] for key in
                      ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
