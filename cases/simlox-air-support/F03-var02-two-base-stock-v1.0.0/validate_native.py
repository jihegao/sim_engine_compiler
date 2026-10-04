"""Author replay of the bounded two-base BASE-01 opening-LRU-stock pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2"
TWO_BASE = HERE.parent / "F03-var01-two-base-crew-v1.0.0"
RUNS = {"depot_only": HERE / "runs/f03-stock-depot-v100-ssh-20261004-01",
        "forward_spare": HERE / "runs/f03-stock-forward-v100-ssh-20261004-01"}
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo",
       "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_rows(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def events(log: str, pattern: str) -> list[re.Match]:
    return list(re.finditer(r"^Time: ([\d.]+) " + pattern, log, re.M))


def overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo)) / (hi - lo)


def resource_usage(log: str) -> dict[tuple[str, str], list[tuple[float, float]]]:
    spans = {}
    for station in ("BASE-01", "BASE-02"):
        for rid in ("P-CREW", "P-MAINT"):
            starts = events(log, rf" <{rid} at <{station},0>> allocated to maintenance task: 1  available now: 0")
            ends = events(log, rf" <{rid} at <{station},0>> deallocated from  maintenance task: 1  available now: 1")
            assert len(starts) == len(ends) and all(float(a.group(1)) <= float(b.group(1)) for a, b in zip(starts, ends))
            spans[(station, rid)] = [(float(a.group(1)), float(b.group(1))) for a, b in zip(starts, ends)]
    return spans


def resource_queues(log: str) -> dict[tuple[str, str], list[tuple[float, float]]]:
    spans: dict[tuple[str, str], list[tuple[float, float]]] = {}
    pending: dict[tuple[str, str, str], float] = {}
    now = None
    task = None
    for line in log.splitlines():
        tick = re.match(r"^Time: ([\d.]+)", line)
        if tick:
            now = float(tick.group(1))
        test_task = re.match(r"^Time: [\d.]+  (.+?) resource availability test", line)
        if test_task:
            task = test_task.group(1)
        test = re.search(r"<(?P<rid>P-CREW|P-MAINT) at <(?P<station>BASE-0[12]),0>> request for: 1 (?P<state>failed|OK)", line)
        if not test:
            continue
        assert now is not None and task is not None
        key = (test.group("station"), test.group("rid"), task)
        if test.group("state") == "failed":
            pending.setdefault(key, now)
        elif key in pending:
            spans.setdefault(key[:2], []).append((pending.pop(key), now))
    assert not pending
    return spans


def main() -> None:
    failures: list[str] = []
    checks = 0

    def ck(condition: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck(contract["case_id"] == "F03" and contract["variant_id"] == "F03.var02" and
       sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen contract/diff")
    ck(sha(PARENT / "risk-input.json") == contract["accepted_risk_parent"]["input_sha256"] and
       sha(PARENT / "runs/f02-pair-v102-risk-ssh-20261004-01/closure.json") == contract["accepted_risk_parent"]["closure_sha256"] and
       sha(TWO_BASE / "staffed-input.json") == contract["accepted_two_base_precedent"]["staffed_input_sha256"], "accepted parents")
    ck(diff["sole_business_pair_change"] == {"table": "StockAllocation", "row": 1, "station": "BASE-01",
       "item": "TEACH-LRU-01", "field": "STSIZ", "depot_only": 0, "forward_spare": 1}, "sole stock field")
    reports = {}
    logs = {}
    for arm, run in RUNS.items():
        ck(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm], f"{arm} frozen input")
        invocation, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(closure["error"] is None and closure["run_id"] == run.name and closure["invocation_sha256"] == sha(run / "invocation.json") and
           closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"] and
           invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and
           invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
           f"{arm} native guards and closure")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
           all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps), f"{arm} native steps")
        ck(set(closure["raw"]) == RAW, f"{arm} 12 raw files")
        for name, meta in closure["raw"].items():
            path = run / name
            ck(path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"{arm} raw {name}")
        original, returned = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
        ck(len(original) == 30 and all(returned.get(name) == value for name, value in original.items()) and
           read(run / "roundtrip-validation.json")["passed"], f"{arm} exact 30-table roundtrip")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and runlog.count("(warning #108)") == 1 and
           not re.search(r"\((?:warning|notice) #(?!108\))", runlog), f"{arm} strict converter diagnostics")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        report = parse(run / "report-raw.json")
        logs[arm], reports[arm] = log, report
        ck([float(m.group(1)) for m in events(log, r"<TEACH-UNIT-2> mission ordered: BASE2-MISSION")] == [7] and
           [float(m.group(1)) for m in events(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission starting[^\n]+<TEACH-AIR-01,2>")] == [8] and
           [float(m.group(1)) for m in events(log, r"<BASE2-MISSION,TEACH-UNIT-2,[^>]+> mission success:")] == [10],
           f"{arm} BASE-02 success")
        faults = [(float(m.group(1)), int(m.group(2))) for m in events(log, r"<TEACH-AIR-01,([012])> critical random failure added")]
        ck(faults == [(22.24, 1), (46.7231, 0), (46.8394, 1)], f"{arm} matched fault samples")
        demands = [float(m.group(1)) for m in events(log, r"<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0>")]
        ck(demands == [23.74, 48.2231, 48.2231], f"{arm} three matched BASE-01 LRU demands")
        base2_demand = events(log, r"<TEACH-LRU-01,0,BASE-02,0> Item demand arrives")
        ck(not base2_demand, f"{arm} BASE-02 has no stock demand")
        starts = [float(m.group(1)) for m in events(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder added")]
        ends = [float(m.group(1)) for m in events(log, r"<TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2")]
        expected_starts = [23.74, 48.2231, 48.2231] if arm == "depot_only" else [48.2231]
        expected_ends = [25.74, 50.2231, 50.2231] if arm == "depot_only" else [50.2231]
        ck(starts == expected_starts and ends == expected_ends, f"{arm} backorder intervals")
        local_takes = [float(m.group(1)) for m in events(log, r"<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,\d+> from stock")]
        ck(local_takes == ([] if arm == "depot_only" else [23.74, 48.2231]), f"{arm} immediate local issue")
        depot_takes = [float(m.group(1)) for m in events(log, r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,\d+> from stock")]
        ck(depot_takes == [23.74, 48.2231, 48.2231], f"{arm} depot replenishment requests remain")
        completed = [(float(m.group(1)), int(m.group(2))) for m in events(log, r" system SURP task \d+ on <TEACH-AIR-01,([012])> completed")]
        expected_repairs = ([(26.0733, 1), (50.5565, 0), (50.8898, 1)] if arm == "depot_only"
                            else [(24.24, 1), (48.7231, 0), (50.5565, 1)])
        ck(completed == expected_repairs, f"{arm} aircraft repair times")
        basic_starts = [float(m.group(1)) for m in events(log, r"<BASIC-MISSION,TEACH-UNIT,[^>]+> mission starting")]
        ck(basic_starts == ([26.5733] if arm == "depot_only" else [24.75]) and
           [float(m.group(1)) for m in events(log, r"<BASIC-MISSION,TEACH-UNIT,[^>]+> mission cancelled:")] == [50.25],
           f"{arm} earlier BASIC mission launch, late cancellation")
        system, stock, resource = (table_rows(report, name) for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
        ck(all(len(rows) == 120 and all(abs(row["STINT"] - i*.5) < 1e-7 and abs(row["ETINT"] - (i+1)*.5) < 1e-7
           for i, row in enumerate(rows)) for rows in (system, stock, resource)), f"{arm} 120 aligned bins")
        ck(all(abs(row["NSYRY"] + row["NSYMA"] + row["NSYUA"] - 3) < 1e-4 for row in system), f"{arm} three-aircraft conservation")
        backorders = list(zip(starts, ends))
        used, queued = resource_usage(log), resource_queues(log)
        for i in range(120):
            lo, hi = i*.5, (i+1)*.5
            expected_nbo = sum(overlap(a, b, lo, hi) for a, b in backorders)
            expected_used = sum(overlap(a, b, lo, hi) for v in used.values() for a, b in v)
            expected_wait = sum(overlap(a, b, lo, hi) for v in queued.values() for a, b in v)
            ck(abs(stock[i]["NBO"] - expected_nbo) < 2e-4, f"{arm} stock backorder bin {i}")
            ck(resource[i]["NR"] == 4 and abs(resource[i]["NRUM"] - expected_used) < 2e-3 and
               abs(resource[i]["NRW"] - expected_wait) < 2e-3, f"{arm} resource bin {i}")
        ck(abs(sum(r["NBO"]*.5 for r in stock) - (6 if arm == "depot_only" else 2)) < 1e-4,
           f"{arm} backorder item-hours")
        ck(abs(sum(r["NSYMO"]*.5 for r in system) - 11.926181) < 1e-3 and
           abs(sum(r["NSYPM"]*.5 for r in system) - 6) < 1e-4, f"{arm} mission and PM aircraft-hours")
        summary = table_rows(report, "ResultSummary")[0]
        ck(all(abs(summary[k] - target) < 2e-6 for k, target in {"MTMF": .69630903, "MSTF": .8, "MSUF": .4, "STMF": .66256559}.items()),
           f"{arm} summary metrics")
        ck(system[-1]["NSYRY"] == 3 and all(system[-1][k] == 0 for k in ("NSYMA", "NSYUA", "NSYMP", "NSYRP")) and
           stock[-1]["NBO"] == 0 and resource[-1]["NRUM"] == resource[-1]["NRW"] == 0,
           f"{arm} terminal three ready/no queue/backorder")
    ck(table_rows(reports["depot_only"], "ResultSummary") == table_rows(reports["forward_spare"], "ResultSummary"),
       "paired summary unchanged despite earlier local recovery")
    result = {"schema": "simlox-f03-two-base-stock-author-replay/v1", "case_id": "F03", "variant_id": "F03.var02",
              "passed": not failures, "checks": checks, "failures": failures,
              "runs": {a: {"id": p.name, "closure_sha256": sha(p / "closure.json")} for a, p in RUNS.items()},
              "publication_state": "not_published"}
    target = HERE / "author-validation-2026-10-04.json"
    target.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(f"{checks-len(failures)}/{checks} checks: {target}")
    if failures:
        print(failures[:25])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
