"""Author replay of sealed J05.var04 nested/repeated collection evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_IDS = {
    "baseline": "j05-nested-baseline-v100-20261001-01",
    "direct-control": "j05-nested-direct-v100-20261001-01",
    "nested-repeat": "j05-nested-repeat-v100-20261001-01",
}
REPORT_IDS = {
    "direct-control": "j05-nested-direct-report-v100-20261001-01",
    "nested-repeat": "j05-nested-repeat-report-v100-20261001-01",
}
SHA = {
    "baseline": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
    "direct-control": "0eaa2c466e196f471bde4054f278bd018bae5f3eea2e15b9d0f21dba96223e38",
    "nested-repeat": "f14aadd297fb97cb5031726c6da6acf0060fe051c73a65ae271489369874c5f1",
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name: str, result: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(result), "detail": detail})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(report: dict) -> dict[str, list[dict]]:
    out = {}
    for table in report["report"]["tables"]:
        cols = [c["name"] for c in table["columns"]]
        out[table["name"]] = [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]
    return out


contract = load(HERE / "contract.json")
inputs = {v: parse_native(HERE / f"{v}-input.json") for v in RUN_IDS}
source_tables = {v: {t["name"]: t for t in doc["model"]["tables"]} for v, doc in inputs.items()}
ck("contract_sources", sha(HERE / "baseline-input.json") == sha(HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json") == contract["parent_input_sha256"]
   and sha(HERE / "direct-control-input.json") == sha(HERE.parent / "J05-profile-snapshot-v1.0.1" / "mixed-profile-input.json") == contract["direct_control_input_sha256"]
   and sha(HERE / "nested-repeat-input.json") == contract["nested_input_sha256"])
ck("only_three_tables_changed", {name for name in set(source_tables["direct-control"]) | set(source_tables["nested-repeat"])
   if source_tables["direct-control"].get(name) != source_tables["nested-repeat"].get(name)} ==
   {"ProblemDescription", "ResultCollection", "ResultCollectionProfile"})
ck("nested_rows", source_tables["nested-repeat"]["ResultCollectionProfile"]["instances"][0]["rows"] == [
    ["J05SEG", "CONTINUOUS", 0, 1, None, .5, .5, None],
    ["J05SEG", "SNAPSHOT", .5, 1, None, None, None, None],
    ["J05TOP", "J05SEG", 7.75, 2, 2, None, None, None],
])
ck("collection_ref", source_tables["nested-repeat"]["ResultCollection"]["instances"][0]["rows"][1] ==
   ["SYSTEM", 1, 0, 36, "J05TOP", None])
ck("global_times_unchanged", source_tables["nested-repeat"]["SnapshotResultTimes"] == source_tables["direct-control"]["SnapshotResultTimes"]
   and [r[0] for r in source_tables["nested-repeat"]["SnapshotResultTimes"]["instances"][0]["rows"]] == [6, 14])

native = {}
event_logs = {}
for variant, run_id in RUN_IDS.items():
    run = HERE / "runs" / run_id
    closure, invocation, steps = (load(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
    ck(f"{variant}_input", sha(HERE / f"{variant}-input.json") == SHA[variant] == sha(run / "input.json"))
    ck(f"{variant}_identity", closure["run_id"] == invocation["run_id"] == run_id and closure["error"] is None)
    ck(f"{variant}_source_seal", closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
       and closure["source_hashes_before"]["input"] == SHA[variant]
       and closure["source_hashes_before"]["direct_parent"] == SHA["direct-control"])
    ck(f"{variant}_invocation_seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{variant}_raw_seals", len(closure["raw"]) == 12 and all(
       sha(run / name) == meta["sha256"] and (run / name).stat().st_size == meta["bytes"]
       for name, meta in closure["raw"].items()))
    ck(f"{variant}_guard", invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui"]["pid"] == 13340
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck(f"{variant}_five_steps", [x["name"] for x in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps))
    roundtrip = load(run / "roundtrip-validation.json")
    ck(f"{variant}_roundtrip", roundtrip["passed"] and not roundtrip["differences"]
       and len(populated(inputs[variant])) == {"baseline": 13, "direct-control": 16, "nested-repeat": 16}[variant]
       and all(populated(parse_native(run / "roundtrip-raw.json")).get(name) == value
               for name, value in populated(inputs[variant]).items()))
    ck(f"{variant}_zero_errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in
       (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    event_logs[variant] = (run / "model.log").read_bytes()
    native[variant] = tables(parse_native(run / "report-raw.json"))
    summary = native[variant]["ResultSummary"]
    ck(f"{variant}_full_horizon", len(summary) == 1 and summary[0]["NREP"] == 1
       and (summary[0]["RTILW"], summary[0]["RTIUP"], summary[0]["MTMF"], summary[0]["MSTF"]) == (0, 36, 1, 1))
    stock = native[variant]["StockTotalResults"]
    ck(f"{variant}_stock", len(stock) == 72 and all(
       row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5 and row["PNB"] == 1
       and all(value in (0, None) for field, value in row.items() if field not in ("STINT", "ETINT", "PNB"))
       for i, row in enumerate(stock)))

ck("event_logs_identical", len(set(event_logs.values())) == 1 and
   sha(HERE / "runs" / RUN_IDS["nested-repeat"] / "model.log") == "6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed")
for event in (b"Time: 7 <TEACH-UNIT> mission ordered", b"Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting",
              b"Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", b"Time: 10 <TEACH-AIR-01,BASE-01,0> System ready",
              b"Time: 24  Start of day no 1"):
    ck(f"event_{event[:24].decode()}", event in event_logs["nested-repeat"])
ck("baseline_72_system_bins", len(native["baseline"]["SystemResults"]) == 72)
expected_bins = [(7.75, 8.25, 0, 1, .5, .5), (9.75, 10.25, .5, .5, .5, .5)]
for variant in ("direct-control", "nested-repeat"):
    rows = native[variant]["SystemResults"]
    ck(f"{variant}_two_bins", [(r["STINT"], r["ETINT"], r["NSYRY"], r["NSYMA"], r["NSYMO"], r["STACC"]) for r in rows] == expected_bins)
    ck(f"{variant}_default_omits_snapshots", "SystemResultsReplicationSnapshot" not in native[variant])
ck("native_direct_nested_rows_equal", {k: v for k, v in native["direct-control"].items() if k != "ProblemDescription"} ==
   {k: v for k, v in native["nested-repeat"].items() if k != "ProblemDescription"})

installed = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
patched = HERE / "runs" / "report-settings" / "replications-enabled.sxs"
original_bytes, patched_bytes = installed.read_bytes(), patched.read_bytes()
ck("one_byte_report_settings", len(original_bytes) == len(patched_bytes) == 119129
   and [(i, a, b) for i, (a, b) in enumerate(zip(original_bytes, patched_bytes)) if a != b] == [(67165, 78, 89)]
   and sha(installed) == "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
   and sha(patched) == "6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882")
enabled = {}
for variant, run_id in REPORT_IDS.items():
    run = HERE / "runs" / "report-settings" / run_id
    closure, invocation = load(run / "closure.json"), load(run / "invocation.json")
    ck(f"{variant}_report_seals", closure["run_id"] == invocation["run_id"] == run_id
       and closure["error"] is None and closure["exit_code"] == 0
       and closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["invocation_sha256"] == sha(run / "invocation.json")
       and len(closure["raw"]) == 2 and all(sha(run / n) == m["sha256"] and (run / n).stat().st_size == m["bytes"] for n, m in closure["raw"].items()))
    ck(f"{variant}_report_guard", invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui"]["pid"] == 13340
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck(f"{variant}_report_complete", "Report completed" in (run / "report-export.log").read_text(encoding="utf-8-sig")
       and "Export completed!" in (run / "report-export.log").read_text(encoding="utf-8-sig"))
    enabled[variant] = tables(parse_native(run / "report-raw.json"))
    snapshots = enabled[variant]["SystemResultsReplicationSnapshot"]
    ck(f"{variant}_snapshots", [(r["UNID"], r["SID"], r["SSTIM"], r["REPLID"], r["NSYRY"], r["NSYMA"], r["NSYMO"]) for r in snapshots] == [
       ("TEACH-UNIT", "TEACH-AIR-01", 8.25, 1, 0, 1, 1),
       ("TEACH-UNIT", "TEACH-AIR-01", 10.25, 1, 1, 0, 0)])
    ck(f"{variant}_report_system_matches_native", enabled[variant]["SystemResults"] == native[variant]["SystemResults"])
ck("enabled_direct_nested_rows_equal", {k: v for k, v in enabled["direct-control"].items() if k != "ProblemDescription"} ==
   {k: v for k, v in enabled["nested-repeat"].items() if k != "ProblemDescription"})

result = {"schema": "simlox-j05-nested-repeat-author-validation/v1", "case_id": "J05", "variant_id": "J05.var04",
          "version": "1.0.0", "passed": all(c["pass"] for c in checks), "check_count": len(checks), "checks": checks,
          "scope": "one_subprofile_repeated_twice_with_continuous_and_snapshot_equivalent_to_direct_profile",
          "limitations": contract["limitations"]}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{sum(c['pass'] for c in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
for item in checks:
    if not item["pass"]:
        print(item["name"], item["detail"])
raise SystemExit(0 if result["passed"] else 1)
