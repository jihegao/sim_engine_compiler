"""Bounded read-only replay of D04.var01's OPHOURS=4 native evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d04-flight-v100-ssh-20260930-01"
RUN_ID = "d04-var01-op4-v010-ssh-20261006-01"
CHILD_SHA = "cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd"
PARENT_SHA = "d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a"
PARENT_CLOSURE_SHA = "3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def equal(got: object, want: object, tolerance: float = 5e-5) -> bool:
    if isinstance(got, (int, float)) and not isinstance(got, bool) and isinstance(want, (int, float)) and not isinstance(want, bool):
        return math.isfinite(float(got)) and abs(float(got) - float(want)) <= tolerance
    return got == want


def safe(value: object) -> object:
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    return value


def cells(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        for instance_index, instance in enumerate(table["instances"]):
            columns = [column["name"] for column in table["columns"]]
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError(f"nonrectangular source {table['name']}")
                for field, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, field)
                    if key in result:
                        raise ValueError(f"duplicate source cell {key}")
                    result[key] = value
    return result


def events(log: str, phrase: str) -> dict[int, float]:
    pattern = (r"^Time: ([\d.]+) <(?:BASIC-MISSION|SHORT-MISSION),TEACH-UNIT,0,0,(\d+)> "
               + re.escape(phrase) + r"$")
    pairs = [(int(identity), float(time)) for time, identity in re.findall(pattern, log, re.M)]
    if len(pairs) != len({identity for identity, _ in pairs}):
        raise ValueError(f"duplicate event {phrase}")
    return dict(pairs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=HERE / "runs" / RUN_ID)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--parent-negative-control", action="store_true")
    args = ap.parse_args()
    if args.parent_negative_control:
        assert sha(PARENT_RUN / "closure.json") == PARENT_CLOSURE_SHA
        parent_closure = load(PARENT_RUN / "closure.json")
        assert len(parent_closure["raw"]) == 12
        for name, pin in parent_closure["raw"].items():
            path = PARENT_RUN / name
            assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"]
        report = native(PARENT_RUN / "report-raw.json")
        rows = table_rows(report, "SystemResults")
        pm_starts = sum(row["NPMS"] for row in rows)
        pm_hours = sum(row["NSYPM"] * .5 for row in rows)
        ready_hours = sum(row["NSYRY"] * .5 for row in rows)
        available_hours = sum(row["NSYA"] * .5 for row in rows)
        result = {"schema": "simlox-d04-var01-v010-parent-negative-control/v1",
                  "parent_run_id": PARENT_RUN.name, "passed": False,
                  "rejected_by_no_pm_gate": pm_starts != 0 and pm_hours != 0,
                  "observed_pm_starts": pm_starts, "observed_pm_hours": pm_hours,
                  "observed_ready_hours": ready_hours,
                  "observed_available_hours": available_hours,
                  "child_contract_requires": {"pm_starts": 0, "pm_hours": 0,
                                              "ready_hours": 55, "available_hours": 60},
                  "scope": "sealed accepted OPHOURS=3 parent must fail OPHOURS=4 no-PM gate"}
        data = (json.dumps(result, indent=2) + "\n").encode("utf-8")
        if args.output:
            args.output.write_bytes(data)
        else:
            sys.stdout.buffer.write(data)
        return 1
    run = args.run
    checks = []

    def check(name: str, got: object, want: object, tolerance: float | None = None) -> None:
        passed = equal(got, want, tolerance) if tolerance is not None else got == want
        checks.append({"name": name, "passed": passed, "actual": safe(got), "expected": safe(want)})

    try:
        contract = load(HERE / "contract.json")
        check("run identity", run.name, RUN_ID)
        check("frozen contract", sha(HERE / "contract.json"),
              "0ee824f2ccc35319f8cd369d961099ecaf3258641f424bdbd875b69af1ce6450")
        check("contract review", sha(HERE / "review" / "independent-contract-go-2026-10-06.md"),
              "d7b0cd954ed860f5ef31b2283b450b63945648143ef3df87cdf35d46a90dfec8")
        for name, path, expected in (
            ("parent input", PARENT / "native-input.json", PARENT_SHA),
            ("parent signoff", PARENT / "cli-scope-signoff-2026-09-30.md", contract["accepted_parent"]["signoff_sha256"]),
            ("parent closure", PARENT_RUN / "closure.json", PARENT_CLOSURE_SHA),
            ("child input", HERE / "native-input.json", CHILD_SHA),
            ("D03 prerequisite input", ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json",
             contract["instructional_prerequisites"][0]["input_sha256"]),
            ("D03 prerequisite signoff", ROOT / "D03-calendar-pm-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
             contract["instructional_prerequisites"][0]["signoff_sha256"]),
            ("manual", Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"), contract["source"]["manual_pdf_sha256"]),
            ("executable", Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"), contract["source"]["native_executable_sha256"]),
        ):
            check(name + " SHA", sha(path), expected)
        parent_closure, closure = load(PARENT_RUN / "closure.json"), load(run / "closure.json")
        check("parent/child closure complete", [parent_closure["error"], closure["error"]], [None, None])
        check("child closure run", closure["run_id"], RUN_ID)
        check("child invocation pin", closure["invocation_sha256"], sha(run / "invocation.json"))
        check("source hash stable", closure["source_hashes_before"], closure["source_hashes_after"])
        check("child source/exe pins", [closure["source_hashes_before"]["input"],
                                        closure["source_hashes_before"]["parent"],
                                        closure["source_hashes_before"]["simlox_exe"]],
              [CHILD_SHA, PARENT_SHA, contract["source"]["native_executable_sha256"]])
        check("12+12 raw files", [len(parent_closure["raw"]), len(closure["raw"])], [12, 12])
        for role, folder, doc in (("parent", PARENT_RUN, parent_closure), ("child", run, closure)):
            for name, pin in sorted(doc["raw"].items()):
                path = folder / name
                check(f"{role} raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
        invocation, steps = load(run / "invocation.json"), load(run / "steps.json")
        check("SSH session/ancestry", [invocation["session_id"], invocation["ssh_connection_present"],
                                        "sshd.exe" in invocation["ssh_ancestor_names"]], [0, True, True])
        check("GUI identity", invocation["gui"], {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("native mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("five steps", [step["name"] for step in steps],
              ["import", "export", "check_import_export", "calc", "jsonreport"])
        check("all steps complete/GUI preserved", all(step["status"] == "completed" and step["exit_code"] == 0
                                                   and step["gui_preserved"] for step in steps), True)
        roundtrip = load(run / "roundtrip-validation.json")
        check("18-table roundtrip", [roundtrip["passed"], len(roundtrip["authored_row_containing_tables"])], [True, 18])
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
        check("only warnings 108/126", sorted(re.findall(r"\(warning #(\d+)\)", converter)), ["108", "126"])

        parent_source, child_source = native(PARENT / "native-input.json"), native(HERE / "native-input.json")
        old, new = cells(parent_source), cells(child_source)
        check("source keys", set(new), set(old))
        check("sole source delta", {key: (old[key], new[key]) for key in old if old[key] != new[key]},
              {("MaterielPM", 0, 0, "PMINT"): (3.0, 4.0)})
        check("221 source cells", len(old), 221)
        check("copied input", sha(run / "input.json"), CHILD_SHA)
        exported = native(run / "roundtrip-raw.json")
        exported_tables = {table["name"]: table for table in exported["model"]["tables"]}
        for table in child_source["model"]["tables"]:
            if any(instance["rows"] for instance in table["instances"]):
                name = table["name"]
                check(f"roundtrip columns {name}", exported_tables[name]["columns"], table["columns"])
                check(f"roundtrip instances {name}", exported_tables[name]["instances"], table["instances"])

        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        def prefix(source: str) -> list[str]:
            return [line for line in source.splitlines()
                    if (match := re.match(r"^Time: ([\d.]+) ", line)) and float(match.group(1)) < 41]
        check("event prefix before h41", prefix(log), prefix(parent_log))
        check("mission starts", events(log, "mission starting, duration: 2 : <TEACH-AIR-01,0>") |
              events(log, "mission starting, duration: 1 : <TEACH-AIR-01,0>"), {0: 8.0, 1: 40.0})
        check("mission success", events(log, "mission success: "), {0: 10.0, 1: 41.0})
        check("mission completed", events(log, "mission completed: <TEACH-AIR-01,0>"), {0: 10.0, 1: 41.0})
        check("no mission cancellation", events(log, "mission cancelled: "), {})
        check("no PM task/subtask events", bool(re.search(r"^Time: .*\b(?:system PM task|subtask \d+ seqno \d+ within system PM task|System to PM|Maintained system arrives)\b", log, re.M)), False)
        check("no PM arrival claim", " 1 PM tasks:" in log or "OP3 Critical" in log, False)

        report, parent_report = native(run / "report-raw.json"), native(PARENT_RUN / "report-raw.json")
        system, parent_system = table_rows(report, "SystemResults"), table_rows(parent_report, "SystemResults")
        stock, parent_stock = table_rows(report, "StockTotalResults"), table_rows(parent_report, "StockTotalResults")
        summary, parent_summary = table_rows(report, "ResultSummary"), table_rows(parent_report, "ResultSummary")
        check("120 System/Stock rows", [len(system), len(stock), len(parent_system), len(parent_stock)], [120] * 4)
        check("40/16 field sets", [len(system[0]), len(stock[0])], [40, 16])
        ready = next(row for row in parent_system if row["STINT"] == 42.5)
        for index, row in enumerate(system):
            time = index * .5
            expected = dict(parent_system[index]) if time < 41 else dict(ready, STINT=time, ETINT=time + .5)
            check(f"System field set h{time}", set(row), set(expected))
            for field, want in expected.items():
                check(f"System h{time} {field}", row[field], want, tolerance=5e-5)
        for index, (row, expected) in enumerate(zip(stock, parent_stock)):
            check(f"Stock field set {index}", set(row), set(expected))
            for field, want in expected.items():
                check(f"Stock row {index} {field}", row[field], want)
        check("one summary row", [len(summary), len(parent_summary)], [1, 1])
        check("summary field set", set(summary[0]), set(parent_summary[0]))
        for field, want in parent_summary[0].items():
            check(f"summary {field}", summary[0][field], want, tolerance=3e-8)
        for field, want in (("NSYRY", 55), ("NSYA", 60), ("NSYMO", 3), ("NSYPM", 0), ("NSYMA", 5)):
            check(f"integrated {field}", sum(row[field] * .5 for row in system), want, tolerance=5e-5)
        check("zero PM markers", [sum(row["NPMS"] for row in system), sum(row["NPMT"] for row in system)], [0, 0])
        check("zero failure/repair", all(row["NFAIL"] == 0 and row["NREPT"] == 0 for row in system), True)
        check("terminal ready/no PM/flight", [system[-1][field] for field in ("NSYRY", "NSYPM", "NSYMO")], [1, 0, 0])
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        checks.append({"name": "validator exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d04-var01-v010-native-validation/v1", "run_id": run.name,
              "passed": all(item["passed"] for item in checks), "checks_count": len(checks),
              "checks": checks, "scope": "one OPHOURS=3 at-threshold parent versus OPHOURS=4 below-threshold child",
              "human_label_note": "PMID OP3 and DESCR Three-operation-hour service are retained labels; PMINT=4 is authoritative in child",
              "publication_state": "not_published"}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
