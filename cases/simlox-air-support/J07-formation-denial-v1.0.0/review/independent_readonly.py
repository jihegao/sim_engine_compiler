"""Independent raw replay for the bounded J07 formation and denied demand case.

Only standard-library reads of sealed native files are used. No author module
is imported, no SIMLOX process is invoked, and only the adjacent report is made.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
VARIANTS = ("single-control", "formation-control", "denied-demand")
SOURCE_SHA = {
    "single-control": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
    "formation-control": "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4",
    "denied-demand": "09bc55982f4623549880899687b79a17816a858e1a92663fa9cb2cf07420fbba",
}
RUNS = {v: CASE / "runs" / f"j07-{v}-v100-20261001-01" for v in VARIANTS}
checks: list[dict] = []


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, okay: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(okay), "detail": detail})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    """Remove native writer trailing commas outside quoted strings for parsing."""
    raw = path.read_text(encoding="utf-8-sig")
    result: list[str] = []
    quoted = escaped = False
    for i, ch in enumerate(raw):
        if quoted:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            result.append(ch)
        elif ch == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            result.append(ch)
    return json.loads("".join(result))


def model_tables(doc: dict) -> dict:
    output = {}
    for t in doc["model"]["tables"]:
        assert t["name"] not in output
        output[t["name"]] = t
    return output


def business(doc: dict) -> dict:
    output = {}
    for name, table in model_tables(doc).items():
        rows = [r for instance in table["instances"] for r in instance["rows"]]
        if rows:
            assert all(len(r) == len(table["columns"]) for r in rows)
            output[name] = ([c["name"] for c in table["columns"]], rows)
    return output


def report_tables(doc: dict) -> dict:
    output = {}
    for table in doc["report"]["tables"]:
        assert table["name"] not in output
        cols = [c["name"] for c in table["columns"]]
        output[table["name"]] = [dict(zip(cols, r)) for i in table["instances"] for r in i["rows"]]
    return output


def almost(x: object, target: float) -> bool:
    return x is not None and math.isclose(float(x), target, rel_tol=0, abs_tol=1e-6)


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


contract = load(CASE / "contract.json")
publication = load(ROOT / "publication-index-v1.json")
published_ids = {entry["publication_id"] for entry in publication["entries"]}
check("published_prerequisites", set(contract["parent_publication_ids"]) ==
      {"A01.normal.1.0.0", "A03.formation.1.0.1",
       "J05.var05.collection_end_vs_simulation_period.1.0.0"} and
      set(contract["parent_publication_ids"]).issubset(published_ids))
src = {v: native(CASE / f"{v}-input.json") for v in VARIANTS}
tables = {v: model_tables(src[v]) for v in VARIANTS}
rows = {v: business(src[v]) for v in VARIANTS}
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
check("manual_dictionary_fingerprints", digest(manual) == contract["source_manual_sha256"] and
      digest(dictionary) == contract["source_dictionary_sha256"])
check("accepted_A01_input", digest(CASE / "single-control-input.json") ==
      digest(ROOT / "A01-single-aircraft-single-mission" / "native-input.json") == SOURCE_SHA["single-control"])
check("accepted_A03_input", digest(CASE / "formation-control-input.json") ==
      digest(ROOT / "A03-two-aircraft-formation-v1.0.1" / "native-input.json") == SOURCE_SHA["formation-control"])
for v in VARIANTS:
    check(f"{v}_frozen_source", digest(CASE / f"{v}-input.json") == SOURCE_SHA[v] ==
          contract["input_sha256"][v])
    check(f"{v}_source_tables", len(tables[v]) == 31 and len(rows[v]) == 13)
changed = {name for name in tables["formation-control"] if
           tables["formation-control"][name] != tables["denied-demand"][name]}
check("exact_full_child_delta", set(tables["formation-control"]) == set(tables["denied-demand"]) and
      changed == {"ProblemDescription", "MissionType", "OperationProfile"})
diff = load(CASE / "exact-diff.json")
check("documented_diff_matches_rows", set(diff["changed_tables"]) == changed and
      diff["parent_input_sha256"] == SOURCE_SHA["formation-control"] and
      diff["child_input_sha256"] == SOURCE_SHA["denied-demand"] and
      all(diff["tables"][name]["before"] == tables["formation-control"][name]["instances"][0]["rows"] and
          diff["tables"][name]["after"] == tables["denied-demand"][name]["instances"][0]["rows"]
          for name in changed))
missions = rows["denied-demand"]["MissionType"][1]
schedule = rows["denied-demand"]["OperationProfile"][1]
check("three_aircraft_requirement", len(missions) == 2 and missions[1][:4] ==
      ["THREE-AIR-DEMAND", "Two-hour demand requiring three aircraft", 3, 3] and missions[1][5] == 2)
check("two_scheduled_waves", len(schedule) == 2 and schedule[0][1:5] ==
      ["BASIC-MISSION", 8, "SCHEDULED", 1] and schedule[1][1:5] ==
      ["THREE-AIR-DEMAND", 12, "SCHEDULED", 1] and
      schedule[0][8] == schedule[1][8] == 1/3)
check("deployed_quantity_stays_two", rows["denied-demand"]["SystemDeployment"][1] ==
      rows["formation-control"]["SystemDeployment"][1] ==
      [["TEACH-AIR-01", "TEACH-UNIT", 2, 1, None, None, None]])

evidence: dict[str, dict] = {}
parsed_reports: dict[str, dict] = {}
event_lines: dict[str, list[str]] = {}
gui: set[tuple] = set()
for v in VARIANTS:
    run = RUNS[v]
    invocation, closure, steps = [load(run / f) for f in ("invocation.json", "closure.json", "steps.json")]
    evidence[v] = {"closure_sha256": digest(run / "closure.json"),
                   "raw_sha256": {name: item["sha256"] for name, item in closure["raw"].items()}}
    gui.add((invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"]))
    check(f"{v}_identity", closure["run_id"] == invocation["run_id"] == run.name and
          invocation["variant"] == v and invocation["input_sha256"] == SOURCE_SHA[v] and closure["error"] is None)
    check(f"{v}_raw_sha_seals", closure["invocation_sha256"] == digest(run / "invocation.json") and
          len(closure["raw"]) == 12 and all((run / name).is_file() and
          (run / name).stat().st_size == meta["bytes"] and digest(run / name) == meta["sha256"]
          for name, meta in closure["raw"].items()))
    before = closure["source_hashes_before"]
    check(f"{v}_source_seals", before == closure["source_hashes_after"] and
          before["input"] == SOURCE_SHA[v] == digest(run / "input.json") and
          before["parent"] == SOURCE_SHA["single-control"] and
          before["formation_parent"] == SOURCE_SHA["formation-control"] and
          before["contract"] == digest(CASE / "contract.json") and
          before["builder"] == digest(CASE / "build.py") and
          before["checker"] == digest(CASE / "check_roundtrip.py") and
          before["runner_script"] == digest(CASE / "run_native_ssh.ps1"))
    check(f"{v}_session_gui_queue", invocation["execution_mode"] == "ssh_cli_v1" and
          invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and
          invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    check(f"{v}_five_steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    exported = business(native(run / "roundtrip-raw.json"))
    check(f"{v}_source_roundtrip", all(exported.get(k) == value for k, value in rows[v].items()))
    check(f"{v}_import_export_markers", "Import completed!" in
          (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
          "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{v}_zero_errors", "Errors: 0, Warnings: 2, Notes: 0" in conversion and
          "warning #108" in conversion and "warning #126" in conversion and "Saving results" in conversion)
    parsed_reports[v] = report_tables(native(run / "report-raw.json"))
    check(f"{v}_report_shape", set(parsed_reports[v]) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    event_lines[v] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    summary = parsed_reports[v]["ResultSummary"]
    assert len(summary) == 1
    target = {"single-control": (1, 1, 1, 1), "formation-control": (1, 1, 1, 1),
              "denied-demand": (.5, .5, .5, .4)}[v]
    check(f"{v}_summary", summary[0]["NREP"] == 1 and summary[0]["RTILW"] == 0 and
          summary[0]["RTIUP"] == 36 and all(almost(summary[0][key], expected) for key, expected in
          zip(("MTMF", "MSTF", "MSUF", "STMF"), target)))
    stock = parsed_reports[v]["StockTotalResults"]
    check(f"{v}_stock_72", len(stock) == 72 and all(
          r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 and r["PNB"] == 1 and
          all(value in (0, None) for key, value in r.items() if key not in ("STINT", "ETINT", "PNB"))
          for i, r in enumerate(stock)))

check("same_gui_identity", len(gui) == 1)
for v in VARIANTS:
    log = "\n".join(event_lines[v])
    aircraft = 1 if v == "single-control" else 2
    basic_id = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    check(f"{v}_first_wave", len(re.findall(r"<BASIC-MISSION[^\n]*> mission starting, duration: 2", log)) == 1 and
          f"Time: 8 {basic_id} mission starting" in log and
          f"Time: 10 {basic_id} mission success" in log and
          f"Time: 10 {basic_id} mission completed" in log and
          log.count("task starting:") == log.count("task completed:") == 1 and
          len(re.findall(r"<BASIC-MISSION[^\n]*> mission allocates system:", log)) == aircraft)
    basic_alloc = re.findall(r"<BASIC-MISSION[^\n]*> mission allocates system: <TEACH-AIR-01,(\d+)>", log)
    check(f"{v}_distinct_first_wave_aircraft", sorted(basic_alloc) == [str(i) for i in range(aircraft)])
    check(f"{v}_terminal_event", f"systems ready: {aircraft} :" in log and
          "Time: 24  Start of day no 1" in log and not re.search(r"failure occurred|mission aborted", log))
    ready = [(0, 7), (10, 36)]
    assigned = [(7, 10)]
    if v == "denied-demand":
        denied_id = "<THREE-AIR-DEMAND,TEACH-UNIT,0,0,1>"
        check("denied_order_allocation", f"Time: 11 {denied_id} mission activated, systems requested: 3" in log and
              f"Time: 11 {denied_id} mission waiting:  timeout at 12.3333" in log and
              sorted(re.findall(r"<THREE-AIR-DEMAND[^\n]*> mission allocates system: <TEACH-AIR-01,(\d+)>", log)) == ["0", "1"])
        check("denied_cancel_no_flight", f"Time: 12.3333 {denied_id} mission cancelled:" in log and
              log.count("mission cancelled:") == 1 and
              not re.search(r"<THREE-AIR-DEMAND[^\n]*> mission (starting|success|completed)", log) and
              log.count("mission starting, duration:") == 1)
        check("denied_releases_both", "Time: 12.3333 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log)
        ready = [(0, 7), (10, 11), (12 + 1/3, 36)]
        assigned = [(7, 10), (11, 12 + 1/3)]
    else:
        check(f"{v}_no_second_demand", "THREE-AIR-DEMAND" not in log and "mission cancelled:" not in log)
    system = parsed_reports[v]["SystemResults"]
    check(f"{v}_system_72_event_integrals", len(system) == 72 and all(
          r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 and
          almost(r["NSYRY"], aircraft*sum(overlap(i/2, (i+1)/2, a, b) for a, b in ready)/.5) and
          almost(r["NSYMA"], aircraft*sum(overlap(i/2, (i+1)/2, a, b) for a, b in assigned)/.5) and
          almost(r["NSYMO"], aircraft*overlap(i/2, (i+1)/2, 8, 10)/.5) and
          almost(r["STACC"], aircraft*overlap(i/2, (i+1)/2, 8, 10)/.5)
          for i, r in enumerate(system)))
    check(f"{v}_terminal_system", almost(system[-1]["NSYRY"], aircraft) and
          all(almost(system[-1][field], 0) for field in
              ("NSYMA", "NSYMO", "NFAIL", "NPMT", "NSYWR", "NSYWI")))
    check(f"{v}_aircraft_hours", almost(sum(r["NSYMO"]*.5 for r in system), 2*aircraft) and
          almost(sum(r["STACC"]*.5 for r in system), 2*aircraft))

check("first_wave_same_as_formation_control", all(
      line in event_lines["denied-demand"] for line in event_lines["formation-control"]
      if line.startswith("Time: ") and "BASIC-MISSION" in line))
first_mission_hours = 2.0
denied_mission_hours = 2.0
first_aircraft_hours = 2 * first_mission_hours
denied_requested_aircraft_hours = 3 * denied_mission_hours
check("hand_denominators", almost(first_mission_hours/(first_mission_hours+denied_mission_hours), .5) and
      almost(first_aircraft_hours/(first_aircraft_hours+denied_requested_aircraft_hours), .4) and
      almost(1/2, .5) and sum(r["NSYMO"]*.5 for r in parsed_reports["denied-demand"]["SystemResults"]) == 4)

result = {
    "schema": "simlox-j07-independent-readonly/v1", "case_id": "J07", "version": "1.0.0",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go" if all(c["pass"] for c in checks) else "no_go",
    "passed": sum(c["pass"] for c in checks), "total": len(checks), "checks": checks,
    "evidence": evidence,
    "derived_denominators": {
        "completed_mission_hours": 2, "planned_mission_hours": 4,
        "completed_aircraft_hours": 4, "planned_aircraft_hours": 10,
        "successful_waves": 1, "planned_waves": 2,
        "first_wave_sorties": 2, "denied_demand_sorties": 0,
        "MTMF": .5, "STMF": .4, "MSTF": .5, "MSUF": .5,
    },
    "limitations": [
        "Single seed, one unit, one successful formation and one cancelled fixed demand; no fault or resource competition.",
        "The denominator interpretation is established for these fixed scheduled demands and observed summary rows only.",
        "Partial successes, success-point timing, regenerative exclusions, GUI display, and cross-engine behavior remain untested.",
        "Native JSON trailing commas were removed only in a parser copy; hashes bind untouched raw bytes.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['passed']}/{result['total']} {result['decision']}")
for item in checks:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if result["decision"] == "bounded_go" else 1)
