"""Independent read-only replay of the three J07.var03 native runs.

Uses only Python's standard library and sealed inputs/raw evidence. No author
module is imported and no native program is invoked.
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
VARIANTS = ("full-control", "strict-shortage", "partial-minimum")
RUNS = {
    "full-control": CASE / "runs" / "j07-full-form-control-v100-20261001-01",
    "strict-shortage": CASE / "runs" / "j07-strict-shortage-v100-20261001-01",
    "partial-minimum": CASE / "runs" / "j07-partial-minimum-v100-20261001-01",
}
FINGERPRINT = {
    "full-control": "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4",
    "strict-shortage": "b4074a56007fc989e20025932741d3dc40d7207f23b2c6908dfd10eff98c3a03",
    "partial-minimum": "90c89f8fa4fc7202d5b461a022a7219c0eae436aa842be410018dc16c96f17f6",
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(name: str, result: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(result), "detail": detail})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_native(path: Path) -> dict:
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


def tables(document: dict) -> dict:
    result = {}
    for t in document["model"]["tables"]:
        assert t["name"] not in result
        result[t["name"]] = t
    return result


def source_rows(document: dict) -> dict:
    result = {}
    for name, table in tables(document).items():
        values = [r for instance in table["instances"] for r in instance["rows"]]
        if values:
            assert all(len(r) == len(table["columns"]) for r in values)
            result[name] = ([c["name"] for c in table["columns"]], values)
    return result


def report_rows(document: dict) -> dict:
    result = {}
    for table in document["report"]["tables"]:
        assert table["name"] not in result
        columns = [c["name"] for c in table["columns"]]
        result[table["name"]] = [dict(zip(columns, r)) for i in table["instances"] for r in i["rows"]]
    return result


def close(value: object, expected: float) -> bool:
    return value is not None and math.isclose(float(value), expected, rel_tol=0, abs_tol=1e-6)


def intersection(a: float, b: float, c: float, d: float) -> float:
    return max(0, min(b, d) - max(a, c))


contract = load(CASE / "contract.json")
publication = load(ROOT / "publication-index-v1.json")
published = {entry["publication_id"] for entry in publication["entries"]}
verify("published_lineage", set(contract["parent_publication_ids"]) ==
       {"A03.formation.1.0.1", "J05.var05.collection_end_vs_simulation_period.1.0.0",
        "J07.var02.formation_and_denied_fixed_demand.1.0.0"} and
       set(contract["parent_publication_ids"]).issubset(published))
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
verify("pinned_manual_dictionary", sha(manual) == contract["source_manual_sha256"] and
       sha(dictionary) == contract["source_dictionary_sha256"])
verify("accepted_A03_parent", sha(CASE / "full-control-input.json") ==
       sha(ROOT / "A03-two-aircraft-formation-v1.0.1" / "native-input.json") == FINGERPRINT["full-control"])
sources = {v: parse_native(CASE / f"{v}-input.json") for v in VARIANTS}
all_tables = {v: tables(sources[v]) for v in VARIANTS}
business = {v: source_rows(sources[v]) for v in VARIANTS}
for v in VARIANTS:
    verify(f"{v}_source_hash", sha(CASE / f"{v}-input.json") == FINGERPRINT[v] == contract["input_sha256"][v])
    verify(f"{v}_source_table_count", len(all_tables[v]) == 31 and len(business[v]) == 13)
exact = load(CASE / "exact-diffs.json")
verify("diff_parent", exact["parent_input_sha256"] == FINGERPRINT["full-control"])
for v, expected in (("strict-shortage", {"ProblemDescription", "SystemDeployment"}),
                    ("partial-minimum", {"ProblemDescription", "SystemDeployment", "MissionType"})):
    changed = {n for n in all_tables["full-control"] if all_tables["full-control"][n] != all_tables[v][n]}
    spec = exact["variants"][v]
    verify(f"{v}_exact_diff", set(all_tables["full-control"]) == set(all_tables[v]) and
           changed == expected == set(spec["changed_tables"]) and spec["child_input_sha256"] == FINGERPRINT[v] and
           all(spec["tables"][n]["before"] == all_tables["full-control"][n]["instances"][0]["rows"] and
               spec["tables"][n]["after"] == all_tables[v][n]["instances"][0]["rows"] for n in changed))
for v, nominal, minimum, deployed in (("full-control", 2, 2, 2),
                                      ("strict-shortage", 2, 2, 1),
                                      ("partial-minimum", 2, 1, 1)):
    mission = business[v]["MissionType"][1][0]
    deployment = business[v]["SystemDeployment"][1][0]
    verify(f"{v}_authored_capacity", (mission[2], mission[3], mission[5], deployment[2]) ==
           (nominal, minimum, 2, deployed))
    verify(f"{v}_same_schedule", business[v]["OperationProfile"] == business["full-control"]["OperationProfile"] and
           business[v]["OperationProfile"][1][0][2] == 8)

reports: dict[str, dict] = {}
logs: dict[str, str] = {}
gui: set[tuple] = set()
evidence: dict[str, dict] = {}
for v, run in RUNS.items():
    invocation, closure, steps = (load(run / n) for n in ("invocation.json", "closure.json", "steps.json"))
    evidence[v] = {"closure_sha256": sha(run / "closure.json"),
                   "raw_sha256": {n: info["sha256"] for n, info in closure["raw"].items()}}
    gui.add((invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"]))
    verify(f"{v}_run_identity", closure["run_id"] == invocation["run_id"] == run.name and
           invocation["variant"] == v and closure["error"] is None)
    verify(f"{v}_raw_seals", closure["invocation_sha256"] == sha(run / "invocation.json") and
           len(closure["raw"]) == 12 and all((run / n).is_file() and
           (run / n).stat().st_size == meta["bytes"] and sha(run / n) == meta["sha256"]
           for n, meta in closure["raw"].items()))
    before = closure["source_hashes_before"]
    verify(f"{v}_source_seals", before == closure["source_hashes_after"] and
           before["input"] == FINGERPRINT[v] == sha(run / "input.json") and
           before["parent"] == FINGERPRINT["full-control"] and
           before["contract"] == sha(CASE / "contract.json") and
           before["builder"] == sha(CASE / "build.py") and
           before["checker"] == sha(CASE / "check_roundtrip.py") and
           before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    verify(f"{v}_ssh_gui_mutex", invocation["execution_mode"] == "ssh_cli_v1" and
           invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
           "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0)
    verify(f"{v}_five_steps", [s["name"] for s in steps] ==
           ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    exported = source_rows(parse_native(run / "roundtrip-raw.json"))
    verify(f"{v}_source_roundtrip", all(exported.get(n) == value for n, value in business[v].items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    verify(f"{v}_zero_errors", "Errors: 0, Warnings: 2, Notes: 0" in conversion and
           "warning #108" in conversion and "warning #126" in conversion and "Saving results" in conversion)
    reports[v] = report_rows(parse_native(run / "report-raw.json"))
    logs[v] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    summary = reports[v]["ResultSummary"][0]
    expected = {"full-control": (1, 1, 1, 1), "strict-shortage": (0, 0, 0, 0),
                "partial-minimum": (1, 1, 1, .5)}[v]
    verify(f"{v}_summary", summary["NREP"] == 1 and summary["RTILW"] == 0 and summary["RTIUP"] == 36 and
           all(close(summary[k], target) for k, target in zip(("MTMF", "MSTF", "MSUF", "STMF"), expected)))
    stock = reports[v]["StockTotalResults"]
    verify(f"{v}_stock_72_zero_demand", len(stock) == 72 and all(
           r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 and r["PNB"] == 1 and
           all(value in (0, None) for name, value in r.items() if name not in ("STINT", "ETINT", "PNB"))
           for i, r in enumerate(stock)))

verify("same_gui_identity", len(gui) == 1)
mission_id = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
for v in VARIANTS:
    log = logs[v]
    aircraft = 2 if v == "full-control" else 1
    verify(f"{v}_one_order", log.count("<TEACH-UNIT> mission ordered: BASIC-MISSION") == 1 and
           f"Time: 7 {mission_id} mission activated, systems requested: 2" in log)
    allocated = sorted(re.findall(r"<BASIC-MISSION[^\n]*> mission allocates system: <TEACH-AIR-01,(\d+)>", log))
    verify(f"{v}_allocated_distinct", allocated == [str(i) for i in range(aircraft)])
    if v == "strict-shortage":
        verify("strict_cancel_without_wave", f"Time: 7 {mission_id} mission waiting:  timeout at 8.33333" in log and
               f"Time: 8.33333 {mission_id} mission cancelled:" in log and
               "mission starting, duration:" not in log and "mission success:" not in log and
               log.count("mission cancelled:") == 1)
        ready = [(0, 7), (8 + 1/3, 36)]
        assigned = [(7, 8 + 1/3)]
        operating = []
    else:
        verify(f"{v}_one_successful_wave", f"Time: 8 {mission_id} mission starting, duration: 2" in log and
               f"Time: 10 {mission_id} mission success:" in log and
               f"Time: 10 {mission_id} mission completed:" in log and
               log.count("mission starting, duration:") == log.count("mission success:") == 1 and
               "mission cancelled:" not in log)
        ready = [(0, 7), (10, 36)]
        assigned = [(7, 10)]
        operating = [(8, 10)]
    system = reports[v]["SystemResults"]
    verify(f"{v}_system_72_event_integrals", len(system) == 72 and all(
           r["STINT"] == i/2 and r["ETINT"] == (i+1)/2 and
           close(r["NSYRY"], aircraft*sum(intersection(i/2, (i+1)/2, a, b) for a, b in ready)/.5) and
           close(r["NSYMA"], aircraft*sum(intersection(i/2, (i+1)/2, a, b) for a, b in assigned)/.5) and
           close(r["NSYMO"], aircraft*sum(intersection(i/2, (i+1)/2, a, b) for a, b in operating)/.5) and
           close(r["STACC"], aircraft*sum(intersection(i/2, (i+1)/2, a, b) for a, b in operating)/.5)
           for i, r in enumerate(system)))
    verify(f"{v}_terminal_ready", close(system[-1]["NSYRY"], aircraft) and
           all(close(system[-1][name], 0) for name in ("NSYMA", "NSYMO", "NFAIL", "NSYWR", "NSYWI")) and
           f"systems ready: {aircraft} :" in log)
    expected_hours = 4 if v == "full-control" else (0 if v == "strict-shortage" else 2)
    verify(f"{v}_sortie_aircraft_hours", close(sum(r["NSYMO"]*.5 for r in system), expected_hours) and
           close(sum(r["STACC"]*.5 for r in system), expected_hours))

verify("nominal_shortfall_denominator", business["partial-minimum"]["MissionType"][1][0][2] == 2 and
       business["partial-minimum"]["MissionType"][1][0][5] == 2 and
       close(2/(2*2), reports["partial-minimum"]["ResultSummary"][0]["STMF"]))
result = {
    "schema": "simlox-j07-partial-formation-independent-readonly/v1", "case_id": "J07", "variant_id": "J07.var03",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go" if all(c["pass"] for c in checks) else "no_go",
    "passed": sum(c["pass"] for c in checks), "total": len(checks), "checks": checks,
    "evidence": evidence,
    "hand_ledger": {"full": {"sorties": 2, "operation_aircraft_hours": 4},
                    "strict": {"sorties": 0, "operation_aircraft_hours": 0},
                    "partial": {"sorties": 1, "operation_aircraft_hours": 2,
                                "nominal_requested_aircraft_hours": 4, "STMF": .5}},
    "limitations": [
        "The observed partial case is a successful mission with a nominal two-aircraft target and a one-aircraft minimum; it is not a partially successful mission outcome.",
        "One seed, one unit, one scheduled wave, no mid-mission aircraft loss, fault, or resource contention.",
        "The strict cancellation and relaxed success do not establish a general formation-selection policy.",
        "Native JSON trailing commas are removed only for parsing; closure hashes bind untouched bytes.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['passed']}/{result['total']} {result['decision']}")
for item in checks:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if result["decision"] == "bounded_go" else 1)
