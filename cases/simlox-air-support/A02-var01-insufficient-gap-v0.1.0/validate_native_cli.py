"""Read-only A02 insufficient-gap cancellation and full-ledger check."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
A01 = ROOT / "A01-single-aircraft-single-mission"
A02 = ROOT / "A02-single-aircraft-repeated-missions"
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1")
RUN_ID = "a02-var01-insufficient-gap-v010-ssh-20261006-01"
INPUT_SHA = "df7d693e7364c50d489723c2d4c336c1225959e1e03cfb6535f82d9cf32a2109"
CONTRACT_SHA = "de070694526da7d99f114aeb7fec5a979728912fd9a99aa1519fca528917fa8a"
CONTRACT_REVIEW_SHA = "3e5d37321ea78a746a0e7b18ac3d2470b0a13d52508644a749dd40b13eb6e0d3"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))

def report_table(report: dict, name: str) -> tuple[list[str], list[list]]:
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"report table count {name}: {len(found)}")
    columns = [c["name"] for c in found[0]["columns"]]
    rows = [r for ins in found[0]["instances"] for r in ins["rows"]]
    if len(columns) != len(set(columns)) or any(len(r) != len(columns) for r in rows):
        raise ValueError(f"report table shape {name}")
    return columns, rows

def event_times(lines: list[str], fragment: str) -> list[float]:
    values = []
    for line in lines:
        if fragment in line:
            match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s", line)
            if not match:
                raise ValueError(f"event lacks time: {line}")
            values.append(float(match.group(1)))
    return values

def run_checks(run: Path) -> dict:
    checks: list[dict] = []
    def ck(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    contract = parse(HERE / "contract.json")
    ck("contract SHA", sha(HERE / "contract.json"), CONTRACT_SHA)
    ck("independent contract GO SHA", sha(HERE / "review/independent-contract-go-2026-10-06.md"), CONTRACT_REVIEW_SHA)
    ck("child source SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    ck("run source SHA", sha(run / "input.json"), INPUT_SHA)
    sibling = contract["published_at_return_sibling"]
    sibling_folder = ROOT / sibling["package"]
    sibling_run = sibling_folder / "runs" / sibling["run_id"]
    ck("published sibling input SHA", sha(sibling_folder / "native-input.json"), sibling["input_sha256"])
    ck("published sibling index SHA", sha(sibling_folder / "evidence-index.json"), sibling["evidence_index_sha256"])
    ck("published sibling verdict SHA", sha(sibling_folder / "review/independent-verdict.json"), sibling["independent_verdict_sha256"])
    ck("published sibling closure SHA", sha(sibling_run / "closure.json"), sibling["closure_sha256"])
    sibling_closure = parse(sibling_run / "closure.json")
    ck("published sibling raw count", len(sibling_closure["raw"]), 12)
    for name, pin in sibling_closure["raw"].items():
        path = sibling_run / name
        ck(f"published sibling raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    for label, package, entry in (("A01", A01, contract["prerequisite_a01"]),
                                  ("A02", A02, contract["accepted_parent"])):
        for name, file in (("input", "native-input.json"), ("contract", "contract.json"),
                           ("signoff", "cli-scope-signoff-2026-09-29.md"),
                           ("evidence_index", "evidence-index.json")):
            ck(f"{label} {name} SHA", sha(package / file), entry[f"{name}_sha256"])
        index = parse(package / "evidence-index.json")
        ck(f"{label} two accepted runs", len(index["runs"]), 2)
        expected_runs = {entry["final_run_id"]: entry["final_closure_sha256"],
                         entry["replay_run_id"]: entry["replay_closure_sha256"]}
        ck(f"{label} run IDs", sorted(x["run_id"] for x in index["runs"]), sorted(expected_runs))
        for indexed in index["runs"]:
            raw_folder = RAW_ROOT / label / indexed["run_id"]
            ck(f"{label} closure {indexed['run_id']}", sha(raw_folder / "closure.json"),
               expected_runs[indexed["run_id"]])
            ck(f"{label} {indexed['run_id']} indexed raw count", len(indexed["artifacts"]), 17)
            for name, pin in indexed["artifacts"].items():
                path = raw_folder / name
                ck(f"{label} {indexed['run_id']} raw {name}",
                   [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])

    closure = parse(run / "closure.json")
    invocation = parse(run / "invocation.json")
    ck("run identity", closure["run_id"], RUN_ID)
    ck("native closure error", closure["error"], None)
    ck("invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
    ck("frozen sources unchanged", closure["source_hashes_after"], closure["source_hashes_before"])
    ck("SSH session", invocation["session_id"], 0)
    ck("SSH ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    ck("serial queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    ck("protected GUI", [invocation["gui"][k] for k in ("pid", "session_id", "start_unix_ms")],
       [13340, 1, 1790590196826])
    ck("five completed steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                                for s in parse(run / "steps.json")],
       [(n, "completed", 0, True) for n in
        ("import", "export", "check_import_export", "calc", "jsonreport")])
    ck("child raw count", len(closure["raw"]), 12)
    for name, pin in closure["raw"].items():
        path = run / name
        ck(f"child raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    roundtrip = parse(run / "roundtrip-validation.json")
    ck("exact import-export checker", roundtrip["passed"], True)
    ck("13 row-containing authored tables", len(roundtrip["authored_row_containing_tables"]), 13)
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    ck("converter warnings", re.findall(r"\(warning #(\d+)\)", log), ["108", "126"])
    ck("converter errors", re.findall(r"\(error #(\d+)\)", log), [])

    parent_lines = (RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"] / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    ck("mission notices", event_times(lines, "mission ordered: BASIC-MISSION"), [7.0, 8.5, 31.0])
    for identity, start, finish in ((0, 8.0, 10.0), (2, 32.0, 34.0)):
        tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{identity}>"
        ck(f"mission {identity} created", event_times(lines, tag + " mission created:"), [start - 1])
        ck(f"mission {identity} launch", event_times(lines, tag + " mission starting, duration: 2 : <TEACH-AIR-01,0>"), [start])
        ck(f"mission {identity} task start", event_times(lines, tag + " task starting: <TEACH-AIR-01,0>"), [start + .5])
        ck(f"mission {identity} task completion", event_times(lines, tag + " task completed: <TEACH-AIR-01,0>"), [finish - .5])
        ck(f"mission {identity} success", event_times(lines, tag + " mission success:"), [finish])
        ck(f"mission {identity} completed", event_times(lines, tag + " mission completed: <TEACH-AIR-01,0>"), [finish])
        ck(f"unchanged mission {identity} event lines", [line for line in lines if tag in line],
           [line for line in parent_lines if tag in line])
    second = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
    ck("second mission created", event_times(lines, second + " mission created:"), [8.5])
    ck("second mission requests one aircraft", event_times(lines, second + " mission activated, systems requested: 1"), [8.5])
    waiting = [line for line in lines if second + " mission waiting:" in line]
    ck("second mission waiting count", len(waiting), 1)
    ck("second waiting deadline recorded", len(waiting) == 1 and
       re.search(r"timeout at 9\.8333(?:3)?\b", waiting[0]) is not None, True)
    cancellation = event_times(lines, second + " mission cancelled:")
    ck("second mission cancellation count", len(cancellation), 1)
    ck("second mission cancelled at deferment deadline", len(cancellation) == 1 and abs(cancellation[0] - (9.5 + 1/3)) < 0.0001, True)
    ck("second mission no launch/task/success", [line for line in lines if second in line and any(x in line for x in
       (" mission starting", " task starting", " task completed", " mission success:", " mission completed:"))], [])
    ck("only expected cancellation", [line for line in lines if "mission cancelled:" in line],
       [line for line in lines if second + " mission cancelled:" in line])
    ck("exactly two physical mission successes", len(event_times(lines, " mission success:")), 2)
    ck("exactly two physical mission completions", len(event_times(lines, " mission completed:")), 2)
    ck("one physical aircraft only", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])
    ck("deadline precedes first return", len(cancellation) == 1 and cancellation[0] < 10.0, True)

    parent_report = parse(RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"] / "report-raw.json")
    child_report = parse(run / "report-raw.json")
    pcols, prows = report_table(parent_report, "SystemResults")
    ccols, crows = report_table(child_report, "SystemResults")
    ck("System columns", ccols, pcols)
    ck("System shapes", [len(crows), len(ccols), len(prows), len(pcols)], [72, 40, 72, 40])
    templates = {"ready": prows[0], "reserved": prows[14], "flight": prows[16]}
    def expected_state(t):
        if 8 <= t < 10 or 32 <= t < 34:
            return "flight"
        if 7 <= t < 8 or 31 <= t < 32:
            return "reserved"
        return "ready"
    for i, row in enumerate(crows):
        t = i / 2
        template = templates[expected_state(t)]
        for field, actual, expected in zip(ccols, row, template):
            if field == "STINT": expected = t
            if field == "ETINT": expected = t + .5
            ck(f"System row {i} {field}", actual, expected)
    ck("ready-hour integral", sum(row[ccols.index("NSYRY")] * .5 for row in crows), 30.0)
    ck("flight-hour integral", sum(row[ccols.index("FTMO")] * .5 for row in crows), 4.0)
    ck("terminal ready", crows[-1][ccols.index("NSYRY")], 1)
    for name, nrows, nfields in (("StockTotalResults", 72, 16), ("ResultSummary", 1, 11)):
        pc, pr = report_table(parent_report, name)
        cc, cr = report_table(child_report, name)
        ck(f"{name} columns", cc, pc)
        ck(f"{name} shape", [len(cr), len(cc), len(pr), len(pc)], [nrows, nfields, nrows, nfields])
        for i, (before, after) in enumerate(zip(pr, cr)):
            for field, expected, actual in zip(pc, before, after):
                ck(f"{name} row {i} {field}", actual, expected)
    failures = [c["name"] for c in checks if not c["passed"]]
    return {"schema": "simlox-a02-var01-insufficient-gap-v010-native-validation/v1",
            "run_id": run.name, "passed": not failures, "checks_count": len(checks),
            "failed": failures, "checks": checks, "publication_state": "not_published",
            "scope": "one fixed h9.5 mission timeout before h10 return, two sorties and full report ledgers"}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = run_checks(args.run)
    except Exception as exc:
        result = {"schema": "simlox-a02-var01-insufficient-gap-v010-native-validation/v1",
                  "run_id": args.run.name, "passed": False, "checks_count": 0,
                  "failed": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
