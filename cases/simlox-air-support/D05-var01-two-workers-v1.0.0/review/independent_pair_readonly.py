"""Independent, read-only replay of the D05 one/two-worker native pair.

Uses only the standard library and raw source/run files. It never imports the
case builder, author validator, roundtrip checker, or native SIMLOX component.
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
CHILD_RUN = CASE / "runs" / "d05-var01-two-v100-ssh-20260930-01"
PARENT_RUN = PARENT / "runs" / "d05-pilot-v100-ssh-20260930-03"
CHILD_SHA = "a29857331ed02bf4150c04be71d34a5f84ce66e6e76f1db27bdd94a14320686a"
PARENT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
PARENT_REPORT_SHA = "46975e779235a773b6e3473423dbb83a635cee9afd43baa77bb748f873cc406c"
PARENT_LOG_SHA = "daeacfda91304217c1e3ac75e6842bd17de5ae2bac067fbf21aff82f96396fd5"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Strip trailing commas outside quoted strings in native JSON."""
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
    bookings = [
        (float(match.group(1)), match.group(2), int(match.group(3)))
        for match in re.finditer(
            r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> (allocated to maintenance task|deallocated from\s+maintenance task): 1  available now: ([012])$",
            log,
            flags=re.MULTILINE,
        )
    ]
    return {
        "failures": [float(time) for time in find(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added, now")],
        "aborts": [float(time) for time in find(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted: ?$")],
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
        "repair_starts": [
            float(time) for time in find(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> started$")
        ],
        "repair_work": [
            float(time) for time in find(
                r"^Time: ([\d.]+)  direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,1> starts performing, planned to last for 5 hours$"
            )
        ],
        "repair_done": [
            float(time) for time in find(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> completed$")
        ],
        "pm_objects": [
            (float(time), int(aircraft))
            for time, aircraft in find(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> started$")
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
        "worker_bookings": bookings,
        "worker_availability_failures": len(find(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed ?$")),
        "worker_availability_ok": len(find(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 OK ?$")),
        "mission_cancellation": bool(re.search(r"mission cancelle?d", log, flags=re.IGNORECASE)),
    }


def report_metrics(report: dict) -> dict:
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
        "repair_hours": sum(row["NSYRP"] * 0.5 for row in system),
        "pm_hours": sum(row["NSYPM"] * 0.5 for row in system),
        "worker_use_hours": sum(row["NRUM"] * 0.5 for row in resource),
        "worker_wait_hours": sum(row["NRW"] * 0.5 for row in resource),
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
        invocation = read_json(CHILD_RUN / "invocation.json")
        closure = read_json(CHILD_RUN / "closure.json")
        parent_closure = read_json(PARENT_RUN / "closure.json")
        steps = read_json(CHILD_RUN / "steps.json")
        checker = read_json(CHILD_RUN / "roundtrip-validation.json")
        source = native_json(CASE / "native-input.json")
        parent = native_json(PARENT / "native-input.json")
        copied = native_json(CHILD_RUN / "input.json")
        exported = native_json(CHILD_RUN / "roundtrip-raw.json")
        child_report = native_json(CHILD_RUN / "report-raw.json")
        parent_report = native_json(PARENT_RUN / "report-raw.json")
        child_log = (CHILD_RUN / "model.log").read_text(encoding="utf-8-sig")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
        run_log = (CHILD_RUN / "run.log").read_text(encoding="utf-8-sig")
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
        source_hashes = {key: sha(path) for key, path in source_paths.items()}
        raw_hashes = {
            name: {"sha256": sha(CHILD_RUN / name), "bytes": (CHILD_RUN / name).stat().st_size}
            for name in closure["raw"]
        }
        check("accepted one-worker parent source hash", source_hashes["parent"], PARENT_SHA)
        check("frozen two-worker source hash", source_hashes["input"], CHILD_SHA)
        check("copied child input hash", sha(CHILD_RUN / "input.json"), CHILD_SHA)
        check(
            "contract and invocation source binding",
            (contract["input_sha256"], contract["parent_input_sha256"], invocation["input_sha256"], invocation["parent_sha256"]),
            (CHILD_SHA, PARENT_SHA, CHILD_SHA, PARENT_SHA),
        )
        check("child source hashes before and after", (closure["source_hashes_before"], closure["source_hashes_after"]), (source_hashes, source_hashes))
        check("invocation source hashes", invocation["source_hashes_before"], source_hashes)
        check("child invocation byte seal", closure["invocation_sha256"], sha(CHILD_RUN / "invocation.json"))
        check("12 sealed child raw files and byte counts", (len(raw_hashes), raw_hashes), (12, closure["raw"]))
        check(
            "child sealed raw file inventory",
            sorted(raw_hashes),
            sorted([
                "input.json", "import.log", "model.sxi", "roundtrip-raw.json",
                "export.log", "model.sxo", "model.log", "run.log",
                "report-raw.json", "report-export.log", "roundtrip-validation.json", "steps.json",
            ]),
        )
        check("child closure error", closure["error"], None)
        check("child run and case identity", (closure["run_id"], invocation["run_id"], invocation["case_id"]), (CHILD_RUN.name, CHILD_RUN.name, "D05.var01"))
        check("parent sealed source and raw hashes", (
            parent_closure["source_hashes_before"]["input"],
            sha(PARENT_RUN / "report-raw.json"),
            sha(PARENT_RUN / "model.log"),
        ), (PARENT_SHA, PARENT_REPORT_SHA, PARENT_LOG_SHA))
        check(
            "SSH session zero and GUI identity",
            (invocation["session_id"], invocation["ssh_connection_present"], "sshd.exe" in invocation["ssh_ancestor_names"], invocation["gui"]["pid"], invocation["gui"]["session_id"]),
            (0, True, True, 13340, 1),
        )
        check("host mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("runner guard implementation", all(token in runner for token in [
            "session-0 SSH required", "host-wide Issue 18 native queue busy",
            "expected existing GUI PID 13340 only", "GUI session not active",
            "GUI process changed", "immutable native run already exists",
        ]), True)
        check("five child steps", [step["name"] for step in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
        check("five steps successful and GUI preserved", all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), True)

        check("source equals copied child input model", copied, source)
        parent_tables, child_tables = tables(parent, "model"), tables(source, "model")
        check("same 31 native model tables", (len(parent_tables), sorted(parent_tables)), (31, sorted(child_tables)))
        changed = sorted(name for name in parent_tables if parent_tables[name] != child_tables[name])
        check("only three table differences", changed, ["ProblemDescription", "Resource", "ResourceAllocation"])
        field_changes = {
            name: sorted(key for key in rows(parent, "model", name)[0] if rows(parent, "model", name)[0][key] != rows(source, "model", name)[0][key])
            for name in changed
        }
        check("only two label fields and RQTY change", field_changes, {
            "ProblemDescription": ["PDESC"],
            "Resource": ["DESCR"],
            "ResourceAllocation": ["RQTY"],
        })
        check(
            "sole behavioral delta: worker quantity one to two",
            (rows(parent, "model", "ResourceAllocation")[0]["RQTY"], rows(source, "model", "ResourceAllocation")[0]["RQTY"]),
            (1, 2),
        )
        before, after = row_tables(copied), row_tables(exported)
        check("22 source row-containing tables roundtrip unchanged", (len(before), len(after), all(after.get(name) == value for name, value in before.items())), (22, 31, True))
        extras = sorted(name for name in after if name not in before)
        check("nine added all-null native placeholder tables", (extras, all(
            all(value is None for row in after[name][1] for value in row) for name in extras
        )), (sorted([
            "Item", "ItemReorder", "ItemRepair", "ItemReplacement", "ItemStructure",
            "MissionPreparation", "StationStructure", "StockAllocation", "TaskResource",
        ]), True))
        check("recorded roundtrip checker", (checker["passed"], len(checker["populated_tables"]), checker["source_sha256"]), (True, 22, CHILD_SHA))
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        check("conversion errors, warnings, notes", conversion.groups() if conversion else None, ("0", "2", "0"))
        check("known warning codes", ("(warning #108)" in run_log, "(warning #126)" in run_log), (True, True))

        child_events, parent_events = log_events(child_log), log_events(parent_log)
        shared_keys = ["failures", "aborts", "mission_starts", "mission_successes", "repair_starts", "repair_work", "repair_done", "pm_objects", "mission_cancellation"]
        check("failure, repair and mission events unchanged from one-worker control", {k: child_events[k] for k in shared_keys}, {k: parent_events[k] for k in shared_keys})
        check("one critical failure and abort", (child_events["failures"], child_events["aborts"]), ([22.6835], [22.6835]))
        check("mission starts and aircraft identities", child_events["mission_starts"], [
            (8.0, "BASIC-MISSION", 0), (20.0, "RISK-MISSION", 1), (32.0, "BASIC-MISSION", 0),
        ])
        check("two success times and no cancellation", (child_events["mission_successes"], child_events["mission_cancellation"]), ([(10.0, "BASIC-MISSION"), (34.0, "BASIC-MISSION")], False))
        check("direct repair 23 to 28", (child_events["repair_starts"], child_events["repair_work"], child_events["repair_done"]), ([23.0], [23.0], [28.0]))
        check("two PM objects start at 24 in both runs", sorted(child_events["pm_objects"]), [(24.0, 0), (24.0, 1)])
        check("child PM physical work 24 and 28", child_events["pm_work"], [(24.0, 0), (28.0, 1)])
        check("parent PM physical work 28 and 29", parent_events["pm_work"], [(28.0, 0), (29.0, 1)])
        check("child PM completion 25 and 29", child_events["pm_done"], [(25.0, 0), (29.0, 1)])
        check("parent PM completion 29 and 30", parent_events["pm_done"], [(29.0, 0), (30.0, 1)])
        check("no child worker request failure and three successful requests", (child_events["worker_availability_failures"], child_events["worker_availability_ok"]), (0, 3))
        check("two-worker booking order and available balance", child_events["worker_bookings"], [
            (23.0, "allocated to maintenance task", 1),
            (24.0, "allocated to maintenance task", 0),
            (25.0, "deallocated from  maintenance task", 1),
            (28.0, "deallocated from  maintenance task", 2),
            (28.0, "allocated to maintenance task", 1),
            (29.0, "deallocated from  maintenance task", 2),
        ])
        held = 0
        held_sequence: list[int] = []
        for _, action, available in child_events["worker_bookings"]:
            held += 1 if action.startswith("allocated") else -1
            held_sequence.append(held)
            check(f"worker availability balance after transaction {len(held_sequence)}", held + available, 2)
        check("worker occupancy peaks at two and ends at zero", (min(held_sequence), max(held_sequence), held), (0, 2, 0))

        child_metrics, parent_metrics = report_metrics(child_report), report_metrics(parent_report)
        s, r, stock = child_metrics["system"], child_metrics["resource"], child_metrics["stock"]
        check("36-hour aligned half-hour report", (
            len(child_metrics["summary"]), child_metrics["summary"][0]["RTIUP"],
            len(s), len(r), len(stock),
            all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for group in (s, r, stock) for i, row in enumerate(group)),
        ), (1, 36, 72, 72, 72, True))
        check("child system event markers", (
            [(x["STINT"], x["NFAIL"]) for x in s if x["NFAIL"]],
            [(x["STINT"], x["NREPT"]) for x in s if x["NREPT"]],
            [(x["STINT"], x["NPMS"]) for x in s if x["NPMS"]],
            [(x["STINT"], x["NPMT"]) for x in s if x["NPMT"]],
        ), ([(22.5, 1)], [(28, 1)], [(24, 2)], [(25, 1), (29, 1)]))
        check("child event totals", (
            sum(x["NFAIL"] for x in s), sum(x["NREPT"] for x in s),
            sum(x["NPMS"] for x in s), sum(x["NPMT"] for x in s),
        ), (1, 1, 2, 2))
        near("five aircraft-hours direct repair in child", child_metrics["repair_hours"], 5)
        near("two aircraft-hours PM in child", child_metrics["pm_hours"], 2)
        near("seven worker-hours used in child", child_metrics["worker_use_hours"], 7)
        near("zero worker wait in child", child_metrics["worker_wait_hours"], 0)
        near("five worker-hours waited in parent", parent_metrics["worker_wait_hours"], 5)
        near("same seven worker-hours used in parent", parent_metrics["worker_use_hours"], 7)
        check("child resource count and peak simultaneous use", (
            child_metrics["resource_total"][0]["NR"], max(x["NRUM"] for x in r),
        ), (2, 2))
        check("parent resource count and peak simultaneous use", (
            parent_metrics["resource_total"][0]["NR"], max(x["NRUM"] for x in parent_metrics["resource"]),
        ), (1, 1))
        near("child resource total normalized use", child_metrics["resource_total"][0]["NRUM"], 7 / 36)
        near("child resource total normalized wait", child_metrics["resource_total"][0]["NRW"], 0)
        near("child mission success two of three", child_metrics["summary"][0]["MSUF"], 2 / 3)
        near("parent mission success two of three", parent_metrics["summary"][0]["MSUF"], 2 / 3)
        check("child terminal two ready and resource idle", (
            s[-1]["NSYRY"], s[-1]["NSYRP"], s[-1]["NSYPM"], r[-1]["NRUM"], r[-1]["NRW"],
        ), (2, 0, 0, 0, 0))
        check("parent terminal two ready and resource idle", (
            parent_metrics["system"][-1]["NSYRY"], parent_metrics["system"][-1]["NSYRP"],
            parent_metrics["system"][-1]["NSYPM"], parent_metrics["resource"][-1]["NRUM"],
            parent_metrics["resource"][-1]["NRW"],
        ), (2, 0, 0, 0, 0))

        observed = {
            "child": child_events,
            "parent": parent_events,
            "child_report": {
                "half_hour_bins": len(s),
                "repair_aircraft_hours": child_metrics["repair_hours"],
                "pm_aircraft_hours": child_metrics["pm_hours"],
                "worker_hours_used": child_metrics["worker_use_hours"],
                "worker_hours_waiting": child_metrics["worker_wait_hours"],
                "terminal_ready_aircraft": s[-1]["NSYRY"],
            },
            "parent_report": {
                "worker_hours_used": parent_metrics["worker_use_hours"],
                "worker_hours_waiting": parent_metrics["worker_wait_hours"],
            },
        }
        hashes = {
            "child_source": source_hashes,
            "parent_input_sha256": sha(PARENT / "native-input.json"),
            "child_invocation_sha256": sha(CHILD_RUN / "invocation.json"),
            "child_closure_sha256": sha(CHILD_RUN / "closure.json"),
            "child_raw": raw_hashes,
            "parent_model_log_sha256": sha(PARENT_RUN / "model.log"),
            "parent_report_sha256": sha(PARENT_RUN / "report-raw.json"),
        }
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration, json.JSONDecodeError) as exc:
        checks.append({"name": "independent replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    passed = all(item["passed"] for item in checks)
    return {
        "schema": "simlox-d05-var01-independent-pair-review/v1",
        "reviewer": "independent read-only reviewer; standard-library raw replay, no author validator imported",
        "case_id": "D05.var01",
        "child_run_id": CHILD_RUN.name,
        "parent_run_id": PARENT_RUN.name,
        "passed": passed,
        "decision": "bounded_native_pair_evidence_pass" if passed else "independent_pair_review_failed",
        "checks_count": len(checks),
        "checks": checks,
        "hashes": hashes,
        "observed": observed,
        "limits": [
            "This is one fixed-seed two-worker comparison against one accepted one-worker run; only ResourceAllocation.RQTY changes behavior.",
            "The same one critical failure and mission schedule happened in both runs. Additional seeds and fault rates are untested.",
            "The healthy aircraft's PM overlaps repair from hour 24 to 25 with two workers. The failed aircraft's PM still waits for its own repair and works 28-29.",
            "Zero resource wait does not mean zero PM delay: the failed aircraft's PM task object starts at 24 but its subtask waits on repair until 28.",
            "The report's resource-total NRUM is seven worker-hours divided by the 36-hour horizon, not a per-worker utilization percentage.",
            "Native conversion has zero errors and two known warnings (#108 event logging and #126 itemless teaching system).",
            "Session-0 SSH, mutex, and GUI PID preservation are recorded by the runner; this review did not visually inspect the GUI.",
            "No general priority rule, other staffing level, additional fault, item repair, or post-hour-36 behavior is accepted.",
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
