"""Read-only A02 same-time competition and complete ledger validation."""
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
RUN_ID = "a02-var03-same-time-v010-ssh-20261006-01"
INPUT_SHA = "856b7e60086b2b2983245a117601bde35392801fea97f109164fb4364bec8a76"
CONTRACT_SHA = "e9792037600763ee8309b77bb6622a975830ab80332652ad026e240ed4985d47"
CONTRACT_REVIEW_SHA = "3dd392712a0e2a9882d4ea6ac220f3e7011eedfa3b3240e6ae6d3b7c1d708f1b"
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


def times(lines, fragment):
    found = []
    for line in lines:
        if fragment in line:
            match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s", line)
            if not match:
                raise ValueError(f"event lacks time: {line}")
            found.append(float(match.group(1)))
    return found


def run_checks(run):
    checks = []

    def ck(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected,
                       "actual": actual, "expected": expected})

    contract = parse(HERE / "contract.json")
    ck("contract SHA", sha(HERE / "contract.json"), CONTRACT_SHA)
    ck("independent contract GO SHA", sha(HERE / "review/independent-contract-go-2026-10-06.md"), CONTRACT_REVIEW_SHA)
    ck("child input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    ck("run input SHA", sha(run / "input.json"), INPUT_SHA)
    for label, entry in (("A01", contract["prerequisite_a01"]), ("A02", contract["accepted_parent"])):
        folder = ROOT / entry["package"]
        for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                          ("signoff", "cli-scope-signoff-2026-09-29.md"),
                          ("evidence_index", "evidence-index.json")):
            ck(f"{label} {key} SHA", sha(folder / name), entry[f"{key}_sha256"])
        index = parse(folder / "evidence-index.json")
        expected = {entry["final_run_id"]: entry["final_closure_sha256"],
                    entry["replay_run_id"]: entry["replay_closure_sha256"]}
        ck(f"{label} indexed run IDs", sorted(x["run_id"] for x in index["runs"]), sorted(expected))
        for indexed in index["runs"]:
            raw = RAW_ROOT / label / indexed["run_id"]
            ck(f"{label} closure {indexed['run_id']}", sha(raw / "closure.json"), expected[indexed["run_id"]])
            ck(f"{label} indexed raw count {indexed['run_id']}", len(indexed["artifacts"]), 17)
            for name, pin in indexed["artifacts"].items():
                path = raw / name
                ck(f"{label} {indexed['run_id']} raw {name}",
                   [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    analogue = contract["accepted_cancellation_analogue"]
    afolder = ROOT / analogue["package"]
    arun = afolder / "runs" / analogue["run_id"]
    for label, path, key in (("input", afolder / "native-input.json", "input_sha256"),
                             ("contract", afolder / "contract.json", "contract_sha256"),
                             ("signoff", afolder / "cli-scope-signoff-2026-10-06.md", "signoff_sha256"),
                             ("index", afolder / "evidence-index.json", "evidence_index_sha256"),
                             ("verdict", afolder / "review/independent-verdict.json", "independent_verdict_sha256"),
                             ("closure", arun / "closure.json", "closure_sha256")):
        ck(f"accepted cancellation analogue {label} SHA", sha(path), analogue[key])
    ac = parse(arun / "closure.json")
    ck("accepted cancellation analogue raw count", len(ac["raw"]), 12)
    for name, pin in ac["raw"].items():
        path = arun / name
        ck(f"accepted cancellation analogue raw {name}",
           [path.stat().st_size, sha(path)], [pin["bytes"], pin["sha256"]])
    alines = (arun / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    ck("accepted analogue second cancellation", times(alines, ",0,0,1> mission cancelled:"), [9.83333])

    closure, invocation = parse(run / "closure.json"), parse(run / "invocation.json")
    ck("run identity", closure["run_id"], RUN_ID)
    ck("native closure error", closure["error"], None)
    ck("invocation SHA", closure["invocation_sha256"], sha(run / "invocation.json"))
    ck("frozen source hashes unchanged", closure["source_hashes_after"], closure["source_hashes_before"])
    ck("SSH session", invocation["session_id"], 0)
    ck("SSH ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    ck("serial mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
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
    ck("roundtrip passed", roundtrip["passed"], True)
    ck("13 authored populated tables", len(roundtrip["authored_row_containing_tables"]), 13)
    raw_roundtrip = parse(run / "roundtrip-raw.json")
    profile = [x for x in raw_roundtrip["model"]["tables"] if x["name"] == "OperationProfile"]
    ck("one roundtrip OperationProfile table", len(profile), 1)
    if len(profile) == 1:
        cols = [x["name"] for x in profile[0]["columns"]]
        rows = profile[0]["instances"][0]["rows"]
        ck("three duplicate-key-preserved profile rows", len(rows), 3)
        ck("same-time first two profile keys", [(row[cols.index("PRID")], row[cols.index("SPRID")],
                                                   row[cols.index("STIM")]) for row in rows],
           [("BASIC-SCHEDULE", "BASIC-MISSION", 8), ("BASIC-SCHEDULE", "BASIC-MISSION", 8),
            ("BASIC-SCHEDULE", "BASIC-MISSION", 32)])
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    ck("converter warnings", re.findall(r"\(warning #(\d+)\)", log), ["108", "126"])
    ck("converter errors", re.findall(r"\(error #(\d+)\)", log), [])

    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    ck("native horizon", lines[1], "36")
    ck("two early and one late notices", times(lines, " mission ordered: BASIC-MISSION"), [7, 7, 31])
    early = {}
    for identity in (0, 1):
        tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{identity}>"
        ck(f"early {identity} created", times(lines, tag + " mission created:"), [7])
        ck(f"early {identity} activated", times(lines, tag + " mission activated, systems requested: 1"), [7])
        early[identity] = {"start": times(lines, tag + " mission starting, duration: 2 : <TEACH-AIR-01,0>"),
                           "success": times(lines, tag + " mission success:"),
                           "complete": times(lines, tag + " mission completed: <TEACH-AIR-01,0>"),
                           "cancel": times(lines, tag + " mission cancelled:"),
                           "wait": [line for line in lines if tag + " mission waiting:" in line],
                           "task_start": times(lines, tag + " task starting: <TEACH-AIR-01,0>"),
                           "task_complete": times(lines, tag + " task completed: <TEACH-AIR-01,0>")}
    winners = [i for i in (0, 1) if early[i]["start"] == [8]]
    losers = [i for i in (0, 1) if len(early[i]["cancel"]) == 1]
    ck("one early h8 winner", len(winners), 1)
    ck("one distinct early cancellation", len(losers) == 1 and losers != winners, True)
    if len(winners) == len(losers) == 1:
        w, l = early[winners[0]], early[losers[0]]
        ck("winner h10 success/completion", [w["success"], w["complete"]], [[10], [10]])
        ck("winner task h8.5–9.5", [w["task_start"], w["task_complete"]], [[8.5], [9.5]])
        ck("winner not cancelled/waiting", [w["cancel"], w["wait"]], [[], []])
        ck("loser no start/task/success", [l["start"], l["task_start"], l["task_complete"],
                                             l["success"], l["complete"]], [[], [], [], [], []])
        ck("loser one waiting line", len(l["wait"]), 1)
        timeout = re.search(r"timeout at ([0-9]+(?:\.[0-9]+)?)", l["wait"][0]) if len(l["wait"]) == 1 else None
        deadline = float(timeout.group(1)) if timeout else None
        ck("loser deadline printed near h8+1/3", deadline is not None and abs(deadline - 8-1/3) < 0.00002, True)
        ck("loser cancellation near h8+1/3 before return", len(l["cancel"]) == 1 and
           abs(l["cancel"][0] - (8+1/3)) < 0.00002 and l["cancel"][0] < 10, True)
    third = "<BASIC-MISSION,TEACH-UNIT,0,0,2>"
    ck("third h32 launch", times(lines, third + " mission starting, duration: 2 : <TEACH-AIR-01,0>"), [32])
    ck("third h34 success/return", [times(lines, third + " mission success:"),
                                     times(lines, "System arrives <TEACH-AIR-01,0>, mission success")[-1:]],
       [[34], [34]])
    ck("only two launches", times(lines, " mission starting, duration: 2 : <TEACH-AIR-01,0>"), [8, 32])
    ck("only two successes", times(lines, " mission success:"), [10, 34])
    ck("only one cancellation", len(times(lines, " mission cancelled:")), 1)
    ck("one physical aircraft", sorted(set(re.findall(r"<TEACH-AIR-01,(\d+)>", "\n".join(lines)))), ["0"])

    parent = parse(RAW_ROOT / "A02" / contract["accepted_parent"]["final_run_id"] / "report-raw.json")
    child = parse(run / "report-raw.json")
    ck("report table names", sorted(x["name"] for x in child["report"]["tables"]),
       sorted(x["name"] for x in parent["report"]["tables"]))
    pc, pr = table(parent, "SystemResults")
    cc, cr = table(child, "SystemResults")
    ck("System columns", cc, pc)
    ck("System shape", [len(cr), len(cc)], [72, 40])
    templates = {"ready": pr[0], "reserved": pr[14], "flight": pr[16]}
    for i, row in enumerate(cr):
        t = i / 2
        state = "flight" if 8 <= t < 10 or 32 <= t < 34 else "reserved" if 7 <= t < 8 or 31 <= t < 32 else "ready"
        for field, actual, expected in zip(cc, row, templates[state]):
            if field == "STINT": expected = t
            if field == "ETINT": expected = t + .5
            ck(f"System row {i} {field}", actual, expected)
    ck("ready hours", sum(row[cc.index("NSYRY")] * .5 for row in cr), 30)
    ck("flight hours", sum(row[cc.index("FTMO")] * .5 for row in cr), 4)
    ck("terminal ready", cr[-1][cc.index("NSYRY")], 1)
    for name, nrows, ncols in (("StockTotalResults", 72, 16), ("ProblemDescription", 1, 1)):
        pc, pr = table(parent, name)
        cc, cr = table(child, name)
        ck(f"{name} columns", cc, pc)
        ck(f"{name} shape", [len(cr), len(cc)], [nrows, ncols])
        for i, (before, after) in enumerate(zip(pr, cr)):
            for field, expected, actual in zip(cc, before, after):
                ck(f"{name} row {i} {field}", actual, expected)
    pc, pr = table(parent, "ResultSummary")
    cc, cr = table(child, "ResultSummary")
    ck("summary columns", cc, pc)
    ck("summary shape", [len(cr), len(cc)], [1, 11])
    for field, before, actual in zip(cc, pr[0], cr[0]):
        if field in {"MTMF", "MSTF", "MSUF", "STMF"}:
            ck(f"summary {field} two of three", isinstance(actual, (int, float)) and abs(actual - 2/3) < 1e-6, True)
        else:
            ck(f"summary {field} retained", actual, before)
    failures = [c["name"] for c in checks if not c["passed"]]
    return {"schema": "simlox-a02-var03-same-time-v010-native-validation/v1",
            "run_id": run.name, "passed": not failures, "checks_count": len(checks),
            "failed": failures, "checks": checks, "publication_state": "not_published",
            "scope": "one fixed two-at-h8 competition, one cancellation, two sorties and complete ledgers"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        result = run_checks(args.run)
    except Exception as exc:
        result = {"schema": "simlox-a02-var03-same-time-v010-native-validation/v1",
                  "run_id": args.run.name, "passed": False, "checks_count": 0,
                  "failed": [f"checker exception: {type(exc).__name__}: {exc}"],
                  "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
