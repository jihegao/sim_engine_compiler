"""Independent read-only replay of the sealed A14 v1.0.1 native pair.

Uses only the Python standard library and raw source/native files. It imports
no author validator or checker and does not invoke SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
DIAGNOSTIC = ROOT / "A14-continuous-mutual-v1.0.0"
RUNS = {name: CASE / "runs" / f"a14-{name}-v101-20261001-01"
        for name in ("control", "dependent")}
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for i, char in enumerate(raw):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def check(name: str, passed: bool, detail: object = None) -> None:
    CHECKS.append({"name": name, "pass": bool(passed), "detail": detail})


def near(value: object, target: float) -> bool:
    return value is not None and math.isclose(float(value), target, rel_tol=0, abs_tol=1e-6)


def source_tables(document: dict) -> dict:
    result = {}
    for table in document["model"]["tables"]:
        assert table["name"] not in result
        result[table["name"]] = table
    return result


def business(document: dict) -> dict:
    result = {}
    for name, table in source_tables(document).items():
        records = [row for instance in table["instances"] for row in instance["rows"]]
        if records:
            assert all(len(row) == len(table["columns"]) for row in records)
            result[name] = ([col["name"] for col in table["columns"]], records)
    return result


def difference(before: dict, after: dict) -> dict:
    return {name: {"before": before.get(name), "after": after.get(name)}
            for name in sorted(before.keys() | after.keys())
            if before.get(name) != after.get(name)}


def result_tables(document: dict) -> dict:
    result = {}
    for table in document["report"]["tables"]:
        assert table["name"] not in result
        columns = [col["name"] for col in table["columns"]]
        result[table["name"]] = [dict(zip(columns, row)) for instance in table["instances"]
                                 for row in instance["rows"]]
    return result


def overlap(a: float, b: float, first: float, last: float) -> float:
    return max(0.0, min(b, last) - max(a, first))


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
check("predeclared_bounded_contract", contract["case_version"] == "1.0.1-candidate" and
      contract["publication_state"] == "not_published" and
      "predecessor-completion abort" in contract["limits"][0] and
      "opposing ordinary rows launched concurrently" in contract["excluded_diagnostic"]["reason"])
check("manual_dictionary_and_A05_parent", sha(manual) == contract["source"]["manual_sha256"] and
      sha(dictionary) == contract["source"]["dictionary_sha256"] and
      sha(PARENT) == contract["parent"]["input_sha256"] ==
      "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea" and
      (CASE / contract["parent"]["signoff"]).is_file())
check("two_frozen_inputs_and_diff_hash", all(sha(CASE / f"{variant}-input.json") ==
      contract["inputs_sha256"][variant] == diff["sources_sha256"][variant]
      for variant in RUNS) and
      sha(PARENT) == diff["sources_sha256"]["parent"] and
      sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
parent = source_tables(native(PARENT))
control = source_tables(native(CASE / "control-input.json"))
dependent = source_tables(native(CASE / "dependent-input.json"))
check("exact_parent_and_pair_delta", len(parent) == len(control) == 31 and
      len(dependent) == 32 and
      diff["changes"]["parent_to_control"] == difference(parent, control) and
      diff["changes"]["control_to_dependent"] == difference(control, dependent) and
      set(diff["changes"]["parent_to_control"]) ==
      {"MissionType", "OperationProfile", "ProblemDescription"} and
      set(diff["changes"]["control_to_dependent"]) ==
      {"MissionDependence", "ProblemDescription"})
check("13_14_source_row_tables", len(business(native(CASE / "control-input.json"))) == 13 and
      len(business(native(CASE / "dependent-input.json"))) == 14)
dep_columns, dep_rows = business(native(CASE / "dependent-input.json"))["MissionDependence"]
dep_row = dict(zip(dep_columns, dep_rows[0]))
check("single_continuous_dependence", len(dep_rows) == 1 and dep_row ==
      {"DUNID": "TEACH-UNIT", "DMTID": "EXECUTE", "DSTIM": 8.0,
       "PUNID": "TEACH-UNIT", "PMTID": "SUPPORT", "PSTIM": 8.0,
       "DTYPE": "CONTINUOUS", "MUTD": "N", "DTTOL": None, "NOTE": None} and
      "MissionDependence" not in business(native(CASE / "control-input.json")))
mission_cols, mission_rows = business(native(CASE / "dependent-input.json"))["MissionType"]
missions = [dict(zip(mission_cols, row)) for row in mission_rows]
check("two_continuous_mission_templates", len(missions) == 2 and
      [(r["MTID"], r["DURN"], r["MPAT"], r["NOS"], r["MNOS"]) for r in missions] ==
      [("SUPPORT", 2, "CONTINUOUS", 1, 1),
       ("EXECUTE", 4, "CONTINUOUS", 1, 1)])

EVIDENCE: dict[str, dict] = {}
for variant, run in RUNS.items():
    source = CASE / f"{variant}-input.json"
    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    steps = load(run / "steps.json")
    before = closure["source_hashes_before"]
    check(f"{variant}_fresh_source_seal", invocation["run_id"] == closure["run_id"] == run.name and
          closure["error"] is None and before == closure["source_hashes_after"] and
          before["input"] == invocation["input_sha256"] == sha(source) and
          before["parent"] == invocation["parent_sha256"] == sha(PARENT) and
          before["contract"] == invocation["contract_sha256"] == sha(CASE / "contract.json") and
          before["builder"] == sha(CASE / "build.py") and
          before["exact_diff"] == sha(CASE / "exact-diff.json") and
          before["diff_checker"] == sha(CASE / "describe_diff.py") and
          before["checker"] == sha(CASE / "check_roundtrip.py") and
          before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    check(f"{variant}_12_raw_hashes", closure["invocation_sha256"] ==
          sha(run / "invocation.json") and len(closure["raw"]) == 12 and
          set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} -
          {"invocation.json", "closure.json"} and
          all((run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"] for name, meta in closure["raw"].items()))
    check(f"{variant}_session0_gui_mutex_five_steps", invocation["session_id"] == 0 and
          invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and
          [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["status"] == "completed" and step["exit_code"] == 0 and
              step["gui_preserved"] for step in steps))
    check(f"{variant}_planned_commands_and_order", all(
          steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"]
          for i in range(4)) and
          steps[4]["arguments"] == invocation["planned_check"]["arguments"] and
          all(steps[i]["started_utc"] <= steps[i]["completed_utc"] and
              steps[i]["completed_utc"] <= steps[i+1]["started_utc"]
              for i in range(4)) and
          steps[4]["started_utc"] <= steps[4]["completed_utc"])
    exported = business(native(run / "roundtrip-raw.json"))
    wanted = business(native(source))
    check(f"{variant}_exact_business_row_roundtrip", len(wanted) ==
          (13 if variant == "control" else 14) and
          all(exported.get(name) == value for name, value in wanted.items()))
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{variant}_zero_error_conversion", "Errors: 0, Warnings: 2, Notes: 0" in log and
          "warning #108" in log and "warning #126" in log and
          "Saving results" in log)
    report = result_tables(native(run / "report-raw.json"))
    check(f"{variant}_32_report_bins", len(report["ResultSummary"]) == 1 and
          len(report["SystemResults"]) == len(report["StockTotalResults"]) == 32 and
          all(near(row["STINT"], i/2) and near(row["ETINT"], (i+1)/2)
              for series in (report["SystemResults"], report["StockTotalResults"])
              for i, row in enumerate(series)))
    EVIDENCE[variant] = {"run": run, "event": (run / "model.log").read_text(
        encoding="utf-8-sig", errors="replace"), "report": report}

support = "<SUPPORT,TEACH-UNIT,0,0,0>"
execute = "<EXECUTE,TEACH-UNIT,0,0,1>"
for variant, data in EVIDENCE.items():
    event = data["event"]
    check(f"{variant}_same_two_launches", all(line in event for line in
          ("Time: 7 <TEACH-UNIT> mission ordered: SUPPORT",
           "Time: 7 <TEACH-UNIT> mission ordered: EXECUTE",
           f"Time: 8 {support} mission starting, duration: 2 : <TEACH-AIR-01,0>",
           f"Time: 8 {execute} mission starting, duration: 4 : <TEACH-AIR-01,1>")) and
          event.count("mission starting, duration:") == 2)
    check(f"{variant}_support_success_and_no_fault", all(line in event for line in
          (f"Time: 10 {support} mission success:",
           f"Time: 10 {support} mission completed: <TEACH-AIR-01,0>")) and
          "critical CM failure" not in event and "mission cancelled:" not in event)
control_event = EVIDENCE["control"]["event"]
dependent_event = EVIDENCE["dependent"]["event"]
check("control_EXECUTE_completes_at_12", f"Time: 12 {execute} mission success:" in control_event and
      f"Time: 12 {execute} mission completed: <TEACH-AIR-01,1>" in control_event and
      "mission aborted:" not in control_event and control_event.count("mission success:") == 2)
check("dependent_EXECUTE_aborts_at_support_end", f"Time: 10 {execute} mission aborted: <TEACH-AIR-01,1>" in
      dependent_event and
      f"Time: 10 {execute} task completed: (aborted):<TEACH-AIR-01,1>" in dependent_event and
      f"Time: 10 {execute} aborted mission completed: <TEACH-AIR-01,1>" in dependent_event and
      f"{execute} mission success:" not in dependent_event and
      dependent_event.count("mission aborted:") == 1 and
      dependent_event.count("mission success:") == 1)

for variant, data in EVIDENCE.items():
    report = data["report"]
    summary = report["ResultSummary"][0]
    factor = 1 if variant == "control" else 2/3
    check(f"{variant}_continuous_summary", all(near(summary[field], value)
          for field, value in (("NREP", 1), ("RTILW", 0), ("RTIUP", 16),
                               ("MTMF", factor), ("STMF", factor),
                               ("MSTF", 0), ("MSUF", 0),
                               ("RSMTMF", 0), ("RSMSTF", 0),
                               ("RSMSUF", 0), ("RSSTMF", 0))))
    assigned = [(7, 10), (7, 12 if variant == "control" else 10)]
    operating = [(8, 10), (8, 12 if variant == "control" else 10)]
    for i, row in enumerate(report["SystemResults"]):
        a, b = i/2, (i+1)/2
        ma = 2*sum(overlap(a, b, first, last) for first, last in assigned)
        mo = 2*sum(overlap(a, b, first, last) for first, last in operating)
        check(f"{variant}_system_bin_{i:02d}", all(near(row[field], target)
              for field, target in (("NSYMA", ma), ("NSYMO", mo), ("NSYMR", ma-mo),
                                    ("NSYRY", 2-ma), ("NSYA", 2), ("STACC", mo),
                                    ("NFAIL", 0), ("NREPT", 0))))
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": a, "ETINT": b, "NSYMA": ma, "NSYMO": mo,
                    "NSYMR": ma-mo, "NSYRY": 2-ma, "NSYA": 2,
                    "STACC": mo, "FTMO": 1 if 8 <= a < 10 else
                    (.5 if variant == "control" and 10 <= a < 12 else 0),
                    "SYDT": None}
        check(f"{variant}_complete_system_fields_{i:02d}", all(
              row[field] == value if isinstance(value, (str, type(None))) else
              near(row[field], value)
              for field, value in ((field, expected.get(field, 0)) for field in row)))
    stock = report["StockTotalResults"]
    check(f"{variant}_stock_no_demand", all(row["PNB"] == 1 and all(
          value in (0, None) for key, value in row.items()
          if key not in ("STINT", "ETINT", "PNB")) for row in stock))
    system = report["SystemResults"]
    check(f"{variant}_aircraft_hour_integral_and_terminal", near(
          sum(row["NSYMO"]*.5 for row in system), 6 if variant == "control" else 4) and
          near(sum(row["STACC"]*.5 for row in system), 6 if variant == "control" else 4) and
          all(near(system[-1][field], value) for field, value in
              (("NSYRY", 2), ("NSYMA", 0), ("NSYMO", 0))))

old_contract = load(DIAGNOSTIC / "contract.json")
old_run = DIAGNOSTIC / "runs" / "a14-opposing-v100-20261001-01"
old_inv, old_seal = load(old_run / "invocation.json"), load(old_run / "closure.json")
old_event = (old_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
check("v100_opposing_source_and_seal", old_contract["publication_state"] == "not_published" and
      sha(DIAGNOSTIC / "opposing-input.json") == old_contract["inputs_sha256"]["opposing"] ==
      old_seal["source_hashes_before"]["input"] and
      old_seal["source_hashes_before"] == old_seal["source_hashes_after"] and
      old_seal["source_hashes_before"]["contract"] == sha(DIAGNOSTIC / "contract.json") and
      old_seal["invocation_sha256"] == sha(old_run / "invocation.json") and
      old_inv["run_id"] == old_seal["run_id"] == old_run.name and
      all(sha(old_run / name) == meta["sha256"] for name, meta in old_seal["raw"].items()))
check("v100_opposing_not_deadlocked", "Time: 8 <SUPPORT,TEACH-UNIT,0,0,0> mission starting" in
      old_event and "Time: 8 <EXECUTE,TEACH-UNIT,0,0,1> mission starting" in old_event and
      "Time: 12 <SUPPORT,TEACH-UNIT,0,0,0> mission success:" in old_event and
      "Time: 12 <EXECUTE,TEACH-UNIT,0,0,1> mission aborted:" in old_event and
      "mission cancelled:" not in old_event)
for variant in ("oneway", "mutual"):
    diagnostic_run = DIAGNOSTIC / "runs" / f"a14-{variant}-v100-20261001-01"
    diagnostic_seal = load(diagnostic_run / "closure.json")
    diagnostic_event = (diagnostic_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"v100_{variant}_raw_seal", diagnostic_seal["run_id"] == diagnostic_run.name and
          diagnostic_seal["invocation_sha256"] == sha(diagnostic_run / "invocation.json") and
          all((diagnostic_run / name).stat().st_size == meta["bytes"] and
              sha(diagnostic_run / name) == meta["sha256"]
              for name, meta in diagnostic_seal["raw"].items()))
    check(f"v100_{variant}_launch_and_abort_not_deadlock", all(line in diagnostic_event for line in
          ("Time: 8 <SUPPORT,TEACH-UNIT,0,0,0> mission starting",
           "Time: 8 <EXECUTE,TEACH-UNIT,0,0,1> mission starting",
           "Time: 12 <SUPPORT,TEACH-UNIT,0,0,0> mission success:",
           "Time: 12 <EXECUTE,TEACH-UNIT,0,0,1> mission aborted:")) and
          "mission cancelled:" not in diagnostic_event)
for variant, data in EVIDENCE.items():
    terminal_hour = 12 if variant == "control" else 10
    check(f"{variant}_terminal_event_ready_two", f"Time: {terminal_hour} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in
          data["event"])

passed = sum(c["pass"] for c in CHECKS)
result = {
    "schema": "simlox-a14-continuous-end-abort-independent-readonly/v1",
    "case_id": "A14", "version": "1.0.1-candidate",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go_one_continuous_end_abort" if passed == len(CHECKS) else "no_go_evidence_mismatch",
    "passed": passed, "total": len(CHECKS), "checks": CHECKS,
    "source_sha256": {"parent": sha(PARENT), "contract": sha(CASE / "contract.json"),
                      "control": sha(CASE / "control-input.json"),
                      "dependent": sha(CASE / "dependent-input.json"),
                      "exact_diff": sha(CASE / "exact-diff.json")},
    "native_sha256": {variant: {"closure": sha(run / "closure.json"),
                                "model_log": sha(run / "model.log"),
                                "report": sha(run / "report-raw.json")}
                      for variant, run in RUNS.items()},
    "excluded_diagnostic_sha256": {"closure": sha(old_run / "closure.json"),
                                     "model_log": sha(old_run / "model.log")},
    "finding": "Both variants launch SUPPORT on aircraft #0 and EXECUTE on #1 at hour 8. In the control SUPPORT succeeds at 10 and EXECUTE succeeds at 12. With one CONTINUOUS dependence row, SUPPORT succeeds at 10 and EXECUTE aborts and returns at 10. Operating exposure falls from six to four aircraft-hours; the native time factors fall from 1 to about 2/3. Both finish with two ready aircraft and no stock or fault demand.",
    "diagnostic_disposition": "The separate v1.0.0 opposing-row run launched both missions at hour 8 rather than deadlocking, so that hypothesis remains excluded and unpublished.",
    "limitations": [
        "The evidence supports one predecessor-completion abort with a single CONTINUOUS dependence row; it does not establish a generic dependency rule.",
        "MSTF and MSUF remain zero in both runs for these continuous missions despite native success events; MTMF/STMF are time factors, not fixed-wave success counts.",
        "No positive-duration suspension or DTTOL behavior is exercised. MUTD, mutual deadlock, profiles, regenerative gaps and cross-unit dependencies remain open.",
        "One seed, no failures or support-resource contention; GUI visual content and cross-engine parity are outside this review.",
        "Native JSON trailing commas are removed only in parser memory; closure SHA-256 values bind raw bytes.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{passed}/{len(CHECKS)} {result['decision']}")
for item in CHECKS:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if passed == len(CHECKS) else 1)
