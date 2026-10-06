"""Strict read-only zero-return task and full-ledger check for A01."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A01-single-aircraft-single-mission"
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01/a01-bound-final-20260927-03")
PARENT_REPLAY = PARENT_RUN.parent / "a01-bound-replay-20260927-04"
SIBLINGS = (
    ("zero_outbound", ROOT / "A01-var01-zero-outbound-v0.1.0", "a01-var01-tfout0-v010-ssh-20261006-01",
     "ac0c134a34362c2cec6ec6c51a90b0f81a7d21b229e8ec76a2595a818d14e3ea",
     "26d2b99528992c630ea7c1fc875be161f63ed1d95dfc750196f6ddcbb73c3006",
     "0372f51f8dfe83f43e1b91ffb3f92ca2fc887fcbbdb20725ebb18ede51b6d91f",
     "ea378b70e1e5af5f37b47dc2dd20a4318943fdb24a1608745eccf549eda809af"),
    ("sum_one", ROOT / "A01-var01-sum-one-v0.1.0", "a01-var01-sum1-v010-ssh-20261006-01",
     "242d83ba901e7f64dc8a0ccefd4f5a405a51ede86359e240d4abb12bf543b1f9",
     "3dbc766842d988f03b6973337d0437db671c1a5e2a15ce5c5e18e5c7a3d97f51",
     "4ede9d1078be7c3e64d47def072615865914ed9cea9ce0cd1a52e581b259acf0",
     "3cf082ca278f91d4afb0b63b0a4bbc2de560e62c6574966e0fb67a62e4500b4e"),
)
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

INPUT_SHA = "66f2c6fc9d7e4438514f4965c968e0bc3d11db824fd5682f06d1e7362a1346ef"
PARENT_INPUT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
PARENT_SIGNOFF_SHA = "20ca6217068b2c6b998e70f26a82b065ebf6a15e555769c176baee204c137afa"
PARENT_INDEX_SHA = "2fe2383e513b0e59c581d5e7b48ec8da000a674a9f41e257b0e4f91836deb880"
PARENT_CLOSURE_SHA = "7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e"
PARENT_REPLAY_CLOSURE_SHA = "3781103d253f08c6d3f8f84572877f6b65319a18c10a9e40736e608f829811ee"
CONTRACT_SHA = "15afed5c5c0b344ecbbfb419a0c326dc4c5a0ed3ff8e4d180ca543b47079c987"
CONTRACT_REVIEW_SHA = "2ce4709094ddbe56f9553b7af3dcb1b637ee37e0e907430f0560eaca2413efdc"
RUN_ID = "a01-var01-tfret0-v010-ssh-20261006-01"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse(path: Path) -> dict:
    return json.loads(remove_trailing_commas(path.read_bytes()))

def table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    found = [t for t in doc["report"]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"report table count {name}: {len(found)}")
    columns = [column["name"] for column in found[0]["columns"]]
    rows = [row for instance in found[0]["instances"] for row in instance["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError(f"report table shape {name}")
    return columns, rows

def event_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()]

def timed(lines: list[str], fragment: str) -> list[tuple[float, str]]:
    found = []
    for line in lines:
        if fragment in line:
            match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s", line)
            if not match:
                raise ValueError(f"event lacks time: {line}")
            found.append((float(match.group(1)), line))
    return found

def run_checks(run: Path) -> dict:
    checks = []
    def ck(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    ck("accepted parent input SHA", sha(PARENT / "native-input.json"), PARENT_INPUT_SHA)
    ck("accepted parent signoff SHA", sha(PARENT / "cli-scope-signoff-2026-09-29.md"), PARENT_SIGNOFF_SHA)
    ck("accepted parent evidence index SHA", sha(PARENT / "evidence-index.json"), PARENT_INDEX_SHA)
    ck("contract SHA", sha(HERE / "contract.json"), CONTRACT_SHA)
    ck("independent contract GO SHA", sha(HERE / "review" / "independent-contract-go-2026-10-06.md"), CONTRACT_REVIEW_SHA)
    ck("child input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    ck("run input SHA", sha(run / "input.json"), INPUT_SHA)
    ck("parent closure SHA", sha(PARENT_RUN / "closure.json"), PARENT_CLOSURE_SHA)
    ck("parent replay closure SHA", sha(PARENT_REPLAY / "closure.json"), PARENT_REPLAY_CLOSURE_SHA)
    for label, sibling, sibling_run_id, input_sha, signoff_sha, index_sha, closure_sha in SIBLINGS:
        sibling_run = sibling / "runs" / sibling_run_id
        ck(f"{label} input SHA", sha(sibling / "native-input.json"), input_sha)
        ck(f"{label} signoff SHA", sha(sibling / "cli-scope-signoff-2026-10-06.md"), signoff_sha)
        ck(f"{label} index SHA", sha(sibling / "evidence-index.json"), index_sha)
        ck(f"{label} closure SHA", sha(sibling_run / "closure.json"), closure_sha)
        sibling_closure = parse(sibling_run / "closure.json")
        ck(f"{label} run identity", sibling_closure["run_id"], sibling_run_id)
        ck(f"{label} error", sibling_closure["error"], None)
        ck(f"{label} raw count", len(sibling_closure["raw"]), 12)
        for name, pin in sibling_closure["raw"].items():
            path = sibling_run / name
            ck(f"{label} raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    index = json.loads((PARENT / "evidence-index.json").read_text(encoding="utf-8-sig"))
    for parent_run in (PARENT_RUN, PARENT_REPLAY):
        parent_entry = [entry for entry in index["runs"] if entry["run_id"] == parent_run.name]
        ck(f"one accepted {parent_run.name} index entry", len(parent_entry), 1)
        if len(parent_entry) == 1:
            for name, pin in parent_entry[0]["artifacts"].items():
                path = parent_run / name
                ck(f"{parent_run.name} raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    closure = parse(run / "closure.json")
    invocation = parse(run / "invocation.json")
    ck("run identity", closure["run_id"], RUN_ID)
    ck("native closure error", closure["error"], None)
    ck("invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
    ck("before-after frozen source hashes", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("SSH session", invocation["session_id"], 0)
    ck("SSH ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    ck("serial queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    ck("protected GUI identity", [invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_unix_ms"]], [13340, 1, 1790590196826])
    ck("completed native steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in parse(run / "steps.json")],
       [(name, "completed", 0, True) for name in ("import", "export", "check_import_export", "calc", "jsonreport")])
    ck("raw count", len(closure["raw"]), 12)
    for name, pin in closure["raw"].items():
        path = run / name
        ck(f"child raw {name}", [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    roundtrip = parse(run / "roundtrip-validation.json")
    ck("exact import-export checker", roundtrip["passed"], True)
    ck("13 row-containing authored tables", len(roundtrip["authored_row_containing_tables"]), 13)
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    ck("converter warning numbers", re.findall(r"\(warning #(\d+)\)", log), ["108", "126"])
    ck("converter errors", re.findall(r"\(error #(\d+)\)", log), [])
    parent_lines, child_lines = event_lines(PARENT_RUN / "model.log"), event_lines(run / "model.log")
    parent_start = timed(parent_lines, "task starting: <TEACH-AIR-01,0>")
    child_start = timed(child_lines, "task starting: <TEACH-AIR-01,0>")
    ck("accepted parent task start", [x[0] for x in parent_start], [8.5])
    ck("child task start", [x[0] for x in child_start], [8.5])
    ck("child task start identity", len(child_start) == 1 and "<BASIC-MISSION,TEACH-UNIT,0,0,0>" in child_start[0][1], True)
    parent_completion = timed(parent_lines, "task completed: <TEACH-AIR-01,0>")
    child_completion = timed(child_lines, "task completed: <TEACH-AIR-01,0>")
    ck("accepted parent task completion", [x[0] for x in parent_completion], [9.5])
    ck("child task completion", [x[0] for x in child_completion], [10.0])
    ck("child task completion identity", len(child_completion) == 1 and "<BASIC-MISSION,TEACH-UNIT,0,0,0>" in child_completion[0][1], True)
    ck("child mission start", [x[0] for x in timed(child_lines, "mission starting, duration: 2 : <TEACH-AIR-01,0>")], [8.0])
    ck("child mission success", [x[0] for x in timed(child_lines, "mission success:")], [10.0])
    ck("child mission completed", [x[0] for x in timed(child_lines, "mission completed: <TEACH-AIR-01,0>")], [10.0])
    ck("child log except moved task completion", [line for line in child_lines if "task completed: <TEACH-AIR-01,0>" not in line],
       [line for line in parent_lines if "task completed: <TEACH-AIR-01,0>" not in line])
    parent_report, child_report = parse(PARENT_RUN / "report-raw.json"), parse(run / "report-raw.json")
    for table_name, expected_rows, expected_fields in (("SystemResults", 72, 40), ("StockTotalResults", 72, 16), ("ResultSummary", 1, 11)):
        parent_columns, parent_rows = table(parent_report, table_name)
        child_columns, child_rows = table(child_report, table_name)
        ck(f"{table_name} columns", child_columns, parent_columns)
        ck(f"{table_name} shape", [len(child_rows), len(child_columns)], [expected_rows, expected_fields])
        ck(f"{table_name} parent shape", [len(parent_rows), len(parent_columns)], [expected_rows, expected_fields])
        for row_index, (parent_row, child_row) in enumerate(zip(parent_rows, child_rows)):
            for field, before, after in zip(parent_columns, parent_row, child_row):
                ck(f"{table_name} row {row_index} {field}", after, before)
    failed = [c["name"] for c in checks if not c["passed"]]
    return {"schema": "simlox-a01-var01-zero-return-v010-native-validation/v1", "run_id": run.name,
            "passed": not failed, "checks_count": len(checks), "failed": failed,
            "checks": checks, "scope": "one TFOUT=0.25 TFRET=0 fixed-mission child against accepted A01 parent",
            "publication_state": "not_published"}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = run_checks(args.run)
    except Exception as exc:
        result = {"schema": "simlox-a01-var01-zero-return-v010-native-validation/v1", "run_id": args.run.name,
                  "passed": False, "checks_count": 0,
                  "failed": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
