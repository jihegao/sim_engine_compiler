"""Author replay of J05 mixed continuous/snapshot collection evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_IDS = {
    "baseline": "j05-profile-baseline-v101-20261001-01",
    "snapshot-control": "j05-snapshot-control-v101-20261001-01",
    "mixed-profile": "j05-mixed-profile-v101-20261001-01",
}
REPORT_IDS = {
    "default": "j05-snapshot-report-default-20261001-01",
    "direct": "j05-snapshot-report-replications-20261001-01",
    "profile": "j05-mixed-report-replications-20261001-01",
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name: str, condition: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(condition), "detail": detail})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(report: dict) -> dict[str, list[dict]]:
    out = {}
    for table in report["report"]["tables"]:
        cols = [c["name"] for c in table["columns"]]
        out[table["name"]] = [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]
    return out


def near(value: object, expected: float) -> bool:
    return value is not None and abs(float(value) - expected) < 1e-9


contract = load(HERE / "contract.json")
inputs = {variant: parse_native(HERE / f"{variant}-input.json") for variant in RUN_IDS}
tabs = {variant: {t["name"]: t for t in doc["model"]["tables"]} for variant, doc in inputs.items()}
ck("parent_identity", sha(HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json") ==
   contract["parent_input_sha256"] == sha(HERE / "baseline-input.json"))
for variant in RUN_IDS:
    ck(f"{variant}_input_sha", sha(HERE / f"{variant}-input.json") == contract["input_sha256"][variant])
ck("direct_exact_changed_tables", {k for k in set(tabs["baseline"]) | set(tabs["snapshot-control"])
   if tabs["baseline"].get(k) != tabs["snapshot-control"].get(k)} ==
   {"ProblemDescription", "SnapshotResultTimes", "ReplicationResultControlSystem"})
ck("profile_exact_changed_tables", {k for k in set(tabs["snapshot-control"]) | set(tabs["mixed-profile"])
   if tabs["snapshot-control"].get(k) != tabs["mixed-profile"].get(k)} ==
   {"ProblemDescription", "SnapshotResultTimes", "ResultCollection", "ResultCollectionProfile"})
ck("snapshot_source_times", [r[0] for r in tabs["snapshot-control"]["SnapshotResultTimes"]["instances"][0]["rows"]] == [8.25, 10.25])
ck("profile_global_snapshot_times", [r[0] for r in tabs["mixed-profile"]["SnapshotResultTimes"]["instances"][0]["rows"]] == [6, 14])
ck("profile_source_rows", tabs["mixed-profile"]["ResultCollectionProfile"]["instances"][0]["rows"] == [
   ["J05MIX", "CONTINUOUS", 7.75, 1, None, .5, .5, None],
   ["J05MIX", "SNAPSHOT", 8.25, 1, None, None, None, None],
   ["J05MIX", "CONTINUOUS", 9.75, 1, None, .5, .5, None],
   ["J05MIX", "SNAPSHOT", 10.25, 1, None, None, None, None]])
ck("replication_snapshot_enabled", tabs["mixed-profile"]["ReplicationResultControlSystem"]["instances"][0]["rows"] ==
   [["TEACH-AIR-01", "TEACH-UNIT", "Y", "Y", "Y", None]])

native_reports = {}
logs = {}
for variant, run_id in RUN_IDS.items():
    run = HERE / "runs" / run_id
    closure = load(run / "closure.json")
    invocation = load(run / "invocation.json")
    steps = load(run / "steps.json")
    ck(f"{variant}_native_identity", closure["run_id"] == invocation["run_id"] == run_id and closure["error"] is None)
    ck(f"{variant}_native_source_seal", closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
       and closure["source_hashes_before"]["input"] == contract["input_sha256"][variant])
    ck(f"{variant}_native_invocation_seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{variant}_native_raw_seals", len(closure["raw"]) == 12 and all(
       sha(run / name) == meta["sha256"] and (run / name).stat().st_size == meta["bytes"]
       for name, meta in closure["raw"].items()))
    ck(f"{variant}_native_guard", invocation["execution_mode"] == "ssh_cli_v1"
       and invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui"]["pid"] == 13340
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck(f"{variant}_native_steps", [x["name"] for x in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps))
    ck(f"{variant}_native_roundtrip", load(run / "roundtrip-validation.json")["passed"]
       and len(populated(inputs[variant])) == {"baseline": 13, "snapshot-control": 15, "mixed-profile": 16}[variant]
       and all(populated(parse_native(run / "roundtrip-raw.json")).get(name) == table
               for name, table in populated(inputs[variant]).items()))
    ck(f"{variant}_zero_converter_errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in
       (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    logs[variant] = (run / "model.log").read_bytes()
    native_reports[variant] = tables(parse_native(run / "report-raw.json"))
    summary = native_reports[variant]["ResultSummary"]
    ck(f"{variant}_full_summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36
       and summary[0]["MTMF"] == summary[0]["MSTF"] == 1)
    stock = native_reports[variant]["StockTotalResults"]
    ck(f"{variant}_stock_ledger", len(stock) == 72 and all(
       near(row["STINT"], i * .5) and near(row["ETINT"], (i + 1) * .5)
       and row["PNB"] == 1 and all(v in (0, None) for k, v in row.items() if k not in ("STINT", "ETINT", "PNB"))
       for i, row in enumerate(stock)))

ck("same_full_event_log", len(set(logs.values())) == 1 and b"mission starting" in logs["baseline"]
   and b"mission success" in logs["baseline"] and b"Time: 24  Start of day no 1" in logs["baseline"])
ck("direct_system_default_bins", len(native_reports["baseline"]["SystemResults"]) ==
   len(native_reports["snapshot-control"]["SystemResults"]) == 72)
mixed_system = native_reports["mixed-profile"]["SystemResults"]
ck("profile_continuous_bins", len(mixed_system) == 2 and [
   (r["STINT"], r["ETINT"], r["NSYRY"], r["NSYMA"], r["NSYMO"], r["STACC"])
   for r in mixed_system] == [
       (7.75, 8.25, 0, 1, .5, .5), (9.75, 10.25, .5, .5, .5, .5)])
ck("native_default_omits_snapshots", all("SystemResultsReplicationSnapshot" not in r for r in native_reports.values()))

default_sxs = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
probe_sxs = HERE / "runs" / "report-settings" / "replications-enabled.sxs"
orig, patched = default_sxs.read_bytes(), probe_sxs.read_bytes()
ck("installed_settings_fingerprint", sha(default_sxs) == "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d")
ck("one_byte_settings_probe", len(orig) == len(patched) == 119129
   and [(i, a, b) for i, (a, b) in enumerate(zip(orig, patched)) if a != b] == [(67165, ord("N"), ord("Y"))]
   and sha(probe_sxs) == "6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882")

report_tables = {}
for mode, run_id in REPORT_IDS.items():
    run = HERE / "runs" / "report-settings" / run_id
    closure, invocation = load(run / "closure.json"), load(run / "invocation.json")
    ck(f"{mode}_report_identity", closure["run_id"] == invocation["run_id"] == run_id
       and closure["exit_code"] == 0 and closure["error"] is None)
    ck(f"{mode}_report_source_seal", closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["settings"] ==
       (sha(default_sxs) if mode == "default" else sha(probe_sxs)))
    ck(f"{mode}_report_invocation_seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{mode}_report_raw_seals", len(closure["raw"]) == 2 and all(
       sha(run / name) == meta["sha256"] and (run / name).stat().st_size == meta["bytes"]
       for name, meta in closure["raw"].items()))
    ck(f"{mode}_report_guard", invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui"]["pid"] == 13340
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck(f"{mode}_report_completed", "Report completed" in (run / "report-export.log").read_text(encoding="utf-8-sig")
       and "Export completed!" in (run / "report-export.log").read_text(encoding="utf-8-sig"))
    report_tables[mode] = tables(parse_native(run / "report-raw.json"))

ck("default_vs_enabled_snapshot_table", "SystemResultsReplicationSnapshot" not in report_tables["default"]
   and len(report_tables["direct"]["SystemResultsReplicationSnapshot"]) == 2
   and len(report_tables["profile"]["SystemResultsReplicationSnapshot"]) == 2)
for mode in ("direct", "profile"):
    rows = report_tables[mode]["SystemResultsReplicationSnapshot"]
    ck(f"{mode}_instantaneous_snapshots", [
       (r["UNID"], r["SID"], r["SSTIM"], r["REPLID"], r["NSYRY"], r["NSYMA"], r["NSYMO"])
       for r in rows] == [
           ("TEACH-UNIT", "TEACH-AIR-01", 8.25, 1, 0, 1, 1),
           ("TEACH-UNIT", "TEACH-AIR-01", 10.25, 1, 1, 0, 0)])
ck("profile_overrides_global_snapshot_times", [r["SSTIM"] for r in report_tables["profile"]["SystemResultsReplicationSnapshot"]] == [8.25, 10.25]
   and [r[0] for r in tabs["mixed-profile"]["SnapshotResultTimes"]["instances"][0]["rows"]] == [6, 14])
ck("profile_report_matches_native_intervals", report_tables["profile"]["SystemResults"] == mixed_system)
ck("snapshot_vs_interval_at_8_25", mixed_system[0]["NSYMO"] == .5
   and report_tables["profile"]["SystemResultsReplicationSnapshot"][0]["NSYMO"] == 1)
ck("snapshot_vs_interval_at_10_25", mixed_system[1]["NSYRY"] == .5
   and report_tables["profile"]["SystemResultsReplicationSnapshot"][1]["NSYRY"] == 1)

result = {
    "schema": "simlox-j05-profile-snapshot-author-validation/v1",
    "case_id": "J05", "version": "1.0.1", "passed": all(c["pass"] for c in checks),
    "check_count": len(checks), "checks": checks,
    "scope": "system_continuous_interval_average_and_replication_snapshot_profile_override",
    "limitations": ["one replication", "default JSON report omits snapshots; a local one-field settings copy was required",
                    "nested/repeated profiles and other result types not verified"],
}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{sum(c['pass'] for c in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
for item in checks:
    if not item["pass"]:
        print(item["name"], item["detail"])
raise SystemExit(0 if result["passed"] else 1)
