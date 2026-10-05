"""Independent read-only E05.var01 v1.0.2 evidence replay."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

CASE = pathlib.Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs/e05-var01-repair-backorder-v102-ssh-20261005-01"
PARENT = ROOT / "E05-local-repair-reissue-v1.0.0"
PARENT_RUN = PARENT / "runs/e05-v100-ssh-20260929-01"
checks: list[tuple[str, bool]] = []


def ck(name: str, condition: bool) -> None:
    checks.append((name, bool(condition)))


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_report(path: pathlib.Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        # Parser copy only. The original report remains sealed unchanged.
        return json.loads(re.sub(r",(?=\s*[}\]])", "", raw)), False


def events(text: str, pattern: str):
    return [(float(m.group(1)), m) for m in re.finditer(r"^Time: ([0-9.]+) " + pattern, text, re.M)]


def occupancy(intervals, lo: float, hi: float) -> float:
    return sum(max(0, min(hi, b) - max(lo, a)) for a, b in intervals) / (hi - lo)


def populated(doc):
    result = {}
    for table in doc["model"]["tables"]:
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        if rows:
            result[table["name"]] = (
                [(col["name"], col["datatype"]) for col in table["columns"]], rows
            )
    return result


def main() -> None:
    contract, closure, invocation = (load(p) for p in
        (CASE / "contract.json", RUN / "closure.json", RUN / "invocation.json"))
    outcome, steps, parent_closure = (load(p) for p in
        (RUN / "outcome.json", RUN / "steps.json", PARENT_RUN / "closure.json"))
    ck("contract/run identity", contract["run_id"] == RUN.name and contract["version"] == "1.0.2")
    ck("parent three pins", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"]
       and sha(PARENT / "cli-scope-signoff-2026-09-29.md") == contract["parent"]["signoff_sha256"]
       and sha(PARENT_RUN / "closure.json") == contract["parent"]["closure_sha256"])
    ck("parent 12 raw", len(parent_closure["raw"]) == 12)
    for name, record in parent_closure["raw"].items():
        p = PARENT_RUN / name
        ck("parent raw " + name, p.stat().st_size == record["bytes"] and sha(p) == record["sha256"])
    ck("invocation seal", sha(RUN / "invocation.json") == closure["invocation_sha256"])
    ck("source stable", invocation["source_hashes_before"] == closure["source_hashes_before"]
       == closure["source_hashes_after"])
    ck("13 raw", len(closure["raw"]) == 13)
    for name, record in closure["raw"].items():
        p = RUN / name
        ck("run raw " + name, p.stat().st_size == record["bytes"] and sha(p) == record["sha256"])
    source = {
        "contract": CASE / "contract.json", "input": CASE / "native-input.json",
        "builder": CASE / "build.py", "source_checker": CASE / "check_source.py",
        "roundtrip_checker": CASE / "check_roundtrip.py",
        "author_validator": CASE / "validate_native.py", "ledger_replay": CASE / "ledger_replay.py",
        "shared_validator_module": ROOT / "tools/validate_native.py",
        "native_binding_module": ROOT / "tools/native_binding.py",
        "parent_input": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "parent_closure": PARENT_RUN / "closure.json",
        "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "runner": CASE / "run_native_ssh.ps1",
        "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for name, path in source.items():
        ck("source " + name, sha(path) == closure["source_hashes_before"][name])
    ck("completed", closure["error"] is None and outcome["error"] is None
       and outcome["result"] == "native_run_completed" and outcome["roundtrip"] == "exact")
    ck("SSH0/GUI/mutex", invocation["session_id"] == 0
       and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["gui"] == {"pid": 13340, "session_id": 1,
          "start_utc": "2026-09-28T10:09:56.8261381Z"}
       and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    ck("four guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "report"]
       and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    ck("default report command", "-jsonreport" in steps[-1]["arguments"]
       and "-rpts" not in steps[-1]["arguments"])

    parent = load(PARENT / "native-input.json")
    child = load(CASE / "native-input.json")
    item_repair = next(t for t in parent["model"]["tables"] if t["name"] == "ItemRepair")
    ck("parent DIRPT 1", item_repair["instances"][0]["rows"][0][2] == 1)
    item_repair["instances"][0]["rows"][0][2] = 13
    ck("sole source cell", parent == child)
    ck("frozen/copy input", sha(CASE / "native-input.json") == contract["native_input_sha256"]
       == sha(RUN / "input.json"))
    authored = populated(child)
    exported = populated(load(RUN / "roundtrip-raw.json"))
    ck("20 authored tables", len(authored) == 20)
    for name, value in authored.items():
        ck("roundtrip " + name, exported.get(name) == value)
    roundtrip = load(RUN / "roundtrip-check.json")
    ck("runner roundtrip gate", roundtrip["passed"] and not roundtrip["differences"])
    calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("converter 0/1/0 #108", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc
       and re.findall(r"\(warning #(\d+)\)", calc) == ["108"])
    ck("valid SXO", (RUN / "model.sxo").stat().st_size > 1000)

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    stock = re.escape("<TEACH-LRU-01,0,BASE-01,0>")
    demand = events(log, stock + r" Item demand arrives .* item requiring maintenance is <TEACH-LRU-01,0,(\d+)>")
    issue = events(log, stock + r" Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    added = events(log, stock + r" Backorder added")
    cleared = events(log, stock + r" Backorder removed, waiting time was ([0-9.]+)")
    repair_start = events(log, stock + r" Start repair of item <TEACH-LRU-01,0,(\d+)>")
    repair_end = events(log, stock + r" Finished repair of item <TEACH-LRU-01,0,(\d+)>")
    received = events(log, r" system SURP task (\d+) on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,(\d+)>")
    failure = events(log, r"<TEACH-AIR-01,0> critical random failure added, now")
    system_repair = events(log, r"<TEACH-AIR-01,BASE-01,0> System to repair")
    system_ready = events(log, r"<TEACH-AIR-01,BASE-01,0> System ready")
    ck("event counts", tuple(map(len, (demand, issue, added, cleared, repair_start, repair_end,
        received, failure, system_repair, system_ready))) == (3, 1, 2, 2, 3, 2, 3, 3, 3, 3))
    ck("failed item identities", [m.group(2) for _, m in demand] == ["1", "2", "3"])
    ck("critical failure IDs", all(re.search(r"^Time: [0-9.]+ <TEACH-AIR-01,0> critical random failure added, now\s*\n 1 failures:\s*\n  subitem failed: <TEACH-LRU-01,0," + str(identity) + r">", log, re.M)
       for identity in (1, 2, 3)))
    ck("replacement receipt identities", [m.group(3) for _, m in received] == ["0", "1", "2"])
    ck("repair identities", [m.group(2) for _, m in repair_start] == ["1", "2", "3"]
       and [m.group(2) for _, m in repair_end] == ["1", "2"])
    ck("13h completed repairs", all(abs(repair_end[i][0] - repair_start[i][0] - 13) < .001
       for i in range(2)))
    ck("repair-to-backorder-to-fit", all(repair_start[i][0] < added[i][0] < repair_end[i][0]
       and abs(repair_end[i][0] - cleared[i][0]) < .001
       and repair_end[i][1].group(2) == received[i + 1][1].group(3)
       and abs(float(cleared[i][1].group(2)) - (cleared[i][0] - added[i][0])) < .001
       for i in range(2)))
    ck("terminal", abs(system_ready[-1][0] - 35.5) < .001 and len(repair_start) - len(repair_end) == 1
       and cleared[-1][0] < 36)
    ck("stock ID0 issued and no restock", [m.group(2) for _, m in issue] == ["0"]
       and not events(log, stock + r" Put back replacement item"))
    ck("stock level zero after issue", "  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log)
    for task, removal, fitted, fit_end, waited in (
        (0, 9.92193, 9.92193, 10.2553, False),
        (2, 22.1667, 22.9219, 23.2553, True),
        (4, 33.9746, 35.1667, 35.5, True),
    ):
        remove = events(log, r" remove subitem subtask \d+ seqno 1 within system SURP task " + str(task) + r" on <TEACH-AIR-01,0> completed")
        fit_start = events(log, r" fit subitem subtask \d+ seqno 2 within system SURP task " + str(task) + r" on <TEACH-AIR-01,0> starts performing")
        fit_done = events(log, r" fit subitem subtask \d+ seqno 2 within system SURP task " + str(task) + r" on <TEACH-AIR-01,0> completed")
        wait = events(log, r" fit subitem subtask \d+ seqno 2 within system SURP task " + str(task) + r" on <TEACH-AIR-01,0> wait for subitem")
        ck(f"SURP task {task} removal/fit", len(remove) == len(fit_start) == len(fit_done) == 1
           and abs(remove[0][0] - removal) < .001 and abs(fit_start[0][0] - fitted) < .001
           and abs(fit_done[0][0] - fit_end) < .001 and bool(wait) == waited)
        ck(f"SURP task {task} completed", len(events(log, r" system SURP task " + str(task) + r" on <TEACH-AIR-01,0> completed")) == 1)

    report, strict_json = parse_report(RUN / "report-raw.json")
    tables = {t["name"]: t for t in report["report"]["tables"]}
    def rows(name):
        t = tables[name]
        cols = [c["name"] for c in t["columns"]]
        return [dict(zip(cols, row)) for i in t["instances"] for row in i["rows"]]
    system, stock_rows = rows("SystemResults"), rows("StockTotalResults")
    ck("72 by two", len(system) == len(stock_rows) == 72)
    ready_intervals = []
    state, previous = 0, 0.0
    for line in log.splitlines():
        m = re.match(r"Time: ([0-9.]+) <TEACH-AIR-01,0> nbr ready (increased|decreased) at unit:", line)
        if m:
            time = float(m.group(1))
            if state == 1 and time > previous:
                ready_intervals.append((previous, time))
            state += 1 if m.group(2) == "increased" else -1
            previous = time
    if state == 1:
        ready_intervals.append((previous, 36.0))
    ck("ready state terminal", state == 1)
    repair_intervals = [(system_repair[i][0], system_ready[i][0]) for i in range(3)]
    backorder_intervals = [(added[i][0], cleared[i][0]) for i in range(2)]
    for i, (sr, st) in enumerate(zip(system, stock_rows)):
        lo, hi = i / 2, (i + 1) / 2
        ck(f"grid {i}", all(abs(row["STINT"] - lo) < 1e-8 and abs(row["ETINT"] - hi) < 1e-8
             for row in (sr, st)))
        ck(f"ready {i}", abs(sr["NSYRY"] - occupancy(ready_intervals, lo, hi)) < .003)
        ck(f"system repair {i}", abs(sr["NSYUA"] - occupancy(repair_intervals, lo, hi)) < .003)
        ck(f"failure {i}", sr["NFAIL"] == sum(lo <= t < hi for t, _ in failure))
        bo_value = occupancy(backorder_intervals, lo, hi)
        ck(f"backorder {i}", abs(st["NBO"] - bo_value) < .003)
        ck(f"nonbackorder {i}", abs(st["PNB"] - (1 - bo_value)) < .003)
        ck(f"demand count {i}", st["NDF"] == sum(lo <= t < hi for t, _ in demand))
        matches = [j for j, (t, _) in enumerate(added) if lo <= t < hi]
        if matches:
            j = matches[0]
            wait = cleared[j][0] - added[j][0]
            ck(f"demand shortage/wait {i}", abs(st["ROS"] - 1) < .003
               and abs(st["WT"] - wait) < .003 and abs(st["WTS"] - wait) < .003)
    ck("parent had no BO", "Backorder added" not in (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig"))

    result = {"verdict": "GO_BOUNDED" if all(v for _, v in checks) else "NO_GO",
      "checks": len(checks), "failures": [name for name, passed in checks if not passed],
      "report_strict_json": strict_json,
      "demands": [(t, m.group(2)) for t, m in demand],
      "backorders": [(a[0], b[0]) for a, b in zip(added, cleared)],
      "completed_repair_ids": [m.group(2) for _, m in repair_end],
      "terminal_pending_repair_id": repair_start[-1][1].group(2),
      "terminal_ready_hour": system_ready[-1][0],
      "limit": "No installed physical item ID mapping across fit and later failure."}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
