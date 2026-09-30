"""Independent, read-only replay of the C10.var04 native evidence."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "C10-resource-failure-v1.0.0"
FIXED = PARENT / "runs/c10-oper-no-spare-20260930-01"
CHILD = CASE / "runs/c10-exponential-two-crew-20260930-01"
PARENT_SHA = "c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b"
CHILD_SHA = "24c8d3c6c16b9f5354063673c24b3dbccdc84329627ab870aba695ce0c485865"
PARENT_CLOSURE_SHA = "3c5f222d1a09116098b5001426856ab02495002c46b1f1e4fa4099fc184ea650"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, condition: bool, detail: object = None) -> None:
    row = {"name": name, "passed": bool(condition)}
    if detail is not None:
        row["detail"] = detail
    CHECKS.append(row)


def native_json(path: Path) -> dict:
    """Remove native trailing commas from a parser copy, preserving raw bytes."""
    source = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(source)
    except json.JSONDecodeError:
        output: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(source):
            if quoted:
                output.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                output.append(char)
            elif char == "," and source[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                output.append(char)
        return json.loads("".join(output))


def tables(document: dict, key: str) -> dict:
    result: dict = {}
    for table in document[key]["tables"]:
        name = table["name"]
        if name in result:
            raise ValueError(f"duplicate table {name}")
        result[name] = table
    return result


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def event_time(log: str, pattern: str) -> float:
    found = re.findall(pattern, log, flags=re.MULTILINE)
    if len(found) != 1:
        raise ValueError(f"expected one event for {pattern!r}; got {found!r}")
    return float(found[0])


def overlap(start: float, end: float, lower: float, upper: float) -> float:
    return max(0.0, min(end, upper) - max(start, lower))


def close(value: float | None, expected: float, tolerance: float = 3e-5) -> bool:
    return value is not None and abs(value - expected) <= tolerance


def seal(run: Path, tag: str) -> tuple[dict, dict]:
    invocation = native_json(run / "invocation.json")
    closure = native_json(run / "closure.json")
    check(f"{tag}: closure binds invocation", closure["invocation_sha256"] == sha(run / "invocation.json"))
    check(f"{tag}: source hashes unchanged", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    raw = closure["raw"]
    check(f"{tag}: complete raw inventory", set(raw) | {"invocation.json", "closure.json"} == {p.name for p in run.iterdir() if p.is_file()} and len(raw) == 12)
    for name, details in sorted(raw.items()):
        path = run / name
        check(f"{tag}: raw seal {name}", path.is_file() and path.stat().st_size == details["bytes"] and sha(path) == details["sha256"])
    check(f"{tag}: no runner error", closure["error"] is None)
    steps = native_json(run / "steps.json")
    check(f"{tag}: five ordered guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps))
    check(f"{tag}: session-0 SSH, mutex and GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    check(f"{tag}: actual source input bound", sha(run / "input.json") == invocation["input_sha256"] == closure["source_hashes_before"]["input"])
    return invocation, closure


def replay_report(run: Path, tag: str, failure: float, repair: float, resume: float, prep_end: float, mission_end: float) -> dict:
    report = tables(native_json(run / "report-raw.json"), "report")
    check(f"{tag}: six report tables", set(report) == {"ProblemDescription", "ResultSummary", "ResourceResults", "ResourceResultsTotal", "SystemResults", "StockTotalResults"})
    rr = records(report["ResourceResults"])
    sy = records(report["SystemResults"])
    st = records(report["StockTotalResults"])
    for name, data in (("resource", rr), ("system", sy), ("stock", st)):
        check(f"{tag}: {name} 72 contiguous half-hour bins", len(data) == 72 and all(close(r["STINT"], i / 2, 1e-8) and close(r["ETINT"], (i + 1) / 2, 1e-8) for i, r in enumerate(data)))
    for field, intervals in {
        "NRF": [(failure, repair)],
        "NRW": [(failure, resume)],
        "NRUM": [(7.5, failure), (resume, prep_end), (7.5, 8.0)],
    }.items():
        expected = [sum(overlap(a, b, r["STINT"], r["ETINT"]) for a, b in intervals) / 0.5 for r in rr]
        check(f"{tag}: event-derived 72-bin {field}", all(close(r[field], x) for r, x in zip(rr, expected)))
    check(f"{tag}: event-derived 72-bin NRA", all(close(r["NRA"], 2 - r["NRF"]) for r in rr))
    expected_prep = [(7.5, prep_end), (7.5, 8.0)]
    expected_mission = [(prep_end, mission_end)] * 2
    expected_ready = [(0, 7.5), (mission_end, 36)] * 2
    for field, intervals in (("NSYMP", expected_prep), ("NSYMO", expected_mission), ("NSYRY", expected_ready)):
        expected = [sum(overlap(a, b, r["STINT"], r["ETINT"]) for a, b in intervals) / 0.5 for r in sy]
        check(f"{tag}: event-derived 72-bin {field}", all(close(r[field], x) for r, x in zip(sy, expected)))
    check(f"{tag}: zero system failures and terminal readiness", all(r["NFAIL"] == 0 for r in sy) and sy[-1]["NSYRY"] == 2 and sy[-1]["NSYMO"] == 0 and sy[-1]["NSYMP"] == 0)
    check(f"{tag}: zero stock movement and backorders", all(all(r[k] == 0 for k in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for r in st))
    summary = records(report["ResultSummary"])[0]
    check(f"{tag}: one successful formation and 36h summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and all(summary[k] == 1 for k in ("MTMF", "MSTF", "MSUF", "STMF")))
    totals = records(report["ResourceResultsTotal"])[0]
    integrals = {field: sum((r["ETINT"] - r["STINT"]) * (r[field] or 0) for r in rr) for field in ("NRUM", "NRF", "NRW")}
    check(f"{tag}: resource total matches bins", all(close(totals[k] * 36, v) for k, v in integrals.items()))
    check(f"{tag}: one crew-hour work, failed duration, waiting duration", close(integrals["NRUM"], 1) and close(integrals["NRF"], repair - failure) and close(integrals["NRW"], resume - failure))
    check(f"{tag}: terminal resources ready", rr[-1]["NR"] == 2 and rr[-1]["NRA"] == 2 and rr[-1]["NRF"] == 0 and rr[-1]["NRUM"] == 0 and rr[-1]["NRW"] == 0)
    return integrals


def run() -> dict:
    contract = native_json(CASE / "contract.json")
    diff = native_json(CASE / "exact-diff.json")
    parent_source = native_json(PARENT / "oper-no-spare-input.json")
    child_source = native_json(CASE / "exponential-two-crew-input.json")
    check("source and contract fingerprints", sha(PARENT / "oper-no-spare-input.json") == PARENT_SHA == contract["parent_input_sha256"] == diff["parent_input_sha256"] and sha(CASE / "exponential-two-crew-input.json") == CHILD_SHA == contract["child_input_sha256"] == diff["child_input_sha256"])
    check("accepted parent closure fingerprint", sha(FIXED / "closure.json") == PARENT_CLOSURE_SHA)
    index = native_json(BASE / "publication-index-v1.json")
    check("accepted parent publication identity", any(item["publication_id"] == contract["parent_publication_id"] == "C10.var02.operational_crew_failure_spare.1.0.0" and item["package"] == PARENT.name for item in index["entries"]))
    check("installed manual, dictionary and executable", sha(MANUAL) == contract["source_manual_sha256"] and sha(DICTIONARY) == contract["source_dictionary_sha256"] and sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")
    dictionary = DICTIONARY.read_text(encoding="utf-8-sig", errors="replace")
    check("RMDTD accepts direct <EXP>", "ResourceStationData;7;RMDTD;" in dictionary and "Multiple choice: <EXP>, or element in related table" in dictionary)
    ptab, ctab = tables(parent_source, "model"), tables(child_source, "model")
    changed = sorted(k for k in ptab if ptab[k] != ctab[k])
    check("exact 32-table parent delta", len(ptab) == len(ctab) == 32 and set(ptab) == set(ctab) and changed == ["ProblemDescription", "ResourceStationData"])
    pcols = [c["name"] for c in ptab["ResourceStationData"]["columns"]]
    check("one-field RMDTD delta", pcols == [c["name"] for c in ctab["ResourceStationData"]["columns"]] and dict(zip(pcols, rows(ptab["ResourceStationData"])[0])) | {"RMDTD": "<EXP>"} == dict(zip(pcols, rows(ctab["ResourceStationData"])[0])))
    check("unchanged crew, seed and horizon", rows(ptab["ResourceAllocation"]) == rows(ctab["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]] and rows(ptab["Control"]) == rows(ctab["Control"]) and rows(ptab["MissionPreparation"]) == rows(ctab["MissionPreparation"]) and rows(ptab["OperationProfile"]) == rows(ctab["OperationProfile"]))
    fixed_inv, _ = seal(FIXED, "fixed")
    child_inv, child_closure = seal(CHILD, "exponential")
    check("run source/runtime fingerprints", fixed_inv["input_sha256"] == PARENT_SHA and child_inv["input_sha256"] == CHILD_SHA and child_inv["parent_sha256"] == PARENT_SHA and child_closure["source_hashes_before"]["contract"] == sha(CASE / "contract.json") and child_closure["source_hashes_before"]["builder"] == sha(CASE / "build.py") and child_closure["source_hashes_before"]["checker"] == sha(CASE / "check_roundtrip.py") and child_closure["source_hashes_before"]["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    imported = tables(native_json(CHILD / "input.json"), "model")
    exported = tables(native_json(CHILD / "roundtrip-raw.json"), "model")
    source_names = {k for k, t in imported.items() if rows(t)}
    check("21 row-containing source tables", len(source_names) == 21)
    for name in sorted(source_names):
        check(f"exact child native roundtrip {name}", name in exported and imported[name]["columns"] == exported[name]["columns"] and rows(imported[name]) == rows(exported[name]))
    check("roundtrip checker reports pass", native_json(CHILD / "roundtrip-validation.json")["passed"] is True)
    for tag, path in (("fixed", FIXED), ("exponential", CHILD)):
        runlog = (path / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check(f"{tag}: zero conversion errors; classified warnings", "Input conversion completed. Errors: 0, Warnings: 2" in runlog and re.findall(r"warning #(\d+)", runlog) == ["108", "126"])
        check(f"{tag}: native outputs nonempty", all((path / n).stat().st_size > 4 for n in ("model.sxi", "model.sxo", "report-raw.json")))
    times: dict[str, dict] = {}
    for tag, path, repair_expected, resume_expected, prep_expected, success_expected in (("fixed", FIXED, 7.98494, 7.98494, 8.25, 9.25), ("exponential", CHILD, 8.3441, 8.0, 8.26506, 9.26506)):
        log = (path / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        failure = event_time(log, r"^Time: ([\d.]+) <P-CREW at <BASE-01,0>> Failed")
        repair = event_time(log, r"^Time: ([\d.]+) <P-CREW at <BASE-01,0>> Repaired")
        stop = event_time(log, r"^Time: ([\d.]+)  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to a resource failure")
        resumes = [float(x) for x in re.findall(r"^Time: ([\d.]+)  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", log, re.MULTILINE)]
        prep_end = event_time(log, r"^Time: ([\d.]+) <TEACH-AIR-01,0> preparation ended")
        mission_start = event_time(log, r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting")
        mission_success = event_time(log, r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success")
        check(f"{tag}: one failure/repair and actual downtime", close(failure, 7.73494, 1e-6) and close(repair, repair_expected, 1e-5) and len(re.findall(r"P-CREW at <BASE-01,0>> Failed", log)) == len(re.findall(r"P-CREW at <BASE-01,0>> Repaired", log)) == 1)
        check(f"{tag}: stopped task and resumption", close(stop, failure, 1e-6) and resumes == [7.5, resume_expected] and "time left= 0.265061" in log)
        check(f"{tag}: preparation and same-ID mission success", close(prep_end, prep_expected, 1e-5) and close(mission_start, prep_expected, 1e-5) and close(mission_success, success_expected, 1e-5) and log.count("mission completed: <TEACH-AIR-01") == 1 and "System arrives <TEACH-AIR-01,0>" in log and "System arrives <TEACH-AIR-01,1>" in log)
        check(f"{tag}: second aircraft prep ends at 8", "Time: 8 <TEACH-AIR-01,1> preparation ended" in log)
        integrals = replay_report(path, tag, failure, repair, resume_expected, prep_expected, success_expected)
        times[tag] = {"failure": failure, "repair": repair, "downtime": repair - failure, "resume": resume_expected, "preparation_end": prep_end, "mission_start": mission_start, "mission_success": mission_success, "resource_hours": integrals}
    check("distribution sample differs from fixed downtime", close(times["fixed"]["downtime"], 0.25, 1e-5) and close(times["exponential"]["downtime"], 0.60916, 2e-5) and times["exponential"]["downtime"] > times["fixed"]["downtime"])
    check("child resumes on freed crew before repair", times["exponential"]["resume"] == 8.0 < times["exponential"]["repair"] and times["exponential"]["mission_start"] < times["exponential"]["repair"])
    child_log = (CHILD / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    release = "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> frees resources"
    booking = "Time: 8  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> books resources"
    check("child hour-8 release precedes stopped task rebooking", release in child_log and booking in child_log and child_log.index(release) < child_log.index(booking) and "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1" in child_log)
    failures = [item["name"] for item in CHECKS if not item["passed"]]
    return {
        "schema": "simlox-c10-var04-independent-readonly/v1",
        "case_id": "C10.var04",
        "review_date": "2026-09-30",
        "passed": not failures,
        "check_count": len(CHECKS),
        "passed_count": len(CHECKS) - len(failures),
        "failures": failures,
        "decision": "GO_bounded_one_sample_downtime_contrast" if not failures else "NO_GO",
        "observed": times,
        "scope": "The <EXP> child yielded a 0.60916h repair versus the fixed parent's 0.25h. The stopped task resumed at hour 8 when another crew became free, before the failed crew repaired at 8.3441; mission success was 9.26506 versus 9.25.",
        "limits": ["One fixed seed and one sampled resource downtime cannot establish the exponential distribution's shape or mean.", "The pool-level log does not identify individual crew; the alternative worker at hour 8 is inferred from release/allocation events and capacity, not named.", "GUI/session/mutex claims are replayed from sealed metadata; native SIMLOX was not rerun."],
        "checks": CHECKS,
    }


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        result = {"schema": "simlox-c10-var04-independent-readonly/v1", "case_id": "C10.var04", "review_date": "2026-09-30", "passed": False, "check_count": len(CHECKS) + 1, "passed_count": sum(x["passed"] for x in CHECKS), "failures": [f"{type(exc).__name__}: {exc}"], "decision": "NO_GO", "checks": CHECKS}
    path = CASE / "review/independent-readonly-2026-09-30.json"
    path.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "check_count", "passed_count", "failures", "decision")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
