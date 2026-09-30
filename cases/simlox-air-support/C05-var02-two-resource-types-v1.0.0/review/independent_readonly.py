"""Independent read-only replay of C05.var02 sealed native evidence.

Standard library only. Does not import author code, execute SIMLOX, or edit raw runs.
"""

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
CAPACITIES = (2, 0)
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
    # Native SIMLOX reports have a structural trailing comma; remove only those
    # outside strings, preserving all other report content.
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    removed = 0
    for pos, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == "," and re.match(r"\s*[}\]]", raw[pos + 1 :]):
            removed += 1
        else:
            out.append(ch)
    return json.loads("".join(out)), removed


def check(name: str, ok: bool, detail=None):
    item = {"name": name, "passed": bool(ok)}
    if detail is not None:
        item["detail"] = detail
    checks.append(item)


def tables(obj, root="model"):
    arr = obj[root]["tables"]
    names = [t["name"] for t in arr]
    return {t["name"]: t for t in arr}, len(names) == len(set(names))


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def cols(table):
    return [c["name"] for c in table["columns"]]


def at(table, t):
    names = cols(table)
    return dict(zip(names, next(row for row in rows(table) if row[names.index("STINT")] == t)))


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ledger(text):
    pattern = r"Time: ([\d.]+)\s+<(MISSION-CREW|MISSION-RADIO) at <BASE-01,0>> (allocated to mission assigned|deallocated from\s+mission operation): 1\s+available now: (\d+)"
    return [(float(t), kind, "book" if verb.startswith("allocated") else "release", int(left)) for t, kind, verb, left in re.findall(pattern, text)]


def main():
    contract = load(CASE / "contract.json")
    check("contract identity and accepted C05 parent SHA", contract["case_id"] == "C05" and contract["variant_id"] == "C05.var02" and contract["parent_case"] == "C05.mission_resource_capacity.1.0.0" and sha(PARENT) == contract["parent_input_sha256"] == "d2ea6e874eff82f1e50f271051010985c28adfba7aab94d2a0a0b343b989e865")
    check("manual fingerprint and printed pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [300, 301, 302, 412, 413, 414])
    check("frozen unpublished contract", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    changed = {"ProblemDescription", "Resource", "ResourceAllocation", "MissionResource"}
    check("frozen changed table list", set(contract["changed_tables_only"]) == changed)
    parent, unique = tables(load(PARENT))
    check("parent unique 32 tables", unique and len(parent) == 32)
    source_maps = {}

    for radio in CAPACITIES:
        variant = f"radio-{radio}"
        prefix = variant + ": "
        run_id = f"c05-var02-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        source_path = CASE / f"{variant}-input.json"
        source, unique = tables(load(source_path))
        source_maps[radio] = source
        check(prefix + "unique 32 source tables", unique and len(source) == 32)
        check(prefix + "source and copied input SHA", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant])
        actual_diff = {name for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
        check(prefix + "exact four-table parent delta", actual_diff == changed, sorted(actual_diff))
        check(prefix + "all other parent tables exact", all(parent.get(name) == source.get(name) for name in parent.keys() | source.keys() if name not in changed))
        check(prefix + "description row", rows(source["ProblemDescription"]) == [[f"C05.var02 two mission resource types; radio capacity {radio}"]])
        expected_radio = ["MISSION-RADIO", "Distinct mission radio resource", None, None, None, "SPECIAL", None, None]
        check(prefix + "two distinct special resources", source["Resource"]["columns"] == parent["Resource"]["columns"] and rows(source["Resource"]) == [*rows(parent["Resource"]), expected_radio])
        check(prefix + "crew 2 and radio capacity at base", source["ResourceAllocation"]["columns"] == parent["ResourceAllocation"]["columns"] and rows(source["ResourceAllocation"]) == [*rows(parent["ResourceAllocation"]), ["AIR_BASIC", "MISSION-RADIO", "BASE-01", radio, None]])
        check(prefix + "one of each type per aircraft", source["MissionResource"]["columns"] == parent["MissionResource"]["columns"] and rows(source["MissionResource"]) == [*rows(parent["MissionResource"]), ["BASIC-MISSION", "TEACH-AIR-01", "MISSION-RADIO", 1, None]])
        check(prefix + "no ground preparation resource demand", not rows(source["MissionPreparation"]) and not rows(source["TaskResource"]))

        inv = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "invocation identity/source", inv["case_id"] == "C05" and inv["variant"] == variant and inv["run_id"] == run_id and inv["input_sha256"] == sha(source_path) and inv["parent_sha256"] == sha(PARENT))
        check(prefix + "SSH session 0 and queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(prefix + "GUI identity preserved", inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] > 0 and all(s["gui_preserved"] is True for s in steps))
        paths = {
            "input": run / "input.json", "parent": PARENT,
            "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(inv["planned_check"]["executable"]),
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        sealed = inv["source_hashes_before"]
        check(prefix + "current source/runtime seals and unchanged before/after", all(path.exists() and sha(path) == sealed[key] for key, path in paths.items()) and closure["source_hashes_before"] == sealed == closure["source_hashes_after"] and inv["contract_sha256"] == sealed["contract"] and inv["builder_sha256"] == sealed["builder"] and inv["checker_sha256"] == sealed["checker"] and inv["runner_script_sha256"] == sealed["runner_script"] and inv["simlox_exe_sha256"] == sealed["simlox_exe"])
        check(prefix + "invocation and closure seal", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        files = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw seal inventory", files == set(closure["raw"]))
        for filename, meta in closure["raw"].items():
            p = run / filename
            check(prefix + "raw seal " + filename, p.exists() and p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"])
        check(prefix + "five successful ordered steps", len(steps) == 5 and [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["error"] is None for s in steps))
        check(prefix + "native command arguments match invocation", [s["name"] for s in steps[:4]] == [s["name"] for s in inv["planned_commands"]] and [s["arguments"] for s in steps[:4]] == [s["arguments"] for s in inv["planned_commands"]])
        check(prefix + "ordered step timestamps", all(stamp(s["started_utc"]) <= stamp(s["completed_utc"]) for s in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

        original, original_unique = tables(load(run / "input.json"))
        roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        check(prefix + "16 row-containing input tables", original_unique and roundtrip_unique and len(populated) == 16)
        for name in sorted(populated):
            check(prefix + "exact roundtrip " + name, original[name] == roundtrip.get(name))
        import_log = (run / "import.log").read_text(errors="replace")
        export_log = (run / "export.log").read_text(errors="replace")
        calc_log = (run / "run.log").read_text(errors="replace")
        check(prefix + "import and export complete", "Number of forms inserted: 32" in import_log and "Import completed!" in import_log and "Export completed!" in export_log)
        check(prefix + "zero conversion errors, two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc_log and calc_log.count("warning #108") == 1 and calc_log.count("warning #126") == 1 and "error #" not in calc_log.lower() and "Starting simulation..." in calc_log and "Saving results ..." in calc_log)
        check(prefix + "report generation complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(prefix + "single two-aircraft wave ordered", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1)
        check(prefix + "initial two-type stock", f"Free resources at: <BASE-01,0> MISSION-CREW 2, MISSION-RADIO {radio}" in log)
        check(prefix + "both crew checks OK", log.count("<MISSION-CREW at <BASE-01,0>> request for: 1 OK") == 2)
        check(prefix + "radio check outcome", log.count(f"<MISSION-RADIO at <BASE-01,0>> request for: 1 {'OK' if radio else 'failed'}") == 2)
        observed = ledger(log)
        expected = ([(7, "MISSION-CREW", "book", 1), (7, "MISSION-RADIO", "book", 1), (7, "MISSION-CREW", "book", 0), (7, "MISSION-RADIO", "book", 0), (10, "MISSION-CREW", "release", 1), (10, "MISSION-RADIO", "release", 1), (10, "MISSION-CREW", "release", 2), (10, "MISSION-RADIO", "release", 2)] if radio == 2 else [])
        check(prefix + "exact per-type allocation/release ledger", observed == expected, observed)
        check(prefix + "per-type stock stays bounded and returns", all(0 <= free <= 2 for _, kind, _, free in observed if kind == "MISSION-CREW") and all(0 <= free <= radio for _, kind, _, free in observed if kind == "MISSION-RADIO") and (not observed or observed[-2][3:] == (2,) and observed[-1][3:] == (radio,)))
        report, removed = load_report(run / "report-raw.json")
        rt, unique_report = tables(report, "report")
        check(prefix + "six report tables and structural parse", unique_report and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        check(prefix + "72 complete half-hour bins", all(len(rows(rt[name])) == 72 and all(at(rt[name], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for name in ("SystemResults", "StockTotalResults", "ResourceResults")))
        summary = dict(zip(cols(rt["ResultSummary"]), rows(rt["ResultSummary"])[0]))
        mission_count = 1 if radio == 2 else 0
        check(prefix + "mission summary metrics", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == mission_count)
        total = dict(zip(cols(rt["ResourceResultsTotal"]), rows(rt["ResourceResultsTotal"])[0]))
        check(prefix + "resource total reconciles 36-hour event ledger", total["NR"] == 2 + radio and abs(total["NRMA"] * 36 - (4 if radio == 2 else 0)) < 1e-6 and abs(total["NRMO"] * 36 - (8 if radio == 2 else 0)) < 1e-6)
        check(prefix + "terminal inventory and two ready aircraft", at(rt["SystemResults"], 35.5)["NSYRY"] == 2 and at(rt["ResourceResults"], 35.5)["NR"] == 2 + radio and at(rt["ResourceResults"], 35.5)["NRMA"] == at(rt["ResourceResults"], 35.5)["NRMO"] == 0)
        if radio == 2:
            check(prefix + "both aircraft book both resources", log.count("Time: 7 <TEACH-AIR-01,0> books resources") == 1 and log.count("Time: 7 <TEACH-AIR-01,1> books resources") == 1 and log.count("mission allocates system:") == 2)
            check(prefix + "8-10 two-aircraft mission and success", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1> Resources: <TEACH-AIR-01,0>[MISSION-CREW 1][MISSION-RADIO 1],<TEACH-AIR-01,1>[MISSION-CREW 1][MISSION-RADIO 1]" in log and log.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success") == 1 and log.count("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed") == 1)
            check(prefix + "resource report holds four then releases", at(rt["ResourceResults"], 7)["NRMA"] == 4 and at(rt["ResourceResults"], 8)["NRMO"] == 4 and at(rt["ResourceResults"], 9.5)["NRMO"] == 4 and at(rt["ResourceResults"], 10)["NRMO"] == 0)
            check(prefix + "system report launch and recovery", at(rt["SystemResults"], 7)["NSYMA"] == 2 and at(rt["SystemResults"], 8)["NSYMO"] == 2 and at(rt["SystemResults"], 10)["NSYRY"] == 2)
        else:
            check(prefix + "radio failure blocks bookings of both types", log.count("request for: 1 failed") == 2 and "books resources" not in log and "allocated to mission assigned" not in log and "mission allocates system:" not in log)
            check(prefix + "deadline cancellation, no launch", "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission waiting:  timeout at 8.33333" in log and "Time: 8.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and "mission starting" not in log)
            check(prefix + "report has no assigned or operating resources", all(at(rt["ResourceResults"], i / 2)["NRMA"] == at(rt["ResourceResults"], i / 2)["NRMO"] == 0 for i in range(72)) and all(at(rt["SystemResults"], i / 2)["NSYRY"] == 2 for i in range(72)))

    pair_diff = {name for name in source_maps[2] if source_maps[2][name] != source_maps[0][name]}
    check("pair differs only in radio capacity and description", pair_diff == {"ProblemDescription", "ResourceAllocation"})
    failures = [item for item in checks if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C05.var02", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(checks), "passed_count": len(checks) - len(failures),
        "failures": failures,
        "decision": "GO_bounded_two_type_resource_observation" if not failures else "NO_GO",
        "accepted_scope": "In this fixed two-aircraft, two-hour mission, each aircraft requires one MISSION-CREW and one MISSION-RADIO. With two radios, both aircraft book both types at hour 7, launch at 8, succeed and complete at 10, and release both types. With zero radios, both crew checks pass but both radio checks fail before any booking, and the mission cancels at 8.33333. Both runs return two ready aircraft and their initial resource inventory.",
        "limits": ["One fixed seed, one formation, one site and two extreme radio capacities only; radio capacity one and mixed availability remain unverified.", "The catalog one-hour mission, separate preparation resource, alternate timing and seeds remain unverified.", "ResourceResults is aggregated over types, so type-specific bookings and release are established by the sealed event log, corroborated by aggregate report totals.", "SSH session, GUI continuity, and queue evidence are replayed from sealed records; this reviewer did not observe a live native run."],
        "checks": checks,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
