"""Independent standard-library replay of sealed J07.var04 native evidence.

Reads only frozen source and raw run files. Does not import author code or
launch SIMLOX. Writes a deterministic result beside this script.
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
RUNS = {
    "control": CASE / "runs" / "j07-full-success-control-v100-20261001-01",
    "child": CASE / "runs" / "j07-early-success-v100-20261001-01",
}
SOURCES = {
    "control": CASE / "full-completion-control-input.json",
    "child": CASE / "early-success-point-input.json",
}
SOURCE_SHA = {
    "control": "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78",
    "child": "8117e6f073104b61fe59a52790d22bcf05b85132e75f1bc5d260652dcf67c1be",
}
checks: list[dict] = []


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test(label: str, condition: bool, detail: object = None) -> None:
    checks.append({"name": label, "pass": bool(condition), "detail": detail})


def ordinary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def simlox_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quote = slash = False
    for i, char in enumerate(text):
        if quote:
            out.append(char)
            if slash:
                slash = False
            elif char == "\\":
                slash = True
            elif char == '"':
                quote = False
        elif char == '"':
            quote = True
            out.append(char)
        elif char == "," and text[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def source_tables(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        assert table["name"] not in result
        result[table["name"]] = table
    return result


def populated(doc: dict) -> dict:
    result = {}
    for name, table in source_tables(doc).items():
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            assert all(len(row) == len(table["columns"]) for row in rows)
            result[name] = ([c["name"] for c in table["columns"]], rows)
    return result


def report_tables(doc: dict) -> dict:
    result = {}
    for table in doc["report"]["tables"]:
        assert table["name"] not in result
        columns = [c["name"] for c in table["columns"]]
        result[table["name"]] = [dict(zip(columns, row)) for ins in table["instances"] for row in ins["rows"]]
    return result


def near(a: object, b: float) -> bool:
    return a is not None and math.isclose(float(a), b, abs_tol=1e-6, rel_tol=0)


contract = ordinary(CASE / "contract.json")
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
test("manual_dictionary_hashes", digest(manual) == contract["source_manual_sha256"] and
     digest(dictionary) == contract["source_dictionary_sha256"])
test("accepted_D06_parent", digest(SOURCES["control"]) ==
     digest(ROOT / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json") == SOURCE_SHA["control"])
source = {k: simlox_json(path) for k, path in SOURCES.items()}
tables = {k: source_tables(doc) for k, doc in source.items()}
business = {k: populated(doc) for k, doc in source.items()}
for k in RUNS:
    key = "full-completion-control" if k == "control" else "early-success-point"
    test(f"{k}_frozen_input", digest(SOURCES[k]) == SOURCE_SHA[k] == contract["input_sha256"][key])
    test(f"{k}_table_count", len(tables[k]) == 35 and len(business[k]) == 18)
change = {name for name in tables["control"] if tables["control"][name] != tables["child"][name]}
test("two_changed_tables_only", set(tables["control"]) == set(tables["child"]) and
     change == {"ProblemDescription", "MissionType"})
diff = ordinary(CASE / "exact-diff.json")
test("documented_diff", set(diff["changed_tables"]) == change and
     diff["parent_input_sha256"] == SOURCE_SHA["control"] and
     diff["child_input_sha256"] == SOURCE_SHA["child"] and
     all(diff["tables"][name]["before"] == tables["control"][name]["instances"][0]["rows"] and
         diff["tables"][name]["after"] == tables["child"][name]["instances"][0]["rows"] for name in change))
old_mission = business["control"]["MissionType"][1][0]
new_mission = business["child"]["MissionType"][1][0]
test("MSUCPT_only_business_change", old_mission[7] == 1 and new_mission[7] == .75 and
     new_mission == [*old_mission[:7], .75, *old_mission[8:]])
test("schedule_unchanged", business["control"]["OperationProfile"] ==
     business["child"]["OperationProfile"] and
     [r[2] for r in business["child"]["OperationProfile"][1]] == [8, 20, 32])

logs: dict[str, list[str]] = {}
reports: dict[str, dict] = {}
gui: set[tuple] = set()
evidence: dict[str, dict] = {}
for k, run in RUNS.items():
    invocation, closure, steps = [ordinary(run / n) for n in ("invocation.json", "closure.json", "steps.json")]
    gui.add((invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"]))
    evidence[k] = {"closure_sha256": digest(run / "closure.json"),
                   "raw_sha256": {n: m["sha256"] for n, m in closure["raw"].items()}}
    test(f"{k}_identity", closure["run_id"] == invocation["run_id"] == run.name and
         closure["error"] is None and invocation["input_sha256"] == SOURCE_SHA[k])
    test(f"{k}_raw_seals", closure["invocation_sha256"] == digest(run / "invocation.json") and
         len(closure["raw"]) == 12 and all((run / n).is_file() and (run / n).stat().st_size == m["bytes"] and
         digest(run / n) == m["sha256"] for n, m in closure["raw"].items()))
    seal = closure["source_hashes_before"]
    test(f"{k}_source_seals", seal == closure["source_hashes_after"] and
         seal["input"] == SOURCE_SHA[k] == digest(run / "input.json") and
         seal["parent"] == SOURCE_SHA["control"] and
         seal["contract"] == digest(CASE / "contract.json") and
         seal["builder"] == digest(CASE / "build.py") and
         seal["checker"] == digest(CASE / "check_roundtrip.py") and
         seal["runner_script"] == digest(CASE / "run_native_ssh.ps1"))
    test(f"{k}_guard", invocation["execution_mode"] == "ssh_cli_v1" and
         invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
         "sshd.exe" in invocation["ssh_ancestor_names"] and
         invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
         invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0)
    test(f"{k}_five_steps", [s["name"] for s in steps] ==
         ["import", "export", "calc", "jsonreport", "check_import_export"] and
         all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    exported = populated(simlox_json(run / "roundtrip-raw.json"))
    test(f"{k}_source_roundtrip", all(exported.get(name) == value for name, value in business[k].items()))
    test(f"{k}_import_export_markers", "Import completed!" in
         (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
         "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    test(f"{k}_conversion", "Errors: 0, Warnings: 1, Notes: 0" in conversion and
         "warning #108" in conversion and "Saving results" in conversion)
    logs[k] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    reports[k] = report_tables(simlox_json(run / "report-raw.json"))
    test(f"{k}_report_shape", set(reports[k]) ==
         {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    system, stock = reports[k]["SystemResults"], reports[k]["StockTotalResults"]
    test(f"{k}_72_bins", len(system) == len(stock) == 72 and all(
         r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 for series in (system, stock) for i, r in enumerate(series)))
    test(f"{k}_stock_ledger", all(r["PNB"] == 1 and all(value in (0, None) for name, value in r.items()
         if name not in ("STINT", "ETINT", "PNB")) for r in stock))
    last = system[-1]
    test(f"{k}_terminal", near(last["NSYRY"], 1) and all(near(last[name], 0) for name in
         ("NSYMA", "NSYMO", "NSYRP", "NFAIL", "NSYWR", "NSYWI")) and
         any("Time: 34.5 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in x for x in logs[k]))

test("same_gui_identity", len(gui) == 1)
test("complete_system_stock_equality", reports["control"]["SystemResults"] ==
     reports["child"]["SystemResults"] and reports["control"]["StockTotalResults"] ==
     reports["child"]["StockTotalResults"])
summary_control, summary_child = [reports[k]["ResultSummary"][0] for k in ("control", "child")]
test("summary_only_MSUF_differs", len(reports["control"]["ResultSummary"]) ==
     len(reports["child"]["ResultSummary"]) == 1 and
     {name for name in summary_control if summary_control[name] != summary_child[name]} == {"MSUF"} and
     near(summary_control["MSUF"], 1/3) and near(summary_child["MSUF"], 1) and
     all(summary_child[name] == expected for name, expected in
         {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "MSTF": 1, "STMF": 1}.items()))

control, child = ["\n".join(logs[k]) for k in ("control", "child")]
def without_success_markers(lines: list[str]) -> list[str]:
    return [line.replace(", mission success,", ",") for line in lines if not re.search(
        r"^Time: [\d.]+ <BASIC-MISSION[^\n]*> mission success:", line)]
test("other_events_byte_equivalent", without_success_markers(logs["control"]) ==
     without_success_markers(logs["child"]))
for label, moment, mission_id in (("first", 8, 0), ("middle", 20, 1), ("third", 32, 2)):
    marker = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission_id}>"
    test(f"{label}_start_same_aircraft", all(f"Time: {moment} {marker} mission starting, duration: 2 : <TEACH-AIR-01,0>" in s
         for s in (control, child)))
for label, failure, threshold, finish, mission_id in (("first", 9.8829, 9.5, 10, 0),
                                                        ("third", 33.8602, 33.5, 34, 2)):
    marker = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission_id}>"
    test(f"{label}_threshold_before_failure", threshold < failure < finish and
         all(f"Time: {failure} <TEACH-AIR-01,0> critical CM failure mode added" in s and
             f"Time: {failure} {marker} mission aborted:" in s and
             f"Time: {finish} {marker} aborted mission completed:" in s for s in (control, child)))
    test(f"{label}_completion_success_marker_only_child", f"Time: {finish} {marker} mission success:" not in control and
         f"Time: {finish} {marker} mission success:" in child and
         f"Time: {threshold} {marker} mission success:" not in child)
    repair_end = 10.5 if label == "first" else 34.5
    test(f"{label}_same_repair", all(f"Time: {finish}  system CM task {0 if label == 'first' else 1} on <TEACH-AIR-01,0> started" in s and
         f"Time: {repair_end}  system CM task {0 if label == 'first' else 1} on <TEACH-AIR-01,0> completed" in s
         for s in (control, child)))
test("middle_mission_success_both", all(
     "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:" in s and
     "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed:" in s for s in (control, child)))
test("exact_failure_and_abort_counts", all(s.count("critical CM failure mode added") == 2 and
     s.count("mission aborted:") == 2 and s.count("aborted mission completed:") == 2 for s in (control, child)))

result = {
    "schema": "simlox-j07-success-point-independent-readonly/v1", "case_id": "J07", "variant_id": "J07.var04",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go" if all(c["pass"] for c in checks) else "no_go",
    "passed": sum(c["pass"] for c in checks), "total": len(checks), "checks": checks,
    "raw": evidence,
    "finding": "For this fixed-seed D06 case, lowering MSUCPT from 1 to 0.75 changes only MSUF from about 1/3 to 1; two aborted missions acquire mission-success log markers at their hour-10/34 completion. No success marker occurs at the 9.5/33.5 thresholds themselves.",
    "limits": [
        "Classification is retrospective in this observed trace; a threshold-time success event is not established.",
        "The two failure times are stochastic fixed-seed observations, not guaranteed onset times.",
        "One aircraft, three scheduled missions, two failures, and one success-point change; no generic partial-success policy is inferred.",
        "Native JSON trailing commas are removed only in a parser copy; hashes bind untouched raw bytes.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['passed']}/{result['total']} {result['decision']}")
for item in checks:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if result["decision"] == "bounded_go" else 1)
