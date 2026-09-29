"""Independent, read-only replay of the sealed D05 SIMLOX CLI pilot.

Uses only the Python standard library. It does not import the case builder,
roundtrip checker, author validator, or any native SIMLOX component.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
LIBRARY = CASE.parent
DEFAULT_RUN = CASE / "runs" / "d05-pilot-v100-ssh-20260930-03"
PARENT = LIBRARY / "D03-calendar-pm-v1.0.0" / "native-input.json"
INPUT_SHA = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    """Parse native JSON, removing trailing commas outside quoted strings."""
    raw = path.read_text(encoding="utf-8-sig")
    result: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(raw):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char == "," and re.match(r"\s*[}\]]", raw[index + 1 :]):
            continue
        else:
            result.append(char)
    return json.loads("".join(result))


def table_rows(doc: dict, root: str, name: str) -> list[dict]:
    table = next(t for t in doc[root]["tables"] if t["name"] == name)
    columns = [column["name"] for column in table["columns"]]
    return [
        dict(zip(columns, row))
        for instance in table["instances"]
        for row in instance["rows"]
    ]


def populated_business(doc: dict) -> dict:
    return {
        table["name"]: (
            table["columns"],
            [row for instance in table["instances"] for row in instance["rows"]],
        )
        for table in doc["model"]["tables"]
        if any(instance["rows"] for instance in table["instances"])
    }


def replay(run: Path) -> dict:
    checks: list[dict] = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append(
            {"name": name, "passed": actual == expected, "actual": actual, "expected": expected}
        )

    def near(name: str, actual: float, expected: float, tolerance: float = 3e-5) -> None:
        checks.append(
            {
                "name": name,
                "passed": abs(actual - expected) <= tolerance,
                "actual": actual,
                "expected": expected,
                "tolerance": tolerance,
            }
        )

    try:
        contract = read_json(CASE / "contract.json")
        invocation = read_json(run / "invocation.json")
        closure = read_json(run / "closure.json")
        steps = read_json(run / "steps.json")
        checker = read_json(run / "roundtrip-validation.json")
        source = native_json(CASE / "native-input.json")
        parent = native_json(PARENT)
        copied = native_json(run / "input.json")
        exported = native_json(run / "roundtrip-raw.json")
        report = native_json(run / "report-raw.json")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        run_log = (run / "run.log").read_text(encoding="utf-8-sig")

        source_paths = {
            "input": CASE / "native-input.json",
            "parent": PARENT,
            "contract": CASE / "contract.json",
            "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py",
            "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(invocation["planned_check"]["executable"]),
            "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        }
        source_hashes = {name: sha(path) for name, path in source_paths.items()}
        raw_hashes = {
            name: {"sha256": sha(run / name), "bytes": (run / name).stat().st_size}
            for name in closure["raw"]
        }
        check("accepted D03 parent SHA", source_hashes["parent"], PARENT_SHA)
        check("frozen D05 source SHA", source_hashes["input"], INPUT_SHA)
        check("copied input byte SHA", sha(run / "input.json"), INPUT_SHA)
        check("contract source binding", (contract["input_sha256"], contract["parent_input_sha256"]), (INPUT_SHA, PARENT_SHA))
        check("invocation source binding", (invocation["input_sha256"], invocation["parent_sha256"]), (INPUT_SHA, PARENT_SHA))
        check("source hashes before and after", (closure["source_hashes_before"], closure["source_hashes_after"]), (source_hashes, source_hashes))
        check("invocation byte seal", closure["invocation_sha256"], sha(run / "invocation.json"))
        check("12 sealed raw file hashes and byte counts", (len(raw_hashes), raw_hashes), (12, closure["raw"]))
        check(
            "sealed raw file inventory",
            sorted(raw_hashes),
            sorted([
                "input.json", "import.log", "model.sxi", "roundtrip-raw.json",
                "export.log", "model.sxo", "model.log", "run.log",
                "report-raw.json", "report-export.log", "roundtrip-validation.json", "steps.json",
            ]),
        )
        check("closure error", closure["error"], None)
        check("run and case IDs", (closure["run_id"], invocation["case_id"], invocation["run_id"]), (run.name, "D05", run.name))
        check("SSH session zero", (invocation["session_id"], invocation["ssh_connection_present"], "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
        check("recorded GUI and queue guard", (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["queue_mutex"]), (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        check("five recorded steps", [step["name"] for step in steps], ["import", "export", "calc", "jsonreport", "check_import_export"])
        check("step success and GUI preservation", all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), True)

        before, after = populated_business(copied), populated_business(exported)
        check("source and copied input model equality", copied, source)
        check("22 source row-containing tables roundtrip exactly", (len(before), len(after), all(after.get(name) == value for name, value in before.items())), (22, 31, True))
        placeholder_tables = sorted(name for name in after if name not in before)
        check("nine added native all-null placeholder tables", (placeholder_tables, all(
            all(value is None for row in after[name][1] for value in row)
            for name in placeholder_tables
        )), (sorted([
            "Item", "ItemReorder", "ItemRepair", "ItemReplacement", "ItemStructure",
            "MissionPreparation", "StationStructure", "StockAllocation", "TaskResource",
        ]), True))
        check("recorded import/export checker", (checker["passed"], len(checker["populated_tables"]), checker["source_sha256"]), (True, 22, INPUT_SHA))
        parent_tables = {table["name"]: table for table in parent["model"]["tables"]}
        source_tables = {table["name"]: table for table in source["model"]["tables"]}
        changed = sorted(name for name in source_tables if source_tables[name] != parent_tables[name])
        check(
            "parent table delta",
            changed,
            sorted(
                [
                    "ProblemDescription", "Control", "System", "SystemDeployment",
                    "SystemRepair", "MissionType", "OperationProfile", "Unit",
                    "Tasks", "Resource", "ResourceAllocation", "MaterielPM",
                    "ResultCollection", "TaskBreakDown", "SubTaskResource",
                ]
            ),
        )
        check("two aircraft, MAXPM two, one worker", (table_rows(source, "model", "SystemDeployment")[0]["QTYPS"], table_rows(source, "model", "Unit")[0]["MAXPM"], table_rows(source, "model", "ResourceAllocation")[0]["RQTY"]), (2, 2, 1))
        check("PM and repair use one P-MAINT each", sorted((row["TID"], row["RID"], row["QTY"]) for row in table_rows(source, "model", "SubTaskResource")), [("CM-DIRECT", "P-MAINT", 1), ("PM-CAL24", "P-MAINT", 1)])
        check("noncritical calendar PM and five-hour repair", (table_rows(source, "model", "MaterielPM")[0]["OPID"], table_rows(source, "model", "MaterielPM")[0]["PMINT"], table_rows(source, "model", "MaterielPM")[0]["ATIM"], table_rows(source, "model", "MaterielPM")[0]["DTIM"], table_rows(source, "model", "SystemRepair")[0]["DIRPT"]), ("CALHOURS", 24.0, 0.0, 0.5, 5.0))
        check("failure confined to second mission type", sorted((row["MTID"], row["MFF"]) for row in table_rows(source, "model", "MissionType")), [("BASIC-MISSION", 0.0), ("RISK-MISSION", 1.0)])
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
        check("conversion errors/warnings/notes", conversion.groups() if conversion else None, ("0", "2", "0"))
        check("known warning codes", ("(warning #108)" in run_log, "(warning #126)" in run_log), (True, True))

        matches = lambda pattern: re.findall(pattern, log, flags=re.MULTILINE)
        failure = [float(value) for value in matches(r"^Time: ([\d.]+) <TEACH-AIR-01,1> critical random failure added, now")]
        abort = [float(value) for value in matches(r"^Time: ([\d.]+) <RISK-MISSION,[^\n]+> mission aborted: ?$")]
        repair_start = [float(value) for value in matches(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> started$")]
        repair_work = [float(value) for value in matches(r"^Time: ([\d.]+)  direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,1> starts performing, planned to last for 5 hours$")]
        repair_done = [float(value) for value in matches(r"^Time: ([\d.]+)  system DIRP task \d+ on <TEACH-AIR-01,1> completed$")]
        pm_objects = [(float(time), int(aircraft)) for time, aircraft in matches(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> started$")]
        pm_work = [(float(time), int(aircraft)) for time, aircraft in matches(r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,([01])> starts performing, planned to last for 1 hours$")]
        pm_done = [(float(time), int(aircraft)) for time, aircraft in matches(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,([01])> completed$")]
        mission_start = [(float(time), kind, int(aircraft)) for time, kind, aircraft in matches(r"^Time: ([\d.]+) <(BASIC-MISSION|RISK-MISSION),[^\n]+> mission starting, duration: [\d.]+ : <TEACH-AIR-01,([01])>$")]
        mission_success = [(float(time), kind) for time, kind in matches(r"^Time: ([\d.]+) <(BASIC-MISSION|RISK-MISSION),[^\n]+> mission success: ?$")]
        check("one failure and one abort", (failure, abort), ([22.6835], [22.6835]))
        check("one direct repair from hour 23 to 28", (repair_start, repair_work, repair_done), ([23.0], [23.0], [28.0]))
        check("two CAL24 PM task objects at hour 24", sorted(pm_objects), [(24.0, 0), (24.0, 1)])
        check("actual PM subtask work", pm_work, [(28.0, 0), (29.0, 1)])
        check("PM completion", pm_done, [(29.0, 0), (30.0, 1)])
        check("mission identities and starts", mission_start, [(8.0, "BASIC-MISSION", 0), (20.0, "RISK-MISSION", 1), (32.0, "BASIC-MISSION", 0)])
        check("two successes", mission_success, [(10.0, "BASIC-MISSION"), (34.0, "BASIC-MISSION")])
        check("no cancellation", bool(re.search(r"mission cancelle?d", log, flags=re.IGNORECASE)), False)
        check("PM resource requests fail at 24 and 28", len(matches(r"^  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed ?$")), 2)

        bookings = [
            (float(match.group(1)), match.group(2), int(match.group(3)))
            for match in re.finditer(
                r"^Time: ([\d.]+)  <P-MAINT at <BASE-01,0>> (allocated to maintenance task|deallocated from\s+maintenance task): 1  available now: ([01])$",
                log,
                flags=re.MULTILINE,
            )
        ]
        check(
            "single worker booking and release timeline",
            bookings,
            [
                (23.0, "allocated to maintenance task", 0),
                (28.0, "deallocated from  maintenance task", 1),
                (28.0, "allocated to maintenance task", 0),
                (29.0, "deallocated from  maintenance task", 1),
                (29.0, "allocated to maintenance task", 0),
                (30.0, "deallocated from  maintenance task", 1),
            ],
        )
        held = 0
        occupancy: list[int] = []
        for _, action, _ in bookings:
            held += 1 if action.startswith("allocated") else -1
            occupancy.append(held)
        check("resource occupancy never exceeds one and returns to zero", (min(occupancy), max(occupancy), held), (0, 1, 0))

        system = table_rows(report, "report", "SystemResults")
        resources = table_rows(report, "report", "ResourceResults")
        stock = table_rows(report, "report", "StockTotalResults")
        summary = table_rows(report, "report", "ResultSummary")
        resource_total = table_rows(report, "report", "ResourceResultsTotal")
        check("36-hour report and aligned half-hour bins", (len(summary), summary[0]["RTIUP"], len(system), len(resources), len(stock), all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for rows in (system, resources, stock) for i, row in enumerate(rows))), (1, 36, 72, 72, 72, True))
        check("system event markers", ([row["STINT"] for row in system if row["NFAIL"]], [row["STINT"] for row in system if row["NREPT"]], [(row["STINT"], row["NPMS"]) for row in system if row["NPMS"]], [row["STINT"] for row in system if row["NPMT"]]), ([22.5], [28], [(24, 2)], [29, 30]))
        near("five aircraft-hours in direct repair", sum(row["NSYRP"] * 0.5 for row in system), 5.0)
        near("two aircraft-hours in PM", sum(row["NSYPM"] * 0.5 for row in system), 2.0)
        check("PM never runs concurrently", max(row["NSYPM"] for row in system), 1)
        check("one failure, one repair, two PM starts and completions", (sum(row["NFAIL"] for row in system), sum(row["NREPT"] for row in system), sum(row["NPMS"] for row in system), sum(row["NPMT"] for row in system)), (1, 1, 2, 2))
        near("two successful missions out of three", summary[0]["MSUF"], 2 / 3)
        check("terminal two ready, no active repair or PM", (system[-1]["NSYRY"], system[-1]["NSYRP"], system[-1]["NSYPM"]), (2, 0, 0))
        check("resource quantity and peak use", (len(resource_total), resource_total[0]["NR"], sorted({row["NR"] for row in resources}), max(row["NRUM"] for row in resources)), (1, 1, [1], 1))
        near("resource active use: seven hours", sum(row["NRUM"] * 0.5 for row in resources), 7.0)
        near("resource wait: five hours", sum(row["NRW"] * 0.5 for row in resources), 5.0)
        near("resource total normalized use", resource_total[0]["NRUM"], 7 / 36)
        near("resource total normalized wait", resource_total[0]["NRW"], 5 / 36)
        check("terminal resource idle and no waiting", (resources[-1]["NRUM"], resources[-1]["NRW"]), (0, 0))

        observed = {
            "failure_hour": failure,
            "mission_abort_hour": abort,
            "repair_start_hour": repair_start,
            "repair_completion_hour": repair_done,
            "pm_task_object_starts": pm_objects,
            "pm_subtask_work_starts": pm_work,
            "pm_completions": pm_done,
            "mission_starts": mission_start,
            "mission_successes": mission_success,
            "worker_bookings": bookings,
            "worker_use_hours": sum(row["NRUM"] * 0.5 for row in resources),
            "worker_wait_hours": sum(row["NRW"] * 0.5 for row in resources),
            "report_half_hour_bins": len(system),
            "terminal_ready_aircraft": system[-1]["NSYRY"],
            "conversion_errors": int(conversion.group(1)),
            "conversion_warnings": int(conversion.group(2)),
        }
        hashes = {
            "source": source_hashes,
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "raw": raw_hashes,
        }
    except (OSError, KeyError, ValueError, TypeError, IndexError, StopIteration, json.JSONDecodeError) as exc:
        checks.append({"name": "independent replay exception", "passed": False, "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
        observed = {}
        hashes = {}

    return {
        "schema": "simlox-d05-independent-readonly-review/v1",
        "reviewer": "independent read-only reviewer; standard-library replay, no author validator imported",
        "case_id": "D05",
        "run_id": run.name,
        "passed": all(item["passed"] for item in checks),
        "decision": "bounded_native_cli_evidence_pass" if all(item["passed"] for item in checks) else "independent_review_failed",
        "checks_count": len(checks),
        "checks": checks,
        "hashes": hashes,
        "observed": observed,
        "limits": [
            "This is one fixed seeded two-aircraft run with one system-level direct failure, two CAL24 PM tasks, and one P-MAINT worker. It does not establish general scheduling priority or stochastic rates.",
            "Both PM task objects start at hour 24, but their physical subtasks wait for the worker and perform at 28-29 and 29-30. Task-object start time must not be presented as simultaneous PM work.",
            "The first and third BASIC missions disable failure exposure with MFF=0; only the second RISK mission uses MFF=1. The observed failure and abort do not establish other mission paths.",
            "The resource report's seven-hour use and approximately five-hour wait corroborate the event chain. Same-time release and acquisition at 28 and 29 require event-log order to identify the worker handoff.",
            "Two native conversion warnings (#108 event logging and #126 itemless teaching system) are recorded; do not call this run warning-free.",
            "Session-0 SSH, queue use, and GUI PID preservation are recorded by the runner. This reviewer did not visually inspect the live GUI.",
            "No item repair, spare logistics, additional faults, extra PM cycles, resource shifts, mission preparation resource use, or post-hour-36 state is accepted here.",
        ],
        "publication_state": "candidate_review_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, help="write review JSON here; stdout otherwise")
    args = parser.parse_args()
    result = replay(args.run.resolve())
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
