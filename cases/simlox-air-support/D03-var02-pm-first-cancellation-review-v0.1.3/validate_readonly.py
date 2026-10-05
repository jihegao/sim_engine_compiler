"""Read-only bounded PM-first cancellation replay of the sealed v0.1.2 run."""
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
V010 = ROOT / "D03-var02-mission-pm-conflict-v0.1.0"
V011 = ROOT / "D03-var02-mission-pm-conflict-v0.1.1"
V012 = ROOT / "D03-var02-mission-pm-conflict-v0.1.2"
RUN = V012 / "runs" / "d03-var02-mission245-v012-ssh-20261006-01"
PARENT = ROOT / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))


def mission_map(log: str, event: str) -> dict[int, float]:
    pattern = (r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> "
               + re.escape(event) + r"$")
    pairs = [(int(identity), float(time)) for time, identity in re.findall(pattern, log, re.M)]
    if len(pairs) != len(set(identity for identity, _ in pairs)):
        raise ValueError(f"duplicate {event} mission identity")
    return dict(pairs)


def pm_times(log: str, suffix: str) -> list[float]:
    return [float(t) for t in re.findall(r"^Time: ([\d.]+)  " + suffix + r"$", log, re.M)]


def same(got: object, want: object, tolerance: float = 5e-5) -> bool:
    if isinstance(got, (int, float)) and not isinstance(got, bool) and isinstance(want, (int, float)) and not isinstance(want, bool):
        return math.isfinite(float(got)) and abs(float(got) - float(want)) <= tolerance
    return got == want


def json_value(value: object) -> object:
    if isinstance(value, set):
        return sorted(json_value(item) for item in value)
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    checks: list[dict] = []

    def check(name: str, got: object, want: object, tolerance: float | None = None) -> None:
        passed = same(got, want, tolerance) if tolerance is not None else got == want
        checks.append({"name": name, "passed": passed,
                       "actual": json_value(got), "expected": json_value(want)})

    try:
        contract = load(HERE / "contract.json")
        review = HERE / "review" / "independent-contract-go-2026-10-06.md"
        check("v013 contract status", contract["publication_state"], "not_published")
        check("v013 contract independent GO", sha(review), "21e5cf9f43ba1492a0c01e896603255812a74f765df6a452fb22990db2f6a499")
        for label, path, expected in (
            ("v010 contract", V010 / "contract.json", contract["prior_no_go_contract"]["contract_sha256"]),
            ("v010 NO_GO", V010 / "review" / "independent-contract-no-go-2026-10-06.md", contract["prior_no_go_contract"]["independent_no_go_sha256"]),
            ("v011 contract", V011 / "contract.json", contract["predeclared_basis"]["contract_sha256"]),
            ("v011 GO", V011 / "review" / "independent-contract-go-2026-10-06.md", contract["predeclared_basis"]["independent_contract_go_sha256"]),
            ("v011 NO_GO", V011 / "review" / "independent-prelaunch-no-go-2026-10-06.md", contract["predeclared_basis"]["prelaunch_no_go_sha256"]),
            ("v012 contract", V012 / "contract.json", contract["preserved_failed_branch"]["contract_sha256"]),
            ("v012 prelaunch GO", V012 / "review" / "independent-prelaunch-go-2026-10-06.md", contract["preserved_failed_branch"]["prelaunch_go_sha256"]),
            ("v012 author FAIL", V012 / "review" / "author-native-validation-2026-10-06.json", contract["preserved_failed_branch"]["author_failed_verdict_sha256"]),
            ("v012 independent NO_GO", V012 / "review" / "independent-verdict.json", contract["preserved_failed_branch"]["independent_no_go_verdict_sha256"]),
            ("v012 diagnostic memo", V012 / "review" / "independent-diagnostic-postrun-2026-10-06.md", contract["preserved_failed_branch"]["independent_no_go_memo_sha256"]),
            ("v012 independent script", V012 / "review" / "independent_replay.py", contract["sealed_run"]["independent_diagnostic_script_sha256"]),
            ("v012 closure", RUN / "closure.json", contract["sealed_run"]["closure_sha256"]),
            ("v012 input", V012 / "native-input.json", contract["sealed_run"]["input_sha256"]),
            ("v012 log", RUN / "model.log", contract["sealed_run"]["model_log_sha256"]),
            ("v012 report", RUN / "report-raw.json", contract["sealed_run"]["report_sha256"]),
            ("parent input", PARENT / "native-input.json", contract["accepted_parent"]["input_sha256"]),
            ("parent signoff", PARENT / "cli-scope-signoff-2026-09-30.md", contract["accepted_parent"]["signoff_sha256"]),
            ("parent closure", PARENT_RUN / "closure.json", contract["accepted_parent"]["closure_sha256"]),
        ):
            check(label + " SHA", sha(path), expected)
        check("same input in v011, v012 and copied run",
              [sha(V011 / "native-input.json"), sha(V012 / "native-input.json"), sha(RUN / "input.json")],
              [contract["predeclared_basis"]["frozen_child_input_sha256"]] * 3)
        check("v012 original author remains FAIL", load(V012 / "review" / "author-native-validation-2026-10-06.json")["passed"], False)
        check("v012 independent full-contract remains NO_GO", load(V012 / "review" / "independent-verdict.json")["verdict"], "NO_GO_FULL_CONTRACT")

        child_closure, parent_closure = load(RUN / "closure.json"), load(PARENT_RUN / "closure.json")
        invocation, steps = load(RUN / "invocation.json"), load(RUN / "steps.json")
        check("both native closures complete", [child_closure["error"], parent_closure["error"]], [None, None])
        check("child invocation seal", child_closure["invocation_sha256"], sha(RUN / "invocation.json"))
        check("child source stable", child_closure["source_hashes_before"], child_closure["source_hashes_after"])
        check("native executable pin", child_closure["source_hashes_before"]["simlox_exe"],
              contract["source"]["native_executable_sha256"])
        check("manual pin preserved across frozen contracts",
              load(V012 / "contract.json")["source"]["manual_pdf_sha256"],
              contract["source"]["manual_pdf_sha256"])
        check("12+12 raw files", [len(child_closure["raw"]), len(parent_closure["raw"])], [12, 12])
        for role, folder, closure in (("child", RUN, child_closure), ("parent", PARENT_RUN, parent_closure)):
            for name, pin in sorted(closure["raw"].items()):
                path = folder / name
                check(f"{role} raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
        check("SSH0 ancestry", [invocation["session_id"], invocation["ssh_connection_present"],
                                "sshd.exe" in invocation["ssh_ancestor_names"]], [0, True, True])
        check("GUI identity", invocation["gui"], {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("serial mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("five ordered steps", [x["name"] for x in steps],
              ["import", "export", "check_import_export", "calc", "jsonreport"])
        check("all native steps exit0 with GUI", all(x["status"] == "completed" and x["exit_code"] == 0
                                                and x["gui_preserved"] for x in steps), True)
        check("18-table recorded roundtrip", [load(RUN / "roundtrip-validation.json")["passed"],
              len(load(RUN / "roundtrip-validation.json")["populated_tables"])], [True, 18])
        calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc, True)
        check("only converter warning 108 and 126", sorted(re.findall(r"\(warning #(\d+)\)", calc)), ["108", "126"])

        source = native_json(V012 / "native-input.json")
        parent_source = native_json(PARENT / "native-input.json")
        old_tables = {t["name"]: t for t in parent_source["model"]["tables"]}
        new_tables = {t["name"]: t for t in source["model"]["tables"]}
        check("source table set", sorted(new_tables), sorted(old_tables))
        positions = []
        changes = []
        for name, old_table in old_tables.items():
            new_table = new_tables[name]
            check(f"source columns {name}", new_table["columns"], old_table["columns"])
            check(f"source instances {name}", len(new_table["instances"]), len(old_table["instances"]))
            for ii, (old_inst, new_inst) in enumerate(zip(old_table["instances"], new_table["instances"])):
                check(f"source instance rows {name}/{ii}", len(new_inst["rows"]), len(old_inst["rows"]))
                for ri, (old_row, new_row) in enumerate(zip(old_inst["rows"], new_inst["rows"])):
                    check(f"source row cells {name}/{ii}/{ri}", len(new_row), len(old_row))
                    for ci, (old, new) in enumerate(zip(old_row, new_row)):
                        pos = (name, ii, ri, old_table["columns"][ci]["name"])
                        positions.append(pos)
                        if old != new:
                            changes.append((pos, old, new))
        check("216 positional source cells", len(positions), 216)
        check("sole STIM source change", changes, [(('OperationProfile', 0, 1, 'STIM'), 20.0, 24.5)])
        exported = native_json(RUN / "roundtrip-raw.json")
        for t in source["model"]["tables"]:
            authored = [row for inst in t["instances"] for row in inst["rows"]]
            if authored:
                native = [x for x in exported["model"]["tables"] if x["name"] == t["name"]]
                check(f"roundtrip table {t['name']}", len(native), 1)
                check(f"roundtrip columns {t['name']}", native[0]["columns"], t["columns"])
                check(f"roundtrip instance count {t['name']}", len(native[0]["instances"]), len(t["instances"]))
                for ii, (got_inst, want_inst) in enumerate(zip(native[0]["instances"], t["instances"])):
                    check(f"roundtrip instance rows {t['name']}/{ii}", got_inst["rows"], want_inst["rows"])
                check(f"roundtrip rows {t['name']}",
                      [row for inst in native[0]["instances"] for row in inst["rows"]], authored)

        log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        def event_prefix(text: str) -> list[str]:
            return [line for line in text.splitlines()
                    if (m := re.match(r"^Time: ([\d.]+) ", line)) and float(m.group(1)) < 19]
        check("stable event prefix before h19", event_prefix(log), event_prefix(parent_log))
        allocated = mission_map(log, "mission allocates system: <TEACH-AIR-01,0>")
        started = mission_map(log, "mission starting, duration: 2 : <TEACH-AIR-01,0>")
        succeeded = mission_map(log, "mission success: ")
        completed = mission_map(log, "mission completed: <TEACH-AIR-01,0>")
        cancelled = mission_map(log, "mission cancelled: ")
        check("mission allocations", allocated, {0: 7.0, 1: 23.5, 2: 31.0})
        check("mission starts", started, {0: 8.0, 2: 32.0})
        check("mission successes/completions", [succeeded, completed], [{0: 10.0, 2: 34.0}] * 2)
        check("mission 1 cancellation", cancelled, {1: 24.8333})
        pm_start = pm_times(log, r"system PM task \d+ on <TEACH-AIR-01,0> started")
        pm_done = pm_times(log, r"system PM task \d+ on <TEACH-AIR-01,0> completed")
        sub_start = pm_times(log, r"subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours")
        sub_done = pm_times(log, r"subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed")
        check("PM/subtask starts", [pm_start, sub_start], [[24.0, 49.0]] * 2)
        check("PM/subtask completions", [pm_done, sub_done], [[25.0, 50.0]] * 2)
        check("booked aircraft enters PM at h24", "Time: 24 <TEACH-AIR-01,BASE-01,0> System to PM <TEACH-AIR-01,0>" in log, True)
        check("maintained aircraft ready at h25", "Time: 25 <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>" in log, True)
        check("PM-active mission cancellation ordering", 24.0 < cancelled.get(1, -1) < 25.0, True)

        report, parent_report = native_json(RUN / "report-raw.json"), native_json(PARENT_RUN / "report-raw.json")
        system, parent_system = table_rows(report, "SystemResults"), table_rows(parent_report, "SystemResults")
        stock, parent_stock = table_rows(report, "StockTotalResults"), table_rows(parent_report, "StockTotalResults")
        summary = table_rows(report, "ResultSummary")
        check("System/Stock 120 rows", [len(system), len(stock)], [120, 120])
        check("System/Stock field counts", [len(system[0]), len(stock[0])], [40, 16])
        check("System prefix through h19", [r for r in system if r["ETINT"] <= 19],
              [r for r in parent_system if r["ETINT"] <= 19])
        forms = {name: next(r for r in parent_system if r["STINT"] == t) for name, t in
                 (("ready", 18.5), ("reserved", 19.5), ("mission", 20.5), ("pm", 24.5))}
        states = {name: 0 for name in forms}
        for index, row in enumerate(system):
            t = index * .5
            check(f"System interval {index}", [row["STINT"], row["ETINT"]], [t, t + .5])
            active = [name for name, intervals in (
                ("reserved", [(7, 8), (23.5, 24), (31, 32)]),
                ("mission", [(8, 10), (32, 34)]),
                ("pm", [(24, 25), (49, 50)]))
                if any(start <= t < end for start, end in intervals)]
            check(f"one physical state at h{t}", len(active) <= 1, True)
            state = active[0] if active else "ready"
            states[state] += 1
            expected = dict(forms[state])
            expected.update(STINT=t, ETINT=t + .5, NPMS=int(t in pm_start),
                            NPMT=int(t in pm_done), NSYDT=int(t in pm_start),
                            SYDT=1 if t in pm_start else None)
            check(f"System field set h{t}", set(row), set(expected))
            for field, want in expected.items():
                check(f"System h{t} {field}", row[field], want, tolerance=5e-5)
        check("full-horizon state bins", states, {"ready": 103, "reserved": 5, "mission": 8, "pm": 4})
        for index, (row, control) in enumerate(zip(stock, parent_stock)):
            check(f"Stock interval {index}", [row["STINT"], row["ETINT"]], [index * .5, (index + 1) * .5])
            check(f"Stock field set {index}", set(row), set(control))
            for field, want in control.items():
                check(f"Stock row {index} {field}", row[field], want)
        expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 60,
                            "MTMF": 2 / 3, "RSMTMF": 0, "MSTF": 2 / 3,
                            "RSMSTF": 0, "MSUF": 2 / 3, "RSMSUF": 0,
                            "STMF": 2 / 3, "RSSTMF": 0}
        check("one summary row", len(summary), 1)
        check("summary field set", set(summary[0]), set(expected_summary))
        for field, want in expected_summary.items():
            check(f"summary {field}", summary[0][field], want, tolerance=3e-8)
        for field, want in (("NSYRY", 51.5), ("NSYA", 58), ("NSYMO", 4), ("NSYPM", 2), ("NSYMA", 6.5)):
            check(f"integrated {field}", sum(r[field] * .5 for r in system), want, tolerance=5e-5)
        check("PM start/completion report counters", [sum(r["NPMS"] for r in system), sum(r["NPMT"] for r in system)], [2, 2])
        check("zero failure/repair markers", all(r["NFAIL"] == 0 and r["NREPT"] == 0 for r in system), True)
        check("terminal ready/no PM/flight", [system[-1][k] for k in ("NSYRY", "NSYPM", "NSYMO")], [1, 0, 0])
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        checks.append({"name": "reanalysis exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d03-var02-v013-readonly-reanalysis/v1",
              "run_id": RUN.name, "passed": all(x["passed"] for x in checks),
              "checks_count": len(checks), "checks": checks,
              "scope": "one fixed-seed PM-first cancellation under the previously reviewed broad conflict branch",
              "prior_v012_mission_first_status": "NO_GO_FULL_CONTRACT",
              "publication_state": "candidate"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
