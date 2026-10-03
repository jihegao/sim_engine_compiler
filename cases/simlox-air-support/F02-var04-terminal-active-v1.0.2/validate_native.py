"""Replay frozen F02.var04 transit and unfinished-system evidence from native files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "f02-var04-terminal-v102-ssh-20261004-01"
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


def resource_intervals(log: str) -> list[tuple[float, float]]:
    active: dict[str, float] = {}
    intervals = []
    for line in log.splitlines():
        m = re.match(r"Time: ([\d.]+)  <(P-(?:MAINT|CREW)) at <BASE-01,0>> (allocated to|deallocated from)\s+maintenance task:", line)
        if not m:
            continue
        when, person, action = float(m.group(1)), m.group(2), m.group(3)
        if action == "allocated to":
            if person in active:
                raise ValueError(f"resource double allocation {person}")
            active[person] = when
        else:
            intervals.append((active.pop(person), when))
    if active:
        raise ValueError(f"unclosed worker allocation {active}")
    return intervals


def waiting_intervals(log: str) -> list[tuple[float, float]]:
    requests: dict[str, float] = {}
    intervals = []
    for line in log.splitlines():
        m = re.match(r"Time: ([\d.]+)  (.+) requests resources$", line)
        if m:
            if m.group(2) in requests:
                raise ValueError("duplicate task request")
            requests[m.group(2)] = float(m.group(1))
        m = re.match(r"Time: ([\d.]+)  (.+) starts performing,", line)
        if m and m.group(2) in requests:
            start, end = requests.pop(m.group(2)), float(m.group(1))
            if end > start:
                intervals.append((start, end))
    if requests:
        raise ValueError(f"unclosed resource requests {requests}")
    return intervals


def main() -> None:
    failures: list[str] = []
    count = 0

    def ck(ok: bool, label: str) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    diff = load(HERE / "exact-diff.json")
    parent = HERE.parent / contract["accepted_parent"]["package"]
    ck(contract["case_id"] == "F02" and contract["variant_id"] == "F02.var04" and contract["version"] == "1.0.2-candidate", "contract identity")
    ck(sha(HERE / "terminal-input.json") == contract["terminal_input_sha256"] == diff["terminal_input_sha256"], "input fingerprint")
    ck(sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "diff fingerprint")
    ck(sha(parent / "risk-input.json") == contract["accepted_parent"]["input_sha256"], "parent input fingerprint")
    ck(sha(parent / "runs" / contract["accepted_parent"]["run_id"] / "closure.json") == contract["accepted_parent"]["closure_sha256"], "parent closure fingerprint")
    ck(sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"], "parent evidence fingerprint")
    expected_diff = [
        {"table": "StationStructure", "instance": 0, "row": 0, "column": "TFRMS", "before": 2.0, "after": 15.0},
        {"table": "StationStructure", "instance": 0, "row": 0, "column": "TTOMS", "before": 2.0, "after": 15.0},
    ]
    ck(diff["changed_cells"] == expected_diff, "two-cell physical-route delta")
    for old in contract["revised_from"]:
        package = HERE.parent / old["package"]
        diagnostic = load(package / "diagnostic.json")
        ck(sha(package / "diagnostic.json") == old["diagnostic_sha256"] and
           sha(package / "runs" / diagnostic["run_id"] / "closure.json") == old["native_closure_sha256"] and
           diagnostic["publication_state"] == "excluded_diagnostic", f"excluded {old['package']}")

    invocation, closure, steps = (load(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == RUN_ID and invocation["execution_mode"] == "ssh_cli_v1" and
       invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH0 run identity")
    ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and
       invocation["gui"]["session_id"] == 1, "GUI and host queue")
    ck(closure["error"] is None and closure["invocation_sha256"] == sha(RUN / "invocation.json") and
       closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "closure/source stability")
    ck(set(closure["raw"]) == RAW, "12 raw artifacts sealed")
    for name, meta in closure["raw"].items():
        ck((RUN / name).stat().st_size == meta["bytes"] and sha(RUN / name) == meta["sha256"], f"raw {name}")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["status"] == "completed" and s["exit_code"] == 0 and s.get("gui_preserved", True) for s in steps), "five native steps")
    for name in ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"):
        ck(closure["source_hashes_before"][name] == sha(HERE / name), f"sealed script {name}")
    ck(closure["source_hashes_before"]["input"] == contract["terminal_input_sha256"] and
       closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json"), "sealed input/contract")
    roundtrip = load(RUN / "roundtrip-validation.json")
    authored = populated(parse(RUN / "input.json"))
    exported = populated(parse(RUN / "roundtrip-raw.json"))
    ck(roundtrip["passed"] and authored == {n: exported[n] for n in authored} and len(authored) == 30, "exact 30-table roundtrip")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       runlog.count("(warning #108)") == 1 and not re.search(r"\((?:error|warning|notice) #(?!108\))", runlog), "converter diagnostics")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    report = parse(RUN / "report-raw.json")
    ck(len(rows(report, "ResultSummary")) == 1, "valid native summary")
    summary = rows(report, "ResultSummary")[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 60, "summary horizon")
    sysrows, stockrows, resrows = (rows(report, n) for n in ("SystemResults", "StockTotalResults", "ResourceResults"))
    for name, data in (("system", sysrows), ("stock", stockrows), ("resource", resrows)):
        ck(len(data) == 120, f"{name} 120 half-hour rows")
        for i, row in enumerate(data):
            ck(abs(row["STINT"] - i / 2) < 1e-9 and abs(row["ETINT"] - (i + 1) / 2) < 1e-9, f"{name} bin {i}")

    fault = event_times(log, r"<TEACH-AIR-01,0> critical random failure added")
    aborted = event_times(log, r"<RISK-MISSION[^\n]*> mission aborted:")
    success = event_times(log, r"<[^\n]*> mission success:")
    cancelled = event_times(log, r"<BASIC-MISSION[^\n]*> mission cancelled:")
    surp = event_times(log, r" system SURP task 14 on <TEACH-AIR-01,0> started")
    surp_done = event_times(log, r" system SURP task 14 on <TEACH-AIR-01,0> completed")
    back = event_times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added")
    back_clear = event_times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder removed")
    remove = event_times(log, r" remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> completed")
    spare = event_times(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,2> from stock")
    incoming = event_times(log, r" transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started")
    outgoing = event_times(log, r" transport request <<TEACH-LRU-01,0,4>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
    arrival = event_times(log, r" transport task \d+ arrives with")
    ck(len(fault) == len(aborted) == 1 and abs(fault[0] - 46.4896) < 1e-4 and aborted == fault, "critical fault abort")
    ck(success == [23.5, 27.5] and cancelled == [50.25], "four mission outcomes")
    ck(len(surp) == len(back) == len(spare) == len(incoming) == 1 and all(abs(t - 47.9896) < 1e-4 for t in (surp[0], back[0], spare[0], incoming[0])), "depot supply initiates")
    ck(remove == outgoing == [48.1563], "failed LRU 4 sent upstream")
    ck(not surp_done and not back_clear and not arrival and "Replacement item arrives <TEACH-LRU-01,0,2>" not in log and
       "Start repair of item <TEACH-LRU-01,0,4>" not in log, "both transports and SURP open at 60")
    ck(log.count("transport time: 15") == 2 and len(event_times(log, r" transport task \d+ starts with 1 items/systems, transport time: 15")) == 2, "two 15-hour physical shipments")
    ck("system PM task 17 on <TEACH-AIR-01,0> started" in log and "system PM task 17 on <TEACH-AIR-01,0> completed" not in log and
       "system PM task 18 on <TEACH-AIR-01,1> completed" in log, "terminal PM distinction")

    worker = resource_intervals(log)
    waiting = waiting_intervals(log)
    ck(len(worker) >= 8 and len(waiting) == 4, "worker occupancy and request spans")
    for i, (s, st, rr) in enumerate(zip(sysrows, stockrows, resrows)):
        a, b = i / 2, (i + 1) / 2
        ck(abs((s["NSYA"] + s["NSYUA"]) - 2) < 1e-3, f"aircraft conservation bin {i}")
        ck(abs(s["NSYRP"] - exposure(surp[0], remove[0], a, b)) < 1e-3, f"active remove bin {i}")
        ck(abs(s["NSYWI"] - exposure(remove[0], 60, a, b)) < 1e-3, f"aircraft waits for item bin {i}")
        ck(abs(st["NBO"] - exposure(back[0], 60, a, b)) < 1e-3, f"base backorder bin {i}")
        ck(abs(rr["NRUM"] - sum(exposure(x, y, a, b) for x, y in worker)) < 1e-3, f"worker occupancy bin {i}")
        ck(abs(rr["NRW"] - sum(exposure(x, y, a, b) for x, y in waiting)) < 1e-3, f"worker wait bin {i}")
        ck(rr["NR"] == 2 and rr["NRF"] == 0 and 0 <= rr["NRUM"] <= 2.001 and 0 <= rr["NRW"] <= 2.001, f"resource bounds bin {i}")
        ck(st["NDD"] == st["NDR"] == 0 and 0 <= st["NBO"] <= 1.001, f"stock bounds bin {i}")
    ck(sum(s["NFAIL"] for s in sysrows) == 1 and sum(s["NREPT"] for s in sysrows) == 0 and
       sum(s["NPMS"] for s in sysrows) == 4 and sum(s["NPMT"] for s in sysrows) == 3, "failure/PM totals")
    ck(sum(st["NDF"] for st in stockrows) == 1 and abs(sum(st["NBO"] for st in stockrows) * 0.5 - (60 - back[0])) < 1e-3, "physical demand/backorder integral")
    ck(abs(sum(rr["NRUM"] for rr in resrows) * 0.5 - sum(y - x for x, y in worker)) < 1e-3 and
       abs(sum(rr["NRW"] for rr in resrows) * 0.5 - sum(y - x for x, y in waiting)) < 1e-3, "resource time integrals")
    ck(sysrows[-1]["NSYRY"] == 1 and sysrows[-1]["NSYWI"] == 1 and sysrows[-1]["NSYRP"] == 0 and
       stockrows[-1]["NBO"] == 1 and resrows[-1]["NRUM"] == resrows[-1]["NRW"] == 0, "last-bin terminal state")
    parent_report = parse(parent / "runs" / contract["accepted_parent"]["run_id"] / "report-raw.json")
    for name, child in (("SystemResults", sysrows), ("StockTotalResults", stockrows), ("ResourceResults", resrows)):
        baseline = rows(parent_report, name)
        ck(all(child[i] == baseline[i] for i in range(95)), f"{name} exact parent pre-route prefix")

    result = {"schema": "simlox-f02-var04-author-replay/v1", "run_id": RUN_ID,
              "passed": not failures, "checks": count, "failures": failures,
              "observed": {"fault_hour": fault, "backorder_hour": back, "inbound_lru_id": 2,
                           "outbound_lru_id": 4, "inbound_departure_hour": incoming,
                           "outbound_departure_hour": outgoing, "terminal_hour": 60,
                           "worker_intervals": worker, "worker_wait_intervals": waiting,
                           "terminal_aircraft_ready": sysrows[-1]["NSYRY"],
                           "terminal_aircraft_waiting_item": sysrows[-1]["NSYWI"],
                           "terminal_base_backorder": stockrows[-1]["NBO"]},
              "scope": "bounded_physical_transit_and_open_aircraft_repair_wait;reservation_unverified"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
