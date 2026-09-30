"""Independent, standard-library-only replay of the sealed J07 mixed-denominator run.

Reads source and native evidence without importing author code or invoking SIMLOX.
Writes only the adjacent deterministic JSON review artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
A07 = ROOT / "A07-regenerative-relief-v1.0.0"
NATIVE = CASE / "runs" / "j07-fixed-regen-v100-20261001-01"
A07_RUN = A07 / "runs" / "a07-regenerative-relief-v100-ssh-20260930-01"
REPORTS = CASE / "runs" / "report-settings"
OUTPUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    """Remove native writer's trailing commas in memory, retaining raw file bytes."""
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


def close(actual: object, expected: float, tolerance: float = 1e-6) -> bool:
    return actual is not None and math.isclose(float(actual), expected, rel_tol=0, abs_tol=tolerance)


def tables(document: dict) -> dict:
    found = {}
    for table in document["model"]["tables"]:
        assert table["name"] not in found
        found[table["name"]] = table
    return found


def business(document: dict) -> dict:
    found = {}
    for name, table in tables(document).items():
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            assert all(len(row) == len(table["columns"]) for row in rows)
            found[name] = ([col["name"] for col in table["columns"]], rows)
    return found


def results(document: dict) -> dict:
    found = {}
    for table in document["report"]["tables"]:
        assert table["name"] not in found
        columns = [col["name"] for col in table["columns"]]
        found[table["name"]] = [dict(zip(columns, row)) for instance in table["instances"]
                                for row in instance["rows"]]
    return found


def overlap(a: float, b: float, start: float, end: float) -> float:
    return max(0.0, min(b, end) - max(a, start))


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
check("predeclared_bounded_contract", contract["schema"] ==
      "simlox-j07-fixed-regenerative-denominator-contract/v1" and
      contract["publication_state"] == "not_published" and
      "MSTF=MSUF=1/2" in contract["pre_run_metric_hypothesis"])
check("manual_dictionary_hashes", sha(manual) == contract["source_manual_sha256"] and
      sha(dictionary) == contract["source_dictionary_sha256"])
check("A07_accepted_parent_input", sha(A07 / "native-input.json") ==
      contract["parent_input_sha256"] == diff["parent_sha256"] and
      sha(CASE / "native-input.json") == contract["input_sha256"] == diff["child_sha256"])
parent, child = native(A07 / "native-input.json"), native(CASE / "native-input.json")
pt, ct = tables(parent), tables(child)
changed = {name for name in pt if pt[name] != ct[name]}
check("exact_three_table_delta", set(pt) == set(ct) and len(pt) == 31 and
      changed == set(diff["changed_tables"]) ==
      {"ProblemDescription", "MissionType", "OperationProfile"} and
      all(diff["changed_tables"][name]["before"] == pt[name]["instances"][0]["rows"] and
          diff["changed_tables"][name]["after"] == ct[name]["instances"][0]["rows"]
          for name in changed))
check("13_row_containing_tables", len(business(parent)) == len(business(child)) == 13)
mission = business(child)["MissionType"][1]
profile = business(child)["OperationProfile"][1]
check("model_regenerative_plus_fixed_demands", len(mission) == len(profile) == 3 and
      [r[0] for r in mission] == ["BASIC-MISSION", "FIXED-OK", "FIXED-DENY"] and
      [(r[2], r[3], r[5]) for r in mission] == [(1, 1, 4), (1, 1, 4), (3, 3, 4)] and
      [(r[1], r[2], r[3]) for r in profile] ==
      [("BASIC-MISSION", 8, "REGENERATIVE"), ("FIXED-OK", 20, "SCHEDULED"),
       ("FIXED-DENY", 28, "SCHEDULED")] and
      profile[0][6] == 8 and all(r[4] == 1 and r[6] == 0 and close(r[8], 1/3)
                                  for r in profile[1:]))

inv = load(NATIVE / "invocation.json")
seal = load(NATIVE / "closure.json")
steps = load(NATIVE / "steps.json")
check("fresh_native_identity", inv["run_id"] == seal["run_id"] == NATIVE.name and
      seal["error"] is None and inv["input_sha256"] == contract["input_sha256"] and
      inv["parent_sha256"] == contract["parent_input_sha256"])
check("fresh_contract_bound_before_after", inv["contract_sha256"] == sha(CASE / "contract.json") and
      seal["source_hashes_before"] == seal["source_hashes_after"] and
      seal["source_hashes_before"]["contract"] == inv["contract_sha256"] and
      seal["source_hashes_before"]["input"] == sha(CASE / "native-input.json") and
      seal["source_hashes_before"]["parent"] == sha(A07 / "native-input.json") and
      seal["source_hashes_before"]["builder"] == sha(CASE / "build.py") and
      seal["source_hashes_before"]["checker"] == sha(CASE / "check_roundtrip.py") and
      seal["source_hashes_before"]["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
check("native_raw_sha_closure", seal["invocation_sha256"] == sha(NATIVE / "invocation.json") and
      len(seal["raw"]) == 12 and all((NATIVE / name).is_file() and
      (NATIVE / name).stat().st_size == meta["bytes"] and sha(NATIVE / name) == meta["sha256"]
      for name, meta in seal["raw"].items()))
check("native_ssh_mutex_gui_guard", inv["session_id"] == 0 and inv["ssh_connection_present"] and
      "sshd.exe" in inv["ssh_ancestor_names"] and
      inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
      inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] > 0)
check("five_successful_steps", [s["name"] for s in steps] ==
      ["import", "export", "calc", "jsonreport", "check_import_export"] and
      all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"]
          for s in steps))
exported = business(native(NATIVE / "roundtrip-raw.json"))
check("exact_13_table_business_roundtrip", all(exported.get(name) == data
      for name, data in business(child).items()))
log = (NATIVE / "run.log").read_text(encoding="utf-8-sig", errors="replace")
check("zero_errors_classified_warnings", "Errors: 0, Warnings: 2, Notes: 0" in log and
      "warning #108" in log and "warning #126" in log and "Saving results" in log)

event = (NATIVE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
for index, start, end, aircraft in ((0, 8, 12, 0), (1, 10, 14, 1),
                                    (2, 12, 16, 0), (3, 14, 16, 1)):
    marker = f"<BASIC-MISSION,TEACH-UNIT,0,{index},{index}>"
    check(f"regenerative_child_{index}",
          f"Time: {start} {marker} mission starting, duration: 4 : <TEACH-AIR-01,{aircraft}>" in event and
          f"Time: {end} {marker} mission success:" in event and
          f"Time: {end} {marker} mission completed: <TEACH-AIR-01,{aircraft}>" in event)
fixed_ok = "<FIXED-OK,TEACH-UNIT,0,0,4>"
fixed_deny = "<FIXED-DENY,TEACH-UNIT,0,0,5>"
check("fixed_success_event_chain", "Time: 19 <TEACH-UNIT> mission ordered: FIXED-OK" in event and
      f"Time: 20 {fixed_ok} mission starting, duration: 4 : <TEACH-AIR-01,0>" in event and
      f"Time: 24 {fixed_ok} mission success:" in event and
      f"Time: 24 {fixed_ok} mission completed: <TEACH-AIR-01,0>" in event)
check("fixed_denied_event_chain", "Time: 27 <TEACH-UNIT> mission ordered: FIXED-DENY" in event and
      f"Time: 27 {fixed_deny} mission activated, systems requested: 3" in event and
      all(f"Time: 27 {fixed_deny} mission allocates system: <TEACH-AIR-01,{i}>" in event
          for i in (0, 1)) and
      f"Time: 28.3333 {fixed_deny} mission cancelled:" in event and
      f"{fixed_deny} mission starting" not in event)
check("event_cardinality_no_fault", event.count("mission starting, duration: 4") == 5 and
      event.count("mission success:") == 5 and event.count("mission completed:") == 5 and
      event.count("mission cancelled:") == 1 and "critical CM failure" not in event)

default = results(native(NATIVE / "report-raw.json"))
summary = default["ResultSummary"][0]
check("native_global_summary", len(default["ResultSummary"]) == 1 and
      all(close(summary[key], expected) for key, expected in
          (("NREP", 1), ("RTILW", 0), ("RTIUP", 36), ("MSTF", .5),
           ("MSUF", .5), ("MTMF", .75), ("STMF", 18/28))))
system, stock = default["SystemResults"], default["StockTotalResults"]
check("native_72_aligned_bins", len(system) == len(stock) == 72 and all(
      close(row["STINT"], i/2) and close(row["ETINT"], (i+1)/2)
      for series in (system, stock) for i, row in enumerate(series)))
assigned = [(7, 12), (9, 14), (12, 16), (14, 16), (19, 24),
            (27, 28 + 1/3), (27, 28 + 1/3)]
operating = [(8, 12), (10, 14), (12, 16), (14, 16), (20, 24)]
for index, row in enumerate(system):
    a, b = index/2, (index+1)/2
    ma = 2 * sum(overlap(a, b, x, y) for x, y in assigned)
    mo = 2 * sum(overlap(a, b, x, y) for x, y in operating)
    check(f"system_bin_{index:02d}", all(close(row[key], target) for key, target in
          (("NSYMA", ma), ("NSYMO", mo), ("NSYRY", 2-ma),
           ("NSYMR", ma-mo), ("STACC", mo), ("NSYA", 2), ("NFAIL", 0),
           ("NREPT", 0))))
check("integrated_aircraft_hours", close(sum(r["NSYMO"]*.5 for r in system), 18) and
      close(sum(r["STACC"]*.5 for r in system), 18) and
      close(sum(r["NSYMA"]*.5 for r in system), 23+2/3))
check("stock_no_demand", all(row["PNB"] == 1 and all(value in (0, None)
      for key, value in row.items() if key not in ("STINT", "ETINT", "PNB"))
      for row in stock))
check("terminal_ready_two", close(system[-1]["NSYRY"], 2) and
      close(system[-1]["NSYMA"], 0) and close(system[-1]["NSYMO"], 0))

report_data: dict[str, dict] = {}
report_shas: dict[str, str] = {}
settings = {"all": "all.sxs", "regenerative": "regenerative.sxs",
            "fixed-ok": "fixed-ok.sxs", "fixed-deny": "fixed-deny.sxs"}
check("A07_parent_native_sxo_sealed", sha(A07_RUN / "model.sxo") ==
      load(A07_RUN / "closure.json")["raw"]["model.sxo"]["sha256"])
default_settings = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
check("report_runner_session_queue_gui_guards", all(
      all(token in (CASE / name).read_text(encoding="utf-8-sig") for token in
          ("$env:SSH_CONNECTION", "SessionId -ne 0", "sshd.exe",
           "Global\\SimloxIssue18NativeQueue", "13340", "source sxo changed",
           "source closure invalid", "report or GUI guard failed"))
      for name in ("report_a07_parent_ssh.ps1", "report_existing_sxo_ssh.ps1")))
for owner, selectors in (("a07", ("all", "regenerative")),
                         ("j07", ("all", "regenerative", "fixed-ok", "fixed-deny"))):
    source = A07_RUN if owner == "a07" else NATIVE
    runner = CASE / ("report_a07_parent_ssh.ps1" if owner == "a07"
                     else "report_existing_sxo_ssh.ps1")
    for selector in selectors:
        key = f"{owner}-{selector}"
        run = REPORTS / f"{key}-report-20261001-01"
        ri, rc = load(run / "invocation.json"), load(run / "closure.json")
        report_shas[key] = sha(run / "report-raw.json")
        check(f"{key}_sha_closure", ri["run_id"] == rc["run_id"] == run.name and
              rc["exit_code"] == 0 and rc["invocation_sha256"] == sha(run / "invocation.json") and
              ri["source_sxo_sha256"] == rc["source_sxo_sha256"] == sha(source / "model.sxo") and
              ri["source_closure_sha256"] == sha(source / "closure.json") and
              ri["settings_sha256"] == rc["settings_sha256"] ==
              sha(REPORTS / settings[selector]) and
              ri["runner_sha256"] == rc["runner_sha256"] == sha(runner) and
              len(rc["raw"]) == 2 and all((run / name).stat().st_size == meta["bytes"] and
              sha(run / name) == meta["sha256"] for name, meta in rc["raw"].items()))
        check(f"{key}_ssh_gui_report", ri["selector"] == selector and
              ri["gui_pid"] == 13340 and ri["gui_session"] > 0 and
              "sshd.exe" in ri["ssh_ancestors"] and
              ri["installed_default_sha256"] == sha(default_settings) and
              all(flag in ri["command"] for flag in ("-report", "-rpts", "-rjexport")) and
              "Report completed" in (run / "report-export.log").read_text(
                  encoding="utf-8-sig", errors="replace"))
        report_data[key] = results(native(run / "report-raw.json"))

all_child = report_data["j07-all"]
check("report_settings_preserve_global_ledgers", all(
      report_data[f"j07-{selector}"]["ResultSummary"] == default["ResultSummary"] and
      report_data[f"j07-{selector}"]["SystemResults"] == system and
      report_data[f"j07-{selector}"]["StockTotalResults"] == stock
      for selector in settings))


def one(table: str, selector: str) -> dict | None:
    rows = report_data[selector].get(table, [])
    return rows[0] if len(rows) == 1 else None


fixed = one("FixedMissionResultsTotal", "j07-all")
regen = one("RegenMissionResultsTotal", "j07-all")
check("all_fixed_count_and_time", fixed is not None and
      all(close(fixed[field], value) for field, value in
          (("NMREQ", 2), ("NMSTA", 1), ("NMSUC", 1),
           ("MTREQ", 8), ("MTACC", 4), ("STREQ", 16), ("STACC", 4))))
check("each_fixed_branch", all(
      one("FixedMissionResultsTotal", f"j07-fixed-{suffix}") is not None and
      all(close(one("FixedMissionResultsTotal", f"j07-fixed-{suffix}")[field], value)
          for field, value in expected.items())
      for suffix, expected in (("ok", {"NMREQ": 1, "NMSTA": 1, "NMSUC": 1,
                                      "STREQ": 4, "STACC": 4}),
                               ("deny", {"NMREQ": 1, "NMSTA": 0, "NMSUC": 0,
                                         "STREQ": 12, "STACC": 0}))))
check("fixed_period_rows", [(r["STIM"], r["NMREQ"], r["NMSTA"], r["NMSUC"])
      for r in all_child["FixedMissionResults"]] == [(20, 1, 1, 1), (28, 1, 0, 0)])
check("regenerative_total_counts_and_null_request", regen is not None and
      regen["NMREQ"] is None and all(close(regen[field], value) for field, value in
      (("NMSTA", 4), ("NMSUC", 4), ("MTREQ", 8), ("MTACC", 8),
       ("STREQ", 12), ("STACC", 14), ("STF", 14/12))))
check("regenerative_selectors_match_A07", all(
      close(one("RegenMissionResultsTotal", key)[field], value) for key in
      ("j07-regenerative", "a07-all", "a07-regenerative") for field, value in
      (("NMSTA", 4), ("NMSUC", 4), ("MTREQ", 8), ("MTACC", 8),
       ("STREQ", 12), ("STACC", 14))) and
      all(one("RegenMissionResultsTotal", key)["NMREQ"] is None for key in
          ("j07-regenerative", "a07-all", "a07-regenerative")))
check("A07_fixed_factors_zero", all(close(report_data[key]["ResultSummary"][0][f], 0)
      for key in ("a07-all", "a07-regenerative") for f in ("MSTF", "MSUF")))
check("mixed_time_rates_and_factors", one("MissionResultsTotal", "j07-all") is not None and
      all(close(one("MissionResultsTotal", "j07-all")[field], value) for field, value in
      (("MTREQ", 16/36), ("MTACC", 12/36), ("MTF", .75),
       ("STREQ", 28/36), ("STACC", 18/36), ("STF", 18/28))))
check("selection_exclusivity", "RegenMissionResultsTotal" not in report_data["j07-fixed-ok"] and
      "RegenMissionResultsTotal" not in report_data["j07-fixed-deny"] and
      "FixedMissionResultsTotal" not in report_data["j07-regenerative"] and
      "FixedMissionResultsTotal" not in report_data["a07-all"])
check("fixed_denominator_not_five_sixths", close(summary["MSTF"], 1/2) and
      close(summary["MSUF"], 1/2) and not close(summary["MSTF"], 5/6) and
      fixed["NMSTA"] / fixed["NMREQ"] == fixed["NMSUC"] / fixed["NMREQ"] == .5)

passed = sum(c["pass"] for c in CHECKS)
result = {
    "schema": "simlox-j07-mixed-fixed-regenerative-independent-readonly/v1",
    "case_id": "J07", "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go_fixed_count_denominator" if passed == len(CHECKS) else "no_go_evidence_mismatch",
    "passed": passed, "total": len(CHECKS), "checks": CHECKS,
    "source_sha256": {"contract": sha(CASE / "contract.json"),
                      "parent_input": sha(A07 / "native-input.json"),
                      "child_input": sha(CASE / "native-input.json")},
    "native_sha256": {"closure": sha(NATIVE / "closure.json"),
                      "model_log": sha(NATIVE / "model.log"),
                      "report": sha(NATIVE / "report-raw.json")},
    "report_sha256": report_shas,
    "finding": "Four regenerative children succeeded, one fixed mission succeeded, and one fixed demand was cancelled before launch. Fixed totals give 2 requests, 1 start and 1 success, matching global MSTF=MSUF=0.5; regenerative total has 4 starts/successes and null NMREQ. Mixed mission time factor is 12/16=0.75 and system time factor is 18/28. The 72 system bins integrate 18 operating aircraft-hours and both aircraft are terminal ready.",
    "limitations": [
        "A single seed and one regenerative period with no failures support only this mixed fixed-demand denominator observation.",
        "The regenerative NMREQ field is null in the total row; its four child successes are not evidence of four fixed requests.",
        "MissionResultsTotal time fields are per-hour rates over 36 hours; count and hour numerators come from FixedMissionResultsTotal and RegenMissionResultsTotal.",
        "The final regenerative child has truncated on-station service at the period boundary; the 14 aircraft-hours follow observed start/end events.",
        "Native JSON trailing commas are normalized only in memory; SHA-256 seals bind original bytes.",
        "Other J07 variants, stochastic replication, GUI display and cross-engine behavior remain outside this review.",
    ],
}
OUTPUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{passed}/{len(CHECKS)} {result['decision']}")
for item in CHECKS:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if passed == len(CHECKS) else 1)
