"""Versioned read-only replay of sealed D04.var01 OPHOURS=2 native evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

NEW = Path(__file__).resolve().parent
HERE = NEW.parent / "D04-var01-over-threshold-v0.2.0"
ROOT = HERE.parent
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d04-flight-v100-ssh-20260930-01"
SIBLING = ROOT / "D04-var01-threshold-not-reached-v0.1.1"
SIBLING_RUN = SIBLING / "runs" / "d04-var01-op4-v011-ssh-20261006-01"
RUN_ID = "d04-var01-op2-v020-ssh-20261006-01"
INPUT_SHA = "35866de7c9414c9dc39e75416c3464ec00b1d6c5d2f987749c428323dc57e092"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def native(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))

def rows(doc: dict, name: str) -> list[dict]:
    result = [t for t in doc["report"]["tables"] if t["name"] == name]
    if len(result) != 1:
        raise ValueError(f"report table {name} count {len(result)}")
    table = result[0]
    cols = [c["name"] for c in table["columns"]]
    if len(cols) != len(set(cols)):
        raise ValueError(f"duplicate report columns {name}")
    values = [r for inst in table["instances"] for r in inst["rows"]]
    if any(len(r) != len(cols) for r in values):
        raise ValueError(f"nonrectangular report table {name}")
    return [dict(zip(cols, r)) for r in values]

def cells(doc: dict) -> dict:
    found = {}
    for table in doc["model"]["tables"]:
        cols = [c["name"] for c in table["columns"]]
        for i, inst in enumerate(table["instances"]):
            for j, row in enumerate(inst["rows"]):
                if len(row) != len(cols):
                    raise ValueError(f"nonrectangular source {table['name']}")
                for col, value in zip(cols, row):
                    key = (table["name"], i, j, col)
                    if key in found:
                        raise ValueError(f"duplicate source cell {key}")
                    found[key] = value
    return found

def diagnostic(value):
    """Make check records JSON-safe without changing any comparison."""
    if isinstance(value, dict):
        return {repr(key) if not isinstance(key, str) else key: diagnostic(item)
                for key, item in value.items()}
    if isinstance(value, set):
        return sorted((diagnostic(item) for item in value), key=repr)
    if isinstance(value, (tuple, list)):
        return [diagnostic(item) for item in value]
    return value

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=HERE / "runs" / RUN_ID)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--parent-negative-control", action="store_true")
    args = ap.parse_args()
    if args.parent_negative_control:
        c = load(PARENT_RUN / "closure.json")
        assert sha(PARENT_RUN / "closure.json") == "3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45"
        assert len(c["raw"]) == 12
        for name, pin in c["raw"].items():
            p = PARENT_RUN / name
            assert p.stat().st_size == pin["bytes"] and sha(p) == pin["sha256"]
        r = rows(native(PARENT_RUN / "report-raw.json"), "SystemResults")
        result = {"schema": "simlox-d04-var01-v020-parent-negative-control/v1", "passed": False,
                  "parent_run_id": PARENT_RUN.name, "rejected_by_early_pm_gate":
                  [r[20]["NPMS"], r[20]["NSYPM"], r[82]["NPMS"], r[82]["NSYPM"]] == [0, 0, 1, 1],
                  "observed_h10_pm_start_occupancy": [r[20]["NPMS"], r[20]["NSYPM"]],
                  "observed_h41_pm_start_occupancy": [r[82]["NPMS"], r[82]["NSYPM"]],
                  "child_requires_h10_pm_and_h41_ready": True}
        data = (json.dumps(result, indent=2) + "\n").encode()
        (args.output.write_bytes(data) if args.output else sys.stdout.buffer.write(data))
        return 1
    checks = []
    def check(name: str, got, want, tol: float | None = None):
        passed = abs(got - want) <= tol if tol is not None else got == want
        checks.append({"name": name, "passed": passed,
                       "actual": diagnostic(got), "expected": diagnostic(want)})
    try:
        review_contract = load(NEW / "contract.json")
        check("read-only contract version", review_contract["version"], "0.2.1-readonly-candidate")
        check("read-only contract SHA", sha(NEW / "contract.json"), "0d1b6b38d631413811b76596104afb2f67e15f77ceeb392ed5c8ece8317af355")
        check("read-only independent contract GO", sha(NEW / "review" / "independent-contract-go-2026-10-06.md"),
              "7b30f882d75eb7f88957de5f1f384f2b87fd48aed7c2862cf023b8a0a42cdd3a")
        sealed = review_contract["sealed_run"]
        failed = review_contract["preserved_failed_author"]
        for name, path, expected in (
            ("original contract", HERE / "contract.json", sealed["contract_sha256"]),
            ("original input", HERE / "native-input.json", sealed["input_sha256"]),
            ("original closure", HERE / "runs" / RUN_ID / "closure.json", sealed["closure_sha256"]),
            ("original frozen validator", HERE / "validate_native_cli.py", failed["original_validator_sha256"]),
            ("original failed serialization log", HERE / "review" / "failed-author-serialization-2026-10-06.txt", failed["failure_log_sha256"]),
            ("original independent prelaunch GO", HERE / "review" / "independent-prelaunch-go-2026-10-06.md", failed["original_prelaunch_go_sha256"]),
        ):
            check(name + " SHA", sha(path), expected)
        c = load(HERE / "contract.json")
        check("contract version", c["version"], "0.2.0-contract-candidate")
        check("run id", args.run.name, RUN_ID)
        for name, path, expected in (
            ("D04 input", PARENT / "native-input.json", c["accepted_parent"]["input_sha256"]),
            ("D04 signoff", PARENT / "cli-scope-signoff-2026-09-30.md", c["accepted_parent"]["signoff_sha256"]),
            ("D04 closure", PARENT_RUN / "closure.json", c["accepted_parent"]["closure_sha256"]),
            ("sibling input", SIBLING / "native-input.json", c["accepted_sibling_below_threshold"]["input_sha256"]),
            ("sibling signoff", SIBLING / "cli-scope-signoff-2026-10-06.md", c["accepted_sibling_below_threshold"]["signoff_sha256"]),
            ("sibling evidence index", SIBLING / "evidence-index.json", c["accepted_sibling_below_threshold"]["evidence_index_sha256"]),
            ("D03 input", ROOT / c["instructional_prerequisite"]["package"] / "native-input.json", c["instructional_prerequisite"]["input_sha256"]),
            ("D03 signoff", ROOT / c["instructional_prerequisite"]["package"] / "cli-scope-signoff-2026-09-30.md", c["instructional_prerequisite"]["signoff_sha256"]),
            ("manual", Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"), c["source"]["manual_pdf_sha256"]),
            ("executable", Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"), c["source"]["native_executable_sha256"]),
            ("child input", HERE / "native-input.json", INPUT_SHA),
        ):
            check(name + " SHA", sha(path), expected)
        for role, folder, expected_closure in (
            ("parent", PARENT_RUN, c["accepted_parent"]["closure_sha256"]),
            ("sibling", SIBLING_RUN, "98d30d678431fb8ce6661b2cac2b5a3681b226bca32a8076c7eac8899e18dea0"),
        ):
            check(role + " closure SHA", sha(folder / "closure.json"), expected_closure)
            closure = load(folder / "closure.json")
            check(role + " raw count", len(closure["raw"]), 12)
            for name, pin in closure["raw"].items():
                p = folder / name
                check(role + " raw " + name, [p.stat().st_size, sha(p)], [pin["bytes"], pin["sha256"]])
        parent_source, child_source = native(PARENT / "native-input.json"), native(HERE / "native-input.json")
        old, new = cells(parent_source), cells(child_source)
        check("221 source cells", len(old), 221)
        check("source keys", set(new), set(old))
        check("sole source delta", {k: (old[k], new[k]) for k in old if old[k] != new[k]},
              {("MaterielPM", 0, 0, "PMINT"): (3.0, 2.0)})
        run = args.run
        closure, invocation = load(run / "closure.json"), load(run / "invocation.json")
        check("closure complete/run", [closure["error"], closure["run_id"]], [None, RUN_ID])
        check("invocation SHA", sha(run / "invocation.json"), closure["invocation_sha256"])
        check("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
        check("child input/parent/sibling/D03/exe pins", [closure["source_hashes_before"][k] for k in
              ("input", "parent", "sibling_input", "d03_input", "simlox_exe")],
              [INPUT_SHA, c["accepted_parent"]["input_sha256"], c["accepted_sibling_below_threshold"]["input_sha256"],
               c["instructional_prerequisite"]["input_sha256"], c["source"]["native_executable_sha256"]])
        check("12 child raw", len(closure["raw"]), 12)
        for name, pin in closure["raw"].items():
            p = run / name
            check("child raw " + name, [p.stat().st_size, sha(p)], [pin["bytes"], pin["sha256"]])
        check("SSH ancestry", [invocation["session_id"], invocation["ssh_connection_present"],
                               "sshd.exe" in invocation["ssh_ancestor_names"]], [0, True, True])
        check("GUI identity", invocation["gui"], {"pid": 13340, "session_id": 1,
              "start_utc": "2026-09-28T10:09:56.8261381Z"})
        check("mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        steps = load(run / "steps.json")
        check("five steps", [x["name"] for x in steps], ["import", "export", "check_import_export", "calc", "jsonreport"])
        check("all steps/GUI complete", all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps), True)
        check("copied input", sha(run / "input.json"), INPUT_SHA)
        roundtrip = load(run / "roundtrip-validation.json")
        check("18-table roundtrip", [roundtrip["passed"], len(roundtrip["authored_row_containing_tables"])], [True, 18])
        converter = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("converter 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
        check("warnings 108/126", sorted(re.findall(r"\(warning #(\d+)\)", converter)), ["108", "126"])
        parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        def prefix(s: str) -> list[str]:
            return [line for line in s.splitlines() if (m := re.match(r"^Time: ([\d.]+) ", line)) and float(m.group(1)) < 10]
        check("event prefix before h10", prefix(log), prefix(parent_log))
        def event_times(s: str, phrase: str) -> list[float]:
            return [float(m.group(1)) for line in s.splitlines()
                    if (m := re.match(r"^Time: ([\d.]+) (.*)$", line)) and phrase in m.group(2)]
        check("mission starts", event_times(log, "mission starting, duration:"), [8.0, 40.0])
        check("mission success", event_times(log, "mission success: "), [10.0, 41.0])
        check("mission completed", event_times(log, "mission completed: <TEACH-AIR-01,0>"), [10.0, 41.0])
        check("physical aircraft mission identity", len(re.findall(r"mission starting, duration: [12] : <TEACH-AIR-01,0>", log)), 2)
        check("no mission cancellation", event_times(log, "mission cancelled"), [])
        def exact_times(s: str, suffix: str) -> list[float]:
            return [float(m.group(1)) for line in s.splitlines()
                    if (m := re.match(r"^Time: ([\d.]+) (.*)$", line)) and m.group(2).strip() == suffix]
        check("sole PM task start/end", [exact_times(log, "system PM task 0 on <TEACH-AIR-01,0> started"),
                                         exact_times(log, "system PM task 0 on <TEACH-AIR-01,0> completed")], [[10.0], [11.0]])
        check("sole PM subtask start/end", [exact_times(log, "subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> started"),
                                            exact_times(log, "subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> completed")], [[10.0], [11.0]])
        check("no second PM task", len(re.findall(r"^Time: [\d.]+  system PM task \d+ on .* started$", log, re.M)), 1)
        report, parent_report = native(run / "report-raw.json"), native(PARENT_RUN / "report-raw.json")
        system, p_system = rows(report, "SystemResults"), rows(parent_report, "SystemResults")
        stock, p_stock = rows(report, "StockTotalResults"), rows(parent_report, "StockTotalResults")
        summary, p_summary = rows(report, "ResultSummary"), rows(parent_report, "ResultSummary")
        check("120 System/Stock and summary", [len(system), len(stock), len(summary), len(p_system), len(p_stock), len(p_summary)], [120,120,1,120,120,1])
        check("field widths", [len(system[0]), len(stock[0]), len(summary[0])], [40,16,11])
        for i, row in enumerate(system):
            want = dict(p_system[i])
            if i in (20, 21):
                for field in ("NSYRY", "NSYA", "NSYUA", "NSYPM", "NPMS", "NPMT", "SYDT", "NSYDT"):
                    want[field] = p_system[i + 62][field]
            elif i == 22:
                want["NPMT"] = 1
            elif i in (82, 83):
                for field in ("NSYRY", "NSYA", "NSYUA", "NSYPM", "NPMS", "NPMT", "SYDT", "NSYDT"):
                    want[field] = p_system[22][field] if field != "NPMT" else 0
            elif i == 84:
                want["NPMT"] = 0
            check(f"System field set {i}", set(row), set(want))
            for field, expected in want.items():
                check(f"System row {i} {field}", row[field], expected, tol=5e-5 if isinstance(expected, float) else None)
        for i, (row, want) in enumerate(zip(stock, p_stock)):
            check(f"Stock field set {i}", set(row), set(want))
            for field, expected in want.items():
                check(f"Stock row {i} {field}", row[field], expected)
        check("summary field set", set(summary[0]), set(p_summary[0]))
        for field, expected in p_summary[0].items():
            check("summary " + field, summary[0][field], expected, tol=3e-8 if isinstance(expected, float) else None)
        for field, expected in (("NSYRY",54),("NSYA",59),("NSYMO",3),("NSYPM",1)):
            check("integrated " + field, sum(r[field] * .5 for r in system), expected, tol=5e-5)
        check("PM starts/completes", [sum(r["NPMS"] for r in system), sum(r["NPMT"] for r in system)], [1,1])
        check("terminal ready/no PM/flight", [system[-1][k] for k in ("NSYRY","NSYPM","NSYMO")], [1,0,0])
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        checks.append({"name": "validation exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})
    result = {"schema": "simlox-d04-var01-v021-readonly-validation/v1", "run_id": args.run.name,
              "passed": all(x["passed"] for x in checks), "checks_count": len(checks), "checks": checks,
              "scope": "one OPHOURS2 child against accepted OPHOURS3 parent and OPHOURS4 sibling",
              "human_label_note": "PMID OP3 and historical description are retained labels; numeric PMINT2 is authoritative",
              "publication_state": "not_published"}
    data = (json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(data)
    else:
        sys.stdout.buffer.write(data)
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
