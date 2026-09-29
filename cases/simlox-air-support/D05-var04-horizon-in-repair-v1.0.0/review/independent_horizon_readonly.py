"""Independent read-only replay of D05.var04 hour-26 in-repair evidence.

Only the standard library and frozen source/sealed raw files are used. The
builder, author validator, import-export checker, and SIMLOX are not imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "D05-maintenance-competition-v1.0.0"
RUN = CASE / "runs" / "d05-var04-horizon-v100-ssh-20260930-02"
FAILED_PILOT = CASE / "runs" / "d05-var04-horizon-v100-ssh-20260930-01"
PARENT_RUN = PARENT / "runs" / "d05-pilot-v100-ssh-20260930-03"
INPUT_SHA = "c079a64d31f1b4ae2d7d537d1546bc5277bf20bcc55353aa7d1c4f487edd2b74"
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
PARENT_LOG_SHA = "daeacfda91304217c1e3ac75e6842bd17de5ae2bac067fbf21aff82f96396fd5"
PARENT_REPORT_SHA = "46975e779235a773b6e3473423dbb83a635cee9afd43baa77bb748f873cc406c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Strip native JSON trailing commas, preserving quoted string content."""
    raw = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(raw):
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
        elif char == "," and re.match(r"\s*[}\]]", raw[index + 1 :]):
            continue
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict:
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(doc: dict, root: str, name: str) -> list[dict]:
    table = tables(doc, root)[name]
    columns = [column["name"] for column in table["columns"]]
    return [
        dict(zip(columns, row))
        for instance in table["instances"]
        for row in instance["rows"]
    ]


def row_tables(doc: dict) -> dict:
    return {
        table["name"]: (
            table["columns"],
            [row for instance in table["instances"] for row in instance["rows"]],
        )
        for table in doc["model"]["tables"]
        if any(instance["rows"] for instance in table["instances"])
    }


def log_events(log: str) -> dict:
    find = lambda pattern: re.findall(pattern, log, flags=re.MULTILINE)
    return {
        "mission_starts": [
            (float(time), kind, int(aircraft))
            for time, kind, aircraft in find(
                r"^Time: ([\d.]+) <(BASIC-MISSION|RISK-MISSION),[^\n]+> mission starting, duration: [\d.]+ : <TEACH-AIR-01,([01])>$"
            )
        ],
        "mission_successes": [
            (float(time), kind)
            for time, kind in find(r"^Time: ([\d.]+) <(BASIC-MISSION|RISK-MISSION),[^\n]+> mission success: ?$")
        ],
        "failure": [float(x) for x in find(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added, now")],
        "abort": [float(x) for x in find(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted: ?$")],
        "repair_object": [float(x) for x in find(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> started$")],
        "repair_work": [
            float(x) for x in find(
                r"^Time: ([\d.]+)  direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,1> starts performing, planned to last for 5 hours$"
            )
        ],
        "repair_done": [float(x) for x in find(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> completed$")],
        "pm_objects": [
            (float(time), int(aircraft))
            for time, aircraft in find(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> started$")
        ],
        "pm_requests": [
            (float(time), int(aircraft))
            for time, aircraft in find(
                r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,([01])> requests resources$"
            )
        ],
        "pm_work": [
            (float(time), int(aircraft))
            for time, aircraft in find(
                r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,([01])> starts performing, planned to last for 1 hours$"
            )
        ],
        "pm_done": [
            (float(time), int(aircraft))
            for time, aircraft in find(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> completed$")
        ],
        "worker_allocations": [
            (float(time), int(available))
            for time, available in find(
                r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: ([01])$"
            )
        ],
        "worker_releases": [
            (float(time), int(available))
            for time, available in find(
                r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> deallocated from\s+maintenance task: 1  available now: ([01])$"
            )
        ],
        "worker_failed_tests": len(find(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed ?$")),
        "worker_ok_tests": len(find(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 OK ?$")),
        "worker_shift_end": [float(x) for x in find(r"^Time: ([\d.]+)  resource shift 0 ended at <P-MAINT at <BASE-01,0>> time gap to next = 0$")],
        "mission_cancelled": bool(re.search(r"mission cancelle?d", log, flags=re.IGNORECASE)),
    }


def metrics(report: dict) -> dict:
    system = rows(report, "report", "SystemResults")
    resource = rows(report, "report", "ResourceResults")
    stock = rows(report, "report", "StockTotalResults")
    summary = rows(report, "report", "ResultSummary")
    resource_total = rows(report, "report", "ResourceResultsTotal")
    return {
        "system": system,
        "resource": resource,
        "stock": stock,
        "summary": summary,
        "resource_total": resource_total,
        "repair_hours": sum(x["NSYRP"] * 0.5 for x in system),
        "pm_hours": sum(x["NSYPM"] * 0.5 for x in system),
        "worker_use_hours": sum(x["NRUM"] * 0.5 for x in resource),
        "worker_wait_hours": sum(x["NRW"] * 0.5 for x in resource),
    }


def replay() -> dict:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append({
            "name": name,
            "passed": abs(actual - expected) <= tolerance,
            "actual": actual,
            "expected": expected,
            "tolerance": tolerance,
        })

    observed: dict = {}
    hashes: dict = {}
    try:
        contract = read_json(CASE / "contract.json")
        diff = read_json(CASE / "parent-diff.json")
        invocation = read_json(RUN / "invocation.json")
        closure = read_json(RUN / "closure.json")
        parent_closure = read_json(PARENT_RUN / "closure.json")
        steps = read_json(RUN / "steps.json")
        checker = read_json(RUN / "roundtrip-validation.json")
        source = native_json(CASE / "native-input.json")
        parent = native_json(PARENT / "native-input.json")
        copied = native_json(RUN / "input.json")
        exported = native_json(RUN / "roundtrip-raw.json")
        report = native_json(RUN / "report-raw.json")
        parent_report = native_json(PARENT_RUN / "report-raw.json")
        log = (RUN / "model.log").read_text(encoding="utf-8-sig")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
        run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
        failed_log = (FAILED_PILOT / "run.log").read_text(encoding="utf-8-sig")
        runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")

        source_paths = {
            "input": CASE / "native-input.json",
            "parent": PARENT / "native-input.json",
            "contract": CASE / "contract.json",
            "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py",
            "python": Path(invocation["planned_check"]["executable"]),
            "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        }
        source_hashes = {name: sha(path) for name, path in source_paths.items()}
        raw_hashes = {
            name: {"sha256": sha(RUN / name), "bytes": (RUN / name).stat().st_size}
            for name in closure["raw"]
        }
        check("accepted parent input SHA", source_hashes["parent"], PARENT_SHA)
        check("frozen hour-26 input SHA", source_hashes["input"], INPUT_SHA)
        check("copied input SHA", sha(RUN / "input.json"), INPUT_SHA)
        check("contract, diff and invocation source binding", (
            contract["input_sha256"], contract["parent_input_sha256"],
            diff["child_input_sha256"], diff["parent_input_sha256"],
            invocation["input_sha256"], invocation["parent_sha256"],
        ), (INPUT_SHA, PARENT_SHA, INPUT_SHA, PARENT_SHA, INPUT_SHA, PARENT_SHA))
        check("source hashes before and after", (closure["source_hashes_before"], closure["source_hashes_after"]), (source_hashes, source_hashes))
        check("invocation source hashes", invocation["source_hashes_before"], source_hashes)
        check("invocation byte seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
        check("12 sealed raw hashes and byte counts", (len(raw_hashes), raw_hashes), (12, closure["raw"]))
        check("raw inventory", sorted(raw_hashes), sorted([
            "input.json", "import.log", "model.sxi", "roundtrip-raw.json",
            "export.log", "model.sxo", "model.log", "run.log",
            "report-raw.json", "report-export.log", "roundtrip-validation.json", "steps.json",
        ]))
        check("closure error", closure["error"], None)
        check("run and case identity", (closure["run_id"], invocation["run_id"], invocation["case_id"]), (RUN.name, RUN.name, "D05.var04"))
        check("accepted parent sealed log and report", (
            parent_closure["source_hashes_before"]["input"], sha(PARENT_RUN / "model.log"), sha(PARENT_RUN / "report-raw.json"),
        ), (PARENT_SHA, PARENT_LOG_SHA, PARENT_REPORT_SHA))
        check("session-0 SSH and GUI identity", (
            invocation["session_id"], invocation["ssh_connection_present"],
            "sshd.exe" in invocation["ssh_ancestor_names"],
            invocation["gui"]["pid"], invocation["gui"]["session_id"],
        ), (0, True, True, 13340, 1))
        check("host mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("runner implements session, queue, GUI and immutable-run guards", all(token in runner for token in [
            "session-0 SSH required", "host-wide Issue 18 native queue busy",
            "expected existing GUI PID 13340 only", "GUI session not active",
            "GUI process changed", "immutable native run already exists",
        ]), True)
        check("five recorded steps", [x["name"] for x in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
        check("steps exit zero and preserve GUI", all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps), True)

        check("source and copied input model equal", copied, source)
        ptab, ctab = tables(parent, "model"), tables(source, "model")
        check("same native table universe", (len(ptab), sorted(ptab)), (31, sorted(ctab)))
        changed = sorted(name for name in ptab if ptab[name] != ctab[name])
        check("exact four changed tables", changed, ["Control", "OperationProfile", "ProblemDescription", "ResultCollection"])
        check("diff file changed-table set and 27 unchanged", (sorted(diff["changed_tables_only"]), diff["unchanged_table_count"]), (changed, 27))
        field_changes = {
            name: sorted(key for key in rows(parent, "model", name)[0] if rows(parent, "model", name)[0][key] != rows(source, "model", name)[0][key])
            for name in ["Control", "ProblemDescription"]
        }
        check("control horizon fields and descriptive label", field_changes, {"Control": ["RCEND", "SIMPE"], "ProblemDescription": ["PDESC"]})
        check("control horizon 36 to 26", (
            rows(parent, "model", "Control")[0]["SIMPE"], rows(source, "model", "Control")[0]["SIMPE"],
            rows(parent, "model", "Control")[0]["RCEND"], rows(source, "model", "Control")[0]["RCEND"],
        ), (36, 26, 36, 26))
        check("both result windows 36 to 26", (
            [(x["RTYPE"], x["RCEND"]) for x in rows(parent, "model", "ResultCollection")],
            [(x["RTYPE"], x["RCEND"]) for x in rows(source, "model", "ResultCollection")],
        ), ([("MISSION", 36), ("SYSTEM", 36)], [("MISSION", 26), ("SYSTEM", 26)]))
        parent_profile, child_profile = rows(parent, "model", "OperationProfile"), rows(source, "model", "OperationProfile")
        check("only out-of-window third mission removed", (
            child_profile, parent_profile[len(child_profile):],
        ), (parent_profile[:2], [parent_profile[2]]))
        check("third mission was scheduled at hour 32", (
            parent_profile[2]["SPRID"], parent_profile[2]["STIM"],
        ), ("BASIC-MISSION", 32))
        check("diff file rows match actual child and parent", all(
            diff["tables"][name]["parent_rows"] == rows(parent, "model", name)
            and diff["tables"][name]["child_rows"] == rows(source, "model", name)
            for name in changed
        ), True)
        before, after = row_tables(copied), row_tables(exported)
        check("22 source row-containing tables roundtrip unchanged", (
            len(before), len(after), all(after.get(name) == value for name, value in before.items()),
        ), (22, 31, True))
        extras = sorted(name for name in after if name not in before)
        check("nine additional native all-null placeholders", (extras, all(
            all(value is None for row in after[name][1] for value in row) for name in extras
        )), (sorted([
            "Item", "ItemReorder", "ItemRepair", "ItemReplacement", "ItemStructure",
            "MissionPreparation", "StationStructure", "StockAllocation", "TaskResource",
        ]), True))
        check("recorded roundtrip checker", (
            checker["passed"], len(checker["populated_tables"]), checker["source_sha256"],
        ), (True, 22, INPUT_SHA))
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        check("accepted conversion errors, warnings, notes", conversion.groups() if conversion else None, ("0", "2", "0"))
        check("known warning codes", ("(warning #108)" in run_log, "(warning #126)" in run_log), (True, True))
        check("preliminary -01 excluded for conversion #204", (
            "(error #204)" in failed_log,
            "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in failed_log,
        ), (True, True))

        child_events, parent_events = log_events(log), log_events(parent_log)
        check("first two missions match accepted parent", child_events["mission_starts"], parent_events["mission_starts"][:2])
        check("one mission success at hour 10", child_events["mission_successes"], [(10.0, "BASIC-MISSION")])
        check("first success, second critical abort, no cancellation", (
            child_events["mission_starts"], child_events["failure"], child_events["abort"], child_events["mission_cancelled"],
        ), ([(8.0, "BASIC-MISSION", 0), (20.0, "RISK-MISSION", 1)], [22.6835], [22.6835], False))
        check("failure and abort time match parent", (
            child_events["failure"], child_events["abort"],
        ), (parent_events["failure"], parent_events["abort"]))
        check("repair starts and works at hour 23", (
            child_events["repair_object"], child_events["repair_work"],
        ), ([23.0], [23.0]))
        check("repair not completed by hour 26", child_events["repair_done"], [])
        check("parent repair completes later at hour 28", parent_events["repair_done"], [28.0])
        check("two CAL24 PM task objects start", sorted(child_events["pm_objects"]), [(24.0, 0), (24.0, 1)])
        check("only healthy-aircraft PM requests worker at hour 24", child_events["pm_requests"], [(24.0, 0)])
        check("PM has not performed or completed by hour 26", (child_events["pm_work"], child_events["pm_done"]), ([], []))
        check("one successful repair request and one failed PM request", (
            child_events["worker_ok_tests"], child_events["worker_failed_tests"],
        ), (1, 1))
        check("worker booked at 23 and never released before stop", (
            child_events["worker_allocations"], child_events["worker_releases"],
        ), ([(23.0, 0)], []))
        check("resource shift and event log end at hour 26", child_events["worker_shift_end"], [26.0])

        cm, pm = metrics(report), metrics(parent_report)
        s, r, stock = cm["system"], cm["resource"], cm["stock"]
        check("52 aligned half-hour bins and 26-hour summary", (
            len(cm["summary"]), cm["summary"][0]["RTIUP"],
            len(s), len(r), len(stock),
            all(x["STINT"] == i / 2 and x["ETINT"] == (i + 1) / 2 for group in (s, r, stock) for i, x in enumerate(group)),
        ), (1, 26, 52, 52, 52, True))
        check("report event markers without maintenance completion", (
            [(x["STINT"], x["NFAIL"]) for x in s if x["NFAIL"]],
            [(x["STINT"], x["NPMS"]) for x in s if x["NPMS"]],
            sum(x["NREPT"] for x in s), sum(x["NPMT"] for x in s),
        ), ([(22.5, 1)], [(24, 2)], 0, 0))
        near("three partial repair aircraft-hours 23-26", cm["repair_hours"], 3)
        near("zero PM aircraft-hours", cm["pm_hours"], 0)
        near("three worker-use hours 23-26", cm["worker_use_hours"], 3)
        near("two worker-wait hours 24-26", cm["worker_wait_hours"], 2)
        check("terminal one ready, one actively repairing", (
            s[-1]["NSYRY"], s[-1]["NSYRP"], s[-1]["NSYPM"], s[-1]["NSYWR"],
        ), (1, 1, 0, 0))
        check("terminal one worker used and one waiting PM request", (
            r[-1]["NR"], r[-1]["NRUM"], r[-1]["NRW"],
        ), (1, 1, 1))
        check("NRA coexists with worker in use; no free-capacity inference", (
            r[-1]["NRA"], r[-1]["NRUM"],
        ), (1, 1))
        near("resource-total normalized use", cm["resource_total"][0]["NRUM"], 3 / 26)
        near("resource-total normalized wait", cm["resource_total"][0]["NRW"], 2 / 26)
        near("one success out of two missions", cm["summary"][0]["MSUF"], 0.5)
        check("accepted parent continues to terminal completion", (
            pm["system"][-1]["NSYRY"], pm["system"][-1]["NSYRP"],
            sum(x["NREPT"] for x in pm["system"]), sum(x["NPMT"] for x in pm["system"]),
        ), (2, 0, 1, 2))

        observed = {
            "child_events": child_events,
            "parent_first_two_missions": parent_events["mission_starts"][:2],
            "child_report": {
                "half_hour_bins": len(s),
                "end_hour": cm["summary"][0]["RTIUP"],
                "mission_success_fraction": cm["summary"][0]["MSUF"],
                "repair_aircraft_hours": cm["repair_hours"],
                "pm_aircraft_hours": cm["pm_hours"],
                "worker_use_hours": cm["worker_use_hours"],
                "worker_wait_hours": cm["worker_wait_hours"],
                "terminal_ready_aircraft": s[-1]["NSYRY"],
                "terminal_aircraft_in_repair": s[-1]["NSYRP"],
                "terminal_workers_in_use": r[-1]["NRUM"],
                "terminal_worker_requests_waiting": r[-1]["NRW"],
                "terminal_NRA_uninterpreted": r[-1]["NRA"],
            },
        }
        hashes = {
            "source": source_hashes,
            "parent_diff_sha256": sha(CASE / "parent-diff.json"),
            "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "raw": raw_hashes,
            "parent_log_sha256": sha(PARENT_RUN / "model.log"),
            "parent_report_sha256": sha(PARENT_RUN / "report-raw.json"),
            "excluded_preliminary_run_log_sha256": sha(FAILED_PILOT / "run.log"),
        }
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration, json.JSONDecodeError) as exc:
        checks.append({"name": "independent replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    passed = all(item["passed"] for item in checks)
    return {
        "schema": "simlox-d05-var04-horizon-independent-review/v1",
        "reviewer": "independent standard-library read-only raw replay; no author imports",
        "case_id": "D05.var04",
        "run_id": RUN.name,
        "parent_run_id": PARENT_RUN.name,
        "passed": passed,
        "decision": "bounded_hour26_in_repair_native_evidence_pass" if passed else "independent_review_failed",
        "checks_count": len(checks),
        "checks": checks,
        "hashes": hashes,
        "observed": observed,
        "limits": [
            "The accepted child removes the out-of-window third mission and stops simulation/reporting at hour 26; this is not a literal prefix of the full 36-hour parent schedule.",
            "The five-hour direct repair starts at 23 and has three observed hours of work through 26. No completion, worker release, or later return-to-ready is observed.",
            "Both CAL24 PM task objects start at 24. Healthy-aircraft PM waits for the occupied worker; failed-aircraft PM remains behind its own active critical repair. Neither PM performs by 26.",
            "ResourceResults.NRA=1 at the terminal interval while NRUM=1. This review does not interpret NRA as a free-worker count; booking log and NRUM establish use.",
            "The preliminary -01 run failed native input conversion #204 due to the out-of-window hour-32 mission and is excluded from acceptance.",
            "This one fixed-seed CLI run does not establish post-horizon repair completion, general stop-time cleanup, GUI visual behavior, or cross-engine equivalence.",
        ],
        "publication_state": "candidate_review_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write review JSON here; stdout otherwise")
    args = parser.parse_args()
    result = replay()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
