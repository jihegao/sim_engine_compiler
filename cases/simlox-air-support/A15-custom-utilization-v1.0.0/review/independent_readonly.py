"""Independent, read-only replay of A15's two sealed native candidates.

Uses only Python's standard library. It neither imports the case builder/checker
nor executes SIMLOX. The default SIMLOX report has a trailing array comma, so
the report parser removes only structural trailing commas outside JSON strings.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
PARENT = AIR / "A01-single-aircraft-single-mission" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
VARIANTS = {
    "per-hour": "a15-per-hour-20260930-01",
    "per-mission": "a15-per-mission-20260930-01",
}
EXPECTED_PARENT = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
EXPECTED_MANUAL = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
checks: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def j(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_json(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    result = []
    quoted = escaped = False
    removed = 0
    for at, ch in enumerate(text):
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
        elif ch == "," and re.match(r"\s*[}\]]", text[at + 1 :]):
            removed += 1
        else:
            result.append(ch)
    return json.loads("".join(result)), removed


def check(name: str, truth: bool, detail=None):
    entry = {"name": name, "passed": bool(truth)}
    if detail is not None:
        entry["detail"] = detail
    checks.append(entry)


def tables(data, root="model"):
    ts = data[root]["tables"]
    names = [t["name"] for t in ts]
    return {t["name"]: t for t in ts}, len(names) == len(set(names))


def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def body(table):
    return None if table is None else {k: v for k, v in table.items() if k != "name"}


def utc(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = j(CASE / "contract.json")
    diff = j(CASE / "exact-diff.json")
    check("contract identity and A01 parent", contract["case_id"] == "A15" and contract["version"] == "1.0.0" and contract["parent"] == "A01.normal.1.0.0")
    check("frozen A01 parent SHA", sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == EXPECTED_PARENT)
    check("manual SHA and cited printed pages", MANUAL.exists() and sha(MANUAL) == contract["source"]["manual_sha256"] == EXPECTED_MANUAL and contract["source"]["printed_pages"] == [183, 184, 267, 268, 269, 270])
    check("case publication remains pending", contract["publication_state"] == "not_published")

    parent, unique = tables(j(PARENT))
    check("A01 source table names unique", unique and len(parent) == 31)
    source = {}
    reports = {}
    logs = {}
    for variant, run_id in VARIANTS.items():
        prefix = variant + ": "
        run = CASE / "runs" / run_id
        source_path = CASE / (variant + "-input.json")
        input_path = run / "input.json"
        source_doc = j(source_path)
        st, unique = tables(source_doc)
        source[variant] = st
        check(prefix + "unique 32 source tables", unique and len(st) == 32)
        check(prefix + "frozen source SHA and sealed copy", sha(source_path) == sha(input_path) == diff["input_sha256"][variant])
        actual_delta = {key: {"before": body(parent.get(key)), "after": body(st.get(key))} for key in parent.keys() | st.keys() if parent.get(key) != st.get(key)}
        check(prefix + "exact A01 parent delta", actual_delta == diff["parent_differences"][variant], sorted(actual_delta))
        check(prefix + "only intended source tables changed", set(actual_delta) == {"ProblemDescription", "OperationParameter", "MissionTypeUtilization"})
        op = st["OperationParameter"]
        util = st["MissionTypeUtilization"]
        expected_names = ["MTID", "SID", "OPID", "UTIL", "UTILU", "NOTE"]
        expected_util = [60, "1/HOUR"] if variant == "per-hour" else [120, "1/MISSION"]
        check(prefix + "custom operation KM row", [c["name"] for c in op["columns"]] == ["OPID", "DESCR", "NOTE"] and rows(op) == [["KM", "Custom distance in kilometres", None]])
        check(prefix + "MissionTypeUtilization schema", [c["name"] for c in util["columns"]] == expected_names and [c.get("key", False) for c in util["columns"]] == [True, True, True, False, False, False])
        check(prefix + "one intended UTIL/UTILU row", rows(util) == [["BASIC-MISSION", "TEACH-AIR-01", "KM", *expected_util, None]])
        check(prefix + "source report selection excludes MissionOperation", [row[0] for row in rows(st["ResultCollection"])] == ["MISSION", "SYSTEM"])

        inv = j(run / "invocation.json")
        closure = j(run / "closure.json")
        steps = j(run / "steps.json")
        check(prefix + "invocation identity/source", inv["case_id"] == "A15" and inv["variant"] == variant and inv["run_id"] == run_id and inv["input_sha256"] == sha(source_path) and inv["parent_sha256"] == EXPECTED_PARENT)
        check(prefix + "session-0 SSH and mutex", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        gui = inv["gui"]
        check(prefix + "preserved GUI identity", gui["pid"] == 13340 and gui["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        static_paths = {
            "input": input_path,
            "parent": PARENT,
            "contract": CASE / "contract.json",
            "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py",
            "python": Path(inv["planned_check"]["executable"]),
            "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        recorded = inv["source_hashes_before"]
        check(prefix + "source/runtime seals before and after", all(path.exists() and sha(path) == recorded[key] for key, path in static_paths.items()) and closure["source_hashes_before"] == recorded == closure["source_hashes_after"] and inv["contract_sha256"] == recorded["contract"] and inv["builder_sha256"] == recorded["builder"] and inv["checker_sha256"] == recorded["checker"] and inv["runner_script_sha256"] == recorded["runner_script"] and inv["simlox_exe_sha256"] == recorded["simlox_exe"])
        check(prefix + "invocation seal and closure identity", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        actual_raw = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete sealed raw file set", actual_raw == set(closure["raw"]))
        for name, meta in closure["raw"].items():
            path = run / name
            check(prefix + "raw seal " + name, path.exists() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        ordered = ["import", "export", "calc", "jsonreport", "check_import_export"]
        check(prefix + "five successful ordered steps", len(steps) == 5 and [s["name"] for s in steps] == ordered and all(s["status"] == "completed" and s["exit_code"] == 0 and s["error"] is None for s in steps))
        check(prefix + "native step commands match invocation", [s["arguments"] for s in steps[:4]] == [p["arguments"] for p in inv["planned_commands"]] and [s["name"] for s in steps[:4]] == [p["name"] for p in inv["planned_commands"]])
        check(prefix + "step timestamps in sequence", all(utc(s["started_utc"]) <= utc(s["completed_utc"]) for s in steps) and all(utc(steps[i]["completed_utc"]) <= utc(steps[i + 1]["started_utc"]) for i in range(4)))

        imported = j(input_path)
        it, iunique = tables(imported)
        rt, runique = tables(j(run / "roundtrip-raw.json"))
        populated = {name for name, table in it.items() if rows(table)}
        check(prefix + "14 row-containing input tables", iunique and runique and len(populated) == 14)
        for name in sorted(populated):
            check(prefix + "exact populated roundtrip " + name, it[name] == rt.get(name))
        check(prefix + "import/export logs", "Number of forms inserted: 32" in (run / "import.log").read_text(errors="replace") and "Import completed!" in (run / "import.log").read_text(errors="replace") and "Export completed!" in (run / "export.log").read_text(errors="replace"))
        calc_log = (run / "run.log").read_text(errors="replace")
        check(prefix + "zero conversion errors and simulation completed", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc_log and "Starting simulation..." in calc_log and "Saving results ..." in calc_log and "error #" not in calc_log.lower())
        check(prefix + "report generation completed", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))
        logs[variant] = (run / "model.log").read_bytes()
        event = logs[variant].decode("utf-8-sig", errors="replace")
        check(prefix + "single mission 8-10 succeeds", event.count("mission starting, duration: 2") == 1 and "Time: 8 <BASIC-MISSION" in event and event.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success") == 1 and event.count("mission completed:") == 1 and "mission abort" not in event.lower())
        check(prefix + "terminal system ready", "Time: 10 <TEACH-AIR-01,BASE-01,0> System ready" in event and "Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 1" in event)
        report, removed = report_json(run / "report-raw.json")
        reports[variant] = report
        report_tables, unique_report = tables(report, "report")
        check(prefix + "four exported report tables", unique_report and set(report_tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        check(prefix + "MissionOperation.SOACC absent", "MissionOperation" not in report_tables and all("SOACC" not in [c["name"] for c in t["columns"]] for t in report_tables.values()))
        check(prefix + "72 complete half-hour bins", all(len(rows(report_tables[name])) == 72 and all(row[report_tables[name]["columns"].index(next(c for c in report_tables[name]["columns"] if c["name"] == "STINT"))] == i / 2 for i, row in enumerate(rows(report_tables[name]))) for name in ("SystemResults", "StockTotalResults")))
        summary = report_tables["ResultSummary"]
        summary_row = dict(zip((c["name"] for c in summary["columns"]), rows(summary)[0]))
        check(prefix + "one mission success in summary", summary_row["NREP"] == 1 and summary_row["MSTF"] == 1 and summary_row["MSUF"] == 1 and summary_row["RTIUP"] == 36)
        system = report_tables["SystemResults"]
        snames = [c["name"] for c in system["columns"]]
        srows = rows(system)
        check(prefix + "system operation and terminal readiness bins", all(srows[i][snames.index("NSYMO")] == 1 for i in range(16, 20)) and all(srows[i][snames.index("NSYRY")] == 1 for i in range(20, 72)))
        check(prefix + "SIMLOX report trailing comma parsed structurally", removed > 0)

    pair_delta = {key: {"before": body(source["per-hour"].get(key)), "after": body(source["per-mission"].get(key))} for key in source["per-hour"].keys() | source["per-mission"].keys() if source["per-hour"].get(key) != source["per-mission"].get(key)}
    check("exact pairwise source delta", pair_delta == diff["pairwise_differences"] and set(pair_delta) == {"ProblemDescription", "MissionTypeUtilization"})
    check("byte-identical event logs", logs["per-hour"] == logs["per-mission"])
    hr = reports["per-hour"]["report"]["tables"]
    mr = reports["per-mission"]["report"]["tables"]
    check("report tables equal except description", {t["name"]: t for t in hr if t["name"] != "ProblemDescription"} == {t["name"]: t for t in mr if t["name"] != "ProblemDescription"})
    check("distinct expected report descriptions", rows({t["name"]: t for t in hr}["ProblemDescription"]) == [["A15 custom KM mission utilization: per-hour"]] and rows({t["name"]: t for t in mr}["ProblemDescription"]) == [["A15 custom KM mission utilization: per-mission"]])

    failures = [c for c in checks if not c["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "A15",
        "review_date": "2026-09-30",
        "passed": not failures,
        "check_count": len(checks),
        "passed_count": len(checks) - len(failures),
        "failures": failures,
        "decision": "GO_bounded_source_acceptance_and_observable_mission_only" if not failures else "NO_GO",
        "accepted_scope": "These two sealed CLI runs accept and roundtrip custom KM OperationParameter and MissionTypeUtilization source; both convert with zero errors, produce byte-identical event logs, equal non-description report tables, and one successful 8-10 mission ending ready.",
        "rejected_claims": [
            "Neither default JSON report selects MissionOperation; SOACC is absent. Do not claim 120 accomplished custom units or equality of custom exposure from these runs.",
            "The 60 1/HOUR and 120 1/MISSION values are source settings only; one full mission cannot establish behavior for partial missions, failures, other seeds, or fleet aggregation.",
        ],
        "manual_observation": "The SHA-pinned SIMLOX 2017 manual (printed pp. 183-184 and 267-270) describes custom operation parameters, MissionTypeUtilization time/mission rates, and MissionOperation.SOACC as the operation result. Its substantive text was inspected separately; this standard-library replay verifies the manual's byte hash.",
        "checks": checks,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
