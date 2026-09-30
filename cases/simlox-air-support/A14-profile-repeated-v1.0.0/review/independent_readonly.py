"""Independent read-only replay of frozen A14.var06 v1.0.0 evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
PARENT = AIR / "A14-continuous-end-abort-v1.0.1" / "control-input.json"
DONOR = AIR / "A09-hierarchical-operation-profile-v1.0.1" / "native-nested.json"
RUNS = {v: CASE / "runs" / f"a14-profile-{v}-v100-20261001-01"
        for v in ("control", "explicit", "profile")}
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path):
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == ',' and raw[i+1:].lstrip().startswith(('}', ']')):
            continue
        else:
            out.append(ch)
    return json.loads(''.join(out))


def check(name, condition, detail=None):
    CHECKS.append({"name": name, "passed": bool(condition),
                   **({"detail": detail} if detail is not None else {})})


def close(a, b):
    return isinstance(a, (int, float)) and math.isclose(a, b, abs_tol=1e-6, rel_tol=0)


def table_map(doc, root="model"):
    result = {}
    for t in doc[root]["tables"]:
        assert t["name"] not in result
        result[t["name"]] = t
    return result


def rows(t):
    return [r for inst in t["instances"] for r in inst["rows"]]


def records(t):
    columns = [c["name"] for c in t["columns"]]
    return [dict(zip(columns, row)) for row in rows(t)]


def delta(a, b):
    return {name: {"before": a.get(name), "after": b.get(name)}
            for name in sorted(a.keys() | b.keys()) if a.get(name) != b.get(name)}


def first_wave_expected(v, field, h):
    finish = 12 if v == "control" else 10
    values = {
        "UNID": "Total over all Units", "SID": "Total over all Systems",
        "STINT": h, "ETINT": h+.5,
        "NSYRY": 2 if h < 7 or h >= finish else (1 if h >= 10 else 0),
        "NSYMA": 0 if h < 7 or h >= finish else (1 if h >= 10 else 2),
        "NSYMO": 2 if 8 <= h < 10 else (1 if v == "control" and 10 <= h < 12 else 0),
        "NSYMR": 2 if 7 <= h < 8 else 0,
        "NSYA": 2,
        "FTMO": 1 if 8 <= h < 10 else (.5 if v == "control" and 10 <= h < 12 else 0),
        "STACC": 2 if 8 <= h < 10 else (1 if v == "control" and 10 <= h < 12 else 0),
        "SYDT": None,
    }
    return values.get(field, 0)


def source_checks():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check("frozen v100 contract identity", contract["case_id"] == "A14" and
          contract["variant_id"] == "A14.var06" and
          contract["case_version"] == "1.0.0-candidate" and
          contract["publication_state"] == "not_published")
    check("manual and dictionary SHA", sha(manual) == contract["source"]["manual_sha256"] and
          sha(dictionary) == contract["source"]["dictionary_sha256"])
    check("accepted parent and profile donor SHA/signoffs", sha(PARENT) == contract["parent"]["input_sha256"] ==
          diff["sources_sha256"]["parent"] and sha(DONOR) == contract["profile_donor"]["input_sha256"] and
          (CASE / contract["parent"]["signoff"]).is_file() and
          (CASE / contract["profile_donor"]["signoff"]).is_file())
    check("exact diff seal", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    parent = table_map(native(PARENT))
    donor = table_map(native(DONOR))
    sources = {v: table_map(native(CASE / f"{v}-input.json")) for v in RUNS}
    check("OperationProfile schema from A09 donor", sources["profile"]["OperationProfile"]["columns"] ==
          donor["OperationProfile"]["columns"])
    for v, source in sources.items():
        check(f"{v} source SHA and table count", sha(CASE / f"{v}-input.json") ==
              contract["inputs_sha256"][v] == diff["sources_sha256"][v] and
              len(source) == (31 if v == "control" else 32) and
              sum(bool(rows(t)) for t in source.values()) == (13 if v == "control" else 14))
    for key, a, b in (("parent_to_control", parent, sources["control"]),
                      ("control_to_explicit", sources["control"], sources["explicit"]),
                      ("control_to_profile", sources["control"], sources["profile"])):
        check(key + " complete exact table delta", delta(a, b) == diff["changes"][key], sorted(delta(a, b)))
    check("explicit two wave-specific dependency rows", rows(sources["explicit"]["MissionDependence"]) ==
          [["TEACH-UNIT", "EXECUTE", h, "TEACH-UNIT", "SUPPORT", h, "CONTINUOUS", "N", None, None]
           for h in (8., 32.)])
    check("profile single repeated dependency row", rows(sources["profile"]["MissionDependenceProfile"]) ==
          [["A14-WAVE", "EXECUTE", 8., "SUPPORT", 8., "CONTINUOUS", "N", None, None]])
    check("repeating root and two IQTY1 leaves", rows(sources["control"]["OperationProfile"]) ==
          [["BASIC-SCHEDULE", "A14-WAVE", 0., "SCHEDULED", 2, None, 48., None, None, None, None, None],
           ["A14-WAVE", "SUPPORT", 8., "SCHEDULED", 1, None, 0, None, 1/3, None, None, None],
           ["A14-WAVE", "EXECUTE", 8., "SCHEDULED", 1, None, 0, None, 1/3, None, None, None]])
    # A source-level reason why the later native SystemResults bins cannot exist.
    for v, source in sources.items():
        collection = records(source["ResultCollection"])
        check(f"{v} requested 40-hour System/Mission collection", all(
              row["RCSTA"] == 0 and row["RCINT"] == .5 and row["RCEND"] == 40
              for row in collection if row["RTYPE"] in ("SYSTEM", "MISSION")),
              {row["RTYPE"]: row["RCEND"] for row in collection})
    return contract


def run_checks(v, contract):
    run = RUNS[v]
    inv, closure = read(run / "invocation.json"), read(run / "closure.json")
    before = closure["source_hashes_before"]
    source = CASE / f"{v}-input.json"
    check(f"{v} native run/input identity", inv["run_id"] == closure["run_id"] == run.name and
          inv["variant"] == v and inv["case_id"] == "A14" and
          Path(inv["original_run_dir"]).resolve() == run.resolve() and
          inv["input_sha256"] == sha(source) == sha(run / "input.json"))
    check(f"{v} invocation version matches frozen contract", inv["case_version"] == contract["case_version"],
          {"invocation": inv["case_version"], "contract": contract["case_version"]})
    check(f"{v} frozen source closure", before == closure["source_hashes_after"] == inv["source_hashes_before"] and
          before["input"] == sha(source) and before["parent"] == sha(PARENT) and
          before["profile_donor"] == sha(DONOR) and
          before["contract"] == sha(CASE / "contract.json") and
          before["builder"] == sha(CASE / "build.py") and
          before["exact_diff"] == sha(CASE / "exact-diff.json") and
          before["diff_checker"] == sha(CASE / "describe_diff.py") and
          before["checker"] == sha(CASE / "check_roundtrip.py") and
          before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    check(f"{v} runtime/invocation seal", closure["invocation_sha256"] == sha(run / "invocation.json") and
          closure["error"] is None and all(inv[key + "_sha256"] == before[key] for key in
          ("parent", "profile_donor", "contract", "builder", "checker", "python", "runner_script", "simlox_exe")))
    check(f"{v} complete raw inventory", set(closure["raw"]) ==
          {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
    for name, meta in closure["raw"].items():
        check(f"{v} raw SHA {name}", (run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"])
    check(f"{v} session0 SSH mutex GUI", inv["session_id"] == 0 and inv["ssh_connection_present"] and
          "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    steps = read(run / "steps.json")
    check(f"{v} five guarded ordered native steps", [s["name"] for s in steps] ==
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
        check(f"{v} exact source roundtrip {name}", wanted[name] == exported.get(name))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{v} converter zero errors/expected warnings", "Errors: 0, Warnings: 2, Notes: 0" in calc and
          calc.count("warning #108") == 1 and calc.count("warning #126") == 1 and
          "Saving results" in calc)
    check(f"{v} nonempty native outputs", (run / "model.sxo").stat().st_size > 1000 and
          (run / "report-raw.json").stat().st_size > 1000)
    return ((run / "model.log").read_bytes(), table_map(native(run / "report-raw.json"), root="report"))


def event_checks(v, event_bytes):
    event = event_bytes.decode("utf-8-sig", errors="replace")
    check(f"{v} exactly four mission starts", event.count("mission starting, duration:") == 4)
    for wave, start in enumerate((8, 32)):
        support = f"<SUPPORT,TEACH-UNIT,0,0,{wave*2}>"
        execute = f"<EXECUTE,TEACH-UNIT,0,0,{wave*2+1}>"
        finish = start+2
        for name, line in (
            ("support start", f"Time: {start} {support} mission starting, duration: 2 : <TEACH-AIR-01,0>"),
            ("execute start", f"Time: {start} {execute} mission starting, duration: 4 : <TEACH-AIR-01,1>"),
            ("support success", f"Time: {finish} {support} mission success:"),
            ("support complete", f"Time: {finish} {support} mission completed: <TEACH-AIR-01,0>"),
        ):
            check(f"{v} wave{wave+1} {name}", line in event)
        if v == "control":
            check(f"{v} wave{wave+1} execute success at {start+4}",
                  f"Time: {start+4} {execute} mission success:" in event and
                  f"Time: {start+4} {execute} mission completed: <TEACH-AIR-01,1>" in event)
        else:
            check(f"{v} wave{wave+1} execute aborted at {finish}",
                  f"Time: {finish} {execute} mission aborted: <TEACH-AIR-01,1>" in event and
                  f"Time: {finish} {execute} aborted mission completed: <TEACH-AIR-01,1>" in event and
                  f"{execute} mission success:" not in event)
        terminal = start+4 if v == "control" else finish
        check(f"{v} wave{wave+1} both aircraft returned ready",
              f"Time: {terminal} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in event)
    check(f"{v} no failure/repair/cancel", "critical random failure" not in event and
          "mission cancelled:" not in event and "System to repair" not in event)


def report_checks(v, report):
    check(f"{v} report table inventory", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = records(report["ResultSummary"])
    factor = 1 if v == "control" else 2/3
    check(f"{v} summary factors", len(summary) == 1 and summary[0]["NREP"] == 1 and
          summary[0]["RTIUP"] == 40 and close(summary[0]["MTMF"], factor) and
          close(summary[0]["STMF"], factor) and
          all(summary[0][field] == 0 for field in
              ("MSTF", "MSUF", "RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(f"{v} 80 SystemResults bins spanning 0–40", len(system) == 80 and
          all(close(system[i]["STINT"], i/2) and close(system[i]["ETINT"], (i+1)/2)
              for i in range(len(system))), {"observed_bins": len(system),
                                      "last_end": system[-1]["ETINT"]})
    check(f"{v} 80 StockTotalResults bins spanning 0–40", len(stock) == 80 and
          all(close(stock[i]["STINT"], i/2) and close(stock[i]["ETINT"], (i+1)/2)
              for i in range(len(stock))))
    for i, row in enumerate(system):
        for field, actual in row.items():
            wanted = first_wave_expected(v, field, i/2)
            check(f"{v} observed system bin{i:02d} {field}",
                  actual == wanted if wanted is None or isinstance(wanted, str) else close(actual, wanted))
    nullable = {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"}
    for i, row in enumerate(stock):
        for field, actual in row.items():
            wanted = (i/2 if field == "STINT" else (i+1)/2 if field == "ETINT" else
                      None if field in nullable else 1 if field == "PNB" else 0)
            check(f"{v} stock bin{i:02d} {field}", actual == wanted if wanted is None else close(actual, wanted))
    check(f"{v} first-wave observed operating hours", close(sum(r["NSYMO"]*.5 for r in system),
          6 if v == "control" else 4))
    # Cannot verify terminal 40-hour state from SystemResults because source RCEND=16.
    check(f"{v} 40-hour terminal SystemResults available", bool(system) and
          close(system[-1]["ETINT"], 40) and close(system[-1]["NSYRY"], 2))


def main():
    try:
        contract = source_checks()
        evidence = {}
        for v in RUNS:
            event, report = run_checks(v, contract)
            evidence[v] = (event, report)
            event_checks(v, event)
            report_checks(v, report)
        check("explicit/profile byte-identical full event logs", evidence["explicit"][0] ==
              evidence["profile"][0])
        a, b = evidence["explicit"][1], evidence["profile"][1]
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check("explicit/profile report equality " + name, a[name] == b[name])
    except Exception as exc:
        check("reviewer completed without exception", False, repr(exc))
    failed = [c for c in CHECKS if not c["passed"]]
    result = {
        "schema": "simlox-a14-var06-independent-readonly/v1", "version": "1.0.0-candidate",
        "passed": not failed, "check_count": len(CHECKS),
        "passed_count": len(CHECKS)-len(failed), "failures": failed,
        "decision": "NO_GO_frozen_v100_full_horizon_report_mismatch" if failed else "GO_bounded_two_wave_equivalence",
        "finding": "The sealed event logs show two waves and byte-identical explicit/profile behavior, but frozen ResultCollection RCEND=16 truncates every SystemResults report to 32 bins despite the 40-hour horizon and second wave at 32–36. StockTotalResults has 80 bins. The invocation case_version says 1.0.1-candidate while this package contract says 1.0.0-candidate.",
        "limits": ["Only first-wave 0–16 SystemResults bins can be checked; second-wave 32–36 system exposure and 40-hour terminal state are unreported in v1.0.0.",
                   "Two waves, one repeated root, IQTY1 leaves, one unit and no failures; no claim for deeper hierarchy, overlaps, DTTOL, MUTD, GUI visuals or cross-engine behavior."],
        "source_sha256": {"contract": sha(CASE / "contract.json"),
                          "parent": sha(PARENT), "profile_donor": sha(DONOR),
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
