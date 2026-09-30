"""Independent read-only replay of the bounded J07.var05 unit/type slice.

This standard-library script reads frozen source and sealed native/report-only
files. It imports no author module, invokes no native process, and writes only
its deterministic review JSON beside this script.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
A17 = ROOT / "A17-multi-unit-group-v1.0.0"
NATIVE = CASE / "runs" / "j07-unit-type-v100-20261001-01"
A17_RUN = A17 / "runs" / "a17-v100-ssh-20260929-01"
REPORT_DIR = CASE / "runs" / "report-settings"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
MISSION_TABLES = {"MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal"}
checks: list[dict] = []


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, ok: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(ok), "detail": detail})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(raw):
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
        elif char == "," and raw[index + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def source_tables(document: dict) -> dict:
    result = {}
    for table in document["model"]["tables"]:
        assert table["name"] not in result
        result[table["name"]] = table
    return result


def business(document: dict) -> dict:
    output = {}
    for name, table in source_tables(document).items():
        rows = [r for instance in table["instances"] for r in instance["rows"]]
        if rows:
            assert all(len(row) == len(table["columns"]) for row in rows)
            output[name] = ([c["name"] for c in table["columns"]], rows)
    return output


def result_tables(document: dict) -> dict:
    output = {}
    for table in document["report"]["tables"]:
        assert table["name"] not in output
        cols = [c["name"] for c in table["columns"]]
        output[table["name"]] = [dict(zip(cols, r)) for ins in table["instances"] for r in ins["rows"]]
    return output


def near(value: object, target: float) -> bool:
    return value is not None and math.isclose(float(value), target, rel_tol=0, abs_tol=1e-6)


contract = load(CASE / "contract.json")
check("new_bounded_contract", contract["schema"] == "simlox-j07-unit-type-report-contract/v1" and
      contract["publication_state"] == "not_published" and
      "group aggregation of member-unit missions is not established" in contract["limitations"][0] and
      "failed independent review" in contract["prior_diagnostic"])
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
check("pinned_manual_dictionary", digest(manual) == contract["source_manual_sha256"] and
      digest(dictionary) == contract["source_dictionary_sha256"])
check("accepted_A17_parent", digest(A17 / "native-input.json") == contract["parent_input_sha256"] and
      digest(CASE / "native-input.json") == contract["input_sha256"])
parent = native_json(A17 / "native-input.json")
child = native_json(CASE / "native-input.json")
parent_tables, child_tables = source_tables(parent), source_tables(child)
changed = {name for name in parent_tables if parent_tables[name] != child_tables[name]}
diff = load(CASE / "exact-diff.json")
check("four_table_delta", len(parent_tables) == len(child_tables) == 33 and
      set(parent_tables) == set(child_tables) and
      changed == set(diff["changed_tables"]) ==
      {"ProblemDescription", "MissionType", "OperationProfile", "Operations"} and
      all(diff["changed_tables"][name]["before"] == parent_tables[name]["instances"][0]["rows"] and
          diff["changed_tables"][name]["after"] == child_tables[name]["instances"][0]["rows"] for name in changed))
check("15_business_tables", len(business(parent)) == len(business(child)) == 15)
check("unit_ownership", business(parent)["Operations"][1] == [["TEACH-GROUP", "BASIC-SCHEDULE", None]] and
      business(child)["Operations"][1] == [["TEACH-UNIT", "SCHEDULE-A", None],
                                          ["TEACH-UNIT-2", "SCHEDULE-B", None]])
check("two_one_aircraft_types", [r[0] for r in business(child)["MissionType"][1]] ==
      ["MISSION-A", "MISSION-B"] and all(r[2:4] == [1, 1] and r[5] == 2 for r in business(child)["MissionType"][1]))
check("concurrent_schedules", [r[:4] for r in business(child)["OperationProfile"][1]] ==
      [["SCHEDULE-A", "MISSION-A", 8, "SCHEDULED"],
       ["SCHEDULE-B", "MISSION-B", 8, "SCHEDULED"]])

invocation, closure, steps = [load(NATIVE / n) for n in ("invocation.json", "closure.json", "steps.json")]
check("native_identity", invocation["run_id"] == closure["run_id"] == NATIVE.name and
      closure["error"] is None and invocation["input_sha256"] == contract["input_sha256"])
check("native_raw_seals", closure["invocation_sha256"] == digest(NATIVE / "invocation.json") and
      len(closure["raw"]) == 12 and all((NATIVE / n).is_file() and
      (NATIVE / n).stat().st_size == meta["bytes"] and digest(NATIVE / n) == meta["sha256"]
      for n, meta in closure["raw"].items()))
before = closure["source_hashes_before"]
check("native_source_seals", before == closure["source_hashes_after"] and
      before["input"] == digest(CASE / "native-input.json") and
      before["parent"] == digest(A17 / "native-input.json") and
      before["contract"] == digest(CASE / "contract.json") and
      before["builder"] == digest(CASE / "build.py") and
      before["checker"] == digest(CASE / "check_roundtrip.py") and
      before["runner_script"] == digest(CASE / "run_native_ssh.ps1"))
check("contract_frozen_for_fresh_run", before["contract"] == digest(CASE / "contract.json") and
      before["contract"] == closure["source_hashes_after"]["contract"] and
      invocation["run_id"] == "j07-unit-type-v100-20261001-01")
check("native_guard", invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
      "sshd.exe" in invocation["ssh_ancestor_names"] and
      invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
      invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0)
check("native_five_steps", [s["name"] for s in steps] ==
      ["import", "export", "calc", "jsonreport", "check_import_export"] and
      all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
exported = business(native_json(NATIVE / "roundtrip-raw.json"))
check("native_roundtrip", all(exported.get(name) == value for name, value in business(child).items()))
runlog = (NATIVE / "run.log").read_text(encoding="utf-8-sig", errors="replace")
check("native_conversion", "Errors: 0, Warnings: 2, Notes: 0" in runlog and
      "warning #108" in runlog and "warning #126" in runlog and "Saving results" in runlog)
event = (NATIVE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
for label, unit, mission, aircraft, ident in (("a", "TEACH-UNIT", "MISSION-A", 0, 0),
                                               ("b", "TEACH-UNIT-2", "MISSION-B", 1, 1)):
    marker = f"<{mission},{unit},0,0,{ident}>"
    check(f"{label}_event_chain", f"Time: 7 <{unit}> mission ordered: {mission}" in event and
          f"Time: 7 {marker} mission allocates system: <TEACH-AIR-01,{aircraft}>" in event and
          f"Time: 8 {marker} mission starting, duration: 2 : <TEACH-AIR-01,{aircraft}>" in event and
          f"Time: 10 {marker} mission success:" in event and
          f"Time: 10 {marker} mission completed: <TEACH-AIR-01,{aircraft}>" in event)
check("two_waves_no_fault", event.count("mission starting, duration: 2") == 2 and
      event.count("mission ordered:") == 2 and event.count("mission success:") == 2 and
      event.count("mission completed:") == 2 and "mission aborted:" not in event and
      "mission cancelled:" not in event and "critical CM failure" not in event)
default = result_tables(native_json(NATIVE / "report-raw.json"))
system, stock = default["SystemResults"], default["StockTotalResults"]
check("native_summary", len(default["ResultSummary"]) == 1 and
      all(near(default["ResultSummary"][0][field], expected) for field, expected in
          (("NREP", 1), ("RTILW", 0), ("RTIUP", 36), ("MTMF", 1),
           ("MSTF", 1), ("MSUF", 1), ("STMF", 1))))
check("native_default_72_bins", len(system) == len(stock) == 72 and all(
      r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for series in (system, stock) for i, r in enumerate(series)))
check("native_system_occupancy", all(r["NSYRY"] == (2 if i < 14 or i >= 20 else 0) and
      r["NSYMA"] == (2 if 14 <= i < 20 else 0) and
      r["NSYMO"] == (2 if 16 <= i < 20 else 0) and
      r["STACC"] == (2 if 16 <= i < 20 else 0) for i, r in enumerate(system)))
check("native_stock_terminal", all(r["PNB"] == 1 and all(x in (0, None) for key, x in r.items()
      if key not in ("STINT", "ETINT", "PNB")) for r in stock) and
      system[-1]["NSYRY"] == 2 and system[-1]["NSYMA"] == system[-1]["NSYMO"] == 0)

settings_map = {
    "all": "all.sxs", "group": "group.sxs", "unit-a": "unit-a.sxs", "unit-b": "unit-b.sxs",
    "type-a": "type-a.sxs", "type-b": "type-b.sxs",
    "group-type-a": "group-type-a.sxs", "group-type-b": "group-type-b.sxs",
}
report_results: dict[str, dict] = {}
report_hashes: dict[str, str] = {}
parent_closure = A17_RUN / "closure.json"
check("A17_parent_run_sealed", digest(A17_RUN / "model.sxo") ==
      load(parent_closure)["raw"]["model.sxo"]["sha256"])
for owner in ("a17", "j07"):
    selectors = ("all", "group", "unit-a", "unit-b") if owner == "a17" else tuple(settings_map)
    source_run = A17_RUN if owner == "a17" else NATIVE
    runner = CASE / ("report_group_parent_ssh.ps1" if owner == "a17" else "report_existing_sxo_ssh.ps1")
    for selector in selectors:
        key = f"{owner}-{selector}"
        run = REPORT_DIR / f"{key}-report-20261001-01"
        inv, seal = load(run / "invocation.json"), load(run / "closure.json")
        report_hashes[key] = digest(run / "report-raw.json")
        check(f"{key}_report_seals", inv["run_id"] == seal["run_id"] == run.name and
              seal["exit_code"] == 0 and seal["invocation_sha256"] == digest(run / "invocation.json") and
              seal["source_sxo_sha256"] == inv["source_sxo_sha256"] == digest(source_run / "model.sxo") and
              inv["source_closure_sha256"] == digest(source_run / "closure.json") and
              seal["settings_sha256"] == inv["settings_sha256"] == digest(REPORT_DIR / settings_map[selector]) and
              seal["runner_sha256"] == inv["runner_sha256"] == digest(runner) and
              all((run / n).stat().st_size == m["bytes"] and digest(run / n) == m["sha256"]
                  for n, m in seal["raw"].items()))
        check(f"{key}_report_guard", inv["selector"] == selector and inv["gui_pid"] == 13340 and
              inv["gui_session"] == 1 and "sshd.exe" in inv["ssh_ancestors"] and
              "-report" in inv["command"] and "-rpts" in inv["command"] and
              "-rjexport" in inv["command"] and len(seal["raw"]) == 2 and
              inv["installed_default_sha256"] == digest(Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")))
        log = (run / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
        check(f"{key}_report_completed", "Report completed" in log and "Export completed!" in log)
        report_results[key] = result_tables(native_json(run / "report-raw.json"))

def fixed(key: str) -> dict | None:
    rows = report_results[key].get("FixedMissionResultsTotal", [])
    return rows[0] if len(rows) == 1 else None


for key, waves, mission_hours, aircraft_hours in (("j07-all", 2, 4, 4),
                                                   ("j07-unit-a", 1, 2, 2),
                                                   ("j07-unit-b", 1, 2, 2),
                                                   ("j07-type-a", 1, 2, 2),
                                                   ("j07-type-b", 1, 2, 2)):
    row = fixed(key)
    check(f"{key}_fixed_totals", row is not None and
          all(near(row[field], expected) for field, expected in
              (("NMREQ", waves), ("NMSTA", waves), ("NMSUC", waves),
               ("MTREQ", mission_hours), ("MTACC", mission_hours),
               ("STREQ", aircraft_hours), ("STACC", aircraft_hours), ("STF", 1))))
    check(f"{key}_mission_bins", len(report_results[key].get("MissionResults", [])) == 72 and
          len(report_results[key].get("FixedMissionResults", [])) == 1)
check("type_identity", fixed("j07-type-a")["MTID"] == "MISSION-A" and
      fixed("j07-type-b")["MTID"] == "MISSION-B")
check("member_identity", fixed("j07-unit-a")["UNID"] == "TEACH-UNIT" and
      fixed("j07-unit-b")["UNID"] == "TEACH-UNIT-2")
check("all_equals_unit_and_type_sums", all(near(fixed("j07-all")[field],
      fixed("j07-unit-a")[field] + fixed("j07-unit-b")[field]) and
      near(fixed("j07-all")[field], fixed("j07-type-a")[field] + fixed("j07-type-b")[field])
      for field in ("NMREQ", "NMSTA", "NMSUC", "MTREQ", "MTACC", "STREQ", "STACC")))
check("child_report_selectors_preserve_global_ledgers", all(
      len(report_results[f"j07-{selector}"]["SystemResults"]) == 72 and
      len(report_results[f"j07-{selector}"]["StockTotalResults"]) == 72 and
      report_results[f"j07-{selector}"]["SystemResults"] == system and
      report_results[f"j07-{selector}"]["StockTotalResults"] == stock and
      report_results[f"j07-{selector}"]["ResultSummary"] == default["ResultSummary"]
      for selector in settings_map))
check("A17_group_owned_positive_control", fixed("a17-all") is not None and
      fixed("a17-group") is not None and
      all(near(fixed("a17-group")[field], expected) for field, expected in
          (("NMREQ", 1), ("NMSTA", 1), ("NMSUC", 1),
           ("MTREQ", 2), ("MTACC", 2), ("STREQ", 4), ("STACC", 4))) and
      all(near(fixed("a17-group")[field], fixed("a17-all")[field]) for field in
          ("NMREQ", "NMSTA", "NMSUC", "MTREQ", "MTACC", "STREQ", "STACC")) and
      fixed("a17-group")["UNID"] == "TEACH-GROUP" and
      all(not (MISSION_TABLES & set(report_results[f"a17-{unit}"])) for unit in ("unit-a", "unit-b")))
for selector in ("group", "group-type-a", "group-type-b"):
    check(f"child_{selector}_empty_mission_selection", not
          (MISSION_TABLES & set(report_results[f"j07-{selector}"])) and
          "SystemResults" in report_results[f"j07-{selector}"] and
          "StockTotalResults" in report_results[f"j07-{selector}"])

result = {
    "schema": "simlox-j07-unit-type-independent-readonly/v1", "case_id": "J07", "variant_id": "J07.var05",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go_unit_type_reporting" if all(c["pass"] for c in checks) else "evidence_replay_failure",
    "passed": sum(c["pass"] for c in checks), "total": len(checks), "checks": checks,
    "native_closure_sha256": digest(NATIVE / "closure.json"), "report_sha256": report_hashes,
    "finding": "Fresh child all-unit, member-unit and mission-type fixed totals reconcile 2=1+1 waves, 4=2+2 mission-hours and 4=2+2 aircraft-hours. Child group and group+type selectors export no mission-result tables. The same settings on the accepted A17 group-owned parent export a one-wave group total. This meets the new pre-run unit/type contract, which explicitly excludes group rollup.",
    "scope_recommendation": "Accept only the sealed unit/type reporting slice as bounded CLI evidence. Preserve the earlier group-aggregation NO-GO; do not mark full J07.var05 group aggregation accepted.",
    "limitations": [
        "Empty child group selection is observed for unit-owned fixed missions under these report settings; it is not proof of a universal lack of group aggregation. The prior J07.var05 group-rollup contract remains NO-GO.",
        "MissionResultsTotal MTREQ/STREQ are normalized rates over 36h; aircraft-hour counts here use FixedMissionResultsTotal.",
        "One seed, two concurrent two-hour missions, no failure or support-resource competition.",
        "Native JSON trailing commas are removed only in a parser copy; raw closure hashes bind original bytes.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['passed']}/{result['total']} {result['decision']}")
for item in checks:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if all(c["pass"] for c in checks) else 1)
