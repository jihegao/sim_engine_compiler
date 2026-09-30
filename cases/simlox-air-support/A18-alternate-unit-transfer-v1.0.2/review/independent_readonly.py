"""Independent read-only replay of the A18 alternate-unit diagnostic sequence.

Only standard-library parsing is used. Author validators are not imported, and
SIMLOX is never called. The adjacent JSON report is deterministic UTF-8 LF.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "A17-multi-unit-group-v1.0.0"
STAGES = {version: ROOT / f"A18-alternate-unit-transfer-{version}"
          for version in ("v1.0.0", "v1.0.1", "v1.0.2")}
OUTPUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    output: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(raw):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == "," and raw[index + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            output.append(char)
    return json.loads("".join(output))


def check(name: str, passed: bool, detail: object = None) -> None:
    CHECKS.append({"name": name, "pass": bool(passed), "detail": detail})


def close(value: object, expected: float, tol: float = 1e-6) -> bool:
    return value is not None and math.isclose(float(value), expected, rel_tol=0, abs_tol=tol)


def source_tables(document: dict) -> dict:
    found = {}
    for table in document["model"]["tables"]:
        assert table["name"] not in found
        found[table["name"]] = table
    return found


def rows(table: dict) -> list:
    result = [row for instance in table["instances"] for row in instance["rows"]]
    assert all(len(row) == len(table["columns"]) for row in result)
    return result


def business(document: dict) -> dict:
    return {name: ([column["name"] for column in table["columns"]], rows(table))
            for name, table in source_tables(document).items() if rows(table)}


def first_row_dict(entry: tuple) -> dict:
    columns, all_rows = entry
    assert len(all_rows) >= 1
    return dict(zip(columns, all_rows[0]))


def result_tables(document: dict) -> dict:
    result = {}
    for table in document["report"]["tables"]:
        assert table["name"] not in result
        columns = [column["name"] for column in table["columns"]]
        result[table["name"]] = [dict(zip(columns, row)) for instance in table["instances"]
                                 for row in instance["rows"]]
    return result


def difference(before: dict, after: dict) -> dict:
    return {name: {"before": before.get(name), "after": after.get(name)}
            for name in sorted(before.keys() | after.keys())
            if before.get(name) != after.get(name)}


def overlap(a: float, b: float, first: float, last: float) -> float:
    return max(0.0, min(b, last) - max(a, first))


manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
parent_input = PARENT / "native-input.json"
parent_hash = sha(parent_input)
parent_tables = source_tables(native_json(parent_input))
stage_contracts = {version: json_file(stage / "contract.json") for version, stage in STAGES.items()}
for version, stage in STAGES.items():
    contract = stage_contracts[version]
    check(f"{version}_parent_and_manual", contract["parent_input_sha256"] == parent_hash ==
          "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974" and
          contract["source_manual_sha256"] == sha(manual) and
          contract["source_dictionary_sha256"] == sha(dictionary))
    raw_diff = (stage / "exact-diff.json").read_bytes()
    # The builder records its LF serialization hash; native closures seal CRLF disk bytes.
    check(f"{version}_diff_LF_and_disk_provenance",
          hashlib.sha256(raw_diff.replace(b"\r\n", b"\n")).hexdigest() ==
          contract["exact_diff_sha256"] and b"\r\n" in raw_diff)

contract = stage_contracts["v1.0.2"]
check("v102_predeclared_structural_scope", contract["version"] == "1.0.2-candidate" and
      contract["publication_state"] == "not_published" and
      "ENALU=N did not suppress transfer" in contract["limitations"][2] and
      "configured variant adds exactly one AlternateUnit row" in contract["business_delta"])
configured_input = CASE / "configured-input.json"
absent_input = CASE / "absent-input.json"
check("v102_frozen_input_hashes", sha(configured_input) == contract["configured_input_sha256"] and
      sha(absent_input) == contract["absent_input_sha256"])
configured = source_tables(native_json(configured_input))
absent = source_tables(native_json(absent_input))
diff = json_file(CASE / "exact-diff.json")
check("v102_exact_A17_and_control_deltas", diff["source_sha256"] ==
      {"parent": parent_hash, "configured": sha(configured_input), "absent": sha(absent_input)} and
      diff["a17_to_configured"] == difference(parent_tables, configured) and
      diff["absent_to_configured"] == difference(absent, configured) and
      set(diff["a17_to_configured"]) ==
      {"ProblemDescription", "Control", "SystemDeployment", "Unit", "Operations",
       "OperationProfile", "UnitGroup", "UnitGroupMember", "AlternateUnit"} and
      set(diff["absent_to_configured"]) == {"ProblemDescription", "AlternateUnit"})
configured_business = business(native_json(configured_input))
absent_business = business(native_json(absent_input))
check("v102_14_vs_13_row_tables", len(configured_business) == 14 and len(absent_business) == 13)
check("v102_single_alternate_row", configured_business["AlternateUnit"][1] ==
      [["TEACH-UNIT", "TEACH-UNIT-2", 1, None]] and "AlternateUnit" not in absent)
check("v102_same_enabled_control_and_explicit_idle", configured_business["Control"] ==
      absent_business["Control"] and
      first_row_dict(configured_business["Control"])["ENALU"] == "Y" and
      configured_business["Operations"][1] == absent_business["Operations"][1] ==
      [["TEACH-UNIT", "BASIC-SCHEDULE", None], ["TEACH-UNIT-2", "ALT-IDLE", None]] and
      [row[4] for row in configured_business["OperationProfile"][1]] == [1, 0] and
      [row[2] for row in configured_business["SystemDeployment"][1]] == [1, 2] and
      configured_business["MissionType"][1][0][2:4] == [2, 2])

RUNS = [
    ("v1.0.0", "enabled", "enabled-input.json", "a18-enabled-v100-20261001-01", 14),
    ("v1.0.1", "enabled", "enabled-input.json", "a18-enabled-v101-20261001-01", 14),
    ("v1.0.1", "disabled", "disabled-input.json", "a18-disabled-v101-20261001-01", 14),
    ("v1.0.2", "configured", "configured-input.json", "a18-configured-v102-20261001-01", 14),
    ("v1.0.2", "absent", "absent-input.json", "a18-absent-v102-20261001-01", 13),
]
evidence: dict[str, dict] = {}
for version, label, input_name, run_name, expected_tables in RUNS:
    stage = STAGES[version]
    run = stage / "runs" / run_name
    source = stage / input_name
    key = f"{version}_{label}"
    invocation = json_file(run / "invocation.json")
    closure = json_file(run / "closure.json")
    steps = json_file(run / "steps.json")
    before = closure["source_hashes_before"]
    check(f"{key}_native_identity_and_frozen_source", invocation["run_id"] ==
          closure["run_id"] == run_name and closure["error"] is None and
          invocation["input_sha256"] == sha(source) == before["input"] and
          invocation["parent_sha256"] == parent_hash == before["parent"] and
          invocation["contract_sha256"] == sha(stage / "contract.json") == before["contract"] and
          before == closure["source_hashes_after"] and
          before["builder"] == sha(stage / "build.py") and
          before["exact_diff"] == sha(stage / "exact-diff.json") and
          before["diff_checker"] == sha(stage / "describe_diff.py") and
          before["checker"] == sha(stage / "check_roundtrip.py") and
          before["runner_script"] == sha(stage / "run_native_ssh.ps1"))
    check(f"{key}_all_raw_hashes", closure["invocation_sha256"] ==
          sha(run / "invocation.json") and len(closure["raw"]) == 12 and
          all((run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"] for name, meta in closure["raw"].items()))
    check(f"{key}_five_guarded_steps", invocation["session_id"] == 0 and
          invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and
          [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["exit_code"] == 0 and step["status"] == "completed" and
              step["gui_preserved"] for step in steps))
    exported = business(native_json(run / "roundtrip-raw.json"))
    intended = business(native_json(source))
    check(f"{key}_exact_populated_roundtrip", len(intended) == expected_tables and
          all(exported.get(name) == data for name, data in intended.items()))
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{key}_zero_conversion_errors", "Errors: 0," in log and
          "warning #108" in log and "warning #126" in log and
          "Saving results" in log)
    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    report = result_tables(native_json(run / "report-raw.json"))
    check(f"{key}_native_report_shape", len(report["ResultSummary"]) == 1 and
          len(report["SystemResults"]) == len(report["StockTotalResults"]) == 72 and
          all(close(row["STINT"], i/2) and close(row["ETINT"], (i+1)/2)
              for series in (report["SystemResults"], report["StockTotalResults"])
              for i, row in enumerate(series)))
    evidence[key] = {"run": run, "event": event, "report": report, "log": log,
                     "raw_report_sha256": sha(run / "report-raw.json"),
                     "raw_model_log_sha256": sha(run / "model.log"),
                     "closure_sha256": sha(run / "closure.json")}

v100 = evidence["v1.0.0_enabled"]
check("v100_default_profile_diagnostic", "notice #488" in v100["log"] and
      "Default operational profile generated for unit: TEACH-UNIT-2" in v100["log"] and
      "Time: 0 <TEACH-UNIT-2> mission ordered:" in v100["event"] and
      "mission starting, duration: 36" in v100["event"] and
      "Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled:" in v100["event"] and
      "is moved to alternate unit:" not in v100["event"] and
      close(sum(row["NSYMO"]*.5 for row in v100["report"]["SystemResults"]), 72) and
      close(v100["report"]["ResultSummary"][0]["MSTF"], 0))
v101_yes = evidence["v1.0.1_enabled"]
v101_no = evidence["v1.0.1_disabled"]
check("v101_ENALU_nonisolating_diagnostic", "warning #188" in v101_no["log"] and
      "warning #188" not in v101_yes["log"] and
      v101_yes["raw_model_log_sha256"] == v101_no["raw_model_log_sha256"] and
      v101_yes["event"] == v101_no["event"] and
      all(v101_yes["report"][name] == v101_no["report"][name]
          for name in ("ResultSummary", "SystemResults", "StockTotalResults")) and
      "is moved to alternate unit: <TEACH-UNIT-2>" in v101_no["event"])
v101_sources = [business(native_json(STAGES["v1.0.1"] / f"{name}-input.json"))
                for name in ("enabled", "disabled")]
check("v101_ENALU_only_behavior_field", {name for name in v101_sources[0]
      if v101_sources[0][name] != v101_sources[1][name]} ==
      {"Control", "ProblemDescription"} and
      first_row_dict(v101_sources[0]["Control"])["ENALU"] == "Y" and
      first_row_dict(v101_sources[1]["Control"])["ENALU"] == "N")

yes = evidence["v1.0.2_configured"]
no = evidence["v1.0.2_absent"]
original = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
moved = "<BASIC-MISSION,TEACH-UNIT-2,0,0,0>"
check("v102_configured_full_transfer_chain",
      "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION" in yes["event"] and
      f"Time: 7 {original} mission allocates system: <TEACH-AIR-01,0>" in yes["event"] and
      f"Time: 7 {original} is moved to alternate unit: <TEACH-UNIT-2>" in yes["event"] and
      "Time: 7 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>" in yes["event"] and
      all(f"Time: 7 {moved} mission allocates system: <TEACH-AIR-01,{i}>" in yes["event"]
          for i in (1, 2)) and
      f"Time: 8 {moved} mission starting, duration: 2 : <TEACH-AIR-01,1>,<TEACH-AIR-01,2>" in yes["event"] and
      f"Time: 10 {moved} mission success:" in yes["event"] and
      f"Time: 10 {moved} mission completed: <TEACH-AIR-01,1>,<TEACH-AIR-01,2>" in yes["event"])
check("v102_absent_denial_chain", "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION" in no["event"] and
      f"Time: 7 {original} mission allocates system: <TEACH-AIR-01,0>" in no["event"] and
      f"Time: 8.33333 {original} mission cancelled:" in no["event"] and
      "is moved to alternate unit:" not in no["event"] and
      "mission starting, duration:" not in no["event"] and
      "mission success:" not in no["event"])
check("v102_no_default_or_fault_events", all(
      "<TEACH-UNIT-2_TEACH-AIR-01_MISSION>" not in data["event"] and
      data["event"].count("mission ordered:") == 1 and
      "critical CM failure" not in data["event"] and
      "notice #488" not in data["log"]
      for data in (yes, no)))
check("v102_converter_classification", "Errors: 0, Warnings: 2, Notes: 1" in yes["log"] and
      "notice #320" in yes["log"] and
      "Errors: 0, Warnings: 2, Notes: 0" in no["log"] and
      "notice #320" not in no["log"])

for label, data in (("configured", yes), ("absent", no)):
    report = data["report"]
    summary = report["ResultSummary"][0]
    target = 1 if label == "configured" else 0
    check(f"v102_{label}_native_summary", all(close(summary[field], value)
          for field, value in (("NREP", 1), ("RTILW", 0), ("RTIUP", 36),
                               ("MSTF", target), ("MSUF", target),
                               ("MTMF", target), ("STMF", target))))
    assigned = [(7, 10), (7, 10)] if label == "configured" else [(7, 8+1/3)]
    operating = [(8, 10), (8, 10)] if label == "configured" else []
    for index, row in enumerate(report["SystemResults"]):
        a, b = index/2, (index+1)/2
        ma = 2*sum(overlap(a, b, start, end) for start, end in assigned)
        mo = 2*sum(overlap(a, b, start, end) for start, end in operating)
        check(f"v102_{label}_system_bin_{index:02d}", all(close(row[field], value)
              for field, value in (("NSYMA", ma), ("NSYMO", mo), ("NSYMR", ma-mo),
                                   ("NSYRY", 3-ma), ("NSYA", 3), ("STACC", mo),
                                   ("NFAIL", 0), ("NREPT", 0))))
    check(f"v102_{label}_stock_no_demand", all(row["PNB"] == 1 and all(
          value in (0, None) for key, value in row.items()
          if key not in ("STINT", "ETINT", "PNB"))
          for row in report["StockTotalResults"]))
    check(f"v102_{label}_terminal_and_integral", close(report["SystemResults"][-1]["NSYRY"], 3) and
          close(report["SystemResults"][-1]["NSYMA"], 0) and
          close(report["SystemResults"][-1]["NSYMO"], 0) and
          close(sum(row["NSYMO"]*.5 for row in report["SystemResults"]), 4*target))

passed = sum(item["pass"] for item in CHECKS)
result = {
    "schema": "simlox-a18-alternate-unit-independent-readonly/v1",
    "case_id": "A18", "version": "1.0.2-candidate",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go_structural_transfer_only" if passed == len(CHECKS) else "no_go_evidence_mismatch",
    "passed": passed, "total": len(CHECKS), "checks": CHECKS,
    "source_sha256": {"parent_input": parent_hash, "contract": sha(CASE / "contract.json"),
                      "configured_input": sha(configured_input), "absent_input": sha(absent_input),
                      "exact_diff_disk": sha(CASE / "exact-diff.json"),
                      "exact_diff_LF_serialization": contract["exact_diff_sha256"]},
    "native_sha256": {name: {field: data[field] for field in
                             ("closure_sha256", "raw_model_log_sha256", "raw_report_sha256")}
                      for name, data in evidence.items()},
    "finding": "With one AlternateUnit row, the ordinary aircraft is released, the same fixed mission moves to TEACH-UNIT-2, alternate aircraft #1/#2 fly 8–10 and succeed, with four operating aircraft-hours. Without that row, the ordinary unit allocates only #0 and cancels at 8.33333; no mission launches. Both variants use ENALU=Y, finish with three ready aircraft, and have no stock or failure events.",
    "diagnostic_disposition": "v1.0.0 generated an unintended 0–36 alternate default mission; v1.0.1 ENALU=Y/N logs are byte-identical despite warning #188 for N. Both are diagnostics, not evidence that the ENALU switch isolates transfer.",
    "limitations": [
        "The positive result isolates the presence of one AlternateUnit row under ENALU=Y in this single seed, fixed demand, no-fault model.",
        "The native converter emits notice #320 that AlternateUnit modelling is obsolete; unit-group modelling is recommended.",
        "ENALU=N did not suppress transfer in the earlier v1.0.1 pair; broader ENALU semantics are unverified.",
        "The contract exact_diff_sha256 is the LF serialization hash; sealed on-disk CRLF exact-diff bytes have a distinct SHA-256. Their parsed table deltas match source exactly.",
        "Priority among multiple alternates, delayed readiness, failure or contention, GUI display and cross-engine behavior are outside this review.",
        "Native JSON trailing commas are normalized only in memory; raw closure hashes bind original bytes.",
    ],
}
OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{passed}/{len(CHECKS)} {result['decision']}")
for item in CHECKS:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if passed == len(CHECKS) else 1)
