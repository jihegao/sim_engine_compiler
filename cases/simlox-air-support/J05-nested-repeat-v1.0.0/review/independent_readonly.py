"""Independent, standard-library replay of sealed J05.var04 CLI evidence.

Reads frozen source and raw runs only. It does not import the author tooling or
invoke SIMLOX. The sole output is the deterministic JSON beside this script.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
NATIVE = {
    "baseline": "j05-nested-baseline-v100-20261001-01",
    "direct-control": "j05-nested-direct-v100-20261001-01",
    "nested-repeat": "j05-nested-repeat-v100-20261001-01",
}
REPORT = {
    "direct-control": "j05-nested-direct-report-v100-20261001-01",
    "nested-repeat": "j05-nested-repeat-report-v100-20261001-01",
}
INPUT_SHA = {
    "baseline": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
    "direct-control": "0eaa2c466e196f471bde4054f278bd018bae5f3eea2e15b9d0f21dba96223e38",
    "nested-repeat": "f14aadd297fb97cb5031726c6da6acf0060fe051c73a65ae271489369874c5f1",
}
checks: list[dict] = []


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, truth: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(truth), "detail": detail})


def plain(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Ignore native trailing commas only outside quoted strings."""
    raw = path.read_text(encoding="utf-8-sig")
    result: list[str] = []
    quoted = escaped = False
    for pos, char in enumerate(raw):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char == "," and raw[pos + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            result.append(char)
    return json.loads("".join(result))


def source_rows(doc: dict) -> dict:
    output = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        assert name not in output
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            assert all(len(row) == len(table["columns"]) for row in rows)
            output[name] = ([c["name"] for c in table["columns"]], rows)
    return output


def report_rows(doc: dict) -> dict:
    output = {}
    for table in doc["report"]["tables"]:
        name = table["name"]
        assert name not in output
        cols = [c["name"] for c in table["columns"]]
        output[name] = [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]
    return output


def seal(closure: dict, run: Path) -> bool:
    return (closure["invocation_sha256"] == digest(run / "invocation.json")
            and all((run / name).is_file() and (run / name).stat().st_size == meta["bytes"]
                    and digest(run / name) == meta["sha256"]
                    for name, meta in closure["raw"].items()))


def guard(inv: dict) -> bool:
    return (inv["session_id"] == 0 and inv["ssh_connection_present"] is True
            and "sshd.exe" in inv["ssh_ancestor_names"]
            and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
            and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] > 0)


contract = plain(CASE / "contract.json")
sources = {key: native_json(CASE / f"{key}-input.json") for key in NATIVE}
src_rows = {key: source_rows(value) for key, value in sources.items()}
source_tables = {key: {t["name"]: t for t in value["model"]["tables"]}
                 for key, value in sources.items()}
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
check("pinned_manual_dictionary", digest(manual) == contract["source_manual_sha256"] and
      digest(dictionary) == contract["source_dictionary_sha256"])
check("accepted_parent_bytes", digest(CASE / "baseline-input.json") ==
      digest(ROOT / "A01-single-aircraft-single-mission" / "native-input.json") == INPUT_SHA["baseline"])
check("accepted_direct_bytes", digest(CASE / "direct-control-input.json") ==
      digest(ROOT / "J05-profile-snapshot-v1.0.1" / "mixed-profile-input.json") == INPUT_SHA["direct-control"])
check("frozen_child_bytes", digest(CASE / "nested-repeat-input.json") == INPUT_SHA["nested-repeat"])
check("contract_source_hashes", (contract["parent_input_sha256"], contract["direct_control_input_sha256"],
      contract["nested_input_sha256"]) == tuple(INPUT_SHA.values()))
for key, count in (("baseline", 13), ("direct-control", 16), ("nested-repeat", 16)):
    check(f"{key}_source_table_count", len(src_rows[key]) == count)
check("only_three_changed_tables", {name for name in src_rows["direct-control"] if
      src_rows["direct-control"][name] != src_rows["nested-repeat"][name]} ==
      {"ProblemDescription", "ResultCollection", "ResultCollectionProfile"})
check("exact_full_table_delta", len(source_tables["direct-control"]) ==
      len(source_tables["nested-repeat"]) == 34 and
      set(source_tables["direct-control"]) == set(source_tables["nested-repeat"]) and
      {name for name in source_tables["direct-control"] if
       source_tables["direct-control"][name] != source_tables["nested-repeat"][name]} ==
      {"ProblemDescription", "ResultCollection", "ResultCollectionProfile"})
check("nested_profile_wiring", src_rows["nested-repeat"]["ResultCollectionProfile"][1] == [
      ["J05SEG", "CONTINUOUS", 0, 1, None, .5, .5, None],
      ["J05SEG", "SNAPSHOT", .5, 1, None, None, None, None],
      ["J05TOP", "J05SEG", 7.75, 2, 2, None, None, None]])
check("system_profile_reference", src_rows["nested-repeat"]["ResultCollection"][1][1] ==
      ["SYSTEM", 1, 0, 36, "J05TOP", None])
check("global_snapshot_unchanged", src_rows["nested-repeat"]["SnapshotResultTimes"] ==
      src_rows["direct-control"]["SnapshotResultTimes"])

reports: dict[str, dict] = {}
events: dict[str, bytes] = {}
closures: dict[str, dict] = {}
gui_ident: dict[str, tuple] = {}
for variant, run_id in NATIVE.items():
    run = RUNS / run_id
    closure, invocation, steps = (plain(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
    closures[variant] = closure
    gui_ident[variant] = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
    check(f"{variant}_identity", closure["run_id"] == invocation["run_id"] == run_id and
          invocation["variant"] == variant and closure["error"] is None)
    check(f"{variant}_closure", seal(closure, run) and len(closure["raw"]) == 12)
    before = closure["source_hashes_before"]
    check(f"{variant}_source_seal", before == closure["source_hashes_after"] and
          before["input"] == INPUT_SHA[variant] == digest(run / "input.json") and
          before["parent"] == INPUT_SHA["baseline"] and before["direct_parent"] == INPUT_SHA["direct-control"] and
          before["contract"] == digest(CASE / "contract.json") and
          before["builder"] == digest(CASE / "build.py") and
          before["checker"] == digest(CASE / "check_roundtrip.py") and
          before["runner_script"] == digest(CASE / "run_native_ssh.ps1"))
    check(f"{variant}_session_gui", guard(invocation))
    check(f"{variant}_steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    exported = source_rows(native_json(run / "roundtrip-raw.json"))
    check(f"{variant}_roundtrip", all(exported.get(name) == rows for name, rows in src_rows[variant].items()))
    check(f"{variant}_import_export_markers", "Import completed!" in
          (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
          "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{variant}_conversion", "Errors: 0, Warnings: 2, Notes: 0" in conversion and
          "warning #108" in conversion and "warning #126" in conversion and "Saving results" in conversion)
    reports[variant] = report_rows(native_json(run / "report-raw.json"))
    events[variant] = (run / "model.log").read_bytes()
    summary = reports[variant]["ResultSummary"]
    check(f"{variant}_summary", len(summary) == 1 and all(summary[0][k] == v for k, v in
          {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items()))
    stock = reports[variant]["StockTotalResults"]
    check(f"{variant}_stock_72", len(stock) == 72 and all(
          r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 and r["PNB"] == 1 and
          all(value in (0, None) for key, value in r.items() if key not in ("STINT", "ETINT", "PNB"))
          for i, r in enumerate(stock)))

check("gui_identity_common", len(set(gui_ident.values())) == 1)
check("event_logs_byte_equal", len(set(events.values())) == 1)
trace = events["nested-repeat"].decode("utf-8-sig", errors="replace")
for label, pattern in {
    "call_7": r"Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
    "allocation_7": r"Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
    "start_8": r"Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2",
    "task_8_5": r"Time: 8.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> task starting",
    "task_9_5": r"Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> task completed",
    "success_10": r"Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
    "complete_10": r"Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed",
    "ready_10": r"Time: 10 <TEACH-AIR-01,BASE-01,0> System ready",
}.items():
    check(f"event_{label}", pattern in trace)
check("one_mission_no_fault", len(re.findall(r"mission starting, duration", trace)) == 1 and
      "failure occurred" not in trace and "mission cancelled" not in trace and "mission aborted" not in trace)

base = reports["baseline"]["SystemResults"]
check("baseline_72_system_bins", len(base) == 72 and all(
      r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 and
      r["NSYRY"] == (1 if i < 14 or i >= 20 else 0) and
      r["NSYMA"] == (1 if 14 <= i < 20 else 0) and
      r["NSYMO"] == (1 if 16 <= i < 20 else 0) and
      r["STACC"] == (1 if 16 <= i < 20 else 0)
      for i, r in enumerate(base)))
expected = [(7.75, 8.25, 0, 1, .5, .5), (9.75, 10.25, .5, .5, .5, .5)]
for variant in ("direct-control", "nested-repeat"):
    system = reports[variant]["SystemResults"]
    check(f"{variant}_two_system_bins", [tuple(r[k] for k in
          ("STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "STACC")) for r in system] == expected)
    check(f"{variant}_native_no_snapshots", "SystemResultsReplicationSnapshot" not in reports[variant])
check("direct_nested_native_report_equal", {k: v for k, v in reports["direct-control"].items() if k != "ProblemDescription"} ==
      {k: v for k, v in reports["nested-repeat"].items() if k != "ProblemDescription"})

installed = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
patched = RUNS / "report-settings" / "replications-enabled.sxs"
raw_settings, patched_settings = installed.read_bytes(), patched.read_bytes()
differences = [(i, a, b) for i, (a, b) in enumerate(zip(raw_settings, patched_settings)) if a != b]
check("one_byte_settings_patch", len(raw_settings) == len(patched_settings) == 119129 and
      differences == [(67165, 78, 89)] and
      digest(installed) == "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d" and
      digest(patched) == "6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882")

enabled: dict[str, dict] = {}
for variant, run_id in REPORT.items():
    run = RUNS / "report-settings" / run_id
    closure, invocation = plain(run / "closure.json"), plain(run / "invocation.json")
    native_run = RUNS / NATIVE[variant]
    check(f"{variant}_report_closure", closure["run_id"] == invocation["run_id"] == run_id and
          closure["error"] is None and closure["exit_code"] == 0 and seal(closure, run) and
          len(closure["raw"]) == 2)
    source = closure["source_hashes_before"]
    check(f"{variant}_report_source_seal", source == closure["source_hashes_after"] and
          source["sxo"] == digest(native_run / "model.sxo") and
          source["source_closure"] == digest(native_run / "closure.json") and
          source["settings"] == digest(patched) and
          source["installed_default_settings"] == digest(installed) and
          source["runner_script"] == digest(CASE / "report_existing_sxo_ssh.ps1"))
    check(f"{variant}_report_guard", guard(invocation) and
          (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"]) == gui_ident[variant] and
          invocation["source_run_id"] == NATIVE[variant] and "-report" in invocation["command"] and
          "-rpts" in invocation["command"] and "-rjexport" in invocation["command"])
    log = (run / "report-export.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{variant}_report_completion", "Report completed" in log and "Export completed!" in log)
    enabled[variant] = report_rows(native_json(run / "report-raw.json"))
    snapshots = enabled[variant].get("SystemResultsReplicationSnapshot", [])
    check(f"{variant}_snapshots", [(r["UNID"], r["SID"], r["SSTIM"], r["REPLID"],
          r["NSYRY"], r["NSYMA"], r["NSYMO"]) for r in snapshots] == [
          ("TEACH-UNIT", "TEACH-AIR-01", 8.25, 1, 0, 1, 1),
          ("TEACH-UNIT", "TEACH-AIR-01", 10.25, 1, 1, 0, 0)])
    check(f"{variant}_enabled_system_stock_summary", all(enabled[variant][name] == reports[variant][name]
          for name in ("SystemResults", "StockTotalResults", "ResultSummary")))
check("direct_nested_enabled_report_equal", {k: v for k, v in enabled["direct-control"].items() if k != "ProblemDescription"} ==
      {k: v for k, v in enabled["nested-repeat"].items() if k != "ProblemDescription"})

result = {
    "schema": "simlox-j05-nested-repeat-independent-readonly/v1",
    "reviewer": "independent read-only agent; no author module imports or native calls",
    "case_id": "J05", "variant_id": "J05.var04", "version": "1.0.0",
    "decision": "bounded_go" if all(c["pass"] for c in checks) else "no_go",
    "passed": sum(c["pass"] for c in checks), "total": len(checks), "checks": checks,
    "raw_report_sha256": {key: digest(RUNS / run_id / "report-raw.json") for key, run_id in NATIVE.items()},
    "report_only_sha256": {key: digest(RUNS / "report-settings" / run_id / "report-raw.json") for key, run_id in REPORT.items()},
    "limitations": [
        "One fixed seed, one mission, one nested segment repeated twice; deeper nesting and overlap limits untested.",
        "Snapshot rows require the separate report-only pass with a one-byte local settings change; default JSON report omits them.",
        "CLI output demonstrates SYSTEM collection only; MISSION intervals, GUI display, and other result types are untested.",
        "Native JSON has a trailing comma; parsing normalizes a copy while hashes bind original bytes.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['passed']}/{result['total']} {result['decision']}")
for item in checks:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if result["decision"] == "bounded_go" else 1)
