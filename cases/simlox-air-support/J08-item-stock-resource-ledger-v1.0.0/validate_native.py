"""Author replay of J08 item, aggregate stock and resource ledgers."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2" / "runs" / "f02-pair-v102-risk-ssh-20261004-01"
NATIVE = HERE / "runs" / "j08-ledger-v100-ssh-20261004-01"
EMPTY = HERE / "runs" / "j08-item-report-v100-ssh-20261004-01"
FULL = HERE / "runs" / "j08-item-full-v100-ssh-20261004-01"
RAW_NATIVE = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
              "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def event_times(log: str, pattern: str) -> list[float]:
    return [float(m.group(1)) for m in re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M)]


def mean_on_interval(a: float, b: float, start: float, end: float) -> float:
    return max(0, min(b, end) - max(a, start)) / (end - start)


def resource_intervals(log: str) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    used = []
    for rid in ("P-CREW", "P-MAINT"):
        begin = event_times(log, rf" <{rid} at <BASE-01,0>> allocated to maintenance task: 1  available now: 0")
        end = event_times(log, rf" <{rid} at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1")
        assert len(begin) == len(end) and all(a < b for a, b in zip(begin, end))
        used.extend(zip(begin, end))
    queued = []
    current = None
    waiting: dict[str, float] = {}
    for line in log.splitlines():
        match = re.match(r"^Time: ([\d.]+)", line)
        if match:
            current = float(match.group(1))
        match = re.search(r"<(?P<rid>P-CREW|P-MAINT) at <BASE-01,0>> request for: 1 (?P<state>failed|OK)", line)
        if match:
            rid, state = match.group("rid"), match.group("state")
            assert current is not None
            if state == "failed":
                assert rid not in waiting
                waiting[rid] = current
            elif rid in waiting:
                queued.append((waiting.pop(rid), current))
    assert not waiting
    return used, queued


def main() -> None:
    checks = 0
    failures: list[str] = []

    def ck(name: str, condition: bool) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(name)

    contract, amendment = read(HERE / "contract.json"), read(HERE / "report-contract-amendment.json")
    ck("source and amendment pins", contract["case_id"] == "J08" and
       sha(HERE / "contract.json") == amendment["original_contract_sha256"] and
       sha(HERE / "native-input.json") == contract["child_input_sha256"] and
       sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    ck("accepted parent pins", sha(HERE.parent / contract["accepted_parent"]["package"] / "risk-input.json") == contract["accepted_parent"]["input_sha256"] and
       sha(PARENT / "closure.json") == contract["accepted_parent"]["closure_sha256"])
    ck("native closure SHA", sha(NATIVE / "closure.json") == amendment["native_closure_sha256"])
    native_closure, invocation, steps = (read(NATIVE / name) for name in ("closure.json", "invocation.json", "steps.json"))
    ck("native guards and source stability", native_closure["error"] is None and
       native_closure["invocation_sha256"] == sha(NATIVE / "invocation.json") and
       native_closure["source_hashes_before"] == native_closure["source_hashes_after"] == invocation["source_hashes_before"] and
       invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and
       "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("five native steps", [x["name"] for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(x["status"] == "completed" and x["exit_code"] == 0 for x in steps))
    ck("12 raw native files", set(native_closure["raw"]) == RAW_NATIVE)
    for name, meta in native_closure["raw"].items():
        ck("native raw " + name, (NATIVE / name).stat().st_size == meta["bytes"] and sha(NATIVE / name) == meta["sha256"])
    ck("roundtrip", read(NATIVE / "roundtrip-validation.json")["passed"] and
       populated(parse(NATIVE / "input.json")) == {k: v for k, v in populated(parse(NATIVE / "roundtrip-raw.json")).items() if k in populated(parse(NATIVE / "input.json"))})
    runlog = (NATIVE / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter warnings", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       runlog.count("(warning #108)") == 1 and not re.search(r"\((?:warning|notice) #(?!108\))", runlog))
    ck("physical log matches accepted parent", sha(NATIVE / "model.log") == sha(PARENT / "model.log"))
    ck("default report matches accepted parent", sha(NATIVE / "report-raw.json") == sha(PARENT / "report-raw.json"))

    empty_closure, full_closure = read(EMPTY / "closure.json"), read(FULL / "closure.json")
    ck("excluded selected diagnostic sealed", sha(EMPTY / "closure.json") == amendment["excluded_selected_report"]["closure_sha256"] and
       empty_closure["error"] is None and empty_closure["exit_code"] == 0 and
       "ItemResults" not in [t["name"] for t in parse(EMPTY / "item-report-raw.json")["report"]["tables"]])
    ck("full selector pins", sha(HERE / "runs" / "report-settings" / "item-position-results.sxs") == amendment["alternate_report"]["settings_sha256"] and
       full_closure["source_hashes_before"] == full_closure["source_hashes_after"] and full_closure["error"] is None and full_closure["exit_code"] == 0)
    for name, meta in full_closure["raw"].items():
        ck("full report raw " + name, (FULL / name).stat().st_size == meta["bytes"] and sha(FULL / name) == meta["sha256"])
    ck("full export completed", "Export completed!" in (FULL / "report-export.log").read_text(encoding="utf-8-sig"))

    report = parse(FULL / "item-report-raw.json")
    names = [t["name"] for t in report["report"]["tables"]]
    ck("item report table pair", names.count("ItemResults") == names.count("ItemResultsTotal") == 1)
    item, item_total = rows(report, "ItemResults"), rows(report, "ItemResultsTotal")
    stock, resource, system = (rows(report, name) for name in ("StockTotalResults", "ResourceResults", "SystemResults"))
    ck("120 aligned bins", all(len(t) == 120 and all(abs(row["STINT"] - i * .5) < 1e-7 and abs(row["ETINT"] - (i+1) * .5) < 1e-7 for i, row in enumerate(t)) for t in (item, stock, resource, system)))
    ck("selected item identity", all(r["IID"] == "TEACH-LRU-01" and r["STID"] == "DEPOT-01" for r in item) and len(item_total) == 1 and item_total[0]["IID"] == "TEACH-LRU-01" and item_total[0]["STID"] == "DEPOT-01")

    log = (NATIVE / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    back = event_times(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added")
    issue = event_times(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item")
    arrival = event_times(log, r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives")
    restored = event_times(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item")
    ck("one physical backorder, issue, arrival, return", all(len(v) == 1 for v in (back, issue, arrival, restored)))
    if all(len(v) == 1 for v in (back, issue, arrival, restored)):
        b, issued, arrived, restored_at = back[0], issue[0], arrival[0], restored[0]
        ck("transport and repair order", abs(b - issued) < 1e-4 and abs(arrived - issued - 2) < 1e-4 and arrived < restored_at < 60)
        for i, (ir, sr) in enumerate(zip(item, stock)):
            start, end = i*.5, (i+1)*.5
            ck(f"depot nominal/on-hand bin {i}", abs(ir["STSZ"] - 2) < 1e-6 and abs(ir["STOHA"] - (2 - mean_on_interval(issued, restored_at, start, end))) < 1e-3)
            ck(f"base backorder bin {i}", abs(sr["NBO"] - mean_on_interval(b, arrived, start, end)) < 1e-3)
        ck("item total is horizon mean", abs(item_total[0]["STSZ"] - 2) < 1e-6 and
           abs(item_total[0]["STOHA"] - (2 - (restored_at - issued)/60)) < 1e-4 and
           abs(item_total[0]["STOHA"] - sum(r["STOHA"] for r in item)/120) < 1e-5)
        demand_bin = int(b * 2)
        ck("waiting-time event metric", stock[demand_bin]["NWT"] == item[demand_bin]["NWT"] == 1 and
           all(abs(stock[demand_bin][f] - 2) < 1e-4 for f in ("WT", "WTT", "WTS")) and
           item_total[0]["NDF"] == item_total[0]["NWT"] == 1)
        ck("item backorder differs from aggregate", all(r["NBO"] == 0 for r in item) and sum(r["NBO"] for r in stock) > 0)

    used, waiting = resource_intervals(log)
    ck("resource queue exists", len(waiting) >= 3 and sum(b-a for a, b in waiting) > 0)
    for i, row in enumerate(resource):
        start, end = i*.5, (i+1)*.5
        expected_used = sum(mean_on_interval(a, b, start, end) for a, b in used)
        expected_wait = sum(mean_on_interval(a, b, start, end) for a, b in waiting)
        ck(f"resource used bin {i}", abs(row["NRUM"] - expected_used) < 1e-3 and row["NR"] == 2)
        ck(f"resource waiting bin {i}", abs(row["NRW"] - expected_wait) < 1e-3)
    ck("terminal ledger", item[-1]["STOHA"] == item[-1]["STSZ"] == 2 and stock[-1]["NBO"] == 0 and
       resource[-1]["NRW"] == resource[-1]["NRUM"] == 0 and system[-1]["NSYRY"] == 2)

    result = {"schema": "simlox-j08-author-ledger-replay/v1", "case_id": "J08", "passed": not failures,
              "checks": checks, "failures": failures,
              "observed": {"native_run": NATIVE.name, "empty_report_run": EMPTY.name, "full_report_run": FULL.name,
                           "native_closure_sha256": sha(NATIVE / "closure.json"), "full_report_closure_sha256": sha(FULL / "closure.json"),
                           "full_report_sha256": sha(FULL / "item-report-raw.json"),
                           "item_total_on_hand_mean": item_total[0]["STOHA"], "queue_intervals": waiting},
              "publication_state": "not_published"}
    target = HERE / "author-validation-2026-10-04.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{checks-len(failures)}/{checks} checks: {target}")
    if failures:
        print(failures[:20])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
