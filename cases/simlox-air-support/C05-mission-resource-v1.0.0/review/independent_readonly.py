"""Independent read-only replay of the three C05 native candidates.

Standard library only: no author code imports, no native execution, no raw writes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
CAPACITIES = (2, 1, 0)
checks: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    # SIMLOX writes one structural trailing comma in its otherwise JSON report.
    text = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    removed = 0
    for index, char in enumerate(text):
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
        elif char == "," and re.match(r"\s*[}\]]", text[index + 1 :]):
            removed += 1
        else:
            out.append(char)
    return json.loads("".join(out)), removed


def check(name: str, ok: bool, detail=None):
    item = {"name": name, "passed": bool(ok)}
    if detail is not None:
        item["detail"] = detail
    checks.append(item)


def table_map(data, root="model"):
    arr = data[root]["tables"]
    names = [t["name"] for t in arr]
    return {t["name"]: t for t in arr}, len(names) == len(set(names))


def rows(table):
    return [r for instance in table["instances"] for r in instance["rows"]]


def cols(table):
    return [c["name"] for c in table["columns"]]


def at(table, start):
    names = cols(table)
    return dict(zip(names, next(row for row in rows(table) if row[names.index("STINT")] == start)))


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ledger(log: str):
    pattern = r"Time: ([\d.]+)\s+<MISSION-CREW at <BASE-01,0>> (allocated to mission assigned|deallocated from\s+mission (?:assigned|operation)): 1\s+available now: (\d+)"
    return [(float(t), "allocate" if a.startswith("allocated") else "release", int(left)) for t, a, left in re.findall(pattern, log)]


def main():
    contract = load(CASE / "contract.json")
    check("contract identity and frozen A03 parent", contract["case_id"] == "C05" and contract["parent_case"] == "A03@1.0.1" and sha(PARENT) == contract["parent_input_sha256"] == "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4")
    check("frozen manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_pages"] == [300, 301, 302, 412, 413, 414])
    check("contract remains unpublished candidate", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    check("frozen changed-table set", set(contract["changed_tables_only"]) == {"ProblemDescription", "Resource", "ResourceAllocation", "MissionResource"})
    parent, unique = table_map(load(PARENT))
    check("A03 parent unique source tables", unique and len(parent) == 31)

    sources = {}
    for capacity in CAPACITIES:
        variant = f"capacity-{capacity}"
        prefix = variant + ": "
        run_id = f"c05-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        source_path = CASE / (variant + "-input.json")
        source_doc = load(source_path)
        source, unique = table_map(source_doc)
        sources[capacity] = source
        check(prefix + "unique 32 source tables", unique and len(source) == 32)
        check(prefix + "source SHA and copied input", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant])
        delta = {name for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
        check(prefix + "exact parent changed-table set", delta == set(contract["changed_tables_only"]), sorted(delta))
        check(prefix + "all unchanged A03 tables exact", all(parent.get(name) == source.get(name) for name in parent.keys() | source.keys() if name not in delta))
        check(prefix + "problem description", rows(source["ProblemDescription"]) == [[f"C05 mission crew capacity {capacity}; two-aircraft A03 wave"]])
        check(prefix + "special mission crew defined", cols(source["Resource"]) == ["RID", "DESCR", "PRICE", "SUSTC", "TLLEN", "TYPE", "MUTILF", "NOTE"] and rows(source["Resource"]) == [["MISSION-CREW", "Mission crew held during flight", None, None, None, "SPECIAL", None, None]])
        check(prefix + "resource schema preserved from A03", source["Resource"]["columns"] == parent["Resource"]["columns"])
        check(prefix + "allocation capacity at base", cols(source["ResourceAllocation"]) == ["POINT", "RID", "STID", "RQTY", "NOTE"] and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "MISSION-CREW", "BASE-01", capacity, None]])
        check(prefix + "allocation schema preserved from A03", source["ResourceAllocation"]["columns"] == parent["ResourceAllocation"]["columns"])
        check(prefix + "one crew per mission aircraft", cols(source["MissionResource"]) == ["MTID", "SID", "RID", "QTY", "NOTE"] and rows(source["MissionResource"]) == [["BASIC-MISSION", "TEACH-AIR-01", "MISSION-CREW", 1, None]])
        check(prefix + "MissionResource key and quantity schema", source["MissionResource"]["columns"] == [{"datatype": "string", "key": True, "name": "MTID"}, {"datatype": "string", "key": True, "name": "SID"}, {"datatype": "string", "key": True, "name": "RID"}, {"datatype": "integer", "name": "QTY"}, {"datatype": "string", "name": "NOTE"}])
        check(prefix + "no preparation resource table demand", not rows(source["MissionPreparation"]) and not rows(source["TaskResource"]))
        mission_row = dict(zip(cols(source["MissionType"]), rows(source["MissionType"])[0]))
        check(prefix + "A03 two-aircraft two-hour mission retained", mission_row["MTID"] == "BASIC-MISSION" and mission_row["NOS"] == mission_row["MNOS"] == 2 and mission_row["DURN"] == 2)

        inv = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "native invocation identity", inv["case_id"] == "C05" and inv["variant"] == variant and inv["run_id"] == run_id and inv["input_sha256"] == sha(source_path) and inv["parent_sha256"] == sha(PARENT))
        check(prefix + "SSH session and mutex", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(prefix + "GUI identity preserved", inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        static = {
            "input": run / "input.json", "parent": PARENT,
            "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(inv["planned_check"]["executable"]),
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        recorded = inv["source_hashes_before"]
        check(prefix + "source and runtime seals before/after", all(path.exists() and sha(path) == recorded[key] for key, path in static.items()) and closure["source_hashes_before"] == recorded == closure["source_hashes_after"] and inv["contract_sha256"] == recorded["contract"] and inv["builder_sha256"] == recorded["builder"] and inv["checker_sha256"] == recorded["checker"] and inv["runner_script_sha256"] == recorded["runner_script"] and inv["simlox_exe_sha256"] == recorded["simlox_exe"])
        check(prefix + "invocation/closure seal", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        actual = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw seal inventory", actual == set(closure["raw"]))
        for filename, meta in closure["raw"].items():
            p = run / filename
            check(prefix + "raw seal " + filename, p.exists() and p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"])
        check(prefix + "five successful ordered steps", len(steps) == 5 and [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["error"] is None for s in steps))
        check(prefix + "native commands match invocation", [s["name"] for s in steps[:4]] == [s["name"] for s in inv["planned_commands"]] and [s["arguments"] for s in steps[:4]] == [s["arguments"] for s in inv["planned_commands"]])
        check(prefix + "step timestamps ordered", all(stamp(s["started_utc"]) <= stamp(s["completed_utc"]) for s in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

        original, original_unique = table_map(load(run / "input.json"))
        roundtrip, roundtrip_unique = table_map(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        check(prefix + "16 row-containing input tables", original_unique and roundtrip_unique and len(populated) == 16)
        for name in sorted(populated):
            check(prefix + "exact roundtrip " + name, original[name] == roundtrip.get(name))
        import_log = (run / "import.log").read_text(errors="replace")
        export_log = (run / "export.log").read_text(errors="replace")
        calc_log = (run / "run.log").read_text(errors="replace")
        check(prefix + "import/export complete", "Number of forms inserted: 32" in import_log and "Import completed!" in import_log and "Export completed!" in export_log)
        check(prefix + "conversion errors zero; exact known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc_log and calc_log.count("warning #108") == 1 and calc_log.count("warning #126") == 1 and "error #" not in calc_log.lower() and "Starting simulation..." in calc_log and "Saving results ..." in calc_log)
        check(prefix + "report generated", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(prefix + "ordered two-aircraft wave", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1)
        check(prefix + "initial crew shift stock", f"Free resources at: <BASE-01,0> MISSION-CREW {capacity}" in log)
        expected_ledger = {
            2: [(7, "allocate", 1), (7, "allocate", 0), (10, "release", 1), (10, "release", 2)],
            1: [(7, "allocate", 0), (8.33333, "release", 1)],
            0: [],
        }[capacity]
        observed_ledger = ledger(log)
        check(prefix + "exact crew allocation/release ledger", observed_ledger == expected_ledger, observed_ledger)
        check(prefix + "ledger nonnegative and restored", all(0 <= free <= capacity for _, _, free in observed_ledger) and (observed_ledger[-1][2] if observed_ledger else capacity) == capacity)
        report, removed = load_report(run / "report-raw.json")
        rt, rt_unique = table_map(report, "report")
        check(prefix + "six report tables", rt_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
        check(prefix + "72 complete half-hour result bins", all(len(rows(rt[name])) == 72 and all(at(rt[name], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for name in ("SystemResults", "StockTotalResults", "ResourceResults")))
        summary = dict(zip(cols(rt["ResultSummary"]), rows(rt["ResultSummary"])[0]))
        expected_success = 1 if capacity == 2 else 0
        check(prefix + "mission summary metrics", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MSTF"] == expected_success and summary["MSUF"] == expected_success and summary["MTMF"] == expected_success)
        check(prefix + "terminal systems and crew capacity", at(rt["SystemResults"], 35.5)["NSYRY"] == 2 and at(rt["ResourceResults"], 35.5)["NR"] == capacity and at(rt["ResourceResults"], 35.5)["NRMA"] == 0 and at(rt["ResourceResults"], 35.5)["NRMO"] == 0)
        total_resource = dict(zip(cols(rt["ResourceResultsTotal"]), rows(rt["ResourceResultsTotal"])[0]))
        expected_assigned_hours = {2: 2.0, 1: 4 / 3, 0: 0}[capacity]
        expected_operating_hours = 4.0 if capacity == 2 else 0.0
        check(prefix + "resource total reconciles 36-hour ledger", total_resource["NR"] == capacity and abs(total_resource["NRMA"] * 36 - expected_assigned_hours) < 1e-6 and abs(total_resource["NRMO"] * 36 - expected_operating_hours) < 1e-6)
        check(prefix + "report structural comma accounted for", removed > 0)

        allocated = log.count("mission allocates system:")
        failed_tests = log.count("request for: 1 failed")
        if capacity == 2:
            check(prefix + "two aircraft assigned and launch at 8", allocated == 2 and failed_tests == 0 and "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1> Resources: <TEACH-AIR-01,0>[MISSION-CREW 1],<TEACH-AIR-01,1>[MISSION-CREW 1]" in log)
            check(prefix + "success/completion at 10 and two releases", log.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success") == 1 and log.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed") == 1 and log.count("deallocated from  mission operation: 1") == 2)
            check(prefix + "resource report assigned then operational", at(rt["ResourceResults"], 7)["NRMA"] == 2 and at(rt["ResourceResults"], 8)["NRMO"] == 2 and at(rt["ResourceResults"], 9.5)["NRMO"] == 2 and at(rt["ResourceResults"], 10)["NRMO"] == 0)
            check(prefix + "system report launch and recovery", at(rt["SystemResults"], 7)["NSYMA"] == 2 and at(rt["SystemResults"], 8)["NSYMO"] == 2 and at(rt["SystemResults"], 10)["NSYRY"] == 2)
        elif capacity == 1:
            check(prefix + "partial reservation at 7 rejects atomicity hypothesis", allocated == 1 and failed_tests == 2 and "Time: 7 <TEACH-AIR-01,0> books resources" in log and "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>" in log)
            check(prefix + "second aircraft blocked; cancelled and released", "Time: 7 <TEACH-AIR-01,1> system resource availability test" in log and "Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and "Time: 8.33333 <TEACH-AIR-01,0> frees resources" in log and "mission starting" not in log)
            check(prefix + "report records temporary reservation", at(rt["ResourceResults"], 7)["NRMA"] == 1 and abs(at(rt["ResourceResults"], 8)["NRMA"] - 2 / 3) < 1e-6 and at(rt["ResourceResults"], 8.5)["NRMA"] == 0 and all(at(rt["ResourceResults"], i / 2)["NRMO"] == 0 for i in range(72)))
            check(prefix + "system report temporary assignment", at(rt["SystemResults"], 7)["NSYMA"] == 1 and abs(at(rt["SystemResults"], 8)["NSYMA"] - 2 / 3) < 1e-6 and at(rt["SystemResults"], 8.5)["NSYRY"] == 2)
        else:
            check(prefix + "no assignments and two failed tests", allocated == 0 and failed_tests == 2 and "mission starting" not in log and "allocated to mission assigned" not in log)
            check(prefix + "cancellation at timeout", "Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission waiting:  timeout at 8.33333" in log)
            check(prefix + "report has no crew or assigned/operating aircraft", all(at(rt["ResourceResults"], i / 2)["NRMA"] == at(rt["ResourceResults"], i / 2)["NRMO"] == 0 for i in range(72)) and all(at(rt["SystemResults"], i / 2)["NSYRY"] == 2 for i in range(72)))

    check("only capacity and description differ within three-source pair", all(sources[2][n] == sources[1][n] == sources[0][n] for n in sources[2] if n not in {"ProblemDescription", "ResourceAllocation"}))
    failures = [item for item in checks if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C05", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(checks),
        "passed_count": len(checks) - len(failures), "failures": failures,
        "decision": "GO_bounded_three_capacity_native_observation" if not failures else "NO_GO",
        "accepted_scope": "In this fixed A03 two-aircraft, two-hour mission with one special crew required per aircraft, capacity 2 reserves two at hour 7, launches at 8, succeeds at 10, and releases both. Capacity 1 reserves one aircraft/crew at hour 7 while the second fails its check; cancellation at 8.33333 releases the reservation. Capacity 0 reserves none and cancels at 8.33333. All variants return to two ready aircraft and initial free crew capacity.",
        "rejected_hypothesis": "The frozen pre-run capacity-1 claim that the two-aircraft formation cannot be partially assigned before all mission-resource demand is available is false in the sealed native evidence.",
        "limits": ["One fixed seed, one two-aircraft wave, one crew type and site, and the A03 two-hour mission only.", "The catalog one-hour mission, preparation resource interactions, multiple mission resource types, remote support, and alternate timing/seeds remain unverified.", "Session-0 SSH and GUI continuity are replayed from sealed metadata; the reviewer did not run or observe native SIMLOX live."],
        "checks": checks,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
