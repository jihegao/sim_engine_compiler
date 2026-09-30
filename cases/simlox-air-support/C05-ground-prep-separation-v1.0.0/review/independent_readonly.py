"""Independent read-only C05 ground preparation replay; standard library only."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C05-mission-resource-v1.0.0" / "capacity-2-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path):
    # Native JSON-report contains structural trailing commas. Keep all strings
    # untouched and remove only a comma followed by a closing bracket/brace.
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    removed = 0
    for pos, char in enumerate(raw):
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
        elif char == "," and re.match(r"\s*[}\]]", raw[pos + 1 :]):
            removed += 1
        else:
            out.append(char)
    return json.loads("".join(out)), removed


def check(name: str, ok: bool, detail=None):
    entry = {"name": name, "passed": bool(ok)}
    if detail is not None:
        entry["detail"] = detail
    CHECKS.append(entry)


def tables(obj, root="model"):
    seq = obj[root]["tables"]
    names = [table["name"] for table in seq]
    return {table["name"]: table for table in seq}, len(names) == len(set(names))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def at(table, start):
    names = columns(table)
    row = next(row for row in rows(table) if row[names.index("STINT")] == start)
    return dict(zip(names, row))


def stamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def resource_ledger(log):
    pattern = r"Time: ([\d.]+)\s+<(MISSION-CREW|GROUND-TECH) at <BASE-01,0>> (allocated to mission assigned|allocated to maintenance task|deallocated from\s+mission (?:assigned|operation)|deallocated from\s+maintenance task): 1\s+available now: (\d+)"
    result = []
    for when, kind, action, left in re.findall(pattern, log):
        result.append((float(when), kind, "book" if action.startswith("allocated") else "release", int(left)))
    return result


def main():
    contract = load(CASE / "contract.json")
    check("contract and accepted C05 parent", contract["case_id"] == "C05" and contract["variant_id"] == "C05.ground_prep_separation" and contract["parent_case"] == "C05.mission_resource_capacity.1.0.0" and sha(PARENT) == contract["parent_input_sha256"] == "d2ea6e874eff82f1e50f271051010985c28adfba7aab94d2a0a0b343b989e865")
    check("manual fingerprint and cited pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [181, 182, 294, 295, 296, 297, 300, 301, 302, 407, 408, 409, 412, 413, 414])
    check("frozen unpublished contract", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    changed = {"ProblemDescription", "Resource", "ResourceAllocation", "MissionPreparation", "Tasks", "TaskResource"}
    check("frozen six-table change scope", set(contract["changed_tables_only"]) == changed)
    parent, parent_unique = tables(load(PARENT))
    check("parent unique 32-table source", parent_unique and len(parent) == 32)
    source_maps = {}

    for ground in (2, 0):
        variant = f"ground-{ground}"
        prefix = variant + ": "
        run_id = f"c05-ground-{ground}-20260930-01"
        run = CASE / "runs" / run_id
        source_path = CASE / f"{variant}-input.json"
        source, unique = tables(load(source_path))
        source_maps[ground] = source
        check(prefix + "unique 32 source tables", unique and len(source) == 32)
        check(prefix + "source SHA and copied run input", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant])
        delta = {name for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
        check(prefix + "exact six-table parent delta", delta == changed, sorted(delta))
        check(prefix + "all other A03/C05 tables exact", all(parent.get(name) == source.get(name) for name in parent.keys() | source.keys() if name not in changed))
        check(prefix + "description exact", rows(source["ProblemDescription"]) == [[f"C05 distinct ground preparation resource capacity {ground}"]])
        check(prefix + "crew and distinct ground tech source", source["Resource"]["columns"] == parent["Resource"]["columns"] and rows(source["Resource"]) == [*rows(parent["Resource"]), ["GROUND-TECH", "Ground preparation technician", None, None, None, "SPECIAL", None, None]])
        check(prefix + "crew two, ground capacity exact", source["ResourceAllocation"]["columns"] == parent["ResourceAllocation"]["columns"] and rows(source["ResourceAllocation"]) == [*rows(parent["ResourceAllocation"]), ["AIR_BASIC", "GROUND-TECH", "BASE-01", ground, None]])
        check(prefix + "half-hour mission preparation", columns(source["MissionPreparation"]) == ["MTID", "SID", "STID", "DURN", "TID", "DURND", "NOTE"] and rows(source["MissionPreparation"]) == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 0.5, "GROUND-PREP", None, None]])
        check(prefix + "ground preparation task", columns(source["Tasks"]) == ["TID", "DESCR", "TCID", "TLID", "NOTE"] and rows(source["Tasks"]) == [["GROUND-PREP", "Half-hour ground preparation", None, None, None]])
        check(prefix + "only ground tech TaskResource", columns(source["TaskResource"]) == ["TID", "RID", "QTY", "RPROB", "ARID", "ARTF", "ENRMS", "NOTE"] and rows(source["TaskResource"]) == [["GROUND-PREP", "GROUND-TECH", 1, 1, None, None, None, None]])
        check(prefix + "mission crew MissionResource unchanged", source["MissionResource"] == parent["MissionResource"])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "invocation identity/source", invocation["case_id"] == "C05" and invocation["variant"] == variant and invocation["run_id"] == run_id and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(prefix + "session-zero SSH and queue", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(prefix + "GUI identity preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(s["gui_preserved"] is True for s in steps))
        current = {
            "input": run / "input.json", "parent": PARENT,
            "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(invocation["planned_check"]["executable"]),
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        hashes = invocation["source_hashes_before"]
        check(prefix + "source/runtime hashes and frozen before/after", all(path.exists() and sha(path) == hashes[key] for key, path in current.items()) and closure["source_hashes_before"] == hashes == closure["source_hashes_after"] and invocation["contract_sha256"] == hashes["contract"] and invocation["builder_sha256"] == hashes["builder"] and invocation["checker_sha256"] == hashes["checker"] and invocation["runner_script_sha256"] == hashes["runner_script"] and invocation["simlox_exe_sha256"] == hashes["simlox_exe"])
        check(prefix + "sealed invocation and closure", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        actual_raw = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw inventory", actual_raw == set(closure["raw"]))
        for name, metadata in closure["raw"].items():
            path = run / name
            check(prefix + "raw seal " + name, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(prefix + "five successful ordered steps", len(steps) == 5 and [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["error"] is None for s in steps))
        check(prefix + "native step arguments match invocation", [s["name"] for s in steps[:4]] == [p["name"] for p in invocation["planned_commands"]] and [s["arguments"] for s in steps[:4]] == [p["arguments"] for p in invocation["planned_commands"]])
        check(prefix + "step timestamps ordered", all(stamp(s["started_utc"]) <= stamp(s["completed_utc"]) for s in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))
        original, original_unique = tables(load(run / "input.json"))
        roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        check(prefix + "19 row-containing input tables", original_unique and roundtrip_unique and len(populated) == 19)
        for name in sorted(populated):
            check(prefix + "exact roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(prefix + "import/export complete", "Number of forms inserted: 32" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(prefix + "zero conversion errors and expected warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(prefix + "report generation complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(prefix + "one two-aircraft mission ordered", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1)
        check(prefix + "initial two-type resource stock", f"Free resources at: <BASE-01,0> MISSION-CREW 2, GROUND-TECH {ground}" in log)
        check(prefix + "both aircraft reserve mission crew at hour 7", log.count("<MISSION-CREW at <BASE-01,0>> request for: 1 OK") == 2 and log.count("mission allocates system:") == 2 and log.count("Time: 7  <MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1") == 2)
        check(prefix + "ground technician check result", log.count(f"<GROUND-TECH at <BASE-01,0>> request for: 1 {'OK' if ground else 'failed'}") >= 2)
        observed_ledger = resource_ledger(log)
        expected_ledger = ([(7, "MISSION-CREW", "book", 1), (7, "MISSION-CREW", "book", 0), (7, "GROUND-TECH", "book", 1), (7, "GROUND-TECH", "book", 0), (7.5, "GROUND-TECH", "release", 1), (7.5, "GROUND-TECH", "release", 2), (10, "MISSION-CREW", "release", 1), (10, "MISSION-CREW", "release", 2)] if ground == 2 else [(7, "MISSION-CREW", "book", 1), (7, "MISSION-CREW", "book", 0), (7.83333, "MISSION-CREW", "release", 1), (7.83333, "MISSION-CREW", "release", 2)])
        check(prefix + "exact separate resource event ledgers", observed_ledger == expected_ledger, observed_ledger)
        check(prefix + "ledger stock bounds and restoration", all(0 <= free <= (2 if kind == "MISSION-CREW" else ground) for _, kind, _, free in observed_ledger) and [free for _, kind, _, free in observed_ledger if kind == "MISSION-CREW"][-1] == 2 and (not ground or [free for _, kind, _, free in observed_ledger if kind == "GROUND-TECH"][-1] == 2))
        raw_report, removed = report(run / "report-raw.json")
        rt, report_unique = tables(raw_report, "report")
        check(prefix + "six report tables and structural parse", report_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        check(prefix + "72 complete half-hour bins", all(len(rows(rt[name])) == 72 and all(at(rt[name], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for name in ("SystemResults", "StockTotalResults", "ResourceResults")))
        summary = dict(zip(columns(rt["ResultSummary"]), rows(rt["ResultSummary"])[0]))
        success = 1 if ground == 2 else 0
        check(prefix + "mission summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == success)
        total = dict(zip(columns(rt["ResourceResultsTotal"]), rows(rt["ResourceResultsTotal"])[0]))
        expected_assigned_hours = 2 if ground == 2 else 5 / 3
        check(prefix + "aggregate resource total reconciles ledger", total["NR"] == 2 + ground and abs(total["NRMA"] * 36 - expected_assigned_hours) < 1e-4 and abs(total["NRMO"] * 36 - (4 if ground == 2 else 0)) < 1e-4 and abs(total["NRUM"] * 36 - (1 if ground == 2 else 0)) < 1e-4)
        check(prefix + "terminal ready and no resource in use", at(rt["SystemResults"], 35.5)["NSYRY"] == 2 and at(rt["ResourceResults"], 35.5)["NR"] == 2 + ground and all(at(rt["ResourceResults"], 35.5)[key] == 0 for key in ("NRMA", "NRMO", "NRUM", "NRW")))
        if ground == 2:
            check(prefix + "both prep tasks perform half-hour", log.count("starts performing, planned to last for 0.5 hours") == 2 and log.count("Time: 7.5  system preparation task") == 2 and log.count("Time: 7.5  <GROUND-TECH at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
            check(prefix + "ground release precedes crew-held launch", log.index("available now: 2\nTime: 7.5 <BASE-01,0> trig missions") < log.index("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting") and "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1> Resources: <TEACH-AIR-01,0>[MISSION-CREW 1],<TEACH-AIR-01,1>[MISSION-CREW 1]" in log)
            check(prefix + "mission success and crew release at 10", log.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success") == 1 and log.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed") == 1 and log.count("Time: 10  <MISSION-CREW at <BASE-01,0>> deallocated from  mission operation: 1") == 2)
            check(prefix + "report distinguishes prep and operation", at(rt["ResourceResults"], 7)["NRMA"] == 2 and at(rt["ResourceResults"], 7)["NRUM"] == 2 and at(rt["ResourceResults"], 7.5)["NRUM"] == 0 and at(rt["ResourceResults"], 8)["NRMO"] == 2 and at(rt["ResourceResults"], 10)["NRMO"] == 0)
            check(prefix + "system report launch and ready return", at(rt["SystemResults"], 7)["NSYMA"] == 2 and at(rt["SystemResults"], 8)["NSYMO"] == 2 and at(rt["SystemResults"], 10)["NSYRY"] == 2)
        else:
            check(prefix + "both prep tasks wait without ground bookings", log.count("Time: 7  system preparation task") == 2 and "<GROUND-TECH at <BASE-01,0>> allocated" not in log and "starts performing" not in log)
            check(prefix + "cancel and stop both tasks at 7.83333", "Time: 7.83333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and log.count("Time: 7.83333  system preparation task") == 2 and log.count("resource waiting stopped") == 2 and "mission starting" not in log)
            check(prefix + "report temporary crew assignment and task waiting", at(rt["ResourceResults"], 7)["NRMA"] == 2 and at(rt["ResourceResults"], 7)["NRW"] == 2 and abs(at(rt["ResourceResults"], 7.5)["NRMA"] - 4 / 3) < 1e-6 and at(rt["ResourceResults"], 8)["NRMA"] == at(rt["ResourceResults"], 8)["NRW"] == 0)
            check(prefix + "system report ready by hour 8", at(rt["SystemResults"], 7)["NSYMA"] == 2 and at(rt["SystemResults"], 8)["NSYRY"] == 2 and all(at(rt["SystemResults"], i / 2)["NSYMO"] == 0 for i in range(72)))

    pair_delta = {name for name in source_maps[2] if source_maps[2][name] != source_maps[0][name]}
    check("pair differs only by ground capacity and description", pair_delta == {"ProblemDescription", "ResourceAllocation"})
    failures = [entry for entry in CHECKS if not entry["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C05.ground_prep_separation", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_ground_preparation_separation" if not failures else "NO_GO",
        "accepted_scope": "With two GROUND-TECH resources, both preparation tasks use technicians from 7 to 7.5 and release them before the 8-10 mission while two distinct MISSION-CREW resources remain held; mission succeeds and crew releases at 10. With zero technicians, crew is reserved at 7 but both preparation tasks wait; the mission cancels at 7.83333, both tasks stop, crew releases, and both aircraft return ready.",
        "limits": ["One fixed two-aircraft wave, two-hour mission, one site, and ground capacities two/zero only; capacity one and alternate timing/seeds remain unverified.", "No turnaround-preparation or multiple ground-resource types tested.", "ResourceResults aggregates types, so the type-specific allocation/release claim comes from sealed event logs corroborated by aggregate report bins and totals.", "SSH/GUI/queue evidence is replayed from sealed metadata; the reviewer did not observe or rerun native SIMLOX live."],
        "checks": CHECKS,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
