"""Read-only E05.var01 replay; the independent reviewer must use separate code."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E05-local-repair-reissue-v1.0.0"
PARENT_RUN = PARENT / "runs" / "e05-v100-ssh-20260929-01"
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as shared  # noqa: E402

INPUT_SHA = "5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08"
RUN_ID = "e05-var01-repair-backorder-v100-ssh-20261005-01"
STOCK = "<TEACH-LRU-01,0,BASE-01,0>"
ITEM = r"<TEACH-LRU-01,0,(\d+)>"
RAW = {
    "input.json", "import.log", "model.sxi", "roundtrip-raw.json", "export.log",
    "roundtrip-check.json", "run.log", "model.sxo", "model.log",
    "report-raw.json", "report-export.log", "steps.json", "outcome.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def events(text: str, body: str) -> list[tuple[float, re.Match[str]]]:
    return [(float(m[1]), m) for m in re.finditer(r"^Time: ([0-9.]+) " + body + r"\s*$", text, re.M)]


def validate(run: Path) -> dict:
    failed: list[str] = []
    checks = 0

    def ck(name: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failed.append(name)

    contract = load(HERE / "contract.json")
    ck("contract identity", contract["variant_id"] == "E05.var01" and contract["run_id"] == RUN_ID
       and contract["native_input_sha256"] == INPUT_SHA)
    ck("frozen input", sha(HERE / "native-input.json") == INPUT_SHA)
    ck("parent pins", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"]
       and sha(PARENT_RUN / "closure.json") == contract["parent"]["closure_sha256"])
    closure_parent = load(PARENT_RUN / "closure.json")
    for name, record in closure_parent["raw"].items():
        file = PARENT_RUN / name
        ck(f"parent raw {name}", file.stat().st_size == record["bytes"] and sha(file) == record["sha256"])
    ck("run directory identity", run.name == RUN_ID)
    ck("run input", sha(run / "input.json") == INPUT_SHA)
    invocation, closure, outcome = (load(run / name) for name in ("invocation.json", "closure.json", "outcome.json"))
    ck("SSH and GUI invocation", invocation["session_id"] == 0
       and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["gui"] == {"pid": 13340, "session_id": 1,
                                 "start_utc": "2026-09-28T10:09:56.8261381Z"}
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("invocation seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck("source stable", invocation["source_hashes_before"] == closure["source_hashes_before"]
       == closure["source_hashes_after"])
    source_paths = {
        "contract": HERE / "contract.json", "input": HERE / "native-input.json",
        "builder": HERE / "build.py", "source_checker": HERE / "check_source.py",
        "roundtrip_checker": HERE / "check_roundtrip.py",
        "parent_input": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "parent_closure": PARENT_RUN / "closure.json",
        "runner": HERE / "run_native_ssh.ps1",
    }
    for name, path in source_paths.items():
        ck(f"bound {name}", invocation["source_hashes_before"].get(name) == sha(path))
    ck("successful closure", closure["error"] is None and outcome["error"] is None
       and outcome["roundtrip"] == "exact" and outcome["result"] == "native_run_completed")
    ck("raw set", set(closure["raw"]) == RAW)
    for name, record in closure["raw"].items():
        file = run / name
        ck(f"raw {name}", file.stat().st_size == record["bytes"] and sha(file) == record["sha256"])
    steps = load(run / "steps.json")
    ck("native step order", [s["name"] for s in steps] == ["import", "export", "calc", "report"])
    for step in steps:
        ck(f"native step {step['name']}", step["status"] == "completed"
           and step["exit_code"] == 0 and step["gui_preserved"] is True)
    roundtrip = load(run / "roundtrip-check.json")
    ck("roundtrip gate", roundtrip["passed"] is True and not roundtrip["differences"]
       and len(roundtrip["populated_tables"]) == 20
       and shared.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"])
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    ck("converter and warning", m is not None and tuple(map(int, m.groups())) == (0, 1, 0)
       and Counter(re.findall(r"\(warning #(\d+)\)", log)) == Counter({"108": 1}))
    ck("valid SXO", (run / "model.sxo").stat().st_size > 1000)

    text = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    demands = events(text, re.escape(STOCK) + r" Item demand arrives from pos .* item requiring maintenance is " + ITEM)
    issues = events(text, re.escape(STOCK) + r" Take replacement item " + ITEM + r" from stock")
    puts = events(text, re.escape(STOCK) + r" Put back replacement item " + ITEM + r" to stock")
    adds = events(text, re.escape(STOCK) + r" Backorder added")
    removals = events(text, re.escape(STOCK) + r" Backorder removed, waiting time was ([0-9.]+)")
    repair_starts = events(text, re.escape(STOCK) + r" Start repair of item " + ITEM)
    repair_finishes = events(text, re.escape(STOCK) + r" Finished repair of item " + ITEM)
    arrivals = events(text, re.escape(STOCK) + r" Replacement item arrives " + ITEM)
    receives = events(text, r" system SURP task \d+ on <TEACH-AIR-01,0> subitem received " + ITEM)
    ck("material events present", len(demands) >= 2 and len(adds) >= 1 and len(repair_starts) >= 2)
    ck("each demand accounted", len(demands) == len(issues) + len(adds))
    ck("backorder count", len(removals) <= len(adds) and len(removals) == len(receives) - len(issues))
    ck("repair returns", len(repair_finishes) == len(arrivals))
    starts_by_id = {int(m[2]): time for time, m in repair_starts}
    ck("unique repair identities", len(starts_by_id) == len(repair_starts))
    for time, m in repair_finishes:
        identity = int(m[2])
        ck(f"repair {identity} turnaround", identity in starts_by_id
           and abs((time - starts_by_id[identity]) - 13) < 0.001)
    for time, m in arrivals:
        identity = m[2]
        ck(f"repair {identity} return routing", any(abs(t-time)<0.0001 and x[2] == identity for t, x in puts + receives))
    for time, m in demands:
        ck(f"demand at {time} route", sum(abs(t-time)<0.0001 for t, _ in issues + adds) == 1)
    ck("first repair bridges a backorder", bool(repair_starts and repair_finishes and adds
       and repair_starts[0][0] < adds[0][0] < repair_finishes[0][0]
       and any(x[2] == repair_finishes[0][1][2] for _, x in receives)))
    ck("no unexpected item receipt", len(receives) == len(issues) + len(removals))

    on_hand = {0}
    backorders = 0
    stock_events = 0
    for i, line in enumerate(lines):
        change = re.match(r"^Time: [0-9.]+ " + re.escape(STOCK)
                          + r" (Take replacement item|Put back replacement item) " + ITEM, line)
        bo_add = re.match(r"^Time: [0-9.]+ " + re.escape(STOCK) + r" Backorder added", line)
        bo_remove = re.match(r"^Time: [0-9.]+ " + re.escape(STOCK) + r" Backorder removed", line)
        if change:
            stock_events += 1
            identity = int(change[2])
            if change[1] == "Take replacement item":
                ck(f"issue ID {identity} held", identity in on_hand)
                on_hand.discard(identity)
            else:
                ck(f"restock ID {identity} new", identity not in on_hand)
                on_hand.add(identity)
            expected = "  Stock at: " + STOCK + " Level: " + str(len(on_hand))
            ck(f"stock level after event {i}", i+1 < len(lines) and lines[i+1].startswith(expected))
        if bo_add or bo_remove:
            backorders += 1 if bo_add else -1
            ck(f"backorder nonnegative {i}", backorders >= 0)
            expected = "  Backorders at: " + STOCK + " Nbr: " + str(backorders)
            ck(f"backorder level {i}", i+1 < len(lines) and lines[i+1].startswith(expected))
    ck("stock transitions complete", stock_events == len(issues) + len(puts))
    ck("terminal on-hand bound", len(on_hand) in (0, 1) and backorders == len(adds)-len(removals))

    report = json.loads(shared.remove_trailing_commas((run / "report-raw.json").read_bytes()))
    tables = {table["name"]: table for table in report["report"]["tables"]}
    report_rows = {}
    for name in ("SystemResults", "StockTotalResults"):
        table = tables[name]
        columns = [c["name"] for c in table["columns"]]
        rows = [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]
        report_rows[name] = rows
        ck(f"{name} 72 bins", len(rows) == 72)
        for i, row in enumerate(rows):
            ck(f"{name} bin {i}", abs(row["STINT"]-i/2)<1e-8
               and abs(row["ETINT"]-(i+1)/2)<1e-8)
    stock = report_rows["StockTotalResults"]
    bo_hours = sum((t2-t1) for (t1, _), (t2, _) in zip(adds, removals))
    if len(adds) > len(removals):
        bo_hours += sum(36-t for t, _ in adds[len(removals):])
    ck("aggregate backorder occupancy", abs(sum(row["NBO"]*0.5 for row in stock)-bo_hours) < 0.003)
    ck("aggregate demand count", sum(row["NDF"] for row in stock) == len(demands))
    ck("parent no-backorder control", "Backorder added" not in (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig"))

    return {"schema": "simlox-e05-var01-author-replay/v1", "passed": not failed,
            "checks": checks, "failures": failed, "run_id": run.name,
            "demands": len(demands), "backorders_added": len(adds),
            "backorders_removed": len(removals), "repair_starts": len(repair_starts),
            "repair_finishes": len(repair_finishes), "on_hand_ids_at_horizon": sorted(on_hand),
            "aggregate_backorder_hours": bo_hours, "scope": "one fixed-seed E05.var01 CLI boundary only"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        verdict = validate(args.run)
    except (AssertionError, OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        verdict = {"schema": "simlox-e05-var01-author-replay/v1", "passed": False,
                   "failures": [f"replay error: {type(exc).__name__}: {exc}"], "run_id": args.run.name}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
