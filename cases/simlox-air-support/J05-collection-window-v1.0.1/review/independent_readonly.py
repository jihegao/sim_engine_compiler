"""Independent read-only J05 three-run replay; standard library only.

Does not import author code, invoke SIMLOX, or alter source/native files.
Writes only the adjacent deterministic review JSON.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
AIR = HERE.parent
OUTPUT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
RUNS = {
    "baseline": ("j05-baseline-v101-20261001-01", "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7", 13),
    "global-window": ("j05-global-window-v101-20261001-01", "e08a094aba3d0fe70c63aced459ea73ff582cdf8d1a61b5e52d22ed9bfaada15", 12),
    "system-override": ("j05-system-override-v101-20261001-01", "28ad0e43701d4eba1276a391992b67495506afc9076e80065b583d0932d28f6d", 13),
}
PARENT_SHA = RUNS["baseline"][1]
checks = []


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def parse_native(path):
    source = Path(path).read_text(encoding="utf-8-sig")
    out = []
    quoted = escape = False
    for i, char in enumerate(source):
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
        elif char == "," and re.match(r"\s*[}\]]", source[i + 1:]):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def ck(name, predicate, detail=None):
    checks.append({"name": name, "pass": bool(predicate), "detail": detail})


def tabs(doc, outer="model"):
    return {t["name"]: t for t in doc[outer]["tables"]}


def flat(table):
    return [(instance.get("instance_name", ""), row)
            for instance in table["instances"] for row in instance.get("rows", [])]


def populated(doc):
    return {name: table for name, table in tabs(doc).items() if flat(table)}


def records(report, name):
    t = tabs(report, "report")[name]
    columns = [column["name"] for column in t["columns"]]
    return [dict(zip(columns, row)) for _, row in flat(t)]


def close(a, b, tolerance=1e-6):
    return a is not None and math.isclose(float(a), float(b), abs_tol=tolerance, rel_tol=0)


def share(start, end, left, right):
    return max(0.0, min(end, right) - max(start, left)) / (right - left)


parent_file = AIR / "A01-single-aircraft-single-mission" / "native-input.json"
ck("accepted_A01_parent_fingerprint", digest(parent_file) == PARENT_SHA, digest(parent_file))
contract = parse_json(HERE / "contract.json")
diff = parse_json(HERE / "exact-diff.json")
ck("contract_parent", contract["parent_input_sha256"] == PARENT_SHA)
ck("contract_variant_hashes", contract["input_sha256"] == {key: value[1] for key, value in RUNS.items()})
ck("diff_parent", diff["parent_input_sha256"] == PARENT_SHA)
ck("diff_variant_hashes", [diff[k] for k in ("baseline_input_sha256", "global_window_input_sha256", "system_override_input_sha256")]
   == [v[1] for v in RUNS.values()])
inputs = {variant: parse_json(HERE / f"{variant}-input.json") for variant in RUNS}
ck("baseline_byte_identical", (HERE / "baseline-input.json").read_bytes() == parent_file.read_bytes())
for variant, (_, expected_sha, count) in RUNS.items():
    ck(f"{variant}_frozen_sha", digest(HERE / f"{variant}-input.json") == expected_sha)
    ck(f"{variant}_row_table_count", len(populated(inputs[variant])) == count)
base, glob, override = (tabs(inputs[k]) for k in RUNS)
ck("global_exact_changed_tables", {k for k in base if base[k] != glob[k]}
   == {"ProblemDescription", "Control", "ResultCollection"})
ck("override_exact_changed_tables", {k for k in glob if glob[k] != override[k]}
   == {"ProblemDescription", "ResultCollection"})
ck("global_control_window", flat(glob["Control"])[0][1][1:7] == [36.0, "1", "AIR_BASIC", 0.25, 7.5, 9.0]
   and flat(glob["ResultCollection"]) == [])
ck("system_only_override", flat(override["Control"]) == flat(glob["Control"])
   and flat(override["ResultCollection"]) == [("", ["SYSTEM", 0.5, 0, 36.0, None, None])])

results = {}
for variant, (run_id, expected_sha, count) in RUNS.items():
    run = HERE / "runs" / run_id
    invocation, closure, steps = (parse_json(run / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    source = HERE / f"{variant}-input.json"
    ck(f"{variant}_invocation", invocation["run_id"] == run_id
       and invocation["variant"] == variant and invocation["input_sha256"] == expected_sha
       and invocation["parent_sha256"] == PARENT_SHA
       and invocation["schema"] == "simlox-j05-collection-window-v101-native-candidate/ssh-cli-v1"
       and invocation["case_version"] == "1.0.1-candidate")
    ck(f"{variant}_session_gui_mutex", invocation["execution_mode"] == "ssh_cli_v1"
       and invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck(f"{variant}_five_successful_steps", [step["name"] for step in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(step["status"] == "completed" and step["exit_code"] == 0
               and step["gui_preserved"] for step in steps))
    ck(f"{variant}_closure_invocation", closure["run_id"] == run_id
       and closure["invocation_sha256"] == digest(run / "invocation.json")
       and closure["error"] is None
       and closure["schema"] == "simlox-j05-collection-window-v101-native-closure/v1")
    hashes = invocation["source_hashes_before"]
    ck(f"{variant}_source_fingerprint_seal", hashes == closure["source_hashes_before"]
       == closure["source_hashes_after"] and hashes["input"] == digest(source)
       and hashes["parent"] == PARENT_SHA
       and hashes["contract"] == digest(HERE / "contract.json")
       and hashes["builder"] == digest(HERE / "build.py")
       and hashes["checker"] == digest(HERE / "check_roundtrip.py")
       and hashes["runner_script"] == digest(HERE / "run_native_ssh.ps1"))
    bad = [name for name, seal in closure["raw"].items()
           if not (run / name).is_file() or (run / name).stat().st_size != seal["bytes"]
           or digest(run / name) != seal["sha256"]]
    ck(f"{variant}_twelve_raw_hashes", len(closure["raw"]) == 12 and not bad,
       {"sealed_files": len(closure["raw"]), "bad": bad})
    ck(f"{variant}_run_input_copy", digest(run / "input.json") == expected_sha)
    export = tabs(parse_native(run / "roundtrip-raw.json"))
    source_tables = populated(inputs[variant])
    wrong = [name for name, table in source_tables.items()
             if name not in export or table["columns"] != export[name]["columns"]
             or flat(table) != flat(export[name])]
    ck(f"{variant}_exact_business_roundtrip", len(source_tables) == count and not wrong,
       {"row_tables": count, "differences": wrong})
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{variant}_zero_conversion_errors", "Errors: 0, Warnings: 2, Notes: 0" in run_log
       and "(warning #108)" in run_log and "(warning #126)" in run_log
       and (run / "model.sxo").stat().st_size > 4)
    event_log = (run / "model.log").read_text(encoding="utf-8-sig")
    events = ["Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
              "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>",
              "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:",
              "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>",
              "Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>",
              "Time: 24  Start of day no 1"]
    ck(f"{variant}_full_simulation_events", all(x in event_log for x in events)
       and "mission aborted" not in event_log and " Failed" not in event_log)
    report = parse_native(run / "report-raw.json")
    names = set(tabs(report, "report"))
    ck(f"{variant}_report_table_availability", names ==
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, sorted(names))
    summary = records(report, "ResultSummary")[0]
    ck(f"{variant}_full_horizon_summary", summary["NREP"] == 1 and close(summary["RTIUP"], 36)
       and all(close(summary[k], 1) for k in ("MTMF", "MSTF", "MSUF", "STMF")))
    system, stock = records(report, "SystemResults"), records(report, "StockTotalResults")
    sy_start, sy_end, sy_width = ((0, 36, 0.5) if variant != "global-window" else (7.5, 9, 0.25))
    st_start, st_end, st_width = ((0, 36, 0.5) if variant == "baseline" else (7.5, 9, 0.25))
    ck(f"{variant}_system_window", len(system) == round((sy_end - sy_start) / sy_width)
       and all(close(r["STINT"], sy_start + i * sy_width)
               and close(r["ETINT"], sy_start + (i + 1) * sy_width)
               for i, r in enumerate(system)))
    ck(f"{variant}_stock_window", len(stock) == round((st_end - st_start) / st_width)
       and all(close(r["STINT"], st_start + i * st_width)
               and close(r["ETINT"], st_start + (i + 1) * st_width)
               for i, r in enumerate(stock)))
    sy_bad = []
    for i, row in enumerate(system):
        lo, hi = row["STINT"], row["ETINT"]
        exp = {"NSYRY": share(0, 7, lo, hi) + share(10, 36, lo, hi),
               "NSYMA": share(7, 10, lo, hi), "NSYMR": share(7, 8, lo, hi),
               "NSYMO": share(8, 10, lo, hi), "STACC": share(8, 10, lo, hi),
               "FTMO": share(8, 10, lo, hi), "NFAIL": 0}
        sy_bad.extend((i, key, row.get(key), value) for key, value in exp.items()
                      if not close(row.get(key), value))
    ck(f"{variant}_event_derived_system_bins", not sy_bad, sy_bad[:8])
    stock_bad = [(i, key, row.get(key)) for i, row in enumerate(stock)
                 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")
                 if not close(row.get(key), 0)]
    ck(f"{variant}_zero_stock_ledger", not stock_bad, stock_bad[:8])
    if variant != "global-window":
        ck(f"{variant}_terminal_ready_bin", close(system[-1]["NSYRY"], 1)
           and close(system[-1]["NSYMO"], 0))
    results[variant] = {"run_id": run_id, "closure_sha256": digest(run / "closure.json"),
                        "report_sha256": digest(run / "report-raw.json"),
                        "model_log_sha256": digest(run / "model.log"),
                        "report_tables": sorted(names),
                        "system_bins": len(system), "stock_bins": len(stock),
                        "system_window": [system[0]["STINT"], system[-1]["ETINT"]],
                        "stock_window": [stock[0]["STINT"], stock[-1]["ETINT"]]}

ck("identical_full_event_logs", len({value["model_log_sha256"] for value in results.values()}) == 1)
ck("override_restores_baseline_system_bins", results["baseline"]["system_bins"] ==
   results["system-override"]["system_bins"] == 72
   and results["global-window"]["system_bins"] == 6)
ck("override_leaves_stock_on_global_window", results["global-window"]["stock_bins"] ==
   results["system-override"]["stock_bins"] == 6
   and results["baseline"]["stock_bins"] == 72)

report = {
    "schema": "j05-collection-window-v101-independent-readonly/v1",
    "reviewer": "independent standard-library raw replay; no author script imported",
    "decision": "GO_BOUNDED_SYSTEM_STOCK" if all(c["pass"] for c in checks) else "NO_GO",
    "passed": sum(c["pass"] for c in checks), "total": len(checks),
    "checks": checks, "runs": results,
    "accepted_scope": "The Control global collection window changes exported SYSTEM and STOCK TOTAL bins from 72 half-hours over 0-36 to six quarter-hours over 7.5-9; a SYSTEM ResultCollection row restores only SYSTEM to 72 half-hours. All three identical event logs reach mission success at 10 and simulation day 1 at 24; ResultSummary RTIUP remains 36.",
    "limitations": [
        "Default -jsonreport exported no MissionResults table in any run. Mission per-type collection-window behavior is not directly verified by this evidence.",
        "The global-window report has no terminal SystemResults bin; terminal readiness is evidenced by the native hour-10 event log and full-window control/override reports, not by that truncated report.",
        "Session-0 SSH, queue and GUI preservation are sealed runner attestations, not a live GUI inspection by this reviewer.",
        "One deterministic mission and one seed; profiles, snapshots, other result types and cross-engine behavior remain unverified.",
    ],
}
OUTPUT.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{report['decision']} {report['passed']}/{report['total']}")
print(f"script_sha256={digest(__file__)}")
print(f"report_sha256={digest(OUTPUT)}")
