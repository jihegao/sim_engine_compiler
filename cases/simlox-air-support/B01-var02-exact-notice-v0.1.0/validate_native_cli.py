"""Read-only exact-notice event and complete report ledger validator."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT_RUN = Path("C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06")
RUN_ID = "b01-var02-exact-notice-v010-ssh-20261006-01"
INPUT_SHA = "1dcf6977f769693bb4e69639cfeb3f53f4277e56b238250078dd452b686fb319"
PARENT_REPORT_SHA = "6e552899a0ef726891e4fabb03effc5cd25e9bc7fc38756da02bf231e1389f23"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    return json.loads(remove_trailing_commas(path.read_bytes()))


def table(report, name):
    found = [x for x in report["report"]["tables"] if x["name"] == name]
    if len(found) != 1:
        raise ValueError(f"report table count {name}: {len(found)}")
    columns = [x["name"] for x in found[0]["columns"]]
    rows = [row for ins in found[0]["instances"] for row in ins["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError(f"report table shape {name}")
    return columns, rows


def events(raw):
    result = []
    for number, line in enumerate(raw.splitlines(), 1):
        m = re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line)
        if m:
            result.append((float(m[1]), m[2].strip(), number))
    return result


def run_checks(run):
    checks = []

    def ck(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    contract = parse(HERE / "contract.json")
    ck("run identity", run.name, RUN_ID)
    ck("child source SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    ck("copied run input SHA", sha(run / "input.json"), INPUT_SHA)
    parent = contract["accepted_parent"]
    pp = ROOT / parent["package"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                      ("source_diff", "parent-diff.json"),
                      ("evidence", "evidence-2026-09-29.md"),
                      ("independent_verdict", "review/independent-readonly-rerun-2026-09-29.json")):
        ck(f"accepted B01 {key} SHA", sha(pp / name), parent[f"{key}_sha256"])
    ck("accepted B01 closure SHA", sha(PARENT_RUN / "closure.json"), parent["closure_sha256"])
    pc = parse(PARENT_RUN / "closure.json")
    ck("accepted B01 raw count", len(pc["raw"]), 11)
    for name, pin in pc["raw"].items():
        path = PARENT_RUN / name
        ck(f"accepted B01 raw {name}", [path.stat().st_size, sha(path)],
           [pin["bytes"], pin["sha256"]])
    a01 = contract["prerequisite_a01"]
    ap = ROOT / a01["package"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                      ("signoff", "cli-scope-signoff-2026-09-29.md"),
                      ("evidence_index", "evidence-index.json")):
        ck(f"accepted A01 {key} SHA", sha(ap / name), a01[f"{key}_sha256"])
    index = parse(ap / "evidence-index.json")
    ck("accepted A01 final/replay IDs", sorted(x["run_id"] for x in index["runs"]),
       sorted((a01["final_run_id"], a01["replay_run_id"])))
    for entry in index["runs"]:
        arun = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01") / entry["run_id"]
        key = "final_closure_sha256" if entry["run_id"] == a01["final_run_id"] else "replay_closure_sha256"
        ck(f"accepted A01 closure {entry['run_id']}", sha(arun / "closure.json"), a01[key])
        ck(f"accepted A01 raw count {entry['run_id']}", len(entry["artifacts"]), 17)
        for name, pin in entry["artifacts"].items():
            path = arun / name
            ck(f"accepted A01 raw {entry['run_id']}/{name}",
               [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])

    invocation, closure = parse(run / "invocation.json"), parse(run / "closure.json")
    ck("invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
    ck("closure run ID", closure["run_id"], RUN_ID)
    ck("native closure error", closure["error"], None)
    ck("source hashes stable", closure["source_hashes_after"], closure["source_hashes_before"])
    ck("SSH session", invocation["session_id"], 0)
    ck("SSH ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    ck("serial mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    ck("GUI PID/session/start", [invocation["gui"][x] for x in ("pid", "session_id", "start_unix_ms")],
       [13340, 1, 1790590196826])
    ck("five completed steps", [(x["name"], x["status"], x["exit_code"], x["gui_preserved"])
                                for x in parse(run / "steps.json")],
       [(name, "completed", 0, True) for name in
        ("import", "export", "check_import_export", "calc", "jsonreport")])
    ck("child raw count", len(closure["raw"]), 12)
    for name, pin in closure["raw"].items():
        path = run / name
        ck(f"child raw {name}", [path.stat().st_size, sha(path)],
           [pin["bytes"], pin["sha256"]])
    rt = parse(run / "roundtrip-validation.json")
    ck("roundtrip passed", rt["passed"], True)
    ck("15 authored populated tables", len(rt["authored_populated_tables"]), 15)
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter errors zero", re.findall(r"\(error #(\d+)\)", runlog), [])
    ck("converter summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, True)
    ck("known converter warnings", re.findall(r"\(warning #(\d+)\)", runlog), ["108", "126"])

    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    ev = events("\n".join(lines))
    ck("native horizon", lines[1], "36")
    ck("monotone event timestamps", all(ev[i][0] <= ev[i + 1][0] for i in range(len(ev) - 1)), True)
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    owner = "<TEACH-AIR-01,0>"
    wanted = [
        (7.5, "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        (7.5, f"{tag} mission created:"),
        (7.5, f"{tag} mission activated, systems requested: 1"),
        (7.5, f"{tag} mission allocates system: {owner}"),
        (7.5, f"{owner} preparation started, mission: {tag}"),
        (7.5, f"system preparation task 0 on {owner} started"),
        (7.5, f"subtask 0 seqno 0 within system preparation task 0 on {owner} starts performing, planned to last for 0.5 hours"),
        (8, f"subtask 0 seqno 0 within system preparation task 0 on {owner} completed"),
        (8, f"system preparation task 0 on {owner} completed"),
        (8, f"{owner} preparation ended, mission: {tag}"),
        (8, f"{tag} mission starting, duration: 2 : {owner}"),
        (8.5, f"{tag} task starting: {owner}"),
        (9.5, f"{tag} task completed: {owner}"),
        (10, f"{tag} mission success:"),
        (10, f"{tag} mission completed: {owner}"),
        (10, f"<TEACH-AIR-01,BASE-01,0> System arrives {owner}, mission success,")]
    positions = []
    for hour, body in wanted:
        found = [(t, n) for t, actual, n in ev if actual == body]
        ck(f"event {body}", [round(t, 5) for t, _ in found], [hour])
        positions.append(found[0][1] if len(found) == 1 else -1)
    ck("event sequence including h8 prep completion before launch", positions == sorted(positions) and -1 not in positions, True)
    ck("one mission launch", len([x for x in ev if " mission starting, duration:" in x[1]]), 1)
    ck("no cancellation/abort/delay", [x for x in ev if any(s in x[1] for s in
       (" mission cancelled:", " mission aborted:", " mission waiting:"))], [])
    ck("one physical aircraft", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])

    ck("accepted parent report SHA", sha(PARENT_RUN / "report-raw.json"), PARENT_REPORT_SHA)
    before, after = parse(PARENT_RUN / "report-raw.json"), parse(run / "report-raw.json")
    ck("report table names", sorted(x["name"] for x in after["report"]["tables"]),
       sorted(x["name"] for x in before["report"]["tables"]))
    for name, rows, cols in (("StockTotalResults", 72, 16), ("ResultSummary", 1, 11),
                             ("ProblemDescription", 1, 1)):
        bc, br = table(before, name)
        ac, ar = table(after, name)
        ck(f"{name} columns", ac, bc)
        ck(f"{name} shape", [len(ar), len(ac)], [rows, cols])
        for i, (old, new) in enumerate(zip(br, ar)):
            for field, expected, actual in zip(ac, old, new):
                ck(f"{name} row {i} {field}", actual, expected)
    bc, br = table(before, "SystemResults")
    ac, ar = table(after, "SystemResults")
    ck("SystemResults columns", ac, bc)
    ck("SystemResults shape", [len(ar), len(ac)], [72, 40])
    for i, row in enumerate(ar):
        template = list(br[0] if i == 14 else br[14] if i == 15 else br[i])
        if i == 16:
            template[ac.index("NPSUC")] = 1
        for field, actual, expected in zip(ac, row, template):
            if field == "STINT":
                expected = i * .5
            elif field == "ETINT":
                expected = (i + 1) * .5
            ck(f"SystemResults row {i} {field}", actual, expected)
    ck("physical preparation hours", sum(row[ac.index("NSYMP")] * .5 for row in ar), .5)
    ck("physical flight hours", sum(row[ac.index("FTMO")] * .5 for row in ar), 2)
    ck("terminal ready", ar[-1][ac.index("NSYRY")], 1)
    failed = [x["name"] for x in checks if not x["passed"]]
    return {"schema": "simlox-b01-var02-exact-notice-validation/v1", "run_id": run.name,
            "passed": not failed, "checks_count": len(checks), "failed": failed,
            "checks": checks, "publication_state": "not_published",
            "scope": "fixed-seed exact-notice boundary and complete report fields"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = run_checks(args.run)
    except Exception as exc:
        result = {"schema": "simlox-b01-var02-exact-notice-validation/v1", "run_id": args.run.name,
                  "passed": False, "checks_count": 0,
                  "failed": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
