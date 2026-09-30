"""Independent standard-library replay of J05.var03 sealed native and report-only runs.

Reads source, raw native artifacts and installed report settings. Does not import
author implementation, run SIMLOX, or change any frozen input/raw artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
AIR = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
DEFAULT = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
PATCHED = CASE / "runs" / "report-settings" / "replications-enabled.sxs"
EXPECTED = {
    "baseline": ("j05-profile-baseline-v101-20261001-01", "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7", 13),
    "snapshot-control": ("j05-snapshot-control-v101-20261001-01", "4a1233759a3354a1e61a3f5b7463846ac3726ffc0b0f5211c4b617c578d60b28", 15),
    "mixed-profile": ("j05-mixed-profile-v101-20261001-01", "0eaa2c466e196f471bde4054f278bd018bae5f3eea2e15b9d0f21dba96223e38", 16),
}
REPORT_RUNS = {
    "snapshot-default": ("j05-snapshot-report-default-20261001-01", "snapshot-control", "default"),
    "snapshot-replications": ("j05-snapshot-report-replications-20261001-01", "snapshot-control", "replications"),
    "mixed-replications": ("j05-mixed-report-replications-20261001-01", "mixed-profile", "replications"),
}
DEFAULT_SHA = "1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d"
PATCHED_SHA = "6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882"
checks = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def js(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def native(path):
    raw = Path(path).read_text(encoding="utf-8-sig")
    out = []
    quoted = escape = False
    for i, char in enumerate(raw):
        if quoted:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def ck(name, ok, detail=None):
    checks.append({"name": name, "pass": bool(ok), "detail": detail})


def tables(doc, outer="model"):
    return {t["name"]: t for t in doc[outer]["tables"]}


def rows(t):
    return [(i.get("instance_name", ""), row) for i in t["instances"] for row in i.get("rows", [])]


def records(report, name):
    t = tables(report, "report")[name]
    keys = [c["name"] for c in t["columns"]]
    return [dict(zip(keys, row)) for _, row in rows(t)]


def eq(a, b, tolerance=1e-6):
    return a is not None and math.isclose(float(a), float(b), rel_tol=0, abs_tol=tolerance)


def overlap(lo, hi, a, b):
    return max(0, min(hi, b) - max(lo, a)) / (hi - lo)


def seals(run, closure, expected_count):
    wrong = []
    for name, item in closure["raw"].items():
        f = run / name
        if not f.is_file() or f.stat().st_size != item["bytes"] or sha(f) != item["sha256"]:
            wrong.append(name)
    return len(closure["raw"]) == expected_count and not wrong, wrong


parent = AIR / "A01-single-aircraft-single-mission" / "native-input.json"
ck("accepted_A01_parent", sha(parent) == EXPECTED["baseline"][1], sha(parent))
ck("baseline_byte_identical", parent.read_bytes() == (CASE / "baseline-input.json").read_bytes())
contract, diff = js(CASE / "contract.json"), js(CASE / "exact-diff.json")
ck("contract_parent_and_inputs", contract["parent_input_sha256"] == EXPECTED["baseline"][1]
   and contract["input_sha256"] == {v: data[1] for v, data in EXPECTED.items()})
ck("diff_parent_and_inputs", diff["parent_input_sha256"] == EXPECTED["baseline"][1]
   and [diff[k] for k in ("baseline_input_sha256", "snapshot_control_input_sha256", "mixed_profile_input_sha256")]
   == [x[1] for x in EXPECTED.values()])
source = {v: js(CASE / f"{v}-input.json") for v in EXPECTED}
for variant, (_, expected_sha, count) in EXPECTED.items():
    ck(f"{variant}_input_sha", sha(CASE / f"{variant}-input.json") == expected_sha)
    ck(f"{variant}_source_business_table_count", sum(bool(rows(t)) for t in tables(source[variant]).values()) == count)
base, snap, mixed = (tables(source[v]) for v in EXPECTED)
ck("snapshot_delta_tables", {k for k in set(base) | set(snap) if base.get(k) != snap.get(k)}
   == {"ProblemDescription", "SnapshotResultTimes", "ReplicationResultControlSystem"})
ck("mixed_delta_tables", {k for k in set(snap) | set(mixed) if snap.get(k) != mixed.get(k)}
   == {"ProblemDescription", "SnapshotResultTimes", "ResultCollection", "ResultCollectionProfile"})
ck("direct_snapshot_rows", rows(snap["SnapshotResultTimes"]) == [("", [8.25, None]), ("", [10.25, None])]
   and [c.get("key") for c in snap["SnapshotResultTimes"]["columns"]] == [None, None]
   and rows(snap["ReplicationResultControlSystem"]) ==
   [("", ["TEACH-AIR-01", "TEACH-UNIT", "Y", "Y", "Y", None])])
ck("mixed_profile_rows", rows(mixed["SnapshotResultTimes"]) == [("", [6, None]), ("", [14, None])]
   and rows(mixed["ResultCollection"])[1] == ("", ["SYSTEM", 1, 0, 36, "J05MIX", None])
   and [r for _, r in rows(mixed["ResultCollectionProfile"])] == [
       ["J05MIX", "CONTINUOUS", 7.75, 1, None, .5, .5, None],
       ["J05MIX", "SNAPSHOT", 8.25, 1, None, None, None, None],
       ["J05MIX", "CONTINUOUS", 9.75, 1, None, .5, .5, None],
       ["J05MIX", "SNAPSHOT", 10.25, 1, None, None, None, None]])

default_bytes, patched_bytes = DEFAULT.read_bytes(), PATCHED.read_bytes()
changed = [i for i, (a, b) in enumerate(zip(default_bytes, patched_bytes)) if a != b]
ck("default_settings_sha", sha(DEFAULT) == DEFAULT_SHA)
ck("one_byte_OUTRP_patch", len(default_bytes) == len(patched_bytes) and changed == [67165]
   and default_bytes[67165:67167] == b"N\0" and patched_bytes[67165:67167] == b"Y\0"
   and sha(PATCHED) == PATCHED_SHA, {"changed_offsets": changed, "patched_sha256": sha(PATCHED)})

native_results = {}
for variant, (run_id, expected_sha, count) in EXPECTED.items():
    rd = CASE / "runs" / run_id
    inv, cl, steps = (js(rd / x) for x in ("invocation.json", "closure.json", "steps.json"))
    ck(f"{variant}_native_invocation", inv["schema"] == "simlox-j05-profile-snapshot-v101-native-candidate/ssh-cli-v1"
       and inv["variant"] == variant and inv["run_id"] == run_id
       and inv["input_sha256"] == expected_sha and inv["parent_sha256"] == EXPECTED["baseline"][1])
    ck(f"{variant}_native_guard", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0
       and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"]
       and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck(f"{variant}_native_five_steps", [s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps))
    ck(f"{variant}_native_closure", cl["schema"] == "simlox-j05-profile-snapshot-v101-native-closure/v1"
       and cl["run_id"] == run_id and cl["invocation_sha256"] == sha(rd / "invocation.json")
       and cl["error"] is None)
    before = inv["source_hashes_before"]
    ck(f"{variant}_native_source_seal", before == cl["source_hashes_before"] == cl["source_hashes_after"]
       and before["input"] == expected_sha and before["parent"] == EXPECTED["baseline"][1]
       and before["contract"] == sha(CASE / "contract.json")
       and before["builder"] == sha(CASE / "build.py")
       and before["checker"] == sha(CASE / "check_roundtrip.py")
       and before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    ok, wrong = seals(rd, cl, 12)
    ck(f"{variant}_native_raw_seals", ok, wrong)
    ck(f"{variant}_run_input_copy", sha(rd / "input.json") == expected_sha)
    exported = tables(native(rd / "roundtrip-raw.json"))
    actual_tables = {k: t for k, t in tables(source[variant]).items() if rows(t)}
    bad = [k for k, t in actual_tables.items()
           if k not in exported or t["columns"] != exported[k]["columns"] or rows(t) != rows(exported[k])]
    ck(f"{variant}_exact_business_roundtrip", len(actual_tables) == count and not bad, bad)
    run_log = (rd / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{variant}_zero_conversion_errors", "Errors: 0" in run_log and (rd / "model.sxo").stat().st_size > 4)
    log = (rd / "model.log").read_text(encoding="utf-8-sig")
    ck(f"{variant}_mission_event_chain", all(x in log for x in [
        "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>",
        "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:",
        "Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>",
        "Time: 24  Start of day no 1"]) and "mission aborted" not in log)
    rep = native(rd / "report-raw.json")
    summary = records(rep, "ResultSummary")[0]
    ck(f"{variant}_full_horizon_summary", summary["NREP"] == 1 and eq(summary["RTIUP"], 36)
       and all(eq(summary[k], 1) for k in ("MTMF", "MSTF", "MSUF", "STMF")))
    sy, stock = records(rep, "SystemResults"), records(rep, "StockTotalResults")
    target = [(7.75, 8.25), (9.75, 10.25)] if variant == "mixed-profile" else [(i / 2, (i + 1) / 2) for i in range(72)]
    ck(f"{variant}_system_intervals", [(x["STINT"], x["ETINT"]) for x in sy] == target)
    ck(f"{variant}_stock_intervals", [(x["STINT"], x["ETINT"]) for x in stock]
       == [(i / 2, (i + 1) / 2) for i in range(72)])
    bad = []
    for i, x in enumerate(sy):
        lo, hi = x["STINT"], x["ETINT"]
        exp = {"NSYRY": overlap(lo, hi, 0, 7) + overlap(lo, hi, 10, 36),
               "NSYMA": overlap(lo, hi, 7, 10), "NSYMR": overlap(lo, hi, 7, 8),
               "NSYMO": overlap(lo, hi, 8, 10), "STACC": overlap(lo, hi, 8, 10),
               "FTMO": overlap(lo, hi, 8, 10), "NFAIL": 0}
        bad.extend((i, k, x.get(k), v) for k, v in exp.items() if not eq(x.get(k), v))
    ck(f"{variant}_event_derived_system_bins", not bad, bad[:8])
    stock_bad = [(i, k, x.get(k)) for i, x in enumerate(stock)
                 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")
                 if not eq(x.get(k), 0)]
    ck(f"{variant}_stock_zero_demand", not stock_bad and all(eq(x["PNB"], 1) for x in stock), stock_bad[:8])
    native_results[variant] = {"run_id": run_id, "closure_sha256": sha(rd / "closure.json"),
                               "sxo_sha256": sha(rd / "model.sxo"),
                               "model_log_sha256": sha(rd / "model.log"),
                               "report_sha256": sha(rd / "report-raw.json"),
                               "system_bins": len(sy), "stock_bins": len(stock)}

ck("identical_full_native_event_logs", len({x["model_log_sha256"] for x in native_results.values()}) == 1)

report_results = {}
for label, (run_id, variant, mode) in REPORT_RUNS.items():
    rd = CASE / "runs" / "report-settings" / run_id
    source_rd = CASE / "runs" / EXPECTED[variant][0]
    inv, cl = js(rd / "invocation.json"), js(rd / "closure.json")
    expected_settings = DEFAULT_SHA if mode == "default" else PATCHED_SHA
    ck(f"{label}_report_invocation", inv["schema"] == "simlox-j05-report-settings-probe/v1"
       and inv["run_id"] == run_id and inv["variant"] == variant
       and inv["source_run_id"] == EXPECTED[variant][0] and inv["settings_mode"] == mode
       and " -report -rpts " in inv["command"] and " -rjexport " in inv["command"]
       and " -silent " in inv["command"] and inv["command"].endswith(" -close"))
    ck(f"{label}_report_guard", inv["session_id"] == 0 and inv["ssh_connection_present"]
       and "sshd.exe" in inv["ssh_ancestor_names"]
       and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck(f"{label}_report_closure", cl["schema"] == "simlox-j05-report-settings-probe-closure/v1"
       and cl["run_id"] == run_id and cl["invocation_sha256"] == sha(rd / "invocation.json")
       and cl["exit_code"] == 0 and cl["error"] is None)
    expected_sources = {"sxo": sha(source_rd / "model.sxo"),
                        "source_closure": sha(source_rd / "closure.json"),
                        "settings": expected_settings, "installed_default_settings": DEFAULT_SHA,
                        "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
                        "runner_script": sha(CASE / "report_existing_sxo_ssh.ps1")}
    ck(f"{label}_report_source_seal", inv["source_hashes_before"] ==
       cl["source_hashes_before"] == cl["source_hashes_after"] == expected_sources)
    ck(f"{label}_report_tied_to_native_sxo", js(source_rd / "closure.json")["raw"]["model.sxo"]["sha256"]
       == expected_sources["sxo"])
    ok, wrong = seals(rd, cl, 2)
    ck(f"{label}_report_raw_seals", ok, wrong)
    rep = native(rd / "report-raw.json")
    names = set(tables(rep, "report"))
    base_names = {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}
    replication_names = {"Replications", "SystemResultsReplicationTotal",
                         "SystemResultsReplication", "SystemResultsReplicationSnapshot"}
    ck(f"{label}_report_table_contrast", names == (base_names if mode == "default" else base_names | replication_names), sorted(names))
    sy, stock = records(rep, "SystemResults"), records(rep, "StockTotalResults")
    ck(f"{label}_report_intervals", len(stock) == 72
       and len(sy) == (2 if variant == "mixed-profile" else 72)
       and [(x["STINT"], x["ETINT"]) for x in sy] ==
       ([(7.75, 8.25), (9.75, 10.25)] if variant == "mixed-profile"
        else [(i / 2, (i + 1) / 2) for i in range(72)]))
    ck(f"{label}_same_aggregate_rows_as_native", sy == records(native(source_rd / "report-raw.json"), "SystemResults")
       and stock == records(native(source_rd / "report-raw.json"), "StockTotalResults"))
    summary = records(rep, "ResultSummary")[0]
    ck(f"{label}_full_summary", summary["NREP"] == 1 and eq(summary["RTIUP"], 36)
       and all(eq(summary[k], 1) for k in ("MTMF", "MSTF", "MSUF", "STMF")))
    if mode == "replications":
        snaprows = records(rep, "SystemResultsReplicationSnapshot")
        expected_snap = [(8.25, 0, 1, 1), (10.25, 1, 0, 0)]
        actual_snap = [(x["SSTIM"], x["NSYRY"], x["NSYMA"], x["NSYMO"]) for x in snaprows]
        ck(f"{label}_snapshot_times_values", actual_snap == expected_snap
           and all(x["UNID"] == "TEACH-UNIT" and x["SID"] == "TEACH-AIR-01" and x["REPLID"] == 1
                   for x in snaprows), actual_snap)
        repbins = records(rep, "SystemResultsReplication")
        ck(f"{label}_replication_bins", len(repbins) == len(sy)
           and all(eq(x["NSYMO"], y["NSYMO"]) and eq(x["NSYRY"], y["NSYRY"])
                   for x, y in zip(repbins, sy)))
        ck(f"{label}_one_replication", records(rep, "Replications")[0]["REPNO"] == 1
           and records(rep, "Replications")[0]["RSEED"] == "1")
    report_results[label] = {"run_id": run_id, "closure_sha256": sha(rd / "closure.json"),
                             "report_sha256": sha(rd / "report-raw.json"),
                             "tables": sorted(names), "system_bins": len(sy),
                             "stock_bins": len(stock)}

ck("profile_overrides_global_snapshot_times", [x["SSTIM"] for x in records(
   native(CASE / "runs" / "report-settings" / REPORT_RUNS["mixed-replications"][0] / "report-raw.json"),
   "SystemResultsReplicationSnapshot")] == [8.25, 10.25]
   and [r[0] for _, r in rows(mixed["SnapshotResultTimes"])] == [6, 14])
ck("continuous_half_vs_instantaneous_one", all(eq(x["NSYMO"], .5) for x in records(
   native(CASE / "runs" / EXPECTED["mixed-profile"][0] / "report-raw.json"), "SystemResults"))
   and all(eq(x["NSYMO"], value) for x, value in zip(records(native(
       CASE / "runs" / "report-settings" / REPORT_RUNS["mixed-replications"][0] / "report-raw.json"),
       "SystemResultsReplicationSnapshot"), [1, 0])))

result = {
    "schema": "j05-var03-v101-independent-native-and-report-replay/v1",
    "reviewer": "independent read-only standard-library replay; no author code imported",
    "decision": "GO_BOUNDED" if all(x["pass"] for x in checks) else "NO_GO",
    "passed": sum(x["pass"] for x in checks), "total": len(checks),
    "checks": checks, "native_runs": native_results, "report_only_runs": report_results,
    "accepted_scope": "One fixed-seed A01 mission: profile selects two half-hour SYSTEM continuous intervals with 0.5 operating averages, while report-only export with one-byte OUTRP=Y settings exposes SYSTEM replication snapshots at 8.25 operating1 and 10.25 ready1. Profile snapshots override direct SnapshotResultTimes 6/14; Stock remains 72 half-hour bins. Full mission succeeds at 10 and summary horizon is 36.",
    "limitations": [
        "Report-only command and GUI preservation are attested by sealed session-0 runner records; reviewer did not observe live GUI.",
        "One seed, one aircraft and one SYSTEM profile. Nested/repeated profiles and other result types are untested.",
        "Snapshot values were obtained through a local one-byte modification of installed Default.sxs; its binary format has not been generally reverse engineered.",
        "Direct MISSION interval output, GUI display and cross-engine equivalence remain unverified.",
    ],
}
OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['decision']} {result['passed']}/{result['total']}")
print(f"script_sha256={sha(__file__)}")
print(f"report_sha256={sha(OUT)}")
