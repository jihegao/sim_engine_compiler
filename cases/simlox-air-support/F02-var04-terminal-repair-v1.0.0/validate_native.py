"""Replay native F02.var04 active aircraft removal and resource/stock ledgers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "f02-var04-active-repair-v100-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def event_times(log: str, pattern: str) -> list[float]:
    return [float(m.group(1)) for m in re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M)]


def exposure(start: float, end: float, a: float, b: float) -> float:
    return max(0.0, min(end, b) - max(start, a)) / (b - a)


def worker_intervals(log: str) -> tuple[list[tuple[float, float]], dict[str, float]]:
    active: dict[str, float] = {}
    periods = []
    for line in log.splitlines():
        m = re.match(r"Time: ([\d.]+)  <(P-(?:MAINT|CREW)) at <BASE-01,0>> (allocated to|deallocated from)\s+maintenance task:", line)
        if not m:
            continue
        t, person, action = float(m.group(1)), m.group(2), m.group(3)
        if action == "allocated to":
            if person in active:
                raise ValueError(f"double-booked {person}")
            active[person] = t
        else:
            periods.append((active.pop(person), t))
    periods.extend((t, 60.0) for t in active.values())
    return periods, active


def request_intervals(log: str) -> tuple[list[tuple[float, float]], dict[str, float]]:
    active: dict[str, float] = {}
    periods = []
    for line in log.splitlines():
        m = re.match(r"Time: ([\d.]+)  (.+) requests resources$", line)
        if m:
            if m.group(2) in active:
                raise ValueError("duplicate worker request")
            active[m.group(2)] = float(m.group(1))
        m = re.match(r"Time: ([\d.]+)  (.+) starts performing,", line)
        if m and m.group(2) in active:
            start, end = active.pop(m.group(2)), float(m.group(1))
            if end > start:
                periods.append((start, end))
    periods.extend((t, 60.0) for t in active.values())
    return periods, active


def main() -> None:
    failures = []
    count = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    contract, diff = load(HERE / "contract.json"), load(HERE / "exact-diff.json")
    parent = HERE.parent / contract["accepted_parent"]["package"]
    sibling = HERE.parent / contract["accepted_sibling"]["package"]
    ck(contract["case_id"] == "F02" and contract["variant_id"] == "F02.var04" and contract["version"] == "1.0.0-candidate", "contract identity")
    ck(sha(HERE / "repair-input.json") == contract["repair_input_sha256"] == diff["terminal_input_sha256"], "frozen child input")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"] and diff["changed_cells"] == [
        {"table": "SystemRepair", "instance": 0, "row": 0, "column": "SURPT", "before": 0.5, "after": 15.333333333333334},
        {"table": "TaskBreakDown", "instance": 0, "row": 1, "column": "DURN", "before": 1 / 6, "after": 15.0}], "two-cell labor duration delta")
    ck(sha(parent / "risk-input.json") == contract["accepted_parent"]["input_sha256"] and
       sha(parent / "runs" / contract["accepted_parent"]["run_id"] / "closure.json") == contract["accepted_parent"]["closure_sha256"] and
       sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"], "accepted parent pins")
    ck(sha(sibling / "evidence-index.json") == contract["accepted_sibling"]["evidence_index_sha256"] and
       sha(sibling / "runs/f02-var04-terminal-v102-ssh-20261004-01/closure.json") == contract["accepted_sibling"]["native_closure_sha256"], "accepted sibling pins")
    invocation, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN_ID and invocation["execution_mode"] == "ssh_cli_v1" and
       invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 identity")
    ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and
       invocation["gui"]["session_id"] == 1, "host queue and GUI identity")
    ck(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json") and
       closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "closure and stable sources")
    ck(set(closure["raw"]) == RAW, "12 raw artifacts sealed")
    for name, meta in closure["raw"].items():
        ck((RUN / name).stat().st_size == meta["bytes"] and sha(RUN / name) == meta["sha256"], f"raw {name}")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(step["status"] == "completed" and step["exit_code"] == 0 and step.get("gui_preserved", True) for step in steps), "five completed native steps")
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
        ck(closure["source_hashes_before"][name] == sha(HERE / name), f"sealed source {name}")
    ck(closure["source_hashes_before"]["input"] == contract["repair_input_sha256"] and
       closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), "sealed contract/input")
    roundtrip = load(RUN / "roundtrip-validation.json")
    authored, exported = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    ck(roundtrip["passed"] and len(authored) == 30 and authored == {n: exported[n] for n in authored}, "exact 30-table roundtrip")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1 and
       not re.search(r"\((?:error|warning|notice) #(?!108\))", runlog), "converter diagnostics")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    report = parse(RUN / "report-raw.json")
    summary = rows(report, "ResultSummary")
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 60, "valid native report/horizon")
    system, stock, resource = (rows(report, n) for n in ("SystemResults", "StockTotalResults", "ResourceResults"))
    for name, data in (("system", system), ("stock", stock), ("resource", resource)):
        ck(len(data) == 120, f"{name} 120 rows")
        for i, row in enumerate(data):
            ck(abs(row["STINT"] - i / 2) < 1e-9 and abs(row["ETINT"] - (i + 1) / 2) < 1e-9, f"{name} bin {i}")
    fault = event_times(log, r"<TEACH-AIR-01,0> critical random failure added")
    aborted = event_times(log, r"<RISK-MISSION[^\n]*> mission aborted:")
    success = event_times(log, r"<[^\n]*> mission success:")
    cancelled = event_times(log, r"<BASIC-MISSION[^\n]*> mission cancelled:")
    surp = event_times(log, r" system SURP task 14 on <TEACH-AIR-01,0> started")
    remove_work = event_times(log, r" remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> starts performing, planned to last for 15 hours")
    removal_complete = event_times(log, r" remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> completed")
    back = event_times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added")
    clear = event_times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder removed")
    supply = event_times(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,2> from stock")
    incoming = event_times(log, r" transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started")
    received = event_times(log, r" system SURP task 14 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,2>")
    outgoing = event_times(log, r" transport request <<TEACH-LRU-01,0,4>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
    ck(fault == aborted == [46.4896] and success == [23.5, 27.5] and cancelled == [50.25], "four mission outcomes and fixed-seed fault")
    ck(surp == remove_work == back == supply == incoming == [47.9896], "active removal and physical spare dispatch")
    ck(clear == received == [49.9896] and not removal_complete and not outgoing and
       "system SURP task 14 on <TEACH-AIR-01,0> completed" not in log, "spare received; installed item still in open removal")
    ck("fit subitem subtask" not in log or not event_times(log, r" fit subitem subtask \d+ seqno 2 within system SURP task 14 on <TEACH-AIR-01,0> starts performing"), "no system fit labor yet")
    ck("Start repair of item <TEACH-LRU-01,0,4>" not in log, "failed LRU has not reached depot repair")
    pm_started = event_times(log, r" system PM task \d+ on <TEACH-AIR-01,[01]> started")
    pm_complete = event_times(log, r" system PM task \d+ on <TEACH-AIR-01,[01]> completed")
    ck(len(pm_started) == 4 and len(pm_complete) == 2 and all(t < 48 for t in pm_complete), "second-day PMs remain uncompleted")
    workers, active_workers = worker_intervals(log)
    waits, active_requests = request_intervals(log)
    ck(active_workers == {"P-MAINT": 47.9896} and len(workers) >= 9, "P-MAINT still performing removal at cutoff")
    ck(len(active_requests) == 1 and abs(next(iter(active_requests.values())) - 54.5) < 1e-4, "healthy aircraft PM waits for P-MAINT at cutoff")
    for i, (sy, st, rr) in enumerate(zip(system, stock, resource)):
        a, b = i / 2, (i + 1) / 2
        ck(abs(sy["NSYA"] + sy["NSYUA"] - 2) < 1e-3, f"aircraft conservation bin {i}")
        ck(abs(sy["NSYRP"] - exposure(surp[0], 60, a, b)) < 1e-3 and sy["NSYWI"] == 0, f"active SURP bin {i}")
        ck(abs(st["NBO"] - exposure(back[0], clear[0], a, b)) < 1e-3, f"stock backorder bin {i}")
        ck(abs(rr["NRUM"] - sum(exposure(x, y, a, b) for x, y in workers)) < 1e-3, f"worker occupancy bin {i}")
        ck(abs(rr["NRW"] - sum(exposure(x, y, a, b) for x, y in waits)) < 1e-3, f"worker request wait bin {i}")
        ck(rr["NR"] == 2 and rr["NRF"] == 0 and 0 <= rr["NRUM"] <= 2.001 and 0 <= rr["NRW"] <= 2.001, f"resource bounds bin {i}")
        ck(st["NDD"] == st["NDR"] == 0 and 0 <= st["NBO"] <= 1.001, f"stock bounds bin {i}")
    ck(sum(s["NFAIL"] for s in system) == 1 and sum(s["NREPT"] for s in system) == 0 and
       sum(s["NPMS"] for s in system) == 4 and sum(s["NPMT"] for s in system) == 2, "failure/PM totals")
    ck(sum(s["NDF"] for s in stock) == 1 and abs(sum(s["NBO"] for s in stock) * 0.5 - 2) < 1e-3, "spare demand and 2-hour backorder")
    ck(abs(sum(r["NRUM"] for r in resource) * 0.5 - sum(y - x for x, y in workers)) < 1e-3 and
       abs(sum(r["NRW"] for r in resource) * 0.5 - sum(y - x for x, y in waits)) < 1e-3, "resource time integrals")
    ck(system[-1]["NSYRY"] == system[-1]["NSYRP"] == 1 and system[-1]["NSYWI"] == 0 and
       stock[-1]["NBO"] == 0 and resource[-1]["NRUM"] == resource[-1]["NRW"] == 1, "last-bin active-repair state")
    parent_report = parse(parent / "runs" / contract["accepted_parent"]["run_id"] / "report-raw.json")
    ck(all(stock[i] == rows(parent_report, "StockTotalResults")[i] for i in range(120)), "all stock result bins match parent")
    ck(all(system[i] == rows(parent_report, "SystemResults")[i] for i in range(95)), "pre-repair system prefix matches parent")
    ck(all(resource[i] == rows(parent_report, "ResourceResults")[i] for i in range(96)), "pre-repair resource prefix matches parent")
    result = {"schema": "simlox-f02-var04-active-repair-author-replay/v1", "run_id": RUN_ID,
              "passed": not failures, "checks": count, "failures": failures,
              "observed": {"fault_hour": fault, "repair_start_hour": surp, "lru2_departure_hour": incoming,
                           "lru2_received_by_open_surp_hour": received, "backorder_cleared_hour": clear,
                           "terminal_hour": 60, "terminal_system_nsyry": system[-1]["NSYRY"],
                           "terminal_system_nsyrp": system[-1]["NSYRP"], "terminal_system_nsywi": system[-1]["NSYWI"],
                           "terminal_base_nbo": stock[-1]["NBO"], "terminal_resource_nrum": resource[-1]["NRUM"],
                           "terminal_resource_nrw": resource[-1]["NRW"],
                           "open_workers": active_workers, "open_requests": active_requests},
              "scope": "bounded_active_aircraft_removal_at_60;stock_item_reservation_unverified"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
