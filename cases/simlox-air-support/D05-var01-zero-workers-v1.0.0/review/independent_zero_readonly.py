"""Independent, read-only replay of D05.var01 zero-worker native evidence.

This script uses only standard-library parsing of frozen source and sealed raw
files. It imports no author builder, validator, roundtrip checker, or SIMLOX.
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
RUN = CASE / "runs" / "d05-var01-zero-v100-ssh-20260930-01"
PARENT_RUN = PARENT / "runs" / "d05-pilot-v100-ssh-20260930-03"
INPUT_SHA = "e8ef846a1f5c87e2fce982baaa3c5057b2f9554f3a620b09c49d6ecb8bd4e158"
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
PARENT_LOG_SHA = "daeacfda91304217c1e3ac75e6842bd17de5ae2bac067fbf21aff82f96396fd5"
PARENT_REPORT_SHA = "46975e779235a773b6e3473423dbb83a635cee9afd43baa77bb748f873cc406c"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Remove native trailing commas without changing quoted string content."""
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


def events(log: str) -> dict:
    find = lambda pattern: re.findall(pattern, log, flags=re.MULTILINE)
    return {
        "failure": [float(x) for x in find(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added, now")],
        "abort": [float(x) for x in find(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted: ?$")],
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
        "mission_cancelled": bool(re.search(r"mission cancelle?d", log, flags=re.IGNORECASE)),
        "repair_object": [float(x) for x in find(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> started$")],
        "repair_request": [
            float(x) for x in find(
                r"^Time: ([\d.]+)  direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,1> requests resources$"
            )
        ],
        "repair_test": [
            float(x) for x in find(
                r"^Time: ([\d.]+)  direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,1> resource availability test$"
            )
        ],
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
        "pm_paused": [float(x) for x in find(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task \d+ on <TEACH-AIR-01,0> paused\.$")],
        "pm_wait_stopped": [float(x) for x in find(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> resource waiting stopped$")],
        "pm_continued": [float(x) for x in find(r"^Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> system PM task \d+ on <TEACH-AIR-01,0> continued ?$")],
        "resource_failed": len(find(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed ?$")),
        "resource_ok": len(find(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 OK ?$")),
        "worker_allocations": len(find(r"^Time: [\d.]+  <P-MAINT at <BASE-01,0>> allocated to maintenance task:")),
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
        check("frozen zero-worker input SHA", source_hashes["input"], INPUT_SHA)
        check("copied input SHA", sha(RUN / "input.json"), INPUT_SHA)
        check("contract and invocation source binding", (
            contract["input_sha256"], contract["parent_input_sha256"],
            invocation["input_sha256"], invocation["parent_sha256"],
        ), (INPUT_SHA, PARENT_SHA, INPUT_SHA, PARENT_SHA))
        check("source hashes before and after", (closure["source_hashes_before"], closure["source_hashes_after"]), (source_hashes, source_hashes))
        check("invocation source hash record", invocation["source_hashes_before"], source_hashes)
        check("invocation byte seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
        check("12 raw hashes and byte counts", (len(raw_hashes), raw_hashes), (12, closure["raw"]))
        check("raw inventory", sorted(raw_hashes), sorted([
            "input.json", "import.log", "model.sxi", "roundtrip-raw.json",
            "export.log", "model.sxo", "model.log", "run.log",
            "report-raw.json", "report-export.log", "roundtrip-validation.json", "steps.json",
        ]))
        check("closure error", closure["error"], None)
        check("run and case identity", (closure["run_id"], invocation["run_id"], invocation["case_id"]), (RUN.name, RUN.name, "D05.var01"))
        check("accepted parent sealed log and report", (
            parent_closure["source_hashes_before"]["input"],
            sha(PARENT_RUN / "model.log"), sha(PARENT_RUN / "report-raw.json"),
        ), (PARENT_SHA, PARENT_LOG_SHA, PARENT_REPORT_SHA))
        check("SSH session and GUI identity", (
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
        check("only three changed tables", changed, ["ProblemDescription", "Resource", "ResourceAllocation"])
        field_changes = {
            name: sorted(key for key in rows(parent, "model", name)[0] if rows(parent, "model", name)[0][key] != rows(source, "model", name)[0][key])
            for name in changed
        }
        check("two labels and one behavior field change", field_changes, {
            "ProblemDescription": ["PDESC"], "Resource": ["DESCR"], "ResourceAllocation": ["RQTY"],
        })
        check("resource quantity one to zero", (
            rows(parent, "model", "ResourceAllocation")[0]["RQTY"],
            rows(source, "model", "ResourceAllocation")[0]["RQTY"],
        ), (1, 0))
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
        check("conversion errors, warnings, notes", conversion.groups() if conversion else None, ("0", "2", "0"))
        check("known warning codes", ("(warning #108)" in run_log, "(warning #126)" in run_log), (True, True))

        child_events, parent_events = events(log), events(parent_log)
        for key in ["failure", "abort", "mission_starts", "mission_successes", "mission_cancelled", "repair_object", "pm_objects"]:
            check(f"matched one-worker {key}", child_events[key], parent_events[key])
        check("one critical failure and abort at 22.6835", (
            child_events["failure"], child_events["abort"],
        ), ([22.6835], [22.6835]))
        check("three mission starts with aircraft identity", child_events["mission_starts"], [
            (8.0, "BASIC-MISSION", 0), (20.0, "RISK-MISSION", 1), (32.0, "BASIC-MISSION", 0),
        ])
        check("first and third successes, no cancellation", (
            child_events["mission_successes"], child_events["mission_cancelled"],
        ), ([(10.0, "BASIC-MISSION"), (34.0, "BASIC-MISSION")], False))
        check("critical repair task starts at return", child_events["repair_object"], [23.0])
        check("repair requests at 23 and retry at 24", (
            child_events["repair_request"], child_events["repair_test"],
        ), ([23.0], [23.0, 24.0]))
        check("PM task objects start at 24", sorted(child_events["pm_objects"]), [(24.0, 0), (24.0, 1)])
        check("only healthy PM requests worker, at 24 and 34", child_events["pm_requests"], [(24.0, 0), (34.0, 0)])
        check("healthy PM pauses for third mission and resumes", (
            child_events["pm_paused"], child_events["pm_wait_stopped"], child_events["pm_continued"],
        ), ([31.0], [31.0], [34.0]))
        check("four resource tests fail and none succeeds", (
            child_events["resource_failed"], child_events["resource_ok"],
        ), (4, 0))
        check("no worker allocation, repair work or PM work", (
            child_events["worker_allocations"], child_events["repair_work"],
            child_events["repair_done"], child_events["pm_work"], child_events["pm_done"],
        ), (0, [], [], [], []))
        check("parent repair and PM complete", (
            parent_events["repair_work"], parent_events["repair_done"],
            parent_events["pm_work"], parent_events["pm_done"],
        ), ([23.0], [28.0], [(28.0, 0), (29.0, 1)], [(29.0, 0), (30.0, 1)]))

        cm, pm = metrics(report), metrics(parent_report)
        s, r, stock = cm["system"], cm["resource"], cm["stock"]
        check("36-hour aligned half-hour report", (
            len(cm["summary"]), cm["summary"][0]["RTIUP"],
            len(s), len(r), len(stock),
            all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for group in (s, r, stock) for i, row in enumerate(group)),
        ), (1, 36, 72, 72, 72, True))
        check("one failure and two PM object starts, no completions", (
            [(x["STINT"], x["NFAIL"]) for x in s if x["NFAIL"]],
            [(x["STINT"], x["NPMS"]) for x in s if x["NPMS"]],
            sum(x["NREPT"] for x in s), sum(x["NPMT"] for x in s),
        ), ([(22.5, 1)], [(24, 2)], 0, 0))
        near("zero repair occupancy", cm["repair_hours"], 0)
        near("zero PM occupancy", cm["pm_hours"], 0)
        near("zero worker usage", cm["worker_use_hours"], 0)
        near("22 worker wait-hours", cm["worker_wait_hours"], 22)
        check("zero workers reported and terminal two pending requests", (
            cm["resource_total"][0]["NR"], r[-1]["NR"], r[-1]["NRUM"], r[-1]["NRW"],
        ), (0, 0, 0, 2))
        near("resource-total normalized wait", cm["resource_total"][0]["NRW"], 22 / 36)
        check("resource-total normalized use zero", cm["resource_total"][0]["NRUM"], 0)
        near("mission success remains two of three", cm["summary"][0]["MSUF"], 2 / 3)
        check("terminal one ready, one waiting for repair", (
            s[-1]["NSYRY"], s[-1]["NSYUA"], s[-1]["NSYWR"], s[-1]["NSYRP"], s[-1]["NSYPM"],
        ), (1, 1, 1, 0, 0))
        check("parent terminal two ready and no repair pending", (
            pm["system"][-1]["NSYRY"], pm["system"][-1]["NSYWR"],
        ), (2, 0))
        near("parent worker use seven hours", pm["worker_use_hours"], 7)
        near("parent worker wait five hours", pm["worker_wait_hours"], 5)

        def wait_segment(start: float, end: float) -> float:
            return sum(x["NRW"] * 0.5 for x in r if start <= x["STINT"] < end)

        near("wait segment 23-24: one repair request", wait_segment(23, 24), 1)
        near("wait segment 24-31: repair plus healthy PM", wait_segment(24, 31), 14)
        near("wait segment 31-34: repair only while PM paused", wait_segment(31, 34), 3)
        near("wait segment 34-36: repair plus resumed PM", wait_segment(34, 36), 4)
        check("zero worker use throughout and waiting pattern", (
            all(x["NRUM"] == 0 for x in r),
            [(start, end, round(wait_segment(start, end))) for start, end in [(23, 24), (24, 31), (31, 34), (34, 36)]],
        ), (True, [(23, 24, 1), (24, 31, 14), (31, 34, 3), (34, 36, 4)]))

        observed = {
            "child_events": child_events,
            "parent_events": parent_events,
            "child_report": {
                "half_hour_bins": len(s),
                "worker_wait_hours": cm["worker_wait_hours"],
                "worker_use_hours": cm["worker_use_hours"],
                "repair_occupancy_hours": cm["repair_hours"],
                "pm_occupancy_hours": cm["pm_hours"],
                "wait_segments": {
                    "repair_only_23_24": wait_segment(23, 24),
                    "repair_plus_healthy_pm_24_31": wait_segment(24, 31),
                    "repair_only_pm_paused_31_34": wait_segment(31, 34),
                    "repair_plus_resumed_pm_34_36": wait_segment(34, 36),
                },
                "terminal_ready": s[-1]["NSYRY"],
                "terminal_waiting_for_repair": s[-1]["NSYWR"],
                "terminal_worker_requests_waiting": r[-1]["NRW"],
            },
            "parent_report": {
                "worker_wait_hours": pm["worker_wait_hours"],
                "worker_use_hours": pm["worker_use_hours"],
                "terminal_ready": pm["system"][-1]["NSYRY"],
            },
        }
        hashes = {
            "source": source_hashes,
            "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "raw": raw_hashes,
            "parent_log_sha256": sha(PARENT_RUN / "model.log"),
            "parent_report_sha256": sha(PARENT_RUN / "report-raw.json"),
        }
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration, json.JSONDecodeError) as exc:
        checks.append({"name": "independent replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    passed = all(item["passed"] for item in checks)
    return {
        "schema": "simlox-d05-var01-zero-workers-independent-review/v1",
        "reviewer": "independent standard-library read-only raw replay; author validator not imported",
        "case_id": "D05.var01",
        "run_id": RUN.name,
        "parent_run_id": PARENT_RUN.name,
        "passed": passed,
        "decision": "bounded_zero_worker_native_evidence_pass" if passed else "independent_review_failed",
        "checks_count": len(checks),
        "checks": checks,
        "hashes": hashes,
        "observed": observed,
        "limits": [
            "One fixed seed and one 36-hour horizon; ResourceAllocation.RQTY one to zero is the sole behavioral change.",
            "Twenty-two worker wait-hours are an integral over simultaneous requests, not elapsed wall time: 13 repair, seven healthy PM before pause, and two after resumption.",
            "The failed aircraft's PM object starts at 24 but makes no worker request while its critical repair remains unfinished. It must not be counted as additional worker wait.",
            "The healthy aircraft's noncritical PM pauses at 31 for the third mission and resumes at 34 without performing; its mission succeeds despite PM remaining open.",
            "No repair or PM completion is observed before hour 36; future completion beyond the stop is not inferred.",
            "The terminal report has one ready aircraft, one waiting for repair, and two waiting worker requests despite ResourceAllocation.RQTY=0.",
            "Native conversion has zero errors and two known warnings (#108 event logging and #126 itemless teaching system).",
            "Session-0 SSH, host mutex, and GUI PID preservation are recorded by the runner. GUI visual content was not inspected.",
            "This does not establish general priority, other fault draws, alternate capacity values, or cross-engine equivalence.",
        ],
        "publication_state": "candidate_review_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON review here; stdout otherwise")
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
