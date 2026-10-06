"""Read-only A02 third-mission System cutoff and complete report reconciliation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1")
RUN_ID = "a02-var02-third-cutoff-v010-ssh-20261006-01"
INPUT_SHA = "f7a2ff367b2d34294a6a0393fa83d040c8d01b433fc09e9d720f7483baa8d716"
CONTRACT_SHA = "5feb16862f49421faf2b7a52ad58b321e39138f6b31d208de5edb0587df9b57e"
CONTRACT_REVIEW_SHA = "4562ec07297ce943b26c8137cbc3b907b2448156b9acb71043d98ff258b21de5"
sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    return json.loads(remove_trailing_commas(path.read_bytes()))


def report_table(report, name):
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"report table count {name}: {len(found)}")
    columns = [c["name"] for c in found[0]["columns"]]
    rows = [r for ins in found[0]["instances"] for r in ins["rows"]]
    if len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
        raise ValueError(f"report table shape {name}")
    return columns, rows


def event_times(lines, fragment):
    result = []
    for line in lines:
        if fragment in line:
            match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s", line)
            if not match:
                raise ValueError(f"event lacks time: {line}")
            result.append(float(match.group(1)))
    return result


def run_checks(run):
    checks = []

    def ck(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    contract = parse(HERE / "contract.json")
    ck("contract SHA", sha(HERE / "contract.json"), CONTRACT_SHA)
    ck("independent revised contract GO SHA", sha(HERE / "review/independent-contract-revision-go-2026-10-06.md"), CONTRACT_REVIEW_SHA)
    ck("frozen child input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    ck("run input SHA", sha(run / "input.json"), INPUT_SHA)
    for label, entry in (("A01", contract["prerequisite_a01"]), ("A02", contract["accepted_parent"])):
        folder = ROOT / entry["package"]
        for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                          ("signoff", "cli-scope-signoff-2026-09-29.md"),
                          ("evidence_index", "evidence-index.json")):
            ck(f"{label} {key} SHA", sha(folder / name), entry[f"{key}_sha256"])
        index = parse(folder / "evidence-index.json")
        expected_runs = {entry["final_run_id"]: entry["final_closure_sha256"],
                         entry["replay_run_id"]: entry["replay_closure_sha256"]}
        ck(f"{label} indexed runs", sorted(x["run_id"] for x in index["runs"]), sorted(expected_runs))
        for indexed in index["runs"]:
            raw_folder = RAW_ROOT / label / indexed["run_id"]
            ck(f"{label} closure {indexed['run_id']}", sha(raw_folder / "closure.json"),
               expected_runs[indexed["run_id"]])
            ck(f"{label} {indexed['run_id']} indexed raw count", len(indexed["artifacts"]), 17)
            for name, artifact in indexed["artifacts"].items():
                path = raw_folder / name
                ck(f"{label} {indexed['run_id']} raw {name}",
                   [path.stat().st_size, sha(path)], [artifact["bytes"], artifact["sha256"]])
    analogue = contract["accepted_j05_var05_analogue"]
    analogue_folder = ROOT / analogue["package"]
    analogue_run = analogue_folder / "runs" / analogue["run_id"]
    for label, path, key in (("input", analogue_folder / analogue["input_file"], "input_sha256"),
                             ("contract", analogue_folder / "contract.json", "contract_sha256"),
                             ("signoff", analogue_folder / "cli-scope-signoff-2026-10-01.md", "signoff_sha256"),
                             ("independent verdict", analogue_folder / "review/independent-readonly-2026-10-01.json", "independent_verdict_sha256"),
                             ("closure", analogue_run / "closure.json", "closure_sha256"),
                             ("event log", analogue_run / "model.log", "model_log_sha256"),
                             ("raw report", analogue_run / "report-raw.json", "report_raw_sha256")):
        ck(f"accepted J05 analogue {label} SHA", sha(path), analogue[key])
    jcols, jrows = report_table(parse(analogue_run / "report-raw.json"), "SystemResults")
    ck("accepted J05 analogue System shape", [len(jrows), len(jcols)], [18, 40])
    ck("accepted J05 analogue last System end", jrows[-1][jcols.index("ETINT")], 9)

    closure, invocation = parse(run / "closure.json"), parse(run / "invocation.json")
    ck("run identity", closure["run_id"], RUN_ID)
    ck("native closure error", closure["error"], None)
    ck("invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
    ck("frozen source hashes unchanged", closure["source_hashes_after"], closure["source_hashes_before"])
    ck("SSH session", invocation["session_id"], 0)
    ck("SSH ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    ck("serial queue", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    ck("protected GUI", [invocation["gui"][key] for key in ("pid", "session_id", "start_unix_ms")],
       [13340, 1, 1790590196826])
    ck("five completed steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                                for s in parse(run / "steps.json")],
       [(name, "completed", 0, True) for name in
        ("import", "export", "check_import_export", "calc", "jsonreport")])
    ck("child raw count", len(closure["raw"]), 12)
    for name, artifact in closure["raw"].items():
        path = run / name
        ck(f"child raw {name}", [path.stat().st_size, sha(path)],
           [artifact["bytes"], artifact["sha256"]])
    roundtrip = parse(run / "roundtrip-validation.json")
    ck("exact import-export checker", roundtrip["passed"], True)
    ck("13 row-containing authored tables", len(roundtrip["authored_row_containing_tables"]), 13)
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, True)
    ck("converter warnings", re.findall(r"\(warning #(\d+)\)", runlog), ["108", "126"])
    ck("converter errors", re.findall(r"\(error #(\d+)\)", runlog), [])
    parent_run = RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"]
    ck("accepted parent event log SHA", sha(parent_run / "model.log"),
       contract["accepted_parent"]["model_log_sha256"])
    ck("event log byte identity", sha(run / "model.log"), sha(parent_run / "model.log"))
    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    ck("native horizon", lines[1], "36")
    ck("mission starts", event_times(lines, " mission starting, duration: 2 : <TEACH-AIR-01,0>"),
       [8.0, 20.0, 32.0])
    ck("mission success", event_times(lines, " mission success:"), [10.0, 22.0, 34.0])
    ck("mission completion", event_times(lines, " mission completed:"), [10.0, 22.0, 34.0])
    ck("h34 return after collection end", event_times(lines, "System arrives <TEACH-AIR-01,0>, mission success"),
       [10.0, 22.0, 34.0])
    ck("one physical aircraft", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])
    parent_report, child_report = parse(parent_run / "report-raw.json"), parse(run / "report-raw.json")
    parent_names = sorted(t["name"] for t in parent_report["report"]["tables"])
    child_names = sorted(t["name"] for t in child_report["report"]["tables"])
    ck("report table names", child_names, parent_names)
    pc, pr = report_table(parent_report, "SystemResults")
    cc, cr = report_table(child_report, "SystemResults")
    ck("System columns", cc, pc)
    ck("System shapes", [len(cr), len(cc), len(pr), len(pc)], [66, 40, 72, 40])
    for i, (before, after) in enumerate(zip(pr[:66], cr)):
        for field, expected, actual in zip(pc, before, after):
            ck(f"System row {i} {field}", actual, expected)
    ck("System first start", cr[0][cc.index("STINT")], 0)
    ck("System last interval", [cr[-1][cc.index("STINT")], cr[-1][cc.index("ETINT")]], [32.5, 33.0])
    ck("System last interval in flight", cr[-1][cc.index("FTMO")], 1)
    for name, nrows, nfields in (("StockTotalResults", 72, 16),
                                 ("ResultSummary", 1, 11), ("ProblemDescription", 1, 1)):
        pc, pr = report_table(parent_report, name)
        cc, cr = report_table(child_report, name)
        ck(f"{name} columns", cc, pc)
        ck(f"{name} shape", [len(cr), len(cc), len(pr), len(pc)],
           [nrows, nfields, nrows, nfields])
        for i, (before, after) in enumerate(zip(pr, cr)):
            for field, expected, actual in zip(pc, before, after):
                ck(f"{name} row {i} {field}", actual, expected)
    failures = [item["name"] for item in checks if not item["passed"]]
    return {"schema": "simlox-a02-var02-third-cutoff-v010-native-validation/v1",
            "run_id": run.name, "passed": not failures, "checks_count": len(checks),
            "failed": failures, "checks": checks, "publication_state": "not_published",
            "scope": "one fixed A02 third-mission System cutoff with complete retained and truncated report ledger"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = run_checks(args.run)
    except Exception as exc:
        result = {"schema": "simlox-a02-var02-third-cutoff-v010-native-validation/v1",
                  "run_id": args.run.name, "passed": False, "checks_count": 0,
                  "failed": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
