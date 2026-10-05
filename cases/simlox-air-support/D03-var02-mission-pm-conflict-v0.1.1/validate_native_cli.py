"""Replay guarded D03.var02 run and require event-supported PM interaction."""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas, table_rows  # noqa: E402

INPUT_SHA = "393f80c1c271d3687862c639bfc5e7aa1c534e7a375d9c773a2afb18066c1427"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
PARENT_CLOSURE_SHA = "9cd845f957105eb8659809ec09cf380ae5df68a63babb264d70631c164f7d2d8"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def times(log, pattern):
    return [float(x) for x in re.findall(pattern, log, re.MULTILINE)]


def prefix(log, end):
    return [line for line in log.splitlines()
            if (m := re.match(r"^Time: ([\d.]+) ", line)) and float(m.group(1)) < end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    run = args.run.resolve()
    checks = []

    def check(name, got, want):
        checks.append({"name": name, "passed": got == want, "actual": got, "expected": want})

    try:
        parent = HERE.parent / "D03-calendar-pm-v1.0.0"
        parent_run = parent / "runs" / "d03-calendar-v100-ssh-20261001-02"
        parent_closure = load(parent_run / "closure.json")
        contract = load(HERE / "contract.json")
        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        roundtrip = load(run / "roundtrip-validation.json")
        report = json.loads(remove_trailing_commas((run / "report-raw.json").read_bytes()))
        parent_report = json.loads(remove_trailing_commas((parent_run / "report-raw.json").read_bytes()))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check("parent input SHA", sha(parent / "native-input.json"), PARENT_SHA)
        check("child input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
        check("copied input SHA", sha(run / "input.json"), INPUT_SHA)
        check("parent closure SHA", sha(parent_run / "closure.json"), PARENT_CLOSURE_SHA)
        check("parent closure status", parent_closure["error"], None)
        for name, seal in sorted(parent_closure["raw"].items()):
            check(f"parent raw {name}", [sha(parent_run / name), (parent_run / name).stat().st_size],
                  [seal["sha256"], seal["bytes"]])
        check("contract ID/version", [contract["variant_id"], contract["version"]],
              ["D03.var02", "0.1.1-contract-candidate"])
        check("reserved run", contract["ownership"]["native_run_id_reserved"], run.name)
        check("run ID", invocation["run_id"], "d03-var02-mission245-v011-ssh-20261006-01")
        check("run input/parent", [invocation["input_sha256"], invocation["parent_sha256"]],
              [INPUT_SHA, PARENT_SHA])
        check("SSH0 and ancestor", [invocation["session_id"], invocation["ssh_connection_present"],
                                    "sshd.exe" in invocation["ssh_ancestor_names"]], [0, True, True])
        check("GUI identity", [invocation["gui"]["pid"], invocation["gui"]["session_id"],
                               invocation["gui"]["start_utc"]],
              [13340, 1, "2026-09-28T10:09:56.8261381Z"])
        check("serial mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        check("ordered native steps", [x["name"] for x in steps],
              ["import", "export", "check_import_export", "calc", "jsonreport"])
        check("step completion and GUI", all(x["status"] == "completed" and x["exit_code"] == 0
                                             and x["gui_preserved"] for x in steps), True)
        check("18-table pre-calc roundtrip", [roundtrip["passed"], len(roundtrip["populated_tables"])],
              [True, 18])
        check("closure status/invocation", [closure["error"], closure["invocation_sha256"]],
              [None, sha(run / "invocation.json")])
        check("source hashes unchanged", closure["source_hashes_before"], closure["source_hashes_after"])
        check("child raw count", len(closure["raw"]), 12)
        for name, seal in sorted(closure["raw"].items()):
            check(f"child raw {name}", [sha(run / name), (run / name).stat().st_size],
                  [seal["sha256"], seal["bytes"]])

        pm_start = times(log, r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$")
        pm_done = times(log, r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$")
        sub_start = times(log, r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours$")
        sub_done = times(log, r"^Time: ([\d.]+)  subtask \d+ seqno 1 within system PM task \d+ on <TEACH-AIR-01,0> completed$")
        mission_start = times(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission starting, duration: 2 : <TEACH-AIR-01,0>$")
        mission_done = times(log, r"^Time: ([\d.]+) <BASIC-MISSION,[^\n]+> mission completed: <TEACH-AIR-01,0>$")
        check("event prefix before parent second notice h19", prefix(log, 19), prefix(parent_log, 19))
        check("first mission start", mission_start[:1], [8.0])
        check("PM/subtask event pairing", [pm_start, pm_done], [sub_start, sub_done])
        check("PM starts match completions", len(pm_start), len(pm_done))
        pm_changed = pm_start != [24.0, 49.0] or pm_done != [25.0, 50.0]
        active_at_shifted_start = any(a <= 24.5 < b for a, b in zip(pm_start, pm_done))
        delayed = len(mission_start) >= 2 and mission_start[1] > 24.5 and active_at_shifted_start
        cancelled = len(mission_start) < 3 and active_at_shifted_start and bool(
            re.search(r"mission (?:cancelled|canceled)", log, re.I))
        check("PM interaction beyond tautological STIM shift", pm_changed or delayed or cancelled, True)

        summary = table_rows(report, "ResultSummary")
        rows = table_rows(report, "SystemResults")
        stock = table_rows(report, "StockTotalResults")
        parent_rows = table_rows(parent_report, "SystemResults")
        check("one summary and 60h horizon", [len(summary), summary[0]["RTIUP"]], [1, 60])
        check("120 system and stock rows", [len(rows), len(stock)], [120, 120])
        grid = [(i / 2, (i + 1) / 2) for i in range(120)]
        for name, ledger in (("system", rows), ("stock", stock)):
            check(f"{name} complete half-hour grid", [(x["STINT"], x["ETINT"]) for x in ledger], grid)
        check("system schema", all(set(x) == set(parent_rows[0]) for x in rows), True)
        check("stock schema", all(set(x) == set(stock[0]) for x in stock), True)
        check("item-free stock ledger equals parent", stock, table_rows(parent_report, "StockTotalResults"))
        check("system grid prefix before h19", [x for x in rows if x["ETINT"] <= 19],
              [x for x in parent_rows if x["ETINT"] <= 19])
        check("PM markers match event counts", [sum(x["NPMS"] for x in rows), sum(x["NPMT"] for x in rows)],
              [len(pm_start), len(pm_done)])
        check("no failure or repair markers", all(x["NFAIL"] == 0 and x["NREPT"] == 0 for x in rows), True)
        check("no simultaneous PM and flight occupancy", all(x["NSYPM"] + x["NSYMO"] <= 1.00003 for x in rows), True)
        check("finite status integrals", all(math.isfinite(sum(float(x[f]) * .5 for x in rows))
                                            for f in ("NSYRY", "NSYA", "NSYMO", "NSYPM")), True)
        check("mission completions bounded by starts", len(mission_done) <= len(mission_start), True)
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        checks.append({"name": "replay exception", "passed": False,
                       "actual": f"{type(exc).__name__}: {exc}", "expected": "none"})

    result = {"schema": "simlox-d03-var02-v011-behavior-replay/v1", "case_id": "D03",
              "run_id": run.name, "passed": all(x["passed"] for x in checks),
              "checks_count": len(checks), "checks": checks,
              "scope": "one shifted mission nominally overlaps first CAL24 PM",
              "publication_state": "candidate"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(raw)
    else:
        sys.stdout.buffer.write(raw)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
